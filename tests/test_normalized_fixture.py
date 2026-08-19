import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestNormalizedFixture(unittest.TestCase):
    VALID_STATUSES = {"working", "blocked", "done", "idle", "unknown"}
    EXPECTED_COUNT_KEYS = {"working", "blocked", "done", "idle", "unknown", "total"}
    EXPECTED_AGENT_KEYS = {"pane_id", "name", "status", "focused", "workspace", "tab"}
    EXPECTED_WORKSPACE_KEYS = {"id", "label", "number"}
    EXPECTED_TAB_KEYS = {"id", "label", "number"}
    PRIVATE_FIELDS = {
        "cwd", "prompts", "pane_output", "terminal_id", "terminal_ids",
        "session_id", "session_ids", "token", "tokens", "username", "hostname",
        "absolute_path", "absolute_paths", "path", "paths", "terminal_title",
        "foreground_cwd", "revision", "agent_session", "agent_sessions"
    }

    @classmethod
    def setUpClass(cls):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "normalized_state.json")
        with open(fixture_path, "r", encoding="utf-8") as f:
            cls.fixture = json.load(f)

    def test_valid_json(self):
        self.assertIsInstance(self.fixture, dict)

    def test_exact_top_level_keys(self):
        self.assertEqual(set(self.fixture.keys()), {"agents", "counts"})

    def test_agents_is_list(self):
        self.assertIsInstance(self.fixture["agents"], list)

    def test_counts_is_dict(self):
        self.assertIsInstance(self.fixture["counts"], dict)

    def test_exact_agent_keys(self):
        for agent in self.fixture["agents"]:
            self.assertEqual(set(agent.keys()), self.EXPECTED_AGENT_KEYS)

    def test_exact_workspace_keys(self):
        for agent in self.fixture["agents"]:
            self.assertEqual(set(agent["workspace"].keys()), self.EXPECTED_WORKSPACE_KEYS)

    def test_exact_tab_keys(self):
        for agent in self.fixture["agents"]:
            self.assertEqual(set(agent["tab"].keys()), self.EXPECTED_TAB_KEYS)

    def test_supported_status_values_only(self):
        for agent in self.fixture["agents"]:
            self.assertIn(agent["status"], self.VALID_STATUSES)

    def test_exactly_five_agents(self):
        self.assertEqual(len(self.fixture["agents"]), 5)

    def test_all_five_statuses_represented(self):
        statuses = {agent["status"] for agent in self.fixture["agents"]}
        self.assertEqual(statuses, self.VALID_STATUSES)

    def test_counts_match_agent_records(self):
        counts = self.fixture["counts"]
        for status in self.VALID_STATUSES:
            actual = sum(1 for agent in self.fixture["agents"] if agent["status"] == status)
            self.assertEqual(counts[status], actual, f"Count mismatch for status '{status}'")

    def test_total_equals_number_of_agents(self):
        self.assertEqual(self.fixture["counts"]["total"], len(self.fixture["agents"]))

    def test_exactly_one_focused_agent(self):
        focused = sum(1 for agent in self.fixture["agents"] if agent["focused"])
        self.assertEqual(focused, 1)

    def test_at_least_two_workspaces(self):
        workspace_ids = {agent["workspace"]["id"] for agent in self.fixture["agents"]}
        self.assertGreaterEqual(len(workspace_ids), 2)

    def test_at_least_three_tabs(self):
        tab_ids = {agent["tab"]["id"] for agent in self.fixture["agents"]}
        self.assertGreaterEqual(len(tab_ids), 3)

    def test_exactly_two_workspaces(self):
        workspace_ids = {agent["workspace"]["id"] for agent in self.fixture["agents"]}
        self.assertEqual(len(workspace_ids), 2)

    def test_exactly_three_tabs(self):
        tab_ids = {agent["tab"]["id"] for agent in self.fixture["agents"]}
        self.assertEqual(len(tab_ids), 3)

    def test_workspace_with_multiple_tabs(self):
        agents_by_workspace = {}
        for agent in self.fixture["agents"]:
            ws_id = agent["workspace"]["id"]
            if ws_id not in agents_by_workspace:
                agents_by_workspace[ws_id] = set()
            agents_by_workspace[ws_id].add(agent["tab"]["id"])
        multi_tab_ws = [ws for ws, tabs in agents_by_workspace.items() if len(tabs) >= 2]
        self.assertGreaterEqual(len(multi_tab_ws), 1)

    def test_tab_with_multiple_agents(self):
        agents_by_tab = {}
        for agent in self.fixture["agents"]:
            tab_id = agent["tab"]["id"]
            if tab_id not in agents_by_tab:
                agents_by_tab[tab_id] = []
            agents_by_tab[tab_id].append(agent)
        multi_agent_tabs = [tab for tab, agents in agents_by_tab.items() if len(agents) >= 2]
        self.assertGreaterEqual(len(multi_agent_tabs), 1)

    def test_pane_ids_unique(self):
        pane_ids = [agent["pane_id"] for agent in self.fixture["agents"]]
        self.assertEqual(len(pane_ids), len(set(pane_ids)))

    def test_no_private_fields_in_agents(self):
        for agent in self.fixture["agents"]:
            agent_keys = set(agent.keys())
            private_in_agent = agent_keys & self.PRIVATE_FIELDS
            self.assertEqual(private_in_agent, set(), f"Private fields in agent: {private_in_agent}")
            workspace_keys = set(agent["workspace"].keys())
            private_in_ws = workspace_keys & self.PRIVATE_FIELDS
            self.assertEqual(private_in_ws, set(), f"Private fields in workspace: {private_in_ws}")
            tab_keys = set(agent["tab"].keys())
            private_in_tab = tab_keys & self.PRIVATE_FIELDS
            self.assertEqual(private_in_tab, set(), f"Private fields in tab: {private_in_tab}")

    def test_no_private_fields_in_counts(self):
        count_keys = set(self.fixture["counts"].keys())
        private_in_counts = count_keys & self.PRIVATE_FIELDS
        self.assertEqual(private_in_counts, set(), f"Private fields in counts: {private_in_counts}")

    def test_fixture_survives_json_round_trip(self):
        snapshot = self.fixture
        for _ in range(3):
            json_str = json.dumps(snapshot)
            snapshot = json.loads(json_str)
        self.assertEqual(snapshot, self.fixture)


if __name__ == "__main__":
    unittest.main()
