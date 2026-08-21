"""State publication includes a once-per-process presentation descriptor."""

import copy
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, _HERE)

from fakes.fake_herdr import FakeHerdrServer
from helper.ipc import HelperIPC
from helper.presentation import (
    build_presentation_descriptor,
    sanitize_presentation_descriptor,
)
from helper.runtime import Helper, publication_fingerprint
from helper.shepherd_helper import build_helper
from helper.socket_path import resolve_socket_path
from support import DEFAULT_PRESENTATION, JsonlSink, make_helper, wait_until
from test_ipc import ProtocolCapture, parse_jsonl_strict


STATE_KEYS = {"type", "connection", "stale", "agents", "counts", "presentation"}
PRESENTATION_KEYS = {"kind", "supported", "app_id", "argv"}
APP_ID_PREFIX = "org.omarchy.herdr.session-"

NAMED_SESSION = "state-pres-named"
NAMED_PRESENTATION = {
    "kind": "named",
    "supported": True,
    "app_id": APP_ID_PREFIX + hashlib.sha256(
        NAMED_SESSION.encode("utf-8")
    ).hexdigest()[:12],
    "argv": ["herdr", "--session", NAMED_SESSION],
}

UNSUPPORTED_PRESENTATION = {
    "kind": "socket_override",
    "supported": False,
    "app_id": "",
    "argv": [],
}


def _assert_presentation(test, msg, expected):
    test.assertEqual(set(msg.keys()), STATE_KEYS)
    test.assertEqual(set(msg["presentation"].keys()), PRESENTATION_KEYS)
    test.assertEqual(msg["presentation"], expected)


class TestSanitizePresentation(unittest.TestCase):
    def test_exact_keys_required(self):
        dirty = dict(DEFAULT_PRESENTATION)
        dirty["socket_path"] = "/tmp/shepherd-pres-leak.sock"
        clean = sanitize_presentation_descriptor(dirty)
        self.assertEqual(clean, UNSUPPORTED_PRESENTATION)

    def test_named_accepts_matching_app_id(self):
        self.assertEqual(
            sanitize_presentation_descriptor(NAMED_PRESENTATION),
            NAMED_PRESENTATION,
        )

    def test_named_rejects_mismatched_app_id(self):
        bad = dict(NAMED_PRESENTATION)
        bad["app_id"] = APP_ID_PREFIX + ("a" * 12)
        self.assertEqual(
            sanitize_presentation_descriptor(bad),
            UNSUPPORTED_PRESENTATION,
        )

    def test_supported_integer_one_downgrades(self):
        bad = dict(DEFAULT_PRESENTATION)
        bad["supported"] = 1
        self.assertEqual(
            sanitize_presentation_descriptor(bad),
            UNSUPPORTED_PRESENTATION,
        )

    def test_supported_integer_zero_downgrades(self):
        bad = dict(UNSUPPORTED_PRESENTATION)
        bad["supported"] = 0
        self.assertEqual(
            sanitize_presentation_descriptor(bad),
            UNSUPPORTED_PRESENTATION,
        )

    def test_malformed_argv_types_downgrade(self):
        bad = dict(DEFAULT_PRESENTATION)
        bad["argv"] = ["herdr", 1]
        self.assertEqual(
            sanitize_presentation_descriptor(bad),
            UNSUPPORTED_PRESENTATION,
        )

    def test_default_with_extra_args_downgrades(self):
        bad = dict(DEFAULT_PRESENTATION)
        bad["argv"] = ["herdr", "--session", "x"]
        self.assertEqual(
            sanitize_presentation_descriptor(bad),
            UNSUPPORTED_PRESENTATION,
        )

    def test_named_missing_or_extra_args_downgrade(self):
        short = dict(NAMED_PRESENTATION)
        short["argv"] = ["herdr", "--session"]
        self.assertEqual(
            sanitize_presentation_descriptor(short),
            UNSUPPORTED_PRESENTATION,
        )
        long = dict(NAMED_PRESENTATION)
        long["argv"] = ["herdr", "--session", NAMED_SESSION, "extra"]
        # app_id no longer matches either after length change
        self.assertEqual(
            sanitize_presentation_descriptor(long),
            UNSUPPORTED_PRESENTATION,
        )

    def test_unsupported_nonempty_fields_downgrade(self):
        bad = dict(UNSUPPORTED_PRESENTATION)
        bad["app_id"] = "x"
        self.assertEqual(
            sanitize_presentation_descriptor(bad),
            UNSUPPORTED_PRESENTATION,
        )
        bad2 = dict(UNSUPPORTED_PRESENTATION)
        bad2["argv"] = ["herdr"]
        self.assertEqual(
            sanitize_presentation_descriptor(bad2),
            UNSUPPORTED_PRESENTATION,
        )

    def test_downgrade_allocates_new_object(self):
        a = sanitize_presentation_descriptor({"kind": "bogus"})
        b = sanitize_presentation_descriptor(None)
        self.assertEqual(a, UNSUPPORTED_PRESENTATION)
        self.assertEqual(b, UNSUPPORTED_PRESENTATION)
        self.assertIsNot(a, b)
        a["argv"].append("x")
        self.assertEqual(b["argv"], [])

    def test_whitespace_session_name_truthiness(self):
        # Documented: whitespace-only remains truthy like the socket resolver.
        name = "   "
        desc = build_presentation_descriptor({"HERDR_SESSION": name})
        self.assertEqual(desc["kind"], "named")
        self.assertEqual(desc["argv"][2], name)
        self.assertEqual(sanitize_presentation_descriptor(desc), desc)

    def test_argv_is_copied(self):
        src = dict(DEFAULT_PRESENTATION)
        src["argv"] = ["herdr"]
        out = sanitize_presentation_descriptor(src)
        out["argv"].append("mutated")
        self.assertEqual(src["argv"], ["herdr"])


class TestBuildHelperEnvironmentOwnership(unittest.TestCase):
    def test_build_helper_uses_same_snapshot_for_socket_and_presentation(self):
        env = {
            "HOME": "/fake/build-home",
            "HERDR_SESSION": "unified-sess",
        }
        expected_socket = resolve_socket_path(env)
        expected_pres = build_presentation_descriptor(env)
        with mock.patch("helper.shepherd_helper.Helper") as helper_cls:
            helper_cls.return_value = mock.Mock()
            build_helper(environ=env)
        kwargs = helper_cls.call_args.kwargs
        self.assertEqual(kwargs["socket_path"], expected_socket)
        self.assertEqual(kwargs["presentation"], expected_pres)
        self.assertEqual(kwargs["presentation"]["kind"], "named")
        self.assertEqual(kwargs["presentation"]["argv"][2], "unified-sess")

    def test_injected_mapping_ignores_real_environ(self):
        with mock.patch.dict(
            os.environ,
            {
                "HERDR_SESSION": "real-leak",
                "HERDR_SOCKET_PATH": "/real/leak.sock",
                "HOME": "/real/home",
            },
            clear=False,
        ):
            env = {"HOME": "/fake/home", "HERDR_SESSION": "fake-only"}
            with mock.patch("helper.shepherd_helper.Helper") as helper_cls:
                helper_cls.return_value = mock.Mock()
                build_helper(environ=env)
            kwargs = helper_cls.call_args.kwargs
        self.assertEqual(
            kwargs["socket_path"],
            "/fake/home/.config/herdr/sessions/fake-only/herdr.sock",
        )
        self.assertEqual(kwargs["presentation"]["argv"][2], "fake-only")
        self.assertNotIn("real-leak", json.dumps(kwargs["presentation"]))

    def test_conventional_socket_override_matches(self):
        env = {
            "XDG_CONFIG_HOME": "/fake/xdg",
            "HERDR_SOCKET_PATH": "/fake/xdg/herdr/sessions/conv/herdr.sock",
        }
        with mock.patch("helper.shepherd_helper.Helper") as helper_cls:
            helper_cls.return_value = mock.Mock()
            build_helper(environ=env)
        kwargs = helper_cls.call_args.kwargs
        self.assertEqual(kwargs["socket_path"], env["HERDR_SOCKET_PATH"])
        self.assertEqual(kwargs["presentation"]["kind"], "named")
        self.assertEqual(kwargs["presentation"]["argv"][2], "conv")

    def test_arbitrary_override_unsupported_no_fallback(self):
        env = {
            "HERDR_SOCKET_PATH": "/tmp/shepherd-arb.sock",
            "HERDR_SESSION": "would-be-named",
            "HOME": "/fake/home",
        }
        with mock.patch("helper.shepherd_helper.Helper") as helper_cls:
            helper_cls.return_value = mock.Mock()
            build_helper(environ=env)
        kwargs = helper_cls.call_args.kwargs
        self.assertEqual(kwargs["socket_path"], "/tmp/shepherd-arb.sock")
        self.assertEqual(kwargs["presentation"], UNSUPPORTED_PRESENTATION)

    def test_production_snapshots_environ_once(self):
        with mock.patch(
            "helper.shepherd_helper.resolve_socket_path",
            return_value="/fake/sock",
        ) as resolve:
            with mock.patch(
                "helper.shepherd_helper.build_presentation_descriptor",
                return_value=dict(DEFAULT_PRESENTATION),
            ) as build_pres:
                with mock.patch("helper.shepherd_helper.Helper") as helper_cls:
                    helper_cls.return_value = mock.Mock()
                    build_helper()
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(build_pres.call_count, 1)
        self.assertIs(resolve.call_args.args[0], build_pres.call_args.args[0])

    def test_rejects_explicit_socket_or_presentation_kwargs(self):
        with self.assertRaises(TypeError):
            build_helper(socket_path="/x")
        with self.assertRaises(TypeError):
            build_helper(presentation=DEFAULT_PRESENTATION)


class TestHelperConstructorContract(unittest.TestCase):
    def test_missing_socket_path_fails(self):
        with self.assertRaises(TypeError):
            Helper(presentation=DEFAULT_PRESENTATION)

    def test_missing_presentation_fails(self):
        with self.assertRaises(TypeError):
            Helper(socket_path="/tmp/fake.sock")

    def test_empty_socket_path_fails(self):
        with self.assertRaises(TypeError):
            Helper(socket_path="", presentation=DEFAULT_PRESENTATION)

    def test_make_helper_uses_explicit_fakes(self):
        helper = make_helper("/tmp/shepherd-unit.sock")
        self.assertEqual(helper.socket_path, "/tmp/shepherd-unit.sock")
        self.assertEqual(helper.presentation, DEFAULT_PRESENTATION)


class TestIpcPresentationEmission(unittest.TestCase):
    def setUp(self):
        self.capture = ProtocolCapture()

    def test_default_named_unsupported_pass_through(self):
        for expected in (DEFAULT_PRESENTATION, NAMED_PRESENTATION, UNSUPPORTED_PRESENTATION):
            helper = type("H", (), {"presentation": copy.deepcopy(expected)})()
            ipc = HelperIPC(helper, outfile=self.capture)
            ipc.send_state({"agents": [], "counts": {"total": 0}})
            msg = parse_jsonl_strict(self.capture.raw())[-1]
            _assert_presentation(self, msg, expected)

    def test_disconnected_stale_includes_presentation(self):
        helper = type("H", (), {"presentation": copy.deepcopy(NAMED_PRESENTATION)})()
        ipc = HelperIPC(helper, outfile=self.capture)
        ipc.send_state(
            {"agents": [], "counts": {"total": 0}},
            connection="disconnected",
            stale=True,
        )
        msg = parse_jsonl_strict(self.capture.raw())[0]
        self.assertEqual(msg["connection"], "disconnected")
        self.assertIs(msg["stale"], True)
        _assert_presentation(self, msg, NAMED_PRESENTATION)

    def test_extra_injected_keys_never_emitted(self):
        leak_path = "/tmp/shepherd-state-pres-extra.sock"
        dirty = dict(DEFAULT_PRESENTATION)
        dirty["socket_path"] = leak_path
        helper = type("H", (), {"presentation": dirty})()
        ipc = HelperIPC(helper, outfile=self.capture)
        ipc.send_state({"agents": [], "counts": {}})
        raw = self.capture.raw()
        msg = parse_jsonl_strict(raw)[0]
        # Extra keys make the descriptor malformed → unsupported, no leak.
        self.assertEqual(msg["presentation"], UNSUPPORTED_PRESENTATION)
        self.assertNotIn(leak_path, raw)

    def test_action_and_error_exclude_presentation(self):
        helper = type("H", (), {"presentation": DEFAULT_PRESENTATION})()
        ipc = HelperIPC(helper, outfile=self.capture)
        ipc.send_action_result("req-1", True)
        ipc.send_error("req-2", "invalid_json", "Malformed JSON")
        for msg in parse_jsonl_strict(self.capture.raw()):
            self.assertNotIn("presentation", msg)
            self.assertNotIn("argv", msg)


class TestHelperPresentationPublication(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.socket_path = os.path.join(self.temp_dir, "herdr.sock")
        self.server = FakeHerdrServer(self.socket_path)
        self.server.start()
        self.sink = JsonlSink()
        stdin_r, stdin_w = os.pipe()
        self.stdin_read = os.fdopen(stdin_r)
        self.stdin_write = os.fdopen(stdin_w, "w")

    def tearDown(self):
        if hasattr(self, "helper"):
            self.helper.stop()
        if hasattr(self, "thread"):
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

    def _start(self, presentation):
        self.helper = make_helper(
            self.socket_path,
            presentation=presentation,
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

    def test_connected_state_includes_presentation(self):
        self._start(NAMED_PRESENTATION)
        state = self.sink.of_type("state")[0]
        self.assertEqual(state["connection"], "connected")
        _assert_presentation(self, state, NAMED_PRESENTATION)

    def test_disconnect_reconnect_keeps_presentation(self):
        self._start(DEFAULT_PRESENTATION)
        self.server.disconnect_subscribers()
        self.assertTrue(
            wait_until(
                lambda: any(
                    s.get("connection") == "disconnected" for s in self.sink.of_type("state")
                ),
                timeout=3.0,
            )
        )
        self.assertTrue(
            wait_until(
                lambda: len([s for s in self.sink.of_type("state") if s.get("connection") == "connected"]) >= 2,
                timeout=3.0,
            )
        )
        for state in self.sink.of_type("state"):
            _assert_presentation(self, state, DEFAULT_PRESENTATION)

    def test_caller_mutation_after_construction_ignored(self):
        injected = copy.deepcopy(DEFAULT_PRESENTATION)
        self._start(injected)
        injected["kind"] = "named"
        injected["argv"].append("--session")
        injected["argv"].append("mutated")
        before = len(self.sink.of_type("state"))
        snapshot = copy.deepcopy(self.server.snapshot)
        for agent in snapshot["agents"]:
            if agent["pane_id"] == "w1:p1":
                agent["agent_status"] = "blocked"
        self.server.snapshot = snapshot
        self.server.push_scoped(
            "pane.agent_status_changed",
            {"pane_id": "w1:p1", "agent_status": "blocked"},
        )
        self.assertTrue(wait_until(lambda: len(self.sink.of_type("state")) > before, timeout=2.0))
        latest = self.sink.of_type("state")[-1]
        _assert_presentation(self, latest, DEFAULT_PRESENTATION)

    def test_emitted_argv_mutation_isolated(self):
        self._start(NAMED_PRESENTATION)
        first = self.sink.of_type("state")[0]
        first["presentation"]["argv"].append("mutated")
        before = len(self.sink.of_type("state"))
        snapshot = copy.deepcopy(self.server.snapshot)
        snapshot["workspaces"][0]["label"] = "Renamed-Pres"
        self.server.snapshot = snapshot
        self.server.push_lifecycle(
            "workspace_renamed",
            {"type": "workspace_renamed", "workspace_id": "w1", "label": "Renamed-Pres"},
        )
        self.assertTrue(wait_until(lambda: len(self.sink.of_type("state")) > before, timeout=2.0))
        self.assertEqual(
            self.sink.of_type("state")[-1]["presentation"],
            NAMED_PRESENTATION,
        )

    def test_identical_state_including_presentation_deduped(self):
        self._start(DEFAULT_PRESENTATION)
        before = len(self.sink.of_type("state"))
        for _ in range(5):
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
        import time
        time.sleep(0.15)
        self.assertEqual(len(self.sink.of_type("state")), before)

    def test_fingerprint_includes_presentation(self):
        state = {"agents": [], "counts": {"total": 0}}
        a = publication_fingerprint(state, "connected", False, DEFAULT_PRESENTATION)
        b = publication_fingerprint(state, "connected", False, NAMED_PRESENTATION)
        self.assertNotEqual(a, b)

    def test_refresh_correlation_unchanged(self):
        self._start(DEFAULT_PRESENTATION)
        before = len(self.sink.of_type("state"))
        self.stdin_write.write('{"type":"refresh","request_id":"req-pres-refresh"}\n')
        self.stdin_write.flush()
        self.assertTrue(
            wait_until(
                lambda: any(
                    m.get("request_id") == "req-pres-refresh" and m.get("ok") is True
                    for m in self.sink.of_type("action_result")
                ),
                timeout=2.0,
            )
        )
        self.assertEqual(len(self.sink.of_type("state")), before)
        for msg in self.sink.of_type("action_result"):
            self.assertNotIn("presentation", msg)

    def test_json_serializable_state(self):
        self._start(UNSUPPORTED_PRESENTATION)
        raw = json.dumps(self.sink.of_type("state")[0])
        loaded = json.loads(raw)
        self.assertEqual(loaded["presentation"], UNSUPPORTED_PRESENTATION)
        self.assertNotIn(self.socket_path, raw)
