"""Check a dynamic-DW native ILA CSV against independently frozen jobs.

Column names must be derived from the final LTX, then checked against actual
CSV headers. This verifier does not create or collect hardware evidence.
"""
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

JOB_SHA = '409fd10559f23a0b167624a977c61ae65dd237eb2eb840288a383e1a85a0b9e8'
WIDTHS = dict(heartbeat=32, rst=1, status=3, job_id=32, output_count=11,
              pixel_count=11, weight_count=6, cycles=32, output_event=1,
              output_index=10, output_value=32, handshakes=8, responses=4, completed=32)
RADIX = {'HEX': 16, 'BINARY': 2, 'BIN': 2, 'UNSIGNED': 10, 'SIGNED': 10, 'DECIMAL': 10}


def load_jobs(directory):
    path = Path(directory) / 'manifest.json'
    if hashlib.sha256(path.read_bytes()).hexdigest() != JOB_SHA:
        raise ValueError('DW job manifest identity mismatch')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    jobs = {}
    for entry in manifest['jobs']:
        if Path(entry['golden']).name != entry['golden']:
            raise ValueError('invalid golden filename')
        raw = (path.parent / entry['golden']).read_bytes()
        if len(raw) != 4096 or hashlib.sha256(raw).hexdigest() != entry['golden_sha256']:
            raise ValueError('DW golden identity mismatch')
        job_id = entry['job_id_if_fresh']
        if job_id in jobs:
            raise ValueError('duplicate expected job ID')
        jobs[job_id] = struct.unpack('<1024i', raw)
    return jobs


def read_rows(path, columns):
    if set(columns) != set(WIDTHS) or len(set(columns.values())) != len(WIDTHS):
        raise ValueError('exact unique column map required')
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.reader(stream)
        names, radices = next(reader), next(reader)
        indices = {}
        for field, name in columns.items():
            if names.count(name) != 1:
                raise ValueError('missing/nonunique column: ' + name)
            indices[field] = names.index(name)
        return [{field: int(row[i], RADIX[radices[i].strip().upper()])
                 for field, i in indices.items()} for row in reader if row]


def check_rows(rows, jobs=None, samples=8192):
    if len(rows) != samples:
        raise ValueError('unexpected sample count')
    previous, first_job = None, None
    seen, done, active = {}, {}, set()
    for row in rows:
        for field, bits in WIDTHS.items():
            value = row[field]
            if field == 'output_value' and value < 0:
                if value < -(1 << 31):
                    raise ValueError('signed output out of range')
            elif not 0 <= value < (1 << bits):
                raise ValueError('probe out of range: ' + field)
        if row['rst'] or row['status'] & 4 or row['status'] == 3:
            raise ValueError('reset or hardware error')
        if row['handshakes'] & 4 and row['responses'] & 12:
            raise ValueError('RVALID with error response')
        if row['handshakes'] & 2 and row['responses'] & 3:
            raise ValueError('BVALID with error response')
        if row['output_count'] > 1024 or row['pixel_count'] > 1024 or row['weight_count'] > 49:
            raise ValueError('hardware count exceeds task size')
        if previous is not None:
            if row['heartbeat'] != (previous['heartbeat'] + 1) % (1 << 32):
                raise ValueError('heartbeat discontinuity')
            completed_now = bool(previous['status'] & 1) and row['status'] == 2
            if row['completed'] != (previous['completed'] + int(completed_now)) % (1 << 32):
                raise ValueError('completion count disagrees with BUSY to DONE')
            if row['job_id'] == previous['job_id']:
                for field in ('output_count', 'pixel_count', 'weight_count'):
                    if row[field] not in (previous[field], previous[field] + 1):
                        raise ValueError('count changed by more than one handshake')
                if row['output_count'] != previous['output_count'] + row['output_event']:
                    raise ValueError('output event/count disagree')
                expected_cycles = min(previous['cycles'] + int(bool(previous['status'] & 1)), (1 << 32) - 1)
                if row['cycles'] != expected_cycles:
                    raise ValueError('job cycle count disagrees with BUSY duration')
            elif row['job_id'] != (previous['job_id'] + 1) % (1 << 32):
                raise ValueError('job ID discontinuity')
        if jobs is None:
            if any(row[name] for name in WIDTHS if name not in ('heartbeat', 'rst')):
                raise ValueError('activity before first PS operation')
        else:
            job_id = row['job_id']
            if job_id not in jobs:
                raise ValueError('unknown hardware job ID')
            if first_job is None:
                first_job = job_id
            if row['status'] & 1:
                active.add(job_id)
            if row['output_event']:
                index, value = row['output_index'], row['output_value']
                if value >= (1 << 31):
                    value -= 1 << 32
                values = seen.setdefault(job_id, [])
                if index != len(values) or row['output_count'] != index + 1:
                    raise ValueError('missing, duplicate or misaligned output')
                if value != jobs[job_id][index]:
                    raise ValueError('integer output differs from independent golden')
                values.append(value)
            if row['status'] == 2:
                if (row['output_count'], row['pixel_count'], row['weight_count']) != (1024, 1024, 49):
                    raise ValueError('DONE without exact task counts')
                done[job_id] = row['cycles']
        previous = row
    if jobs is not None:
        if first_job != min(jobs) or first_job not in active or first_job not in done:
            raise ValueError('first expected job must show BUSY and DONE')
        if len(seen.get(first_job, [])) != 1024:
            raise ValueError('capture does not include all first-job outputs')
    return {'status': 'PASS', 'kind': 'clock-reset-baseline' if jobs is None else 'PS-DW-transaction',
            'samples': samples, 'errors': 0,
            'observed_values_per_job': {str(k): len(v) for k, v in seen.items()},
            'completed_job_cycles': done}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--columns', type=Path, required=True)
    parser.add_argument('--jobs', type=Path)
    parser.add_argument('--samples', type=int, default=8192)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check_rows(read_rows(args.csv, json.loads(args.columns.read_text(encoding='utf-8'))),
                        load_jobs(args.jobs) if args.jobs else None, args.samples)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))
