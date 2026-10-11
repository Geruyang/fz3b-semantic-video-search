"""Developer SSH link, credentials in memory; pin original board identity."""
import os
from pathlib import Path
import re
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'releases/final/resources/ssh/python312-ssh-deps')]
import paramiko


def open_link():
    username, password = os.environ.get('FZ3B_SSH_USER'), os.environ.get('FZ3B_SSH_PASSWORD')
    if not username or not password:
        source = (ROOT / 'docs/hardware/FZ3B/TF-LINUX-INSTALL.md').read_text(encoding='utf-8')
        username, password = re.findall(r'默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`', source)[0]
        del source
    client = paramiko.SSHClient()
    client.load_host_keys(str(ROOT / 'releases/final/resources/ssh/board-known_hosts'))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    sock = socket.socket()
    sock.settimeout(10)
    sock.bind((os.environ.get('FZ3B_SSH_SOURCE', '169.254.220.34'), 0))
    sock.connect((os.environ.get('FZ3B_CONNECT_IP', '169.254.220.254'), 22))
    client.connect(hostname='192.168.1.254', username=username, password=password, sock=sock, allow_agent=False, look_for_keys=False, timeout=10, banner_timeout=10, auth_timeout=10)
    return client


def run(client, command, timeout=60):
    _, out, err = client.exec_command(command, timeout=timeout)
    stdout, stderr = out.read().decode('utf-8', 'replace'), err.read().decode('utf-8', 'replace')
    code = out.channel.recv_exit_status()
    if code:
        raise RuntimeError('Board command failed (%d): %s' % (code, stderr))
    return stdout


if __name__ == '__main__':
    import json
    source = Path(sys.argv[1])
    commands = json.loads(source.read_text(encoding='utf-8'))
    client = open_link()
    results = {}
    try:
        for name, command in commands.items():
            results[name] = run(client, command)
            print(name)
            print(results[name])
    finally:
        client.close()
    source.with_name(source.stem + '-result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
