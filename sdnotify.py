"""Minimal systemd notify (no dependencies). Does nothing when not run under systemd.

Used by homenow.py with Type=notify / WatchdogSec= in homenow.service: if the service
stops calling notify("WATCHDOG=1") systemd restarts it.
"""
import os
import socket


def notify(message="WATCHDOG=1"):
    path = os.environ.get("NOTIFY_SOCKET")
    if not path:
        return False
    if path.startswith("@"):  # abstract socket
        path = "\0" + path[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(path)
            s.sendall(message.encode())
        return True
    except OSError:
        return False
