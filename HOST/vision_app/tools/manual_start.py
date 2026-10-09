"""Manual board start after power-up, without enabling any boot services."""
import argparse
import hashlib
import json
import re
import socket
import time
import serial
from vision_app.tools.board_link import ROOT, open_link, run
from vision_app.tools import deploy_r5, deploy_board

REMOTE_CONFIG = '/root/fz3b-vision-console-20261009-001/config.json'


def recover_link(port):
    handle = serial.Serial(port=None, baudrate=115200, timeout=.2, write_timeout=3)
    handle.dtr = handle.rts = False
    handle.port = port
    handle.open()
    def until(token, seconds=10):
        data = b''
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            data += handle.read(8192)
            if token in data:
                return data
        raise TimeoutError('board console response deadline; UART must be available to getty')
    try:
        handle.write(b'\n')
        data = handle.read(8192)
        time.sleep(.3)
        data += handle.read(8192)
        if b'login:' in data:
            text = (ROOT / 'docs/hardware/FZ3B/TF-LINUX-INSTALL.md').read_text(encoding='utf-8')
            username, password = re.findall(r'默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`', text)[0]
            del text
            handle.write(username.encode() + b'\n')
            until(b'Password:')
            handle.write(password.encode() + b'\n')
            del username, password
            until(b'@EdgeBoard:~# ', 15)
        handle.write(b"printf '\\nVISION_MANUAL_READY\\n'\n")
        until(b'\nVISION_MANUAL_READY')
        handle.write(b"ip addr show dev eth0 | grep -q '169.254.220.254/16' || ip addr add 169.254.220.254/16 dev eth0; printf '\\nVISION_LINK_READY\\n'\n")
        until(b'\nVISION_LINK_READY')
    finally:
        handle.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM6')
    parser.add_argument('--restart', action='store_true', help='normally drain and restart this application')
    args = parser.parse_args()
    try:
        client = open_link()
    except (socket.timeout, ConnectionRefusedError, OSError):
        recover_link(args.port)
        client = open_link()
    running = False
    try:
        active = run(client, 'systemctl is-active fz3b-vision-console.service || true').strip()
        if active == 'active' and not args.restart:
            print('Application already active; no board state changed.')
            return
        if active == 'active':
            run(client, 'systemctl stop fz3b-vision-console.service', timeout=370)
        boot_installed = run(client, 'test -f ' + REMOTE_CONFIG + ' && python3 -B -c \'import json; print(int(json.load(open("' + REMOTE_CONFIG + '" )).get("autostart_installed", False)))\' || true').strip() == '1'
        if boot_installed:
            run(client, 'set -e; systemctl start fz3b-app-r5.service; systemctl start fz3b-vision-console.service')
            print('Boot-configured application started through its existing services.')
            return
        run(client, 'systemctl start fz3b-pl-loader.service')
        identity = json.loads(run(client, 'python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status'))
        assert identity['result']['status'] == 'READY_A0005', 'existing loader not ready'
        states = run(client, 'for p in /sys/class/remoteproc/remoteproc*; do test -e "$p/state" || continue; readlink -f "$p"; cat "$p/state" "$p/firmware"; done')
        if 'running' in states:
            for i in range(2):
                assert 'app-r5%d' % i in states and 'fz3b-app-r5%d.elf' % i in states, 'unknown R5 owner; do not replace'
                local = ROOT / ('artifacts/ps-application-20261009/r5/fz3b-app-r5%d.elf' % i)
                expected = hashlib.sha256(local.read_bytes()).hexdigest()
                observed = run(client, 'sha256sum /lib/firmware/fz3b-app-r5%d.elf' % i).split()[0]
                assert observed == expected, 'R5 firmware file identity mismatch'
            run(client, "cd /root/fz3b-vision-console-20261009-001; python3 -B -c 'from vision_app.r5_bridge import R5Bridge; r=R5Bridge(); r.close()'")
            running = True
    finally:
        client.close()
    if not running:
        deploy_r5.main()
    deploy_board.main()
    print('Manual start complete; autostart remains disabled.')


if __name__ == '__main__':
    main()
