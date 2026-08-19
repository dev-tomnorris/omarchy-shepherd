"""Resolve the Herdr Unix socket path."""

import os


def resolve_socket_path(environ=None):
    """Resolve Herdr socket path per documented precedence.

    config_home = XDG_CONFIG_HOME when nonempty, otherwise ~/.config
    socket_path = HERDR_SOCKET_PATH when nonempty
    else config_home/herdr/sessions/HERDR_SESSION/herdr.sock when HERDR_SESSION nonempty
    else config_home/herdr/herdr.sock
    """
    env = os.environ if environ is None else environ
    config_home = env.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    socket_path = env.get("HERDR_SOCKET_PATH")
    if socket_path:
        return socket_path
    session = env.get("HERDR_SESSION")
    if session:
        return os.path.join(config_home, "herdr", "sessions", session, "herdr.sock")
    return os.path.join(config_home, "herdr", "herdr.sock")
