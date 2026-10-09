"""Bound frozen INT16 x INT8 accumulators over the whole signed input domain."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOST = ROOT / 'artifacts/board-debug-20261004/acceleration/host'
FIXTURES = {
    2: ('stage2-dw3-dw7-int16act-007', '68e2a29131ca0965783b00eea54049c313de669e1c758b738f4c530bb78cd282'),
    3: ('stage3-network20-int16-004', '164fdff3ab1a09e0b6282f4281ed09e7846cb44ace36ddbdca86ab57237e94c7'),
}


def check():
    manifests = {}
    for stage, (directory, sha) in FIXTURES.items():
        raw = (HOST / directory / 'manifest.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('Frozen manifest changed')
        manifests[stage] = json.loads(raw)

    def values(stage, filename, fmt):
        raw = (HOST / FIXTURES[stage][0] / filename).read_bytes()
        meta = manifests[stage]['files'][filename]
        if len(raw) != meta['bytes'] or hashlib.sha256(raw).hexdigest() != meta['sha256']:
            raise ValueError('Parameter changed: ' + filename)
        return [item[0] for item in struct.iter_unpack(fmt, raw)]

    records = []
    for stage, prefix, weight_name, count, terms in (
            (2, 'dw3-', 'weights-chw.i8', 128, 9),
            (2, 'dw7-', 'weights-chw.i8', 128, 49),
            (3, 'stage3-pw128-to-384-', 'weights-kn.i8', 384, 128),
            (3, 'stage3-pw384-to-128-', 'weights-kn.i8', 128, 384)):
        weights = values(stage, prefix + weight_name, '<b')
        bias = values(stage, prefix + 'bias.i32', '<i')
        if len(weights) != count * terms or len(bias) != count:
            raise ValueError('Unexpected parameter shape')
        # A triangle bound covers every partial sum as well as the final sum,
        # including the external signed INT16 value -32768 (PS clips to -32767).
        bounds = [abs(bias[c]) + 32768 * sum(abs(w) for w in weights[c * terms:(c + 1) * terms])
                  for c in range(count)]
        maximum = max(bounds)
        if maximum > 2147483647:
            raise ValueError('INT32 accumulator cannot be guaranteed: ' + prefix)
        records.append({'layer': prefix.rstrip('-'), 'outputs': count,
                        'terms_per_output': terms, 'max_abs_partial_sum_bound': maximum,
                        'worst_channel': bounds.index(maximum),
                        'int32_headroom': 2147483647 - maximum})
    return {'status': 'FROZEN_INT32_ACCUMULATOR_BOUND_PASS', 'input_abs_bound': 32768,
            'layers': records,
            'requant_product_abs_bound': 2147483648 * 2147483648,
            'requant_product_fits_signed64': 2147483648 * 2147483648 < 2 ** 63,
            'scope': 'Static arithmetic bound for frozen weights/bias and signed INT16 inputs. Not timing, accuracy, synthesis, or board evidence.'}


if __name__ == '__main__':
    report = check()
    out = HOST / 'stage23-accumulator-bounds.json'
    out.write_bytes((json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps(report, indent=2))
