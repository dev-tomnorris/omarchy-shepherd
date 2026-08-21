"""Resolve the Herdr Unix socket path."""

import os


def resolve_socket_path(environ=None):
    """Resolve Herdr socket path per documented precedence.

    ``environ is None`` uses the real process environment (production).
    An explicit mapping uses only that mapping — never ``os.environ``,
    process ``HOME``, or ``expanduser`` fallbacks.

    Precedence:

    1. nonempty ``HERDR_SOCKET_PATH``
    2. nonempty ``HERDR_SESSION`` under config home
    3. default ``<config_home>/herdr/herdr.sock``

    Config home when using an injected mapping:

    * nonempty ``XDG_CONFIG_HOME``; else
    * nonempty ``HOME`` joined with ``.config``; else
    * unavailable (raises a fixed ``ValueError`` for session/default paths)

    Production (``environ is None``) keeps historical behavior:
    ``XDG_CONFIG_HOME`` or ``expanduser("~/.config")``.
    """
    if environ is None:
        env = os.environ
        config_home = env.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    else:
        env = environ
        config_home = _injected_config_home(env)

    socket_path = env.get("HERDR_SOCKET_PATH")
    if socket_path:
        return socket_path
    session = env.get("HERDR_SESSION")
    if session:
        if not config_home:
            raise ValueError("Herdr config home unavailable")
        return os.path.join(config_home, "herdr", "sessions", session, "herdr.sock")
    if not config_home:
        raise ValueError("Herdr config home unavailable")
    return os.path.join(config_home, "herdr", "herdr.sock")


def _injected_config_home(env):
    """Config home from an injected mapping only (no process fallback)."""
    xdg = env.get("XDG_CONFIG_HOME")
    if xdg:
        return xdg
    home = env.get("HOME")
    if home:
        return os.path.join(home, ".config")
    return None
