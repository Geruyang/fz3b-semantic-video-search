#!/usr/bin/env python3
"""Measure incremental V10 candidates without programming or restoring PL.

Exact baseline comparisons and quantized engineering regression gates are
separate. Feature validation is outside the timed iteration. Results are from
resident tensors, not camera-to-display throughput or recognition accuracy.
"""
import argparse
import hashlib
import json
import math
import os
import pathlib
import time

import numpy as np

try:
    from benchmark_cnn_pipeline_v10_full import _cpu_frequency_khz, _stats
    from benchmark_cnn_pipeline_v10_stream import _memory, _overlap
    from cnn_ddr_v10_runtime import LinuxIoctlV10Transport
    from cnn_pipeline_v10_bundle import load_v10_release_bundle
    from cnn_pipeline_v10_deployment import load_v10_platform_deployment
    from cnn_pipeline_v10_live_runtime import V10LiveRuntime
    from cnn_pipeline_v10_delivery import V10ResultDelivery
except ImportError:
    from .benchmark_cnn_pipeline_v10_full import _cpu_frequency_khz, _stats
    from .benchmark_cnn_pipeline_v10_stream import _memory, _overlap
    from .cnn_ddr_v10_runtime import LinuxIoctlV10Transport
    from .cnn_pipeline_v10_bundle import load_v10_release_bundle
    from .cnn_pipeline_v10_deployment import load_v10_platform_deployment
    from .cnn_pipeline_v10_live_runtime import V10LiveRuntime
    from .cnn_pipeline_v10_delivery import V10ResultDelivery


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _quantized_partitions(args, evidence):
    """Require the loaded backend to attest every requested quantized region."""
    requested = sorted(name for name, path in (
        ('n1', args.n1_manifest), ('suffix', args.suffix_candidate),
        ('n1_pl', getattr(args, 'pl_chain_manifest', None))) if path)
    actual = evidence.get('active_quantized_partitions', [])
    if (not isinstance(actual, list) or
            any(not isinstance(name, str) for name in actual) or
            sorted(actual) != requested):
        raise ValueError('loaded quantized partition identity differs from requested candidates')
    if requested and args.ps_client != 'mixed':
        raise ValueError('quantized partitions require mixed backend')
    return requested


def _check_pl_event(event):
    if 'jobs' in event:
        jobs = event['jobs']
        if (event.get('profiles') != [2, 3, 0] or not isinstance(jobs, list) or
                len(jobs) != 3 or [job.get('profile') for job in jobs] != [2, 3, 0]):
            raise RuntimeError('PL chain job order or extent mismatch')
    else:
        jobs = [event]
    for job in jobs:
        completion = job['completion']
        if completion['protocol_error'] or completion['guard_error_flags']:
            raise RuntimeError('PL protocol or guard error')


def compare_feature(value, expected_sha, reference=None, min_cosine=.999,
                    max_relative_l2=.05):
    array = np.asarray(value, dtype='<f4')
    if array.shape != (512,) or not np.isfinite(array).all():
        raise ValueError('feature must be finite FP32 shape (512,)')
    actual = _sha(array.tobytes())
    record = dict(feature_sha256=actual, reference_sha256=expected_sha,
                  exact=actual == expected_sha)
    if reference is None:
        if not record['exact']:
            raise ValueError('feature SHA mismatch: expected %s, got %s' % (expected_sha, actual))
        return record
    ref = np.asarray(reference, dtype='<f4')
    if (ref.shape != (512,) or not np.isfinite(ref).all()
            or _sha(ref.tobytes()) != expected_sha):
        raise ValueError('reference feature shape, finite or SHA identity mismatch')
    if (not math.isfinite(min_cosine) or not -1 <= min_cosine <= 1
            or not math.isfinite(max_relative_l2) or max_relative_l2 < 0):
        raise ValueError('invalid feature regression thresholds')
    a, b = array.astype(np.float64), ref.astype(np.float64)
    norm_a, norm_b = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    error = float(np.linalg.norm(a-b))
    if norm_b == 0:
        if error != 0:
            raise ValueError('feature regression: nonzero result for zero reference')
        cosine, relative = 1.0, 0.0
    else:
        cosine = float(np.dot(a, b)/(norm_a*norm_b)) if norm_a else 0.0
        cosine = max(-1.0, min(1.0, cosine))
        relative = error/norm_b
    record.update(cosine=cosine, relative_l2=relative,
                  max_abs=float(np.max(np.abs(a-b))))
    if cosine < min_cosine or relative > max_relative_l2:
        raise ValueError('feature regression threshold failed: %s' % json.dumps(record, sort_keys=True))
    return record


def measure_live_phase(runtime, tensors, expected, pairs, first_id, in_flight,
                       references=None, min_cosine=.999, max_relative_l2=.05,
                       feature_dump_path=None, delivery_path=None, delivery_capacity=4):
    def inputs():
        for index in range(pairs*2):
            yield first_id+index, tensors[index % 2]
    records, deliveries, results = [], [], []
    output_stream = None if delivery_path is None else pathlib.Path(delivery_path).open('x', encoding='utf-8')
    emitted = []
    def emit(result):
        output_stream.write(json.dumps(dict(frame_id=result['frame_id'],
            features=np.asarray(result['features']).tolist()), allow_nan=False)+'\n')
        output_stream.flush()
        emitted.append(dict(frame_id=result['frame_id'],
                            flushed_ms=(time.perf_counter()-started)*1000))
    sink = None if output_stream is None else V10ResultDelivery(emit, delivery_capacity)
    started = time.perf_counter()
    first_result_ms = None
    primary_error = None
    try:
        with runtime.iter_results(inputs(), max_in_flight=in_flight, record_history=True) as stream:
            for result in stream:
                if first_result_ms is None:
                    first_result_ms = (time.perf_counter()-started)*1000
                # No SHA or numerical validation in the timing window.
                results.append(result)
                if sink is not None:
                    sink.submit(result)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_errors, first_cleanup_error = [], None
        try:
            if sink is not None:
                sink.close()
        except BaseException as error:
            first_cleanup_error = error
            cleanup_errors.append('%s: %s' % (type(error).__name__, error))
        try:
            if output_stream is not None:
                output_stream.close()
        except BaseException as error:
            if first_cleanup_error is None:
                first_cleanup_error = error
            cleanup_errors.append('%s: %s' % (type(error).__name__, error))
        if primary_error is not None:
            primary_error.delivery_cleanup_errors = cleanup_errors
        elif first_cleanup_error is not None:
            first_cleanup_error.delivery_cleanup_errors = cleanup_errors
            raise first_cleanup_error
    wall_ms = (time.perf_counter()-started)*1000
    summary = runtime.last_run_summary
    if feature_dump_path is not None:
        pathlib.Path(feature_dump_path).write_bytes(
            b''.join(np.asarray(r['features'], dtype='<f4').tobytes() for r in results))
    if len(results) != pairs*2 or summary['status'] != 'COMPLETED':
        raise RuntimeError('incomplete live inference phase')
    for index, result in enumerate(results):
        if result['frame_id'] != first_id+index or result['shadow_partner_used']:
            raise RuntimeError('unexpected frame order or shadow in paired benchmark')
        comparison = compare_feature(result['features'], expected[index % 2],
            None if references is None else references[index % 2], min_cosine, max_relative_l2)
        for event in result['pl_completions']:
            _check_pl_event(event)
        comparison.update(frame_id=result['frame_id'], shadow_partner_used=False)
        records.append(comparison)
        deliveries.append(dict(frame_id=result['frame_id'], delivery_ms=result['delivery_ms'],
            completion_to_delivery_ms=result['completion_to_delivery_ms']))
    pair_timings = summary['pair_timings']
    if len(pair_timings) != pairs:
        raise RuntimeError('pair timing count mismatch')
    return dict(real_frames=len(records), pair_count=pairs, execution_ms=wall_ms,
        fps_including_fill_and_drain=len(records)*1000/wall_ms,
        first_result_ms=first_result_ms, deliveries=deliveries,
        result_delivery=None if sink is None else dict(summary=sink.summary(),
            flushed_results=emitted, first_flushed_ms=emitted[0]['flushed_ms'],
            last_flushed_ms=emitted[-1]['flushed_ms']),
        completion_to_delivery_ms=_stats([x['completion_to_delivery_ms'] for x in deliveries]),
        admission_to_completion_ms=_stats([p['pair_wall_ms'] for p in pair_timings]),
        ps_call_sum_ms=_stats([sum(e['call_wall_ms'] for e in p['ps_events']) for p in pair_timings]),
        ps_ort_sum_ms=_stats([sum(e['ort_run_ms'] for e in p['ps_events']) for p in pair_timings]),
        ps_native_sum_ms=_stats([sum(e.get('native_run_ms', 0.0) for e in p['ps_events']) for p in pair_timings]),
        ps_backend_sum_ms=_stats([sum(e.get('backend_run_ms',
            e['ort_run_ms']+e.get('native_run_ms', 0.0)) for e in p['ps_events']) for p in pair_timings]),
        pl_window_sum_ms=_stats([sum(e['timing']['pl_window_wall_ms'] for e in p['pl_events'])
                               for p in pair_timings]),
        features=records, runtime_summary=summary, overlap=_overlap(summary['timeline']),
        validation_mode='exact' if references is None else 'quantized_engineering_regression',
        feature_protocol_pass=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle-root', required=True)
    parser.add_argument('--expected-bundle-sha256', required=True)
    parser.add_argument('--deployment-manifest', required=True)
    parser.add_argument('--expected-deployment-sha256', required=True)
    parser.add_argument('--runner', required=True)
    parser.add_argument('--ps-client', choices=('optimized', 'shm', 'mixed'), default='shm')
    parser.add_argument('--n1-manifest')
    parser.add_argument('--pl-chain-manifest')
    parser.add_argument('--expected-pl-chain-manifest-sha256')
    parser.add_argument('--capture-suffix-input-dir',
                        help='capture P3-domain suffix inputs for quality checks; invalidates performance measurement')
    parser.add_argument('--suffix-candidate')
    parser.add_argument('--native-lib')
    parser.add_argument('--threads', type=int, default=3)
    parser.add_argument('--max-in-flight', type=int, choices=(1, 2, 3, 4), default=3)
    parser.add_argument('--warmup-pairs', type=int, default=3)
    parser.add_argument('--measured-pairs', type=int, default=30)
    parser.add_argument('--timeout-s', type=float, default=300)
    parser.add_argument('--device', default='/dev/network10_v10')
    parser.add_argument('--wc-qualification')
    parser.add_argument('--expected-wc-qualification-sha256')
    parser.add_argument('--input-tensor', action='append', required=True)
    parser.add_argument('--expected-feature-sha256', action='append', required=True)
    parser.add_argument('--reference-feature', action='append')
    parser.add_argument('--min-feature-cosine', type=float, default=.999)
    parser.add_argument('--max-feature-relative-l2', type=float, default=.05)
    parser.add_argument('--deliver-jsonl', action='store_true',
                        help='include bounded background JSONL feature delivery in measured throughput')
    parser.add_argument('--delivery-queue-capacity', type=int, default=4)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    if len(args.input_tensor) != 2 or len(args.expected_feature_sha256) != 2:
        parser.error('two different real inputs and two reference feature hashes required')
    if not (1 <= args.threads <= 4 and args.warmup_pairs >= 3 and args.measured_pairs >= 10):
        parser.error('threads 1..4, >=3 warmup pairs and >=10 measured pairs required')
    if not math.isfinite(args.timeout_s) or args.timeout_s <= 0:
        parser.error('finite positive timeout required')
    if not 1 <= args.delivery_queue_capacity <= 64:
        parser.error('delivery queue capacity must be 1..64')
    if bool(args.wc_qualification) != bool(args.expected_wc_qualification_sha256):
        parser.error('WC qualification path and expected SHA must be supplied together')
    if bool(args.pl_chain_manifest) != bool(args.expected_pl_chain_manifest_sha256):
        parser.error('PL chain manifest and expected SHA must be supplied together')
    if args.capture_suffix_input_dir and not args.pl_chain_manifest:
        parser.error('suffix input capture requires the PL chain')
    if args.pl_chain_manifest and (args.n1_manifest or args.wc_qualification):
        parser.error('PL chain excludes PS-native N1 and the A0001 WC qualification')
    if args.ps_client != 'mixed' and any((args.n1_manifest, args.suffix_candidate,
                                        args.native_lib, args.pl_chain_manifest)):
        parser.error('mixed/native artifacts require --ps-client mixed')
    if args.reference_feature and len(args.reference_feature) != 2:
        parser.error('two reference feature files required')
    if any((args.n1_manifest, args.suffix_candidate, args.pl_chain_manifest)) and not args.reference_feature:
        parser.error('quantized candidates require explicit reference features and regression gates')
    for value in args.expected_feature_sha256:
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            parser.error('lowercase reference SHA256 required')
    tensors, input_hashes, references = [], [], None
    for path in args.input_tensor:
        raw = pathlib.Path(path).read_bytes()
        value = np.frombuffer(raw, dtype='<f4')
        if value.size != 3*256*256 or not np.isfinite(value).all():
            raise ValueError('invalid finite FP32 image tensor')
        tensors.append(value.reshape(1, 3, 256, 256).copy())
        input_hashes.append(_sha(raw))
    if input_hashes[0] == input_hashes[1]:
        raise ValueError('two different image tensors required')
    if args.reference_feature:
        references = [np.frombuffer(pathlib.Path(p).read_bytes(), dtype='<f4').copy()
                      for p in args.reference_feature]
        for value, expected in zip(references, args.expected_feature_sha256):
            compare_feature(value, expected, value, args.min_feature_cosine, args.max_feature_relative_l2)
    loaded = load_v10_release_bundle(args.bundle_root, args.expected_bundle_sha256)
    p3_parameters = p3_mixin = None
    transport_type = LinuxIoctlV10Transport
    parameter_words = loaded['parameter_manifest_words']
    if args.pl_chain_manifest:
        try:
            from cnn_pipeline_v10_chain_deployment import load_v10_chain_deployment
            from cnn_pipeline_v10_p3_runtime import V10P3ChainMixin, load_v10_p3_parameters
            from cnn_ddr_v10_p3_runtime import LinuxIoctlV10P3Transport
        except ImportError:
            from .cnn_pipeline_v10_chain_deployment import load_v10_chain_deployment
            from .cnn_pipeline_v10_p3_runtime import V10P3ChainMixin, load_v10_p3_parameters
            from .cnn_ddr_v10_p3_runtime import LinuxIoctlV10P3Transport
        deployment = load_v10_chain_deployment(args.deployment_manifest,
            args.expected_deployment_sha256, loaded['manifest_sha256'],
            args.expected_pl_chain_manifest_sha256)
        p3_parameters = load_v10_p3_parameters(args.pl_chain_manifest,
            args.expected_pl_chain_manifest_sha256, loaded['parameter_contract'])
        wanted_words = tuple(int(args.expected_pl_chain_manifest_sha256[i:i+8], 16)
                             for i in range(0, 64, 8))
        if (p3_parameters.get('manifest_sha256') != args.expected_pl_chain_manifest_sha256 or
                p3_parameters.get('parameter_manifest_words') != wanted_words):
            raise ValueError('PL chain parameters differ from combined manifest identity')
        parameter_contract = p3_parameters.get('contract')
        deployment_contract = deployment['manifest'].get('chain_contract')
        if (not isinstance(parameter_contract, dict) or
                not isinstance(deployment_contract, dict) or
                json.dumps(parameter_contract, sort_keys=True, allow_nan=False) !=
                json.dumps(deployment_contract, sort_keys=True, allow_nan=False)):
            raise ValueError('PL chain parameter and deployment contracts differ')
        parameter_words = wanted_words
        transport_type, p3_mixin = LinuxIoctlV10P3Transport, V10P3ChainMixin
    else:
        deployment = load_v10_platform_deployment(args.deployment_manifest,
            args.expected_deployment_sha256, loaded['manifest_sha256'])
    qualified = None
    target_device = deployment['manifest']['target']['device']
    if args.wc_qualification:
        try:
            from cnn_pipeline_v10_wc_deployment import load_v10_wc_qualification
        except ImportError:
            from .cnn_pipeline_v10_wc_deployment import load_v10_wc_qualification
        qualified = load_v10_wc_qualification(args.wc_qualification,
            args.expected_wc_qualification_sha256, args.deployment_manifest,
            args.expected_deployment_sha256, loaded['manifest_sha256'])
        target_device = qualified['manifest']['target']['device']
    if args.device != target_device:
        raise ValueError('device differs from deployment target contract')
    runner_sha_before = _sha(pathlib.Path(args.runner).read_bytes())
    output = pathlib.Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    clients = transport = runtime = cleanup = None
    capture_client = None
    cpu_before = _cpu_frequency_khz()
    candidate_evidence, mixin_kwargs = {}, {}
    report = dict(schema='v10-live-ps-candidate-benchmark-v1', status='FAILED',
                  ps_client=args.ps_client, ort_threads=args.threads,
                  device=args.device, runner_sha256=runner_sha_before,
                  pl_chain_manifest_sha256=args.expected_pl_chain_manifest_sha256,
                  wc_qualification=None if qualified is None else qualified['manifest'],
                  wc_qualification_sha256=None if qualified is None else qualified['manifest_sha256'],
                  deliver_jsonl=args.deliver_jsonl,
                  input_tensor_sha256=input_hashes,
                  expected_feature_sha256=args.expected_feature_sha256,
                  min_feature_cosine=args.min_feature_cosine,
                  max_feature_relative_l2=args.max_feature_relative_l2)
    failure = None
    try:
        started = time.perf_counter()
        cls = V10LiveRuntime
        if args.ps_client == 'mixed':
            try:
                from cnn_pipeline_v10_mixed_runtime import (
                    build_v10_mixed_components, V10MixedBoundaryMixin)
            except ImportError:
                from .cnn_pipeline_v10_mixed_runtime import (
                    build_v10_mixed_components, V10MixedBoundaryMixin)
            clients, unused_sha, mixin_kwargs, candidate_evidence = build_v10_mixed_components(
                loaded['model_root'], loaded['model_manifest'], loaded['model_manifest_sha256'],
                args.runner, threads=args.threads, n1_manifest=args.n1_manifest,
                suffix_candidate=args.suffix_candidate, native_lib=args.native_lib)
            class V10LiveMixedRuntime(V10MixedBoundaryMixin, V10LiveRuntime):
                pass
            cls = V10LiveMixedRuntime
            if p3_parameters is not None:
                class V10LiveChainRuntime(p3_mixin, V10MixedBoundaryMixin, V10LiveRuntime):
                    pass
                cls = V10LiveChainRuntime
                mixin_kwargs['p3_parameters'] = p3_parameters
                candidate_evidence = dict(candidate_evidence)
                active = candidate_evidence.get('active_quantized_partitions', [])
                if not isinstance(active, list):
                    raise ValueError('mixed backend active partition identity is malformed')
                candidate_evidence['active_quantized_partitions'] = active + ['n1_pl']
                candidate_evidence['pl_chain'] = {
                    'manifest_sha256': p3_parameters['manifest_sha256'],
                    'p3_manifest_sha256': p3_parameters['p3_manifest_sha256'],
                    'evidence': p3_parameters['evidence'],
                }
        else:
            if args.ps_client == 'shm':
                try:
                    from cnn_v10_ps_shm_clients import load_shm_split_clients as loader
                except ImportError:
                    from .cnn_v10_ps_shm_clients import load_shm_split_clients as loader
            else:
                try:
                    from cnn_v10_ps_clients import load_optimized_split_clients as loader
                except ImportError:
                    from .cnn_v10_ps_clients import load_optimized_split_clients as loader
            clients, unused_sha = loader(loaded['model_root'], args.runner,
                loaded['model_manifest'], loaded['model_manifest_sha256'], threads=args.threads)
        active_quantized = _quantized_partitions(args, candidate_evidence)
        if args.capture_suffix_input_dir:
            try:
                from cnn_pipeline_v10_suffix_capture import wrap_suffix_capture_client
            except ImportError:
                from .cnn_pipeline_v10_suffix_capture import wrap_suffix_capture_client
            capture_client = wrap_suffix_capture_client(
                clients['suffix'], args.capture_suffix_input_dir, max_distinct=2)
            clients['suffix'] = capture_client
        # Supplying reference files alone must never weaken a feature-exact
        # transport/conversion comparison.
        validation_references = references if active_quantized else None
        report['active_quantized_partitions'] = active_quantized
        headers = {name: client.header for name, client in clients.items()}
        transport = transport_type(args.device,
            expected_parameter_manifest_words=parameter_words)
        runtime = cls(transport, loaded['parameter_contract'], loaded['manifest_sha256'],
                      clients, timeout_s=args.timeout_s, **mixin_kwargs)
        report.update(setup_ms=(time.perf_counter()-started)*1000,
                      ort_headers=headers, candidate_evidence=candidate_evidence)
        report['warmup'] = measure_live_phase(runtime, tensors, args.expected_feature_sha256,
            args.warmup_pairs, 100000, args.max_in_flight, validation_references,
            args.min_feature_cosine, args.max_feature_relative_l2, output/'warmup-features.f32',
            output/'warmup-live.jsonl' if args.deliver_jsonl else None, args.delivery_queue_capacity)
        report['owned_process_memory_before'] = _memory(clients)
        report['measured'] = measure_live_phase(runtime, tensors, args.expected_feature_sha256,
            args.measured_pairs, 200000, args.max_in_flight, validation_references,
            args.min_feature_cosine, args.max_feature_relative_l2, output/'measured-features.f32',
            output/'measured-live.jsonl' if args.deliver_jsonl else None, args.delivery_queue_capacity)
        report['owned_process_memory_after'] = _memory(clients)
        report['status'] = ('FEATURE_EXACT_PROTOCOL_CLEAN' if validation_references is None
                            else 'ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN')
    except BaseException as error:
        failure = error
        report['error'] = '%s: %s' % (type(error).__name__, error)
        report['delivery_cleanup_errors'] = getattr(error, 'delivery_cleanup_errors', [])
    finally:
        started = time.perf_counter()
        cleanup_errors = []
        try:
            if runtime is not None:
                cleanup = runtime.close()
            else:
                if transport is not None:
                    cleanup = transport.close()
        except BaseException as error:
            cleanup_errors.append('%s: %s' % (type(error).__name__, error))
            if failure is None:
                failure = error
        if runtime is None:
            for client in (clients or {}).values():
                try:
                    client.close()
                except BaseException as error:
                    cleanup_errors.append('%s: %s' % (type(error).__name__, error))
                    if failure is None:
                        failure = error
        report.update(cleanup=cleanup, cleanup_errors=cleanup_errors,
                      cleanup_ms=(time.perf_counter()-started)*1000)
    if failure is None and not all((cleanup or {}).get(key) for key in
            ('transport_closed', 'clients_closed', 'all_handles_freed', 'quiesce_confirmed')):
        failure = RuntimeError('incomplete runtime cleanup')
        report['error'] = str(failure)
    try:
        report['runner_sha256_after'] = _sha(pathlib.Path(args.runner).read_bytes())
        if report['runner_sha256_after'] != runner_sha_before:
            raise RuntimeError('runner changed during benchmark')
    except BaseException as error:
        report['runner_identity_error'] = '%s: %s' % (type(error).__name__, error)
        if failure is None:
            failure = error
    if failure is not None:
        report['status'] = 'FAILED'
    if capture_client is not None:
        try:
            report['suffix_input_capture'] = capture_client.capture_summary()
        except BaseException as error:
            report['capture_summary_error'] = '%s: %s' % (type(error).__name__, error)
            report['status'] = 'FAILED'
            if failure is None:
                failure = error
    report['performance_valid'] = failure is None and not bool(args.capture_suffix_input_dir)
    report['performance_invalid_reason'] = (
        'diagnostic suffix input capture includes hashing and file writes'
        if args.capture_suffix_input_dir else ('failed validation' if failure is not None else None))
    for phase in ('warmup', 'measured'):
        if phase in report:
            report[phase]['performance_valid'] = report['performance_valid']
    report.update(release_manifest_sha256=loaded['manifest_sha256'],
        deployment_manifest_sha256=deployment['manifest_sha256'],
        kernel_clock_hz=deployment['clock_hz'],
        cpu_frequency_khz_before=cpu_before, cpu_frequency_khz_after=_cpu_frequency_khz(),
        ort_partition_allow_spinning=os.environ.get('ORT_PARTITION_ALLOW_SPINNING', 'unset'),
        ort_partition_prealloc_outputs=os.environ.get('ORT_PARTITION_PREALLOC_OUTPUTS', 'unset'),
        scope='Resident engineering tensors; includes fill/drain and result collection, plus JSONL serialization/flush/drain when deliver_jsonl=true; excludes setup, input loading and feature validation; not recognition accuracy or camera-to-display FPS')
    raw = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n').encode('utf-8')
    (output/'result.json').write_bytes(raw)
    print(json.dumps(dict(status=report['status'], result_sha256=_sha(raw),
        fps=(report.get('measured', {}).get('fps_including_fill_and_drain')
             if report['performance_valid'] else None))))
    if failure is not None:
        raise RuntimeError('candidate benchmark failed; evidence saved in %s' % output) from failure
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
