"""Independent packed-W16 stripe oracle for the v7 shared sequential core."""

import math

import numpy as np

import cnn_shared_v7_contract as v7c
import cnn_w16_contract as w16
from cnn_w16_fixture import q31_tensor_wide


def _field_map(channels):
    fields, stride = w16.layout(channels)
    return {item["name"]: item for item in fields}, stride


def _array(blob, field, dtype, shape):
    count = int(np.prod(shape))
    result = np.frombuffer(blob, dtype=dtype, count=count,
                           offset=int(field["offset"])).copy()
    return result.reshape(shape)


def _unpack_pw(blob, field, outputs, inputs):
    groups = int(math.ceil(float(outputs) / 6.0))
    reductions = inputs // 16
    tiles = _array(blob, field, "<i2", (groups, reductions, 6, 16))
    result = np.zeros((outputs, inputs), dtype="<i2")
    for group in range(groups):
        valid = min(6, outputs - group * 6)
        for reduction in range(reductions):
            result[group * 6:group * 6 + valid,
                   reduction * 16:(reduction + 1) * 16] = \
                tiles[group, reduction, :valid, :]
    return result


def decode_w16_block(payload, profile):
    """Decode one legacy W16 block without changing its byte representation."""
    spec = v7c.profile_spec(profile)
    channels = spec["channels"]
    fields, stride = _field_map(channels)
    blob = bytes(payload)
    if len(blob) != stride:
        raise ValueError("packed W16 block has wrong byte size")
    biases = _array(blob, fields["bias_i64"], "<i8", (6 * channels,))
    multipliers = _array(blob, fields["multiplier_i32"], "<i4", (6 * channels,))
    shifts = _array(blob, fields["shift_i32"], "<i4", (6 * channels,))
    if np.any(shifts < 0) or np.any(shifts > 62):
        raise ValueError("packed operation shift is outside 0..62")
    if np.any(biases < -(1 << 47)) or np.any(biases >= (1 << 47)):
        raise ValueError("packed bias is outside signed48")
    scale_multiplier = _array(blob, fields["scale_multiplier_i32"], "<i4", (channels,))
    scale_shift = _array(blob, fields["scale_shift_i32"], "<i4", (channels,))
    if np.any(scale_shift < 0) or np.any(scale_shift > 62):
        raise ValueError("packed scale shift is outside 0..62")
    residual_raw = blob[fields["residual_q31_and_pad"]["offset"]:
                        fields["residual_q31_and_pad"]["offset"] + 16]
    residual_words = np.frombuffer(residual_raw, dtype="<i4").copy()
    if residual_words[1] < 0 or residual_words[1] > 62:
        raise ValueError("packed residual shift is outside 0..62")
    if any(residual_raw[8:]):
        raise ValueError("packed residual padding must be zero")

    slices = {
        "dw3": slice(0, channels),
        "dw7": slice(channels, 2 * channels),
        "pw1": slice(2 * channels, 5 * channels),
        "pw2": slice(5 * channels, 6 * channels),
    }
    weights = {
        "dw3": _array(blob, fields["dw3_weights_i16"], "<i2",
                      (channels, 1, 3, 3)),
        "dw7": _array(blob, fields["dw7_weights_i16"], "<i2",
                      (channels, 1, 7, 7)),
        "pw1": _unpack_pw(blob, fields["pw1_tiles_i16"], 3 * channels, channels),
        "pw2": _unpack_pw(blob, fields["pw2_tiles_i16"], channels, 3 * channels),
    }
    layers = {}
    for name in ("dw3", "dw7", "pw1", "pw2"):
        section = slices[name]
        layers[name] = {
            "weights": weights[name],
            "bias": biases[section].astype(object),
            "multiplier": multipliers[section].copy(),
            "shift": shifts[section].copy(),
            "full_range_abs_bound": [0] * weights[name].shape[0],
        }
    return {
        "layers": layers,
        "scale_multiplier": scale_multiplier,
        "scale_shift": scale_shift,
        "residual_multiplier": residual_words[0:1],
        "residual_shift": residual_words[1:2],
        "gelu": _array(blob, fields["gelu_lut_i16"], "<i2", (65536,)),
        "packed_bytes": len(blob),
        "profile": int(profile),
    }


def _requantized(raw, layer):
    bias = np.asarray(layer["bias"], dtype=np.int64).reshape(-1, 1, 1)
    total = np.asarray(raw, dtype=np.int64) + bias
    if np.any(total < -(1 << 47)) or np.any(total >= (1 << 47)):
        raise OverflowError("stripe accumulator exceeds signed48")
    return q31_tensor_wide(total, layer["multiplier"], layer["shift"],
                           (-32767, 32767))


def _depthwise_global_rows(source, layer, row_start, row_end):
    x = np.asarray(source, dtype="<i2")
    weights = np.asarray(layer["weights"], dtype="<i2")
    channels, height, width = x.shape
    if height != width or weights.shape[0:2] != (channels, 1):
        raise ValueError("depthwise source/weight shape mismatch")
    kernel = weights.shape[2]
    if weights.shape[3] != kernel or kernel not in (3, 7):
        raise ValueError("depthwise kernel must be square K3 or K7")
    if row_start < 0 or row_end > height or row_end <= row_start:
        raise ValueError("depthwise output row range is invalid")
    radius = kernel // 2
    padded = np.pad(x.astype(np.int64),
                    ((0, 0), (radius, radius), (radius, radius)))
    raw = np.zeros((channels, row_end - row_start, width), dtype=np.int64)
    for ky in range(kernel):
        for kx in range(kernel):
            raw += (padded[:, row_start + ky:row_end + ky, kx:kx + width] *
                    weights[:, 0, ky, kx].astype(np.int64)[:, None, None])
    return _requantized(raw, layer)


def _dw7_from_local_q3(q3, q3_origin, image_width, layer, start, end):
    values = np.asarray(q3, dtype="<i2")
    channels, rows, width = values.shape
    if width != image_width or layer["weights"].shape != (channels, 1, 7, 7):
        raise ValueError("local q3/weight shape mismatch")
    required_start = max(0, start - 3)
    required_end = min(image_width, end + 3)
    if q3_origin > required_start or q3_origin + rows < required_end:
        raise ValueError("local q3 scratch omits required DW7 halo")
    raw = np.zeros((channels, end - start, width), dtype=np.int64)
    weights = np.asarray(layer["weights"], dtype="<i2")
    for out_y in range(start, end):
        local_out = out_y - start
        for ky in range(7):
            source_y = out_y + ky - 3
            if source_y < 0 or source_y >= image_width:
                continue
            local_y = source_y - q3_origin
            if local_y < 0 or local_y >= rows:
                raise ValueError("DW7 attempted to treat stripe boundary as padding")
            padded = np.pad(values[:, local_y, :].astype(np.int64), ((0, 0), (3, 3)))
            for kx in range(7):
                raw[:, local_out, :] += (padded[:, kx:kx + width] *
                    weights[:, 0, ky, kx].astype(np.int64)[:, None])
    return _requantized(raw, layer)


def _pointwise_tiles(source, layer, tile_pixels):
    x = np.asarray(source, dtype="<i2")
    weights = np.asarray(layer["weights"], dtype="<i2")
    inputs, rows, width = x.shape
    if weights.ndim != 2 or weights.shape[1] != inputs:
        raise ValueError("pointwise source/weight shape mismatch")
    if tile_pixels != 16:
        raise ValueError("v7 oracle is frozen to 16-pixel tiles")
    output = np.empty((weights.shape[0], rows, width), dtype="<i2")
    for row in range(rows):
        for x0 in range(0, width, tile_pixels):
            count = min(tile_pixels, width - x0)
            raw = weights.astype(np.int64) @ x[:, row, x0:x0 + count].astype(np.int64)
            quantized = _requantized(raw[:, None, :], layer)[:, 0, :]
            output[:, row, x0:x0 + count] = quantized
    return output


def _clip_i16(values):
    result = np.empty(values.shape, dtype="<i2")
    for index, value in enumerate(np.asarray(values, dtype=object).reshape(-1)):
        result.reshape(-1)[index] = min(32767, max(-32767, int(value)))
    return result


def execute_stripe(source, params, start_row, row_count, tile_pixels=16):
    """Execute one stripe using only its real global halo and local q3 scratch."""
    x = np.asarray(source, dtype="<i2")
    if x.ndim != 3 or x.shape[1] != x.shape[2]:
        raise ValueError("source must be square CHW int16")
    height = x.shape[1]
    start, count = int(start_row), int(row_count)
    if count < 1 or count > 4 or start < 0 or start >= height or count > height - start:
        raise ValueError("stripe row range is invalid")
    q3_start, q3_end = max(0, start - 3), min(height, start + count + 3)
    q3 = _depthwise_global_rows(x, params["layers"]["dw3"], q3_start, q3_end)
    q7 = _dw7_from_local_q3(q3, q3_start, height, params["layers"]["dw7"],
                            start, start + count)
    pw1 = _pointwise_tiles(q7, params["layers"]["pw1"], tile_pixels)
    gelu = params["gelu"][(pw1.astype(np.int32) + 32768)].astype("<i2")
    pw2 = _pointwise_tiles(gelu, params["layers"]["pw2"], tile_pixels)
    scale = q31_tensor_wide(pw2, params["scale_multiplier"], params["scale_shift"])
    q3_target = q3[:, start - q3_start:start - q3_start + count, :]
    residual = q31_tensor_wide(q3_target, params["residual_multiplier"],
                               params["residual_shift"])
    add = _clip_i16(scale + residual)
    return {
        "start_row": start,
        "row_count": count,
        "q3_start_row": q3_start,
        "q3_end_row": q3_end,
        "q3_scratch": q3,
        "dw7": q7,
        "pw1": pw1,
        "gelu": gelu,
        "pw2": pw2,
        "scale": scale,
        "residual": residual,
        "add": add,
        "output": add,
    }

