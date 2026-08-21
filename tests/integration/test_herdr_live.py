"""Live Herdr integration against a disposable shepherd-it-* session."""

import json
import os
import sys
import threading
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_TESTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, _TESTS)

from helper.presentation import build_presentation_descriptor
from integration.herdr_session import (
    DisposableHerdrSession,
    SESSION_PREFIX,
    assert_not_default_target,
    default_server_running,
    live_herdr_skip_reason,
    session_socket_path,
    validate_session_name,
)
from support import JsonlSink, make_helper, wait_until

_LIVE_SKIP_REASON = live_herdr_skip_reason()
_APP_ID_PREFIX = "org.omarchy.herdr.session-"


@unittest.skipIf(_LIVE_SKIP_REASON is not None, _LIVE_SKIP_REASON or "")
class TestHerdrLiveIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default_running_before = default_server_running()

    @classmethod
    def tearDownClass(cls):
        cls.default_running_after = default_server_running()
        if cls.default_running_before != cls.default_running_after:
            raise AssertionError("default Herdr server running state changed")

    def setUp(self):
        self.session = DisposableHerdrSession()
        validate_session_name(self.session.session_name)
        assert_not_default_target(self.session.session_name, self.session.socket_path)
        self.session.start_server()
        self.panes = self.session.seed_minimal_state()
        self.sink = JsonlSink()
        stdin_r, stdin_w = os.pipe()
        self.stdin_read = os.fdopen(stdin_r)
        self.stdin_write = os.fdopen(stdin_w, "w")
        self.helper = make_helper(
            self.session.socket_path,
            presentation=build_presentation_descriptor({
                "HERDR_SESSION": self.session.session_name,
            }),
            debounce_s=0.15,
            recv_timeout=0.1,
            rpc_timeout=5.0,
            backoff_initial=0.2,
            backoff_max=1.0,
            infile=self.stdin_read,
            outfile=self.sink,
        )
        self.thread = threading.Thread(target=self.helper.run, name="shepherd-run")
        self.thread.start()
        self.assertTrue(
            wait_until(lambda: len(self.sink.of_type("state")) >= 1, timeout=5.0),
            "helper did not emit initial state",
        )

    def tearDown(self):
        if hasattr(self, "helper"):
            self.helper.stop()
        try:
            if hasattr(self, "stdin_write") and self.stdin_write is not None:
                self.stdin_write.close()
        except OSError:
            pass
        if hasattr(self, "thread"):
            started = getattr(self.thread, "_started", None)
            if started is not None and started.is_set():
                self.thread.join(timeout=5.0)
        try:
            if hasattr(self, "stdin_read"):
                self.stdin_read.close()
        except OSError:
            pass
        self.session.cleanup()

    def test_session_name_guard(self):
        self.assertTrue(self.session.session_name.startswith(SESSION_PREFIX))
        self.assertNotEqual(self.session.session_name, "default")
        self.assertEqual(
            self.session.socket_path,
            session_socket_path(self.session.session_name),
        )
        self.assertNotEqual(
            os.path.normpath(self.session.socket_path),
            os.path.normpath(os.path.join(
                os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                "herdr",
                "herdr.sock",
            )),
        )

    def test_initial_connection_emits_connected_state(self):
        state = self.sink.of_type("state")[0]
        self.assertEqual(state["connection"], "connected")
        self.assertIs(state["stale"], False)
        self.assertGreaterEqual(len(state["agents"]), 1)

    def test_presentation_describes_disposable_named_session(self):
        state = self.sink.of_type("state")[0]
        presentation = state["presentation"]
        self.assertEqual(
            set(presentation.keys()),
            {"kind", "supported", "app_id", "argv"},
        )
        self.assertEqual(presentation["kind"], "named")
        self.assertIs(presentation["supported"], True)
        self.assertTrue(presentation["app_id"].startswith(_APP_ID_PREFIX))
        self.assertEqual(len(presentation["app_id"]), len(_APP_ID_PREFIX) + 12)
        self.assertEqual(presentation["argv"][:2], ["herdr", "--session"])
        self.assertEqual(presentation["argv"][2], self.session.session_name)
        # Raw socket path must never appear in serialized state.
        blob = json.dumps(state)
        self.assertNotIn(self.session.socket_path, blob)
        self.assertNotIn("socket_path", presentation)

    def test_snapshot_normalization_from_live_session(self):
        state = self.sink.of_type("state")[0]
        agent = state["agents"][0]
        self.assertEqual(
            set(agent.keys()),
            {"pane_id", "name", "status", "focused", "workspace", "tab"},
        )
        self.assertEqual(set(agent["workspace"].keys()), {"id", "label", "number"})
        self.assertEqual(set(agent["tab"].keys()), {"id", "label", "number"})
        self.assertEqual(
            set(state["counts"].keys()),
            {"working", "blocked", "done", "idle", "unknown", "total"},
        )
        self.assertNotIn("cwd", agent)
        self.assertNotIn("terminal_id", agent)

    def test_status_change_triggers_debounced_refresh(self):
        before = len(self.sink.of_type("state"))
        self.session.herdr(
            "pane", "report-agent", self.panes["pane1"],
            "--source", "it",
            "--agent", "fake-agent",
            "--state", "blocked",
            "--message", "it",
        )
        self.assertTrue(
            wait_until(lambda: len(self.sink.of_type("state")) > before, timeout=3.0),
            "status change did not trigger refreshed state",
        )
        latest = self.sink.of_type("state")[-1]
        statuses = {a["pane_id"]: a["status"] for a in latest["agents"]}
        self.assertEqual(statuses.get(self.panes["pane1"]), "blocked")

    def test_lifecycle_change_triggers_refresh(self):
        before = len(self.sink.of_type("state"))
        self.session.herdr("tab", "rename", "w1:t1", "it-tab")
        self.assertTrue(
            wait_until(lambda: len(self.sink.of_type("state")) > before, timeout=3.0),
            "lifecycle change did not trigger refreshed state",
        )
        labels = {a["pane_id"]: a["tab"]["label"] for a in self.sink.of_type("state")[-1]["agents"]}
        self.assertEqual(labels.get(self.panes["pane1"]), "it-tab")

    def test_focus_ipc_targets_disposable_pane(self):
        self.stdin_write.write(json.dumps({
            "type": "focus",
            "request_id": "req-focus",
            "pane_id": self.panes["pane2"],
        }) + "\n")
        self.stdin_write.flush()
        self.assertTrue(
            wait_until(
                lambda: any(
                    m.get("request_id") == "req-focus" and m.get("ok") is True
                    for m in self.sink.of_type("action_result")
                ),
                timeout=3.0,
            ),
        )
        result = [m for m in self.sink.of_type("action_result") if m.get("request_id") == "req-focus"][0]
        self.assertEqual(result["type"], "action_result")
        self.assertNotIn("message", result)

    def test_refresh_ipc_emits_action_result(self):
        self.stdin_write.write(json.dumps({
            "type": "refresh",
            "request_id": "req-refresh",
        }) + "\n")
        self.stdin_write.flush()
        self.assertTrue(
            wait_until(
                lambda: any(
                    m.get("request_id") == "req-refresh" and m.get("ok") is True
                    for m in self.sink.of_type("action_result")
                ),
                timeout=3.0,
            ),
        )

    def test_disconnect_and_reconnect_within_named_session(self):
        before = len(self.sink.of_type("state"))
        before_presentation = self.sink.of_type("state")[0]["presentation"]
        self.session.stop_server()
        self.assertTrue(
            wait_until(
                lambda: any(s.get("connection") == "disconnected" for s in self.sink.of_type("state")),
                timeout=5.0,
            ),
            "helper did not emit disconnected state",
        )
        disconnected = [s for s in self.sink.of_type("state") if s.get("connection") == "disconnected"][-1]
        self.assertIs(disconnected["stale"], True)
        self.assertEqual(disconnected["presentation"], before_presentation)
        self.session.start_server()
        self.assertTrue(
            wait_until(
                lambda: self.sink.of_type("state")[-1].get("connection") == "connected",
                timeout=8.0,
            ),
            "helper did not reconnect to named session",
        )
        self.assertGreater(len(self.sink.of_type("state")), before)
        after_presentation = self.sink.of_type("state")[-1]["presentation"]
        self.assertEqual(after_presentation, before_presentation)

    def test_shutdown_closes_helper_threads(self):
        self.helper.stop()
        self.stdin_write.close()
        self.thread.join(timeout=5.0)
        self.assertFalse(self.thread.is_alive())
        live = [t.name for t in threading.enumerate() if t.name.startswith("shepherd-")]
        self.assertEqual(live, [])


if __name__ == "__main__":
    unittest.main()
