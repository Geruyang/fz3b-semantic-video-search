import copy
import hashlib
import pytest
from compare_stages import compare, summarize


def fixture(duration=100):
    records = [{'frame_id': i, 'input_sha256': 'a' * 64, 'feature_sha256': 'b' * 64,
                'submit_ms': i * duration, 'complete_ms': (i + 1) * duration,
                'correct': True} for i in range(30)]
    return {'schema_version': 1, 'stage': 'test', 'execution': 'board',
            'model_sha256': 'c' * 64,
            'input_sequence_sha256': hashlib.sha256((('a' * 64 + '\n') * 30).encode()).hexdigest(),
            'boundary': 'preprocessed_tensor_to_features', 'threads': {'full': 4},
            'cpu_frequency_khz': [1066666] * 4, 'profile': False, 'warmup_count': 3,
            'expected_frame_ids': list(range(30)), 'records': records,
            'batch_start_ms': 0, 'batch_end_ms': 30 * duration,
            'identity': {'software': 'synthetic fixture only'}}


def test_serial_controlled_comparison():
    result = compare(fixture(100), fixture(50))
    assert result['controlled_comparison']
    assert result['throughput_speedup'] == 2
    assert result['latency_p50_reduction_percent'] == 50


def test_pipeline_uses_total_batch_not_inverse_latency():
    data = fixture()
    for i, record in enumerate(data['records']):
        record.update(submit_ms=i * 10, complete_ms=i * 10 + 100)
    data['batch_end_ms'] = 390
    result = summarize(data)
    assert result['latency_p50_ms'] == 100
    assert result['throughput_fps'] == pytest.approx(30 / .390)


@pytest.mark.parametrize('mutation', [
    lambda x: x['records'].pop(),
    lambda x: x['records'].append(copy.deepcopy(x['records'][0])),
    lambda x: x['records'][0].update(correct=False),
    lambda x: x['records'][0].update(complete_ms=float('nan')),
    lambda x: x['records'][0].update(submit_ms=-1),
    lambda x: x['records'][0].update(frame_id=True),
    lambda x: x['records'][0].update(input_sha256='d' * 64),
    lambda x: x.update(batch_end_ms=1),
    lambda x: x.update(status='FAILED'),
    lambda x: x.update(compare_eligible=False),
])
def test_invalid_or_incomplete_results_rejected(mutation):
    data = fixture()
    mutation(data)
    with pytest.raises(ValueError):
        summarize(data)


@pytest.mark.parametrize('key,value', [
    ('execution', 'simulation'), ('boundary', 'jpeg_to_result'),
    ('threads', {'prefix': 2, 'suffix': 2}), ('profile', True),
    ('warmup_count', 0), ('cpu_frequency_khz', [1000000] * 4),
])
def test_mismatched_runs_never_claim_controlled_speedup(key, value):
    old, new = fixture(), fixture(50)
    new[key] = value
    result = compare(old, new)
    assert not result['controlled_comparison']
    assert 'throughput_speedup' not in result


def test_reordered_results_flagged():
    old, new = fixture(), fixture()
    new['records'].reverse()
    result = compare(old, new)
    assert 'returned_order_changed' in result['condition_differences']
