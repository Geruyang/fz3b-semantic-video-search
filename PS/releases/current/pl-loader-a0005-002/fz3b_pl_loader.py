#!/usr/bin/env python3
"""FZ3B root-only FPGA Manager service for the A0005/factory pair.

The daemon owns the IOPLL lease FD for the full lifetime of A0005.  It uses
the Linux FPGA Manager for full-PL programming and writes only the dedicated
PL1 clock-control word after checking every protected clock register.
"""
from __future__ import print_function

import argparse
import errno
try:
    import fcntl
except ImportError:  # Host contract tests run on Windows; board execution is Linux-only.
    fcntl = None
import hashlib
import json
import mmap
import os
import pathlib
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time


IOC_BEGIN = 0x00004D01
IOC_FINALIZE = 0x00004D02
IOC_STATUS = 0x80404D03
LEASE_STATUS = struct.Struct('<IIIIIIIIIIiIQII')
LEASE_FIELDS = ('version', 'flags', 'pl0_ref_ctrl', 'pl1_ref_ctrl',
                'pl2_ref_ctrl', 'pl3_ref_ctrl', 'iopll_ctrl', 'pll_status',
                'rpll_ctrl', 'ddr_ctrl', 'last_error', 'begin_count',
                'iopll_rate_hz', 'reserved0', 'reserved1')

CRL_BASE = 0xFF5E0000
CRF_BASE = 0xFD1A0000
MAP_SIZE = 0x1000
REG = {
    'iopll_ctrl': ('crl', 0x20), 'rpll_ctrl': ('crl', 0x30),
    'pll_status': ('crl', 0x40), 'pl0_ref_ctrl': ('crl', 0xC0),
    'pl1_ref_ctrl': ('crl', 0xC4), 'pl2_ref_ctrl': ('crl', 0xC8),
    'pl3_ref_ctrl': ('crl', 0xCC), 'ddr_ctrl': ('crf', 0x80),
}
PROTECTED = {
    'iopll_ctrl': 0x00015A00, 'rpll_ctrl': 0x00013000,
    'pll_status': 0x0000001B, 'pl0_ref_ctrl': 0x01010802,
    'pl2_ref_ctrl': 0x00052000, 'pl3_ref_ctrl': 0x00052000,
    'ddr_ctrl': 0x01000200,
}
PL1_ENTRY = 0x00052000
PL1_TARGET = 0x01010F00
IOPLL_HZ = 1499999985
A0005_SYNC = bytes.fromhex('665599aa')
SYNC_OFFSET = 80


class LoaderError(RuntimeError):
    pass

class BusyError(LoaderError):
    pass


def _atomic_json(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk: break
            digest.update(chunk)
    return digest.hexdigest()


def _load_config(path):
    with open(path, 'r') as stream: config = json.load(stream)
    if config.get('schema') != 'fz3b-v10.5-ps-pl-loader-v1':
        raise LoaderError('unsupported loader configuration schema')
    return config


class LinuxBackend(object):
    def __init__(self, config, event):
        self.config = config
        self.event = event
        self.lease_fd = None
        self.lease_baseline = None

    def run(self, argv, check=True):
        self.event('command', argv=argv)
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate()
        if check and proc.returncode:
            raise LoaderError('%s failed rc=%d stderr=%s' %
                              (argv[0], proc.returncode,
                               err.decode('utf-8', 'replace')[-1000:]))
        return proc.returncode, out, err

    def verify_assets(self):
        for label, item in sorted(self.config['assets'].items()):
            path = item['path']; expected = item['sha256'].lower()
            if not os.path.isfile(path): raise LoaderError('%s is missing' % label)
            if 'bytes' in item and os.path.getsize(path) != item['bytes']:
                raise LoaderError('%s size mismatch' % label)
            actual = _sha256(path)
            if actual != expected:
                raise LoaderError('%s SHA mismatch' % label)
        a5 = self.config['assets']['a0005_firmware']['path']
        with open(a5, 'rb') as stream:
            stream.seek(SYNC_OFFSET); sync = stream.read(4)
        if sync != A0005_SYNC:
            raise LoaderError('A0005 firmware is not Linux/PCAP word order')
        native_a5 = self.config['assets']['a0005_native_bin']['path']
        self._verify_word_swap(native_a5, a5, 'A0005')
        native = self.config['assets']['factory_native_source']['path']
        pcap = self.config['assets']['factory_firmware']['path']
        with open(pcap, 'rb') as stream:
            stream.seek(SYNC_OFFSET); factory_sync = stream.read(4)
        if factory_sync != A0005_SYNC:
            raise LoaderError('factory firmware is not Linux/PCAP word order')
        self._verify_word_swap(native, pcap, 'factory')

    @staticmethod
    def _verify_word_swap(native, pcap, label):
        with open(native, 'rb') as source, open(pcap, 'rb') as converted:
            while True:
                left = source.read(1024 * 1024); right = converted.read(len(left))
                if not left:
                    if right: raise LoaderError('%s PCAP payload has trailing bytes' % label)
                    break
                if len(left) % 4 or len(right) != len(left):
                    raise LoaderError('%s PCAP payload extent mismatch' % label)
                expected = bytearray(len(left))
                for offset in range(0, len(left), 4):
                    expected[offset:offset+4] = left[offset:offset+4][::-1]
                if bytes(expected) != right:
                    raise LoaderError('%s PCAP payload is not an exact word swap' % label)

    def _module(self, name):
        return os.path.isdir('/sys/module/' + name)

    def _overlay(self):
        return self.config['paths']['overlay_dir']

    def wait_manager(self):
        deadline = time.monotonic() + self.config.get('manager_timeout_s', 30)
        required = ('manager_firmware', 'manager_flags', 'manager_state')
        while time.monotonic() < deadline:
            if all(os.path.exists(self.config['paths'][key]) for key in required):
                state = open(self.config['paths']['manager_state']).read().strip()
                if state == 'operating':
                    return
            time.sleep(0.1)
        raise LoaderError('FPGA manager is unavailable or not operating')

    def detect_target(self):
        a5_module = self._module(self.config['paths']['a0005_module'])
        a5_overlay = os.path.isdir(self._overlay())
        a5_device = os.path.exists(self.config['paths']['a0005_device'])
        factory = self._module(self.config['paths']['factory_module'])
        if a5_module and a5_overlay and a5_device and not factory:
            return 'a0005' if self.lease_fd is not None else 'external-a0005'
        if factory and not a5_module and not a5_overlay:
            return 'factory'
        return 'unknown'

    def runtime_status(self):
        result = {'detected_target': self.detect_target(),
                  'manager_state': (open(self.config['paths']['manager_state']).read().strip()
                                    if os.path.exists(self.config['paths']['manager_state']) else 'absent'),
                  'raw_clocks': self.raw_snapshot()}
        if self.lease_fd is not None:
            result['lease'] = self._lease_status()
        return result

    def ensure_no_owner(self):
        device = self.config['paths']['a0005_device']
        if os.path.exists(device):
            for pid in os.listdir('/proc'):
                if not pid.isdigit() or int(pid) == os.getpid(): continue
                fdroot = '/proc/%s/fd' % pid
                try: names = os.listdir(fdroot)
                except OSError: continue
                for name in names:
                    try: target = os.path.realpath(os.path.join(fdroot, name))
                    except OSError: continue
                    if target == device:
                        raise BusyError('inference device is owned by pid %s' % pid)
        blocked = ('benchmark_cnn_pipeline_v10', 'ort_partition_runner',
                   'run_cnn_pipeline_v10')
        for pid in os.listdir('/proc'):
            if not pid.isdigit() or int(pid) == os.getpid(): continue
            try:
                data = open('/proc/%s/cmdline' % pid, 'rb').read().replace(b'\0', b' ')
            except IOError: continue
            text = data.decode('utf-8', 'replace')
            if any(token in text for token in blocked):
                raise BusyError('inference process is active: pid %s' % pid)

    def remove_a0005_stack(self):
        name = self.config['paths']['a0005_module']
        if self._module(name):
            self.quiesce_a0005()
            self.run(['/sbin/rmmod', name])
        overlay = self._overlay()
        if os.path.isdir(overlay): os.rmdir(overlay)

    def remove_factory_stack(self):
        name = self.config['paths']['factory_module']
        if self._module(name): self.run(['/sbin/rmmod', name])

    def _lease_status(self):
        payload = bytearray(LEASE_STATUS.size)
        fcntl.ioctl(self.lease_fd, IOC_STATUS, payload, True)
        return dict(zip(LEASE_FIELDS, LEASE_STATUS.unpack(bytes(payload))))

    def acquire_lease(self):
        if self.lease_fd is not None: return self._lease_status()
        name = self.config['paths']['lease_module']
        if not self._module(name):
            self.run(['/sbin/insmod', self.config['assets']['lease_ko']['path']])
        self.lease_fd = os.open(self.config['paths']['lease_device'],
                                os.O_RDWR | os.O_CLOEXEC)
        opened = self._lease_status()
        if opened['version'] != 2 or opened['flags'] != 0x23:
            raise LoaderError('unexpected opened lease status')
        fcntl.ioctl(self.lease_fd, IOC_BEGIN)
        begun = self._lease_status()
        if begun['flags'] != 0x27 or begun['last_error'] or begun['iopll_rate_hz'] != IOPLL_HZ:
            raise LoaderError('lease BEGIN validation failed')
        for key, value in PROTECTED.items():
            if begun[key] != value: raise LoaderError('lease %s mismatch' % key)
        if begun['pl1_ref_ctrl'] != PL1_ENTRY:
            raise LoaderError('lease PL1 did not start from canonical entry')
        self.lease_baseline = begun
        return begun

    def _maps(self):
        fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC | os.O_CLOEXEC)
        try:
            crl = mmap.mmap(fd, MAP_SIZE, mmap.MAP_SHARED,
                            mmap.PROT_READ | mmap.PROT_WRITE, offset=CRL_BASE)
            crf = mmap.mmap(fd, MAP_SIZE, mmap.MAP_SHARED,
                            mmap.PROT_READ | mmap.PROT_WRITE, offset=CRF_BASE)
        except Exception:
            os.close(fd); raise
        return fd, crl, crf

    @staticmethod
    def _word(mm, offset): return struct.unpack('<I', mm[offset:offset+4])[0]

    def raw_snapshot(self):
        fd, crl, crf = self._maps()
        try:
            result = {}
            for key, (bank, offset) in REG.items():
                result[key] = self._word(crl if bank == 'crl' else crf, offset)
            return result
        finally:
            crl.close(); crf.close(); os.close(fd)

    def set_pl1(self, expected, target):
        if self.lease_fd is None: raise LoaderError('PL1 write requires lease')
        before = self.raw_snapshot()
        for key, value in PROTECTED.items():
            if before[key] != value: raise LoaderError('%s changed before PL1 write' % key)
        if before['pl1_ref_ctrl'] != expected:
            raise LoaderError('PL1 source value mismatch')
        fd, crl, crf = self._maps()
        try:
            crl[0xC4:0xC8] = struct.pack('<I', target)
            first = self._word(crl, 0xC4); time.sleep(0.002)
            second = self._word(crl, 0xC4)
        finally:
            crl.close(); crf.close(); os.close(fd)
        if first != target or second != target:
            raise LoaderError('PL1 readback mismatch after write')
        after = self.raw_snapshot()
        for key, value in PROTECTED.items():
            if after[key] != value: raise LoaderError('%s changed during PL1 write' % key)
        self.event('pl1_write', before=expected, after=target)
        return after

    def load_firmware(self, label):
        item = self.config['assets'][label]
        if _sha256(item['path']) != item['sha256']:
            raise LoaderError('%s changed before manager load' % label)
        firmware_name = item['firmware_name']
        if firmware_name.startswith('/') or '..' in firmware_name.split('/'):
            raise LoaderError('unsafe firmware name')
        flags = self.config['paths']['manager_flags']
        with open(flags, 'w') as stream: stream.write('0\n')
        if open(flags).read().strip() != '0': raise LoaderError('FPGA manager flags are not zero')
        with open(self.config['paths']['manager_firmware'], 'w') as stream:
            stream.write(firmware_name + '\n'); stream.flush()
        deadline = time.monotonic() + self.config.get('manager_timeout_s', 30)
        while time.monotonic() < deadline:
            state = open(self.config['paths']['manager_state']).read().strip()
            if state == 'operating':
                self.event('firmware_loaded', label=label, name=firmware_name)
                return
            if state.endswith('error'): raise LoaderError('FPGA manager state ' + state)
            time.sleep(0.05)
        raise LoaderError('FPGA manager did not reach operating before deadline')

    def apply_a0005_stack(self):
        overlay = self._overlay()
        if os.path.exists(overlay): raise LoaderError('A0005 overlay already exists')
        os.mkdir(overlay, 0o755)
        try:
            data = open(self.config['assets']['a0005_dtbo']['path'], 'rb').read()
            with open(os.path.join(overlay, 'dtbo'), 'wb') as stream: stream.write(data)
            status = open(os.path.join(overlay, 'status')).read().strip()
            if status != 'applied': raise LoaderError('A0005 overlay did not apply')
            self.run(['/sbin/insmod', self.config['assets']['a0005_driver_ko']['path'],
                      'allow_global_zynqmp_memcpy=0'])
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if os.path.exists(self.config['paths']['a0005_device']): return
                time.sleep(0.05)
            raise LoaderError('A0005 device was not created')
        except Exception:
            if self._module(self.config['paths']['a0005_module']):
                self.run(['/sbin/rmmod', self.config['paths']['a0005_module']], check=False)
            if os.path.isdir(overlay): os.rmdir(overlay)
            raise

    def strict_identity(self):
        helper = self.config['paths']['strict_identity_helper']
        rc, out, err = self.run([sys.executable, '-B', helper,
                                 '--config', self.config['_config_path']], check=False)
        if rc: raise LoaderError('strict identity failed: ' + err.decode('utf-8','replace')[-1000:])
        result = json.loads(out.decode('utf-8'))
        if not result.get('pass'): raise LoaderError('strict identity did not pass')
        # Opening the driver is terminal for this protocol; leave a fresh module.
        self.remove_a0005_stack()
        self.apply_a0005_stack()
        return result

    def quiesce_a0005(self):
        """Open and close the live transport so the driver reaches terminal QUIESCE.

        The A0005 kernel module deliberately refuses removal while a freshly
        probed endpoint can still accept work.  The strict helper exercises the
        real transport identity path and closes it terminally; unlike
        ``strict_identity`` this method does not reload a fresh module.
        """
        name = self.config['paths']['a0005_module']
        if not self._module(name):
            return {'pass': True, 'already_absent': True}
        with open('/sys/module/' + name + '/refcnt') as stream:
            reference_count = int(stream.read().strip())
        if reference_count == 0:
            return {'pass': True, 'already_quiesced': True}
        self.ensure_no_owner()
        helper = self.config['paths']['strict_identity_helper']
        rc, out, err = self.run([sys.executable, '-B', helper,
                                 '--config', self.config['_config_path']], check=False)
        if rc:
            raise LoaderError('A0005 terminal quiesce failed: ' +
                              err.decode('utf-8', 'replace')[-1000:])
        result = json.loads(out.decode('utf-8'))
        if not result.get('pass'):
            raise LoaderError('A0005 terminal quiesce identity did not pass')
        return result

    def finalize_lease(self):
        if self.lease_fd is None: return
        fcntl.ioctl(self.lease_fd, IOC_FINALIZE)
        status = self._lease_status()
        if status['flags'] != 0x23 or status['last_error']:
            raise LoaderError('lease FINALIZE validation failed')
        os.close(self.lease_fd); self.lease_fd = None
        name = self.config['paths']['lease_module']
        self.run(['/sbin/rmmod', name])

    def apply_factory_stack(self):
        self.run(['/sbin/insmod', self.config['assets']['factory_driver_ko']['path']])
        for path in self.config['paths']['factory_devices']:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not os.path.exists(path): time.sleep(0.05)
            if not os.path.exists(path): raise LoaderError('factory device missing: ' + path)

    def close(self):
        # Never implicitly close an active A0005 lease: the kernel guard will
        # quarantine it, but an orderly switch-factory is the only supported path.
        pass


class Controller(object):
    def __init__(self, config, backend, state_path, event):
        self.config = config; self.backend = backend
        self.state_path = state_path; self.event = event
        detected = backend.detect_target()
        ready = detected in ('a0005', 'factory')
        status = ('READY_A0005' if detected == 'a0005' else
                  'READY_FACTORY' if detected == 'factory' else 'NOT_READY')
        self.state = {'schema':'fz3b-v10.5-ps-pl-loader-state-v1',
                      'status':status,'target':detected,'ready':ready,
                      'failure':None,'updated_unix_ns':int(time.time()*1000000000)}
        self._save()

    def _save(self):
        self.state['updated_unix_ns'] = int(time.time()*1000000000); _atomic_json(self.state_path, self.state)

    def status(self):
        result = dict(self.state)
        try: result['observed'] = self.backend.runtime_status()
        except Exception as exc: result['observed_error'] = repr(exc)
        return result

    def switch_a0005(self):
        self.backend.verify_assets(); self.backend.wait_manager()
        if self.state['target'] == 'a0005' and self.state['ready']:
            try:
                self.backend.ensure_no_owner()
            except BusyError:
                return self.status()
            self.state.update(status='PREPARING_A0005', ready=False, failure=None); self._save()
            try:
                self.backend.remove_a0005_stack()
                self.backend.apply_a0005_stack()
                identity = self.backend.strict_identity()
                self.state.update(status='READY_A0005', target='a0005', ready=True,
                                  identity=identity, failure=None)
                self._save(); return self.status()
            except Exception as exc:
                self.state.update(status='FAILED_CLOSED', target='unknown', ready=False,
                                  failure=repr(exc)); self._save(); raise
        self.backend.ensure_no_owner()
        if self.state['target'] != 'factory':
            raise LoaderError('cannot switch A0005 from target %s' % self.state['target'])
        self.state.update(status='SWITCHING_A0005', ready=False, failure=None); self._save()
        try:
            self.backend.remove_a0005_stack(); self.backend.remove_factory_stack()
            lease = self.backend.acquire_lease()
            self.backend.set_pl1(PL1_ENTRY, PL1_TARGET)
            self.backend.load_firmware('a0005_firmware')
            self.backend.apply_a0005_stack()
            identity = self.backend.strict_identity()
            self.state.update(status='READY_A0005', target='a0005', ready=True,
                              identity=identity, lease=lease)
            self._save(); return self.status()
        except Exception as exc:
            # Never make an implicit factory rollback after programming begins.
            self.state.update(status='FAILED_CLOSED', target='unknown', ready=False,
                              failure=repr(exc)); self._save(); raise

    def switch_factory(self):
        self.backend.verify_assets(); self.backend.wait_manager()
        if self.state['target'] == 'factory' and self.state['ready']:
            return self.status()
        self.backend.ensure_no_owner()
        if self.state['target'] != 'a0005' or self.backend.lease_fd is None:
            raise LoaderError('factory switch requires daemon-owned A0005 lease')
        self.state.update(status='SWITCHING_FACTORY', ready=False, failure=None); self._save()
        try:
            self.backend.quiesce_a0005()
            self.backend.remove_a0005_stack()
            self.backend.load_firmware('factory_firmware')
            self.backend.set_pl1(PL1_TARGET, PL1_ENTRY)
            self.backend.finalize_lease(); self.backend.apply_factory_stack()
            self.state.update(status='READY_FACTORY', target='factory', ready=True,
                              identity=None, lease=None); self._save(); return self.status()
        except Exception as exc:
            self.state.update(status='FAILED_CLOSED', target='unknown', ready=False,
                              failure=repr(exc)); self._save(); raise


class Daemon(object):
    def __init__(self, args):
        self.lock_stream = open(args.lock, 'w')
        try: fcntl.flock(self.lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError: raise LoaderError('another FPGA loader owns the service lock')
        config = _load_config(args.config); config['_config_path'] = os.path.abspath(args.config)
        self.config = config; self.log_path = pathlib.Path(args.log)
        self.sock_path = args.socket; self.stop = False
        self.backend = LinuxBackend(config, self.event)
        self.controller = Controller(config, self.backend, args.state, self.event)

    def event(self, kind, **fields):
        record = {'kind':kind, 'unix_ns':int(time.time()*1000000000)}; record.update(fields)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(self.log_path), 'a') as stream:
            stream.write(json.dumps(record, sort_keys=True)+'\n'); stream.flush(); os.fsync(stream.fileno())

    def serve(self, auto_target):
        if auto_target == 'a0005':
            try: self.controller.switch_a0005()
            except Exception as exc: self.event('auto_switch_failed', error=repr(exc))
        if os.path.exists(self.sock_path): os.unlink(self.sock_path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.sock_path); os.chmod(self.sock_path, 0o600); server.listen(4); server.settimeout(1)
        try:
            while not self.stop:
                try: conn, _ = server.accept()
                except socket.timeout: continue
                try:
                    conn.settimeout(60); data=b''
                    while not data.endswith(b'\n'):
                        part=conn.recv(4096)
                        if not part: break
                        data += part
                        if len(data)>65536: raise LoaderError('control request is too large')
                    request = json.loads(data.decode('utf-8'))
                    command = request.get('command')
                    if command == 'status': result = self.controller.status()
                    elif command in ('switch-a0005', 'prepare-a0005'):
                        result = self.controller.switch_a0005()
                    elif command == 'switch-factory': result = self.controller.switch_factory()
                    else: raise LoaderError('unsupported command')
                    reply = {'ok':True,'result':result}
                except Exception as exc:
                    reply = {'ok':False,'error':repr(exc),'result':self.controller.status()}
                conn.sendall((json.dumps(reply, sort_keys=True)+'\n').encode()); conn.close()
        finally:
            server.close()


def client(socket_path, command):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); sock.settimeout(60); sock.connect(socket_path)
    sock.sendall((json.dumps({'command':command})+'\n').encode()); data=b''
    while not data.endswith(b'\n'):
        part=sock.recv(4096)
        if not part: break
        data += part
        if len(data)>65536: raise LoaderError('control reply is too large')
    sock.close(); result=json.loads(data.decode()); print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result.get('ok') else 1


def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='mode'); sub.required=True
    daemon=sub.add_parser('daemon'); daemon.add_argument('--config',required=True)
    daemon.add_argument('--state',default='/run/fz3b-pl-loader/state.json')
    daemon.add_argument('--log',default='/var/log/fz3b-pl-loader.jsonl')
    daemon.add_argument('--socket',default='/run/fz3b-pl-loader/control.sock')
    daemon.add_argument('--lock',default='/run/lock/fz3b-pl-loader.lock')
    daemon.add_argument('--auto-target',choices=('none','a0005'),default='a0005')
    for mode in ('status','switch-a0005','prepare-a0005','switch-factory'):
        child=sub.add_parser(mode); child.add_argument('--socket',default='/run/fz3b-pl-loader/control.sock')
    args=parser.parse_args()
    if args.mode=='daemon': return Daemon(args).serve(args.auto_target)
    return client(args.socket, args.mode)


if __name__=='__main__': sys.exit(main())
