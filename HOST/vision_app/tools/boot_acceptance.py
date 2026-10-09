"""Reboot proof: no manual alias setup, R5 deployment or application start."""
import datetime
import argparse
import json
import socket
import time
from vision_app.protocol import Decoder, JSON, encode_message
from vision_app.tools.board_link import ROOT, open_link, run
from vision_app.tools.frequency_reboot_acceptance import status


def application_hello(config):
    with socket.create_connection((config['host'], 8765), timeout=12) as sock:
        sock.settimeout(12)
        sock.sendall(encode_message(JSON, {'op': 'hello', 'token': config['token']}))
        return status(sock, Decoder(), lambda x: x.get('type') == 'hello')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recover-startup', action='store_true', help='one controlled retry after a recorded startup failure; require no PL owner')
    args = parser.parse_args()
    config = json.loads((ROOT / 'vision_app/client-config.json').read_text(encoding='utf-8'))
    evidence = ROOT / 'artifacts/ps-application-20261009/boot'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report = {'ok': False, 'host_utc': stamp, 'manual_recovery_after_reboot': False, 'pl_or_model_changed': False}
    client = open_link()
    try:
        report['previous_boot_id'] = run(client, 'cat /proc/sys/kernel/random/boot_id').strip()
        if args.recover_startup:
            run(client, 'if fuser /dev/network10_v10_signed40; then exit 17; fi')
            report['prior_startup_repair'] = True
        else:
            hello = application_hello(config)
            if hello['inference']['state'] != 'STOPPED':
                raise RuntimeError('stop inference before the reboot acceptance')
        run(client, 'systemctl stop fz3b-vision-console.service', timeout=370)
        report['getty_after_stop'] = run(client, 'sleep 1; systemctl is-active serial-getty@ttyPS0.service').strip()
        if not args.recover_startup:
            run(client, 'systemctl start fz3b-vision-console.service')
            report['getty_after_start'] = run(client, 'sleep 1; systemctl is-active serial-getty@ttyPS0.service || true').strip()
            if report['getty_after_stop'] != 'active' or report['getty_after_start'] != 'inactive':
                raise RuntimeError('serial console ownership does not follow application lifecycle')
        else:
            report['getty_after_start'] = 'startup was failed; checked after next boot'
        run(client, 'nohup sh -c "sleep 1; reboot" >/dev/null 2>&1 </dev/null &')
    finally:
        client.close()
    started = time.monotonic()
    end = started + 150
    failures = []
    try:
        while time.monotonic() < end:
            time.sleep(1)
            candidate = None
            try:
                candidate = open_link()
                boot_id = run(candidate, 'cat /proc/sys/kernel/random/boot_id').strip()
                if boot_id != report['previous_boot_id']:
                    client = candidate
                    break
            except OSError as exc:
                failures.append(type(exc).__name__)
            if candidate:
                candidate.close()
        else:
            raise TimeoutError('new boot never became reachable on the persistent alias')
        try:
            report['new_boot_id'] = boot_id
            report['ssh_reachable_after_s'] = time.monotonic() - started
            report['services'] = run(client, 'systemctl is-enabled fz3b-pl-loader.service fz3b-app-r5.service fz3b-app-cpu-clock.service fz3b-vision-console.service; systemctl is-active fz3b-pl-loader.service fz3b-app-r5.service fz3b-app-cpu-clock.service fz3b-vision-console.service').splitlines()
            report['ready'] = json.loads(run(client, 'cat /run/fz3b-r5-ready.json'))
            report['loader'] = json.loads(run(client, 'python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status'))
            report['network'] = run(client, 'ip -brief addr show dev eth0')
            report['journal'] = run(client, 'journalctl -b -u fz3b-app-r5.service -u fz3b-vision-console.service --no-pager')
            report['remoteproc'] = run(client, 'for p in /sys/class/remoteproc/remoteproc*; do readlink -f "$p"; cat "$p/state" "$p/firmware"; done')
            report['raw_clocks'] = run(client, '/root/fz3b-vision-console-20261009-001/read_clock')
            report['clock_control'] = json.loads(run(client, 'cd /root/fz3b-vision-console-20261009-001; python3 -B -m vision_app.cpu_clock_service --status'))
            if report['services'] != ['enabled'] * 4 + ['active'] * 4:
                raise RuntimeError('startup services not all enabled and active')
            if report['ready']['boot_id'] != boot_id or not report['ready']['ok'] or report['ready']['decision'] != 'start':
                raise RuntimeError('R5 was not started and qualified in this boot')
            if report['loader']['result']['status'] != 'READY_A0005':
                raise RuntimeError('A0005 identity not ready')
        finally:
            client.close()
        time.sleep(2)
        hello = application_hello(config)
        report['application'] = hello
        if hello['boot_id'] != boot_id or not hello['r5']['offload_verified'] or hello['camera']['frames'] < 1 or hello['camera']['error']:
            raise RuntimeError('application did not acquire both R5s and a live camera')
        if hello['cpu']['current_khz'] != 1199999 or not hello['cpu']['verified'] or hello['cpu']['actual_hz'] != 1199999988:
            raise RuntimeError('unexpected CPU default after reboot')
        report['ok'] = True
        print(json.dumps({k: report[k] for k in ('ok', 'previous_boot_id', 'new_boot_id', 'ssh_reachable_after_s', 'services', 'getty_after_stop', 'getty_after_start')}, indent=2))
    finally:
        report['transient_connection_failures'] = failures
        (evidence / ('reboot-' + stamp + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
