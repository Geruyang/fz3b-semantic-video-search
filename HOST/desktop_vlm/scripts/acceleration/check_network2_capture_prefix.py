"""Check actual FZC1 mode4 ILA prefixes against the frozen 12-block packets.

Stream checks preserve the previously board-validated Stage23 checker rules.
This separately named checker leaves the historical checker unchanged.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'artifacts/board-debug-20261005/acceleration/host/network2-cascade-fixture-001'
FIXTURE_SHA = '39f120bf2cd959436cbc23919d4eafbe1fde3d0502445a369be1e1ce7143f0d7'
PARAMETER_SHA = '5d48cd42136199834ce2e59b00a2d441af7ca5d7cf7515a9c72706de0bad5b62'


def packet(stage, side, sample):
    if stage != 4 or side not in ('in', 'out') or sample not in (0, 1, 2):
        raise ValueError('FZC1 mode4 frozen sample required')
    raw = (FIXTURE / 'fixture-manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA:
        raise ValueError('Frozen fixture manifest changed')
    manifest = json.loads(raw)
    if (manifest['parameter_manifest_sha256'] != PARAMETER_SHA or
            hashlib.sha256((FIXTURE / 'parameter-manifest.json').read_bytes()).hexdigest() != PARAMETER_SHA):
        raise ValueError('Frozen parameter identity changed')
    entry = manifest['images'][sample]
    name = 'image-%02d' % sample
    if entry['image'] != name:
        raise ValueError('Frozen sample order changed')
    kind = 'input' if side == 'in' else 'output'
    data = (FIXTURE / (name + '.' + kind + '.bin')).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != entry[kind + '_bytes'] or digest != entry[kind + '_sha256']:
        raise ValueError('Frozen packet length/hash changed')
    return data, digest, FIXTURE_SHA


def inspect(csv_path, native_path, stage, side, sample, depth=1024, position=256):
    data, data_sha, pin = packet(stage, side, sample)
    raw, native = csv_path.read_bytes(), native_path.read_bytes()
    rows = list(csv.reader(raw.decode('utf-8-sig').splitlines()))
    header, radix, samples = rows[0], rows[1], rows[2:]
    if depth not in (1024, 2048, 4096, 8192) or not 0 < position < depth:
        raise ValueError('Unsupported acquisition setting')
    if len(samples) != depth or not native or len(set(header)) != len(header):
        raise ValueError('Missing native ILA, wrong depth, or duplicate columns')
    if len(radix) != len(header) or any(len(row) != len(header) for row in samples):
        raise ValueError('Malformed CSV width')
    for name in ('Sample in Buffer', 'Sample in Window'):
        column = header.index(name)
        if [int(row[column]) for row in samples] != list(range(depth)):
            raise ValueError('Discontinuous sample indices')

    def signal(name):
        column = header.index('dma_shell_i/' + name)
        if radix[column] != 'HEX':
            raise ValueError('Signal is not hexadecimal: ' + name)
        return [int(row[column], 16) for row in samples]

    heartbeat = signal('reset_heartbeat[31:0]')
    if any(b != (a + 1) & 0xffffffff for a, b in zip(heartbeat, heartbeat[1:])):
        raise ValueError('Heartbeat discontinuity')
    if set(signal('reset_rst')) != {0} or set(signal('core_reset_sync_peripheral_aresetn[0:0]')) != {1}:
        raise ValueError('Reset during acquisition')
    if any(signal('datapath_protocol_error')) or any(v & 0x44 for v in signal('ctrl_debug_status[6:0]')):
        raise ValueError('Protocol/error/reset flag observed')
    if set(signal('ctrl_core_mode[31:0]')[position:]) != {stage}:
        raise ValueError('Wrong accelerator mode')
    prefix = 'probe_' + side + '_mon_'
    valid, ready = signal(prefix + 'tvalid'), signal(prefix + 'tready')
    words = signal(prefix + 'tdata[63:0]')
    keep, last = signal(prefix + 'tkeep[7:0]'), signal(prefix + 'tlast')
    if side == 'in':
        starts = [i for i, value in enumerate(signal('ctrl_core_start_pulse')) if value]
        if starts != [position] or any(valid[:position + 1]):
            raise ValueError('START acquisition does not contain the first input prefix')
    elif any(valid[:position]) or valid[position] != 1:
        raise ValueError('Output acquisition does not begin with the first TVALID')
    for i in range(depth - 1):
        if valid[i] and not ready[i]:
            if not valid[i + 1] or (words[i], keep[i], last[i]) != (words[i + 1], keep[i + 1], last[i + 1]):
                raise ValueError('AXIS payload changed under backpressure')
    transfers = [i for i in range(depth) if valid[i] and ready[i]]
    if not transfers:
        raise ValueError('No accepted beats in acquisition')
    offset = 0
    for i in transfers:
        if offset + 8 > len(data) or keep[i] != 0xff or bool(last[i]) != (offset + 8 == len(data)):
            raise ValueError('Packet length/TKEEP/TLAST mismatch')
        if words[i].to_bytes(8, 'little') != data[offset:offset + 8]:
            raise ValueError('Payload mismatch at byte %d' % offset)
        offset += 8
    return {
        'status': 'NETWORK2_CAPTURED_PREFIX_PASS', 'stage': stage, 'side': side,
        'sample': sample, 'samples': depth, 'trigger_position': position,
        'first_handshake_sample': transfers[0], 'last_handshake_sample': transfers[-1],
        'bytes_checked': offset, 'handshakes': len(transfers),
        'full_packet_captured': offset == len(data), 'packet_sha256': data_sha,
        'fixture_manifest_sha256': pin, 'csv_sha256': hashlib.sha256(raw).hexdigest(),
        'native_ila_sha256': hashlib.sha256(native).hexdigest(),
        'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'Observed prefix only. Full-frame completion, counters, correctness and native reopening require separate evidence.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('ila', type=Path)
    parser.add_argument('--stage', type=int, choices=(4,), default=4)
    parser.add_argument('--side', choices=('in', 'out'), required=True)
    parser.add_argument('--sample', type=int, choices=(0, 1, 2), default=0)
    parser.add_argument('--depth', type=int, default=1024)
    parser.add_argument('--position', type=int, default=256)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.csv, args.ila, args.stage, args.side, args.sample, args.depth, args.position)
    encoded = (json.dumps(report, indent=2) + '\n').encode()
    args.output.write_bytes(encoded)
    print(encoded.decode())


if __name__ == '__main__':
    main()
