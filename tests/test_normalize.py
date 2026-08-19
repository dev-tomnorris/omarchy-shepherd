import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from helper.normalize import Normalizer


class TestNormalizer(unittest.TestCase):
    def setUp(self):
        self.normalizer = Normalizer()

    def test_normalize_basic_agent(self):
        snapshot = {
            "agents": [
                {
                    "pane_id": "w1:p1",
                    "agent": "opencode",
                    "name": "opencode",
                    "agent_status": "working",
                    "focused": True,
                    "tab_id": "w1:t1",
                    "workspace_id": "w1",
                }
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["pane_id"], "w1:p1")
        self.assertEqual(result["agents"][0]["status"], "working")

    def test_normalize_unknown_status(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent_status": "unknown_status", "tab_id": "w1:t1", "workspace_id": "w1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["status"], "unknown")
