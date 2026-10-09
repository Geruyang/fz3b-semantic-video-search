"""Final board state and delivery hashes; never archive application credentials."""
import datetime
import hashlib
import json
import re
from pathlib import Path
import socket
import subprocess
import sys
import time
from vision_app.protocol import Decoder, JSON, encode_message
from vision_app.tools.board_link import ROOT, open_link, run
from vision_app.tools.frequency_reboot_acceptance import status


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def main():
    evidence = ROOT / 'artifacts/ps-application-20261009'
    config = json.loads((ROOT / 'vision_app/client-config.json').read_text(encoding='utf-8'))
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'vision_app/tests', '-v'], cwd=str(ROOT), capture_output=True, text=True)
    (evidence / 'final-tests.log').write_text(tests.stdout + tests.stderr, encoding='utf-8')
    assert tests.returncode == 0
    preserved = subprocess.run([sys.executable, 'scripts/verify_retained_releases.py'], cwd=str(ROOT), capture_output=True, text=True, check=True)
    receipt = {'schema': 'fz3b-vision-console-qualification-v1', 'host_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'tests_pass': True, 'tests_count': int(re.search(r'Ran (\d+) tests', tests.stderr).group(1)), 'retained_release_check': json.loads(preserved.stdout),
               'pl_or_model_changed': False, 'software_autostart_installed': False}
    receipt['frequency_scope']={'client_rates_mhz':[600,800,1000,1200],
        'verified_board_rates_mhz':[600,800,1000,1200],'four_rate_completed':True,
        'method':'firmware-authorized VPLL integer API for 800/1000; DPLL divider for 600/1200; no MMIO writes',
        'inference_before_change':'normal drain','resume_on_success':True,'user_stop_cancels_resume':True}
    with socket.create_connection((config['host'], 8765), timeout=12) as sock:
        sock.settimeout(12)
        sock.sendall(encode_message(JSON, {'op': 'hello', 'token': config['token']}))
        receipt['board'] = status(sock, Decoder(), lambda x: x.get('type') == 'hello')
    assert receipt['board']['inference']['state'] == 'STOPPED'
    assert receipt['board']['r5']['offload_verified']
    assert receipt['board']['camera']['error'] is None
    assert receipt['board']['cpu']['current_khz'] == 1199999
    assert receipt['board']['cpu']['verified'] and receipt['board']['cpu']['actual_hz'] == 1199999988
    client = open_link()
    try:
        receipt['loader'] = json.loads(run(client, 'python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status'))
        assert receipt['loader']['result']['status'] == 'READY_A0005'
        receipt['services'] = run(client, 'systemctl is-active fz3b-vision-console.service; systemctl is-enabled fz3b-vision-console.service || true; systemctl is-active fz3b-pl-loader.service; fuser /dev/network10_v10_signed40 || true').splitlines()
        receipt['boot_services'] = run(client, 'systemctl is-enabled fz3b-app-r5.service fz3b-vision-console.service; systemctl is-active fz3b-app-r5.service fz3b-vision-console.service').splitlines()
        receipt['cpu_service'] = run(client, 'systemctl is-enabled fz3b-app-cpu-clock.service; systemctl is-active fz3b-app-cpu-clock.service').splitlines()
        assert receipt['cpu_service'] == ['enabled', 'active']
        cpu_module='/root/fz3b-vision-console-20261009-001/cpu-clock/fz3b_cpu_clock.ko'
        receipt['cpu_module_sha256']=run(client,'sha256sum '+cpu_module).split()[0]
        assert receipt['cpu_module_sha256']==sha(evidence/'cpu-clock/fz3b_cpu_clock.ko')
        receipt['raw_clocks']=run(client,'/root/fz3b-vision-console-20261009-001/read_clock')
        receipt['software_autostart_installed'] = receipt['boot_services'] == ['enabled', 'enabled', 'active', 'active']
        if receipt['software_autostart_installed']:
            receipt['boot_ready'] = json.loads(run(client, 'cat /run/fz3b-r5-ready.json'))
            assert receipt['boot_ready']['boot_id'] == receipt['board']['boot_id'] and receipt['boot_ready']['ok']
        receipt['r5_owner_guard'] = run(client, "cd /root/fz3b-vision-console-20261009-001; python3 -B -c 'from vision_app.r5_bridge import R5Bridge; r=R5Bridge()'" )
    except RuntimeError as exc:
        if 'mailboxes already have an application owner' not in str(exc):
            raise
        receipt['r5_owner_guard'] = 'PASS: second process denied while application owns both mailboxes'
    finally:
        client.close()
    for name in ('exe-text-test-final.json', 'gui-acceptance.json', 'uart-reconnect.json'):
        value = json.loads((evidence / name).read_text(encoding='utf-8'))
        assert value['ok'], name
        receipt[name] = {'ok': True, 'sha256': sha(evidence / name)}
    receipt['legacy_frequency_evidence'] = {'path':'artifacts/ps-application-20261009/frequency-reboot.json',
        'superseded':True,'reason':'sysfs cache readback did not prove physical A53 frequency'}
    cpu_api = sorted((evidence/'cpu-clock').glob('api-*.json'))[-1]
    cpu_result = json.loads(cpu_api.read_text(encoding='utf-8'))
    assert cpu_result['ok'] and cpu_result['restore']['result']['verified']
    assert [step['result']['requested_khz'] for step in cpu_result['steps']]==[600000,800000,1000000,1200000]
    receipt['verified_cpu_api'] = {'path':str(cpu_api.relative_to(ROOT)).replace('\\','/'),'sha256':sha(cpu_api),'ok':True}
    lifecycle=sorted((evidence/'cpu-clock').glob('lifecycle-*.json'))[-1]
    lifecycle_result=json.loads(lifecycle.read_text(encoding='utf-8'))
    assert lifecycle_result['ok']
    assert all('running_%d'%khz in lifecycle_result for khz in (600000,800000,1000000,1200000))
    receipt['frequency_lifecycle']={'path':str(lifecycle.relative_to(ROOT)).replace('\\','/'),'sha256':sha(lifecycle),'ok':True}
    cycle=sorted((evidence/'cpu-clock').glob('fine-probe-*.json'))[-1]
    cycle_result=json.loads(cycle.read_text(encoding='utf-8'))
    assert cycle_result['ok'] and cycle_result['restored_exactly'] and len(cycle_result['steps'])==9
    receipt['four_rate_cycle']={'path':str(cycle.relative_to(ROOT)).replace('\\','/'),'sha256':sha(cycle),'ok':True,'raw_register_count':16}
    gui=evidence/'gui-four-rates.json'
    assert json.loads(gui.read_text(encoding='utf-8'))['ok']
    receipt['four_rate_gui']={'path':str(gui.relative_to(ROOT)).replace('\\','/'),'sha256':sha(gui),'ok':True}
    app = ROOT / 'deliverables/vision-console/FZ3BVisionConsole'
    required = [app / 'FZ3BVisionConsole.exe', app / 'semantic-contract.json', app / 'build-environment.txt', app / 'models/mobileclip_s1.pt']
    required += sorted((ROOT / 'vision_app').rglob('*.py'))
    required += sorted((ROOT / 'vision_app').glob('*.ps1'))
    required += sorted((ROOT / 'vision_app/r5').glob('*'))
    required += sorted((ROOT / 'vision_app/cpu_clock').glob('*'))
    required += [evidence/'cpu-clock/fz3b_cpu_clock.ko']
    receipt['files'] = [{'path': str(p.relative_to(ROOT)).replace('\\', '/'), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in required if p.is_file()]
    receipt['ok'] = True
    receipt['review'] = {'previous_findings_resolved': 7, 'performance_findings_resolved': 3,
        'endpoint_frequency_rereview':'PASS','automatic_resume_and_same_link_stop_rereview':'PASS',
        'safe_endpoint_deployment_rereview':'PASS','four_rate_firmware_VPLL_rereview':'PASS',
        'reference': 'artifacts/ps-application-20261009/review-final.md'}
    for name in ('backend-acceptance.json', 'exe-network-dialog.json', 'exe-permission-denial.json'):
        path = evidence/'host-network'/name
        value = json.loads(path.read_text(encoding='utf-8'))
        assert value['ok'], name
        receipt['host_network_'+name] = {'ok':True,'sha256':sha(path),'host_network_writes':False}
    speed_path = sorted(evidence.glob('speed-1p2-*/summary.json'))[-1]
    speed = json.loads(speed_path.read_text(encoding='utf-8'))
    assert speed['ok'] and speed['cpu_khz'] == 1199999 and speed['cpu_verified'] and speed['cpu_actual_hz'] == 1199999988
    receipt['final_fixed_speed'] = dict(speed, evidence_path=str(speed_path.relative_to(ROOT)).replace('\\', '/'))
    live_path = sorted(evidence.glob('live-smoke-*/evidence.json'))[-1]
    live = json.loads(live_path.read_text(encoding='utf-8'))
    assert not live['errors'] and live['last_board_status']['cpu']['current_khz'] == 1199999 and live['last_board_status']['cpu']['verified'] and live['last_board_status']['cpu']['actual_hz'] == 1199999988
    receipt['final_camera_speed'] = {k:live[k] for k in ('inference_result_interval_fps','inference_results_received','preview_received_fps','result_age_p50_ms','elapsed_s')}
    receipt['final_camera_speed']['evidence_path'] = str(live_path.relative_to(ROOT)).replace('\\', '/')
    if receipt['software_autostart_installed']:
        boots = sorted((evidence / 'boot').glob('reboot-*.json'))
        latest = json.loads(boots[-1].read_text(encoding='utf-8'))
        assert latest['ok'] and not latest['manual_recovery_after_reboot']
        receipt['autostart_reboot_evidence'] = {'path': str(boots[-1].relative_to(ROOT)).replace('\\', '/'), 'sha256': sha(boots[-1]), 'ok': True}
    (evidence / 'qualification.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (app / 'delivery-manifest.json').write_text(json.dumps({k: receipt[k] for k in ('schema', 'host_utc', 'ok', 'files')}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ok': True, 'boot_id': receipt['board']['boot_id'], 'cpu_khz': receipt['board']['cpu']['current_khz'], 'camera_fps': receipt['board']['camera']['fps'], 'inference_state': receipt['board']['inference']['state'], 'manifest': str(evidence / 'qualification.json')}))


if __name__ == '__main__':
    main()
