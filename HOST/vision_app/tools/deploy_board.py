"""Deploy only the application; frozen A0005 payloads are referenced in place."""
import json
import os
from pathlib import Path
import secrets
import shlex
import sys
from vision_app.tools.board_link import ROOT, open_link, run
from vision_app.boot_units import application_unit

REMOTE = '/root/fz3b-vision-console-20261009-001'
HERE = ROOT / 'vision_app'


def main():
    token_path = HERE / 'connection-token.txt'
    if not token_path.exists():
        token_path.write_text(secrets.token_hex(32), encoding='ascii')
    token = token_path.read_text().strip()
    config = {'contract': REMOTE + '/vision_app/semantic-contract.json', 'token_file': REMOTE + '/token',
              'camera_helper': REMOTE + '/mjpeg_source', 'camera_device': '/dev/v4l/by-id/usb-UGREEN_Camera_2K_UGREEN_Camera_2K_SN0001-video-index0',
              'width': 1280, 'height': 720, 'fps': 30, 'control_port': 8765, 'video_port': 8766, 'serial_device': '/dev/ttyPS0', 'r5_enabled': True, 'default_cpu_khz': 1199999}
    client = open_link()
    try:
        existing = client.open_sftp()
        try:
            with existing.file(REMOTE + '/config.json') as handle:
                prior = json.loads(handle.read().decode('utf-8'))
            for key in ('autostart_installed', 'serial_restore_getty', 'r5_require_ready', 'cpu_control_socket', 'preprocess_async'):
                if key in prior:
                    config[key] = prior[key]
        except IOError:
            pass
        finally:
            existing.close()
        state = run(client, 'systemctl is-active fz3b-pl-loader.service; cat /sys/class/fpga_manager/fpga0/state; fuser /dev/network10_v10_signed40 || true')
        if not state.startswith('active\noperating\n'):
            raise RuntimeError('A0005 loader/manager not ready')
        run(client, 'systemctl stop fz3b-vision-console.service 2>/dev/null || true', timeout=370)
        run(client, 'if fuser /dev/network10_v10_signed40; then exit 17; fi')
        run(client, 'mkdir -p ' + shlex.quote(REMOTE + '/vision_app'))
        sftp = client.open_sftp()
        uploaded = []
        for source in HERE.glob('*.py'):
            if source.name in ('client.py', 'launch.py', 'text_encoder.py', 'transports.py', 'host_network.py', 'network_dialog.py'):
                continue
            sftp.put(str(source), REMOTE + '/vision_app/' + source.name)
            uploaded.append(source.name)
        sftp.put(str(HERE / 'semantic-contract.json'), REMOTE + '/vision_app/semantic-contract.json')
        sftp.put(str(HERE / 'mjpeg_source.c'), REMOTE + '/mjpeg_source.c')
        for name, content in [('token', token), ('config.json', json.dumps(config)), ('run.sh', '#!/bin/sh\nset -eu\ncd ' + REMOTE + '\nexport PYTHONDONTWRITEBYTECODE=1\nexport PYTHONUNBUFFERED=1\nexport LD_LIBRARY_PATH=/root/board-debug-runtime-20261004/runtime/onnxruntime-linux-aarch64-1.16.3/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\nexec python3 -B -m vision_app.board_agent --config ' + REMOTE + '/config.json\n')]:
            with sftp.file(REMOTE + '/' + name, 'w') as f:
                f.write(content)
            sftp.chmod(REMOTE + '/' + name, 0o700 if name == 'run.sh' else 0o600)
        unit = application_unit(REMOTE, boot=config.get('autostart_installed', False), cpu_clock=bool(config.get('cpu_control_socket')))
        with sftp.file('/etc/systemd/system/fz3b-vision-console.service', 'w') as f:
            f.write(unit)
        sftp.close()
        print(run(client, 'cd ' + REMOTE + '; gcc -O2 -Wall -Wextra mjpeg_source.c -o mjpeg_source; python3 -B -c "from vision_app.contract import load_contract; load_contract(\'vision_app/semantic-contract.json\')"; systemctl daemon-reload; systemctl start fz3b-vision-console.service; systemctl is-active fz3b-vision-console.service'))
        host = os.environ.get('FZ3B_CONNECT_IP', '169.254.220.254')
        (HERE / 'client-config.json').write_text(json.dumps({'host': host, 'token': token, 'model_root': str(ROOT / 'releases/current/model-source')}, indent=2) + '\n', encoding='utf-8')
        enabled = run(client, 'systemctl is-enabled fz3b-vision-console.service || true').strip() == 'enabled'
        record = {'remote': REMOTE, 'uploaded': uploaded, 'pl_or_model_changed': False, 'started': True, 'enabled': enabled, 'host': host}
        (ROOT / 'artifacts/ps-application-20261009/deployment.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    finally:
        client.close()


if __name__ == '__main__':
    main()
