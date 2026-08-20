import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fakes.fake_herdr import FakeHerdrServer
from helper.runtime import Helper
from support import JsonlSink, wait_until


class TestHelperRuntime(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.socket_path = os.path.join(self.temp_dir, "herdr.sock")
        self.server = FakeHerdrServer(self.socket_path)
        self.server.start()
        self.sink = JsonlSink()
        stdin_r, stdin_w = os.pipe()
        self.stdin_read = os.fdopen(stdin_r)
        self.stdin_write = os.fdopen(stdin_w, "w")
        self.helper = Helper(
            socket_path=self.socket_path,
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

    def test_snapshot_uses_rpc_connection_separate_from_subscribe(self):
        self.assertGreaterEqual(len(self.server.rpc_records()), 1)
        self.assertEqual(len(self.server.subscribe_records()), 1)
        self.assertEqual(self.server.rpc_records()[0].methods, ["session.snapshot"])
        self.assertEqual(self.server.subscribe_records()[0].methods, ["events.subscribe"])

    def test_one_subscribe_reader(self):
        readers = [t for t in threading.enumerate() if t.name == "shepherd-subscribe"]
        self.assertEqual(len(readers), 1)

    def test_idle_timeout_does_not_reconnect(self):
        time.sleep(0.3)
        self.assertEqual(len(self.server.subscribe_records()), 1)
        self.assertEqual(len(self.sink.of_type("state")), 1)

    def test_eof_does_reconnect(self):
        self.server.disconnect_subscribers()
        self.assertTrue(wait_until(lambda: len(self.server.subscribe_records()) >= 2, timeout=3.0))

    def test_burst_events_one_debounced_refresh(self):
        before = len(self.server.rpc_records())
        before_states = len(self.sink.of_type("state"))
        for _ in range(5):
            self.server.push_lifecycle("pane_focused", {"type": "pane_focused", "pane_id": "w1:p1", "workspace_id": "w1"})
        self.assertTrue(
            wait_until(
                lambda: len([r for r in self.server.rpc_records() if r.methods == ["session.snapshot"]])
                >= before + 1,
                timeout=2.0,
            )
        )
        time.sleep(0.15)
        snapshot_rpcs = [r for r in self.server.rpc_records() if r.methods == ["session.snapshot"]]
        self.assertEqual(len(snapshot_rpcs), before + 1)
        # Unchanged normalized state must not re-publish.
        self.assertEqual(len(self.sink.of_type("state")), before_states)

    def test_focus_uses_separate_rpc_connection(self):
        before = len(self.server.rpc_records())
        self.stdin_write.write('{"type":"focus","request_id":"req-1","pane_id":"w1:p1"}\n')
        self.stdin_write.flush()
        self.assertTrue(wait_until(lambda: any(m.get("ok") is True for m in self.sink.of_type("action_result"))))
        focus_records = [r for r in self.server.rpc_records()[before:] if r.methods == ["agent.focus"]]
        self.assertEqual(len(focus_records), 1)
        self.assertTrue(focus_records[0].closed)
        self.assertEqual(len(self.server.subscribe_records()), 1)

    def test_scoped_status_subscriptions_match_snapshot_panes(self):
        scoped = [
            item["pane_id"]
            for item in self.server.last_subscriptions
            if item.get("type") == "pane.agent_status_changed"
        ]
        self.assertEqual(set(scoped), {"w1:p1", "w1:p2"})

    def test_pane_membership_rebuilds_subscribe(self):
        snapshot = dict(self.server.snapshot)
        snapshot["panes"] = list(snapshot["panes"]) + [{
            "pane_id": "w1:p3",
            "terminal_id": "t3",
            "workspace_id": "w1",
            "tab_id": "w1:t1",
            "focused": False,
            "agent_status": "idle",
        }]
        self.server.snapshot = snapshot
        self.server.push_lifecycle("pane_created", {"type": "pane_created", "pane": {"pane_id": "w1:p3"}})
        self.assertTrue(wait_until(lambda: len(self.server.subscribe_records()) >= 2, timeout=3.0))
        scoped = [
            item["pane_id"]
            for item in self.server.last_subscriptions
            if item.get("type") == "pane.agent_status_changed"
        ]
        self.assertEqual(set(scoped), {"w1:p1", "w1:p2", "w1:p3"})

    def test_shutdown_joins_threads(self):
        self.helper.stop()
        self.thread.join(timeout=3.0)
        self.assertFalse(self.thread.is_alive())
        live = [t.name for t in threading.enumerate() if t.name.startswith("shepherd-")]
        self.assertEqual(live, [])
        self.assertEqual(self.helper._thread_errors, [])
        self.assertEqual(self.server.thread_errors, [])
