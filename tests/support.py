"""Shared test helpers."""

import json
import time
from threading import Lock


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
