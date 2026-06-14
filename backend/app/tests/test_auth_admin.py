import importlib
import base64
import json
import logging
import sys
import types
import unittest
from types import SimpleNamespace

from fastapi import HTTPException


def install_lightweight_stubs():
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

    def get_db():
        raise AssertionError("database access is not expected in these tests")
        yield

    database_stub.get_db = get_db
    database_stub.SessionLocal = object
    database_stub.init_db = lambda: None
    sys.modules["utils.database"] = database_stub

    password_stub = types.ModuleType("utils.password")
    password_stub.verify_password = lambda password, hashed: password == hashed
    password_stub.hash_password = lambda password: password
    sys.modules["utils.password"] = password_stub

    if "fastapi_jwt" not in sys.modules:
        fastapi_jwt_stub = types.ModuleType("fastapi_jwt")

        class JwtAuthorizationCredentials:
            def __init__(self, subject=None):
                self.subject = subject or {}

        class JwtAccessBearerCookie:
            def __init__(self, *_, **__):
                pass

            def create_access_token(self, subject):
                header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode("utf-8")).rstrip(b"=")
                payload = base64.urlsafe_b64encode(json.dumps({"subject": subject}).encode("utf-8")).rstrip(b"=")
                return b".".join([header, payload, b""]).decode("ascii")

            async def __call__(self):
                return JwtAuthorizationCredentials()

        fastapi_jwt_stub.JwtAuthorizationCredentials = JwtAuthorizationCredentials
        fastapi_jwt_stub.JwtAccessBearerCookie = JwtAccessBearerCookie
        sys.modules["fastapi_jwt"] = fastapi_jwt_stub

    file_parse_stub = types.ModuleType("service.core.file_parse")
    file_parse_stub.execute_insert_process = lambda *_, **__: None
    sys.modules.setdefault("service.core.file_parse", file_parse_stub)

    file_utils_stub = types.ModuleType("service.core.api.utils.file_utils")
    file_utils_stub.get_project_base_directory = lambda: ""
    sys.modules.setdefault("service.core.api.utils.file_utils", file_utils_stub)

    retrieval_stub = types.ModuleType("service.core.retrieval")
    retrieval_stub.retrieve_content = lambda *_, **__: []
    sys.modules.setdefault("service.core.retrieval", retrieval_stub)

    chat_stub = sys.modules.get("service.core.chat") or types.ModuleType("service.core.chat")
    chat_stub.get_chat_completion = getattr(chat_stub, "get_chat_completion", lambda *_, **__: iter(()))
    chat_stub.update_session_name = getattr(chat_stub, "update_session_name", lambda *_, **__: None)
    chat_stub.write_chat_to_db = getattr(chat_stub, "write_chat_to_db", lambda *_, **__: None)
    sys.modules["service.core.chat"] = chat_stub

    knowledge_ops_stub = types.ModuleType("database.knowledgebase_operations")
    knowledge_ops_stub.insert_knowledgebase = lambda *_, **__: None
    knowledge_ops_stub.verify_user_knowledgebase = lambda *_, **__: True
    sys.modules.setdefault("database.knowledgebase_operations", knowledge_ops_stub)

    quick_parse_stub = types.ModuleType("service.quick_parse_service")
    quick_parse_stub.quick_parse_service = SimpleNamespace()
    sys.modules.setdefault("service.quick_parse_service", quick_parse_stub)

    upload_service_stub = types.ModuleType("service.document_upload_service")
    upload_service_stub.DocumentUploadService = object
    sys.modules.setdefault("service.document_upload_service", upload_service_stub)

    document_ops_stub = types.ModuleType("service.document_operations")
    document_ops_stub.delete_document = lambda *_, **__: None
    sys.modules.setdefault("service.document_operations", document_ops_stub)

    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    sys.modules.setdefault("openai", openai_stub)


install_lightweight_stubs()

from fastapi.routing import APIRoute

from models.user import User
from service import auth


def decode_jwt_payload(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))


class UserRoleStatusModelTests(unittest.TestCase):
    def test_user_model_defines_role_and_status_defaults(self):
        columns = User.__table__.columns

        self.assertIn("role", columns)
        self.assertIn("status", columns)
        self.assertFalse(columns["role"].nullable)
        self.assertFalse(columns["status"].nullable)
        self.assertEqual(columns["role"].default.arg, "user")
        self.assertEqual(columns["status"].default.arg, 1)


class AuthTokenTests(unittest.TestCase):
    def test_create_token_embeds_role_and_status_in_subject(self):
        token = auth.create_token(7, "admin-user", role="admin", status=1)

        claims = decode_jwt_payload(token)
        subject = claims["subject"]

        self.assertEqual(subject["user_id"], 7)
        self.assertEqual(subject["user_name"], "admin-user")
        self.assertEqual(subject["role"], "admin")
        self.assertEqual(subject["status"], 1)


class RequireAdminTests(unittest.IsolatedAsyncioTestCase):
    async def test_require_admin_allows_admin_subject(self):
        credentials = SimpleNamespace(subject={"role": "admin", "status": 1})

        result = await auth.require_admin(credentials)

        self.assertIs(result, credentials)

    async def test_require_admin_rejects_non_admin_subject(self):
        credentials = SimpleNamespace(subject={"role": "user", "status": 1})

        with self.assertRaises(HTTPException) as exc:
            await auth.require_admin(credentials)

        self.assertEqual(exc.exception.status_code, 403)


class RagentAdminRouteProtectionTests(unittest.TestCase):
    def test_management_routes_under_api_ragent_include_require_admin_dependency(self):
        install_lightweight_stubs()
        app_main = importlib.import_module("app_main")
        protected_paths = {
            route.path
            for route in app_main.app.routes
            if isinstance(route, APIRoute)
            and route.path.startswith("/api/ragent/")
            and (
                route.path.startswith("/api/ragent/intent-tree")
                or route.path.startswith("/api/ragent/users")
                or route.path.startswith("/api/ragent/user/password")
                or route.path.startswith("/api/ragent/admin/")
                or route.path.startswith("/api/ragent/knowledge-base")
                or route.path.startswith("/api/ragent/ingestion/")
                or route.path.startswith("/api/ragent/rag/settings")
                or route.path.startswith("/api/ragent/rag/traces/")
                or route.path.startswith("/api/ragent/mappings")
                or route.path.startswith("/api/ragent/sample-questions")
            )
        }

        self.assertTrue(protected_paths)
        for route in app_main.app.routes:
            if not isinstance(route, APIRoute) or route.path not in protected_paths:
                continue

            dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
            self.assertIn(auth.require_admin, dependency_calls, route.path)


if __name__ == "__main__":
    unittest.main()
