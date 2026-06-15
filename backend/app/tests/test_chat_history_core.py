import logging
import sys
import types
import unittest
from datetime import datetime
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

db_stub = types.ModuleType("utils.database")
db_stub.get_db = lambda: iter(())
sys.modules.setdefault("utils.database", db_stub)

doc_ops_stub = types.ModuleType("service.document_operations")
doc_ops_stub.delete_document = lambda *_, **__: {"status": "success", "message": "ok"}
sys.modules.setdefault("service.document_operations", doc_ops_stub)

from router import history_rt


class ChatHistoryRecordTests(unittest.TestCase):
    def test_legacy_merged_question_is_split_for_display(self):
        merged = """用户原始提问：中午出差第二天晚上回去，可以报销多少钱

用户对追问的补充说明：上海

请基于以上完整信息生成回答。"""
        message = SimpleNamespace(
            message_id="m1",
            session_id="s1",
            user_question=merged,
            model_answer="回答",
            documents="[]",
            recommended_questions="[]",
            think=None,
            message_type="answer",
            metadata_json=None,
            created_at=datetime(2026, 6, 15, 10, 0, 0),
        )

        record = history_rt._message_record(message)

        self.assertEqual(record["user_question"], "上海")
        self.assertEqual(record["original_question"], "中午出差第二天晚上回去，可以报销多少钱")
        self.assertTrue(record["legacy_merged_clarification"])

    def test_clarify_message_metadata_is_exposed(self):
        message = SimpleNamespace(
            message_id="m2",
            session_id="s1",
            user_question="差旅报销怎么算？",
            model_answer="",
            documents="[]",
            recommended_questions="[]",
            think=None,
            message_type="clarify",
            metadata_json='{"original_question":"差旅报销怎么算？","clarifying_questions":["出差城市是哪座？"]}',
            created_at=datetime(2026, 6, 15, 10, 0, 0),
        )

        record = history_rt._message_record(message)

        self.assertEqual(record["message_type"], "clarify")
        self.assertEqual(record["original_question"], "差旅报销怎么算？")
        self.assertEqual(record["clarifying_questions"], ["出差城市是哪座？"])


if __name__ == "__main__":
    unittest.main()
