"""Independently validate unqualified HPM ILA captures using exact CSV columns.

The column map must be taken from the actual design/probe identity, not guessed.
Job expectations come from PS receipts matched to the frozen input fixture.
"""
import argparse
import csv
import json
from pathlib import Path

FIELDS = ('heartbeat', 'rst', 'handshakes', 'responses', 'status', 'job_id',
          'result', 'completed', 'done_event', 'accepted')
RADIX = {'HEX': 16, 'BINARY': 2, 'BIN': 2, 'UNSIGNED': 10, 'SIGNED': 10, 'DECIMAL': 10}


def read_rows(path, columns):
    if set(columns) != set(FIELDS) or len(set(columns.values())) != len(FIELDS):
        raise ValueError('exact unique column map required')
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.reader(stream)
        names, radices = next(reader), next(reader)
        indices = {}
        for field, name in columns.items():
            if names.count(name) != 1:
                raise ValueError('missing/nonunique column: ' + name)
            indices[field] = names.index(name)
        return [{field: int(row[index], RADIX[radices[index].strip().upper()])
                 for field, index in indices.items()} for row in reader if row]


def check_rows(rows, jobs=None, samples=2048):
    if len(rows) != samples:
        raise ValueError('unexpected sample count')
    widths = dict(heartbeat=32, rst=1, handshakes=8, responses=4, status=3,
                  job_id=32, result=32, completed=32, done_event=1, accepted=32)
    expected = None
    if jobs is not None:
        expected = {job['job_id']: job for job in jobs}
        if not jobs or len(expected) != len(jobs):
            raise ValueError('nonempty unique expected job IDs required')
        for job in jobs:
            if not 1 <= job['length'] <= 512 or not -(1 << 31) <= job['expected'] < (1 << 31):
                raise ValueError('invalid expected job')
    events = []
    previous = None
    saw_busy = False
    for row in rows:
        for field, bits in widths.items():
            value = row[field]
            if field == 'result' and value < 0:
                if value < -(1 << 31):
                    raise ValueError('signed result out of range')
            elif not 0 <= value < (1 << bits):
                raise ValueError('probe out of range: ' + field)
        if row['rst'] or row['status'] & 4 or row['status'] == 3:
            raise ValueError('reset or hardware error observed')
        if row['handshakes'] & 4 and row['responses'] & 12:
            raise ValueError('read error response while RVALID')
        if row['handshakes'] & 2 and row['responses'] & 3:
            raise ValueError('write error response while BVALID')
        if previous is not None:
            if row['heartbeat'] != (previous['heartbeat'] + 1) % (1 << 32):
                raise ValueError('clock/reset continuity failure')
            if row['completed'] != (previous['completed'] + row['done_event']) % (1 << 32):
                raise ValueError('completion/event continuity failure')
            if row['job_id'] == previous['job_id'] and row['accepted'] < previous['accepted']:
                raise ValueError('accepted count regressed within a job')
        if expected is None:
            if any(row[field] for field in ('handshakes', 'status', 'job_id', 'result', 'completed', 'done_event', 'accepted')):
                raise ValueError('unexpected activity before PS test')
        else:
            if row['job_id'] not in expected:
                raise ValueError('capture job has no independent PS expectation')
            job = expected[row['job_id']]
            if row['accepted'] > job['length']:
                raise ValueError('too many accepted input pairs')
            saw_busy = saw_busy or bool(row['status'] & 1)
            if row['done_event']:
                result = row['result']
                if result >= (1 << 31):
                    result -= 1 << 32
                if row['status'] != 2 or row['accepted'] != job['length'] or result != job['expected']:
                    raise ValueError('completed job differs from independent expectation')
                if row['job_id'] in [event['job_id'] for event in events]:
                    raise ValueError('duplicate completion event')
                events.append({'job_id': row['job_id'], 'result': result,
                               'accepted': row['accepted'], 'completed': row['completed']})
        previous = row
    if expected is not None and (not saw_busy or not events):
        raise ValueError('capture must include actual busy and a valid completion')
    return {'status': 'PASS', 'kind': 'clock-reset-baseline' if expected is None else 'PS-job-transaction',
            'samples': samples, 'heartbeat_contiguous_mod32': True, 'errors': 0,
            'completed_jobs_observed': events}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--columns', type=Path, required=True)
    parser.add_argument('--jobs', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    columns = json.loads(args.columns.read_text(encoding='utf-8'))
    jobs = json.loads(args.jobs.read_text(encoding='utf-8')) if args.jobs else None
    result = check_rows(read_rows(args.csv, columns), jobs)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))
