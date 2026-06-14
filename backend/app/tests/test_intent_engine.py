import unittest
import logging
import sys
import types
from types import SimpleNamespace

from schemas.intent import IntentNodeCreateRequest

if "colorlog" not in sys.modules:
    class PlainColoredFormatter(logging.Formatter):
        def __init__(self, fmt=None, datefmt=None, style="%", validate=True, *, defaults=None, **_):
            super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate, defaults=defaults)

    colorlog_stub = types.ModuleType("colorlog")
    colorlog_stub.StreamHandler = logging.StreamHandler
    colorlog_stub.ColoredFormatter = PlainColoredFormatter
    colorlog_stub.getLogger = logging.getLogger
    sys.modules["colorlog"] = colorlog_stub

chat_stub = types.ModuleType("service.core.chat")
chat_stub.get_chat_completion = lambda *_, **__: iter(())
chat_stub.stream_clarify_response = lambda *_, **__: iter(())
chat_stub.update_session_name = lambda *_, **__: None
chat_stub.write_chat_to_db = lambda *_, **__: None
sys.modules["service.core.chat"] = chat_stub

from service.intent_engine import (
    INTENT_KIND_KB,
    INTENT_KIND_MCP,
    INTENT_KIND_SYSTEM,
    IntentClassification,
    IntentRouter,
)


def make_intent(**overrides):
    values = {
        "id": "intent-1",
        "intent_code": "kb-it",
        "name": "IT Support",
        "kind": INTENT_KIND_KB,
        "level": 2,
        "collection_name": None,
        "kb_id": None,
        "top_k": None,
        "mcp_tool_id": None,
        "prompt_snippet": None,
        "prompt_template": None,
        "param_prompt_template": None,
        "description": None,
        "examples": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StubClassifier:
    def __init__(self, classification):
        self.classification = classification

    def classify(self, db, question):
        return self.classification


class IntentSchemaTests(unittest.TestCase):
    def test_create_request_accepts_collection_name(self):
        payload = IntentNodeCreateRequest(
            intentCode="kb-it",
            name="IT Support",
            level=2,
            kind=INTENT_KIND_KB,
            collectionName="tenant-it",
        )

        self.assertEqual(payload.collectionName, "tenant-it")


class IntentRouterTests(unittest.TestCase):
    def test_kb_intent_keeps_classification_but_uses_default_rag_route(self):
        intent = make_intent(collection_name="tenant-it", kb_id="kb-001", top_k=3)
        router = IntentRouter(StubClassifier(IntentClassification(intent=intent, score=0.91)))

        decision = router.decide(db=None, question="How do I configure VPN?", user_id="user-1")

        self.assertEqual(decision.kind, INTENT_KIND_KB)
        self.assertEqual(decision.intent.intent_code, "kb-it")
        self.assertEqual(decision.collection_name, "user-1")
        self.assertIsNone(decision.kb_ids)
        self.assertEqual(decision.top_k, 5)

    def test_kb_intent_without_collection_uses_default_rag_route(self):
        intent = make_intent(collection_name=None, kb_id="legacy-tenant", top_k=None)
        router = IntentRouter(StubClassifier(IntentClassification(intent=intent, score=0.8)))

        decision = router.decide(db=None, question="What is the invoice title?", user_id="user-1")

        self.assertEqual(decision.kind, INTENT_KIND_KB)
        self.assertEqual(decision.collection_name, "user-1")
        self.assertIsNone(decision.kb_ids)
        self.assertEqual(decision.top_k, 5)

    def test_system_intent_keeps_match_but_uses_default_rag_route(self):
        intent = make_intent(kind=INTENT_KIND_SYSTEM, intent_code="sys-hi")
        router = IntentRouter(StubClassifier(IntentClassification(intent=intent, score=0.9)))

        decision = router.decide(db=None, question="hello", user_id="user-1")

        self.assertEqual(decision.kind, INTENT_KIND_KB)
        self.assertEqual(decision.intent.intent_code, "sys-hi")
        self.assertEqual(decision.collection_name, "user-1")
        self.assertIsNone(decision.kb_ids)
        self.assertEqual(decision.top_k, 5)

    def test_mcp_intent_keeps_match_but_uses_default_rag_route(self):
        intent = make_intent(kind=INTENT_KIND_MCP, intent_code="sales-stats", mcp_tool_id="sales")
        router = IntentRouter(StubClassifier(IntentClassification(intent=intent, score=0.9)))

        decision = router.decide(db=None, question="today sales", user_id="user-1")

        self.assertEqual(decision.kind, INTENT_KIND_KB)
        self.assertEqual(decision.intent.intent_code, "sales-stats")
        self.assertEqual(decision.collection_name, "user-1")
        self.assertIsNone(decision.kb_ids)
        self.assertEqual(decision.top_k, 5)


if __name__ == "__main__":
    unittest.main()
