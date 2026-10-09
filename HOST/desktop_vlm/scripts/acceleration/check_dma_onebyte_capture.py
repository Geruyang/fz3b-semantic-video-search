"""Independently inspect the frozen first one-byte FZL1 transaction capture."""
import csv
import hashlib
import json
from pathlib import Path


BASE = Path('artifacts/board-debug-20261004/acceleration/jtag/dma-loopback-board-002/transaction-001')


def main():
    raw = (BASE / 'dma-first-1b.csv').read_bytes()
    native = (BASE / 'dma-first-1b.ila').read_bytes()
    rows = list(csv.reader(raw.decode('utf-8-sig').splitlines()))
    header, radix = rows[:2]
    samples = rows[2:]
    if len(samples) != 8192:
        raise AssertionError('expected one full 8192-sample capture')

    def values(name):
        col = header.index('dma_shell_i/' + name)
        if radix[col] != 'HEX':
            raise ValueError('unexpected signal radix')
        return [int(row[col], 16) for row in samples]

    heartbeat = values('reset_heartbeat[31:0]')
    if any(b != (a + 1) & 0xffffffff for a, b in zip(heartbeat, heartbeat[1:])):
        raise AssertionError('clock heartbeat discontinuity')
    if set(values('reset_rst')) != {0} or set(values('core_reset_sync_peripheral_aresetn[0:0]')) != {1}:
        raise AssertionError('reset interrupted the captured transaction')
    starts = [n for n, value in enumerate(values('ctrl_core_start_pulse')) if value]
    if len(starts) != 1:
        raise AssertionError('expected exactly one start')
    observed = {}
    for side in ('in', 'out'):
        prefix = 'probe_' + side + '_mon_'
        valid, ready = values(prefix + 'tvalid'), values(prefix + 'tready')
        data, keep, last = values(prefix + 'tdata[63:0]'), values(prefix + 'tkeep[7:0]'), values(prefix + 'tlast')
        handshakes = [n for n, (v, r) in enumerate(zip(valid, ready)) if v and r]
        if len(handshakes) != 1:
            raise AssertionError('expected exactly one ' + side + ' handshake')
        n = handshakes[0]
        if keep[n] != 1 or last[n] != 1 or n <= starts[0]:
            raise AssertionError('one-byte packet sideband/order mismatch')
        observed[side] = {'sample': n, 'keep': keep[n], 'last': last[n], 'byte': data[n] & 255}
    seed = 0x6d2b79f4
    seed ^= (seed << 13) & 0xffffffff
    seed ^= seed >> 17
    seed ^= (seed << 5) & 0xffffffff
    expected = seed & 255
    if observed['in']['byte'] != expected or observed['out']['byte'] != expected:
        raise AssertionError('input/output byte differs from acceptance seed')
    if observed['out']['sample'] < observed['in']['sample']:
        raise AssertionError('output precedes input')
    status = values('ctrl_debug_status[6:0]')
    if any(value & 0x44 for value in status) or not any((value & 0x3f) == 0x3a for value in status):
        raise AssertionError('controller error/reset or missing done')
    report = {'status': 'FIRST_ONE_BYTE_REAL_CAPTURE_PASS', 'samples': len(samples),
              'start_sample': starts[0], 'handshakes': observed, 'expected_byte': expected,
              'csv_sha256': hashlib.sha256(raw).hexdigest(),
              'native_ila_sha256': hashlib.sha256(native).hexdigest(),
              'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'First one-byte AXIS packet only; remaining sizes are checked by board acceptance, not inferred from this capture.'}
    destination = BASE.parents[2] / 'host' / 'fzl1-build009-onebyte-capture-check.json'
    destination.write_bytes((json.dumps(report, indent=2) + '\n').encode('utf-8'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
