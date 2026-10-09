"""User-approved persistent R5/application start; never touch boot images."""
import datetime
import hashlib
import json
import argparse
from vision_app.boot_units import application_unit, r5_unit
from vision_app.tools.board_link import ROOT, open_link, run
from vision_app.tools.boot_transaction import backup_state, restore_state

REMOTE = '/root/fz3b-vision-console-20261009-001'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recover_failure(client, snapshot, record):
    try:
        record['failure_logs'] = run(client, 'journalctl -b -u fz3b-app-r5.service -u fz3b-vision-console.service --no-pager -n 60')
    except BaseException as log_error:
        record['failure_log_error'] = str(log_error)
    if snapshot is not None:
        try:
            record['rollback'] = restore_state(client, snapshot)
        except BaseException as rollback_error:
            record['rollback_error'] = str(rollback_error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fail-after-promote', action='store_true', help='development-only rollback acceptance injection')
    args = parser.parse_args()
    evidence = ROOT / 'artifacts/ps-application-20261009/boot'
    evidence.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    record = {'ok': False, 'host_utc': stamp, 'authorization': '2026-10-09 user explicitly requested: 开机自启启用',
              'pl_or_model_changed': False, 'boot_images_changed': False, 'host_network_changed': False}
    client = open_link()
    snapshot = None
    try:
        record['loader_before'] = json.loads(run(client, 'python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status'))
        if record['loader_before']['result']['status'] != 'READY_A0005':
            raise RuntimeError('A0005 not ready')
        backup = REMOTE + '/boot-backup-' + stamp
        snapshot = backup_state(client, backup)
        record['backup'] = backup
        record['previous_state'] = snapshot
        run(client, 'systemctl stop fz3b-vision-console.service', timeout=370)
        run(client, 'if fuser /dev/network10_v10_signed40; then exit 17; fi')
        record['getty_after_drain'] = run(client, 'sleep 1; systemctl is-active serial-getty@ttyPS0.service || true').strip()
        # Stop an already installed service through its normal lifecycle on update.
        run(client, 'if systemctl is-active --quiet fz3b-app-r5.service; then systemctl stop fz3b-app-r5.service; fi')
        sftp = client.open_sftp()
        for name in ('board_agent.py', 'r5_start.py', 'link_setup.py', 'boot_units.py', 'r5_bridge.py'):
            sftp.put(str(ROOT / 'vision_app' / name), REMOTE + '/vision_app/' + name)
        sftp.put(str(ROOT / 'vision_app/r5/tcm_io.c'), REMOTE + '/tcm_io.c')
        sftp.close()
        run(client, 'gcc -O2 -Wall -Wextra -Werror -shared -fPIC ' + REMOTE + '/tcm_io.c -o ' + REMOTE + '/vision_app/libr5_tcm_io.so')
        manifest = {'schema': 'fz3b-r5-tcm-boot-v1', 'kernel_prefix': '4.14.0-xilinx-v2018.3', 'files': []}
        local_r5 = ROOT / 'artifacts/ps-application-20261009/r5'
        for i in range(2):
            path = '/lib/firmware/fz3b-app-r5%d.elf' % i
            expected = sha(local_r5 / ('fz3b-app-r5%d.elf' % i))
            if run(client, 'sha256sum ' + path).split()[0] != expected:
                raise RuntimeError('Installed R5 firmware differs; refuse to silently replace')
            manifest['files'].append({'path': path, 'sha256': expected})
        overlay = REMOTE + '/tcm-split-overlay.dtbo'
        expected = sha(local_r5 / 'tcm-split-overlay.dtbo')
        if run(client, 'sha256sum ' + overlay).split()[0] != expected:
            raise RuntimeError('Installed TCM overlay differs')
        manifest['files'].append({'path': overlay, 'sha256': expected})
        native_path = REMOTE + '/vision_app/libr5_tcm_io.so'
        manifest['files'].append({'path': native_path, 'sha256': run(client, 'sha256sum ' + native_path).split()[0]})
        sftp = client.open_sftp()
        with sftp.file(REMOTE + '/config.json') as handle:
            config = json.loads(handle.read().decode('utf-8'))
        config.update(autostart_installed=True, r5_require_ready=True, serial_restore_getty=True)
        files = [(REMOTE + '/config.json', json.dumps(config), 0o600),
                 (REMOTE + '/r5-boot-manifest.json', json.dumps(manifest, indent=2), 0o600),
                 ('/etc/systemd/system/fz3b-app-r5.service', r5_unit(REMOTE), 0o644),
                 ('/etc/systemd/system/fz3b-vision-console.service', application_unit(REMOTE, boot=True, cpu_clock=bool(config.get('cpu_control_socket'))), 0o644)]
        for path, content, mode in files:
            with sftp.file(path, 'w') as handle:
                handle.write(content)
            sftp.chmod(path, mode)
        sftp.close()
        record['manifest'] = manifest
        if args.fail_after_promote:
            raise RuntimeError('Intentional rollback acceptance injection after file promotion')
        record['unit_validation'] = run(client, 'systemd-analyze verify /etc/systemd/system/fz3b-app-r5.service /etc/systemd/system/fz3b-vision-console.service')
        run(client, 'set -e; systemctl daemon-reload; systemctl enable fz3b-app-r5.service fz3b-vision-console.service; systemctl start fz3b-app-r5.service; systemctl start fz3b-vision-console.service')
        record['services'] = run(client, 'systemctl is-enabled fz3b-app-r5.service fz3b-vision-console.service; systemctl is-active fz3b-app-r5.service fz3b-vision-console.service').splitlines()
        record['qualification'] = json.loads(run(client, 'cat /run/fz3b-r5-ready.json'))
        record['logs'] = run(client, 'journalctl -b -u fz3b-app-r5.service -u fz3b-vision-console.service --no-pager -n 40')
        if record['services'] != ['enabled', 'enabled', 'active', 'active']:
            raise RuntimeError('Autostart services not enabled and active')
        record['ok'] = True
        print(json.dumps({k: record[k] for k in ('ok', 'services', 'qualification', 'backup')}, indent=2))
    except BaseException as exc:
        record['error'] = str(exc)
        recover_failure(client, snapshot, record)
        raise
    finally:
        client.close()
        (evidence / ('install-' + stamp + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
