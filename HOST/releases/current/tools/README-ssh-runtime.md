# FZ3B SSH Python runtime

This directory preserves the Python 3.12 Paramiko/CFFI dependencies used by
`releases/current/ps/tools/ssh/connect.py`. It does not store credentials.

Offline import check:

```powershell
& 'E:\AIProject\FPGAVibecoding\releases\current\tools\fz3b-ssh-python.ps1' `
  -Command "import paramiko, cryptography, _cffi_backend, connect; print(paramiko.__version__)"
```

For an authorized board connection, set `FZ3B_SSH_USER` and
`FZ3B_SSH_PASSWORD` in the process environment, then invoke `connect.connect()`
through the same launcher. The pinned host key remains in the frozen current PS
package. Do not put credentials in this directory or its manifests.
