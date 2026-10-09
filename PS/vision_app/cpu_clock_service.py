"""Exclusive CPU-only clock lease; Python 3.6, root UNIX socket, no sysfs writes."""
import argparse
import json
import os
import signal
import socket
import struct
import subprocess
import threading

SOCKET = '/run/fz3b-cpu-clock/control.sock'
STATE = struct.Struct('<2Q6I')
from .frequency import validate_khz,TARGETS,DPLL_TARGETS


def validate_target(value):
    return validate_khz(value)


def receive(sock):
    data = bytearray()
    while b'\n' not in data:
        block = sock.recv(1024)
        if not block:
            raise RuntimeError('CPU control socket closed')
        data.extend(block)
        if len(data) > 4096:
            raise ValueError('CPU request exceeds bound')
    return json.loads(bytes(data).split(b'\n')[0].decode('utf-8'))


def request(op='status', khz=None, path=SOCKET):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        sock.connect(path)
        sock.sendall((json.dumps({'op': op, 'khz': khz}) + '\n').encode())
        answer = receive(sock)
    if not answer.get('ok'):
        raise RuntimeError(answer.get('error', 'CPU control failed'))
    return answer['state']


class Lease:
    def __init__(self):
        import fcntl
        self.fcntl = fcntl
        self.fd = os.open('/dev/fz3b_cpu_clock', os.O_RDWR)
        try:
            self.initial_raw = self.read_raw()
        except BaseException:
            os.close(self.fd)
            raise

    def read_raw(self):
        from pathlib import Path
        reader = str(Path(__file__).resolve().parents[1] / 'read_clock')
        return subprocess.check_output([reader], timeout=3).decode('ascii')

    def status(self):
        buffer = bytearray(STATE.size)
        self.fcntl.ioctl(self.fd, 0x80284300, buffer, True)
        hz, ccf, raw, parent, divider, error, held, requested = STATE.unpack(buffer)
        if error >= 0x80000000:
            error -= 0x100000000
        endpoint=requested in DPLL_TARGETS
        verified=bool(held and error==0 and requested in TARGETS and
                      abs(hz-requested*1000)<=300 and
                      parent==(2 if endpoint else 3) and
                      divider==(2 if requested==600000 else 1))
        return dict(actual_hz=hz, ccf_hz=ccf, acpu_ctrl=raw, parent=parent,
                    divider=divider, last_error=error, held=bool(held),
                    requested_khz=requested,supported_khz=list(TARGETS),
                    verified=verified)

    def set(self, khz):
        khz=validate_target(khz)
        try:
            self.fcntl.ioctl(self.fd, 0x40044301, struct.pack('<I', khz))
        except PermissionError:
            if khz in DPLL_TARGETS:
                raise
            # PMU denied before writing APLL; driver restored the baseline.
            # Recover only via its guarded SET, never bypass quarantine.
            self.fcntl.ioctl(self.fd,0x40044301,struct.pack('<I',1200000))
            state=self.status()
            if not state['verified'] or state['requested_khz']!=1200000:
                raise RuntimeError('CPU default restoration not verified')
            raise RuntimeError('PMU拒绝调频；已核验恢复1200MHz，推理保持停止')
        state = self.status()
        if not state['verified'] or abs(state['actual_hz'] // 1000 - khz) > 1:
            raise RuntimeError('CPU hardware frequency not verified')
        return state

    def diagnostic(self, clock_id=None):
        if clock_id is None:
            buffer = bytearray(48)
            self.fcntl.ioctl(self.fd, 0x80304302, buffer, True)
            keys = ('mode','mode_error','frac','frac_error','fbdiv','divider_error','enabled','state_error','ctrl','frac_raw','reference_hz','clock_id')
            return dict(zip(keys,struct.unpack('<12I',buffer)))
        if type(clock_id) is not int or not 0 <= clock_id <= 150:
            raise ValueError('diagnostic clock ID out of range')
        buffer = bytearray(struct.pack('<I16s14I',clock_id,b'',*([0]*14)))
        self.fcntl.ioctl(self.fd, 0xc04c4303, buffer, True)
        parts = struct.unpack('<I16s14I',buffer)
        return dict(id=parts[0],name=parts[1].split(b'\0')[0].decode('ascii','replace'),
                    enabled=parts[2],state_error=parts[3],parent=parts[4],parent_error=parts[5],
                    parents=list(parts[6:15]),parents_error=parts[15])

    def close(self):
        os.close(self.fd)
        self.fd = None
        # Linux fput ignores fops.release's return code. Independent MMIO
        # readback must prove restoration; otherwise the daemon exits failed.
        if self.read_raw() != self.initial_raw:
            raise RuntimeError('CPU clock restoration not verified; do not unload quarantined module')


def notify_ready():
    target = os.environ.get('NOTIFY_SOCKET')
    if target:
        target = '\0' + target[1:] if target.startswith('@') else target
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(target)
            sock.sendall(b'READY=1')


def serve(module):
    # Type=simple loader active is earlier than FPGA/R5 platform initialization.
    # Capture the immutable clock baseline only after both owners are ready.
    from .r5_start import wait_loader, qualified_boot
    wait_loader()
    if not qualified_boot():
        raise RuntimeError('R5 platform initialization is not qualified in this boot')
    # Installed module identity is pinned by the root-owned manifest.
    import hashlib
    with open(module + '.sha256') as handle:
        expected = handle.read().strip()
    with open(module, 'rb') as handle:
        if hashlib.sha256(handle.read()).hexdigest() != expected:
            raise RuntimeError('CPU clock module identity mismatch')
    if not os.path.exists('/dev/fz3b_cpu_clock'):
        subprocess.check_call(['/sbin/insmod', module])
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *unused: stop.set())
    directory = os.path.dirname(SOCKET)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    lease = Lease()  # exclusive driver open before unlinking a stale socket
    try:
        print(json.dumps(dict(initial_raw=lease.initial_raw)), flush=True)
        print(json.dumps(lease.set(1199999)), flush=True)
        if os.path.exists(SOCKET):
            os.unlink(SOCKET)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(SOCKET)
            os.chmod(SOCKET, 0o600)
            server.listen(4)
            server.settimeout(.5)
            notify_ready()
            while not stop.is_set():
                try:
                    connection, unused = server.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.settimeout(2)
                    try:
                        pid, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                        if uid != 0:
                            raise PermissionError('root CPU controller required')
                        command = receive(connection)
                        if command.get('op') == 'status':
                            state = lease.status()
                        elif command.get('op') == 'diagnostic':
                            state = lease.diagnostic(command.get('khz'))
                        elif command.get('op') == 'set':
                            state = lease.set(command.get('khz'))
                        else:
                            raise ValueError('unsupported CPU operation')
                        answer = dict(ok=True, state=state)
                    except Exception as exc:
                        answer = dict(ok=False, error=str(exc))
                    try:
                        connection.sendall((json.dumps(answer) + '\n').encode())
                    except OSError:
                        pass
    finally:
        lease.close()  # driver restores exactly the original CPU branch
        if os.path.exists(SOCKET):
            os.unlink(SOCKET)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--module')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        print(json.dumps(request()))
    else:
        serve(args.module)


if __name__ == '__main__':
    main()
