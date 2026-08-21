#!/usr/bin/env python3
"""Shepherd Helper: connect to Herdr and emit normalized state for QML."""

import os

from helper.presentation import build_presentation_descriptor
from helper.runtime import Helper
from helper.socket_path import resolve_socket_path


def build_helper(environ=None, **helper_kwargs):
    """Create a Helper from one frozen environment snapshot.

    Snapshots ``os.environ`` (or an injected mapping) exactly once, then derives
    both ``socket_path`` and ``presentation`` from that snapshot so they cannot
    disagree. Callers must not pass ``socket_path`` or ``presentation`` here.
    """
    if "socket_path" in helper_kwargs or "presentation" in helper_kwargs:
        raise TypeError("build_helper owns socket_path and presentation")
    env_snapshot = dict(os.environ if environ is None else environ)
    socket_path = resolve_socket_path(env_snapshot)
    presentation = build_presentation_descriptor(env_snapshot)
    return Helper(
        socket_path=socket_path,
        presentation=presentation,
        **helper_kwargs,
    )


def main():
    helper = build_helper()
    try:
        helper.run()
    except KeyboardInterrupt:
        helper.stop()


if __name__ == "__main__":
    main()
