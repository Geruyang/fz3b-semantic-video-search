"""Transfer task artifacts through the established SSH channel; never print credentials."""
import argparse
import hashlib
import json
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from fz3b_ssh import open_link

ap = argparse.ArgumentParser()
ap.add_argument('--upload', type=Path)
ap.add_argument('--download')
ap.add_argument('--remote', required=True)
ap.add_argument('--local', type=Path)
args = ap.parse_args()
if bool(args.upload) == bool(args.download):
    raise SystemExit('Choose one transfer direction.')
allowed = '/root/rtl_optim-board-20261010/'
if not args.remote.startswith(allowed) or '..' in args.remote.split('/'):
    raise SystemExit('Remote path must remain inside the task board directory.')
client = open_link()
try:
    sftp = client.open_sftp()
    if args.upload:
        raw = args.upload.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        temporary = '/tmp/rtl-optim-upload-' + digest
        sftp.put(str(args.upload), temporary)
        command = ('sudo -n install -D -m 0600 ' + shlex.quote(temporary) + ' ' + shlex.quote(args.remote)
                   + ' && sudo -n sha256sum ' + shlex.quote(args.remote))
        _, out, err = client.exec_command(command)
        result = out.read().decode()
        code = out.channel.recv_exit_status()
        if code or result.split()[0] != digest:
            raise RuntimeError('Upload integrity failed: ' + err.read().decode())
        sftp.remove(temporary)
        print('UPLOAD_VERIFIED', args.upload.name, len(raw), digest)
    else:
        if args.download != args.remote or args.local is None:
            raise SystemExit('Download path/local target missing.')
        _, out, err = client.exec_command('sudo -n cat ' + shlex.quote(args.remote))
        raw = out.read()
        if out.channel.recv_exit_status():
            raise RuntimeError('Download failed: ' + err.read().decode())
        args.local.parent.mkdir(parents=True, exist_ok=True)
        args.local.write_bytes(raw)
        print('DOWNLOAD_VERIFIED', args.local.name, len(raw), hashlib.sha256(raw).hexdigest())
    sftp.close()
finally:
    client.close()
