"""Audit saved real-board pipeline receipts without contacting the board."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from compare_stages import compare, percentile, summarize


def require(condition, message):
    if not condition:
        raise ValueError(message)


def phase_audit(data, golden):
    summary = summarize(data)
    require(len(data['records']) == 30 and data['warmup_count'] == 3, 'formal sample counts')
    prior = None
    for index, record in enumerate(data['records']):
        reference = golden[index]
        require(record['frame_id'] == index, 'returned frame order')
        for key in ('sample_id', 'input_sha256', 'pl_input_sha256', 'pl_output_sha256'):
            require(record[key] == reference[key], 'frozen reference mismatch: ' + key)
        mapping = record['frame_mapping']
        require(mapping['logical_frame_id'] == index, 'logical mapping')
        require(mapping['completed_frames_after'] == mapping['completed_frames_before'] + 1,
                'completed counter increment')
        if prior is not None:
            require(mapping['completed_frames_before'] == prior['completed_frames_after'],
                    'completed counter continuity')
            for key in ('hardware_frame_id', 'request_id'):
                require(mapping[key] == prior[key] + 1, key + ' continuity')
        prior = mapping
        validation = record['validation']
        require(validation['pl_input_sha256_match'] and validation['pl_output_sha256_match'],
                'live packet validation')
        feature = validation['feature']
        require(feature['numeric_match'] and 0 <= feature['max_abs'] <= 1e-6
                and feature['cosine'] >= .99999, 'feature numeric threshold')
    return summary


def audit(current, previous, baseline):
    require(current['stage'] == 'stage3-bounded-pipeline-v2', 'expected v2 stage3')
    require(current['execution'] == previous['execution'] == 'board', 'real board runs required')
    require(current['identity']['backend'] == previous['identity']['backend'],
            'hardware/driver/quantization identity differs')
    require(current['identity']['runtime_split_manifest_sha256'] ==
            previous['identity']['runtime_split_manifest_sha256'], 'runtime split differs')
    require(current['quiesce_status']['success'] and current['runtime_close_success']
            and not current['pipeline_threads_alive_after_run'], 'teardown incomplete')
    queue = current['queue']
    require(queue['max_in_flight'] == queue['admitted_frame_bound'] == 2, 'global limit differs')
    require(0 < queue['observed_in_flight_peak'] <= 2
            and queue['observed_in_flight_current_after_run'] == 0, 'global lease leak/overflow')
    require(all(0 <= peak <= queue['capacity_per_boundary'] for peak in queue['peak'].values()),
            'queue capacity overflow')
    control = copy.deepcopy(current)
    control.update(current['matched_serial_control'])
    control['stage'] = 'stage3-matched-serial-1-3'
    control['batch_start_ms'] = 0.0
    for phase in (current, control):
        phase_audit(phase, previous['records'])
    require(current['matched_comparison']['frequency_conditions_match'], 'CPU frequency changed')
    vectors = current['matched_comparison']['frequency_vectors']
    require(len(vectors) == 4 and all(v == current['cpu_frequency_khz'] for v in vectors.values()),
            'four frequency snapshots do not match')
    boundaries = {name: [] for name in ('arrival_to_complete_ms', 'admission_wait_ms',
                                       'admitted_to_complete_ms')}
    admitted = copy.deepcopy(current)
    for record, normalized in zip(current['records'], admitted['records']):
        arrival, entry, done = record['submit_ms'], record['queue_admitted_ms'], record['complete_ms']
        require(math.isfinite(entry) and arrival <= entry <= done, 'invalid admission time')
        require(math.isclose(arrival, record['admission_start_ms'], abs_tol=1e-6), 'arrival boundary')
        require(math.isclose(done-arrival, record['end_to_end_ms'], abs_tol=1e-6), 'end-to-end boundary')
        require(math.isclose(entry-arrival, record['admission_wait_ms'], abs_tol=1e-6), 'admission wait')
        boundaries['arrival_to_complete_ms'].append(done-arrival)
        boundaries['admission_wait_ms'].append(entry-arrival)
        boundaries['admitted_to_complete_ms'].append(done-entry)
        normalized['submit_ms'] = entry
    boundaries = {name: {'p50': percentile(values, .5), 'p95': percentile(values, .95),
                         'max': max(values)} for name, values in boundaries.items()}
    old_comparison = compare(previous, admitted)
    old_comparison['latency_scope'] = 'Both normalized to actual queue admission; excludes producer admission wait.'
    return {'status': 'PASS_INDEPENDENT_PIPELINE_V2_AUDIT',
            'matched_serial': compare(control, current),
            'previous_pipeline_admitted_boundary': old_comparison,
            'vs_pure_ps': compare(baseline, current),
            'latency_boundaries': boundaries, 'queue': queue,
            'resident_memory': current['resident_memory'],
            'scope': 'Recomputes receipt/counter/hash/threshold/timing consistency. Raw features are not retained in this receipt; feature metrics remain board validation evidence. Old pipeline has no per-frame producer-arrival timestamps.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('current', 'previous', 'baseline'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = [args.current, args.previous, args.baseline]
    result = audit(*(json.loads(path.read_text(encoding='utf-8')) for path in paths))
    result['sources'] = [{'path': str(path.resolve()),
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
    result['checker_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
