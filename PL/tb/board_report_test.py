"""Recorded 007 audit/mutation tests plus SYNTHETIC capture-schema tests.

Synthetic captures are not hardware results and never produce a qualification.
"""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('board_report',ROOT/'scripts/board_report.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


class Recorded007Tests(unittest.TestCase):
    def setUp(self):
        self.doc=b.load(ROOT/'reports/board/rtl-profiles.json')

    def errors(self):
        errors=[];b.profile_stats(self.doc,errors,b.digest(ROOT/'board/compare_board.py'));return errors

    def test_original_profile_numeric_data(self):
        self.assertEqual(self.errors(),[])

    def test_nonzero_protocol(self):
        raw=self.doc['rows'][0]['jobs'][2]['completion']
        raw['protocol_error']=raw['status_after']['protocol_error']=1
        self.assertTrue(self.errors())

    def test_B_not_drained(self):
        raw=self.doc['rows'][0]['jobs'][2]['completion']
        raw['b_total']=raw['status_after']['b_total']=raw['b_total']-1
        self.assertTrue(self.errors())

    def test_median_not_sample_median(self):
        self.doc['rows'][1]['median_job_cycles']-=5000000
        self.assertTrue(self.errors())

    def test_exact_swapped_outputs_required(self):
        j=self.doc['rows'][0]['jobs'][1]
        j['actual_sha256'].reverse()
        self.assertTrue(self.errors())

    def test_canary_checker_source_changed(self):
        for snapshots in ('source_snapshot_before','source_snapshot_after'):
            self.doc[snapshots]=copy.deepcopy(self.doc[snapshots])
            self.doc[snapshots][0]['sha256']='0'*64
        self.assertTrue(self.errors())

    def test_cleanup_not_quiesced(self):
        self.doc['cleanup']['quiesce_confirmed']=False
        self.assertTrue(self.errors())

    def test_missing_measured_sample(self):
        self.doc['rows'][2]['jobs'].pop()
        self.assertTrue(self.errors())

    def test_actual007_functional_pass_performance_fail(self):
        result=b.audit(ROOT/'reports/board','007','hls-post-reboot','rtl','legacy-chain','restore-hls-007')
        self.assertTrue(result['functional_pass']);self.assertFalse(result['performance_pass']);self.assertFalse(result['qualified'])
        self.assertGreater(result['profiles'][1]['cycle_change_pct'],21)
        self.assertGreater(result['profiles'][3]['cycle_change_pct'],17)

    def test_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('{"fps": NaN}')
            with self.assertRaises(ValueError):b.load(p)


class SyntheticCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.profile={'identity':{'core_id':1},'artifact_sha256':'a'*64}
        self.states=[]
        for phase,wall,mono in [('before',200,20),('after',500,50)]:
            journal=self.root/('rtl-events-'+phase+'.jsonl')
            record={'kind':'firmware_loaded','label':'a0005_firmware','name':'candidate/test.pcap.bin','unix_ns':100}
            journal.write_text(json.dumps(record)+'\n')
            assets={role:{'path':'/remote/'+role,'bytes':1,'sha256':'a'*64 if role=='source_bit' else 'b'*64}
                    for role in ('source_bit','native_bin','pcap')}
            state=dict(schema='board-state-evidence-v1',variant='rtl',phase=phase,boot_id='synthetic-same-boot',
                captured_wall_ns=wall,monotonic_ns=mono,
                manager=dict(state='operating',flags='0',firmware_name=None,firmware_read_supported=False,firmware_read_error='PermissionError'),
                loader=dict(config={'path':'/remote/cfg.json','sha256':'c'*64,'bytes':1},argv=['python3','--config','/remote/cfg.json'],
                    ExecStart='python3 --config /remote/cfg.json',configured_assets=assets,pid=10,
                    source={'sha256':b.digest(ROOT/'../releases/final/PS/loader/fz3b_pl_loader.py')},config_firmware_name='candidate/test.pcap.bin'),
                collector_source={'sha256':b.digest(ROOT/'board/capture_state.py')},
                kernel_identity={'pass':True,'identity':{'core_id':1}},loader_status={'ok':True,'result':{'ready':True}},
                clocks=dict(job_hz=200000000,pw_hz=400000000,raw_registers={'pl1_ref_ctrl':0x01010f00},lease={'last_error':0}),
                cpu=dict(actual_hz=1200000000,requested_khz=1200000,verified=True,held=True,last_error=0),
                services={unit:{'active_state':'inactive' if 'vision-console' in unit else 'active'} for unit in
                    ('fz3b-pl-loader.service','fz3b-app-cpu-clock.service','fz3b-app-r5.service','fz3b-vision-console.service')},
                load_event=dict(record=record,firmware_load_count=1,journal={'path':str(journal),'sha256':b.digest(journal),'bytes':journal.stat().st_size}))
            self.states.append(state)
        self.states[1]['benchmark_artifacts']=[]
        for role,suffix in [('profiles','profiles.json'),('full','full-result.json'),('features','measured-features.f32')]:
            p=self.root/('rtl-'+suffix);p.write_bytes(b'SYNTHETIC capture fixture only')
            self.states[1]['benchmark_artifacts'].append(dict(role=role,path='/remote/nested/'+p.name,sha256=b.digest(p),bytes=p.stat().st_size,mtime_ns=300))

    def tearDown(self):self.tmp.cleanup()

    def errors(self):
        for st in self.states:(self.root/('rtl-state-'+st['phase']+'.json')).write_text(json.dumps(st))
        errors=[];b.strict_states(self.root,'rtl','rtl',self.profile,{},errors);return errors

    def test_valid_schema_and_unsupported_manager_read(self):self.assertEqual(self.errors(),[])

    def test_wrong_loaded_bit(self):
        self.states[0]['loader']['configured_assets']['source_bit']['sha256']='d'*64
        self.assertTrue(self.errors())

    def test_loader_config_changed(self):
        self.states[1]['loader']['config']['sha256']='d'*64
        self.assertTrue(self.errors())

    def test_intervening_programming(self):
        self.states[1]['load_event']['firmware_load_count']=2
        self.assertTrue(self.errors())

    def test_wrong_boot(self):
        self.states[1]['boot_id']='different-boot'
        self.assertTrue(self.errors())

    def test_result_outside_capture(self):
        self.states[1]['benchmark_artifacts'][0]['mtime_ns']=199
        self.assertTrue(self.errors())

    def test_clock_or_cpu_changed(self):
        self.states[1]['clocks']['job_hz']=100000000
        self.states[1]['cpu']['actual_hz']=1066666656
        self.assertTrue(self.errors())

    def test_unsupported_read_requires_journal_and_flag(self):
        self.states[0]['manager']['firmware_read_supported']=True
        self.assertTrue(self.errors())

    def test_services_quarantined(self):
        self.states[0]['services']['fz3b-vision-console.service']['active_state']='active'
        self.assertTrue(self.errors())


class FirmwareProofTests(unittest.TestCase):
    def setUp(self):
        self.cfg=b.load(ROOT/'reports/board/rtl-loader-config.json')
        self.bit=self.cfg['assets']['a0005_source_bit']['sha256']
        self.state={'loader':{'configured_assets':{role:self.cfg['assets'][name] for role,name in
            [('source_bit','a0005_source_bit'),('native_bin','a0005_native_bin'),('pcap','a0005_firmware')]}}}

    def test_actual007_offline_preparation_proof(self):
        errors=[];b.firmware_identity(ROOT/'reports/board/firmware_prep_receipt.json',self.bit,[self.state],errors)
        self.assertEqual(errors,[])

    def test_wrong_independent_approved_bit(self):
        errors=[];b.firmware_identity(ROOT/'reports/board/firmware_prep_receipt.json','0'*64,[self.state],errors)
        self.assertTrue(errors)

    def test_actual_config_pcap_not_prepared_pcap(self):
        self.state=copy.deepcopy(self.state);self.state['loader']['configured_assets']['pcap']['sha256']='0'*64
        errors=[];b.firmware_identity(ROOT/'reports/board/firmware_prep_receipt.json',self.bit,[self.state],errors)
        self.assertTrue(errors)

    def test_preparation_not_bound_to_signed_route(self):
        prep=b.load(ROOT/'reports/board/firmware_prep_receipt.json');prep['route_receipt_sha256']='0'*64
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'prep.json';p.write_text(json.dumps(prep));errors=[]
            b.firmware_identity(p,self.bit,[self.state],errors);self.assertTrue(errors)


class RecordedFullMutationTests(unittest.TestCase):
    def setUp(self):self.doc=b.load(ROOT/'reports/board/rtl-full-result.json')
    def errors(self):
        errors=[];b.full_stats(self.doc,errors);return errors
    def test_recorded_full_protocol_pass(self):self.assertEqual(self.errors(),[])
    def test_relaxed_feature_gate_rejected(self):
        self.doc['min_feature_cosine']=.5;self.doc['max_feature_relative_l2']=1
        self.assertTrue(self.errors())
    def test_worker_not_drained(self):
        self.doc['measured']['runtime_summary']['workers_drained']=False
        self.assertTrue(self.errors())
    def test_duplicate_delivery_frame(self):
        self.doc['measured']['deliveries'][1]['frame_id']=self.doc['measured']['deliveries'][0]['frame_id']
        self.assertTrue(self.errors())
    def test_full_profile_event_missing(self):
        self.doc['measured']['runtime_summary']['pair_timings'][0]['pl_events'].pop()
        self.assertTrue(self.errors())
    def test_full_clock_changed(self):
        self.doc['kernel_clock_hz']=100000000
        self.assertTrue(self.errors())
    def test_missing_phase_metric(self):
        self.doc['measured']['pl_window_sum_ms'].pop('mean')
        self.assertTrue(self.errors())
    def test_nonfinite_phase_metric(self):
        self.doc['measured']['ps_call_sum_ms']['mean']=float('nan')
        self.assertTrue(self.errors())


class SyntheticProcedureTests(SyntheticCaptureTests):
    # Inherit state negatives and add complete synthetic procedure/transition gates.
    def setUp(self):
        super().setUp()
        self.remote='/remote/candidate'
        for st in self.states:
            st['boot_id']='3da2f700-a50a-4b1d-ab1c-1e3e691cd645'
            st['loader']['config']['path']=self.remote+'/rtl-loader-config.json'
            st['loader']['argv']=['python3','--config',st['loader']['config']['path'],'--log',self.remote+'/loader-events.jsonl']
            st['loader']['ExecStart']=' '.join(st['loader']['argv'])
            st['load_event']['canonical_journal_path']=self.remote+'/loader-events.jsonl'
            (self.root/('rtl-state-'+st['phase']+'.json')).write_text(json.dumps(st))
        hls=copy.deepcopy(self.states[0]);hls['variant']='hls';hls['loader']['config']['path']='/remote/original-config.json'
        hls['loader']['argv']=['python3','--config','/remote/original-config.json'];hls['loader']['ExecStart']=' '.join(hls['loader']['argv'])
        (self.root/'hls-state-before.json').write_text(json.dumps(hls))
        (self.root/'dummy-prep.json').write_text('{"SYNTHETIC":true}')
        scripts=[]
        for name in ('prepare.sh','load-rtl.sh','restore-hls.sh','hls-benchmark.sh','rtl-benchmark.sh'):
            p=self.root/name
            variant='hls' if name.startswith('hls') else 'rtl'
            text='set -eu\nP='+self.remote+'\n'
            if name.endswith('benchmark.sh'):
                text+=f'capture_state.py --variant {variant} --phase before\ncompare_board.py --execute --label {variant} --artifact-sha256 '+('a'*64)+f' --output {variant}-profiles.json\n'
                text+='benchmark_cnn_pipeline_v10_live.py --measured-pairs 30 --warmup-pairs 3 --ps-schedule split --ps-front-threads 1 --ps-suffix-threads 3 --output-dir /remote/full\n'
                text+=f'capture_state.py --variant {variant} --phase after\n'
            if name=='load-rtl.sh':text+='daemon --config '+self.remote+'/rtl-loader-config.json --log '+self.remote+'/loader-events.jsonl\n'
            if name=='restore-hls.sh':text+='daemon --config /remote/original-config.json\n'
            p.write_text(text);scripts.append(dict(path=str(p),sha256=b.digest(p)))
            if name not in ('prepare.sh',):
                stem=name.removesuffix('.sh');ex=self.root/(stem+'.executed.sh');ex.write_text(text)
                (self.root/(stem+'.execution.json')).write_text(json.dumps(dict(exit_code=0,executed_script_sha256=b.digest(ex))))
        for n,stem in enumerate(('hls-benchmark','load-rtl','rtl-benchmark','restore-hls'),start=1):
            p=self.root/(stem+'.execution.json');r=json.loads(p.read_text());r.update(
                started_utc=f'2026-10-0{n}T00:00:00+00:00',ended_utc=f'2026-10-0{n}T00:01:00+00:00');p.write_text(json.dumps(r))
        hls_after=copy.deepcopy(hls);hls_after['phase']='after';hls_after['monotonic_ns']=10
        (self.root/'hls-state-after.json').write_text(json.dumps(hls_after))
        self.procedure=dict(schema='board-candidate-procedure-v1',remote_root=self.remote,
            generator_sha256=b.digest(ROOT/'scripts/board_candidate.py'),firmware_receipt_sha256=b.digest(self.root/'dummy-prep.json'),
            template_sha256={name:b.digest(ROOT/'scripts'/name) for name in
                ('board_baseline_prepare.sh','board_load_rtl.sh','board_restore_hls.sh','board_hls_profiles.sh','board_full_compare.sh','board_rtl_profiles.sh')},scripts=scripts)
        (self.root/'procedure_manifest.json').write_text(json.dumps(self.procedure))
        boot=self.states[0]['boot_id']
        (self.root/'load-rtl.log').write_text(boot+'\nRTL_CONFIG_ASSETS_SHA_VERIFIED\nFACTORY_FENCE_LEASE_RELEASE_CONFIRMED\nRTL_PROGRAMMED_IDENTITY_READY\nRTL_READY_CPU1200_PL200_400\n'+'c'*64+'\n'+'b'*64+'\n'+self.remote+'/rtl-loader-config.json\n'+boot+'\n')
        restore=boot+'\nORIGINAL_HLS_CONFIGURATION_AND_SERVICES_RESTORED\n'
        for unit in ('fz3b-pl-loader.service','fz3b-vision-console.service','fz3b-app-cpu-clock.service','fz3b-app-r5.service'):
            restore+='Id='+unit+'\nActiveState=active\n'
        restore+=json.dumps(dict(actual_hz=1200000000,requested_khz=1200000,held=True,verified=True,last_error=0))+'\n'+boot+'\n'
        (self.root/'restore-hls.log').write_text(restore)
        self.restored=copy.deepcopy(hls);self.restored['captured_wall_ns']=800;self.restored['monotonic_ns']=80
        self.restored['services']['fz3b-vision-console.service']['active_state']='active'
        folder=self.root/'restored';folder.mkdir();journal=folder/'hls-events-before.jsonl'
        record=copy.deepcopy(hls['load_event']['record']);record['unix_ns']=600
        journal.write_text(json.dumps(hls['load_event']['record'])+'\n'+json.dumps(record)+'\n')
        self.restored['load_event'].update(record=record,firmware_load_count=2,
            journal={'path':str(journal),'sha256':b.digest(journal),'bytes':journal.stat().st_size})
        self.update_restored()
        markers=''.join('BOARD_STATE_CAPTURED rtl '+st['phase']+' '+st['boot_id']+' '+b.digest(self.root/('rtl-state-'+st['phase']+'.json'))+'\n' for st in self.states)
        (self.root/'rtl-benchmark.log').write_text(markers)

    def update_restored(self):
        p=self.root/'restored/hls-state-before.json';p.write_text(json.dumps(self.restored))
        log=self.root/'restore-hls.log';text=log.read_text()
        text='\n'.join(line for line in text.splitlines() if not line.startswith('BOARD_STATE_CAPTURED'))+'\n'
        text+='BOARD_STATE_CAPTURED hls before '+self.restored['boot_id']+' '+b.digest(p)+'\n'
        log.write_text(text)

    def test_procedure_generated_executed_script_binding(self):
        errors=[];b.procedure_identity(self.root,self.root/'dummy-prep.json',errors);self.assertEqual(errors,[])

    def test_combined_capture_hash_markers_and_full_commands(self):
        errors=[];b.combined_execution(self.root,'rtl','a'*64,errors);self.assertEqual(errors,[])

    def test_actual_forced_transition_restore_schema(self):
        errors=[];self.assertTrue(b.strict_transition_restore(self.root,self.procedure,'restore-hls',self.states[0]['boot_id'],errors));self.assertEqual(errors,[])

    def test_missing_restore_not_qualified(self):
        errors=[];self.assertFalse(b.strict_transition_restore(self.root,self.procedure,None,self.states[0]['boot_id'],errors));self.assertTrue(errors)

    def test_modified_executed_script(self):
        (self.root/'rtl-benchmark.executed.sh').write_text('set -eu\n# forged procedure')
        errors=[];b.combined_execution(self.root,'rtl','a'*64,errors);self.assertTrue(errors)

    def test_marker_bound_to_wrong_state_sha(self):
        (self.root/'rtl-benchmark.log').write_text((self.root/'rtl-benchmark.log').read_text().replace(b.digest(self.root/'rtl-state-before.json'),'0'*64))
        errors=[];b.combined_execution(self.root,'rtl','a'*64,errors);self.assertTrue(errors)

    def test_loaded_config_pcap_not_in_actual_transition_log(self):
        (self.root/'load-rtl.log').write_text((self.root/'load-rtl.log').read_text().replace('b'*64,'d'*64))
        errors=[];self.assertFalse(b.strict_transition_restore(self.root,self.procedure,'restore-hls',self.states[0]['boot_id'],errors))

    def test_restore_not_all_services_active(self):
        (self.root/'restore-hls.log').write_text((self.root/'restore-hls.log').read_text().replace('Id=fz3b-app-r5.service\nActiveState=active','Id=fz3b-app-r5.service\nActiveState=inactive'))
        errors=[];self.assertFalse(b.strict_transition_restore(self.root,self.procedure,'restore-hls',self.states[0]['boot_id'],errors))

    def test_positive_host_and_board_chronology(self):
        errors=[];b.execution_chronology(self.root,'restore-hls',errors);self.assertEqual(errors,[])

    def test_restore_before_rtl_cannot_qualify(self):
        p=self.root/'restore-hls.execution.json';r=json.loads(p.read_text());r.update(
            started_utc='2026-09-30T00:00:00+00:00',ended_utc='2026-09-30T00:01:00+00:00');p.write_text(json.dumps(r))
        errors=[];b.execution_chronology(self.root,'restore-hls',errors);self.assertTrue(errors)
        errors=[];self.assertFalse(b.strict_transition_restore(self.root,self.procedure,'restore-hls',self.states[0]['boot_id'],errors))
        self.assertTrue(errors)

    def test_load_before_hls_done_cannot_qualify(self):
        p=self.root/'load-rtl.execution.json';r=json.loads(p.read_text());r.update(
            started_utc='2026-10-01T00:00:30+00:00',ended_utc='2026-10-01T00:00:40+00:00');p.write_text(json.dumps(r))
        errors=[];b.execution_chronology(self.root,'restore-hls',errors);self.assertTrue(errors)

    def test_rtl_before_load_done_cannot_qualify(self):
        p=self.root/'rtl-benchmark.execution.json';r=json.loads(p.read_text());r.update(
            started_utc='2026-10-02T00:00:10+00:00',ended_utc='2026-10-02T00:00:20+00:00');p.write_text(json.dumps(r))
        errors=[];b.execution_chronology(self.root,'restore-hls',errors);self.assertTrue(errors)

    def test_missing_naive_nonfinite_reversed_utc_rejected(self):
        base={'started_utc':'2026-10-01T00:00:00+00:00','ended_utc':'2026-10-01T00:01:00+00:00'}
        for bad in ({},dict(base,started_utc='2026-10-01T00:00:00'),dict(base,ended_utc='NaN'),
                    dict(base,ended_utc='2026-09-30T00:01:00+00:00'),dict(base,ended_utc=base['started_utc'])):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):b.execution_interval(bad)

    def test_cross_variant_monotonic_order_rejected(self):
        p=self.root/'hls-state-after.json';r=json.loads(p.read_text());r['monotonic_ns']=21;p.write_text(json.dumps(r))
        errors=[];b.execution_chronology(self.root,'restore-hls',errors);self.assertTrue(errors)

    def test_actual_postrestore_capture_schema(self):
        errors=[];self.assertTrue(b.restored_capture(self.root,'restore-hls',self.states[0]['boot_id'],errors));self.assertEqual(errors,[])

    def test_stale_postrestore_pcap_event_rejected(self):
        p=self.root/'restored/hls-events-before.jsonl';record=copy.deepcopy(self.restored['load_event']['record']);record['unix_ns']=100
        p.write_text(json.dumps(record)+'\n'+json.dumps(record)+'\n');self.restored['load_event'].update(record=record,
            journal={'path':str(p),'sha256':b.digest(p),'bytes':p.stat().st_size});self.update_restored()
        errors=[];self.assertFalse(b.restored_capture(self.root,'restore-hls',self.states[0]['boot_id'],errors))

    def test_postrestore_cfg_not_original_rejected(self):
        self.restored['loader']['config']['sha256']='d'*64;self.update_restored()
        errors=[];self.assertFalse(b.restored_capture(self.root,'restore-hls',self.states[0]['boot_id'],errors))

    def test_postrestore_service_not_active_rejected(self):
        self.restored['services']['fz3b-vision-console.service']['active_state']='inactive';self.update_restored()
        errors=[];self.assertFalse(b.restored_capture(self.root,'restore-hls',self.states[0]['boot_id'],errors))

    def test_postrestore_monotonic_not_after_rtl_rejected(self):
        self.restored['monotonic_ns']=40;self.update_restored()
        errors=[];self.assertFalse(b.restored_capture(self.root,'restore-hls',self.states[0]['boot_id'],errors))


if __name__=='__main__':unittest.main()
