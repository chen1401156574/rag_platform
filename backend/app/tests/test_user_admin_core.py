import unittest
import asyncio
import logging
import sys
import types
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


if "colorlog" not in sys.modules:
    class PlainColoredFormatter(logging.Formatter):
        def __init__(self, fmt=None, datefmt=None, style="%", validate=True, *, defaults=None, **_):
            if fmt:
                fmt = fmt.replace("%(log_color)s", "")
            super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate, defaults=defaults)

    colorlog_stub = types.ModuleType("colorlog")
    colorlog_stub.StreamHandler = logging.StreamHandler
    colorlog_stub.ColoredFormatter = PlainColoredFormatter
    colorlog_stub.getLogger = logging.getLogger
    sys.modules["colorlog"] = colorlog_stub

database_stub = types.ModuleType("utils.database")
database_stub.get_db = lambda: iter(())
database_stub.SessionLocal = object
database_stub.init_db = lambda: None
sys.modules["utils.database"] = database_stub

if "fastapi_jwt" not in sys.modules:
    fastapi_jwt_stub = types.ModuleType("fastapi_jwt")

    class JwtAuthorizationCredentials:
        def __init__(self, subject=None):
            self.subject = subject or {}

    class JwtAccessBearerCookie:
        def __init__(self, *_, **__):
            pass

        def create_access_token(self, subject):
            return str(subject)

        async def __call__(self):
            return JwtAuthorizationCredentials()

    fastapi_jwt_stub.JwtAuthorizationCredentials = JwtAuthorizationCredentials
    fastapi_jwt_stub.JwtAccessBearerCookie = JwtAccessBearerCookie
    sys.modules["fastapi_jwt"] = fastapi_jwt_stub

from models.base import Base
from models.user import User
from router import user_admin_rt
from schemas.user_admin import UserCreatePayload, UserUpdatePayload
from utils.password import verify_password


class UserAdminCoreTableTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.credentials = SimpleNamespace(subject={"user_id": 1, "role": "admin"})

    def tearDown(self):
        self.engine.dispose()

    def test_user_model_has_admin_control_fields(self):
        columns = User.__table__.columns

        self.assertIn("role", columns)
        self.assertIn("status", columns)
        self.assertIn("deleted", columns)

    def test_admin_user_lifecycle_updates_login_users_table(self):
        asyncio.run(self._assert_admin_user_lifecycle_updates_login_users_table())

    async def _assert_admin_user_lifecycle_updates_login_users_table(self):
        db = self.SessionLocal()
        try:
            create_result = await user_admin_rt.create_user(
                UserCreatePayload(username="managed-user", password="secret", role="user", status=1),
                db,
                self.credentials,
            )
            self.assertEqual(create_result["code"], "0")

            user = db.query(User).filter(User.username == "managed-user").one()
            self.assertEqual(user.role, "user")
            self.assertEqual(user.status, 1)
            self.assertEqual(user.deleted, 0)
            self.assertTrue(verify_password("secret", user.password_hash))

            update_result = await user_admin_rt.update_user(
                str(user.id),
                UserUpdatePayload(role="admin", status=0),
                db,
                self.credentials,
            )
            self.assertEqual(update_result["code"], "0")
            db.refresh(user)
            self.assertEqual(user.role, "admin")
            self.assertEqual(user.status, 0)

            page_result = await user_admin_rt.get_users_page(
                current=1,
                size=10,
                keyword="managed",
                status=0,
                db=db,
                credentials=self.credentials,
            )
            self.assertEqual(page_result["code"], "0")
            self.assertEqual(page_result["data"]["total"], 1)
            self.assertEqual(page_result["data"]["records"][0]["status"], 0)

            delete_result = await user_admin_rt.delete_user(str(user.id), db, self.credentials)
            self.assertEqual(delete_result["code"], "0")
            db.refresh(user)
            self.assertEqual(user.deleted, 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
