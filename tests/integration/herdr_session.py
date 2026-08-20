"""Disposable named Herdr session helpers for live integration tests."""

import atexit
import os
import shutil
import subprocess
import tempfile
import time
import uuid

SESSION_PREFIX = "shepherd-it-"
LIVE_HERDR_ENV = "SHEPHERD_RUN_LIVE_HERDR"


def live_herdr_enabled():
    return os.environ.get(LIVE_HERDR_ENV) == "1"


def live_herdr_skip_reason():
    if not live_herdr_enabled():
        return "live Herdr integration requires SHEPHERD_RUN_LIVE_HERDR=1"
    if not herdr_available():
        return "herdr 0.8.x not available"
    return None


def require_live_herdr_opt_in():
    reason = live_herdr_skip_reason()
    if reason:
        raise RuntimeError(reason)


def herdr_available():
    try:
        result = subprocess.run(
            ["herdr", "--version"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "0.8." in (result.stdout or result.stderr or "")


def config_home():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def default_socket_path():
    return os.path.join(config_home(), "herdr", "herdr.sock")


def generate_session_name():
    name = SESSION_PREFIX + uuid.uuid4().hex[:12]
    validate_session_name(name)
    return name


def validate_session_name(name):
    if not name or not isinstance(name, str):
        raise ValueError("session name must be a non-empty string")
    if not name.startswith(SESSION_PREFIX):
        raise ValueError("session name must begin with %r" % SESSION_PREFIX)
    if name == "default":
        raise ValueError("session name must not be 'default'")


def session_socket_path(session_name):
    validate_session_name(session_name)
    return os.path.join(config_home(), "herdr", "sessions", session_name, "herdr.sock")


def assert_not_default_target(session_name, socket_path):
    validate_session_name(session_name)
    if session_name == "default":
        raise RuntimeError("refusing default Herdr session")
    if os.path.normpath(socket_path) == os.path.normpath(default_socket_path()):
        raise RuntimeError("refusing default Herdr socket")


def default_server_running():
    try:
        result = subprocess.run(
            ["herdr", "status", "server"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "status: running" in result.stdout


class DisposableHerdrSession:
    """Create, use, and destroy exactly one shepherd-it-* Herdr session."""

    def __init__(self):
        require_live_herdr_opt_in()
        self.session_name = generate_session_name()
        self.socket_path = session_socket_path(self.session_name)
        assert_not_default_target(self.session_name, self.socket_path)
        self.project_dir = tempfile.mkdtemp(prefix="shepherd-it-proj-")
        self.server_proc = None
        self._cleaned = False
        atexit.register(self.cleanup)

    def herdr(self, *args, timeout=30.0):
        validate_session_name(self.session_name)
        cmd = ["herdr", "--session", self.session_name, *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def start_server(self, timeout=10.0):
        assert_not_default_target(self.session_name, self.socket_path)
        self.server_proc = subprocess.Popen(
            ["herdr", "--session", self.session_name, "server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if os.path.exists(self.socket_path):
                result = self.herdr("status", "server", timeout=5.0)
                if result.returncode == 0 and "status: running" in result.stdout:
                    if self.session_name in result.stdout:
                        return
            time.sleep(0.1)
        raise RuntimeError("named Herdr session failed to start")

    def stop_server(self):
        result = self.herdr("session", "stop", self.session_name, timeout=10.0)
        if self.server_proc is not None:
            try:
                self.server_proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.server_proc.terminate()
                try:
                    self.server_proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self.server_proc.kill()
            self.server_proc = None
        return result

    def delete_session(self):
        result = self.herdr("session", "delete", self.session_name, timeout=10.0)
        return result

    def seed_minimal_state(self):
        result = self.herdr(
            "workspace", "create",
            "--cwd", self.project_dir,
            "--label", "IT",
            "--focus",
            timeout=15.0,
        )
        if result.returncode != 0:
            raise RuntimeError("workspace create failed")
        import json
        payload = json.loads(result.stdout)
        pane1 = payload["result"]["root_pane"]["pane_id"]
        self.herdr(
            "pane", "report-agent", pane1,
            "--source", "it",
            "--agent", "fake-agent",
            "--state", "working",
            "--message", "it",
            timeout=10.0,
        )
        split = self.herdr(
            "pane", "split", pane1,
            "--direction", "down",
            "--focus", "--no-focus",
            timeout=10.0,
        )
        if split.returncode != 0:
            raise RuntimeError("pane split failed")
        pane2 = json.loads(split.stdout)["result"]["pane"]["pane_id"]
        self.herdr(
            "pane", "report-agent", pane2,
            "--source", "it",
            "--agent", "fake-agent-2",
            "--state", "idle",
            "--message", "it",
            timeout=10.0,
        )
        return {"pane1": pane1, "pane2": pane2}

    def cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        try:
            if self.server_proc is not None:
                self.server_proc.terminate()
                try:
                    self.server_proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self.server_proc.kill()
                self.server_proc = None
            self.herdr("session", "stop", self.session_name, timeout=10.0)
        except Exception:
            pass
        try:
            self.herdr("session", "delete", self.session_name, timeout=10.0)
        except Exception:
            pass
        shutil.rmtree(self.project_dir, ignore_errors=True)
