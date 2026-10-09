"""Independent frozen B007 arithmetic check. Host-only; does not certify PL."""
import hashlib
import json
from pathlib import Path

import numpy as np


MANIFEST_SHA = '68e2a29131ca0965783b00eea54049c313de669e1c758b738f4c530bb78cd282'
BASE = Path('artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-int16act-007')


def load_record(record):
    blob = (BASE / record['path']).read_bytes()
    if hashlib.sha256(blob).hexdigest() != record['sha256']:
        raise ValueError('file digest differs: ' + record['path'])
    if 'bytes' in record and len(blob) != record['bytes']:
        raise ValueError('file length differs: ' + record['path'])
    return np.frombuffer(blob, dtype=record['dtype']).reshape(record['shape']).astype(np.int64)


def rounded_shift(value, shift):
    if not np.all((shift > 0) & (shift < 63)):
        raise ValueError('B007 expects a positive shift below 63')
    magnitude = np.abs(value)
    quotient = np.right_shift(magnitude, shift)
    remainder = magnitude - np.left_shift(quotient, shift)
    half = np.left_shift(np.ones_like(shift), shift - 1)
    quotient += (remainder > half) | ((remainder == half) & ((quotient & 1) != 0))
    return np.where(value < 0, -quotient, quotient)


def convolution(pixels, weights, bias):
    kernel = weights.shape[-1]
    pad = kernel // 2
    padded = np.pad(pixels, ((0, 0), (pad, pad), (pad, pad)))
    accum = np.broadcast_to(bias[:, None, None], pixels.shape).copy()
    for y in range(kernel):
        for x in range(kernel):
            accum += padded[:, y:y + 32, x:x + 32] * weights[:, 0, y, x, None, None]
    if np.any(accum < -(1 << 31)) or np.any(accum > (1 << 31) - 1):
        raise OverflowError('bias-included accumulator exceeds signed32')
    return accum


def requantize_independent(accum, params):
    multiplier = load_record(params['multiplier_file'])[:, None, None]
    shift = load_record(params['shift_file'])[:, None, None]
    if int(np.max(np.abs(accum))) * int(np.max(np.abs(multiplier))) >= 1 << 63:
        raise OverflowError('requant product exceeds signed64')
    return np.clip(rounded_shift(accum * multiplier, shift), -32767, 32767)


def main():
    raw = (BASE / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError('frozen B007 manifest changed')
    manifest = json.loads(raw)
    edge = rounded_shift(np.array([-5, -3, -1, 1, 3, 5], dtype=np.int64),
                         np.ones(6, dtype=np.int64))
    if not np.array_equal(edge, [-2, -2, 0, 0, 2, 2]):
        raise AssertionError('signed ties-even edge check failed')
    p3 = manifest['stage2_jtag_parameters']['dw3']
    p7 = manifest['stage2_jtag_parameters']['dw7']
    w3, b3 = load_record(p3['weight_file']), load_record(p3['bias_i32_file'])
    w7, b7 = load_record(p7['weight_file']), load_record(p7['bias_i32_file'])
    rows = []
    for row in manifest['results']:
        files = row['files']
        a3 = convolution(load_record(files['pre_dw3_i16']), w3, b3)
        q3 = requantize_independent(a3, p3['requant_to_dw7'])
        a7 = convolution(q3, w7, b7)
        q7 = requantize_independent(a7, p7['requant_to_stage3'])
        for name, actual in [('dw3_with_bias_i32', a3), ('dw3_middle_i16', q3),
                             ('dw3_residual_i16', q3), ('dw7_with_bias_i32', a7),
                             ('dw7_stage3_i16', q7)]:
            if not np.array_equal(actual, load_record(files[name])):
                raise AssertionError(row['sample_id'] + ': ' + name)
        packet = a3.astype('<i4').tobytes() + a7.astype('<i4').tobytes()
        digest = hashlib.sha256(packet).hexdigest()
        if len(packet) != 1048576 or digest != files['dual_accumulator_packet']['sha256']:
            raise AssertionError('packet differs: ' + row['sample_id'])
        rows.append({'sample': row['sample_id'], 'packet_sha256': digest,
                     'int32_bias_included_values_checked': int(a3.size + a7.size),
                     'int16_requant_values_checked': int(q3.size + q7.size),
                     'exact_match': True})
    print(json.dumps({'status': 'INDEPENDENT_HOST_ARITHMETIC_PASS_NOT_PL',
                      'manifest_sha256': MANIFEST_SHA,
                      'checker_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'cases': rows}, indent=2))


if __name__ == '__main__':
    main()
