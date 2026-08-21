"""QML ↔ helper JSON Lines IPC. Snapshot/focus use one-shot RPC, not the subscribe socket."""

import codecs
import io
import json
import os
import select
import sys
from threading import Lock, Thread

from helper.presentation import sanitize_presentation_descriptor
from helper.rpc import RpcDisconnected, RpcError, RpcTimeout

FOCUS_FAILURE_MESSAGE = "Unable to focus pane."
REFRESH_FAILURE_MESSAGE = "Unable to refresh state."
MAX_LINE_BYTES = 65536


def _diag(message):
    sys.stderr.write("Helper: %s\n" % message)
    sys.stderr.flush()


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _pending_byte_length(text):
    return len(text.encode("utf-8"))


def _reject_oversized_pending(ipc, pending):
    if "\n" in pending or _pending_byte_length(pending) <= MAX_LINE_BYTES:
        return pending
    ipc.send_error(None, "invalid_json", "Line too long")
    return ""


class HelperIPC:
    def __init__(self, helper, infile=None, outfile=None):
        self.helper = helper
        self.infile = infile if infile is not None else sys.stdin
        self.outfile = outfile if outfile is not None else sys.stdout
        self.lock = Lock()
        self._thread = None
        self.running = False

    def start(self):
        self.running = True
        self._thread = Thread(target=self._read_loop, name="shepherd-ipc", daemon=False)
        self._thread.start()

    def stop(self):
        self.running = False

    def join(self, timeout=2.0):
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)

    def send(self, msg):
        with self.lock:
            self.outfile.write(json.dumps(msg) + "\n")
            self.outfile.flush()

    def send_state(self, state, connection="connected", stale=False, presentation=None):
        if presentation is None:
            presentation = getattr(self.helper, "presentation", None)
        # Sanitize at the privacy boundary: only the four presentation keys,
        # with argv copied. Extra keys and malformed values never reach stdout.
        safe_presentation = sanitize_presentation_descriptor(presentation)
        self.send({
            "type": "state",
            "connection": connection,
            "stale": stale,
            "agents": state.get("agents", []),
            "counts": state.get("counts", {}),
            "presentation": safe_presentation,
        })

    def send_action_result(self, req_id, ok, message=None):
        result = {"type": "action_result", "request_id": req_id, "ok": ok}
        if message:
            result["message"] = message
        self.send(result)

    def send_error(self, req_id, code, message):
        self.send({"type": "error", "request_id": req_id, "code": code, "message": message})

    def _read_loop(self):
        try:
            fd = self.infile.fileno()
        except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
            fd = None

        if fd is None:
            self._read_loop_readline()
            return

        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        pending = ""
        while self.running:
            pending = _reject_oversized_pending(self, pending)
            while self.running and "\n" in pending:
                line, pending = pending.split("\n", 1)
                if _pending_byte_length(line) > MAX_LINE_BYTES:
                    self.send_error(None, "invalid_json", "Line too long")
                    continue
                self._handle_line(line)
            if not self.running:
                return
            try:
                ready, _, _ = select.select([fd], [], [], 0.2)
            except (OSError, ValueError, TypeError):
                if not self.running:
                    return
                continue
            if not ready:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                self.running = False
                self._stop_helper_on_eof()
                return
            if not chunk:
                pending += decoder.decode(b"", final=True)
                pending = _reject_oversized_pending(self, pending)
                if pending.strip():
                    self._handle_line(pending)
                self.running = False
                self._stop_helper_on_eof()
                return
            pending += decoder.decode(chunk)

    def _read_loop_readline(self):
        while self.running:
            try:
                line = self.infile.readline()
            except Exception:
                if not self.running:
                    return
                continue
            if not line:
                self.running = False
                self._stop_helper_on_eof()
                return
            self._handle_line(line)

    def _stop_helper_on_eof(self):
        # QML Process closes stdin on stop; exit the helper session cleanly.
        helper = self.helper
        if helper is None:
            return
        stop = getattr(helper, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass

    def _handle_line(self, line):
        line = line.strip()
        if not line:
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            self.send_error(None, "invalid_json", "Malformed JSON")
            return
        if not isinstance(msg, dict):
            self.send_error(None, "invalid_message", "Message must be a JSON object")
            return
        cmd_type = msg.get("type")
        if cmd_type == "focus":
            self._handle_focus(msg)
        elif cmd_type == "refresh":
            self._handle_refresh(msg)
        else:
            self.send_error(self._correlation_id(msg), "unknown_command", "Unknown command")

    def _correlation_id(self, msg):
        req_id = msg.get("request_id")
        if _nonempty_string(req_id):
            return req_id
        return None

    def _validated_request_id(self, msg):
        if "request_id" not in msg or msg.get("request_id") is None:
            self.send_error(None, "missing_param", "Missing request_id")
            return None
        req_id = msg.get("request_id")
        if isinstance(req_id, str) and not req_id.strip():
            self.send_error(None, "missing_param", "Missing request_id")
            return None
        if not isinstance(req_id, str):
            self.send_error(None, "invalid_param", "Invalid request_id")
            return None
        return req_id

    def _handle_focus(self, msg):
        req_id = self._validated_request_id(msg)
        if req_id is None:
            return
        if "pane_id" not in msg or msg.get("pane_id") is None:
            self.send_error(req_id, "missing_param", "Missing pane_id")
            return
        pane_id = msg.get("pane_id")
        if isinstance(pane_id, str) and not pane_id.strip():
            self.send_error(req_id, "missing_param", "Missing pane_id")
            return
        if not isinstance(pane_id, str):
            self.send_error(req_id, "invalid_param", "Invalid pane_id")
            return
        try:
            self.helper.focus_agent(pane_id)
            self.send_action_result(req_id, True)
        except (RpcDisconnected, RpcTimeout, OSError):
            _diag("focus failed")
            self.send_error(req_id, "connection_lost", "Herdr socket closed")
        except (RpcError, Exception):
            _diag("focus failed")
            self.send_action_result(req_id, False, FOCUS_FAILURE_MESSAGE)

    def _handle_refresh(self, msg):
        req_id = self._validated_request_id(msg)
        if req_id is None:
            return
        try:
            self.helper.refresh_snapshot(reason="ipc")
            self.send_action_result(req_id, True)
        except (RpcDisconnected, RpcTimeout, OSError):
            _diag("refresh failed")
            self.send_error(req_id, "connection_lost", "Herdr socket closed")
            self.helper.note_connection_lost()
        except (RpcError, Exception):
            _diag("refresh failed")
            self.send_action_result(req_id, False, REFRESH_FAILURE_MESSAGE)
