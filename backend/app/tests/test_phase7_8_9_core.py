"""Core tests for Phase 7 (Ingestion), Phase 8 (Trace), Phase 9 (Dashboard)."""
import logging
import sys
import types
import unittest
from types import SimpleNamespace
from datetime import datetime

# ── Stubs ──

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

if "fastapi_jwt" not in sys.modules:
    jwt_stub = types.ModuleType("fastapi_jwt")
    class JwtAuthorizationCredentials:
        def __init__(self, subject=None):
            self.subject = subject or {}
    class JwtAccessBearerCookie:
        def __init__(self, *_, **__): pass
        def create_access_token(self, subject): return str(subject)
        async def __call__(self): return JwtAuthorizationCredentials()
    jwt_stub.JwtAuthorizationCredentials = JwtAuthorizationCredentials
    jwt_stub.JwtAccessBearerCookie = JwtAccessBearerCookie
    sys.modules["fastapi_jwt"] = jwt_stub

for stub_name in (
    "service.core.file_parse", "service.core.api.utils.file_utils",
    "service.core.retrieval", "service.core.chat",
    "database.knowledgebase_operations", "service.quick_parse_service",
    "service.document_upload_service", "service.document_operations",
):
    if stub_name not in sys.modules:
        sys.modules[stub_name] = types.ModuleType(stub_name)
if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    sys.modules["openai"] = openai_stub

from router import ingestion_rt, trace_rt, dashboard_rt


class IngestionRecordTests(unittest.TestCase):
    """Test ingestion record formatting."""

    def test_pipeline_record_includes_nodes(self):
        p = SimpleNamespace(
            id="p1", name="Test Pipeline", description="desc",
            nodes_json='[{"nodeId":"n1","nodeType":"parser"}]',
            created_by="admin", created_at=datetime.now(), updated_at=datetime.now(),
        )
        record = ingestion_rt._pipeline_record(p)
        self.assertEqual(record["id"], "p1")
        self.assertEqual(record["name"], "Test Pipeline")
        self.assertEqual(len(record["nodes"]), 1)
        self.assertEqual(record["nodes"][0]["nodeId"], "n1")

    def test_task_record_formats_fields(self):
        t = SimpleNamespace(
            id="t1", pipeline_id="p1", source_type="file",
            source_location="/tmp/test.pdf", source_file_name="test.pdf",
            status="success", chunk_count=42, error_message=None,
            logs_json=None, metadata_json=None,
            started_at=None, completed_at=None,
            created_by="admin", created_at=datetime.now(), updated_at=datetime.now(),
        )
        record = ingestion_rt._task_record(t)
        self.assertEqual(record["id"], "t1")
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["chunkCount"], 42)
        self.assertEqual(record["sourceType"], "file")

    def test_pagination_helper(self):
        result = ingestion_rt._page([], 100, current=3, size=10)
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["pages"], 10)
        self.assertEqual(result["current"], 3)

    def test_uid_format(self):
        uid = ingestion_rt._uid()
        self.assertEqual(len(uid), 20)


class TraceRecordTests(unittest.TestCase):
    """Test trace record formatting."""

    def test_run_record_formats_all_fields(self):
        r = SimpleNamespace(
            trace_id="trace-abc-123",
            trace_name="test-trace", entry_method="chat",
            conversation_id="conv-1", task_id=None,
            user_name="admin", user_id="1",
            status="success", error_message=None,
            duration_ms=1500, ttft_ms=200,
            question="What is RAG?",
            start_time=datetime(2026, 6, 13, 10, 0, 0),
            end_time=datetime(2026, 6, 13, 10, 0, 1),
        )
        record = trace_rt._run_record(r)
        self.assertEqual(record["traceId"], "trace-abc-123")
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["durationMs"], 1500)
        self.assertEqual(record["ttftMs"], 200)
        self.assertEqual(record["question"], "What is RAG?")
        self.assertEqual(record["userName"], "admin")
        self.assertEqual(record["username"], "admin")

    def test_node_record_formats_fields(self):
        n = SimpleNamespace(
            trace_id="trace-abc-123", node_id="node-1",
            parent_node_id=None, depth=0,
            node_type="IntentClassify", node_name="Intent Classification",
            class_name=None, method_name=None,
            status="success", error_message=None,
            duration_ms=50, extra_data_json='{"score":0.95}',
            start_time=datetime(2026, 6, 13, 10, 0, 0),
            end_time=datetime(2026, 6, 13, 10, 0, 0),
        )
        record = trace_rt._node_record(n)
        self.assertEqual(record["nodeId"], "node-1")
        self.assertEqual(record["nodeType"], "IntentClassify")
        self.assertEqual(record["nodeName"], "Intent Classification")
        self.assertEqual(record["durationMs"], 50)
        self.assertEqual(record["extraData"], '{"score":0.95}')


class DashboardHelperTests(unittest.TestCase):
    """Test dashboard utility functions."""

    def test_window_hours_24h(self):
        self.assertEqual(dashboard_rt._window_hours("24h"), 24)

    def test_window_hours_7d(self):
        self.assertEqual(dashboard_rt._window_hours("7d"), 168)

    def test_window_hours_30d(self):
        self.assertEqual(dashboard_rt._window_hours("30d"), 720)

    def test_window_hours_unknown_defaults_to_24(self):
        self.assertEqual(dashboard_rt._window_hours("unknown"), 24)


class ModelDefinitionsTests(unittest.TestCase):
    """Verify models have expected table names and columns."""

    def test_ingestion_models_exist(self):
        from models.ingestion import IngestionPipeline, IngestionTask, IngestionTaskNode, IngestionChunkLog
        self.assertEqual(IngestionPipeline.__tablename__, "t_ingestion_pipeline")
        self.assertEqual(IngestionTask.__tablename__, "t_ingestion_task")
        self.assertEqual(IngestionTaskNode.__tablename__, "t_ingestion_task_node")
        self.assertEqual(IngestionChunkLog.__tablename__, "t_knowledge_document_chunk_log")

    def test_trace_models_exist(self):
        from models.trace import TraceRun, TraceNode
        self.assertEqual(TraceRun.__tablename__, "t_rag_trace_run")
        self.assertEqual(TraceNode.__tablename__, "t_rag_trace_node")
        # Verify key columns
        self.assertIn("trace_id", TraceRun.__table__.columns)
        self.assertIn("status", TraceRun.__table__.columns)
        self.assertIn("duration_ms", TraceRun.__table__.columns)
        self.assertIn("node_type", TraceNode.__table__.columns)
        self.assertIn("input_json", TraceNode.__table__.columns)
        self.assertIn("output_json", TraceNode.__table__.columns)

    def test_chunk_log_has_monitoring_columns(self):
        from models.ingestion import IngestionChunkLog
        cols = IngestionChunkLog.__table__.columns
        self.assertIn("extract_duration", cols)
        self.assertIn("chunk_duration", cols)
        self.assertIn("embed_duration", cols)
        self.assertIn("persist_duration", cols)
        self.assertIn("total_duration", cols)


class RouteAvailabilityTests(unittest.TestCase):
    """Verify new routers expose expected paths."""

    def test_ingestion_routes(self):
        paths = [r.path for r in ingestion_rt.router.routes]
        self.assertIn("/ingestion/stats", paths)
        self.assertIn("/ingestion/queue", paths)
        self.assertIn("/ingestion/pipelines", paths)
        self.assertIn("/ingestion/tasks", paths)

    def test_trace_routes(self):
        paths = [r.path for r in trace_rt.router.routes]
        self.assertIn("/rag/traces/runs", paths)
        self.assertIn("/trace/page", paths)

    def test_dashboard_routes(self):
        paths = [r.path for r in dashboard_rt.router.routes]
        self.assertIn("/admin/dashboard/overview", paths)
        self.assertIn("/admin/dashboard/performance", paths)
        self.assertIn("/admin/dashboard/trends", paths)
        self.assertIn("/dashboard/stats", paths)
        self.assertIn("/dashboard/trend", paths)


if __name__ == "__main__":
    unittest.main()
