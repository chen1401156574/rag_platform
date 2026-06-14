import logging
import json
import sys
import types
import unittest
from types import SimpleNamespace


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

from router import settings_rt
from models.system_config import SystemConfig


class _ScalarResult:
    def __init__(self, db):
        self.db = db

    def first(self):
        return self.db.row


class _FakeDb:
    def __init__(self):
        self.row = None
        self.committed = False
        self.rolled_back = False

    def scalars(self, *_):
        return _ScalarResult(self)

    def add(self, row):
        self.row = row

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class RuntimeSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = _FakeDb()
        self.credentials = SimpleNamespace(subject={"role": "admin", "status": 1})

    async def test_save_runtime_rag_settings_updates_tunable_fields_and_masks_secrets(self):
        result = await settings_rt.save_settings(
            {
                "rag": {
                    "retrieval": {"topK": 8},
                    "generation": {
                        "temperature": 0.25,
                        "promptTemplate": "Answer with citations for: {question}",
                    },
                },
                "ai": {
                    "chat": {"defaultModel": "deepseek-v4-pro"},
                    "providers": {"dashscope": {"apiKey": "should-not-be-returned"}},
                },
            },
            db=self.db,
            _=self.credentials,
        )

        self.assertEqual(result["code"], "0")
        data = result["data"]
        self.assertEqual(data["rag"]["retrieval"]["topK"], 8)
        self.assertEqual(data["rag"]["generation"]["temperature"], 0.25)
        self.assertEqual(data["rag"]["generation"]["promptTemplate"], "Answer with citations for: {question}")
        self.assertEqual(data["ai"]["chat"]["defaultModel"], "deepseek-v4-pro")
        self.assertIsNone(data["ai"]["providers"]["dashscope"]["apiKey"])

        read_back = await settings_rt.get_settings(db=self.db, _=self.credentials)
        self.assertEqual(read_back["data"]["rag"]["retrieval"]["topK"], 8)
        self.assertEqual(read_back["data"]["rag"]["generation"]["temperature"], 0.25)

    async def test_save_runtime_rag_settings_rejects_out_of_range_values(self):
        result = await settings_rt.save_settings(
            {"rag": {"retrieval": {"topK": 0}, "generation": {"temperature": 3}}},
            db=self.db,
            _=self.credentials,
        )

        self.assertEqual(result["code"], "400")

    async def test_saved_legacy_candidates_are_backfilled_with_deepseek_v4_pro(self):
        self.db.row = SystemConfig(
            config_key="rag_settings",
            config_value=json.dumps(
                {
                    "ai": {
                        "chat": {
                            "defaultModel": "qwen2.5-72b-instruct",
                            "candidates": [
                                {
                                    "id": "qwen2.5-72b-instruct",
                                    "provider": "dashscope",
                                    "model": "qwen2.5-72b-instruct",
                                    "enabled": True,
                                }
                            ],
                        }
                    }
                }
            ),
        )

        result = await settings_rt.get_settings(db=self.db, _=self.credentials)
        candidates = result["data"]["ai"]["chat"]["candidates"]

        self.assertIn("deepseek-v4-pro", {item["id"] for item in candidates})


if __name__ == "__main__":
    unittest.main()
