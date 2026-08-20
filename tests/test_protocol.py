import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from helper.protocol import classify_message, is_invalidation_push


class TestEnvelopeClassification(unittest.TestCase):
    def test_rpc_result(self):
        classified = classify_message({"id": "1", "result": {"type": "session_snapshot", "snapshot": {}}})
        self.assertEqual(classified["kind"], "rpc_result")
        self.assertFalse(is_invalidation_push(classified))

    def test_rpc_error(self):
        classified = classify_message({"id": "1", "error": {"code": "not_found", "message": "nope"}})
        self.assertEqual(classified["kind"], "rpc_error")

    def test_subscribe_ack(self):
        classified = classify_message({"id": "sub_1", "result": {"type": "subscription_started"}})
        self.assertEqual(classified["kind"], "subscribe_ack")
        self.assertFalse(is_invalidation_push(classified))

    def test_lifecycle_push_snake_case(self):
        classified = classify_message({
            "event": "workspace_created",
            "data": {"type": "workspace_created", "workspace": {"workspace_id": "w1"}},
        })
        self.assertEqual(classified["kind"], "lifecycle_push")
        self.assertTrue(is_invalidation_push(classified))

    def test_scoped_special_push_dotted(self):
        classified = classify_message({
            "event": "pane.agent_status_changed",
            "data": {"pane_id": "w1:p1", "workspace_id": "w1", "agent_status": "working"},
        })
        self.assertEqual(classified["kind"], "scoped_push")
        self.assertTrue(is_invalidation_push(classified))

    def test_wait_matched_is_not_a_subscription_push(self):
        top_level = classify_message({"type": "wait_matched", "event": {"event": "pane_created", "data": {}}})
        self.assertEqual(top_level["kind"], "unknown")
        self.assertFalse(is_invalidation_push(top_level))

        wait_rpc = classify_message({
            "id": "w1",
            "result": {"type": "wait_matched", "event": {"event": "pane_created", "data": {}}},
        })
        self.assertEqual(wait_rpc["kind"], "rpc_result")
        self.assertFalse(is_invalidation_push(wait_rpc))
