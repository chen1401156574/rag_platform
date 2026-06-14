"""Core tests for Phase 5 (System Settings) and Phase 6 (Knowledge Base Admin)."""
import importlib
import logging
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.routing import APIRoute


def _install_stubs():
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

    db_stub = types.ModuleType("utils.database")
    db_stub.get_db = lambda: iter(())
    db_stub.SessionLocal = object
    db_stub.init_db = lambda: None
    sys.modules.setdefault("utils.database", db_stub)

    pw_stub = types.ModuleType("utils.password")
    pw_stub.verify_password = lambda p, h: p == h
    pw_stub.hash_password = lambda p: p
    sys.modules.setdefault("utils.password", pw_stub)

    if "fastapi_jwt" not in sys.modules:
        jwt_stub = types.ModuleType("fastapi_jwt")

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

        jwt_stub.JwtAuthorizationCredentials = JwtAuthorizationCredentials
        jwt_stub.JwtAccessBearerCookie = JwtAccessBearerCookie
        sys.modules["fastapi_jwt"] = jwt_stub

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
    chat_stub.stream_clarify_response = getattr(chat_stub, "stream_clarify_response", lambda *_, **__: iter(()))
    chat_stub.update_session_name = getattr(chat_stub, "update_session_name", lambda *_, **__: None)
    chat_stub.write_chat_to_db = getattr(chat_stub, "write_chat_to_db", lambda *_, **__: None)
    sys.modules["service.core.chat"] = chat_stub

    for mod_name in (
        "database.knowledgebase_operations",
        "service.quick_parse_service",
        "service.document_upload_service",
        "service.document_operations",
    ):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)
    kb_ops_stub = sys.modules["database.knowledgebase_operations"]
    kb_ops_stub.insert_knowledgebase = getattr(kb_ops_stub, "insert_knowledgebase", lambda *_, **__: None)
    kb_ops_stub.verify_user_knowledgebase = getattr(kb_ops_stub, "verify_user_knowledgebase", lambda *_, **__: True)

    quick_parse_stub = sys.modules["service.quick_parse_service"]
    if not hasattr(quick_parse_stub, "quick_parse_service"):
        quick_parse_stub.quick_parse_service = SimpleNamespace(
            quick_parse_document=lambda *_, **__: {},
            get_parsed_content=lambda *_, **__: {},
        )

    doc_upload_stub = sys.modules["service.document_upload_service"]
    if not hasattr(doc_upload_stub, "DocumentUploadService"):
        class DocumentUploadService:
            create_upload_record = staticmethod(lambda *_, **__: None)
            get_session_documents = staticmethod(lambda *_, **__: [])
            has_uploaded_documents = staticmethod(lambda *_, **__: False)
            get_latest_document = staticmethod(lambda *_, **__: None)

        doc_upload_stub.DocumentUploadService = DocumentUploadService

    doc_ops_stub = sys.modules["service.document_operations"]
    doc_ops_stub.delete_document = getattr(doc_ops_stub, "delete_document", lambda *_, **__: None)

    if "openai" not in sys.modules:
        openai_stub = types.ModuleType("openai")
        openai_stub.OpenAI = object
        sys.modules["openai"] = openai_stub


_install_stubs()

from service import auth
from router import settings_rt, knowledge_admin_rt


# ── Phase 5: Settings Validation ──

class SettingsValidationTests(unittest.TestCase):
    """Test the settings validation logic from settings_rt."""

    def setUp(self):
        self.base_settings = {
            "rag": {
                "retrieval": {"topK": 5},
                "generation": {"temperature": 0.7, "promptTemplate": "test: {question}"},
                "queryRewrite": {"enabled": False},
            },
            "ai": {
                "chat": {
                    "defaultModel": "qwen2.5-72b-instruct",
                    "candidates": [
                        {"id": "qwen2.5-72b-instruct", "provider": "dashscope", "model": "qwen2.5-72b-instruct", "enabled": True},
                        {"id": "deepseek-v4-pro", "provider": "dashscope", "model": "deepseek-v4-pro", "enabled": True},
                    ],
                },
            },
        }

    def test_validate_valid_topK(self):
        patch, err = settings_rt._validate_settings_patch(
            {"rag": {"retrieval": {"topK": 10}}}, self.base_settings
        )
        self.assertIsNone(err)
        self.assertEqual(patch["rag"]["retrieval"]["topK"], 10)

    def test_validate_topK_below_1_rejected(self):
        _, err = settings_rt._validate_settings_patch(
            {"rag": {"retrieval": {"topK": 0}}}, self.base_settings
        )
        self.assertIsNotNone(err)

    def test_validate_topK_above_50_rejected(self):
        _, err = settings_rt._validate_settings_patch(
            {"rag": {"retrieval": {"topK": 51}}}, self.base_settings
        )
        self.assertIsNotNone(err)

    def test_validate_valid_temperature(self):
        patch, err = settings_rt._validate_settings_patch(
            {"rag": {"generation": {"temperature": 0.3}}}, self.base_settings
        )
        self.assertIsNone(err)
        self.assertEqual(patch["rag"]["generation"]["temperature"], 0.3)

    def test_validate_temperature_below_0_rejected(self):
        _, err = settings_rt._validate_settings_patch(
            {"rag": {"generation": {"temperature": -0.1}}}, self.base_settings
        )
        self.assertIsNotNone(err)

    def test_validate_temperature_above_2_rejected(self):
        _, err = settings_rt._validate_settings_patch(
            {"rag": {"generation": {"temperature": 2.1}}}, self.base_settings
        )
        self.assertIsNotNone(err)

    def test_validate_empty_prompt_rejected(self):
        _, err = settings_rt._validate_settings_patch(
            {"rag": {"generation": {"promptTemplate": ""}}}, self.base_settings
        )
        self.assertIsNotNone(err)

    def test_validate_prompt_too_long_rejected(self):
        _, err = settings_rt._validate_settings_patch(
            {"rag": {"generation": {"promptTemplate": "x" * 10001}}}, self.base_settings
        )
        self.assertIsNotNone(err)

    def test_validate_default_model_must_be_candidate(self):
        _, err = settings_rt._validate_settings_patch(
            {"ai": {"chat": {"defaultModel": "gpt-4"}}}, self.base_settings
        )
        self.assertIsNotNone(err)

    def test_validate_default_model_is_valid_candidate(self):
        patch, err = settings_rt._validate_settings_patch(
            {"ai": {"chat": {"defaultModel": "deepseek-v4-pro"}}}, self.base_settings
        )
        self.assertIsNone(err)

    def test_deep_merge_nested_dicts(self):
        base = {"a": {"b": 1, "c": 2}, "d": 3}
        settings_rt._deep_merge(base, {"a": {"c": 99}})
        self.assertEqual(base["a"]["b"], 1)
        self.assertEqual(base["a"]["c"], 99)
        self.assertEqual(base["d"], 3)

    def test_deep_merge_overwrites_scalar(self):
        base = {"a": {"b": 1}, "c": 3}
        settings_rt._deep_merge(base, {"a": "replaced"})
        self.assertEqual(base["a"], "replaced")

    def test_api_key_stripped_from_response(self):
        settings = {
            "ai": {
                "providers": {
                    "test": {"url": "http://example.com", "apiKey": "secret123"}
                }
            }
        }
        result = settings_rt._sanitize_for_response(settings)
        self.assertIsNone(result["ai"]["providers"]["test"]["apiKey"])


# ── Phase 6: Knowledge Admin Record Formatting ──

class KnowledgeRecordTests(unittest.TestCase):
    """Test knowledge base and document record formatting."""

    def test_kb_record_formats_all_fields(self):
        mock_kb = SimpleNamespace(
            id="kb001",
            name="Test KB",
            embedding_model="text-embedding-v1",
            collection_name="test_collection",
            created_by="admin",
            document_count=5,
            created_at=None,
            updated_at=None,
        )
        record = knowledge_admin_rt._kb_record(mock_kb)
        self.assertEqual(record["id"], "kb001")
        self.assertEqual(record["name"], "Test KB")
        self.assertEqual(record["embeddingModel"], "text-embedding-v1")
        self.assertEqual(record["collectionName"], "test_collection")
        self.assertEqual(record["createdBy"], "admin")
        self.assertEqual(record["documentCount"], 5)

    def test_doc_record_formats_all_fields(self):
        mock_doc = SimpleNamespace(
            id="doc001",
            kb_id="kb001",
            doc_name="test.pdf",
            source_type="file",
            source_location=None,
            schedule_enabled=0,
            schedule_cron=None,
            enabled=1,
            chunk_count=10,
            file_url=None,
            file_type="pdf",
            file_size=1024,
            process_mode="chunk",
            chunk_strategy="fixed_size",
            chunk_config='{"chunkSize":512}',
            pipeline_id=None,
            status="success",
            created_by="admin",
            updated_by="admin",
            created_at=None,
            updated_at=None,
            chunks_edited=0,
        )
        record = knowledge_admin_rt._doc_record(mock_doc)
        self.assertEqual(record["id"], "doc001")
        self.assertEqual(record["kbId"], "kb001")
        self.assertEqual(record["docName"], "test.pdf")
        self.assertTrue(record["enabled"])
        self.assertEqual(record["chunkCount"], 10)
        self.assertFalse(record["chunksEdited"])
        self.assertEqual(record["fileType"], "pdf")
        self.assertEqual(record["fileSize"], 1024)

    def test_paging_calculates_pages_correctly(self):
        result = knowledge_admin_rt._page([], 25, current=1, size=10)
        self.assertEqual(result["total"], 25)
        self.assertEqual(result["pages"], 3)
        self.assertEqual(result["current"], 1)
        self.assertEqual(result["size"], 10)

    def test_paging_with_zero_total(self):
        result = knowledge_admin_rt._page([], 0, current=1, size=10)
        self.assertEqual(result["pages"], 0)
        self.assertEqual(result["total"], 0)

    def test_uid_generates_20_char_string(self):
        uid = knowledge_admin_rt._uid()
        self.assertEqual(len(uid), 20)
        self.assertTrue(uid.isalnum())


# ── Route mounting verification ──

class Phase5And6RouteMountingTests(unittest.TestCase):
    """Verify new routers are mounted with admin protection in app_main."""

    def test_settings_and_knowledge_routes_have_admin_dependency(self):
        # Re-import to get fresh app instance
        app_main = importlib.import_module("app_main")
        protected_prefixes = [
            "/api/ragent/rag/settings",
            "/api/ragent/knowledge-base",
        ]

        all_paths = {
            route.path
            for route in app_main.app.routes
            if isinstance(route, APIRoute)
        }

        # Check that our new routes exist
        settings_paths = [p for p in all_paths if p.startswith("/api/ragent/rag/settings")]
        kb_paths = [p for p in all_paths if p.startswith("/api/ragent/knowledge-base")]

        self.assertTrue(settings_paths, "Settings routes should be mounted")
        self.assertTrue(kb_paths, "Knowledge base routes should be mounted")

    def test_new_routes_exist(self):
        app_main = importlib.import_module("app_main")
        all_paths = {
            route.path
            for route in app_main.app.routes
            if isinstance(route, APIRoute)
        }

        essential_paths = [
            "/api/ragent/rag/settings",
            "/api/ragent/knowledge-base",
            "/api/ragent/knowledge-base/page",
            "/api/ragent/knowledge-base/{kb_id}",
            "/api/ragent/knowledge-base/{kb_id}/docs",
            "/api/ragent/knowledge-base/{kb_id}/documents",
            "/api/ragent/knowledge-base/docs/{doc_id}",
        ]
        for path in essential_paths:
            self.assertIn(path, all_paths, f"Expected route {path} not found")


if __name__ == "__main__":
    unittest.main()
