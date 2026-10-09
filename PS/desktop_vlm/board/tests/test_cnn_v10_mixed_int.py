from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "desktop_vlm" / "board"))

from cnn_v10_mixed_int import (Conv, accumulator_bound, error_metrics,
                               load_n1_contract, quantize_a16,
                               quantize_w8_per_output)

MODEL = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-release-bundle-003/models/network1-bridge.onnx"


def test_real_frozen_n1_contract():
    dw, pw, contract = load_n1_contract(MODEL)
    assert contract["input_shape"] == [1, 64, 64, 64]
    assert contract["output_shape"] == [1, 128, 32, 32]
    assert dw.weight.shape == (128, 1, 7, 7) and dw.group == 64 and dw.stride == (2, 2)
    assert pw.weight.shape == (128, 128, 1, 1)


def test_signed32_reduction_bounds_cover_n1():
    dw = accumulator_bound(7 * 7)
    pw = accumulator_bound(128)
    assert dw["worst_case_abs"] == 205_520_896
    assert pw["worst_case_abs"] == 536_870_912
    assert dw["fits_signed32"] and pw["fits_signed32"]
    assert accumulator_bound(511)["fits_signed32"]
    assert not accumulator_bound(512)["fits_signed32"]


def test_ties_even_symmetric_quantization_and_wide_intermediate():
    values = np.array([-2.5, -1.5, -0.5, 0.5, 1.5, 2.5], dtype=np.float32)
    assert quantize_a16(values, 1.0).tolist() == [-2, -2, 0, 0, 2, 2]
    q, scales = quantize_w8_per_output(np.array([[[[0.0, 1.0]]], [[[0.0, 2.0]]]], dtype=np.float32))
    assert q.reshape(2, -1).tolist() == [[0, 127], [0, 127]]
    assert scales[1] == pytest.approx(scales[0] * 2)


def test_grouped_conv_accumulator_matches_scalar_exactly():
    from cnn_v10_mixed_int import _conv_accumulate
    conv = Conv("depthwise-multiplier-test", "x", "y",
                np.array([[[[1]]], [[[2]]], [[[3]]], [[[4]]]], dtype=np.float32),
                np.zeros(4, dtype=np.float32), (1, 1), (0, 0, 0, 0), 2)
    x = np.array([[[[2]], [[-3]]]], dtype=np.int16)
    qweight = np.array([[[[1]]], [[[2]]], [[[3]]], [[[4]]]], dtype=np.int8)
    actual = _conv_accumulate(x, conv, qweight)
    assert actual.tolist() == [[[[2]], [[4]], [[-9]], [[-12]]]]


def test_sensitive_channel_fallback_uses_only_dequantized_a16_input():
    from cnn_v10_mixed_int import _run_conv
    conv = Conv("fp32-weight-fallback", "x", "y",
                np.array([[[[0.5]], [[-1.25]]]], dtype=np.float32),
                np.array([0.125], dtype=np.float32), (1, 1), (0, 0, 0, 0), 1)
    qx = np.array([[[[2]], [[-4]]]], dtype=np.int16)
    y, proof = _run_conv(qx, 0.25, conv, fp32_channels=[0])
    expected = (qx.astype(np.float32) * 0.25 * conv.weight.reshape(1, 2, 1, 1)).sum(axis=1, keepdims=True) + 0.125
    np.testing.assert_array_equal(y, expected)
    assert proof["fp32_weight_output_channels"] == [0]


def test_error_gate_metrics_are_finite_and_directional():
    ref = np.array([1.0, 0.0, -1.0], dtype=np.float32)
    same = error_metrics(ref, ref.copy())
    opposite = error_metrics(ref, -ref)
    assert same["max_abs"] == 0 and same["cosine"] == pytest.approx(1.0)
    assert opposite["cosine"] == pytest.approx(-1.0)

