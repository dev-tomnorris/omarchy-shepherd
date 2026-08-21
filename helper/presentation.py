"""Deterministic Herdr session presentation descriptors for Omarchy launch.

Pure classification only: no terminal launching, subprocesses, sockets, or
filesystem writes. Callers inject the environment and optional config home.

Configuration-root selection never consults the process home, passwd database,
``os.environ``, or the process working directory. Relative paths and process
``expanduser``/``abspath`` are not used for classification.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


_DEFAULT_APP_ID = "org.omarchy.herdr"
_APP_ID_PREFIX = "org.omarchy.herdr.session-"
_PRESENTATION_KEYS = ("kind", "supported", "app_id", "argv")
_VALID_KINDS = frozenset(("default", "named", "socket_override"))


def build_presentation_descriptor(env, config_dir=None):
    """Build a JSON-serializable presentation descriptor from env.

    ``env`` is an injected mapping (never the live process environment unless
    the caller passes ``os.environ``). ``config_dir`` optionally overrides the
    XDG-style configuration home — the parent directory that contains
    ``herdr/`` — matching the role of ``XDG_CONFIG_HOME``.

    Default and named-session descriptors do not require a resolvable
    configuration home. Conventional socket-override classification does, and
    uses only:

    1. absolute explicit ``config_dir``;
    2. nonempty absolute ``env["XDG_CONFIG_HOME"]``;
    3. nonempty absolute ``env["HOME"]`` joined with ``.config``;
    4. otherwise conventional classification is unavailable.

    Returns a dict with exactly ``kind``, ``supported``, ``app_id``, and
    ``argv``. Does not mutate ``env``.
    """
    socket_path = env.get("HERDR_SOCKET_PATH")
    if socket_path:
        config_home = _resolve_config_home(env, config_dir)
        return _classify_socket_override(socket_path, env, config_home)

    session = env.get("HERDR_SESSION")
    if session:
        return _named_descriptor(session)

    return _default_descriptor()


def sanitize_presentation_descriptor(value):
    """Return an isolated, JSON-safe presentation dict for state publication.

    Policy for malformed or incomplete internal values: emit the standard
    unsupported socket_override descriptor. Never raise with path/session
    details, never forward extra keys, and always copy ``argv``.

    Input must contain exactly the keys kind/supported/app_id/argv. Named
    descriptors must carry the Task 1 SHA-256 app ID for argv[2]. Boolean
    ``supported`` must be the True/False singletons (not 0/1).
    """
    if not isinstance(value, dict):
        return _unsupported_socket_override()
    if set(value.keys()) != set(_PRESENTATION_KEYS):
        return _unsupported_socket_override()

    kind = value.get("kind")
    supported = value.get("supported")
    app_id = value.get("app_id")
    argv = value.get("argv")

    if kind not in _VALID_KINDS:
        return _unsupported_socket_override()
    # Reject integer 0/1 and other truthy/falsy stand-ins.
    if supported is not True and supported is not False:
        return _unsupported_socket_override()
    if not isinstance(app_id, str):
        return _unsupported_socket_override()
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        return _unsupported_socket_override()

    if kind == "default":
        if supported is not True or app_id != _DEFAULT_APP_ID or argv != ["herdr"]:
            return _unsupported_socket_override()
    elif kind == "named":
        if supported is not True:
            return _unsupported_socket_override()
        if len(argv) != 3 or argv[0] != "herdr" or argv[1] != "--session":
            return _unsupported_socket_override()
        # Preserve Task 1 truthiness: whitespace-only names remain accepted
        # (nonempty string), matching socket_path / build_presentation_descriptor.
        if not argv[2]:
            return _unsupported_socket_override()
        if app_id != _named_app_id(argv[2]):
            return _unsupported_socket_override()
    else:  # socket_override
        if supported is not False or app_id != "" or argv != []:
            return _unsupported_socket_override()

    return {
        "kind": kind,
        "supported": supported,
        "app_id": app_id,
        "argv": list(argv),
    }


def _resolve_config_home(env, config_dir):
    """Return a safe absolute config home, or None if unavailable."""
    if config_dir is not None:
        return _safe_absolute_path(str(config_dir))

    xdg = env.get("XDG_CONFIG_HOME")
    if xdg:
        # Present but unsafe/relative/tilde → do not fall through to HOME.
        if not isinstance(xdg, str) or xdg.startswith("~"):
            return None
        return _safe_absolute_path(xdg)

    home = env.get("HOME")
    if home:
        if not isinstance(home, str) or home.startswith("~"):
            return None
        home_abs = _safe_absolute_path(home)
        if home_abs is None:
            return None
        return _safe_absolute_path(os.path.join(home_abs, ".config"))

    return None


def _default_descriptor():
    return {
        "kind": "default",
        "supported": True,
        "app_id": _DEFAULT_APP_ID,
        "argv": ["herdr"],
    }


def _named_descriptor(session_name):
    return {
        "kind": "named",
        "supported": True,
        "app_id": _named_app_id(session_name),
        "argv": ["herdr", "--session", session_name],
    }


def _unsupported_socket_override():
    return {
        "kind": "socket_override",
        "supported": False,
        "app_id": "",
        "argv": [],
    }


def _named_app_id(session_name):
    digest = hashlib.sha256(session_name.encode("utf-8")).hexdigest()[:12]
    return _APP_ID_PREFIX + digest


def _classify_socket_override(socket_path, env, config_home):
    normalized = _resolve_socket_path_text(socket_path, env)
    if normalized is None:
        return _unsupported_socket_override()
    if config_home is None:
        return _unsupported_socket_override()

    herdr_root = _safe_absolute_path(os.path.join(config_home, "herdr"))
    if herdr_root is None:
        return _unsupported_socket_override()

    default_sock = _safe_absolute_path(os.path.join(herdr_root, "herdr.sock"))
    if default_sock is not None and normalized == default_sock:
        return _default_descriptor()

    session_name = _conventional_named_session(normalized, herdr_root)
    if session_name is not None:
        return _named_descriptor(session_name)

    return _unsupported_socket_override()


def _resolve_socket_path_text(socket_path, env):
    """Resolve HERDR_SOCKET_PATH using only injected HOME for ``~/...``."""
    if not isinstance(socket_path, str):
        return None

    if socket_path.startswith("~/"):
        home = env.get("HOME")
        if not isinstance(home, str) or home.startswith("~"):
            return None
        home_abs = _safe_absolute_path(home)
        if home_abs is None:
            return None
        return _safe_absolute_path(home_abs + socket_path[1:])

    # Bare "~" or "~otheruser/..." — never consult passwd / process home.
    if socket_path.startswith("~"):
        return None

    return _safe_absolute_path(socket_path)


def _safe_absolute_path(path_text):
    """Return a normalized absolute path, or None if relative/unsafe.

    Does not call ``expanduser`` or ``abspath`` (those consult process state).
    """
    if not isinstance(path_text, str) or not path_text:
        return None
    if not os.path.isabs(path_text):
        return None
    # Inspect raw components before normpath collapses them.
    if _has_dot_or_traversal_segment(path_text):
        return None
    normalized = os.path.normpath(path_text)
    if not os.path.isabs(normalized):
        return None
    if _has_dot_or_traversal_segment(normalized):
        return None
    return normalized


def _has_dot_or_traversal_segment(path_text):
    return any(part in (".", "..") for part in path_text.split(os.sep))


def _conventional_named_session(normalized_socket, herdr_root):
    """Return session name if socket is exactly herdr_root/sessions/<name>/herdr.sock."""
    sock = Path(normalized_socket)
    if sock.name != "herdr.sock":
        return None

    session_dir = sock.parent
    sessions_dir = session_dir.parent
    root = sessions_dir.parent

    if str(root) != herdr_root:
        return None
    if sessions_dir.name != "sessions":
        return None

    name = session_dir.name
    if not _is_safe_session_component(name):
        return None

    expected = os.path.normpath(
        os.path.join(herdr_root, "sessions", name, "herdr.sock")
    )
    if normalized_socket != expected:
        return None

    # Lexical relative parts without os.path.relpath (which calls abspath).
    prefix = herdr_root.rstrip(os.sep) + os.sep
    if not normalized_socket.startswith(prefix):
        return None
    relative = normalized_socket[len(prefix) :]
    parts = tuple(p for p in relative.split(os.sep) if p)
    if parts != ("sessions", name, "herdr.sock"):
        return None

    return name


def _is_safe_session_component(name):
    if not isinstance(name, str) or not name:
        return False
    if name in (".", ".."):
        return False
    if "/" in name or os.sep in name:
        return False
    if os.altsep and os.altsep in name:
        return False
    if Path(name).name != name:
        return False
    return True
