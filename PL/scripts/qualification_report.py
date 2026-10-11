"""Fail-closed host qualification from hash-bound simulation and routed evidence.

This checker never starts tools, changes RTL, or upgrades incomplete evidence.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def resolved(path, base):
    p = Path(str(path).replace('\\\\', '/').replace('\\', '/'))
    return p if p.is_absolute() else base / p


class Audit:
    def __init__(self):
        self.errors = []

    def require(self, condition, message):
        if not condition:
            self.errors.append(message)
        return bool(condition)

    def file(self, path, sha, label):
        if not self.require(Path(path).is_file(), f'{label}: missing {path}'):
            return False
        return self.require(bool(sha) and digest(path) == str(sha).lower(),
                            f'{label}: SHA256 mismatch {path}')


def memory_resources(text):
    def number(label):
        pattern = re.escape(label.rstrip('*')) + (r'\*?' if label.endswith('*') else '')
        match = re.search(r'^\s*\|\s*' + pattern + r'\s*\|\s*([\d,.]+)', text, re.M)
        if not match:
            raise ValueError('missing routed utilization row: ' + label)
        return float(match.group(1).replace(',', ''))
    return dict(lut=number('CLB LUTs*'), ff=number('CLB Registers'),
                bram36_equivalent=number('Block RAM Tile'), dsp=number('DSPs'))


def timing_values(text):
    match = re.search(r'WNS\(ns\).*?\n\s*[- \t]+\n\s*([^\n]+)', text, re.S)
    if not match:
        raise ValueError('missing routed timing summary table')
    row = match.group(1).split()
    return dict(wns_ns=float(row[0]), tns_ns=float(row[1]),
                whs_ns=float(row[4]), ths_ns=float(row[5]), wpws_ns=float(row[8]))


def drc_severity_counts(text):
    if ('Report DRC' not in text or not re.search(r'Design State\s*:\s*Fully Routed', text)
            or not re.search(r'Ruledeck:\s*default', text) or 'Max checks: <unlimited>' not in text
            or not re.search(r'Checks found:\s*\d+', text)):
        raise ValueError('unrecognized raw DRC report')
    rows = re.findall(r'^\s*\|\s*[^|]+\|\s*(Error|Critical Warning)\s*\|[^|]*\|\s*(\d+)\s*\|', text, re.M | re.I)
    all_rows = re.findall(r'^\s*\|\s*[^|]+\|\s*(?:Error|Critical Warning|Warning|Advisory|Info)\s*\|[^|]*\|\s*(\d+)\s*\|', text, re.M | re.I)
    found = int(re.search(r'Checks found:\s*(\d+)', text)[1])
    if sum(int(n) for n in all_rows) != found:
        raise ValueError('raw DRC summary checks/severity rows incomplete')
    errors = sum(int(n) for severity, n in rows if severity.lower() == 'error')
    critical = sum(int(n) for severity, n in rows if severity.lower() == 'critical warning')
    error_details = re.findall(r'^\s*(?:[\w-]+#\d+\s+Error\b|ERROR\b.*)', text, re.M | re.I)
    critical_details = re.findall(r'^\s*(?:[\w-]+#\d+\s+Critical Warning\b|CRITICAL WARNING\b.*)', text, re.M | re.I)
    return max(errors, len(error_details)), max(critical, len(critical_details))


def clock_roles(text):
    rows = re.findall(r'^\s*(\S+)\s+([\d.]+)\s+\{[^}]+\}\s+\S+\s+\{([^}]+)\}', text, re.M)
    roles = {'input': set(), 'job': set(), 'pw': set()}
    for name, period, source in rows:
        if ('PLCLK[0]' in source or 'PLCLK[1]' in source) and abs(float(period)-10) < .001:
            roles['input'].add(name)
        if 'driver_job_bufgce_div/O' in source and abs(float(period)-5) < .001:
            roles['job'].add(name)
        if ('pw_local_bufgce_div/O' in source or 'mmcme4_adv_inst/CLKOUT0' in source) and abs(float(period)-2.5) < .001:
            roles['pw'].add(name)
    return roles


def clock_topology(text, roles):
    rows = re.findall(r'^\s*(\S+)\s+([\d.]+)\s+\{[^}]+\}\s+\S+\s+\{([^}]+)\}', text, re.M)
    periods = {name: float(period) for name, period, _ in rows}
    if len(periods) != len(rows):
        return False
    generated = {}
    for block in re.split(r'Generated Clock\s*:\s*', text)[1:]:
        name = block.splitlines()[0].strip()
        master = re.search(r'Master Clock\s*:\s*(\S+)', block)
        mul = re.search(r'Multiply By\s*:\s*([\d.]+)', block)
        div = re.search(r'Divide By\s*:\s*([\d.]+)', block)
        if name in generated or not master:
            return False
        generated[name] = (master[1], float(mul[1]) if mul else 1., float(div[1]) if div else 1.)

    def ancestors(name):
        chain = []
        while name not in roles['input']:
            if name in chain or name not in generated or name not in periods:
                return None
            chain.append(name)
            master, mul, div = generated[name]
            if mul <= 0 or div <= 0 or master not in periods or abs(periods[name]-periods[master]*div/mul) > .001:
                return None
            name = master
        return chain + [name]

    fast_chains = [ancestors(name) for name in roles['pw']]
    if not fast_chains or any(chain is None for chain in fast_chains):
        return False
    for job in roles['job']:
        chain = ancestors(job)
        if chain is None or job not in generated:
            return False
        master, mul, div = generated[job]
        if mul != 1 or div != 2 or not any(master in fast_chain[:-1] for fast_chain in fast_chains):
            return False
    return bool(roles['job'])


def route_counts(text):
    """Support explicit zero or Vivado's omitted-zero fully-routed format.

    Missing values are never zero by default. Derivation requires a complete,
    unique, nonnegative routable/fully-routed pair and explicit error count.
    """
    labels = ('unrouted nets', 'routable nets', 'fully routed nets',
              'nets with routing errors', 'partially routed nets')
    values = {}
    for label in labels:
        matches = re.findall(r'^[ \t]*# of ' + re.escape(label) + r'\b[^\r\n]*', text, re.M)
        if len(matches) > 1:
            raise ValueError('duplicate route-status count: ' + label)
        if matches:
            parsed = re.fullmatch(r'[ \t]*# of ' + re.escape(label) + r'\.+[ \t]*:[ \t]*(\d+)[ \t]*(?::[ \t]*)?', matches[0])
            if not parsed:
                raise ValueError('invalid/negative route-status count: ' + label)
            values[label] = int(parsed[1])
    if 'nets with routing errors' not in values:
        raise ValueError('routing-error count missing')
    pair_present = ('routable nets' in values, 'fully routed nets' in values)
    if pair_present[0] != pair_present[1]:
        raise ValueError('incomplete routable/fully-routed pair')
    if all(pair_present):
        difference = values['routable nets'] - values['fully routed nets']
        if difference < 0:
            raise ValueError('fully-routed count exceeds routable count')
        if 'unrouted nets' in values and values['unrouted nets'] != difference:
            raise ValueError('explicit unrouted count contradicts routable/fully-routed counts')
        unrouted = difference
    elif 'unrouted nets' in values:
        unrouted = values['unrouted nets']
    else:
        raise ValueError('unrouted count missing without complete derivation inputs')
    if values.get('partially routed nets', 0) > unrouted:
        raise ValueError('partial-route count contradicts unrouted count')
    return dict(unrouted_nets=unrouted, routing_errors=values['nets with routing errors'])


def check(simulation_candidate, platform_reports, project, root):
    audit = Audit()
    candidate, platform, project = map(Path, (simulation_candidate, platform_reports, project))
    if project.suffix == '.xpr':
        project = project.parent
    report = dict(schema='rtl-optim-qualification-report-v1', status='INCOMPLETE',
                  qualified=False, board_operations=False, board_fps='not_measured',
                  simulation_candidate=str(candidate), platform_reports=str(platform),
                  project=str(project), errors=audit.errors, cycles=[], resources=[])
    baseline = load(root / 'reports/baseline.json')
    baseline_cycles = {x['profile']: x for x in baseline['baseline_cycles_from_historical_receipt']}
    report['baseline_sha256'] = digest(root / 'reports/baseline.json')

    manifest_path = candidate / 'source_manifest.json'
    try:
        manifest = load(manifest_path)
        hashes = {}
        for entry in manifest:
            original = resolved(entry['original'], root)
            frozen = resolved(entry['snapshot'], candidate)
            sha = entry['sha256']
            audit.file(frozen, sha, 'simulation frozen source')
            # FAST primitives and testbench are checked too; production RTL must
            # additionally match the immutable project source snapshot.
            audit.file(original, sha, 'current simulation source')
            if (root / 'rtl' / original.name).is_file():
                hashes['rtl/' + original.name] = sha.lower()
                audit.file(root / 'rtl' / original.name, sha, 'current production source')
        audit.require(bool(hashes), 'simulation manifest contains no production RTL')
        expected = {'rtl/' + p.name for p in (root / 'rtl').iterdir()
                    if p.suffix in ('.sv', '.v') and p.name not in ('cnn_rtl_bd.sv', 'cnn_dsp_primitives.v')}
        audit.require(set(hashes) == expected, 'simulation production RTL set incomplete/unexpected: ' + str(sorted(expected ^ set(hashes))))
        snapshot = project / 'source_snapshot'
        sha_file = snapshot / 'SHA256SUMS.txt'
        entries = {}
        for line in sha_file.read_text(encoding='utf-8-sig').splitlines():
            match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.+)', line)
            if match:
                name = match[2].replace('\\', '/')
                entries[name] = match[1].lower()
                audit.file(snapshot / name, match[1], 'project frozen source')
                if name.startswith('rtl/'):
                    audit.file(root / name, match[1], 'current/project production source')
        audit.require(expected <= entries.keys(), 'project production RTL set incomplete')
        for name, sha in hashes.items():
            audit.require(entries.get(name) == sha, 'simulation/project source mismatch: ' + name)
        report['source_identity'] = dict(simulation_manifest_sha256=digest(manifest_path),
                                         project_snapshot_sha256=digest(sha_file),
                                         matched_rtl_files=len(hashes))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        audit.errors.append('source identity incomplete: ' + str(exc))

    proof_sha = fixture_sha = binary_sha = None
    compile_sha = None
    try:
        compile_log = candidate / 'compile.log'
        compile_sha = digest(compile_log)
        compiled_paths = [resolved(p, candidate) for p in re.findall(r'Analyzing (?:SystemVerilog|Verilog) file "([^"]+)"', compile_log.read_text())]
        compiled = {p.resolve() for p in compiled_paths if p.name != 'glbl.v'}
        wanted = {resolved(e['snapshot'], candidate).resolve() for e in manifest}
        audit.require(compiled == wanted and len(compiled_paths) >= len(wanted), 'raw compiler source file list differs from complete simulation manifest')
    except (OSError, ValueError, KeyError, TypeError, UnboundLocalError) as exc:
        audit.errors.append('compiler source list evidence incomplete: ' + str(exc))
    try:
        binary_path = candidate / 'simulation_snapshot/binary_manifest.json'
        binary_sha = digest(binary_path)
        binaries = load(binary_path)
        audit.require(bool(binaries), 'compiled snapshot manifest empty')
        for entry in binaries:
            audit.file(resolved(entry['path'], candidate), entry['sha256'], 'compiled simulation snapshot')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        audit.errors.append('compiled snapshot evidence incomplete: ' + str(exc))
    try:
        binding_path = candidate / 'fast_proof_binding.json'
        binding = load(binding_path)
        proof_sha = digest(binding_path)
        audit.require(binding.get('pass') is True and binding.get('candidate_source_matches') is True
                      and binding.get('all_current_input_generated_log_hashes_checked') is True,
                      'FAST proof binding did not pass')
        proof_path = candidate / 'fast_proof/receipt.json'
        audit.file(proof_path, binding.get('proof_receipt_sha256'), 'FAST proof receipt')
        proof = load(proof_path)
        audit.require(proof.get('run_id') == binding.get('proof_run_id') and proof.get('pass') is True
                      and proof.get('production_source_changed') is False
                      and proof.get('controller_fifo_source_identical') is True, 'FAST proof identity/status invalid')
        coverage = proof.get('result', {})
        audit.require(coverage.get('accepted_tiles') == 1024 and coverage.get('lane_results') == 4096
                      and coverage.get('compared_job_clock_cycles') == 3413
                      and coverage.get('every_cycle_valid_ready_and_valid_data') is True,
                      'FAST proof lacks cycle-exact coverage')
        audit.require(bool(proof.get('commands')) and all(c.get('exit_code') == 0 for c in proof['commands']),
                      'FAST proof tool command failed/missing')
        for entry in binding.get('copies', []):
            audit.file(resolved(entry['path'], candidate), entry['sha256'], 'FAST frozen copy')
        audit.require(len(binding.get('copies', [])) >= 10, 'FAST proof copies incomplete')
        for name, field in [('cnn_pw_mac.sv', 'production_mac_sha256'),
                            ('cnn_dsp_primitives.v', 'real_primitives_sha256')]:
            audit.file(root / 'rtl' / name, binding.get(field), 'FAST production identity')
        fixtures_path = candidate / 'fixture_binding.json'
        fixtures = load(fixtures_path)
        fixture_sha = digest(fixtures_path)
        audit.require(fixtures.get('pass') is True and fixtures.get('identity') == 'A0004', 'frozen fixture identity invalid')
        for entry in fixtures.get('entries', []):
            audit.file(resolved(entry['snapshot'], candidate), entry['sha256'], 'frozen fixture')
        audit.require(len(fixtures.get('entries', [])) >= 20, 'four-profile frozen fixture binding incomplete')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        audit.errors.append('FAST/fixture evidence incomplete: ' + str(exc))

    seen = {}
    results = list(candidate.glob('p*_r1_result.json'))
    results += list(candidate.glob('runs/**/result.json'))
    if (candidate / 'result.json').is_file():
        results.append(candidate / 'result.json')
    for result_path in results:
        try:
            result = load(result_path)
            if result.get('mixed_sequence_verified') is True:
                continue
            # Unfinished/failed runs are kept as evidence but never qualify a profile.
            if result.get('functional_pass') is not True or result.get('performance_pass') is not True:
                continue
            audit.require(result.get('source_manifest_sha256', '').lower() == digest(manifest_path),
                          f'{result_path}: source manifest not bound')
            audit.require(result.get('compiled_snapshot_manifest_sha256', '').lower() == binary_sha,
                          f'{result_path}: compiled snapshot not bound')
            audit.require(result.get('compile_log_sha256', '').lower() == compile_sha, f'{result_path}: compiler source log not bound')
            audit.require(result.get('fast_proof_binding_sha256', '').lower() == proof_sha,
                          f'{result_path}: FAST proof not bound')
            audit.require(result.get('fixture_binding_sha256', '').lower() == fixture_sha,
                          f'{result_path}: fixture not bound')
            audit.require(result.get('token') == [1, 2, 32] and result.get('bdelay') == 3,
                          f'{result_path}: DDR must be token=1/2/32 Bdelay=3')
            logs = list(result_path.parent.glob('*.log'))
            if result_path.parent == candidate:
                logs += list(candidate.glob('runs/**/*.log'))
            matches = [p for p in logs if digest(p) == result.get('log_sha256', '').lower()]
            audit.require(len(matches) == 1, f'{result_path}: missing/ambiguous hash-bound simulation log')
            if not matches:
                continue
            log = matches[0].read_text(encoding='utf-8-sig', errors='replace')
            audit.require('FULL_SUITE_PASS' in log and 'FULL_FUNCTIONAL_SUITE_PASS' in log
                          and not re.search(r'Fatal:|FULL_PERFORMANCE_FAIL|DIAGNOSTIC_PROFILE_DONE', log),
                          f'{result_path}: raw functional/performance log failed')
            raw = [(int(a), int(b), int(c)) for a, b, c in
                   re.findall(r'FULL_PASS profile=(\d+) blocks=(\d+) cycles=(\d+)', log)]
            audit.require(bool(raw), f'{result_path}: no raw profile results')
            for profile in result.get('profiles', []):
                p, blocks, cycles = profile['profile'], profile['blocks'], profile['cycles']
                audit.require((p, blocks, cycles) in raw, f'{result_path}: result differs from raw FULL_PASS')
                if p not in baseline_cycles:
                    audit.errors.append('unexpected profile: ' + str(p))
                    continue
                baseline_row = baseline_cycles[p]
                audit.require(blocks == baseline_row['blocks'], f'P{p}: requires max blocks {baseline_row["blocks"]}')
                audit.require(type(cycles) is int and cycles > 0 and cycles <= baseline_row['a0005_cycles'],
                              f'P{p}: cycle gate failed')
                audit.require(f'CYCLE_GATE profile={p} target={baseline_row["a0005_cycles"]} pass=1' in log,
                              f'P{p}: raw cycle gate PASS missing')
                if p in seen:
                    audit.require(seen[p]['cycles'] == cycles, f'P{p}: ambiguous multiple passing runs')
                else:
                    seen[p] = dict(profile=p, blocks=blocks, cycles=cycles,
                                   baseline_cycles=baseline_row['a0005_cycles'],
                                   delta=cycles-baseline_row['a0005_cycles'], result=str(result_path))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            audit.errors.append(f'{result_path}: invalid result evidence: {exc}')
    report['cycles'] = [seen[p] for p in sorted(seen)]
    audit.require(set(seen) == {0, 1, 2, 3}, 'complete four-profile max-block functional/performance matrix missing')

    try:
        mixed_path = candidate / 'mixed_3_2_3_result.json'
        mixed = load(mixed_path)
        audit.require(mixed.get('functional_pass') is True and mixed.get('performance_pass') is True
                      and mixed.get('mixed_sequence_verified') is True and mixed.get('actual_sequence') == [3, 2, 3],
                      'mixed no-reset 3,2,3 functional/performance gate failed')
        for key, sha in [('source_manifest_sha256', digest(manifest_path)), ('fast_proof_binding_sha256', proof_sha),
                         ('fixture_binding_sha256', fixture_sha), ('compiled_snapshot_manifest_sha256', binary_sha), ('compile_log_sha256', compile_sha)]:
            audit.require(mixed.get(key, '').lower() == sha, 'mixed evidence not bound: ' + key)
        audit.require(mixed.get('token') == [1, 2, 32] and mixed.get('bdelay') == 3, 'mixed DDR differs from baseline')
        matches = [p for p in candidate.glob('runs/**/*.log') if digest(p) == mixed.get('log_sha256', '').lower()]
        matches += [p for p in candidate.glob('*.log') if digest(p) == mixed.get('log_sha256', '').lower()]
        audit.require(len(matches) == 1, 'mixed hash-bound raw log missing/ambiguous')
        if matches:
            text = matches[0].read_text(encoding='utf-8-sig', errors='replace')
            raw = [(int(a), int(b), int(c)) for a, b, c in re.findall(r'FULL_PASS profile=(\d+) blocks=(\d+) cycles=(\d+)', text)]
            rows = mixed.get('profiles', [])
            audit.require(len(raw) == 3 and [r[0] for r in raw] == [3, 2, 3]
                          and raw == [(r['profile'], r['blocks'], r['cycles']) for r in rows], 'mixed raw sequence/result mismatch')
            audit.require('MIXED_SEQUENCE_VERIFIED actual_sequence=3,2,3' in text
                          and 'FULL_FUNCTIONAL_SUITE_PASS' in text and 'FULL_SUITE_PASS' in text
                          and not re.search(r'Fatal:|FULL_PERFORMANCE_FAIL|DIAGNOSTIC_PROFILE_DONE', text), 'mixed raw suite did not pass')
            gates = re.findall(r'CYCLE_GATE profile=(\d+) target=(\d+) pass=(\d+)', text)
            audit.require(len(gates) == 3 and [int(g[0]) for g in gates] == [3, 2, 3]
                          and all(int(g[1]) == baseline_cycles[int(g[0])]['a0005_cycles'] and g[2] == '1' for g in gates),
                          'mixed raw performance gates invalid')
            for p, blocks, cycles in raw:
                old = baseline_cycles[p]
                audit.require(blocks == old['blocks'] and 0 < cycles <= old['a0005_cycles'], 'mixed profile maxblock/cycles invalid')
        report['mixed_sequence_verified'] = not audit.errors
    except (OSError, ValueError, KeyError, TypeError) as exc:
        audit.errors.append('mixed no-reset evidence incomplete: ' + str(exc))
        report['mixed_sequence_verified'] = False

    try:
        route_path = platform / 'route_receipt.json'
        route = load(route_path)
        audit.require(route.get('status') == 'ROUTED_SIGNOFF_PASS' and route.get('stage') == 'post_route',
                      'platform receipt is not signed-off post-route evidence')
        audit.require(route.get('part') == baseline['baseline_part_from_routed_report'], 'platform part differs from baseline')
        identity = report.get('source_identity', {})
        audit.require(route.get('source_snapshot_sha256', '').lower() == identity.get('project_snapshot_sha256'),
                      'routed receipt/project source snapshot mismatch')
        artifacts = {}
        for entry in route.get('artifacts', []):
            p = resolved(entry['path'], root)
            if not p.is_file():
                p = resolved(entry['path'], platform)
            audit.file(p, entry['sha256'], 'routed artifact')
            role = entry['role']
            role = 'timing_summary' if role == 'timing' else 'timing_' + role if role in ('slow_slow', 'slow_fast', 'fast_slow', 'fast_fast') else role
            audit.require(role not in artifacts, 'duplicate routed artifact role: ' + role)
            artifacts[role] = p
        required = {'route_dcp', 'utilization', 'timing_summary', 'route_status', 'check_timing', 'cdc',
                    'drc', 'clocks', 'timing_slow_slow', 'timing_slow_fast', 'timing_fast_slow', 'timing_fast_fast', 'signoff', 'exception_review'}
        audit.require(required <= artifacts.keys(), 'routed raw artifact set incomplete')
        for key in ('check_timing', 'cdc', 'drc', 'related_clocks', 'exceptions'):
            audit.require(route.get('checks', {}).get(key) is True, 'routed check not passed: ' + key)
        counts = route.get('counts', {})
        audit.require(counts.get('check_timing_categories', 0) >= 12, 'incomplete routed check_timing coverage')
        for key in ('check_timing_issues', 'drc_errors', 'drc_critical_warnings', 'cdc_unsafe_paths',
                    'debug_cores', 'unconstrained_internal_endpoints', 'unapproved_exceptions'):
            audit.require(counts.get(key) == 0, 'routed nonzero/missing count: ' + key)
        audit.require(type(counts.get('allowed_reset_exceptions')) is int and counts['allowed_reset_exceptions'] >= 0,
                      'audited reset exception count missing')
        impl = route.get('impl_run', {})
        audit.require(str(impl.get('progress')).rstrip('%') == '100' and
                      re.fullmatch(r'(?:route_design|write_bitstream|phys_opt_design \(Post-Route\)) Complete!?', str(impl.get('status'))) is not None,
                      'implementation run is not 100 percent Complete')
        if str(impl.get('status')).startswith('phys_opt_design'):
            audit.require(impl.get('final_step') == 'phys_opt_design (Post-Route)', 'post-route phys_opt final step not bound')
        for key in ('slow_slow', 'slow_fast', 'fast_slow', 'fast_fast'):
            group = route.get('related_clock_groups', {}).get(key, {})
            audit.require(isinstance(group.get('setup_ns'), (int, float)) and group['setup_ns'] >= 0
                          and isinstance(group.get('hold_ns'), (int, float)) and group['hold_ns'] >= 0,
                          'missing/failing related clock group: ' + key)
        resources = memory_resources(artifacts['utilization'].read_text())
        timing = timing_values(artifacts['timing_summary'].read_text())
        timing_text = artifacts['timing_summary'].read_text()
        audit.require(not re.search(r'There are ([1-9]\d*) (?:register/latch pins with no clock|internal endpoints which are not constrained|unconstrained internal endpoints)',
                                   timing_text, re.I), 'raw report has unconstrained endpoints')
        categories = re.findall(r'^\s*\d+\. checking [^(]+\((\d+)\)', artifacts['check_timing'].read_text(), re.M)
        audit.require(len(categories) >= 12 and all(int(n) == 0 for n in categories), 'raw check_timing issues/coverage failed')
        audit.require('All paths are Safely Timed.' in artifacts['cdc'].read_text(), 'raw CDC is not safely timed')
        errors, critical = drc_severity_counts(artifacts['drc'].read_text())
        audit.require(errors == counts.get('drc_errors') == 0 and critical == counts.get('drc_critical_warnings') == 0,
                      'raw DRC Error/Critical Warning differs from zero receipt counts')
        clocks = clock_roles(artifacts['clocks'].read_text())
        audit.require(all(clocks.values()), 'raw clock contract missing input100/job200/pw400MHz on expected hardware sources')
        audit.require(clock_topology(artifacts['clocks'].read_text(), clocks), 'raw generated-clock topology missing/contradictory: common100MHz source, MMCM400MHz and job divide2 required')
        for key in ('slow_slow', 'slow_fast', 'fast_slow', 'fast_fast'):
            group_text = artifacts['timing_' + key].read_text()
            slacks = re.findall(r'Slack\s*\([^)]*\)\s*:\s*(-?[\d.]+)ns', group_text)
            audit.require(len(slacks) >= 2 and all(float(n) >= 0 for n in slacks), 'raw related max/min slack missing/failed: ' + key)
            paths = re.split(r'Slack\s*\([^)]*\)\s*:', group_text)[1:]
            source_role, dest_role = [('job' if mode == 'slow' else 'pw') for mode in key.split('_')]
            for path in paths:
                pair = re.findall(r'clocked by\s+(\S+)\s+\{[^}]*period=([\d.]+)ns', path)
                audit.require(len(pair) >= 2 and pair[0][0] in clocks[source_role] and pair[1][0] in clocks[dest_role]
                              and abs(float(pair[0][1])-(5 if source_role == 'job' else 2.5)) < .001
                              and abs(float(pair[1][1])-(5 if dest_role == 'job' else 2.5)) < .001,
                              'raw related path clock identity/period invalid: ' + key)
        exception_text = artifacts['exception_review'].read_text()
        exception_count = re.search(r'allowed_standard_IP_reset_exceptions=(\d+)', exception_text)
        audit.require(exception_count is not None and int(exception_count[1]) == counts.get('allowed_reset_exceptions')
                      and 'unapproved_data_or_clock_exceptions=0' in exception_text, 'raw exception audit mismatch')
        audit.require(resources == route.get('resources'), 'receipt resources differ from original post-route report')
        audit.require(timing == route.get('timing'), 'receipt timing differs from original post-route report')
        audit.require(timing['wns_ns'] >= 0 and timing['whs_ns'] >= 0 and timing['wpws_ns'] >= 0
                      and timing['tns_ns'] == 0 and timing['ths_ns'] == 0, 'post-route setup/hold/pulse gate failed')
        route_text = artifacts['route_status'].read_text()
        actual_route = route_counts(route_text)
        audit.require(actual_route == dict(unrouted_nets=0, routing_errors=0), 'raw post-route counts not zero')
        audit.require(actual_route == route.get('route'), 'route receipt counts differ from raw post-route report')
        audit.require(route.get('route', {}).get('unrouted_nets') == 0
                      and route.get('route', {}).get('routing_errors') == 0, 'route receipt counts not zero')
        audit.file(artifacts['route_dcp'], route.get('route_dcp_sha256'), 'route DCP receipt identity')
        audit.require(artifacts['route_dcp'].stat().st_size > 0, 'empty routed DCP')
        audit.require('PASS: routed setup/hold/pulse' in artifacts['signoff'].read_text(), 'raw routed signoff missing')
        for name, value in resources.items():
            old = baseline['baseline_resources_from_original_routed_report'][name]
            audit.require(value <= old, f'resource goal exceeded: {name} {value} > {old}')
            report['resources'].append(dict(resource=name, baseline_post_route=old,
                                            candidate_post_route=value, delta=value-old))
        report['routed_timing'] = timing
        report['route_receipt_sha256'] = digest(route_path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        audit.errors.append('routed platform evidence incomplete: ' + str(exc))
    if not audit.errors:
        report['qualified'] = True
        report['status'] = 'QUALIFIED_HOST_SIMULATION_AND_POST_ROUTE'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulation-candidate', type=Path, required=True)
    parser.add_argument('--platform-reports', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--comparison', type=Path, help='Optional Markdown comparison, explicitly INCOMPLETE unless all gates pass')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = check(args.simulation_candidate.resolve(), args.platform_reports.resolve(), args.project.resolve(), root)
    output = args.output or args.platform_reports / 'qualification_report.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if args.comparison:
        lines = ['# RTL candidate comparison', '', '**Status: ' + report['status'] + '**', '',
                 'Baseline: historical A0005. Candidate: hash-bound host simulation and post-route evidence.', '',
                 '| Profile | blocks | A0005 cycles | candidate cycles | delta |',
                 '| --- | ---: | ---: | ---: | ---: |']
        for row in report['cycles']:
            lines.append(f'| P{row["profile"]} | {row["blocks"]} | {row["baseline_cycles"]} | {row["cycles"]} | {row["delta"]} |')
        lines += ['', '| Resource | baseline post-route | candidate post-route | delta |', '| --- | ---: | ---: | ---: |']
        for row in report['resources']:
            lines.append(f'| {row["resource"]} | {row["baseline_post_route"]} | {row["candidate_post_route"]} | {row["delta"]} |')
        lines += ['', 'Board operations: not executed. Board FPS: not measured.', '', 'Evidence issues:']
        lines += ['- ' + error for error in report['errors']] or ['None.']
        args.comparison.parent.mkdir(parents=True, exist_ok=True)
        args.comparison.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(report['status'])
    for error in report['errors']:
        print('- ' + error)
    return 0 if report['qualified'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
