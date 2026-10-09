import hashlib
import importlib.util
import pathlib
import sys
import json
import copy
import tempfile
import threading
import unittest
from types import SimpleNamespace
from types import ModuleType
from unittest import mock
from contextlib import contextmanager

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
from cnn_pipeline_v10_live_runtime import V10LiveRuntime
from test_cnn_pipeline_v10_paired_runtime import (
    FakeTransport, MANIFEST_SHA, clients, contract, image)
if importlib.util.find_spec('benchmark_cnn_pipeline_v10_live') is not None:
    import benchmark_cnn_pipeline_v10_live as benchmark
else:
    import benchmark_cnn_pipeline_v10_stream as benchmark


def sha(array):
    return hashlib.sha256(np.asarray(array, dtype='<f4').tobytes()).hexdigest()


class BenchmarkTests(unittest.TestCase):
    def test_chain_protocol_checks_every_job_and_exact_profile_order(self):
        event = {'profiles': [2, 3, 0], 'jobs': [
            {'profile': p, 'completion': {'protocol_error': 0, 'guard_error_flags': 0}}
            for p in (2, 3, 0)]}
        benchmark._check_pl_event(event)
        event['jobs'][1]['completion']['guard_error_flags'] = 1
        with self.assertRaisesRegex(RuntimeError, 'guard'):
            benchmark._check_pl_event(event)
        event['jobs'][1]['completion']['guard_error_flags'] = 0
        event['jobs'][1]['profile'] = 0
        with self.assertRaisesRegex(RuntimeError, 'chain'):
            benchmark._check_pl_event(event)

    def test_pl_n1_identity_is_distinct_from_ps_native_n1(self):
        args = SimpleNamespace(ps_client='mixed', n1_manifest=None,
                               suffix_candidate=None, pl_chain_manifest='chain.json')
        self.assertEqual(benchmark._quantized_partitions(args,
            {'active_quantized_partitions': ['n1_pl']}), ['n1_pl'])
        for names in ([], ['n1'], ['n1_pl', 'n1_pl']):
            with self.assertRaises(ValueError):
                benchmark._quantized_partitions(args, {'active_quantized_partitions': names})

    def test_chain_cli_uses_new_transport_combined_identity_and_engineering_gate(self):
        self._check_chain_cli(capture=False)

    def test_chain_capture_is_diagnostic_and_delegates_real_runtime(self):
        self._check_chain_cli(capture=True)

    def test_a0004_cli_uses_real_mro_and_direct_target_at_both_boundaries(self):
        self._check_chain_cli(capture=False, a0004=True)

    def test_a0004_capture_uses_same_runtime_without_claiming_performance(self):
        self._check_chain_cli(capture=True, a0004=True)

    def test_a0004_split_ps_uses_real_mro_and_union_overlap(self):
        self._check_chain_cli(capture=False, a0004=True, split=True)

    def test_a0004_split_capture_remains_diagnostic(self):
        self._check_chain_cli(capture=True, a0004=True, split=True)

    def test_a0004_split_thread_budget_reaches_clients_and_report(self):
        self._check_chain_cli(capture=False, a0004=True, split=True, split_threads=(2, 3))

    def test_a0005_cli_binds_signed40_admission_and_direct_target(self):
        self._check_chain_cli(capture=False, a0005=True)

    def test_a0005_split_ps_keeps_signed40_transport_contract(self):
        self._check_chain_cli(capture=False, a0005=True, split=True,
                              split_threads=(1, 3))

    def test_split_ps_rejects_legacy_runtime_before_loading(self):
        args = ['--bundle-root', 'missing', '--expected-bundle-sha256', MANIFEST_SHA,
                '--deployment-manifest', 'missing', '--expected-deployment-sha256', MANIFEST_SHA,
                '--runner', 'missing', '--output-dir', 'missing', '--ps-schedule', 'split',
                '--input-tensor', 'a', '--input-tensor', 'b',
                '--expected-feature-sha256', MANIFEST_SHA, '--expected-feature-sha256', MANIFEST_SHA]
        with mock.patch.object(benchmark, 'load_v10_release_bundle') as loader:
            with self.assertRaises(SystemExit):
                benchmark.main(args)
            loader.assert_not_called()

    def _check_chain_cli(self, capture, a0004=False, a0005=False,
                         split=False, split_threads=None):
        self.assertFalse(a0004 and a0005)
        if a0005:
            from cnn_pipeline_v10_signed40_parameters import (
                CHAIN_CONTRACT, load_v10_signed40_parameters as real_parameter_loader)
            from cnn_pipeline_v10_signed40_runtime import V10Signed40ChainMixin as P3Mixin
            from test_cnn_pipeline_v10_p3_dma_runtime import A0004ChainTransport as BaseTransport
        elif a0004:
            from cnn_pipeline_v10_p3_dma_parameters import (
                CHAIN_CONTRACT, load_v10_p3_dma_parameters as real_parameter_loader)
            from cnn_pipeline_v10_p3_dma_runtime import V10P3DmaChainMixin as P3Mixin
            from test_cnn_pipeline_v10_p3_dma_runtime import A0004ChainTransport as BaseTransport
        else:
            from cnn_pipeline_v10_chain_deployment import CHAIN_CONTRACT
            from cnn_pipeline_v10_p3_chain_parameters import load_v10_p3_parameters as real_parameter_loader
            from cnn_pipeline_v10_p3_runtime import V10P3ChainMixin as P3Mixin
            BaseTransport = FakeTransport
        from cnn_pipeline_v10_mixed_runtime import V10MixedBoundaryMixin as MixedMixin
        from cnn_pipeline_v10_suffix_capture import wrap_suffix_capture_client
        if a0005:
            deployment_module = 'cnn_pipeline_v10_signed40_deployment'
            runtime_module = 'cnn_pipeline_v10_signed40_runtime'
            parameter_module = 'cnn_pipeline_v10_signed40_parameters'
            transport_module = 'cnn_ddr_v10_signed40_candidate_runtime'
            device = '/dev/network10_v10_signed40'
        else:
            deployment_module = ('cnn_pipeline_v10_p3_dma_deployment' if a0004
                                 else 'cnn_pipeline_v10_chain_deployment')
            runtime_module = 'cnn_pipeline_v10_p3_dma_runtime' if a0004 else 'cnn_pipeline_v10_p3_runtime'
            parameter_module = 'cnn_pipeline_v10_p3_dma_parameters' if a0004 else runtime_module
            transport_module = 'cnn_ddr_v10_p3_dma_runtime' if a0004 else 'cnn_ddr_v10_p3_runtime'
            device = '/dev/network10_v10_p3_dma' if a0004 else '/dev/network10_v10_p3'
        combined_sha = '2' * 64
        words = (int('22222222', 16),) * 8
        parameters = dict(manifest_sha256=combined_sha, parameter_manifest_words=words,
                          p3_manifest_sha256='3'*64, evidence={'test_fixture': True},
                          contract=copy.deepcopy(CHAIN_CONTRACT),
                          chain_manifest_sha256=combined_sha, params=bytes(11280*16))
        signed40_admission = object()
        if a0005:
            parameters['pw2_signed40_admission'] = signed40_admission
        class Transport(BaseTransport):
            def submit(self, profile, blocks, params, arena_a, arena_b):
                if profile != 3:
                    return super(Transport, self).submit(profile, blocks, params, arena_a, arena_b)
                # Uniform marker fixtures keep their marker after the mock
                # downsample/channel expansion; the real MRO owns all jobs,
                # conversion, shared arenas and parameter residency.
                assert blocks == 1 and self.pending is None and arena_a != arena_b
                self.submits.append(dict(profile=3, blocks=1, params=params,
                                         arena_a=arena_a, arena_b=arena_b))
                self.pending = 3
                return {'profile': 3, 'blocks': 1}
            def wait_complete(self, profile, timeout_s):
                value = super(Transport, self).wait_complete(profile, timeout_s)
                value['guard_error_flags'] = 0
                return value
        owned = clients()
        for value in owned.values():
            value.header = {'test_fixture': True}
        modules = {name: ModuleType(name) for name in (
            deployment_module, runtime_module, parameter_module,
            transport_module, 'cnn_pipeline_v10_mixed_runtime',
            'cnn_pipeline_v10_suffix_capture')}
        original_suffix = owned['suffix']
        wrapper = mock.Mock(wraps=wrap_suffix_capture_client)
        modules['cnn_pipeline_v10_suffix_capture'].wrap_suffix_capture_client = wrapper
        deployment = dict(manifest={'target': {'device': device},
                                   'chain_contract': copy.deepcopy(CHAIN_CONTRACT)},
                          manifest_sha256=MANIFEST_SHA, clock_hz=196415985,
                          pw_local_clock_hz=(399999996 if a0005 else None),
                          files={'signed40_admission': 'admission.json',
                                 'signed40_range_proof': 'proof.json'})
        deployment_loader_name = ('load_v10_signed40_deployment' if a0005 else
            ('load_v10_p3_dma_deployment' if a0004 else 'load_v10_chain_deployment'))
        setattr(modules[deployment_module], deployment_loader_name,
                mock.Mock(return_value=deployment))
        if a0005:
            modules[deployment_module].ADMISSION_SHA256 = '4' * 64
            modules[deployment_module].PROOF_SHA256 = '5' * 64
        modules[deployment_module].CHAIN_CONTRACT = CHAIN_CONTRACT
        runtime_mixin_name = ('V10Signed40ChainMixin' if a0005 else
            ('V10P3DmaChainMixin' if a0004 else 'V10P3ChainMixin'))
        setattr(modules[runtime_module], runtime_mixin_name, P3Mixin)
        parameter_loader_name = ('load_v10_signed40_parameters' if a0005 else
            ('load_v10_p3_dma_parameters' if a0004 else 'load_v10_p3_parameters'))
        setattr(modules[parameter_module], parameter_loader_name,
                mock.create_autospec(real_parameter_loader, return_value=parameters))
        fake_transport = Transport()
        new_transport = mock.Mock(return_value=fake_transport)
        transport_name = ('LinuxIoctlV10Signed40CandidateTransport' if a0005 else
            ('LinuxIoctlV10P3DmaTransport' if a0004 else 'LinuxIoctlV10P3Transport'))
        setattr(modules[transport_module], transport_name, new_transport)
        modules['cnn_pipeline_v10_mixed_runtime'].V10MixedBoundaryMixin = MixedMixin
        modules['cnn_pipeline_v10_mixed_runtime'].build_v10_mixed_components = mock.Mock(
            return_value=(owned, MANIFEST_SHA, {}, {'active_quantized_partitions': []}))
        loaded = dict(model_root='models', model_manifest='models.json',
                      model_manifest_sha256=MANIFEST_SHA, manifest_sha256=MANIFEST_SHA,
                      parameter_manifest_words=['old identity must not be used'],
                      parameter_contract=contract())
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            runner = root/'runner'
            runner.write_bytes(b'test runner')
            args = ['--bundle-root', 'bundle', '--expected-bundle-sha256', MANIFEST_SHA,
                    '--deployment-manifest', 'new-deployment', '--expected-deployment-sha256', MANIFEST_SHA,
                    '--runner', str(runner), '--ps-client', 'mixed', '--measured-pairs', '10',
                    '--device', device, '--output-dir', str(root/'output'),
                    '--pl-chain-manifest', 'combined.json',
                    '--expected-pl-chain-manifest-sha256', combined_sha]
            if a0004 or a0005:
                args += ['--pl-chain-runtime', 'a0005' if a0005 else 'a0004']
            if split:
                args += ['--ps-schedule', 'split']
            if split_threads is not None:
                args += ['--ps-front-threads', str(split_threads[0]),
                         '--ps-suffix-threads', str(split_threads[1])]
            if capture:
                args += ['--capture-suffix-input-dir', str(root/'captured')]
            for i in range(2):
                input_path, ref_path = root/('in%d' % i), root/('ref%d' % i)
                image(i+1).tofile(input_path)
                reference = np.full(512, i+1, dtype='<f4')
                reference.tofile(ref_path)
                args += ['--input-tensor', str(input_path), '--reference-feature', str(ref_path),
                         '--expected-feature-sha256', sha(reference)]
            with mock.patch.dict(sys.modules, modules), \
                    mock.patch.object(benchmark, 'load_v10_release_bundle', return_value=loaded), \
                    mock.patch.object(benchmark, 'load_v10_platform_deployment') as old_loader, \
                    mock.patch.object(benchmark, 'LinuxIoctlV10Transport') as old_transport, \
                    mock.patch.object(benchmark, '_cpu_frequency_khz', return_value={}):
                parameters['contract']['arena_words'] = 69696
                with self.assertRaisesRegex(ValueError, 'contracts differ'):
                    benchmark.main(args)
                new_transport.assert_not_called()
                self.assertFalse((root/'output').exists())
                parameters['contract'] = copy.deepcopy(CHAIN_CONTRACT)
                benchmark.main(args)
                old_loader.assert_not_called()
                old_transport.assert_not_called()
            expected_transport_kwargs = dict(expected_parameter_manifest_words=words)
            if a0005:
                expected_transport_kwargs['pw2_signed40_admission'] = signed40_admission
            new_transport.assert_called_once_with(device, **expected_transport_kwargs)
            report = json.loads((root/'output'/'result.json').read_text())
            self.assertEqual(report['ps_schedule'], 'split' if split else 'single')
            builder = modules['cnn_pipeline_v10_mixed_runtime'].build_v10_mixed_components
            if split:
                front_threads, suffix_threads = split_threads or (1, 2)
                expected_threads = {'stem-prefix': front_threads, 'network1-bridge': 1,
                                    'network3-bridge': front_threads, 'suffix': suffix_threads}
                self.assertEqual(builder.call_args[1]['partition_threads'], expected_threads)
                self.assertEqual(report['partition_threads'], expected_threads)
                self.assertIsNone(report['ort_threads'])
                measured = report['measured']
                self.assertEqual(measured['overlap'], measured['runtime_summary']['overlap'])
                self.assertGreater(measured['overlap']['ps_front_busy_ms'], 0)
                self.assertGreater(measured['overlap']['ps_suffix_busy_ms'], 0)
            else:
                self.assertNotIn('partition_threads', builder.call_args[1])
                self.assertEqual(report['ort_threads'], 3)
            self.assertEqual(report['active_quantized_partitions'], ['n1_pl'])
            self.assertEqual(report['status'], 'ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN')
            self.assertEqual(report['pl_chain_manifest_sha256'], combined_sha)
            if a0004 or a0005:
                self.assertEqual(report['pl_chain_runtime'],
                                 'a0005' if a0005 else 'a0004')
                self.assertEqual(report['activation_upload_backend'], 'direct_wc')
                self.assertEqual(report['kernel_clock_hz'], 196415985)
                self.assertEqual(report['pw_local_clock_hz'],
                                 399999996 if a0005 else None)
                self.assertEqual(len(fake_transport.direct_quantize_calls), 13 * 4)
                self.assertEqual(fake_transport.legacy_array_uploads, [])
                for pair in report['measured']['runtime_summary']['pair_timings']:
                    self.assertEqual([p for event in pair['pl_events']
                                      for p in event.get('profiles', [event.get('profile')])],
                                     [2, 3, 0, 1])
                    for event, name in zip(pair['pl_events'],
                                           ('profile2_input_upload', 'quantize_upload')):
                        self.assertTrue(event['timing'][name]['direct_target'])
                        self.assertEqual(event['timing'][name]['backend'], 'wc_mmap_direct_quantize')
            self.assertEqual(owned['network1-bridge'].calls, 0)
            self.assertTrue(report['cleanup']['clients_closed'])
            self.assertEqual(report['performance_valid'], not capture)
            self.assertEqual(report['measured']['performance_valid'], not capture)
            if capture:
                wrapper.assert_called_once_with(original_suffix, str(root/'captured'), max_distinct=2)
                captured = report['suffix_input_capture']
                self.assertEqual(captured['status'], 'CAPTURE_COMPLETE')
                self.assertEqual(captured['distinct_count'], 2)
                self.assertEqual(captured['infer_calls'], 26)
                self.assertEqual([r['first_infer_call'] for r in captured['records']], [0, 1])
                for index, record in enumerate(captured['records']):
                    value = np.fromfile(root/'captured'/record['path'], dtype='<f4')
                    self.assertTrue(np.all(value == index+1))
            else:
                wrapper.assert_not_called()

    def test_delivery_cleanup_failure_preserves_primary_inference_error(self):
        primary = ValueError('primary inference failure')
        release = threading.Event()
        class BrokenRuntime(object):
            @contextmanager
            def iter_results(self, *args, **kwargs):
                def results():
                    yield dict(frame_id=1, features=np.ones(512))
                    release.set()
                    raise primary
                yield results()
        def fail_sink(*args, **kwargs):
            self.assertTrue(release.wait(2))
            raise TypeError('sink failure')
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(benchmark.json, 'dumps', side_effect=fail_sink):
                with self.assertRaisesRegex(ValueError, 'primary inference failure') as captured:
                    benchmark.measure_live_phase(BrokenRuntime(), [], [], 1, 0, 1,
                        delivery_path=pathlib.Path(folder)/'result.jsonl')
            self.assertIs(captured.exception, primary)
            self.assertTrue(any('delivery failed' in text for text in primary.delivery_cleanup_errors))

    def test_cli_exact_reference_device_and_runner_identity_gates(self):
        class Transport(FakeTransport):
            def wait_complete(self, profile, timeout_s):
                result = super(Transport, self).wait_complete(profile, timeout_s)
                result['guard_error_flags'] = 0
                return result
        loaded = dict(model_root='models', model_manifest='models.json',
                      model_manifest_sha256=MANIFEST_SHA, manifest_sha256=MANIFEST_SHA,
                      parameter_manifest_words=[], parameter_contract=contract())
        deployment = dict(manifest={'target': {'device': '/dev/network10_v10'}},
                          manifest_sha256=MANIFEST_SHA, clock_hz=196415985)
        for scenario in ('reference_does_not_weaken_exact', 'runner_changes', 'device_mismatch'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as folder:
                root = pathlib.Path(folder)
                runner = root/'runner'
                runner.write_bytes(b'initial runner')
                output = root/'result'
                args = ['--bundle-root', 'bundle', '--expected-bundle-sha256', MANIFEST_SHA,
                        '--deployment-manifest', 'deployment', '--expected-deployment-sha256', MANIFEST_SHA,
                        '--runner', str(runner), '--ps-client', 'shm', '--measured-pairs', '10',
                        '--output-dir', str(output)]
                for index in range(2):
                    tensor_path, ref_path = root/('input%d' % index), root/('ref%d' % index)
                    image(index+1).tofile(tensor_path)
                    reference = np.full(512, (index+1)*(1.001 if scenario == 'reference_does_not_weaken_exact' else 1), dtype='<f4')
                    reference.tofile(ref_path)
                    args += ['--input-tensor', str(tensor_path), '--expected-feature-sha256', sha(reference),
                             '--reference-feature', str(ref_path)]
                if scenario == 'device_mismatch':
                    args += ['--device', '/dev/wrong']
                owned = clients()
                for client in owned.values():
                    client.header = {'test_fake': True}
                if scenario == 'runner_changes':
                    old_infer = owned['suffix'].infer
                    def infer(tensors):
                        runner.write_bytes(b'changed runner')
                        return old_infer(tensors)
                    owned['suffix'].infer = infer
                loader_module = ModuleType('cnn_v10_ps_shm_clients')
                loader_module.load_shm_split_clients = mock.Mock(return_value=(owned, MANIFEST_SHA))
                with mock.patch.dict(sys.modules, {'cnn_v10_ps_shm_clients': loader_module}), \
                        mock.patch.object(benchmark, 'load_v10_release_bundle', return_value=loaded), \
                        mock.patch.object(benchmark, 'load_v10_platform_deployment', return_value=deployment), \
                        mock.patch.object(benchmark, 'LinuxIoctlV10Transport', return_value=Transport()) as transport, \
                        mock.patch.object(benchmark, '_cpu_frequency_khz', return_value={}):
                    with self.assertRaises((ValueError, RuntimeError)):
                        benchmark.main(args)
                    if scenario == 'device_mismatch':
                        transport.assert_not_called()
                        loader_module.load_shm_split_clients.assert_not_called()
                        self.assertFalse(output.exists())
                    else:
                        report = json.loads((output/'result.json').read_text())
                        self.assertEqual(report['status'], 'FAILED')
                        self.assertTrue(report['cleanup']['clients_closed'])
                        self.assertEqual(report['device'], '/dev/network10_v10')
                        if scenario == 'runner_changes':
                            self.assertIn('runner changed', report['runner_identity_error'])
                        else:
                            self.assertIn('SHA mismatch', report['error'])

    def test_tolerance_gate_requires_loaded_candidate_identity(self):
        for backend in ('optimized', 'shm', 'mixed'):
            args = SimpleNamespace(ps_client=backend, n1_manifest=None,
                                   suffix_candidate=None, reference_feature=['a', 'b'])
            self.assertEqual(benchmark._quantized_partitions(args, {}), [])
        args.n1_manifest = 'n1.json'
        with self.assertRaisesRegex(ValueError, 'identity'):
            benchmark._quantized_partitions(args, {})
        self.assertEqual(benchmark._quantized_partitions(args,
            {'active_quantized_partitions': ['n1']}), ['n1'])
        args.suffix_candidate = 'suffix.json'
        self.assertEqual(benchmark._quantized_partitions(args,
            {'active_quantized_partitions': ['suffix', 'n1']}), ['n1', 'suffix'])
        for actual in (['n1'], ['n1', 'suffix', 'n1'], None, [1]):
            with self.assertRaises(ValueError):
                benchmark._quantized_partitions(args, {'active_quantized_partitions': actual})
        args.ps_client = 'shm'
        with self.assertRaisesRegex(ValueError, 'mixed'):
            benchmark._quantized_partitions(args,
                {'active_quantized_partitions': ['n1', 'suffix']})

    def test_explicit_exact_and_quantized_feature_gates(self):
        compare = getattr(benchmark, 'compare_feature', None)
        self.assertTrue(callable(compare), 'candidate feature comparator missing')
        reference = np.linspace(-1, 1, 512, dtype=np.float32)
        exact = compare(reference, sha(reference))
        self.assertTrue(exact['exact'])
        with self.assertRaisesRegex(ValueError, 'SHA'):
            compare(reference * 1.001, sha(reference))
        quantized = compare(reference * 1.001, sha(reference), reference)
        self.assertFalse(quantized['exact'])
        self.assertGreater(quantized['cosine'], .999)
        self.assertLess(quantized['relative_l2'], .05)
        with self.assertRaisesRegex(ValueError, 'regression'):
            compare(-reference, sha(reference), reference)
        with self.assertRaisesRegex(ValueError, 'regression'):
            compare(reference * 2, sha(reference), reference)

    def test_invalid_reference_and_nonfinite_are_rejected(self):
        reference = np.ones(512, dtype=np.float32)
        with self.assertRaises(ValueError):
            benchmark.compare_feature(reference, '0' * 64, reference)
        with self.assertRaises(ValueError):
            benchmark.compare_feature(np.full(512, np.nan), sha(reference), reference)
        with self.assertRaises(ValueError):
            benchmark.compare_feature(reference[:2], sha(reference), reference)

    def test_zero_reference_has_defined_error_metric(self):
        reference = np.zeros(512, dtype=np.float32)
        result = benchmark.compare_feature(reference, sha(reference), reference)
        self.assertEqual(result['cosine'], 1.0)
        self.assertEqual(result['relative_l2'], 0.0)
        with self.assertRaises(ValueError):
            benchmark.compare_feature(np.ones(512), sha(reference), reference)

    def test_live_measurement_reports_delivery_and_validates_after_iteration(self):
        class Transport(FakeTransport):
            def wait_complete(self, profile, timeout_s):
                result = super(Transport, self).wait_complete(profile, timeout_s)
                result['guard_error_flags'] = 0
                return result
        instance = V10LiveRuntime(Transport(), contract(), MANIFEST_SHA, clients())
        references = [np.ones(512, dtype=np.float32), np.full(512, 2, dtype=np.float32)]
        try:
            result = benchmark.measure_live_phase(instance, [image(1), image(2)],
                [sha(x) for x in references], 4, 100, 2)
            self.assertEqual(result['real_frames'], 8)
            self.assertTrue(result['feature_protocol_pass'])
            self.assertLess(result['first_result_ms'], result['execution_ms'])
            self.assertEqual(len(result['deliveries']), 8)
            self.assertTrue(all(r['completion_to_delivery_ms'] >= 0 for r in result['deliveries']))
            self.assertEqual(result['validation_mode'], 'exact')
            with tempfile.TemporaryDirectory() as folder:
                path = pathlib.Path(folder)/'results.jsonl'
                delivered = benchmark.measure_live_phase(instance, [image(1), image(2)],
                    [sha(x) for x in references], 4, 200, 2,
                    delivery_path=path, delivery_capacity=2)
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual([row['frame_id'] for row in rows], list(range(200, 208)))
                self.assertEqual(delivered['result_delivery']['summary']['delivered'], 8)
                self.assertEqual(delivered['result_delivery']['summary']['status'], 'DRAINED')
                self.assertLess(delivered['result_delivery']['first_flushed_ms'], delivered['execution_ms'])
                self.assertTrue(all(len(row['features']) == 512 for row in rows))
        finally:
            instance.close()


if __name__ == '__main__':
    unittest.main()
