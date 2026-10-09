# SSH helper

`connect.py` uses the packaged `board-known_hosts` and requires
`FZ3B_SSH_USER` and `FZ3B_SSH_PASSWORD` in the process environment. It stores
no credentials and rejects unknown host keys. The host needs Python 3.12 with
Paramiko/CFFI available. This replaces current-release dependence on the old
`artifacts/board-debug-20261004/serial/board-known_hosts` path.

