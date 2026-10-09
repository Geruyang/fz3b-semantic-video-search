"""Finish a qualification after serial recovery; do not repeat clock/reboot."""
import json
import shutil
import socket
from vision_app.protocol import Decoder, JSON, encode_message
from vision_app.tools.board_link import ROOT, open_link, run
from vision_app.tools.frequency_reboot_acceptance import status
from vision_app.tools import deploy_r5, deploy_board


def main():
    raise RuntimeError('Historical manual recovery workflow is superseded; use boot_acceptance with current service owners.')
    output = ROOT / 'artifacts/ps-application-20261009/frequency-reboot.json'
    record = json.loads(output.read_text(encoding='utf-8'))
    shutil.copyfile(output, output.with_name('frequency-reboot-first-attempt.json'))
    record['recovery_note'] = 'Initial serial prompt detector matched # too early. Separate serial recovery succeeded; CPU/reboot not repeated. Use full prompt and a command marker in future.'
    client = open_link()
    try:
        record['restored_cpu_khz'] = int(run(client, 'cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq'))
        record['new_boot_id'] = run(client, 'cat /proc/sys/kernel/random/boot_id').strip()
        assert record['restored_cpu_khz'] == record['before']['cpu']['current_khz']
        assert record['new_boot_id'] != record['before']['boot_id']
        record['loader'] = json.loads(run(client, 'python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status'))
        record['application_autostart'] = run(client, 'systemctl is-enabled fz3b-vision-console.service || true').strip()
    finally:
        client.close()
    previous = ROOT / 'artifacts/ps-application-20261009/r5/deployment-result.json'
    shutil.copyfile(previous, previous.with_name('deployment-before-reboot.json'))
    deploy_r5.main()
    deploy_board.main()
    config = json.loads((ROOT / 'vision_app/client-config.json').read_text(encoding='utf-8'))
    with socket.create_connection((config['host'], 8765), timeout=12) as sock:
        sock.settimeout(12)
        sock.sendall(encode_message(JSON, {'op': 'hello', 'token': config['token']}))
        after = status(sock, Decoder(), lambda x: x.get('type') == 'hello')
        record['after'] = {'boot_id': after['boot_id'], 'cpu': after['cpu'], 'r5': after['r5'], 'camera': after['camera']}
        assert after['r5']['offload_verified']
    record['ok'] = True
    output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
