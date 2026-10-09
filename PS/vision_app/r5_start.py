"""TCM-only R5 startup qualification, with no PL/DDR/boot-image changes."""
import argparse
import ctypes
import glob
import hashlib
import json
import os
import subprocess
import time
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READY = '/run/fz3b-r5-ready.json'


def read(path):
    with open(path) as handle:
        return handle.read().strip()


def sha(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def qualified_boot(path=READY, boot_id=None):
    try:
        with open(path) as handle:
            marker = json.load(handle)
        return isinstance(marker, dict) and marker.get('ok') is True and marker.get('boot_id') == (boot_id or read('/proc/sys/kernel/random/boot_id'))
    except (OSError, ValueError, TypeError):
        return False


def instances():
    return [{'path': path, 'realpath': os.path.realpath(path), 'state': read(path + '/state'), 'firmware': read(path + '/firmware')}
            for path in sorted(glob.glob('/sys/class/remoteproc/remoteproc*'))]


def startup_decision(nodes):
    if not nodes:
        return 'start'
    if len(nodes) != 2:
        raise ValueError('unexpected R5 remoteproc instances; refusing to replace owners')
    for core in range(2):
        owned = [node for node in nodes if 'app-r5%d' % core in node['realpath']]
        if len(owned) != 1:
            raise ValueError('unknown R5 owner')
        node = owned[0]
        if node['state'] == 'running' and node['firmware'] != 'fz3b-app-r5%d.elf' % core:
            raise ValueError('unknown running R5 firmware')
    states = [node['state'] for node in nodes]
    if states == ['running', 'running']:
        return 'verify'
    if states == ['offline', 'offline']:
        return 'start'
    raise ValueError('partial or transitional R5 state; refusing to reset cores')


def validate_manifest():
    with open(os.path.join(ROOT, 'r5-boot-manifest.json')) as handle:
        manifest = json.load(handle)
    if not read('/proc/sys/kernel/osrelease').startswith(manifest['kernel_prefix']):
        raise RuntimeError('R5 boot driver/kernel differs from verified platform')
    for item in manifest['files']:
        if sha(item['path']) != item['sha256']:
            raise RuntimeError('R5 boot file identity mismatch: ' + item['path'])
    return manifest


def write_state(path, value):
    with open(path, 'w') as handle:
        handle.write(value)


def remove_ready():
    try:
        os.unlink(READY)
    except FileNotFoundError:
        pass


def wait_loader(timeout=45):
    # Type=simple marks the existing loader active before its RPC is ready.
    # Wait for the actual identity response; do not change the frozen loader.
    end = time.monotonic() + timeout
    last = 'loader control socket not yet ready'
    while time.monotonic() < end:
        try:
            data = subprocess.check_output(['python3', '-B', '/root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py', 'status'], stderr=subprocess.PIPE, timeout=2)
            loader = json.loads(data.decode('utf-8'))
            if loader['result']['ready'] and loader['result']['status'] == 'READY_A0005':
                return loader
            last = str(loader.get('result', {}).get('status'))
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
            last = type(exc).__name__
        time.sleep(.2)
    raise RuntimeError('existing A0005 loader not ready before deadline: ' + last)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    import fcntl
    started = []
    with open('/run/fz3b-r5-start.lock', 'a') as startup_lock:
        fcntl.flock(startup_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # A live application/probe owner must never be interrupted by startup.
        with open('/run/fz3b-vision-r5-owner.lock', 'a') as owner:
            fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            remove_ready()
            if args.stop:
                for node in instances():
                    for core in range(2):
                        if 'app-r5%d' % core in node['realpath'] and node['firmware'] == 'fz3b-app-r5%d.elf' % core and node['state'] == 'running':
                            write_state(node['path'] + '/state', 'stop')
                print('Application R5 workers stopped')
                return
            manifest = validate_manifest()
            wait_loader()
            decision = startup_decision(instances())
            if decision == 'start':
                native = ctypes.CDLL(os.path.join(ROOT, 'vision_app/libr5_tcm_io.so'))
                if native.r5_halted() != 1:
                    raise RuntimeError('RPU hardware is not halted; refusing split setup')
                subprocess.check_call(['modprobe', 'zynqmp_r5_remoteproc'])
                if not os.path.ismount('/sys/kernel/config'):
                    subprocess.check_call(['mount', '-t', 'configfs', 'configfs', '/sys/kernel/config'])
                overlay = '/sys/kernel/config/device-tree/overlays/fz3b-app-r5'
                if not os.path.isdir(overlay):
                    os.mkdir(overlay)
                    with open(os.path.join(ROOT, 'tcm-split-overlay.dtbo'), 'rb') as source, open(overlay + '/dtbo', 'wb') as target:
                        target.write(source.read())
                if read(overlay + '/status') != 'applied':
                    raise RuntimeError('TCM overlay not applied')
                nodes = instances()
                if startup_decision(nodes) != 'start' or len(nodes) != 2:
                    raise RuntimeError('dual R5 instances not created')
                try:
                    for core in range(2):
                        node = next(n for n in nodes if 'app-r5%d' % core in n['realpath'])
                        write_state(node['path'] + '/firmware', 'fz3b-app-r5%d.elf' % core)
                        write_state(node['path'] + '/state', 'start')
                        started.append(node['path'])
                except BaseException:
                    for path in reversed(started):
                        write_state(path + '/state', 'stop')
                    raise
        # The startup lock remains held; release owner before using the bridge.
        bridge = None
        try:
            from .r5_bridge import R5Bridge
            bridge = R5Bridge()
            before = [bridge.heartbeat(i) for i in range(2)]
            assert bridge.request(0, 1, 123) == 123
            assert bridge.request(1, 1, 456) == 456
            data = bytes(range(256)) * 400
            assert bridge.crc(data) == zlib.crc32(data) & 0xffffffff
            assert bridge.request(0, 10, 599999) == 1
            time.sleep(.03)
            if any(bridge.heartbeat(i) == before[i] for i in range(2)):
                raise RuntimeError('R5 heartbeat stopped')
            result = {'ok': True, 'boot_id': read('/proc/sys/kernel/random/boot_id'),
                      'manifest_sha256': sha(os.path.join(ROOT, 'r5-boot-manifest.json')), 'r5': bridge.status(),
                      'boot_monotonic': time.monotonic(), 'decision': decision}
            temporary = READY + '.tmp'
            with open(temporary, 'w') as handle:
                json.dump(result, handle)
            os.chmod(temporary, 0o600)
            os.replace(temporary, READY)
            print(json.dumps(result))
        except BaseException:
            if bridge is not None:
                bridge.close()
                bridge = None
            for path in reversed(started):
                if read(path + '/state') == 'running':
                    write_state(path + '/state', 'stop')
            raise
        finally:
            if bridge is not None:
                bridge.close()


if __name__ == '__main__':
    main()
