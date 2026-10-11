"""Synthetic checker fixtures only. No hardware/simulation success is asserted."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qualification', ROOT / 'scripts/qualification_report.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class SyntheticAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate = self.root / 'candidate'
        self.platform = self.root / 'platform'
        self.project = self.root / 'project'
        for p in (self.candidate, self.platform, self.project, self.root / 'rtl', self.root / 'reports'):
            p.mkdir(parents=True, exist_ok=True)
        self.write(self.root / 'reports/baseline.json', q.load(ROOT / 'reports/baseline.json'))
        manifest = []
        sums = []
        for name in ('cnn_pw_mac.sv', 'cnn_dsp_primitives.v'):
            current = self.root / 'rtl' / name
            current.write_text('// SYNTHETIC checker fixture, not executable RTL\n')
            frozen = self.candidate / 'rtl' / name
            frozen.parent.mkdir(exist_ok=True)
            frozen.write_bytes(current.read_bytes())
            project_copy = self.project / 'source_snapshot/rtl' / name
            project_copy.parent.mkdir(parents=True, exist_ok=True)
            project_copy.write_bytes(current.read_bytes())
            if name != 'cnn_dsp_primitives.v':
                manifest.append(dict(original=str(current), snapshot=str(frozen), sha256=q.digest(current)))
            sums.append(q.digest(current) + '  rtl/' + name)
        self.write(self.candidate / 'source_manifest.json', manifest)
        (self.candidate / 'compile.log').write_text('\n'.join('INFO: Analyzing SystemVerilog file "' + e['snapshot'] + '" into library work' for e in manifest))
        compiled = self.candidate / 'simulation_snapshot/xsim.dir/synthetic.bin'
        compiled.parent.mkdir(parents=True)
        compiled.write_text('SYNTHETIC compiled snapshot test only')
        self.write(self.candidate / 'simulation_snapshot/binary_manifest.json', [dict(path=str(compiled), sha256=q.digest(compiled))])
        sha_file = self.project / 'source_snapshot/SHA256SUMS.txt'
        sha_file.write_text('\n'.join(sums) + '\n')
        proof = dict(run_id='synthetic-not-a-real-proof', pass_=True)
        proof.pop('pass_')
        proof.update({'pass': True, 'production_source_changed': False, 'controller_fifo_source_identical': True,
                      'commands': [{'exit_code': 0}], 'result': {'accepted_tiles': 1024, 'lane_results': 4096,
                      'compared_job_clock_cycles': 3413, 'every_cycle_valid_ready_and_valid_data': True}})
        proof_path = self.candidate / 'fast_proof/receipt.json'
        self.write(proof_path, proof)
        copies = []
        for n in range(10):
            p = self.candidate / f'proof_copy{n}.txt'
            p.write_text('SYNTHETIC test only')
            copies.append(dict(role=f'synthetic{n}', path=str(p), sha256=q.digest(p)))
        self.write(self.candidate / 'fast_proof_binding.json', dict(
            **{'pass': True}, candidate_source_matches=True, all_current_input_generated_log_hashes_checked=True,
            proof_receipt_sha256=q.digest(proof_path), proof_run_id=proof['run_id'], copies=copies,
            production_mac_sha256=q.digest(self.root / 'rtl/cnn_pw_mac.sv'),
            real_primitives_sha256=q.digest(self.root / 'rtl/cnn_dsp_primitives.v')))
        self.write(self.candidate / 'fixture_binding.json', dict(**{'pass': True}, identity='A0004',
            entries=[dict(snapshot=str(self.candidate / 'proof_copy0.txt'), sha256=q.digest(self.candidate / 'proof_copy0.txt')) for _ in range(20)]))
        baseline = q.load(self.root / 'reports/baseline.json')
        for row in baseline['baseline_cycles_from_historical_receipt']:
            p, b, c = row['profile'], row['blocks'], row['a0005_cycles']
            log = self.candidate / f'p{p}.log'
            log.write_text(f'FULL_PASS profile={p} blocks={b} cycles={c}\nCYCLE_GATE profile={p} target={c} pass=1\nFULL_FUNCTIONAL_SUITE_PASS\nFULL_SUITE_PASS\n')
            self.write(self.candidate / f'p{p}_r1_result.json', dict(functional_pass=True, performance_pass=True,
                profiles=[dict(profile=p, blocks=b, cycles=c)], token=[1, 2, 32], bdelay=3,
                source_manifest_sha256=q.digest(self.candidate / 'source_manifest.json'),
                fast_proof_binding_sha256=q.digest(self.candidate / 'fast_proof_binding.json'),
                fixture_binding_sha256=q.digest(self.candidate / 'fixture_binding.json'), log_sha256=q.digest(log)))
            obj = q.load(self.candidate / f'p{p}_r1_result.json')
            obj['compiled_snapshot_manifest_sha256'] = q.digest(self.candidate / 'simulation_snapshot/binary_manifest.json')
            obj['compile_log_sha256'] = q.digest(self.candidate / 'compile.log')
            self.write(self.candidate / f'p{p}_r1_result.json', obj)
        mixed_rows = []
        mixed_text = ''
        for p in (3, 2, 3):
            row = next(r for r in baseline['baseline_cycles_from_historical_receipt'] if r['profile'] == p)
            b, c = row['blocks'], row['a0005_cycles']
            mixed_rows.append(dict(profile=p, blocks=b, cycles=c))
            mixed_text += f'FULL_PASS profile={p} blocks={b} cycles={c}\nCYCLE_GATE profile={p} target={c} pass=1\n'
        mixed_text += 'MIXED_SEQUENCE_VERIFIED actual_sequence=3,2,3\nFULL_FUNCTIONAL_SUITE_PASS\nFULL_SUITE_PASS\n'
        mixed_log = self.candidate / 'mixed.log'
        mixed_log.write_text(mixed_text)
        mixed = q.load(self.candidate / 'p3_r1_result.json')
        mixed.update(mixed_sequence_verified=True, actual_sequence=[3, 2, 3], profiles=mixed_rows, log_sha256=q.digest(mixed_log))
        self.write(self.candidate / 'mixed_3_2_3_result.json', mixed)
        text = '| CLB LUTs* | 10 |\n| CLB Registers | 20 |\n| Block RAM Tile | 2 |\n| DSPs | 4 |\n'
        artifacts = []
        for role in ('route_dcp', 'utilization', 'timing_summary', 'route_status', 'check_timing', 'cdc', 'drc',
                     'clocks', 'timing_slow_slow', 'timing_slow_fast', 'timing_fast_slow', 'timing_fast_fast', 'signoff', 'exception_review'):
            path = self.platform / (role + '.txt')
            content = {'utilization': text, 'timing_summary': 'WNS(ns) table\n --------\n 0.1 0 0 1 0.1 0 0 1 0.1 0\n',
                       'route_status': '# of unrouted nets.... : 0 :\n# of nets with routing errors.... : 0 :\n',
                       'signoff': 'PASS: routed setup/hold/pulse',
                       'check_timing': '\n'.join(f'{n}. checking synthetic (0)' for n in range(12)),
                       'cdc': 'All paths are Safely Timed.',
                       'drc': 'Report DRC\nDesign State : Fully Routed\nRuledeck: default\nMax checks: <unlimited>\nChecks found: 0\n',
                       'clocks': 'input 10.000 {0.000 5.000} P {design/PS8_i/PLCLK[0]}\njob 5.000 {0.000 2.500} P,G,A {design/driver_job_bufgce_div/O}\npw 2.500 {0.000 1.250} P,G,A {design/pw_local_bufgce_div/O}\nGenerated Clock : pw\nMaster Clock : input\nMultiply By : 4\nGenerated Clock : job\nMaster Clock : pw\nDivide By : 2\n',
                       'exception_review': 'allowed_standard_IP_reset_exceptions=3; unapproved_data_or_clock_exceptions=0'}.get(role, 'Slack (MET) : 0.1ns\nSlack (MET) : 0.1ns\nSYNTHETIC fixture only')
            path.write_text(content)
            if role.startswith('timing_') and role != 'timing_summary':
                from_mode, to_mode = role.removeprefix('timing_').split('_')
                a, b = ('job' if from_mode == 'slow' else 'pw'), ('job' if to_mode == 'slow' else 'pw')
                ap, bp = (5 if a == 'job' else 2.5), (5 if b == 'job' else 2.5)
                path.write_text((f'Slack (MET) : 0.1ns\nSource: cell\n (clocked by {a} {{period={ap:.3f}ns}})\nDestination: cell\n (clocked by {b} {{period={bp:.3f}ns}})\n') * 2)
            artifacts.append(dict(role=role, path=str(path), sha256=q.digest(path)))
        self.write(self.platform / 'route_receipt.json', dict(status='ROUTED_SIGNOFF_PASS', stage='post_route',
            part=baseline['baseline_part_from_routed_report'], source_snapshot_sha256=q.digest(sha_file),
            resources=q.memory_resources(text), timing=q.timing_values((self.platform / 'timing_summary.txt').read_text()),
            checks={k: True for k in ('check_timing', 'cdc', 'drc', 'related_clocks', 'exceptions')},
            counts=dict(check_timing_categories=12, check_timing_issues=0, drc_errors=0, drc_critical_warnings=0, cdc_unsafe_paths=0, debug_cores=0, unconstrained_internal_endpoints=0, unapproved_exceptions=0, allowed_reset_exceptions=3),
            impl_run=dict(progress='100%', status='route_design Complete!'),
            related_clock_groups={k: dict(setup_ns=.1, hold_ns=.1) for k in ('slow_slow', 'slow_fast', 'fast_slow', 'fast_fast')},
            route=dict(unrouted_nets=0, routing_errors=0), artifacts=artifacts,
            route_dcp_sha256=q.digest(self.platform / 'route_dcp.txt')))

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj))

    def report(self):
        return q.check(self.candidate, self.platform, self.project, self.root)

    def mutate(self, path, field, value):
        obj = q.load(path)
        obj[field] = value
        self.write(path, obj)

    def test_complete_synthetic_fixture(self):
        result = self.report()
        self.assertEqual(result['errors'], [])
        self.assertTrue(result['qualified'])

    def test_incomplete_matrix(self):
        (self.candidate / 'p2_r1_result.json').unlink()
        self.assertFalse(self.report()['qualified'])

    def test_changed_current_rtl(self):
        (self.root / 'rtl/cnn_pw_mac.sv').write_text('mutated')
        self.assertFalse(self.report()['qualified'])

    def test_wrong_ddr(self):
        self.mutate(self.candidate / 'p0_r1_result.json', 'token', [1, 1, 32])
        self.assertFalse(self.report()['qualified'])

    def test_synth_only(self):
        self.mutate(self.platform / 'route_receipt.json', 'stage', 'synthesis')
        self.assertFalse(self.report()['qualified'])

    def test_unbound_log(self):
        (self.candidate / 'p1.log').write_text('FULL_SUITE_PASS')
        self.assertFalse(self.report()['qualified'])

    def test_failed_proof(self):
        self.mutate(self.candidate / 'fast_proof_binding.json', 'pass', False)
        self.assertFalse(self.report()['qualified'])

    def test_missing_route(self):
        (self.platform / 'route_receipt.json').unlink()
        self.assertFalse(self.report()['qualified'])

    def test_every_physical_count_gate(self):
        path = self.platform / 'route_receipt.json'
        original = q.load(path)
        for key in ('check_timing_issues', 'drc_errors', 'drc_critical_warnings', 'cdc_unsafe_paths',
                    'debug_cores', 'unconstrained_internal_endpoints', 'unapproved_exceptions'):
            with self.subTest(key=key):
                changed = json.loads(json.dumps(original))
                changed['counts'][key] = 1
                self.write(path, changed)
                self.assertFalse(self.report()['qualified'])
        self.write(path, original)

    def test_timing_and_progress_gates(self):
        path = self.platform / 'route_receipt.json'
        original = q.load(path)
        for field in ('wns_ns', 'whs_ns', 'wpws_ns', 'tns_ns', 'ths_ns'):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(original))
                changed['timing'][field] = -1
                self.write(path, changed)
                self.assertFalse(self.report()['qualified'])
        for group in original['related_clock_groups']:
            for delay in ('setup_ns', 'hold_ns'):
                changed = json.loads(json.dumps(original))
                changed['related_clock_groups'][group][delay] = -.1
                self.write(path, changed)
                self.assertFalse(self.report()['qualified'])
        changed = json.loads(json.dumps(original))
        changed['impl_run']['progress'] = '99%'
        self.write(path, changed)
        self.assertFalse(self.report()['qualified'])

    def test_unapproved_exception_gate(self):
        path = self.platform / 'route_receipt.json'
        changed = q.load(path)
        changed['counts']['allowed_reset_exceptions'] += 1
        self.write(path, changed)
        self.assertFalse(self.report()['qualified'])

    def test_missing_mixed(self):
        (self.candidate / 'mixed_3_2_3_result.json').unlink()
        self.assertFalse(self.report()['qualified'])

    def test_mixed_wrong_sequence(self):
        self.mutate(self.candidate / 'mixed_3_2_3_result.json', 'actual_sequence', [3, 3, 2])
        self.assertFalse(self.report()['qualified'])

    def test_compiled_snapshot_changed(self):
        (self.candidate / 'simulation_snapshot/xsim.dir/synthetic.bin').write_text('changed')
        self.assertFalse(self.report()['qualified'])

    def refresh_artifact(self, role):
        path = self.platform / 'route_receipt.json'
        receipt = q.load(path)
        for entry in receipt['artifacts']:
            if entry['role'] == role:
                entry['sha256'] = q.digest(entry['path'])
        self.write(path, receipt)

    def test_raw_drc_error_rehashed_zero_receipt_counts(self):
        path = self.platform / 'drc.txt'
        path.write_text(path.read_text() + 'ERROR: [DRC LUTLP-1] Combinatorial Loop Alert\n1 Errors encountered.\n')
        self.refresh_artifact('drc')
        self.assertFalse(self.report()['qualified'])

    def test_raw_clock_slowed_rehashed(self):
        path = self.platform / 'clocks.txt'
        path.write_text(path.read_text().replace('10.000', '100.000').replace('5.000', '50.000').replace('2.500', '25.000'))
        self.refresh_artifact('clocks')
        self.assertFalse(self.report()['qualified'])

    def test_related_path_period_slowed_rehashed(self):
        path = self.platform / 'timing_slow_fast.txt'
        path.write_text(path.read_text().replace('period=5.000ns', 'period=50.000ns').replace('period=2.500ns', 'period=25.000ns'))
        self.refresh_artifact('timing_slow_fast')
        self.assertFalse(self.report()['qualified'])

    def test_extra_project_preflight_omitted_from_simulation(self):
        (self.root / 'rtl/cnn_preflight.sv').write_text('current version A')
        copy = self.project / 'source_snapshot/rtl/cnn_preflight.sv'
        copy.write_text('other version B')
        sums = self.project / 'source_snapshot/SHA256SUMS.txt'
        sums.write_text(sums.read_text() + q.digest(copy) + '  rtl/cnn_preflight.sv\n')
        self.mutate(self.platform / 'route_receipt.json', 'source_snapshot_sha256', q.digest(sums))
        self.assertFalse(self.report()['qualified'])

    def test_compiler_omits_manifest_dut(self):
        (self.candidate / 'compile.log').write_text('Analyzing Verilog file "glbl.v" into library work')
        self.mutate(self.candidate / 'p0_r1_result.json', 'compile_log_sha256', q.digest(self.candidate / 'compile.log'))
        self.assertFalse(self.report()['qualified'])

    def test_generated_clock_contradiction_rehashed(self):
        path = self.platform / 'clocks.txt'
        path.write_text(path.read_text() + 'Generated Clock : job\nMaster Clock : UNRELATED\nDivide By : 7\n')
        self.refresh_artifact('clocks')
        self.assertFalse(self.report()['qualified'])

    def test_generated_clock_wrong_divide_rehashed(self):
        path = self.platform / 'clocks.txt'
        path.write_text(path.read_text().replace('Divide By : 2', 'Divide By : 7'))
        self.refresh_artifact('clocks')
        self.assertFalse(self.report()['qualified'])

    def test_generated_clock_missing(self):
        path = self.platform / 'clocks.txt'
        path.write_text(path.read_text().split('Generated Clock :')[0])
        self.refresh_artifact('clocks')
        self.assertFalse(self.report()['qualified'])

    def test_real_fully_routed_omitted_zero_format(self):
        path = self.platform / 'route_status.txt'
        path.write_text('Design Route Status\n# of routable nets.... : 98333 :\n# of fully routed nets.... : 98333 :\n# of nets with routing errors.... : 0 :\n')
        self.refresh_artifact('route_status')
        self.assertTrue(self.report()['qualified'])

    def test_route_explicit_and_derived_consistent(self):
        text = '# of routable nets.... : 9 :\n# of fully routed nets.... : 9 :\n# of unrouted nets.... : 0 :\n# of nets with routing errors.... : 0 :\n'
        self.assertEqual(q.route_counts(text), dict(unrouted_nets=0, routing_errors=0))

    def test_route_missing_negative_duplicates_contradictions(self):
        good = '# of routable nets.... : 9 :\n# of fully routed nets.... : 9 :\n# of nets with routing errors.... : 0 :\n'
        bad = [good.replace('# of routable nets.... : 9 :\n', ''),
               good.replace('# of fully routed nets.... : 9 :\n', ''),
               good.replace('# of nets with routing errors.... : 0 :\n', ''),
               good.replace('routable nets.... : 9', 'routable nets.... : -9'),
               good.replace('fully routed nets.... : 9', 'fully routed nets.... : 10'),
               good + '# of unrouted nets.... : 1 :\n',
               good + '# of fully routed nets.... : 9 :\n',
               good + '# of routable nets.... : 10 :\n',
               good + '# of nets with routing errors.... : 0 :\n',
               good + '# of partially routed nets.... : 1 :\n',
               good + '# of unrouted nets.... : -1\n',
               good + '# of fully routed nets.... : nonsense\n',
               '# of unrouted nets.... : 0 :\n# of nets with routing errors.... : 0 :\n# of partially routed nets.... : 1 :\n',
               '# of nets with routing errors.... : 0 :\n']
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    q.route_counts(text)

    def test_route_old_explicit_without_terminal_colon(self):
        self.assertEqual(q.route_counts('# of unrouted nets.... : 0\n# of nets with routing errors.... : 0\n'),
                         dict(unrouted_nets=0, routing_errors=0))

    def test_native_postroute_physopt_and_role_aliases(self):
        path = self.platform / 'route_receipt.json'
        receipt = q.load(path)
        receipt['impl_run'].update(status='phys_opt_design (Post-Route) Complete!', final_step='phys_opt_design (Post-Route)')
        for entry in receipt['artifacts']:
            if entry['role'] == 'timing_summary':
                entry['role'] = 'timing'
            elif entry['role'] in ('timing_slow_slow', 'timing_slow_fast', 'timing_fast_slow', 'timing_fast_fast'):
                entry['role'] = entry['role'].removeprefix('timing_')
        self.write(path, receipt)
        self.assertTrue(self.report()['qualified'])

    def test_duplicate_canonical_artifact_roles(self):
        path = self.platform / 'route_receipt.json'
        receipt = q.load(path)
        alias = dict(next(a for a in receipt['artifacts'] if a['role'] == 'timing_summary'))
        alias['role'] = 'timing'
        receipt['artifacts'].append(alias)
        self.write(path, receipt)
        self.assertFalse(self.report()['qualified'])

    def test_incomplete_or_wrong_postroute_step(self):
        path = self.platform / 'route_receipt.json'
        receipt = q.load(path)
        receipt['impl_run']['status'] = 'phys_opt_design (Post-Route) Complete!'
        receipt['impl_run']['final_step'] = 'phys_opt_design (Post-Place)'
        self.write(path, receipt)
        self.assertFalse(self.report()['qualified'])

    def test_route_nonzero_derivation_or_errors_rehashed(self):
        good = '# of routable nets.... : 9 :\n# of fully routed nets.... : 9 :\n# of nets with routing errors.... : 0 :\n'
        for text in (good.replace('fully routed nets.... : 9', 'fully routed nets.... : 8'),
                     good.replace('routing errors.... : 0', 'routing errors.... : 1')):
            with self.subTest(text=text):
                (self.platform / 'route_status.txt').write_text(text)
                self.refresh_artifact('route_status')
                self.assertFalse(self.report()['qualified'])


if __name__ == '__main__':
    unittest.main()
