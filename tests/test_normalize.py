import copy
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
                {"pane_id": "w1:p1", "agent": "test", "agent_status": "unknown_status", "tab_id": "w1:t1", "workspace_id": "w1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["status"], "unknown")

    def test_normalize_multiple_workspaces_and_tabs(self):
        snapshot = {
            "workspaces": [
                {"workspace_id": "w1", "number": 1, "label": "Project"},
                {"workspace_id": "w2", "number": 2, "label": "Development"},
            ],
            "tabs": [
                {"tab_id": "w1:t1", "workspace_id": "w1", "number": 1, "label": "1"},
                {"tab_id": "w2:t1", "workspace_id": "w2", "number": 1, "label": "1"},
            ],
            "agents": [
                {"pane_id": "w1:p1", "agent": "agent1", "workspace_id": "w1", "tab_id": "w1:t1"},
                {"pane_id": "w2:p1", "agent": "agent2", "workspace_id": "w2", "tab_id": "w2:t1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(len(result["agents"]), 2)
        self.assertEqual(result["agents"][0]["workspace"]["id"], "w1")
        self.assertEqual(result["agents"][0]["workspace"]["label"], "Project")
        self.assertEqual(result["agents"][0]["workspace"]["number"], 1)
        self.assertEqual(result["agents"][0]["tab"]["id"], "w1:t1")
        self.assertEqual(result["agents"][0]["tab"]["label"], "1")
        self.assertEqual(result["agents"][0]["tab"]["number"], 1)

    def test_normalize_all_statuses(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "agent_status": "working", "workspace_id": "w1"},
                {"pane_id": "w1:p2", "agent": "a2", "agent_status": "blocked", "workspace_id": "w1"},
                {"pane_id": "w1:p3", "agent": "a3", "agent_status": "done", "workspace_id": "w1"},
                {"pane_id": "w1:p4", "agent": "a4", "agent_status": "idle", "workspace_id": "w1"},
                {"pane_id": "w1:p5", "agent": "a5", "agent_status": "unknown", "workspace_id": "w1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(len(result["agents"]), 5)
        self.assertEqual(result["counts"]["working"], 1)
        self.assertEqual(result["counts"]["blocked"], 1)
        self.assertEqual(result["counts"]["done"], 1)
        self.assertEqual(result["counts"]["idle"], 1)
        self.assertEqual(result["counts"]["unknown"], 1)
        self.assertEqual(result["counts"]["total"], 5)

    def test_unsupported_status_becomes_unknown(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "agent_status": "paused", "workspace_id": "w1"},
                {"pane_id": "w1:p2", "agent": "a2", "agent_status": "unknown_status", "workspace_id": "w1"},
                {"pane_id": "w1:p3", "agent": "a3", "agent_status": "pending", "workspace_id": "w1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["status"], "unknown")
        self.assertEqual(result["agents"][1]["status"], "unknown")
        self.assertEqual(result["agents"][2]["status"], "unknown")
        self.assertEqual(result["counts"]["unknown"], 3)
        self.assertEqual(result["counts"]["working"], 0)

    def test_all_count_keys_present_when_zero(self):
        snapshot = {
            "agents": [],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertIn("working", result["counts"])
        self.assertIn("blocked", result["counts"])
        self.assertIn("done", result["counts"])
        self.assertIn("idle", result["counts"])
        self.assertIn("unknown", result["counts"])
        self.assertIn("total", result["counts"])
        self.assertEqual(result["counts"]["total"], 0)

    def test_identity_fallback_from_name_to_agent(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "name": "alice", "workspace_id": "w1"},
                {"pane_id": "w1:p2", "agent": "bob", "workspace_id": "w1"},
                {"pane_id": "w1:p3", "name": "charlie", "agent": "charlie-agent", "workspace_id": "w1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["name"], "alice")
        self.assertEqual(result["agents"][1]["name"], "bob")
        self.assertEqual(result["agents"][2]["name"], "charlie")

    def test_identityless_entries_skipped(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "workspace_id": "w1"},
                {"pane_id": "w1:p2", "name": "", "agent": "", "workspace_id": "w1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(len(result["agents"]), 0)

    def test_missing_workspace_reference_fallback(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "missing-ws", "tab_id": "w1:t1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["workspace"]["id"], "missing-ws")
        self.assertEqual(result["agents"][0]["workspace"]["label"], "missing-ws")
        self.assertEqual(result["agents"][0]["workspace"]["number"], 0)

    def test_missing_tab_reference_fallback(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1", "tab_id": "missing-tab"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["tab"]["id"], "missing-tab")
        self.assertEqual(result["agents"][0]["tab"]["label"], "missing-tab")
        self.assertEqual(result["agents"][0]["tab"]["number"], 0)

    def test_missing_workspace_and_tab_reference_fallback(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "missing", "tab_id": "missing"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["workspace"]["id"], "missing")
        self.assertEqual(result["agents"][0]["workspace"]["label"], "missing")
        self.assertEqual(result["agents"][0]["workspace"]["number"], 0)
        self.assertEqual(result["agents"][0]["tab"]["id"], "missing")
        self.assertEqual(result["agents"][0]["tab"]["label"], "missing")
        self.assertEqual(result["agents"][0]["tab"]["number"], 0)

    def test_private_fields_excluded(self):
        snapshot = {
            "agents": [
                {
                    "pane_id": "w1:p1",
                    "agent": "a1",
                    "name": "a1",
                    "agent_status": "working",
                    "workspace_id": "w1",
                    "tab_id": "w1:t1",
                    "terminal_id": "term-123",
                    "revision": 5,
                    "cwd": "/sensitive/path",
                    "terminal_title": "title",
                }
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertNotIn("terminal_id", result["agents"][0])
        self.assertNotIn("revision", result["agents"][0])
        self.assertNotIn("cwd", result["agents"][0])
        self.assertNotIn("terminal_title", result["agents"][0])

    def test_input_snapshot_unchanged(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1"},
            ],
            "workspaces": [{"workspace_id": "w1", "number": 1, "label": "Test"}],
            "tabs": [{"tab_id": "w1:t1", "workspace_id": "w1", "number": 1, "label": "1"}],
        }
        snapshot_copy = copy.deepcopy(snapshot)
        self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(snapshot, snapshot_copy)

    def test_focused_preserved(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "focused": True, "workspace_id": "w1"},
                {"pane_id": "w1:p2", "agent": "a2", "focused": False, "workspace_id": "w1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertTrue(result["agents"][0]["focused"])
        self.assertFalse(result["agents"][1]["focused"])

    def test_workspace_tab_fields_from_records(self):
        snapshot = {
            "workspaces": [
                {"workspace_id": "w1", "number": 3, "label": "My Workspace"},
            ],
            "tabs": [
                {"tab_id": "w1:t1", "workspace_id": "w1", "number": 2, "label": "Code"},
            ],
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1", "tab_id": "w1:t1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["workspace"]["id"], "w1")
        self.assertEqual(result["agents"][0]["workspace"]["label"], "My Workspace")
        self.assertEqual(result["agents"][0]["workspace"]["number"], 3)
        self.assertEqual(result["agents"][0]["tab"]["id"], "w1:t1")
        self.assertEqual(result["agents"][0]["tab"]["label"], "Code")
        self.assertEqual(result["agents"][0]["tab"]["number"], 2)

    def test_status_becomes_unknown_when_missing(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["status"], "unknown")
        self.assertEqual(result["counts"]["unknown"], 1)

    def test_empty_workspace_id_fallback(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "", "tab_id": "w1:t1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["workspace"]["id"], "")
        self.assertEqual(result["agents"][0]["workspace"]["label"], "")
        self.assertEqual(result["agents"][0]["workspace"]["number"], 0)

    def test_empty_tab_id_fallback(self):
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1", "tab_id": ""},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["tab"]["id"], "")
        self.assertEqual(result["agents"][0]["tab"]["label"], "")
        self.assertEqual(result["agents"][0]["tab"]["number"], 0)

    def test_real_record_number_one_preserved(self):
        snapshot = {
            "workspaces": [
                {"workspace_id": "w1", "number": 1, "label": "Workspace One"},
            ],
            "tabs": [
                {"tab_id": "w1:t1", "workspace_id": "w1", "number": 1, "label": "Tab One"},
            ],
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1", "tab_id": "w1:t1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["workspace"]["number"], 1)
        self.assertEqual(result["agents"][0]["tab"]["number"], 1)

    def test_no_snapshot_state_after_normalization(self):
        normalizer = Normalizer()
        snapshot = {
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1"},
            ],
        }
        normalizer.normalize_snapshot(snapshot)
        self.assertFalse(hasattr(normalizer, "_snapshot"))

    def test_label_fallback_to_id_when_missing(self):
        snapshot = {
            "workspaces": [
                {"workspace_id": "w1", "number": 1},
            ],
            "tabs": [
                {"tab_id": "w1:t1", "workspace_id": "w1", "number": 1},
            ],
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1", "tab_id": "w1:t1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["workspace"]["label"], "w1")
        self.assertEqual(result["agents"][0]["tab"]["label"], "w1:t1")

    def test_number_zero_when_missing_in_record(self):
        snapshot = {
            "workspaces": [
                {"workspace_id": "w1", "label": "W"},
            ],
            "tabs": [
                {"tab_id": "w1:t1", "workspace_id": "w1", "label": "T"},
            ],
            "agents": [
                {"pane_id": "w1:p1", "agent": "a1", "workspace_id": "w1", "tab_id": "w1:t1"},
            ],
        }
        result = self.normalizer.normalize_snapshot(snapshot)
        self.assertEqual(result["agents"][0]["workspace"]["number"], 0)
        self.assertEqual(result["agents"][0]["tab"]["number"], 0)


if __name__ == "__main__":
    unittest.main()
