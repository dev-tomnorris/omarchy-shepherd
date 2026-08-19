#!/usr/bin/env python3
"""Shepherd Helper: connect to Herdr and emit normalized state for QML."""

from helper.runtime import Helper
from helper.socket_path import resolve_socket_path
from helper.normalize import Normalizer
from helper.protocol import generate_request_id


def main():
    helper = Helper()
    try:
        helper.run()
    except KeyboardInterrupt:
        helper.stop()


if __name__ == "__main__":
    main()
