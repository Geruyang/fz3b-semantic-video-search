"""Compare measured board stages without mixing timing boundaries or fake runs.

Input schema is documented in docs/plans/2026-10-04-four-stage-acceleration.md.
No hardware access is performed.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' must be finite numeric')
    return float(value)


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(name + ' must be an integer >= ' + str(minimum))
    return value


def _sha(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError(name + ' must be lower-case SHA256')
    return value


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def summarize(data):
    # Legacy baseline v1 has no status field. Explicit failure/teardown flags
    # in newer runs must override otherwise complete and numerically valid rows.
    if 'status' in data and data['status'] != 'PASS':
        raise ValueError('run status is not PASS')
    if 'compare_eligible' in data and data['compare_eligible'] is not True:
        raise ValueError('run is explicitly ineligible for comparison')
    if data.get('schema_version') != 1:
        raise ValueError('unsupported schema_version')
    if data.get('execution') not in ('board', 'simulation'):
        raise ValueError('execution must identify board or simulation')
    for field in ('stage', 'boundary'):
        if not isinstance(data.get(field), str) or not data[field]:
            raise ValueError(field + ' is required')
    for field in ('model_sha256', 'input_sequence_sha256'):
        _sha(data.get(field), field)
    if not isinstance(data.get('profile'), bool):
        raise ValueError('profile must be boolean')
    _integer(data.get('warmup_count'), 'warmup_count')
    threads = data.get('threads')
    if not isinstance(threads, dict) or not threads:
        raise ValueError('threads must describe measured thread allocations')
    for key, value in threads.items():
        _integer(value, 'threads.' + key, 1)
    clocks = data.get('cpu_frequency_khz')
    if not isinstance(clocks, list) or not clocks:
        raise ValueError('cpu_frequency_khz required')
    for clock in clocks:
        _integer(clock, 'cpu_frequency_khz', 1)
    expected = data.get('expected_frame_ids')
    records = data.get('records')
    if not isinstance(expected, list) or not expected or not isinstance(records, list):
        raise ValueError('nonempty expected_frame_ids and records required')
    for frame in expected:
        _integer(frame, 'expected frame_id')
    if len(set(expected)) != len(expected):
        raise ValueError('duplicate expected frame_id')
    start = _number(data.get('batch_start_ms'), 'batch_start_ms')
    end = _number(data.get('batch_end_ms'), 'batch_end_ms')
    if end <= start:
        raise ValueError('batch interval must be positive')
    by_id = {}
    latency = []
    for record in records:
        frame = _integer(record.get('frame_id'), 'frame_id')
        if frame in by_id:
            raise ValueError('duplicate returned frame_id')
        submitted = _number(record.get('submit_ms'), 'submit_ms')
        completed = _number(record.get('complete_ms'), 'complete_ms')
        if not start <= submitted <= completed <= end:
            raise ValueError('frame interval outside batch or reversed')
        _sha(record.get('input_sha256'), 'input_sha256')
        _sha(record.get('feature_sha256'), 'feature_sha256')
        if record.get('correct') is not True:
            raise ValueError('incorrect or unverified frame result')
        by_id[frame] = record
        latency.append(completed - submitted)
    if set(by_id) != set(expected):
        raise ValueError('missing or unexpected returned frame_id')
    # This binds the ordered input identities, rather than trusting an opaque tag.
    sequence = ''.join(by_id[frame]['input_sha256'] + '\n' for frame in expected)
    if hashlib.sha256(sequence.encode('ascii')).hexdigest() != data['input_sequence_sha256']:
        raise ValueError('input sequence digest differs from ordered records')
    if not isinstance(data.get('identity'), dict) or not data['identity']:
        raise ValueError('software/hardware identity required')
    result = {
        'stage': data['stage'], 'execution': data['execution'],
        'frames': len(records), 'batch_wall_ms': end - start,
        'throughput_fps': len(records) * 1000.0 / (end - start),
        'latency_p50_ms': percentile(latency, 0.50),
        'latency_p95_ms': percentile(latency, 0.95),
        'returned_order_matches': [r['frame_id'] for r in records] == expected,
        'all_frames_correct': True,
        'formal_sample_count': data['warmup_count'] >= 3 and len(records) >= 30,
    }
    return result


def compare(previous, current):
    before, after = summarize(previous), summarize(current)
    mismatches = []
    for name in ('model_sha256', 'input_sequence_sha256', 'boundary', 'threads',
                 'cpu_frequency_khz', 'warmup_count', 'expected_frame_ids'):
        if previous[name] != current[name]:
            mismatches.append(name)
    if previous['execution'] != 'board' or current['execution'] != 'board':
        mismatches.append('requires_two_real_board_runs')
    if previous['profile'] or current['profile']:
        mismatches.append('profile_must_be_disabled')
    if not before['formal_sample_count'] or not after['formal_sample_count']:
        mismatches.append('requires_3_warmups_and_30_measured_frames')
    if not before['returned_order_matches'] or not after['returned_order_matches']:
        mismatches.append('returned_order_changed')
    result = {'previous': before, 'current': after,
              'controlled_comparison': not mismatches, 'condition_differences': mismatches}
    if not mismatches:
        result['throughput_speedup'] = after['throughput_fps'] / before['throughput_fps']
        if before['latency_p50_ms'] > 0:
            result['latency_p50_reduction_percent'] = 100 * (1 - after['latency_p50_ms'] / before['latency_p50_ms'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path)
    parser.add_argument('current', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = compare(json.loads(args.previous.read_text(encoding='utf-8')),
                     json.loads(args.current.read_text(encoding='utf-8')))
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded, end='')


if __name__ == '__main__':
    main()
