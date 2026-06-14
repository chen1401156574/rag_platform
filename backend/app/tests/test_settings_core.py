import logging
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

from router import ragent_admin_rt


class RuntimeSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if hasattr(ragent_admin_rt, "reset_runtime_rag_settings"):
            ragent_admin_rt.reset_runtime_rag_settings()
        self.credentials = SimpleNamespace(subject={"role": "admin", "status": 1})

    async def test_save_runtime_rag_settings_updates_tunable_fields_and_masks_secrets(self):
        result = await ragent_admin_rt.save_rag_settings(
            {
                "rag": {
                    "retrieval": {"topK": 8},
                    "generation": {
                        "temperature": 0.25,
                        "promptTemplate": "Answer with citations for: {question}",
                    },
                },
                "ai": {
                    "chat": {"defaultModel": "deepseek-r1"},
                    "providers": {"dashscope": {"apiKey": "should-not-be-returned"}},
                },
            },
            self.credentials,
        )

        self.assertEqual(result["code"], "0")
        data = result["data"]
        self.assertEqual(data["rag"]["retrieval"]["topK"], 8)
        self.assertEqual(data["rag"]["generation"]["temperature"], 0.25)
        self.assertEqual(data["rag"]["generation"]["promptTemplate"], "Answer with citations for: {question}")
        self.assertEqual(data["ai"]["chat"]["defaultModel"], "deepseek-r1")
        self.assertIsNone(data["ai"]["providers"]["dashscope"]["apiKey"])

        read_back = await ragent_admin_rt.get_rag_settings(self.credentials)
        self.assertEqual(read_back["data"]["rag"]["retrieval"]["topK"], 8)
        self.assertEqual(read_back["data"]["rag"]["generation"]["temperature"], 0.25)

    async def test_save_runtime_rag_settings_rejects_out_of_range_values(self):
        result = await ragent_admin_rt.save_rag_settings(
            {"rag": {"retrieval": {"topK": 0}, "generation": {"temperature": 3}}},
            self.credentials,
        )

        self.assertEqual(result["code"], "400")


if __name__ == "__main__":
    unittest.main()
