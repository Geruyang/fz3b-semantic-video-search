"""Host-side contract checks and resource accounting for ``cnn_shared_v7``.

This module is deliberately independent from the v6 runtime and driver.  All
addresses and lengths use 128-bit words, matching the frozen HLS top-level.
"""

import struct


UINT32_MAX = (1 << 32) - 1
DESCRIPTOR_STRUCT = struct.Struct("<9I")
PROFILE_SPECS = {
    0: {"channels": 128, "width": 32, "blocks": 12, "stride_words": 22433},
    1: {"channels": 256, "width": 16, "blocks": 20, "stride_words": 61057},
    2: {"channels": 64, "width": 64, "blocks": 4, "stride_words": 12193},
}


def _uint32(name, value):
    value = int(value)
    if value < 0 or value > UINT32_MAX:
        raise ValueError("%s must fit uint32" % name)
    return value


def profile_spec(profile):
    profile = _uint32("profile", profile)
    if profile not in PROFILE_SPECS:
        raise ValueError("unsupported normal profile")
    return dict(PROFILE_SPECS[profile])


def stripe_geometry(profile, start_row, row_count):
    spec = profile_spec(profile)
    width = spec["width"]
    start = _uint32("start_row", start_row)
    count = _uint32("row_count", row_count)
    if count < 1 or count > 4:
        raise ValueError("row_count must be in 1..4")
    # Subtraction form mirrors the hardware check and cannot wrap.
    if start >= width or count > width - start:
        raise ValueError("row range exceeds the image")
    q3_start = max(0, start - 3)
    q3_end = min(width, start + count + 3)
    source_start = max(0, start - 4)
    source_end = min(width, start + count + 4)
    row_words = spec["channels"] * width // 8
    if row_words != 512:
        raise AssertionError("normal profile row must contain exactly 512 words")
    return {
        "start_row": start,
        "row_count": count,
        "q3_start_row": q3_start,
        "q3_row_count": q3_end - q3_start,
        "source_start_row": source_start,
        "source_row_count": source_end - source_start,
        "row_words": row_words,
        "scratch_required_words": (q3_end - q3_start) * row_words,
    }


def _span(name, offset, length, extent):
    offset = _uint32(name + "_words", offset)
    length = int(length)
    extent = _uint32("arena extent", extent)
    if offset > extent or length > extent - offset:
        raise ValueError("%s span exceeds arena" % name)
    return (offset, offset + length)


def _overlap(left, right):
    return left[0] < right[1] and right[0] < left[1]


def validate_descriptor(value):
    """Validate one host descriptor before any parameter or memory write.

    The HLS top validates parameter metadata separately.  This routine proves
    scalar/range safety and gives the host the exact scratch extent to pin.
    """
    required = ("profile", "param_base_words", "params_words", "memory_words",
                "src_words", "dst_words", "scratch_words", "start_row",
                "row_count")
    missing = [name for name in required if name not in value]
    if missing:
        raise ValueError("descriptor fields missing: %s" % ",".join(missing))
    raw = {name: _uint32(name, value[name]) for name in required}
    spec = profile_spec(raw["profile"])
    geometry = stripe_geometry(raw["profile"], raw["start_row"], raw["row_count"])

    base = raw["param_base_words"]
    total = raw["params_words"]
    stride = spec["stride_words"]
    if base > total or stride > total - base:
        raise ValueError("parameter block exceeds parameter window")

    tensor_words = spec["channels"] * spec["width"] * spec["width"] // 8
    src = _span("src", raw["src_words"], tensor_words, raw["memory_words"])
    dst = _span("dst", raw["dst_words"], tensor_words, raw["memory_words"])
    scratch = _span("scratch", raw["scratch_words"],
                    geometry["scratch_required_words"], raw["memory_words"])
    spans = (("src", src), ("dst", dst), ("scratch", scratch))
    for index, (left_name, left) in enumerate(spans):
        for right_name, right in spans[index + 1:]:
            if _overlap(left, right):
                raise ValueError("%s/%s spans overlap" % (left_name, right_name))

    result = dict(raw)
    result.update(geometry)
    result.update({
        "channels": spec["channels"],
        "width": spec["width"],
        "tensor_words": tensor_words,
        "param_stride_words": stride,
        "spans": {"src": list(src), "dst": list(dst), "scratch": list(scratch)},
    })
    return result


def pack_descriptor(value):
    checked = validate_descriptor(value)
    names = ("profile", "param_base_words", "params_words", "memory_words",
             "src_words", "dst_words", "scratch_words", "start_row", "row_count")
    return DESCRIPTOR_STRUCT.pack(*[checked[name] for name in names])


def unpack_descriptor(payload):
    if len(payload) != DESCRIPTOR_STRUCT.size:
        raise ValueError("v7 descriptor must be exactly 36 bytes")
    names = ("profile", "param_base_words", "params_words", "memory_words",
             "src_words", "dst_words", "scratch_words", "start_row", "row_count")
    return dict(zip(names, DESCRIPTOR_STRUCT.unpack(payload)))


def resource_model(profile, stripe_rows=4, tile_pixels=16):
    spec = profile_spec(profile)
    width, channels = spec["width"], spec["channels"]
    if stripe_rows != 4:
        raise ValueError("production resource model is frozen to four-row stripes")
    if tile_pixels != 16:
        raise ValueError("shared RAM mapping is frozen to tile_pixels=16")
    q3_rows = 0
    source_rows = 0
    for start in range(0, width, stripe_rows):
        geometry = stripe_geometry(profile, start, min(stripe_rows, width - start))
        q3_rows += geometry["q3_row_count"]
        source_rows += geometry["source_row_count"]
    traffic_rows = source_rows + 2 * q3_rows + 4 * width
    full_rows = 7 * width
    recompute = float(q3_rows) / float(width)
    total_macs_per_pixel = 58 * channels + 6 * channels * channels
    extra_dw3_macs = 9 * channels * width * (q3_rows - width)
    total_full_macs = total_macs_per_pixel * width * width
    stride_bytes = spec["stride_words"] * 16
    stripe_count = width // stripe_rows
    spatial_tiles = width * width // tile_pixels
    # The packed 6-output PW groups contain padding for C=64/128/256.  The
    # kernel loops over real output channels, so AXI requests omit those
    # padding rows.  Each real weight is reread for every spatial tile.
    pw_weight_bytes_per_tile = 12 * channels * channels
    pw_weight_bytes_per_block = spatial_tiles * pw_weight_bytes_per_tile
    # Resource-balanced v7 loads the exact 65,536-entry INT16 GELU table into
    # local BRAM at the beginning of every stripe job.  The packed table is
    # 8,192 native 128-bit parameter words and is intentionally not retained
    # across jobs because every block owns a distinct table.
    gelu_table_words_per_job = 8192
    gelu_table_bytes_per_job = gelu_table_words_per_job * 16
    gelu_table_words_per_block = stripe_count * gelu_table_words_per_job
    pw_weight_bytes_per_job = pw_weight_bytes_per_block // stripe_count
    return {
        "profile": int(profile),
        "channels": channels,
        "width": width,
        "stripe_rows": stripe_rows,
        "stripe_count": stripe_count,
        "tile_pixels": tile_pixels,
        "q3_rows_computed": q3_rows,
        "source_rows_read": source_rows,
        "dw3_recompute_factor": recompute,
        "dw3_extra_vs_full_block_mac_ratio": float(extra_dw3_macs) / float(total_full_macs),
        "activation_traffic_row_equivalents": traffic_rows,
        "full_frame_activation_traffic_row_equivalents": full_rows,
        "activation_traffic_increase_ratio": float(traffic_rows) / float(full_rows) - 1.0,
        "activation_traffic_bytes": traffic_rows * channels * width * 2,
        "scratch_peak_bytes": 10 * channels * width * 2,
        "source_dependency_peak_bytes": 12 * channels * width * 2,
        "destination_stripe_bytes": 4 * channels * width * 2,
        "local_shared_ram_bytes": 1024 * 32,
        "gelu_table_bram_bytes": gelu_table_bytes_per_job,
        "gelu_table_load_128b_beats_per_job": gelu_table_words_per_job,
        "gelu_table_load_bytes_per_job": gelu_table_bytes_per_job,
        "gelu_table_load_128b_beats_per_block": gelu_table_words_per_block,
        "gelu_table_load_bytes_per_block":
            gelu_table_words_per_block * 16,
        "gelu_table_load_model":
            "exact 8192x128-bit sequential preload at every stripe job",
        "gelu_lookups_per_block": 3 * channels * width * width,
        "parameter_stride_bytes": stride_bytes,
        "spatial_tiles_per_block": spatial_tiles,
        "pw_weight_read_bytes_per_spatial_tile": pw_weight_bytes_per_tile,
        "pw_weight_read_bytes_per_job": pw_weight_bytes_per_job,
        "pw_weight_read_bytes_per_block": pw_weight_bytes_per_block,
        "pw_weight_read_model":
            "valid PW channels reread once per T16 spatial tile; excludes packed padding",
        "modeled_major_parameter_read_bytes_per_job":
            pw_weight_bytes_per_job + gelu_table_bytes_per_job,
        "modeled_major_parameter_read_bytes_per_block":
            pw_weight_bytes_per_block + gelu_table_words_per_block * 16,
        "modeled_major_parameter_read_scope":
            "PW weights plus fixed GELU preload; excludes smaller metadata, DW weights, coefficients, and AXI overhead",
        "legacy_full_blob_per_stripe_upper_bound_bytes": stripe_count * stride_bytes,
        "worst_case_parameter_window_bytes_if_reloaded_per_stripe":
            stripe_count * stride_bytes,
    }

