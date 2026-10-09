"""Frozen HOST contract helpers for the experimental signed-16 weight ABI.

This module is deliberately separate from the v4 INT8-weight pack and oracle.
It defines layouts and checked wide arithmetic only; it is not PL evidence.
"""
from __future__ import annotations

import math
import numpy as np

PROFILES = {
    0: {"channels": 128, "width": 32, "blocks": 12},
    1: {"channels": 256, "width": 16, "blocks": 20},
    2: {"channels": 64, "width": 64, "blocks": 4},
}
ABI_MAGIC = "FZV5"
ABI_VERSION = 0x00050000
FLAGS = 0
I16_MAX = 32767
I48_MIN, I48_MAX = -(1 << 47), (1 << 47) - 1


def expected_stride(channels: int) -> int:
    if channels not in (64, 128, 256):
        raise ValueError("v5 supports C=64,128,256")
    pw1 = math.ceil(3 * channels / 6) * (channels // 16)
    pw2 = math.ceil(channels / 6) * (3 * channels // 16)
    return 220 * channels + 16 + 131072 + 192 * (pw1 + pw2)


def layout(channels: int):
    """Return naturally 16-byte-aligned fields and exact per-block stride."""
    pw1 = math.ceil(3 * channels / 6) * (channels // 16)
    pw2 = math.ceil(channels / 6) * (3 * channels // 16)
    fields, offset = [], 0

    def add(name, size, dtype, shape, note=""):
        nonlocal offset
        if offset % 16:
            raise AssertionError(f"unaligned field {name} at {offset}")
        fields.append({"name": name, "offset": offset, "bytes": size,
                       "dtype": dtype, "shape": list(shape), "note": note})
        offset += size

    add("dw3_weights_i16", 18 * channels, "i16le", (channels, 9))
    add("dw7_weights_i16", 98 * channels, "i16le", (channels, 49))
    add("bias_i64", 48 * channels, "i64le", (6 * channels,), "signed-48 checked")
    add("multiplier_i32", 24 * channels, "i32le", (6 * channels,))
    add("shift_i32", 24 * channels, "i32le", (6 * channels,), "range 0..62")
    add("scale_multiplier_i32", 4 * channels, "i32le", (channels,))
    add("scale_shift_i32", 4 * channels, "i32le", (channels,), "range 0..62")
    add("residual_q31_and_pad", 16, "i32le+i32le+zero[8]", (16,))
    add("gelu_lut_i16", 131072, "i16le", (65536,))
    add("pw1_tiles_i16", 192 * pw1, "i16le", (pw1, 6, 16),
        "6 outputs x 16 reductions; group-major, reduction-major")
    add("pw2_tiles_i16", 192 * pw2, "i16le", (pw2, 6, 16),
        "6 outputs x 16 reductions; group-major, reduction-major")
    stride = expected_stride(channels)
    if offset != stride:
        raise AssertionError(f"layout {offset} != stride formula {stride}")
    return fields, stride


def pack_pw_i16(matrix, outputs: int, inputs: int) -> bytes:
    a = np.asarray(matrix)
    if a.shape != (outputs, inputs) or a.dtype != np.dtype("<i2"):
        raise ValueError("PW weight matrix must be little-endian int16 OI")
    if inputs % 16:
        raise ValueError("PW reduction width must be divisible by 16")
    words = []
    for group in range(math.ceil(outputs / 6)):
        for red in range(inputs // 16):
            tile = np.zeros((6, 16), dtype="<i2")
            first = group * 6
            valid = min(6, outputs - first)
            tile[:valid] = a[first:first + valid, red * 16:(red + 1) * 16]
            words.append(tile.tobytes(order="C"))
    return b"".join(words)


def checked_i48(value, what="value") -> int:
    result = int(value)
    if result < I48_MIN or result > I48_MAX:
        raise OverflowError(f"{what}={result} does not fit signed 48-bit")
    return result


def q31_round_even_wide(value: int, multiplier: int, shift: int) -> int:
    """Exact Python-integer signed product and nearest/ties-even shift."""
    a, m, s = int(value), int(multiplier), int(shift)
    if not -(1 << 47) <= a < (1 << 47):
        raise OverflowError("Q31 input is outside signed 48-bit")
    if not -(1 << 31) <= m < (1 << 31):
        raise OverflowError("Q31 multiplier does not fit signed int32")
    if not 0 <= s <= 62:
        raise ValueError("Q31 shift must be in 0..62")
    product = a * m  # Python int: exact signed 80-bit-or-wider intermediate.
    if s == 0:
        return product
    magnitude = abs(product)
    q, r = divmod(magnitude, 1 << s)
    half = 1 << (s - 1)
    if r > half or (r == half and (q & 1)):
        q += 1
    return -q if product < 0 else q


def quantize_symmetric_i16(values, scale):
    if not math.isfinite(float(scale)) or float(scale) <= 0:
        raise ValueError("activation scale must be positive finite")
    v = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(v)):
        raise ValueError("activation contains nonfinite values")
    return np.clip(np.rint(v / float(scale)), -I16_MAX, I16_MAX).astype("<i2")


def quantize_weight_i16_per_output(weight):
    w = np.asarray(weight, dtype=np.float64)
    if w.ndim < 2 or not np.all(np.isfinite(w)):
        raise ValueError("weights must be finite OI... tensor")
    axes = tuple(range(1, w.ndim))
    maxima = np.max(np.abs(w), axis=axes)
    scales = np.where(maxima > 0, maxima / I16_MAX, 1.0)
    shape = (len(scales),) + (1,) * (w.ndim - 1)
    q = np.clip(np.rint(w / scales.reshape(shape)), -I16_MAX, I16_MAX).astype("<i2")
    return q, scales


def audit_bound(weights, input_abs_bound, bias):
    """Compute exact conservative per-output abs bound using Python ints."""
    w = np.asarray(weights)
    b = np.asarray(bias).reshape(-1)
    if w.shape[0] != b.size:
        raise ValueError("bias/output-channel mismatch")
    result = []
    for oc in range(w.shape[0]):
        bound = abs(int(b[oc])) + int(input_abs_bound) * sum(abs(int(x)) for x in w[oc].reshape(-1))
        result.append(checked_i48(bound, f"channel {oc} accumulator bound"))
    return result
