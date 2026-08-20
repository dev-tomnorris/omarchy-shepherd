"""QML ↔ helper JSONL IPC contract tests.

Exercises the public HelperIPC interface only. A fake helper is injected so
these tests never open a Herdr socket or read environment configuration.
"""

import copy
import json
import os
import sys
import threading
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, _HERE)

from helper.ipc import HelperIPC
from helper.rpc import RpcError
from support import wait_until


FIXTURE_PATH = os.path.join(_HERE, "fixtures", "normalized_state.json")

STATE_TOP_LEVEL_FIELDS = {"type", "connection", "stale", "agents", "counts"}
AGENT_FIELDS = {"pane_id", "name", "status", "focused", "workspace", "tab"}
COUNT_FIELDS = {"working", "blocked", "done", "idle", "unknown", "total"}
ERROR_FIELDS = {"type", "request_id", "code", "message"}
ACTION_RESULT_REQUIRED = {"type", "request_id", "ok"}

# Fake backend details that must never appear on protocol stdout.
FAKE_TRACEBACK = "Traceback (most recent call last): File ignored.py line 1"
FAKE_SOCKET_PATH = "/tmp/fake-herdr-SHOULD-NOT-APPEAR.sock"
FAKE_SNAPSHOT = '{"cwd": "/home/fake-user/secret", "pane_output": "RAW_SNAPSHOT_SHOULD_NOT_APPEAR"}'
FAKE_EXCEPTION_TEXT = "BACKEND_EXCEPTION_SHOULD_NOT_APPEAR: agent.focus exploded"
LEAK_MARKERS = (FAKE_TRACEBACK, FAKE_SOCKET_PATH, FAKE_SNAPSHOT, FAKE_EXCEPTION_TEXT)

_UNSET = object()


def load_normalized_fixture():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def complete_lines(raw):
    if not raw:
        return []
    parts = raw.split("\n")
    if raw.endswith("\n"):
        return parts[:-1]
    return parts[:-1]


def parse_jsonl_strict(raw):
    """Parse protocol stdout as JSONL. Every complete line must be one JSON object."""
    messages = []
    for line in complete_lines(raw):
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise AssertionError("protocol line is not a JSON object: %r" % line)
        messages.append(obj)
    return messages


class ProtocolCapture:
    """File-like sink that records exact protocol stdout text."""

    def __init__(self):
        self._chunks = []
        self._lock = threading.Lock()

    def write(self, text):
        if not isinstance(text, str):
            text = text.decode("utf-8")
        with self._lock:
            self._chunks.append(text)

    def flush(self):
        pass

    def raw(self):
        with self._lock:
            return "".join(self._chunks)


class RecordingHelper:
    """Injected helper standing in for helper.runtime.Helper public methods."""

    def __init__(self):
        self.focus_calls = []
        self.refresh_calls = []
        self.note_connection_lost_calls = 0
        self.focus_side_effect = None
        self.refresh_side_effect = None
        self._lock = threading.Lock()

    def focus_agent(self, pane_id):
        with self._lock:
            self.focus_calls.append(pane_id)
        if self.focus_side_effect is not None:
            raise self.focus_side_effect

    def refresh_snapshot(self, reason="invalidation"):
        with self._lock:
            self.refresh_calls.append(reason)
        if self.refresh_side_effect is not None:
            raise self.refresh_side_effect

    def note_connection_lost(self):
        with self._lock:
            self.note_connection_lost_calls += 1


class IpcSession:
    """Public HelperIPC reader loop bound to a pipe (never a Herdr socket)."""

    def __init__(self, helper=None):
        self.helper = helper or RecordingHelper()
        self.capture = ProtocolCapture()
        read_fd, write_fd = os.pipe()
        self._infile = os.fdopen(read_fd)
        self._inwrite = os.fdopen(write_fd, "w")
        self.ipc = HelperIPC(self.helper, infile=self._infile, outfile=self.capture)
        self.ipc.start()

    def write_raw(self, text):
        self._inwrite.write(text)
        self._inwrite.flush()

    def write_line(self, text):
        if not text.endswith("\n"):
            text = text + "\n"
        self.write_raw(text)

    def write_command(self, obj):
        self.write_line(json.dumps(obj))

    def close_stdin(self):
        if self._inwrite is not None:
            self._inwrite.close()
            self._inwrite = None

    def messages(self):
        return parse_jsonl_strict(self.capture.raw())

    def wait_for_messages(self, count, timeout=2.0):
        return wait_until(lambda: len(self.messages()) >= count, timeout=timeout)

    def close(self):
        self.ipc.stop()
        self.close_stdin()
        self.ipc.join(timeout=2.0)
        try:
            self._infile.close()
        except OSError:
            pass


def _assert_structured_error(test, msg, request_id=_UNSET):
    test.assertIsInstance(msg, dict)
    test.assertEqual(msg.get("type"), "error")
    test.assertEqual(set(msg.keys()), ERROR_FIELDS)
    test.assertIsInstance(msg.get("code"), str)
    test.assertTrue(msg.get("code"))
    test.assertIsInstance(msg.get("message"), str)
    test.assertTrue(msg.get("message"))
    if request_id is not _UNSET:
        test.assertEqual(msg.get("request_id"), request_id)


def _assert_action_result(test, msg, request_id, ok):
    test.assertIsInstance(msg, dict)
    test.assertEqual(msg.get("type"), "action_result")
    test.assertTrue(ACTION_RESULT_REQUIRED.issubset(msg.keys()))
    extra = set(msg.keys()) - ACTION_RESULT_REQUIRED - {"message"}
    test.assertEqual(extra, set())
    test.assertEqual(msg.get("request_id"), request_id)
    test.assertIs(msg.get("ok"), ok)


def _assert_no_leak_markers(test, raw):
    for marker in LEAK_MARKERS:
        test.assertNotIn(marker, raw)


def _assert_handlers_idle(test, helper):
    test.assertEqual(helper.focus_calls, [])
    test.assertEqual(helper.refresh_calls, [])


class TestJsonlOutput(unittest.TestCase):
    def setUp(self):
        self.capture = ProtocolCapture()
        self.ipc = HelperIPC(RecordingHelper(), outfile=self.capture)

    def test_each_emitted_message_is_one_json_object_and_one_newline(self):
        self.ipc.send({"type": "state", "connection": "connected"})
        self.ipc.send_action_result("req-1", True)
        self.ipc.send_error("req-2", "connection_lost", "Herdr socket closed")
        raw = self.capture.raw()
        self.assertTrue(raw.endswith("\n"))
        lines = complete_lines(raw)
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertNotIn("\n", line)
            obj = json.loads(line)
            self.assertIsInstance(obj, dict)
        self.assertEqual(raw, "".join(line + "\n" for line in lines))

    def test_no_diagnostic_text_on_protocol_stdout(self):
        self.ipc.send_state({"agents": [], "counts": {"total": 0}})
        self.ipc.send_error("req-diag", "connection_lost", "Herdr socket closed")
        raw = self.capture.raw()
        for line in complete_lines(raw):
            json.loads(line)
        self.assertNotIn("Helper:", raw)
        self.assertNotIn("Traceback", raw)
        leftover = raw
        for line in complete_lines(raw):
            leftover = leftover.replace(line + "\n", "", 1)
        self.assertEqual(leftover, "")

    def test_sequential_messages_are_independently_parseable(self):
        self.ipc.send({"type": "state", "n": 1})
        self.ipc.send({"type": "action_result", "request_id": "req-1", "ok": True})
        self.ipc.send({"type": "error", "request_id": "req-2", "code": "connection_lost", "message": "Herdr socket closed"})
        raw = self.capture.raw()
        parsed = []
        for line in complete_lines(raw):
            parsed.append(json.loads(line))
        self.assertEqual([m["type"] for m in parsed], ["state", "action_result", "error"])
        first_newline = raw.index("\n")
        self.assertEqual(json.loads(raw[:first_newline]), parsed[0])
        second_newline = raw.index("\n", first_newline + 1)
        self.assertEqual(json.loads(raw[first_newline + 1:second_newline]), parsed[1])

    def test_concurrent_emissions_do_not_interleave_or_corrupt_lines(self):
        count = 80
        errors = []

        def emit(index):
            try:
                self.ipc.send({
                    "type": "state",
                    "seq": index,
                    "payload": ("block-%d-" % index) + ("x" * 64),
                })
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=emit, args=(i,)) for i in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)
        self.assertEqual(errors, [])
        raw = self.capture.raw()
        self.assertTrue(raw.endswith("\n"))
        messages = parse_jsonl_strict(raw)
        self.assertEqual(len(messages), count)
        seqs = sorted(message["seq"] for message in messages)
        self.assertEqual(seqs, list(range(count)))
        self.assertEqual(len(complete_lines(raw)), count)


class TestStateOutput(unittest.TestCase):
    def setUp(self):
        self.capture = ProtocolCapture()
        self.ipc = HelperIPC(RecordingHelper(), outfile=self.capture)
        self.fixture = load_normalized_fixture()

    def test_normalized_fixture_state_uses_documented_top_level_fields(self):
        self.ipc.send_state(self.fixture, connection="connected", stale=False)
        messages = parse_jsonl_strict(self.capture.raw())
        self.assertEqual(len(messages), 1)
        msg = messages[0]
        self.assertEqual(set(msg.keys()), STATE_TOP_LEVEL_FIELDS)
        self.assertEqual(msg["type"], "state")
        self.assertEqual(msg["connection"], "connected")
        self.assertIs(msg["stale"], False)
        self.assertEqual(set(msg["counts"].keys()), COUNT_FIELDS)

    def test_agent_records_remain_unchanged(self):
        self.ipc.send_state(self.fixture)
        msg = parse_jsonl_strict(self.capture.raw())[0]
        self.assertEqual(msg["agents"], self.fixture["agents"])
        self.assertEqual(msg["counts"], self.fixture["counts"])
        for agent in msg["agents"]:
            self.assertEqual(set(agent.keys()), AGENT_FIELDS)

    def test_send_state_does_not_introduce_private_fields(self):
        state = copy.deepcopy(self.fixture)
        state["socket_path"] = FAKE_SOCKET_PATH
        state["cwd"] = "/home/fake-user/secret"
        state["_cache"] = {"raw_snapshot": FAKE_SNAPSHOT}
        self.ipc.send_state(state, connection="disconnected", stale=True)
        msg = parse_jsonl_strict(self.capture.raw())[0]
        self.assertEqual(set(msg.keys()), STATE_TOP_LEVEL_FIELDS)
        self.assertEqual(msg["connection"], "disconnected")
        self.assertIs(msg["stale"], True)
        self.assertNotIn("socket_path", msg)
        self.assertNotIn("cwd", msg)
        self.assertNotIn("_cache", msg)
        _assert_no_leak_markers(self, self.capture.raw())


class _IpcLoopTest(unittest.TestCase):
    def setUp(self):
        self.session = IpcSession()

    def tearDown(self):
        self.session.close()

    def _wait_one(self, timeout=2.0):
        self.assertTrue(
            self.session.wait_for_messages(1, timeout=timeout),
            "timed out waiting for IPC output: %r" % self.session.capture.raw(),
        )
        return self.session.messages()[0]


class TestFocusSuccess(_IpcLoopTest):
    def test_valid_focus_calls_handler_once_and_returns_ok_action_result(self):
        self.session.write_command({
            "type": "focus",
            "request_id": "req-1",
            "pane_id": "w1:p1",
        })
        msg = self._wait_one()
        self.assertEqual(self.session.helper.focus_calls, ["w1:p1"])
        self.assertEqual(self.session.helper.refresh_calls, [])
        _assert_action_result(self, msg, "req-1", True)
        self.assertNotIn("message", msg)


class TestFocusFailure(_IpcLoopTest):
    def test_controlled_focus_failure_is_structured_and_preserves_request_id(self):
        leaky = RpcError(
            "focus_failed",
            "%s %s %s %s" % (FAKE_TRACEBACK, FAKE_SOCKET_PATH, FAKE_SNAPSHOT, FAKE_EXCEPTION_TEXT),
        )
        self.session.helper.focus_side_effect = leaky
        self.session.write_command({
            "type": "focus",
            "request_id": "req-fail",
            "pane_id": "w1:p1",
        })
        msg = self._wait_one()
        self.assertEqual(self.session.helper.focus_calls, ["w1:p1"])
        _assert_action_result(self, msg, "req-fail", False)
        self.assertEqual(msg.get("message"), "Unable to focus pane.")
        raw = self.session.capture.raw()
        _assert_no_leak_markers(self, raw)
        _assert_no_leak_markers(self, msg.get("message", ""))


class TestRefresh(_IpcLoopTest):
    def test_valid_refresh_invokes_handler_once_and_correlates_request_id(self):
        self.session.write_command({"type": "refresh", "request_id": "req-2"})
        msg = self._wait_one()
        self.assertEqual(len(self.session.helper.refresh_calls), 1)
        self.assertEqual(self.session.helper.focus_calls, [])
        _assert_action_result(self, msg, "req-2", True)
        self.assertNotIn("message", msg)

    def test_controlled_refresh_failure_is_sanitized_action_result(self):
        leaky = RpcError(
            "refresh_failed",
            "%s %s %s" % (FAKE_TRACEBACK, FAKE_SOCKET_PATH, FAKE_EXCEPTION_TEXT),
        )
        self.session.helper.refresh_side_effect = leaky
        self.session.write_command({"type": "refresh", "request_id": "req-2"})
        msg = self._wait_one()
        self.assertEqual(len(self.session.helper.refresh_calls), 1)
        _assert_action_result(self, msg, "req-2", False)
        self.assertEqual(msg.get("message"), "Unable to refresh state.")
        _assert_no_leak_markers(self, self.session.capture.raw())
        _assert_no_leak_markers(self, msg.get("message", ""))


class TestInvalidInput(_IpcLoopTest):
    def _expect_error_then_alive(self, raw_line, request_id=_UNSET):
        self.session.write_line(raw_line)
        msg = self._wait_one()
        _assert_structured_error(self, msg, request_id=request_id)
        _assert_no_leak_markers(self, self.session.capture.raw())
        return msg

    def test_malformed_json_produces_structured_error(self):
        msg = self._expect_error_then_alive("{not json\n", request_id=None)
        self.assertEqual(msg.get("code"), "invalid_json")
        _assert_handlers_idle(self, self.session.helper)

    def test_json_value_that_is_not_an_object_produces_structured_error(self):
        cases = ("[]\n", "true\n", "null\n")
        for payload in cases:
            with self.subTest(payload=payload.strip()):
                session = IpcSession()
                try:
                    session.write_raw(payload)
                    self.assertTrue(
                        session.wait_for_messages(1, timeout=2.0),
                        "non-object JSON %r did not produce a structured error. "
                        "output=%r" % (payload, session.capture.raw()),
                    )
                    msg = session.messages()[0]
                    _assert_structured_error(self, msg, request_id=None)
                    self.assertEqual(msg.get("code"), "invalid_message")
                    _assert_handlers_idle(self, session.helper)
                finally:
                    session.close()

    def test_missing_type_produces_structured_error(self):
        self.session.write_command({"request_id": "req-missing-type"})
        msg = self._wait_one()
        _assert_structured_error(self, msg, request_id="req-missing-type")

    def test_unsupported_type_produces_structured_error(self):
        self.session.write_command({
            "type": "subscribe",
            "request_id": "req-unsupported",
        })
        msg = self._wait_one()
        _assert_structured_error(self, msg, request_id="req-unsupported")

    def test_missing_request_id_on_focus_produces_structured_error(self):
        self.session.write_command({"type": "focus", "pane_id": "w1:p1"})
        self.assertTrue(
            self.session.wait_for_messages(1, timeout=2.0),
            "missing request_id on focus produced no protocol message. output=%r"
            % self.session.capture.raw(),
        )
        msg = self.session.messages()[0]
        _assert_structured_error(self, msg, request_id=None)
        self.assertEqual(msg.get("code"), "missing_param")
        _assert_handlers_idle(self, self.session.helper)

    def test_missing_request_id_on_refresh_produces_structured_error(self):
        self.session.write_command({"type": "refresh"})
        self.assertTrue(
            self.session.wait_for_messages(1, timeout=2.0),
            "missing request_id on refresh produced no protocol message. output=%r"
            % self.session.capture.raw(),
        )
        msg = self.session.messages()[0]
        _assert_structured_error(self, msg, request_id=None)
        self.assertEqual(msg.get("code"), "missing_param")
        _assert_handlers_idle(self, self.session.helper)

    def test_non_string_or_empty_request_id_produces_structured_error(self):
        cases = (
            ({"type": "focus", "request_id": "", "pane_id": "w1:p1"}, "missing_param"),
            ({"type": "focus", "request_id": "   ", "pane_id": "w1:p1"}, "missing_param"),
            ({"type": "focus", "request_id": 12, "pane_id": "w1:p1"}, "invalid_param"),
            ({"type": "refresh", "request_id": ""}, "missing_param"),
            ({"type": "refresh", "request_id": "\t"}, "missing_param"),
            ({"type": "refresh", "request_id": False}, "invalid_param"),
        )
        for command, code in cases:
            with self.subTest(command=command):
                session = IpcSession()
                try:
                    session.write_command(command)
                    self.assertTrue(
                        session.wait_for_messages(1, timeout=2.0),
                        "invalid request_id %r produced no protocol message."
                        % (command.get("request_id"),),
                    )
                    msg = session.messages()[0]
                    _assert_structured_error(self, msg, request_id=None)
                    self.assertEqual(msg.get("code"), code)
                    _assert_handlers_idle(self, session.helper)
                finally:
                    session.close()

    def test_missing_pane_id_for_focus_produces_structured_error(self):
        self.session.write_command({"type": "focus", "request_id": "req-no-pane"})
        msg = self._wait_one()
        _assert_structured_error(self, msg, request_id="req-no-pane")
        self.assertEqual(msg.get("code"), "missing_param")
        _assert_handlers_idle(self, self.session.helper)

    def test_non_string_or_empty_pane_id_produces_structured_error(self):
        cases = (
            ({"type": "focus", "request_id": "req-empty-pane", "pane_id": ""}, "missing_param"),
            ({"type": "focus", "request_id": "req-ws-pane", "pane_id": "  "}, "missing_param"),
            ({"type": "focus", "request_id": "req-num-pane", "pane_id": 1}, "invalid_param"),
            ({"type": "focus", "request_id": "req-bool-pane", "pane_id": True}, "invalid_param"),
        )
        for command, code in cases:
            with self.subTest(pane_id=command["pane_id"]):
                session = IpcSession()
                try:
                    session.write_command(command)
                    self.assertTrue(
                        session.wait_for_messages(1, timeout=2.0),
                        "invalid pane_id %r produced no protocol message."
                        % (command.get("pane_id"),),
                    )
                    msg = session.messages()[0]
                    _assert_structured_error(self, msg, request_id=command["request_id"])
                    self.assertEqual(msg.get("code"), code)
                    _assert_handlers_idle(self, session.helper)
                finally:
                    session.close()


class TestStreamLifecycle(unittest.TestCase):
    def test_multiple_valid_commands_from_one_input_stream(self):
        session = IpcSession()
        try:
            session.write_command({
                "type": "focus",
                "request_id": "req-a",
                "pane_id": "w1:p1",
            })
            self.assertTrue(session.wait_for_messages(1, timeout=2.0), session.capture.raw())
            session.write_command({"type": "refresh", "request_id": "req-b"})
            self.assertTrue(session.wait_for_messages(2, timeout=2.0), session.capture.raw())
            session.write_command({
                "type": "focus",
                "request_id": "req-c",
                "pane_id": "w2:p1",
            })
            self.assertTrue(session.wait_for_messages(3, timeout=2.0), session.capture.raw())
            messages = session.messages()
            self.assertEqual(len(messages), 3)
            self.assertEqual([m.get("request_id") for m in messages], ["req-a", "req-b", "req-c"])
            self.assertEqual(session.helper.focus_calls, ["w1:p1", "w2:p1"])
            self.assertEqual(len(session.helper.refresh_calls), 1)
        finally:
            session.close()

    def test_queued_jsonl_commands_are_each_processed_without_extra_input(self):
        session = IpcSession()
        try:
            session.write_raw(
                '{"type":"focus","request_id":"req-a","pane_id":"w1:p1"}\n'
                '{"type":"refresh","request_id":"req-b"}\n'
                '{"type":"focus","request_id":"req-c","pane_id":"w2:p1"}\n'
            )
            self.assertTrue(
                session.wait_for_messages(3, timeout=2.0),
                "queued JSONL commands on one stream were not each processed. "
                "output=%r" % session.capture.raw(),
            )
            messages = session.messages()
            self.assertEqual(len(messages), 3)
            self.assertEqual([m.get("request_id") for m in messages], ["req-a", "req-b", "req-c"])
            self.assertEqual(session.helper.focus_calls, ["w1:p1", "w2:p1"])
            self.assertEqual(len(session.helper.refresh_calls), 1)
            for msg in messages:
                _assert_action_result(self, msg, msg["request_id"], True)
        finally:
            session.close()

    def test_invalid_command_does_not_prevent_later_valid_command(self):
        session = IpcSession()
        try:
            session.write_line("{nope\n")
            self.assertTrue(session.wait_for_messages(1, timeout=2.0), session.capture.raw())
            session.write_command({
                "type": "focus",
                "request_id": "req-after-invalid",
                "pane_id": "w1:p1",
            })
            self.assertTrue(session.wait_for_messages(2, timeout=2.0), session.capture.raw())
            messages = session.messages()
            _assert_structured_error(self, messages[0], request_id=None)
            self.assertEqual(messages[0].get("code"), "invalid_json")
            _assert_action_result(self, messages[1], "req-after-invalid", True)
            self.assertEqual(session.helper.focus_calls, ["w1:p1"])
        finally:
            session.close()

    def test_invalid_then_valid_in_one_burst_continues(self):
        session = IpcSession()
        try:
            session.write_raw(
                "{nope\n"
                '{"type":"focus","request_id":"req-after-burst","pane_id":"w1:p1"}\n'
            )
            self.assertTrue(session.wait_for_messages(2, timeout=2.0), session.capture.raw())
            messages = session.messages()
            _assert_structured_error(self, messages[0], request_id=None)
            _assert_action_result(self, messages[1], "req-after-burst", True)
            self.assertEqual(session.helper.focus_calls, ["w1:p1"])
        finally:
            session.close()

    def test_stdin_eof_exits_ipc_reader_cleanly(self):
        session = IpcSession()
        try:
            session.close_stdin()
            timeout = 2.0
            started = time.monotonic()
            session.ipc.join(timeout=timeout)
            elapsed = time.monotonic() - started
            self.assertLess(
                elapsed,
                timeout,
                "IPC reader hung after stdin EOF (join used the full %.1fs bound)"
                % timeout,
            )
            thread = session.ipc._thread
            if thread is not None:
                self.assertFalse(
                    thread.is_alive(),
                    "IPC reader thread still alive after stdin EOF",
                )
        finally:
            session.close()


class TestIpcSecurity(_IpcLoopTest):
    def test_protocol_output_omits_fake_backend_exception_details(self):
        leaky = RpcError(
            "focus_failed",
            "%s | %s | %s | %s" % (FAKE_TRACEBACK, FAKE_SOCKET_PATH, FAKE_SNAPSHOT, FAKE_EXCEPTION_TEXT),
        )
        self.session.helper.focus_side_effect = leaky
        self.session.write_command({
            "type": "focus",
            "request_id": "req-sec",
            "pane_id": "w1:p1",
        })
        msg = self._wait_one()
        raw = self.session.capture.raw()
        _assert_no_leak_markers(self, raw)
        _assert_no_leak_markers(self, msg.get("message", ""))
        self.assertEqual(msg.get("message"), "Unable to focus pane.")
        self.assertNotIn("w1:p1", msg.get("message", ""))


if __name__ == "__main__":
    unittest.main()
