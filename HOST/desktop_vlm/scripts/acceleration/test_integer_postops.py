from fractions import Fraction
import numpy as np
import pytest
import torch

from integer_postops import gelu_lut, multiplier_shift, requantize, round_shift_even


def test_signed_ties_and_extreme_products_against_exact_rational():
    rng=np.random.default_rng(719)
    values=np.concatenate([np.arange(-101,102,dtype=np.int64),
                           rng.integers(-(1<<62),1<<62,size=200,dtype=np.int64),
                           np.array([-(1<<62),1<<62],np.int64)])
    for shift in (0,1,2,7,15,31,61,62):
        expected=[round(Fraction(int(v),1<<shift)) for v in values]
        np.testing.assert_array_equal(round_shift_even(values,shift),expected)


def test_coefficients_represent_exact_binary_ratios():
    for ratio in (0.125,0.5,1.,2.,128.):
        m,s=multiplier_shift(ratio)
        assert Fraction(m,1<<s)==Fraction(ratio)


def test_bias_channel_scales_and_clipping():
    a=np.array([[-11,5,1000],[11,-5,-1000]],np.int32)
    bias=np.array([1,1,0],np.int32)
    coefficients=[multiplier_shift(r) for r in (0.5,2.,1.)]
    m,s=map(np.array,zip(*coefficients))
    np.testing.assert_array_equal(requantize(a,bias,m,s),[[-5,12,127],[6,-8,-127]])


def test_bias_overflow_is_not_silently_wrapped():
    m,s=multiplier_shift(0.5)
    with pytest.raises(OverflowError):
        requantize(np.array([[2147483647]],np.int32),np.array([1],np.int32),
                   np.array([m]),np.array([s]))


def test_all_256_gelu_entries_against_pytorch_float64():
    signed=np.array([x if x<128 else x-256 for x in range(256)],np.float64)
    for input_scale,output_scale in ((0.03125,0.02),(0.003,0.005),(0.1,0.03)):
        x=torch.from_numpy(signed*input_scale)
        expected=torch.round(torch.nn.functional.gelu(x,approximate='none')/output_scale)
        expected=expected.clamp(-127,127).to(torch.int8).numpy()
        np.testing.assert_array_equal(gelu_lut(input_scale,output_scale),expected)


@pytest.mark.parametrize('ratio',[0,-1,float('nan'),float('inf'),1e-50,1e50])
def test_invalid_or_unsupported_ratio_rejected(ratio):
    with pytest.raises(ValueError):
        multiplier_shift(ratio)
