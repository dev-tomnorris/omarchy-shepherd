"""Newline-delimited JSON framing and Herdr 0.8.0 envelope classification."""

import json
import uuid


class ProtocolError(Exception):
    """A complete frame that is not a recognized Herdr envelope."""


class LineBuffer:
    """Accumulate socket bytes and yield complete newline-delimited frames."""

    def __init__(self):
        self._buffer = b""

    def feed(self, chunk):
        """Return complete lines (without the newline) from ``chunk``."""
        if not chunk:
            return []
        self._buffer += chunk
        lines = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            lines.append(line)
        return lines

    def pending(self):
        return self._buffer


def generate_request_id():
    return f"req-{uuid.uuid4()}"


def encode_request(method, params=None, req_id=None):
    request = {
        "id": req_id or generate_request_id(),
        "method": method,
        "params": {} if params is None else params,
    }
    return request["id"], (json.dumps(request) + "\n").encode("utf-8")


def decode_frame(line):
    """Parse one JSON line. Empty/whitespace frames yield None."""
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    text = line.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError("malformed JSON frame") from exc


def classify_message(msg):
    """Classify a decoded Herdr JSON object.

    Returns a dict with ``kind`` in:
      rpc_result, rpc_error, subscribe_ack, lifecycle_push, scoped_push, unknown

    ``events.wait`` uses ``result.type == wait_matched``. That is not a
    subscription push and is never treated as invalidation.
    """
    if not isinstance(msg, dict):
        return {"kind": "unknown", "message": msg}

    if "event" in msg:
        event_name = msg.get("event")
        data = msg.get("data")
        if isinstance(event_name, str) and event_name.find(".") >= 0:
            return {"kind": "scoped_push", "event": event_name, "data": data, "message": msg}
        if isinstance(event_name, str):
            return {"kind": "lifecycle_push", "event": event_name, "data": data, "message": msg}
        return {"kind": "unknown", "message": msg}

    msg_id = msg.get("id")
    if "error" in msg and msg_id is not None:
        return {"kind": "rpc_error", "id": msg_id, "error": msg.get("error"), "message": msg}

    if "result" in msg and msg_id is not None:
        result = msg.get("result")
        result_type = result.get("type") if isinstance(result, dict) else None
        if result_type == "subscription_started":
            return {"kind": "subscribe_ack", "id": msg_id, "result": result, "message": msg}
        return {"kind": "rpc_result", "id": msg_id, "result": result, "message": msg}

    return {"kind": "unknown", "message": msg}


def is_invalidation_push(classified):
    return classified.get("kind") in ("lifecycle_push", "scoped_push")
