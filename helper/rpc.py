"""One-shot Herdr RPC: connect, one request, matching response, close."""

import socket
import time

from helper.protocol import (
    LineBuffer,
    ProtocolError,
    classify_message,
    decode_frame,
    encode_request,
)


class RpcError(Exception):
    """Herdr returned an error object for the request."""

    def __init__(self, code, message, payload=None):
        super().__init__(message)
        self.code = code
        self.payload = payload


class RpcDisconnected(Exception):
    """Peer closed the socket before a matching response."""


class RpcTimeout(Exception):
    """No matching response within the deadline."""


class RpcClient:
    """Stateless one-shot Unix-socket RPC client."""

    def __init__(self, socket_path, recv_timeout=0.2, rpc_timeout=5.0, sock_factory=None):
        self.socket_path = socket_path
        self.recv_timeout = recv_timeout
        self.rpc_timeout = rpc_timeout
        self._sock_factory = sock_factory or _default_unix_socket

    def call(self, method, params=None):
        req_id, payload = encode_request(method, params)
        sock = self._sock_factory()
        buffer = LineBuffer()
        try:
            sock.settimeout(self.recv_timeout)
            sock.connect(self.socket_path)
            sock.sendall(payload)
            return self._read_matching_response(sock, buffer, req_id)
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def snapshot(self):
        classified = self.call("session.snapshot", {})
        result = classified["result"]
        if not isinstance(result, dict) or "snapshot" not in result:
            raise ProtocolError("session.snapshot missing result.snapshot")
        return result["snapshot"]

    def agent_focus(self, pane_id):
        return self.call("agent.focus", {"target": pane_id})

    def _read_matching_response(self, sock, buffer, req_id):
        deadline = time.monotonic() + self.rpc_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RpcTimeout("RPC response timed out")
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                raise RpcDisconnected("RPC peer closed before response")
            matched = None
            for raw in buffer.feed(chunk):
                frame = decode_frame(raw)
                if frame is None:
                    continue
                classified = classify_message(frame)
                kind = classified["kind"]
                is_match = (
                    kind in ("rpc_result", "rpc_error", "subscribe_ack")
                    and classified.get("id") == req_id
                )
                if matched is not None:
                    raise ProtocolError("unexpected message on RPC connection")
                if not is_match:
                    raise ProtocolError("unexpected message on RPC connection")
                matched = classified
            if matched is None:
                continue
            if buffer.pending().strip():
                raise ProtocolError("unexpected trailing data after RPC response")
            kind = matched["kind"]
            if kind == "rpc_error":
                err = matched.get("error") or {}
                raise RpcError(err.get("code", "error"), err.get("message", "Herdr error"), err)
            if kind == "subscribe_ack":
                raise ProtocolError("subscription_started on an RPC connection")
            return matched


def _default_unix_socket():
    return socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
