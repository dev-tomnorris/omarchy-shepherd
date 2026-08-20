"""Dedicated events.subscribe connection with a single reader owner."""

import socket
import time

from helper.protocol import (
    LineBuffer,
    ProtocolError,
    classify_message,
    decode_frame,
    encode_request,
    is_invalidation_push,
)


class SubscribeError(Exception):
    """Subscribe handshake or stream failed."""


class SubscribeSession:
    """One exclusive Herdr events.subscribe stream."""

    def __init__(self, socket_path, recv_timeout=0.2, ack_timeout=5.0, sock_factory=None):
        self.socket_path = socket_path
        self.recv_timeout = recv_timeout
        self.ack_timeout = ack_timeout
        self._sock_factory = sock_factory or (lambda: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
        self.sock = None
        self.buffer = LineBuffer()
        self.request_id = None

    def open(self, subscriptions):
        self.close()
        sock = self._sock_factory()
        try:
            sock.settimeout(self.recv_timeout)
            sock.connect(self.socket_path)
            req_id, payload = encode_request("events.subscribe", {"subscriptions": subscriptions})
            sock.sendall(payload)
            self.sock = sock
            self.request_id = req_id
            self.buffer = LineBuffer()
            self._await_ack()
            return req_id
        except Exception:
            self.sock = None
            try:
                sock.close()
            except OSError:
                pass
            raise

    def recv_classified(self):
        """Return the next classified message, None on idle timeout, ``EOF`` on disconnect."""
        if self.sock is None:
            return "EOF"
        try:
            chunk = self.sock.recv(4096)
        except socket.timeout:
            return None
        except OSError:
            return "EOF"
        if not chunk:
            return "EOF"
        frames = self.buffer.feed(chunk)
        if not frames:
            return None
        messages = []
        for raw in frames:
            frame = decode_frame(raw)
            if frame is None:
                continue
            messages.append(classify_message(frame))
        return messages

    def close(self):
        sock = self.sock
        self.sock = None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def _await_ack(self):
        deadline = time.monotonic() + self.ack_timeout
        while time.monotonic() < deadline:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                continue
            except OSError as exc:
                raise SubscribeError("subscribe socket failed during ack") from exc
            if not chunk:
                raise SubscribeError("subscribe peer closed before acknowledgement")
            for raw in self.buffer.feed(chunk):
                frame = decode_frame(raw)
                if frame is None:
                    continue
                classified = classify_message(frame)
                if classified["kind"] == "subscribe_ack" and classified.get("id") == self.request_id:
                    return
                if is_invalidation_push(classified):
                    raise SubscribeError("event push arrived before subscription_started")
                raise SubscribeError("unexpected message before subscription_started")
        raise SubscribeError("subscription_started acknowledgement timed out")
