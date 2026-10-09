"""Zero-point-zero INT8 post-operation contract for future PL implementation.

No board I/O. Bias is added to INT32 accumulators with checked range, then each
channel uses a positive Q31 multiplier, right shift with ties-to-even, and
saturation to [-127,127]. Coefficient approximation is separate from rounding.
"""
import math
import numpy as np


def multiplier_shift(ratio):
    """Approximate positive finite ratio as multiplier / 2**shift."""
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError('ratio must be positive finite')
    fraction, exponent = math.frexp(ratio)
    multiplier = round(fraction * (1 << 31))
    if multiplier == (1 << 31):
        multiplier >>= 1
        exponent += 1
    shift = 31 - exponent
    if not 0 <= shift <= 62:
        raise ValueError('ratio outside this prototype coefficient range')
    return multiplier, shift


def round_shift_even(product, shift):
    """Signed INT64 product within +/-2**62; right shift, nearest ties even."""
    x = np.asarray(product)
    if x.dtype.kind not in 'iu' or (x.dtype.kind == 'u' and np.any(x > (1 << 62))):
        raise ValueError('requires bounded integer products')
    x = x.astype(np.int64)
    if not 0 <= shift <= 62 or np.any(x < -(1 << 62)) or np.any(x > (1 << 62)):
        raise ValueError('invalid shift or product range')
    if shift == 0:
        return x.copy()
    magnitude = np.abs(x)
    divisor = np.int64(1 << shift)
    quotient, remainder = magnitude // divisor, magnitude % divisor
    half = divisor // 2
    increment = (remainder > half) | ((remainder == half) & ((quotient & 1) != 0))
    result = quotient + increment.astype(np.int64)
    return np.where(x < 0, -result, result)


def requantize(accumulator, bias, multipliers, shifts):
    """Input [...,N], per-N bias/multiplier/shift; return symmetric int8."""
    a = np.asarray(accumulator)
    b = np.asarray(bias)
    mult = np.asarray(multipliers)
    shift = np.asarray(shifts)
    if a.ndim < 1 or any(x.dtype.kind not in 'iu' for x in (a,b,mult,shift)):
        raise ValueError('integer accumulator and coefficient arrays required')
    n = a.shape[-1]
    if any(x.shape != (n,) for x in (b,mult,shift)):
        raise ValueError('per-channel coefficient shape mismatch')
    i32 = np.iinfo(np.int32)
    if (np.any(a < i32.min) or np.any(a > i32.max) or
            np.any(b < i32.min) or np.any(b > i32.max) or
            np.any(mult <= 0) or np.any(mult > i32.max) or
            np.any(shift < 0) or np.any(shift > 62)):
        raise ValueError('coefficient or accumulator outside contract')
    total = a.astype(np.int64) + b.astype(np.int64)
    if np.any(total < i32.min) or np.any(total > i32.max):
        raise OverflowError('bias plus accumulator exceeds INT32')
    out = np.empty(a.shape, np.int8)
    for channel in range(n):
        product = total[...,channel] * np.int64(mult[channel])
        rounded = round_shift_even(product, int(shift[channel]))
        out[...,channel] = np.clip(rounded,-127,127).astype(np.int8)
    return out


def gelu_lut(input_scale, output_scale):
    """256 entries; index is the unsigned byte representation of signed int8.

    Input has already been requantized to INT8. The -128 entry is defined even
    though symmetric quantization normally emits only [-127,127].
    """
    if any(not math.isfinite(s) or s <= 0 for s in (input_scale,output_scale)):
        raise ValueError('scales must be positive finite')
    table=[]
    for byte in range(256):
        signed = byte if byte < 128 else byte-256
        x=signed*input_scale
        y=0.5*x*(1+math.erf(x/math.sqrt(2)))
        q=max(-127,min(127,round(y/output_scale)))
        table.append(q)
    return np.array(table,np.int8)
