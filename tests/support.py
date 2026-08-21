"""Shared test helpers."""

import json
import time
from threading import Lock

from helper.runtime import Helper


DEFAULT_PRESENTATION = {
    "kind": "default",
    "supported": True,
    "app_id": "org.omarchy.herdr",
    "argv": ["herdr"],
}


class JsonlSink:
    def __init__(self):
        self.messages = []
        self._buf = ""
        self.lock = Lock()

    def write(self, text):
        with self.lock:
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line.strip():
                    self.messages.append(json.loads(line))

    def flush(self):
        pass

    def of_type(self, type_name):
        with self.lock:
            return [m for m in self.messages if m.get("type") == type_name]


def wait_until(predicate, timeout=2.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def make_helper(socket_path, presentation=None, **kwargs):
    """Construct a Helper with required fake socket_path and presentation."""
    if presentation is None:
        presentation = dict(DEFAULT_PRESENTATION)
        presentation["argv"] = list(DEFAULT_PRESENTATION["argv"])
    return Helper(socket_path=socket_path, presentation=presentation, **kwargs)
