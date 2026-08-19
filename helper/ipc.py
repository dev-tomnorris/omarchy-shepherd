"""QML ↔ helper JSON Lines IPC. Snapshot/focus use one-shot RPC, not the subscribe socket."""

import json
import select
import sys
from threading import Lock, Thread

from helper.rpc import RpcDisconnected, RpcError, RpcTimeout


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

    def send_state(self, state, connection="connected", stale=False):
        self.send({
            "type": "state",
            "connection": connection,
            "stale": stale,
            "agents": state.get("agents", []),
            "counts": state.get("counts", {}),
        })

    def send_action_result(self, req_id, ok, message=None):
        result = {"type": "action_result", "request_id": req_id, "ok": ok}
        if message:
            result["message"] = message
        self.send(result)

    def send_error(self, req_id, code, message):
        self.send({"type": "error", "request_id": req_id, "code": code, "message": message})

    def _read_loop(self):
        while self.running:
            try:
                ready, _, _ = select.select([self.infile], [], [], 0.2)
            except (OSError, ValueError, TypeError):
                if not self.running:
                    return
                try:
                    line = self.infile.readline()
                except Exception:
                    continue
                if not line:
                    return
                self._handle_line(line)
                continue
            if not ready:
                continue
            line = self.infile.readline()
            if not line:
                return
            self._handle_line(line)

    def _handle_line(self, line):
        line = line.strip()
        if not line:
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            self.send_error(None, "invalid_json", "Malformed JSON")
            return
        cmd_type = msg.get("type")
        req_id = msg.get("request_id")
        if cmd_type == "focus":
            self._handle_focus(msg, req_id)
        elif cmd_type == "refresh":
            self._handle_refresh(req_id)
        else:
            self.send_error(req_id, "unknown_command", f"Unknown command: {cmd_type}")

    def _handle_focus(self, msg, req_id):
        pane_id = msg.get("pane_id")
        if not pane_id:
            self.send_error(req_id, "missing_param", "Missing pane_id")
            return
        try:
            self.helper.focus_agent(pane_id)
            self.send_action_result(req_id, True)
        except RpcError as exc:
            self.send_action_result(req_id, False, str(exc) or "Focus failed")
        except (RpcDisconnected, RpcTimeout, OSError):
            self.send_error(req_id, "connection_lost", "Herdr socket closed")
        except Exception:
            self.send_error(req_id, "socket_error", "Socket error")

    def _handle_refresh(self, req_id):
        try:
            self.helper.refresh_snapshot(reason="ipc")
            self.send_action_result(req_id, True)
        except (RpcDisconnected, RpcTimeout, OSError):
            self.send_error(req_id, "connection_lost", "Herdr socket closed")
            self.helper.note_connection_lost()
        except Exception:
            self.send_error(req_id, "socket_error", "Socket error")
            self.helper.note_connection_lost()
