import logging
import json
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


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
from service.settings_service import get_chat_openai_config


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
                    "retrieval": {
                        "topK": 8,
                        "vectorSimilarityWeight": 0.7,
                        "similarityThreshold": 0.2,
                        "candidateTop": 256,
                        "rerankEnabled": True,
                    },
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
        self.assertEqual(data["rag"]["retrieval"]["vectorSimilarityWeight"], 0.7)
        self.assertEqual(data["rag"]["retrieval"]["similarityThreshold"], 0.2)
        self.assertEqual(data["rag"]["retrieval"]["candidateTop"], 256)
        self.assertTrue(data["rag"]["retrieval"]["rerankEnabled"])
        self.assertEqual(data["rag"]["generation"]["temperature"], 0.25)
        self.assertEqual(data["rag"]["generation"]["promptTemplate"], "Answer with citations for: {question}")
        self.assertEqual(data["ai"]["chat"]["defaultModel"], "deepseek-v4-pro")
        self.assertIsNone(data["ai"]["providers"]["dashscope"]["apiKey"])

        read_back = await settings_rt.get_settings(db=self.db, _=self.credentials)
        self.assertEqual(read_back["data"]["rag"]["retrieval"]["topK"], 8)
        self.assertEqual(read_back["data"]["rag"]["retrieval"]["vectorSimilarityWeight"], 0.7)
        self.assertEqual(read_back["data"]["rag"]["generation"]["temperature"], 0.25)

    async def test_save_runtime_rag_settings_rejects_out_of_range_values(self):
        result = await settings_rt.save_settings(
            {"rag": {"retrieval": {"topK": 0}, "generation": {"temperature": 3}}},
            db=self.db,
            _=self.credentials,
        )

        self.assertEqual(result["code"], "400")

    async def test_save_runtime_rag_settings_rejects_invalid_retrieval_params(self):
        result = await settings_rt.save_settings(
            {"rag": {"retrieval": {"vectorSimilarityWeight": 1.5}}},
            db=self.db,
            _=self.credentials,
        )
        self.assertEqual(result["code"], "400")

        result = await settings_rt.save_settings(
            {"rag": {"retrieval": {"candidateTop": 5000}}},
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

    async def test_default_retrieval_config_keeps_rerank_enabled(self):
        result = await settings_rt.get_settings(db=self.db, _=self.credentials)
        retrieval = result["data"]["rag"]["retrieval"]

        self.assertTrue(retrieval["rerankEnabled"])


class ChatOpenAIConfigTests(unittest.TestCase):
    def test_deepseek_env_overrides_user_chat_openai_config(self):
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.example/v1",
                "DEEPSEEK_API_KEY": "deepseek-secret",
                "DEEPSEEK_MODEL": "deepseek-chat",
                "DASHSCOPE_BASE_URL": "https://dashscope.example/v1",
                "DASHSCOPE_API_KEY": "dashscope-secret",
            },
            clear=True,
        ):
            config = get_chat_openai_config({"ai": {"chat": {"defaultModel": "qwen2.5-72b-instruct"}}})

        self.assertEqual(config["provider"], "deepseek-openai-compatible")
        self.assertEqual(config["base_url"], "https://api.deepseek.example/v1")
        self.assertEqual(config["api_key"], "deepseek-secret")
        self.assertEqual(config["model"], "deepseek-chat")

    def test_chat_openai_config_falls_back_to_dashscope_when_deepseek_env_absent(self):
        with patch.dict(
            os.environ,
            {
                "DASHSCOPE_BASE_URL": "https://dashscope.example/v1",
                "DASHSCOPE_API_KEY": "dashscope-secret",
            },
            clear=True,
        ):
            config = get_chat_openai_config(
                {"ai": {"chat": {"defaultModel": "deepseek-v4-pro"}}},
                fallback_model="qwen2.5-7b-instruct",
            )

        self.assertEqual(config["provider"], "dashscope-openai-compatible")
        self.assertEqual(config["base_url"], "https://dashscope.example/v1")
        self.assertEqual(config["api_key"], "dashscope-secret")
        self.assertEqual(config["model"], "qwen2.5-7b-instruct")

    def test_partial_deepseek_env_is_rejected(self):
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.example/v1",
                "DEEPSEEK_API_KEY": "deepseek-secret",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "同时设置"):
                get_chat_openai_config({"ai": {"chat": {"defaultModel": "deepseek-v4-pro"}}})


if __name__ == "__main__":
    unittest.main()
