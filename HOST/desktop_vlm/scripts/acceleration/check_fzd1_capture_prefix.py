"""Check actual captured DW AXIS prefixes, not an uncaptured complete frame."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

PACKETS = Path('artifacts/board-debug-20261004/acceleration/host/dma-validation-packets-001')
EXPECTED = {
    'in': ('case-00-input.bin', 'adfe4fcfb70bfc9c40932d27833d125e92fe267bc8c0623386f342a493fb6ca0'),
    'out': ('case-00-expected.i32', 'c56770c270bbcb8531b8cd933c0b7460116f9faa2135191ea6e51c37cb0b3a9b'),
}


def inspect(csv_path, ila_path):
    raw, native = csv_path.read_bytes(), ila_path.read_bytes()
    rows = list(csv.reader(raw.decode('utf-8-sig').splitlines()))
    header, radix, samples = rows[0], rows[1], rows[2:]
    if len(samples) != 8192 or not native:
        raise ValueError('Expected 8192 samples and paired native ILA')

    def signal(name):
        index = header.index('dma_shell_i/' + name)
        if radix[index] != 'HEX':
            raise ValueError('Unexpected radix: ' + name)
        return [int(row[index], 16) for row in samples]

    heartbeat = signal('reset_heartbeat[31:0]')
    if any(b != (a + 1) & 0xffffffff for a, b in zip(heartbeat, heartbeat[1:])):
        raise ValueError('Heartbeat is discontinuous')
    if set(signal('reset_rst')) != {0} or set(signal('core_reset_sync_peripheral_aresetn[0:0]')) != {1}:
        raise ValueError('Unexpected reset')
    starts = [i for i, value in enumerate(signal('ctrl_core_start_pulse')) if value]
    if len(starts) != 1:
        raise ValueError('Expected exactly one START')
    start = starts[0]
    if set(signal('ctrl_core_mode[31:0]')[start:]) != {1}:
        raise ValueError('Capture is not DW MODE1')
    if any(signal('datapath_protocol_error')) or any(v & 0x44 for v in signal('ctrl_debug_status[6:0]')):
        raise ValueError('Hardware protocol/reset/error indication')
    observations = {}
    for side, (name, sha) in EXPECTED.items():
        packet = (PACKETS / name).read_bytes()
        if hashlib.sha256(packet).hexdigest() != sha:
            raise ValueError('Frozen packet changed')
        prefix = 'probe_' + side + '_mon_'
        valid, ready = signal(prefix + 'tvalid'), signal(prefix + 'tready')
        data, keep, last = signal(prefix + 'tdata[63:0]'), signal(prefix + 'tkeep[7:0]'), signal(prefix + 'tlast')
        for i in range(len(samples) - 1):
            if valid[i] and not ready[i]:
                if not valid[i + 1] or (data[i], keep[i], last[i]) != (data[i + 1], keep[i + 1], last[i + 1]):
                    raise ValueError(side + ' AXIS changed while stalled')
        transfers = [i for i in range(len(samples)) if valid[i] and ready[i]]
        if not transfers or transfers[0] <= start:
            raise ValueError(side + ' missing or pre-START transfer')
        offset = 0
        for i in transfers:
            width = min(8, len(packet) - offset)
            if width <= 0 or keep[i] != (1 << width) - 1:
                raise ValueError(side + ' packet length/TKEEP mismatch')
            if bool(last[i]) != (offset + width == len(packet)):
                raise ValueError(side + ' TLAST mismatch')
            if data[i].to_bytes(8, 'little')[:width] != packet[offset:offset + width]:
                raise ValueError(side + ' payload differs at byte ' + str(offset))
            offset += width
        observations[side] = {'first_sample': transfers[0], 'last_sample': transfers[-1],
                              'handshakes': len(transfers), 'bytes_checked': offset,
                              'full_packet_captured': offset == len(packet), 'packet_sha256': sha}
    return {'status': 'CAPTURED_DW_PREFIX_BYTES_PASS', 'start_sample': start,
            'samples': len(samples), 'observations': observations,
            'csv_sha256': hashlib.sha256(raw).hexdigest(),
            'native_ila_sha256': hashlib.sha256(native).hexdigest(),
            'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Only observed handshakes checked. Full-frame correctness and completion require separate board receipts; native reopening is separate.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv', type=Path)
    parser.add_argument('ila', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.csv, args.ila)
    encoded = (json.dumps(report, indent=2) + '\n').encode('utf-8')
    args.output.write_bytes(encoded)
    print(encoded.decode('utf-8'))


if __name__ == '__main__':
    main()
