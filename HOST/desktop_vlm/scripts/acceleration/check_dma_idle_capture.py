"""Fail-closed FZL1 idle ILA gate before Linux binding; CSV supplements native ILA."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


EXPECTED_IDLE = {
    'dma_shell_i/reset_rst': 0,
    'dma_shell_i/ctrl_core_start_pulse': 0,
    'dma_shell_i/core_reset_sync_peripheral_aresetn[0:0]': 1,
    'dma_shell_i/probe_in_mon_tvalid': 0,
    'dma_shell_i/probe_out_mon_tvalid': 0,
    'dma_shell_i/irq_concat_dout[1:0]': 0,
    'dma_shell_i/ctrl_debug_status[6:0]': 0,
}
HEARTBEAT = 'dma_shell_i/reset_heartbeat[31:0]'


def inspect_capture(csv_path, native_path, expected_samples=8192):
    failures = []
    csv_blob, native_blob = csv_path.read_bytes(), native_path.read_bytes()
    if not native_blob:
        failures.append('native ILA is empty')
    lines = list(csv.reader(csv_blob.decode('utf-8-sig').splitlines()))
    if len(lines) < 3:
        raise ValueError('missing CSV header/radix/samples')
    header, radix = lines[:2]
    if len(header) != len(set(header)):
        raise ValueError('duplicate signal column')
    required = list(EXPECTED_IDLE) + [HEARTBEAT, 'Sample in Buffer', 'Sample in Window']
    index = {name: header.index(name) for name in required}
    if len(header) != len(radix):
        raise ValueError('radix width differs')
    for name in list(EXPECTED_IDLE) + [HEARTBEAT]:
        if radix[index[name]].strip() != 'HEX':
            raise ValueError('expected HEX radix: ' + name)
    samples = lines[2:]
    if expected_samples not in (1024, 2048, 4096, 8192):
        raise ValueError('expected_samples must match a supported frozen ILA depth')
    if len(samples) != expected_samples:
        failures.append('expected %d samples, got %d' % (expected_samples, len(samples)))
    observed = {name: set() for name in EXPECTED_IDLE}
    previous_heartbeat = None
    heartbeat_errors = 0
    sample_errors = 0
    for row_number, row in enumerate(samples):
        if len(row) != len(header):
            raise ValueError('sample width differs')
        if int(row[index['Sample in Buffer']]) != row_number or int(row[index['Sample in Window']]) != row_number:
            sample_errors += 1
        for name in observed:
            observed[name].add(int(row[index[name]], 16))
        heartbeat = int(row[index[HEARTBEAT]], 16)
        if previous_heartbeat is not None and heartbeat != (previous_heartbeat + 1) & 0xffffffff:
            heartbeat_errors += 1
        previous_heartbeat = heartbeat
    for name, values in observed.items():
        if values != {EXPECTED_IDLE[name]}:
            failures.append('%s expected %d, observed %s' % (name, EXPECTED_IDLE[name], sorted(values)))
    if heartbeat_errors:
        failures.append('heartbeat increment mismatches: %d' % heartbeat_errors)
    if sample_errors:
        failures.append('sample index mismatches: %d' % sample_errors)
    return {
        'status': 'IDLE_CAPTURE_GATE_PASS' if not failures else 'IDLE_CAPTURE_GATE_FAIL_DO_NOT_BIND',
        'sample_count': len(samples), 'expected_sample_count': expected_samples, 'failures': failures,
        'observed': {name: sorted(values) for name, values in observed.items()},
        'csv_sha256': hashlib.sha256(csv_blob).hexdigest(),
        'native_ila_sha256': hashlib.sha256(native_blob).hexdigest(),
        'native_ila_bytes': len(native_blob),
        'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'Idle clock/reset/data gate only; native ILA must separately reopen in Vivado. No DMA functional or timing certification.',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv', type=Path)
    parser.add_argument('ila', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-samples', type=int, default=8192,
                        choices=(1024, 2048, 4096, 8192))
    args = parser.parse_args()
    report = inspect_capture(args.csv, args.ila, args.expected_samples)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 2 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
