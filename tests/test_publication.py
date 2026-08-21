"""Publication contract: semantic normalized-state deduplication."""

import copy
import json
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fakes.fake_herdr import FakeHerdrServer
from helper.runtime import publication_fingerprint
from support import JsonlSink, make_helper, wait_until


class TestPublicationFingerprint(unittest.TestCase):
    def test_fingerprint_is_order_stable_and_excludes_private_keys(self):
        state = {
            "agents": [
                {
                    "pane_id": "w1:p1",
                    "name": "a",
                    "status": "idle",
                    "focused": False,
                    "workspace": {"id": "w1", "label": "W", "number": 1},
                    "tab": {"id": "w1:t1", "label": "T", "number": 1},
                }
            ],
            "counts": {"working": 0, "blocked": 0, "done": 0, "idle": 1, "unknown": 0, "total": 1},
            # Must never affect publication identity / diagnostics
            "socket_path": "/secret/path.sock",
            "hostname": "secret-host",
        }
        a = publication_fingerprint(state, "connected", False)
        b = publication_fingerprint(state, "connected", False)
        self.assertEqual(a, b)
        self.assertNotIn("secret", a)
        self.assertNotIn("hostname", a)
        self.assertNotIn("socket_path", a)
        # connection/stale participate
        self.assertNotEqual(a, publication_fingerprint(state, "disconnected", True))


class TestStatePublication(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.socket_path = os.path.join(self.temp_dir, "herdr.sock")
        self.server = FakeHerdrServer(self.socket_path)
        self.server.start()
        self.sink = JsonlSink()
        stdin_r, stdin_w = os.pipe()
        self.stdin_read = os.fdopen(stdin_r)
        self.stdin_write = os.fdopen(stdin_w, "w")
        self.helper = make_helper(
            self.socket_path,
            debounce_s=0.08,
            recv_timeout=0.05,
            rpc_timeout=2.0,
            backoff_initial=0.05,
            backoff_max=0.2,
            infile=self.stdin_read,
            outfile=self.sink,
        )
        self.thread = threading.Thread(target=self.helper.run, name="shepherd-run")
        self.thread.start()
        self.assertTrue(wait_until(lambda: len(self.sink.of_type("state")) >= 1))

    def tearDown(self):
        self.helper.stop()
        self.thread.join(timeout=3.0)
        try:
            self.stdin_write.close()
        except OSError:
            pass
        try:
            self.stdin_read.close()
        except OSError:
            pass
        self.server.stop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _states(self):
        return self.sink.of_type("state")

    def test_initial_publication_is_single_connected_state(self):
        time.sleep(0.2)
        states = self._states()
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["connection"], "connected")
        self.assertFalse(states[0]["stale"])
        self.assertEqual(states[0]["counts"]["total"], 2)
        self.assertIn("presentation", states[0])
        self.assertEqual(set(states[0]["presentation"].keys()), {"kind", "supported", "app_id", "argv"})

    def test_duplicate_invalidations_do_not_republish_unchanged_state(self):
        before = len(self._states())
        for _ in range(8):
            self.server.push_lifecycle(
                "pane_focused",
                {"type": "pane_focused", "pane_id": "w1:p1", "workspace_id": "w1"},
            )
        self.assertTrue(
            wait_until(
                lambda: len([r for r in self.server.rpc_records() if r.methods == ["session.snapshot"]]) >= 2,
                timeout=2.0,
            )
        )
        time.sleep(0.2)
        self.assertEqual(len(self._states()), before)

    def test_actual_status_change_publishes(self):
        before = len(self._states())
        snapshot = copy.deepcopy(self.server.snapshot)
        for agent in snapshot["agents"]:
            if agent["pane_id"] == "w1:p1":
                agent["agent_status"] = "blocked"
        self.server.snapshot = snapshot
        self.server.push_scoped(
            "pane.agent_status_changed",
            {"pane_id": "w1:p1", "agent_status": "blocked"},
        )
        self.assertTrue(wait_until(lambda: len(self._states()) > before, timeout=2.0))
        latest = self._states()[-1]
        statuses = {a["pane_id"]: a["status"] for a in latest["agents"]}
        self.assertEqual(statuses.get("w1:p1"), "blocked")
        self.assertEqual(latest["connection"], "connected")

    def test_workspace_label_change_publishes(self):
        before = len(self._states())
        snapshot = copy.deepcopy(self.server.snapshot)
        snapshot["workspaces"][0]["label"] = "Renamed"
        self.server.snapshot = snapshot
        self.server.push_lifecycle(
            "workspace_renamed",
            {"type": "workspace_renamed", "workspace_id": "w1", "label": "Renamed"},
        )
        self.assertTrue(wait_until(lambda: len(self._states()) > before, timeout=2.0))
        labels = {
            a["pane_id"]: a["workspace"]["label"]
            for a in self._states()[-1]["agents"]
        }
        self.assertEqual(labels.get("w1:p1"), "Renamed")

    def test_tab_label_change_publishes(self):
        before = len(self._states())
        snapshot = copy.deepcopy(self.server.snapshot)
        snapshot["tabs"][0]["label"] = "src"
        self.server.snapshot = snapshot
        self.server.push_lifecycle(
            "tab_renamed",
            {"type": "tab_renamed", "tab_id": "w1:t1", "label": "src"},
        )
        self.assertTrue(wait_until(lambda: len(self._states()) > before, timeout=2.0))
        labels = {a["pane_id"]: a["tab"]["label"] for a in self._states()[-1]["agents"]}
        self.assertEqual(labels.get("w1:p1"), "src")

    def test_disconnect_then_reconnect_republishes_even_if_agents_match(self):
        first = self._states()[0]
        self.server.disconnect_subscribers()
        self.assertTrue(
            wait_until(
                lambda: any(s.get("connection") == "disconnected" and s.get("stale") is True for s in self._states()),
                timeout=3.0,
            )
        )
        self.assertTrue(
            wait_until(
                lambda: len([s for s in self._states() if s.get("connection") == "connected"]) >= 2,
                timeout=3.0,
            )
        )
        states = self._states()
        disc = next(s for s in states if s.get("connection") == "disconnected")
        recon = [s for s in states if s.get("connection") == "connected"][-1]
        self.assertTrue(disc["stale"])
        self.assertFalse(recon["stale"])
        self.assertEqual(
            publication_fingerprint(
                {"agents": first["agents"], "counts": first["counts"]},
                "connected",
                False,
                first.get("presentation"),
            ),
            publication_fingerprint(
                {"agents": recon["agents"], "counts": recon["counts"]},
                "connected",
                False,
                recon.get("presentation"),
            ),
        )
        self.assertEqual(first["presentation"], recon["presentation"])
        self.assertEqual(disc["presentation"], first["presentation"])

    def test_explicit_refresh_correlates_action_result_without_forcing_duplicate_state(self):
        before_states = len(self._states())
        self.stdin_write.write('{"type":"refresh","request_id":"req-refresh-1"}\n')
        self.stdin_write.flush()
        self.assertTrue(
            wait_until(
                lambda: any(
                    m.get("request_id") == "req-refresh-1" and m.get("ok") is True
                    for m in self.sink.of_type("action_result")
                ),
                timeout=2.0,
            )
        )
        # Snapshot unchanged → no additional state publication required.
        self.assertEqual(len(self._states()), before_states)

    def test_dedup_diagnostics_never_emit_private_fields(self):
        blob = json.dumps(self.sink.messages)
        self.assertNotIn(self.socket_path, blob)
        self.assertNotIn(self.temp_dir, blob)
        for msg in self.sink.messages:
            self.assertNotIn("socket_path", msg)
            self.assertNotIn("hostname", msg)
            self.assertNotIn("event", msg)
            self.assertNotIn("raw", msg)
