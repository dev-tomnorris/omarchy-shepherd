"""Protocol-faithful fake Herdr 0.8.0 socket server for tests."""

import json
import os
import socket
from threading import Lock, Thread


def default_snapshot():
    return {
        "version": "0.8.0",
        "protocol": 20,
        "focused_workspace_id": "w1",
        "focused_tab_id": "w1:t1",
        "focused_pane_id": "w1:p1",
        "workspaces": [
            {
                "workspace_id": "w1",
                "number": 1,
                "label": "Project",
                "focused": True,
                "pane_count": 2,
                "tab_count": 1,
                "active_tab_id": "w1:t1",
                "agent_status": "working",
            }
        ],
        "tabs": [
            {
                "tab_id": "w1:t1",
                "workspace_id": "w1",
                "number": 1,
                "label": "1",
                "focused": True,
                "pane_count": 2,
                "agent_status": "working",
            }
        ],
        "panes": [
            {
                "pane_id": "w1:p1",
                "terminal_id": "t1",
                "workspace_id": "w1",
                "tab_id": "w1:t1",
                "focused": True,
                "agent_status": "working",
            },
            {
                "pane_id": "w1:p2",
                "terminal_id": "t2",
                "workspace_id": "w1",
                "tab_id": "w1:t1",
                "focused": False,
                "agent_status": "blocked",
            },
        ],
        "agents": [
            {
                "pane_id": "w1:p1",
                "agent": "opencode",
                "name": "opencode",
                "agent_status": "working",
                "focused": True,
                "tab_id": "w1:t1",
                "workspace_id": "w1",
                "terminal_id": "t1",
                "revision": 1,
            },
            {
                "pane_id": "w1:p2",
                "agent": "formatter",
                "name": "formatter",
                "agent_status": "blocked",
                "focused": False,
                "tab_id": "w1:t1",
                "workspace_id": "w1",
                "terminal_id": "t2",
                "revision": 1,
            },
        ],
        "layouts": [],
    }


class ConnectionRecord:
    def __init__(self, kind):
        self.kind = kind
        self.methods = []
        self.closed = False
        self.second_request_rejected = False
        self.client = None


class FakeHerdrServer:
    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.snapshot = default_snapshot()
        self.sock = None
        self.running = False
        self.accept_thread = None
        self.records = []
        self.thread_errors = []
        self._lock = Lock()
        self._subscribers = []
        self._client_threads = []
        self.last_subscriptions = []

    def start(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        parent = os.path.dirname(self.socket_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.socket_path)
        self.sock.listen(16)
        self.sock.settimeout(0.2)
        self.running = True
        self.accept_thread = Thread(target=self._accept_loop, name="fake-herdr-accept", daemon=False)
        self.accept_thread.start()

    def stop(self):
        self.running = False
        self.disconnect_subscribers()
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        if self.accept_thread is not None:
            self.accept_thread.join(timeout=2.0)
        for thread in list(self._client_threads):
            thread.join(timeout=2.0)
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass

    def rpc_records(self):
        return [r for r in self.records if r.kind == "rpc"]

    def subscribe_records(self):
        return [r for r in self.records if r.kind == "subscribe"]

    def push(self, event_obj):
        line = (json.dumps(event_obj) + "\n").encode("utf-8")
        with self._lock:
            subscribers = list(self._subscribers)
        dead = []
        for client in subscribers:
            try:
                client.sendall(line)
            except OSError:
                dead.append(client)
        for client in dead:
            self._drop_subscriber(client)

    def push_lifecycle(self, event_name, data):
        self.push({"event": event_name, "data": data})

    def push_scoped(self, event_name, data):
        self.push({"event": event_name, "data": data})

    def disconnect_subscribers(self):
        with self._lock:
            subscribers = list(self._subscribers)
            self._subscribers = []
        for client in subscribers:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass

    def _accept_loop(self):
        while self.running:
            try:
                client, _addr = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            thread = Thread(target=self._safe_handle, args=(client,), name="fake-herdr-client", daemon=False)
            self._client_threads.append(thread)
            thread.start()

    def _safe_handle(self, client):
        try:
            self._handle_client(client)
        except Exception as exc:
            self.thread_errors.append(exc)
        finally:
            try:
                client.close()
            except OSError:
                pass

    def _handle_client(self, client):
        client.settimeout(0.2)
        buffer = b""
        while self.running:
            try:
                chunk = client.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            buffer += chunk
            if b"\n" not in buffer:
                continue
            line, rest = buffer.split(b"\n", 1)
            buffer = rest
            try:
                msg = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(client, {"id": "", "error": {"code": "invalid_request", "message": "invalid json"}})
                return
            method = msg.get("method")
            req_id = msg.get("id")
            params = msg.get("params") or {}
            if method == "events.subscribe":
                self._handle_subscribe(client, req_id, params, buffer)
                return
            self._handle_rpc(client, req_id, method, params)
            return

    def _handle_rpc(self, client, req_id, method, params):
        record = ConnectionRecord("rpc")
        record.methods.append(method)
        record.client = client
        with self._lock:
            self.records.append(record)
        if method == "session.snapshot":
            body = {"id": req_id, "result": {"type": "session_snapshot", "snapshot": self.snapshot}}
        elif method == "agent.focus":
            target = params.get("target", "")
            if isinstance(target, str) and ":" in target:
                body = {"id": req_id, "result": {"type": "ok"}}
            else:
                body = {"id": req_id, "error": {"code": "invalid_param", "message": "Invalid target"}}
        else:
            body = {"id": req_id, "error": {"code": "method_not_found", "message": "Unknown method"}}
        self._send(client, body)
        record.closed = True
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _handle_subscribe(self, client, req_id, params, remainder):
        record = ConnectionRecord("subscribe")
        record.methods.append("events.subscribe")
        record.client = client
        with self._lock:
            self.records.append(record)
            self._subscribers.append(client)
        subscriptions = params.get("subscriptions") or []
        self.last_subscriptions = subscriptions
        for item in subscriptions:
            if item.get("type") == "pane.agent_status_changed" and not item.get("pane_id"):
                self._send(
                    client,
                    {"id": req_id, "error": {"code": "invalid_request", "message": "missing field pane_id"}},
                )
                record.closed = True
                self._drop_subscriber(client)
                return
        self._send(client, {"id": req_id, "result": {"type": "subscription_started"}})
        buffer = remainder
        while self.running:
            if b"\n" in buffer:
                record.second_request_rejected = True
                self._send(client, {"id": "", "error": {"code": "invalid_request", "message": "subscribe is exclusive"}})
                record.closed = True
                self._drop_subscriber(client)
                return
            try:
                chunk = client.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                record.closed = True
                self._drop_subscriber(client)
                return
            if not chunk:
                record.closed = True
                self._drop_subscriber(client)
                return
            buffer += chunk

    def _drop_subscriber(self, client):
        with self._lock:
            if client in self._subscribers:
                self._subscribers.remove(client)
        try:
            client.close()
        except OSError:
            pass

    def _send(self, client, obj):
        try:
            client.sendall((json.dumps(obj) + "\n").encode("utf-8"))
        except OSError:
            pass
