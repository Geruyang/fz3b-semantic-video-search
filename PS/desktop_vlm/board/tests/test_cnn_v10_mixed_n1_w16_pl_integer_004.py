import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cnn_v10_mixed_n1_w16_pl_integer as oracle
from cnn_v10_mixed_n1_w16_pl_integer_004 import (
    _requant_lut_frozen, _tables, build_candidate_packed, canonical_q31_from_fixed31, normalized_q31,
    verify_candidate_packed)
from cnn_v10_mixed_n1_w16_pl_integer_004 import _frozen_multiplier_shift


def test_direct_q31_uses_frozen_multiplier_shift_and_declared_windows():
    for ratio in (0.001, 0.003, 0.01):
        m, s = normalized_q31(ratio, (35, 42))
        assert (m, s) == _frozen_multiplier_shift(ratio)
    with pytest.raises((OverflowError, ValueError)):
        normalized_q31(1e-12, (35, 42))


def test_canonical_fixed31_rescale_preserves_exact_rational_coefficient():
    original_multiplier, original_shift = 1234567, 31
    multiplier, shift = canonical_q31_from_fixed31(original_multiplier, original_shift, (35, 42))
    assert shift == 35
    assert Fraction(original_multiplier, 1 << original_shift) == Fraction(multiplier, 1 << shift)


def test_folded_gelu_reconstructs_all_codes_and_zero_exactly():
    for scale in (0.0005223256885074079, 0.00009687628574169352):
        full, negative, reconstructed, bad = _tables(scale, scale)
        assert len(full) == len(reconstructed) == 65536
        assert len(negative) == 32768
        assert bad.size == 0
        assert int(reconstructed[32768]) == 0


def test_wide_frozen_q31_rounding_matches_existing_oracle():
    accum = np.asarray([[[[5, 7, -5, -7]], [[3, -3, 11, -11]]]], dtype=np.int64)
    params = {"bias_q": np.asarray([1, -2]), "multipliers": np.asarray([1 << 29, 1 << 28]),
              "shifts": np.asarray([30, 29])}
    lut = np.arange(-32768, 32768, dtype="<i2")
    got, _ = _requant_lut_frozen(accum, params, lut)
    old, _ = oracle._requant_lut(accum, params, lut)
    np.testing.assert_array_equal(got, old)


def _dummy_params():
    return {"dw_w8": np.zeros((128, 1, 7, 7), np.int8),
        "dw_bias_q48": np.zeros(128, np.int64), "dw_q31_multiplier": np.ones(128, np.int64),
        "dw_q31_shift": np.full(128, 35, np.int64),
        "pw_w8": np.zeros((128, 128, 1, 1), np.int8), "pw_w16_channels": np.asarray([1, 2, 3, 4, 5, 6, 7]),
        "pw_w16": np.zeros((7, 128, 1, 1), np.int16), "pw_bias_q48": np.zeros(128, np.int64),
        "pw_q31_multiplier": np.ones(128, np.int64), "pw_q31_shift": np.full(128, 36, np.int64)}


def test_candidate_packer_layout_size_and_roundtrip():
    packed, layout = build_candidate_packed(_dummy_params(), np.zeros(32768, dtype="<i2"),
                                             np.zeros(32768, dtype="<i2"))
    assert len(packed) == 180480
    assert layout["dw_weights_i16"]["word_offset"] == 0
    assert layout["pw_weights_i16"]["word_offset"] == 5008
    assert layout["pw_gelu_negative_half_i16"]["word_offset"] == 7184
    receipt = verify_candidate_packed(packed, layout)
    assert receipt["pass"] and receipt["total_bytes"] == 180480
    damaged = bytearray(packed)
    damaged[0] = 1
    with pytest.raises(AssertionError):
        verify_candidate_packed(bytes(damaged), layout)
