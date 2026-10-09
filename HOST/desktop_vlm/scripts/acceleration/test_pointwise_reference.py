"""Numerical boundary checks independent of the model fixture experiment."""
import numpy as np
import pytest

from prepare_pointwise import quantize, symmetric_scale


def test_round_ties_and_saturation():
    x = np.array([-1000, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 1000])
    assert quantize(x, 1.0).tolist() == [-127, -2, -2, 0, 0, 2, 2, 127]


def test_per_output_channel_scale_not_input_channel():
    weights_kn = np.array([[127., 0.], [-63.5, 254.], [0., -127.]])
    scale = symmetric_scale(weights_kn, axis=0)
    np.testing.assert_array_equal(scale, [1., 2.])
    np.testing.assert_array_equal(quantize(weights_kn, scale), [[127, 0], [-64, 127], [0, -64]])


def test_zero_channel_is_exactly_zero():
    x = np.zeros((7, 3), dtype=np.float32)
    scale = symmetric_scale(x, axis=0)
    np.testing.assert_array_equal(scale, np.ones(3))
    np.testing.assert_array_equal(quantize(x, scale), np.zeros((7, 3), dtype=np.int8))


@pytest.mark.parametrize('x,scale', [([np.nan], 1), ([np.inf], 1), ([1], 0), ([1], -1), ([1], np.nan)])
def test_invalid_numeric_contract_is_rejected(x, scale):
    with pytest.raises(ValueError):
        quantize(np.array(x), scale)
