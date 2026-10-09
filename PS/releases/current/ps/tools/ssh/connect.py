from __future__ import print_function

import os
import pathlib
import socket

import paramiko


HERE = pathlib.Path(__file__).resolve().parent


def connect(host="192.168.1.254", source="192.168.1.10"):
    """Connect without persisting credentials in the release package."""
    username = os.environ["FZ3B_SSH_USER"]
    password = os.environ["FZ3B_SSH_PASSWORD"]
    client = paramiko.SSHClient()
    client.load_host_keys(str(HERE / "board-known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    sock = socket.socket()
    sock.bind((source, 0))
    sock.connect((host, 22))
    client.connect(
        hostname=host,
        username=username,
        password=password,
        sock=sock,
        allow_agent=False,
        look_for_keys=False,
        timeout=10,
        banner_timeout=10,
        auth_timeout=10,
    )
    return client

