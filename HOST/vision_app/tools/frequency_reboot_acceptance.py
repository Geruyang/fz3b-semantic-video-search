"""Actual policy write/readback, then restore boot default via controlled reboot.

Board-only temporary operation; no autostart or persistent network installation.
"""
import json
from pathlib import Path
import re
import shutil
import socket
import time
import serial
from vision_app.protocol import Decoder, JSON, encode_message
from vision_app.tools.board_link import ROOT, open_link, run


def status(sock, decoder, predicate, timeout=12):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for kind, payload in decoder.feed(sock.recv(65536)):
            if kind == JSON:
                value = json.loads(payload)
                if predicate(value):
                    return value
    raise TimeoutError('application reply deadline')


def main():
    raise RuntimeError('Historical sysfs-only frequency test is superseded; use cpu_api_acceptance and boot_acceptance for PM/raw verification.')
    config = json.loads((ROOT / 'vision_app/client-config.json').read_text(encoding='utf-8'))
    receipt = {'persistent_changes': False, 'pl_or_model_changed': False, 'ok': False}
    output = ROOT / 'artifacts/ps-application-20261009/frequency-reboot.json'
    try:
        with socket.create_connection((config['host'], 8765), timeout=12) as sock:
            sock.settimeout(12)
            decoder = Decoder()
            sock.sendall(encode_message(JSON, {'op': 'hello', 'token': config['token']}))
            before = status(sock, decoder, lambda x: x.get('type') == 'hello')
            assert before['inference']['state'] == 'STOPPED', before['inference']
            receipt['before'] = {'boot_id': before['boot_id'], 'cpu': before['cpu'], 'r5': before['r5']}
            assert before['cpu']['current_khz'] == 1066666, 'unexpected baseline; do not change clock'
            sock.sendall(encode_message(JSON, {'op': 'cpu_frequency', 'khz': 1199999, 'request_id': 'real-frequency-test'}))
            ack = status(sock, decoder, lambda x: x.get('request_id') == 'real-frequency-test')
            receipt['frequency_ack'] = ack
            assert ack['ok'] and abs(ack['result']['current_khz'] - 1199999) <= 2, ack
        client = open_link()
        try:
            run(client, 'systemctl stop fz3b-vision-console.service', timeout=370)
            receipt['getty_restored_before_reboot'] = run(client, 'systemctl is-active serial-getty@ttyPS0.service').strip() == 'active'
            run(client, 'nohup sh -c "sleep 1; reboot" >/dev/null 2>&1 </dev/null &')
        finally:
            client.close()
        handle = serial.Serial(port=None, baudrate=115200, timeout=.2, write_timeout=3)
        handle.dtr = handle.rts = False
        handle.port = 'COM6'
        handle.open()
        def until(token, seconds):
            received = b''
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                received += handle.read(8192)
                if token in received:
                    return
            raise TimeoutError('serial boot/login deadline')
        try:
            until(b'login:', 90)
            text = (ROOT / 'docs/hardware/FZ3B/TF-LINUX-INSTALL.md').read_text(encoding='utf-8')
            username, password = re.findall(r'默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`', text)[0]
            del text
            handle.write(username.encode() + b'\n')
            until(b'Password:', 10)
            handle.write(password.encode() + b'\n')
            del username, password
            until(b'@EdgeBoard:~# ', 15)
            handle.write(b"printf '\\nBOARD_SHELL_READY\\n'\n")
            until(b'\nBOARD_SHELL_READY', 10)
            handle.write(b"ip addr add 169.254.220.254/16 dev eth0; printf '\\nBOARD_LINK_RESTORED\\n'\n")
            until(b'\nBOARD_LINK_RESTORED', 10)
        finally:
            handle.close()
        end = time.monotonic() + 30
        while True:
            try:
                client = open_link()
                break
            except OSError:
                if time.monotonic() > end:
                    raise
                time.sleep(1)
        try:
            receipt['restored_cpu_khz'] = int(run(client, 'cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq'))
            receipt['new_boot_id'] = run(client, 'cat /proc/sys/kernel/random/boot_id').strip()
            assert receipt['restored_cpu_khz'] == receipt['before']['cpu']['current_khz']
            assert receipt['new_boot_id'] != receipt['before']['boot_id']
            run(client, 'systemctl start fz3b-pl-loader.service')
            receipt['loader'] = json.loads(run(client, 'python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status'))
        finally:
            client.close()
        local = ROOT / 'artifacts/ps-application-20261009/r5/deployment-result.json'
        shutil.copyfile(local, local.with_name('deployment-before-reboot.json'))
        from vision_app.tools import deploy_r5, deploy_board
        deploy_r5.main()
        deploy_board.main()
        with socket.create_connection((config['host'], 8765), timeout=12) as sock:
            sock.settimeout(12)
            sock.sendall(encode_message(JSON, {'op': 'hello', 'token': config['token']}))
            after = status(sock, Decoder(), lambda x: x.get('type') == 'hello')
            receipt['after'] = {'boot_id': after['boot_id'], 'cpu': after['cpu'], 'r5': after['r5'], 'camera': after['camera']}
            assert after['r5']['offload_verified']
        receipt['ok'] = True
        print(json.dumps(receipt, indent=2))
    finally:
        output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
