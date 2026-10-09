#!/usr/bin/env python3
"""Fair serial/PS-optimized/cross-pair V10 benchmark, without programming PL."""
import argparse
import hashlib
import json
import os
import pathlib
import time

import numpy as np

try:
    from benchmark_cnn_pipeline_v10_full import _cpu_frequency_khz, _stats
    from cnn_ddr_v10_runtime import LinuxIoctlV10Transport
    from cnn_pipeline_v10_bundle import load_v10_release_bundle
    from cnn_pipeline_v10_deployment import load_v10_platform_deployment
    from cnn_pipeline_v10_paired_runtime import V10PairedNormalRuntime
    from cnn_pipeline_v10_stream_runtime import V10StreamRuntime
    from run_cnn_pipeline_v7_fixed import load_existing_split_clients
except ImportError:
    from .benchmark_cnn_pipeline_v10_full import _cpu_frequency_khz, _stats
    from .cnn_ddr_v10_runtime import LinuxIoctlV10Transport
    from .cnn_pipeline_v10_bundle import load_v10_release_bundle
    from .cnn_pipeline_v10_deployment import load_v10_platform_deployment
    from .cnn_pipeline_v10_paired_runtime import V10PairedNormalRuntime
    from .cnn_pipeline_v10_stream_runtime import V10StreamRuntime
    from .run_cnn_pipeline_v7_fixed import load_existing_split_clients


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _memory(clients):
    pids = [os.getpid()]
    for client in clients.values():
        process = getattr(getattr(client, '_client', client), 'process', None)
        if process is not None:
            pids.append(process.pid)
    result = {}
    for pid in sorted(set(pids)):
        try:
            lines = pathlib.Path('/proc/%d/status' % pid).read_text().splitlines()
            result[str(pid)] = {line.split(':')[0]: int(line.split()[1])
                               for line in lines if line.startswith(('VmRSS:', 'VmHWM:', 'Threads:'))}
        except (OSError, ValueError):
            result[str(pid)] = {'unavailable': True}
    return result


def _overlap(timeline):
    ps = [s for s in timeline if s['owner'] == 'PS']
    pl = [s for s in timeline if s['owner'] == 'PL']
    overlap = sum(max(0, min(a['end_ms'], b['end_ms']) - max(a['start_ms'], b['start_ms']))
                  for a in ps for b in pl if a['pair_index'] != b['pair_index'])
    return dict(cross_pair_ps_pl_overlap_ms=overlap,
                ps_worker_busy_ms=sum(s['end_ms']-s['start_ms'] for s in ps),
                pl_worker_busy_ms=sum(s['end_ms']-s['start_ms'] for s in pl))


def _phase(runtime, tensors, expected, pairs, first_id, schedule, in_flight):
    def inputs():
        for index in range(pairs*2):
            yield first_id+index, tensors[index % 2]
    started = time.perf_counter()
    if schedule == 'pipeline':
        results = runtime.run(inputs(), max_in_flight=in_flight)
    else:
        results = runtime.run(inputs())
    wall_ms = (time.perf_counter()-started)*1000
    summary = runtime.last_run_summary
    assert len(results) == pairs*2
    records = []
    for index, result in enumerate(results):
        assert result['frame_id'] == first_id+index
        raw = np.asarray(result['features'], dtype='<f4').tobytes()
        actual = _sha(raw)
        if actual != expected[index % 2]:
            raise RuntimeError('frame %d feature mismatch: %s' % (result['frame_id'], actual))
        if result['shadow_partner_used']:
            raise RuntimeError('paired benchmark unexpectedly used a shadow')
        for event in result['pl_completions']:
            completion = event['completion']
            if completion['protocol_error'] or completion['guard_error_flags']:
                raise RuntimeError('PL protocol or guard error')
        records.append(dict(frame_id=result['frame_id'], feature_sha256=actual,
                            shadow_partner_used=False))
    pair_timings = summary['pair_timings']
    assert len(pair_timings) == pairs
    ps = [sum(e['call_wall_ms'] for e in p['ps_events']) for p in pair_timings]
    ort = [sum(e['ort_run_ms'] for e in p['ps_events']) for p in pair_timings]
    pl = [sum(e['timing']['pl_window_wall_ms'] for e in p['pl_events']) for p in pair_timings]
    return dict(real_frames=len(records), pair_count=pairs, execution_ms=wall_ms,
                fps_including_fill_and_drain=len(records)*1000/wall_ms,
                admission_to_completion_ms=_stats([p['pair_wall_ms'] for p in pair_timings]),
                ps_call_sum_ms=_stats(ps), ps_ort_sum_ms=_stats(ort),
                pl_window_sum_ms=_stats(pl), features=records, runtime_summary=summary,
                overlap=_overlap(summary.get('timeline', [])), feature_protocol_pass=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle-root', required=True)
    parser.add_argument('--expected-bundle-sha256', required=True)
    parser.add_argument('--deployment-manifest', required=True)
    parser.add_argument('--expected-deployment-sha256', required=True)
    parser.add_argument('--runner', required=True)
    parser.add_argument('--ps-client', choices=('legacy', 'optimized'), default='legacy')
    parser.add_argument('--schedule', choices=('serial', 'pipeline'), required=True)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--max-in-flight', type=int, choices=(1, 2, 3, 4), default=3)
    parser.add_argument('--warmup-pairs', type=int, default=3)
    parser.add_argument('--measured-pairs', type=int, default=10)
    parser.add_argument('--timeout-s', type=float, default=120)
    parser.add_argument('--device', default='/dev/network10_v10')
    parser.add_argument('--input-tensor', action='append', required=True)
    parser.add_argument('--expected-feature-sha256', action='append', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    if len(args.input_tensor) != 2 or len(args.expected_feature_sha256) != 2:
        parser.error('two distinct real inputs and two golden feature hashes required')
    if not (1 <= args.threads <= 4 and args.warmup_pairs >= 3 and args.measured_pairs >= 10):
        parser.error('threads 1..4, at least 3 warmup pairs and 10 measured pairs required')
    if args.timeout_s <= 0:
        parser.error('positive timeout required')
    for sha in args.expected_feature_sha256:
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            parser.error('lowercase SHA256 required')
    output = pathlib.Path(args.output_dir)
    if output.exists():
        raise RuntimeError('output path already exists')
    tensors, input_hashes = [], []
    for path in args.input_tensor:
        raw = pathlib.Path(path).read_bytes()
        value = np.frombuffer(raw, dtype='<f4')
        if value.size != 3*256*256 or not np.isfinite(value).all():
            raise ValueError('invalid finite FP32 image tensor')
        tensors.append(value.reshape(1, 3, 256, 256).copy())
        input_hashes.append(_sha(raw))
    if input_hashes[0] == input_hashes[1]:
        raise ValueError('paired benchmark requires distinct image tensors')
    loaded = load_v10_release_bundle(args.bundle_root, args.expected_bundle_sha256)
    deployment = load_v10_platform_deployment(args.deployment_manifest,
        args.expected_deployment_sha256, loaded['manifest_sha256'])
    loader = load_existing_split_clients
    if args.ps_client == 'optimized':
        try:
            from cnn_v10_ps_clients import load_optimized_split_clients
        except ImportError:
            from .cnn_v10_ps_clients import load_optimized_split_clients
        loader = load_optimized_split_clients
    clients, transport, runtime, cleanup = None, None, None, None
    cpu_before = _cpu_frequency_khz()
    try:
        started = time.perf_counter()
        clients, _ = loader(loaded['model_root'], args.runner, loaded['model_manifest'],
                            loaded['model_manifest_sha256'], threads=args.threads)
        headers = {name: client.header for name, client in clients.items()}
        transport = LinuxIoctlV10Transport(args.device,
            expected_parameter_manifest_words=loaded['parameter_manifest_words'])
        cls = V10StreamRuntime if args.schedule == 'pipeline' else V10PairedNormalRuntime
        runtime = cls(transport, loaded['parameter_contract'], loaded['manifest_sha256'],
                      clients, timeout_s=args.timeout_s)
        setup_ms = (time.perf_counter()-started)*1000
        warmup = _phase(runtime, tensors, args.expected_feature_sha256, args.warmup_pairs,
                        100000, args.schedule, args.max_in_flight)
        memory_before = _memory(clients)
        measured = _phase(runtime, tensors, args.expected_feature_sha256, args.measured_pairs,
                          200000, args.schedule, args.max_in_flight)
        memory_after = _memory(clients)
    finally:
        started = time.perf_counter()
        if runtime is not None:
            cleanup = runtime.close()
        else:
            try:
                if transport is not None:
                    transport.close()
            finally:
                for client in (clients or {}).values():
                    client.close()
        cleanup_ms = (time.perf_counter()-started)*1000
    if not all(cleanup.get(key) for key in ('transport_closed', 'clients_closed',
                                           'all_handles_freed', 'quiesce_confirmed')):
        raise RuntimeError('incomplete cleanup')
    result = dict(schema='v10-ps-cross-pair-benchmark-v1', status='FEATURE_EXACT_PROTOCOL_CLEAN',
        schedule=args.schedule, ps_client=args.ps_client, ort_threads=args.threads,
        ort_partition_allow_spinning=os.environ.get('ORT_PARTITION_ALLOW_SPINNING', 'unset'),
        ort_partition_prealloc_outputs=os.environ.get('ORT_PARTITION_PREALLOC_OUTPUTS', 'unset'),
        ort_headers=headers, runner_sha256=_sha(pathlib.Path(args.runner).read_bytes()),
        release_manifest_sha256=loaded['manifest_sha256'],
        deployment_manifest_sha256=deployment['manifest_sha256'],
        kernel_clock_hz=deployment['clock_hz'], input_tensor_sha256=input_hashes,
        expected_feature_sha256=args.expected_feature_sha256,
        cpu_frequency_khz_before=cpu_before, cpu_frequency_khz_after=_cpu_frequency_khz(),
        owned_process_memory_before=memory_before, owned_process_memory_after=memory_after,
        rss_note='per-process RSS/HWM in kB; sums include shared pages, not unique physical RAM',
        setup_ms=setup_ms, warmup=warmup, measured=measured, cleanup=cleanup, cleanup_ms=cleanup_ms,
        scope='Resident engineering input regression; FPS includes pipeline fill/drain, excludes setup/input loading and output validation; not camera-to-display FPS')
    output.mkdir(parents=True)
    raw = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n').encode('utf-8')
    (output/'result.json').write_bytes(raw)
    print(json.dumps(dict(status=result['status'], result_sha256=_sha(raw),
        fps=measured['fps_including_fill_and_drain'], overlap=measured['overlap'],
        latency=measured['admission_to_completion_ms']), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
