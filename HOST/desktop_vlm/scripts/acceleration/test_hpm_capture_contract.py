import copy

import pytest

from check_hpm_capture import check_rows


def baseline():
    return [dict(heartbeat=(2**32 - 3 + i) % 2**32, rst=0, handshakes=0,
                 responses=0, status=0, job_id=0, result=0, completed=0,
                 done_event=0, accepted=0) for i in range(8)]


def transaction():
    rows = baseline()
    for i, row in enumerate(rows):
        row.update(job_id=7, accepted=min(i, 2), status=1 if i < 3 else 2,
                   result=0 if i < 3 else 2**32 - 42,
                   completed=0 if i < 3 else 1, done_event=int(i == 3))
    return rows


JOBS = [dict(job_id=7, length=2, expected=-42)]


def test_baseline_wrap():
    assert check_rows(baseline(), samples=8)['status'] == 'PASS'


def test_busy_to_signed_completion():
    report = check_rows(transaction(), JOBS, samples=8)
    assert report['completed_jobs_observed'] == [dict(job_id=7, result=-42, accepted=2, completed=1)]


@pytest.mark.parametrize('sample,field,value', [
    (3, 'result', 2**32 - 41),
    (3, 'accepted', 1),
    (3, 'status', 6),
    (3, 'job_id', 8),
    (4, 'heartbeat', 1234),
    (4, 'completed', 2),
    (4, 'done_event', 1),
    (4, 'rst', 1),
    (5, 'accepted', 1),
])
def test_reject_corrupted_capture(sample, field, value):
    rows = transaction()
    rows[sample][field] = value
    with pytest.raises(ValueError):
        check_rows(rows, JOBS, samples=8)


def test_reject_baseline_transaction():
    with pytest.raises(ValueError):
        check_rows(transaction(), samples=8)


@pytest.mark.parametrize('valid,response', [(4, 8), (2, 2)])
def test_reject_response_error_only_when_valid(valid, response):
    rows = transaction()
    rows[1]['responses'] = response
    assert check_rows(rows, JOBS, samples=8)['status'] == 'PASS'
    rows[1]['handshakes'] = valid
    with pytest.raises(ValueError):
        check_rows(rows, JOBS, samples=8)


def test_independent_wrong_expectation_rejected():
    jobs = copy.deepcopy(JOBS)
    jobs[0]['expected'] = -41
    with pytest.raises(ValueError):
        check_rows(transaction(), jobs, samples=8)
