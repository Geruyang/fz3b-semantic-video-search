"""Recompute frozen Stage3 integer boundaries independently; host evidence only."""
import hashlib
import json
from pathlib import Path

import numpy as np
from check_stage2_b007 import rounded_shift


BASE = Path('artifacts/board-debug-20261004/acceleration/host')
SOURCE = BASE / 'stage3-network20-int16-004'
PREVIOUS = BASE / 'stage2-dw3-dw7-int16act-007'
EXPECTED_SHA = '164fdff3ab1a09e0b6282f4281ed09e7846cb44ace36ddbdca86ab57237e94c7'


def main():
    blob = (SOURCE / 'manifest.json').read_bytes()
    if hashlib.sha256(blob).hexdigest() != EXPECTED_SHA:
        raise ValueError('Stage3 manifest changed')
    manifest = json.loads(blob)

    def read(name, dtype, shape=None, record=None, previous=False):
        metadata = record or manifest['files'][name]
        data = ((PREVIOUS if previous else SOURCE) / name).read_bytes()
        if len(data) != metadata['bytes'] or hashlib.sha256(data).hexdigest() != metadata['sha256']:
            raise ValueError('frozen bytes changed: ' + name)
        values = np.frombuffer(data, dtype=dtype).astype(np.int64)
        return values.reshape(shape) if shape else values

    def rescale(values, prefix):
        mult = read(prefix + 'multiplier.i32', '<i4')[:, None]
        shift = read(prefix + 'shift.i32', '<i4')[:, None]
        if int(np.max(np.abs(values))) * int(np.max(np.abs(mult))) >= 1 << 63:
            raise OverflowError('signed64 product')
        return rounded_shift(values * mult, shift)

    def pw(values, kin, kout):
        prefix = 'stage3-pw%d-to-%d-' % (kin, kout)
        # Historical filename says kn; the manifest stores [output, input].
        weight = read(prefix + 'weights-kn.i8', 'i1', (kout, kin))
        accum = np.broadcast_to(read(prefix + 'bias.i32', '<i4')[:, None], (kout, 1024)).copy()
        # Explicit outer-product reduction, independent of the oracle GEMM.
        for index in range(kin):
            accum += weight[:, index, None] * values[index, None, :]
        if np.any(accum < -(1 << 31)) or np.any(accum > (1 << 31) - 1):
            raise OverflowError('signed32 accumulator')
        return accum, np.clip(rescale(accum, prefix + 'requant-'), -32767, 32767)

    lut = read('stage3-gelu-int16-lut.i16le', '<i2')
    results = []
    for row in manifest['results']:
        name = row['sample_id']
        files = row['files']
        q7_meta = files['pw128_input_q7_i16']
        q3_meta = files['residual_q3_i16']
        q7 = read(q7_meta['path'], '<i2', (128, 1024), q7_meta, True)
        q3 = read(q3_meta['path'], '<i2', (128, 1024), q3_meta, True)
        a1, q1 = pw(q7, 128, 384)
        gelu = lut[q1 + 32768]
        a2, q2 = pw(gelu, 384, 128)
        scaled = rescale(q2, 'stage3-scale-add-')
        residual = rescale(q3, 'stage3-residual-')
        output = np.clip(scaled + residual, -32767, 32767)
        checks = [('fc1-with-bias.i32', a1, '<i4'), ('fc1-output.i16', q1, '<i2'),
                  ('gelu-output.i16', gelu, '<i2'), ('fc2-with-bias.i32', a2, '<i4'),
                  ('fc2-output.i16', q2, '<i2'), ('scale-branch.i32', scaled, '<i4'),
                  ('residual-branch.i32', residual, '<i4'), ('block-add-output.i16', output, '<i2')]
        for suffix, actual, dtype in checks:
            expected = read(name + '-stage3-' + suffix, dtype, actual.shape)
            if not np.array_equal(actual, expected):
                raise AssertionError(name + ': ' + suffix)
        packet = output.astype('<i2').tobytes()
        digest = hashlib.sha256(packet).hexdigest()
        if digest != manifest['files'][name + '-stage3-single-output-packet.i16le']['sha256']:
            raise AssertionError('output packet differs')
        results.append({'sample': name, 'boundaries_checked': len(checks),
                        'integer_values_checked': sum(item[1].size for item in checks),
                        'output_bytes': len(packet), 'output_sha256': digest, 'exact_match': True})
    print(json.dumps({'status': 'INDEPENDENT_HOST_ARITHMETIC_PASS_NOT_PL',
                      'manifest_sha256': EXPECTED_SHA,
                      'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'rounding_helper_sha256': hashlib.sha256(Path(__file__).with_name('check_stage2_b007.py').read_bytes()).hexdigest(),
                      'gelu_scope': 'Frozen LUT indexing checked; LUT generation and model accuracy not certified here.',
                      'cases': results}, indent=2))


if __name__ == '__main__':
    main()
