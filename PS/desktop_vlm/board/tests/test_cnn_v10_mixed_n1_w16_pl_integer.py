import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cnn_v10_mixed_n1_w16_pl_integer import (A16_MAX, S16_MIN, _q31_params,
    _requant_lut, _round_even_ratio)
from cnn_v10_mixed_n1_w16 import quantize_w16_per_output


def test_integer_ties_even_division_is_symmetric_and_exact():
    assert [_round_even_ratio(v, 2) for v in (1, 3, 5, -1, -3, -5)] == [0, 2, 2, 0, -2, -2]
    assert _round_even_ratio(7, 4) == 2
    assert _round_even_ratio(9, 4) == 2
    assert _round_even_ratio(-7, 4) == -2


def test_q31_uses_signed_multiplier_with_explicit_shift():
    multiplier, shift = _q31_params(0.25)
    assert (multiplier, shift) == (1 << 29, 31)


def test_requant_round_clip_then_lookup_matches_scalar_codes():
    accum = np.asarray([[[[3, 5, -3, -5, 2]]]], dtype=np.int64)
    params = {"bias_q": np.asarray([0]), "multipliers": np.asarray([1]),
              "shifts": np.asarray([1])}
    lut = np.arange(S16_MIN, S16_MIN + 65536, dtype="<i2")
    output, proof = _requant_lut(accum, params, lut)
    np.testing.assert_array_equal(output.ravel(), np.asarray([2, 2, -2, -2, 1], dtype=np.int16))
    assert proof["bias_signed48"] and proof["product_signed80"]


def test_w16_per_output_quantization_uses_signed_symmetric_domain():
    weight = np.asarray([[[[1.0, -0.5]]], [[[0.0, 0.0]]]], dtype=np.float32)
    q, scales = quantize_w16_per_output(weight)
    assert q.dtype == np.int16
    assert int(q[0, 0, 0, 0]) == 32767
    assert int(q[0, 0, 0, 1]) == -16384
    assert int(q[1, 0, 0, 0]) == 0
    assert np.all(np.abs(q.astype(np.int32)) <= A16_MAX)
    assert np.all(scales > 0)
