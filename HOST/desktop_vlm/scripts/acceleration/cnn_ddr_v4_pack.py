"""Pack network2/network4 parameters and three CPU-oracle activation fixtures.

This is an offline serializer. It does not access a board or change the v3 ABI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def align16(value):
    return (value + 15) & ~15


def pw_word_count(outputs, inputs):
    if inputs % 16:
        raise ValueError("pointwise reduction width must be divisible by 16")
    return math.ceil(outputs / 6) * (inputs // 16)


def expected_stride(channels):
    if channels not in (128, 256):
        raise ValueError("v4 schema is frozen for C=128 or C=256")
    return (58 * channels + 72 * channels + 8 * channels + 16 + 131072 +
            96 * (pw_word_count(3 * channels, channels) +
                  pw_word_count(channels, 3 * channels)))


def make_layout(channels):
    pw1_words = pw_word_count(3 * channels, channels)
    pw2_words = pw_word_count(channels, 3 * channels)
    fields = []
    offset = 0

    def add(name, size, dtype, shape, note=""):
        nonlocal offset
        if offset % 16:
            raise AssertionError(f"{name} does not start on a 16-byte boundary")
        fields.append({"name": name, "offset": offset, "bytes": size,
                       "dtype": dtype, "shape": shape, "note": note})
        offset += size

    add("dw3_weights", 9 * channels, "i8", [channels, 9], "OIHW flattened over 3x3")
    add("dw7_weights", 49 * channels, "i8", [channels, 49], "OIHW flattened over 7x7")
    add("bias", 6 * channels * 4, "i32le", [6 * channels], "DW3,DW7,PW1,PW2 channel order")
    add("multiplier", 6 * channels * 4, "i32le", [6 * channels], "Q31 channel order matches bias")
    add("shift", 6 * channels * 4, "i32le", [6 * channels], "nonnegative right shifts")
    add("scale_multiplier", channels * 4, "i32le", [channels])
    add("scale_shift", channels * 4, "i32le", [channels])
    add("residual_q31", 16, "i32le+i32le+zero[8]", [4],
        "residual multiplier, residual shift, eight zero padding bytes")
    add("gelu", 65536 * 2, "i16le", [65536], "signed INT16 lookup table")
    add("pw1_tiles", pw1_words * 96, "i8", [pw1_words, 6, 16],
        "group-major, reduction-major; zero padded output lanes")
    add("pw2_tiles", pw2_words * 96, "i8", [pw2_words, 6, 16],
        "group-major, reduction-major; zero padded output lanes")
    if offset != expected_stride(channels):
        raise AssertionError(f"stride formula mismatch: layout {offset}, formula {expected_stride(channels)}")
    return fields, offset


def pack_pw(matrix, out_channels, in_channels):
    matrix = np.asarray(matrix)
    if matrix.shape != (out_channels, in_channels) or matrix.dtype != np.dtype("i1"):
        raise ValueError("PW weights must be signed INT8 OI matrix of exact shape")
    words = []
    for group in range(math.ceil(out_channels / 6)):
        for reduction in range(in_channels // 16):
            word = np.zeros((6, 16), dtype="i1")
            first = group * 6
            valid = min(6, out_channels - first)
            word[:valid, :] = matrix[first:first + valid,
                                     reduction * 16:(reduction + 1) * 16]
            words.append(word.tobytes(order="C"))
    return b"".join(words)


def read_meta(root, meta):
    path = (root / meta["path"]).resolve()
    raw = path.read_bytes()
    if len(raw) != meta["bytes"] or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError("oracle source file mismatch: " + str(path))
    dtype = np.dtype(meta["dtype"])
    values = np.frombuffer(raw, dtype=dtype).copy()
    if int(np.prod(meta["shape"])) != values.size:
        raise ValueError("oracle source tensor shape mismatch: " + str(path))
    return values.reshape(meta["shape"])


def block_arrays(manifest_root, oracle, block_index, channels):
    block = oracle["blocks"][block_index]
    if "files" in block:  # Existing network2 oracle schema.
        files = block["files"]
        def get(key):
            return read_meta(manifest_root, files[key])
        weights = {name: get(name) for name in
                   ("dw3_weights", "dw7_weights", "pw1_weights", "pw2_weights")}
        bias, multiplier, shift = get("bias_i32"), get("multiplier_i32"), get("shift_i32")
        scale_mul, scale_shift = get("scale_multiplier_i32"), get("scale_shift_i32")
        residual_mul, residual_shift = get("residual_multiplier_i32"), get("residual_shift_i32")
        gelu = get("gelu_lut")
    else:  # network4 INT oracle schema.
        pfiles = block["parameters"]
        def get(key):
            return read_meta(manifest_root, pfiles[key])
        weights = {"dw3_weights": get("dw3_weights_i8").reshape((channels, 9)),
                   "dw7_weights": get("dw7_weights_i8").reshape((channels, 49)),
                   "pw1_weights": get("pw1_weights_i8"),
                   "pw2_weights": get("pw2_weights_i8")}
        bias = np.concatenate([get(f"{layer}_bias_i32") for layer in ("dw3", "dw7", "pw1", "pw2")])
        multiplier = np.concatenate([get(f"{layer}_multiplier_i32") for layer in ("dw3", "dw7", "pw1", "pw2")])
        shift = np.concatenate([get(f"{layer}_shift_i32") for layer in ("dw3", "dw7", "pw1", "pw2")])
        scale_mul, scale_shift = get("scale_multiplier_i32"), get("scale_shift_i32")
        residual_mul, residual_shift = get("residual_multiplier_i32"), get("residual_shift_i32")
        gelu = get("gelu_lut_i16")
    expected_shapes = {"dw3_weights": (channels, 9), "dw7_weights": (channels, 49),
                       "pw1_weights": (3 * channels, channels),
                       "pw2_weights": (channels, 3 * channels)}
    for name, shape in expected_shapes.items():
        if weights[name].shape != shape or weights[name].dtype != np.dtype("i1"):
            raise ValueError(f"{name} shape/dtype mismatch for C={channels}")
    if bias.shape != (6 * channels,) or multiplier.shape != bias.shape or shift.shape != bias.shape:
        raise ValueError("merged channel parameter shape mismatch")
    if scale_mul.shape != (channels,) or scale_shift.shape != (channels,):
        raise ValueError("scale branch parameter shape mismatch")
    if residual_mul.size != 1 or residual_shift.size != 1 or gelu.shape != (65536,):
        raise ValueError("residual/GELU parameter shape mismatch")
    return {"weights": weights, "bias": bias, "multiplier": multiplier,
            "shift": shift, "scale_multiplier": scale_mul,
            "scale_shift": scale_shift, "residual_multiplier": residual_mul,
            "residual_shift": residual_shift, "gelu": gelu}


def block_calibration_scales(manifest_root, oracle, block_index):
    """Read scales from the oracle block manifest and verify its parent SHA link."""
    block = oracle["blocks"][block_index]
    scales = block.get("calibration_scales")
    if isinstance(scales, dict):
        return scales
    block_manifest_ref = block.get("parameter_manifest")
    expected_sha = block.get("parameter_manifest_sha256")
    rel = block_manifest_ref.get("path") if isinstance(block_manifest_ref, dict) else block.get("path")
    if not rel:
        raise ValueError(f"block {block_index} lacks parameter manifest path")
    if not expected_sha:
        expected_sha = block_manifest_ref.get("sha256") if isinstance(block_manifest_ref, dict) else None
    if not expected_sha:
        raise ValueError(f"block {block_index} lacks parameter manifest SHA link")
    path = (manifest_root / rel).resolve()
    actual_sha = sha256(path)
    linked_sha = block_manifest_ref.get("sha256") if isinstance(block_manifest_ref, dict) else expected_sha
    if actual_sha != expected_sha or actual_sha != linked_sha:
        raise ValueError(f"block {block_index} parameter manifest SHA mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("block_index", -1)) != block_index:
        raise ValueError(f"network4 block manifest index mismatch at {block_index}")
    scales = payload.get("calibration_scales")
    if not isinstance(scales, dict):
        raise ValueError(f"network4 block {block_index} manifest lacks calibration_scales")
    return scales


def pack_block(params, channels):
    w = params["weights"]
    parts = [w["dw3_weights"].tobytes(order="C"),
             w["dw7_weights"].tobytes(order="C"),
             np.asarray(params["bias"], dtype="<i4").tobytes(),
             np.asarray(params["multiplier"], dtype="<i4").tobytes(),
             np.asarray(params["shift"], dtype="<i4").tobytes(),
             np.asarray(params["scale_multiplier"], dtype="<i4").tobytes(),
             np.asarray(params["scale_shift"], dtype="<i4").tobytes(),
             np.asarray(params["residual_multiplier"], dtype="<i4").tobytes(),
             np.asarray(params["residual_shift"], dtype="<i4").tobytes(),
             bytes(8), np.asarray(params["gelu"], dtype="<i2").tobytes(),
             pack_pw(w["pw1_weights"], 3 * channels, channels),
             pack_pw(w["pw2_weights"], channels, 3 * channels)]
    payload = b"".join(parts)
    expected = expected_stride(channels)
    if len(payload) != expected:
        raise AssertionError(f"packed stride {len(payload)} != schema {expected}")
    return payload


def source_fixture_records(manifest_path, oracle):
    root = manifest_path.resolve().parent
    records = []
    network2 = "qinput_file" in oracle["results"][0] if oracle["results"] else False
    for sample in oracle["results"]:
        if sample["sample_id"] not in ("image-00", "image-01", "image-02"):
            raise ValueError("unexpected sample id in oracle")
        if network2:
            input_meta = sample["qinput_file"]
            outputs = [item["add_file"] for item in sample["block_metrics"]]
        else:
            first = sample["blocks"][0]
            input_meta = first["outputs"]["input_i16"]
            outputs = [item["outputs"]["add_output_i16"] for item in sample["blocks"]]
        if len(outputs) != len(oracle["blocks"]):
            raise ValueError("expected one output for every oracle block")
        input_array = read_meta(root, input_meta)
        input_array = input_array.reshape((-1, *input_array.shape[-3:]))[0]
        records.append({"sample_id": sample["sample_id"], "input_sha256": sample["input_sha256"],
                        "input": input_array, "input_source": input_meta,
                        "outputs": [read_meta(root, meta).reshape((-1, *meta["shape"][-3:]))[0]
                                    for meta in outputs],
                        "output_sources": outputs})
    if len(records) != 3 or {item["sample_id"] for item in records} != {
            "image-00", "image-01", "image-02"}:
        raise ValueError("three frozen image fixtures are required")
    return root, records


def to_hcw_bytes(value):
    value = np.asarray(value)
    if value.ndim != 3 or value.dtype != np.dtype("<i2"):
        value = np.asarray(value, dtype="<i2")
    return np.ascontiguousarray(value.transpose(1, 0, 2), dtype="<i2").tobytes(order="C")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest_path = Path(args.oracle_manifest)
    oracle = json.loads(manifest_path.read_text(encoding="utf-8"))
    board_calibrated = (
        oracle.get("status") == "NETWORK2_INT_ORACLE_BOARD_PS_CALIBRATED_CPU_NOT_PL" or
        oracle.get("trace_provenance") == "BOARD_PS_CPU_NETWORK4_TRACE_COLLECTION")
    first_block = oracle["blocks"][0]
    channels = int(first_block.get("files", {}).get("dw3_weights", {}).get("shape", [0])[0]
                   or first_block.get("parameters", {}).get("dw3_weights_i8", {}).get("shape", [0])[0])
    if channels not in (128, 256):
        raise ValueError("unable to resolve supported stage channel count")
    blocks = oracle["blocks"]
    expected_count = 12 if channels == 128 else 20
    if len(blocks) != expected_count:
        raise ValueError(f"C={channels} requires {expected_count} blocks")
    fields, stride = make_layout(channels)
    if stride not in (248592, 561168):
        raise AssertionError("frozen stride changed")
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    root = manifest_path.resolve().parent
    params_blob = bytearray()
    block_records = []
    for index in range(expected_count):
        params = block_arrays(root, oracle, index, channels)
        payload = pack_block(params, channels)
        offset = len(params_blob)
        params_blob.extend(payload)
        block_records.append({"index": index, "offset": offset, "bytes": len(payload),
                              "sha256": hashlib.sha256(payload).hexdigest(),
                              "parameter_manifest_sha256": oracle["blocks"][index].get("parameter_manifest_sha256"),
                              "activation_scale": block_calibration_scales(root, oracle, index)})
    params_path = output / "params-v4.bin"
    params_path.write_bytes(params_blob)
    single_block = None
    if channels == 128:
        single_path = output / "params-v4-block0.bin"
        first_block = params_blob[:stride]
        if len(first_block) != stride:
            raise AssertionError("profile0 block0 prefix is shorter than the frozen stride")
        single_path.write_bytes(first_block)
        single_block = {"block_index": 0, "profile": 0,
                        "purpose": "profile0/block1 high-DDR kernel fixture",
                        "path": single_path.name, "bytes": single_path.stat().st_size,
                        "sha256": sha256(single_path), "source_path": params_path.name,
                        "source_offset": 0, "source_bytes": stride}
    _, samples = source_fixture_records(manifest_path, oracle)
    fixtures = []
    slot_bytes = int(channels * 16 * 16 * 2) if channels == 256 else int(channels * 32 * 32 * 2)
    for sample in samples:
        sample_dir = output / sample["sample_id"]
        sample_dir.mkdir()
        input_bytes = to_hcw_bytes(sample["input"])
        if len(input_bytes) != slot_bytes:
            raise ValueError("input fixture byte count differs from fixed slot size")
        input_path = sample_dir / "input-slot0-hcw.i16le"
        input_path.write_bytes(input_bytes)
        output_records = []
        for index, value in enumerate(sample["outputs"]):
            if value.shape[0] != channels:
                raise ValueError("block output channel count mismatch")
            encoded = to_hcw_bytes(value)
            if len(encoded) != slot_bytes:
                raise ValueError("expected output byte count differs from fixed slot size")
            slot = (index + 1) & 1
            path = sample_dir / f"block-{index:02d}-output-slot{slot}-hcw.i16le"
            path.write_bytes(encoded)
            output_records.append({"block_index": index, "read_slot": index & 1,
                                   "write_slot": slot, "path": path.name,
                                   "bytes": len(encoded), "sha256": sha256(path),
                                   "shape_hcw": [value.shape[1], value.shape[0], value.shape[2]],
                                   "dtype": "<i2", "oracle_source": sample["output_sources"][index]})
        fixtures.append({"sample_id": sample["sample_id"], "input_sha256": sample["input_sha256"],
                         "input": {"path": input_path.relative_to(output).as_posix(),
                                   "bytes": input_path.stat().st_size, "sha256": sha256(input_path),
                                   "shape_hcw": [sample["input"].shape[1], sample["input"].shape[0], sample["input"].shape[2]],
                                   "dtype": "<i2", "initial_slot": 0,
                                   "oracle_source": sample["input_source"]},
                         "expected_block_outputs": output_records})
    report = {
        "schema_version": 4,
        "status": "NETWORK2_CNN_DDR_V4_BOARD_PS_FIXTURE_NOT_PL" if board_calibrated
                  else "NETWORK2_CNN_DDR_V4_HOST_FIXTURE_NOT_BOARD_PS_OR_PL",
        "oracle_manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path),
                            "status": oracle.get("status")},
        "channel_count": channels, "block_count": expected_count,
        "parameter_file": {"path": params_path.name, "bytes": params_path.stat().st_size,
                            "sha256": sha256(params_path), "block_stride_bytes": stride,
                            "contains_frame_or_block_headers": False,
                            "blocks": block_records,
                            **({"single_block_fixture": single_block} if single_block else {})},
        "parameter_layout": {"order": [field["name"] for field in fields],
                             "fields": fields, "stride_formula": "58C+72C+8C+16+131072+96*(ceil(3C/6)*C/16+ceil(C/6)*3C/16)",
                             "field_alignment": "Every field starts at a 16-byte boundary; residual pair plus 8 zero bytes occupies 16 bytes.",
                             "pw_tile": {"bytes": 96, "shape": [6, 16],
                                         "order": "group-major, reduction-major, output-lane-major, reduction-lane-minor",
                                         "padding": "invalid output lanes are zero"}},
        "activation_layout": {"logical_order": "CHW", "serialized_order": "HCW",
                              "dtype": "little-endian signed INT16", "slots": 2,
                              "slot_bytes": slot_bytes,
                              "block_schedule": "read slot block_index%2; write slot (block_index+1)%2",
                              "packet_headers": False},
        "runtime_path_contract": {
            "network4_isolated_oracle": {
                "purpose": "exactly validate network4 itself from a real PS-observed network4 input boundary",
                "entry": "PS prefix output at network4 input boundary; captured network4 input trace used only for independent oracle validation",
                "status": "PENDING_REAL_BOARD_PS_NETWORK4_TRACE",
            },
            "full_runtime_chain": ["PS prefix", "v4 network2", "PS network3 bridge", "v4 network4", "PS suffix"],
            "network4_runtime_input": {
                "source": "actual network3 runtime output after dequantizing v3-equivalent INT16 network2 Add output",
                "operation": "run real PS network3 inference, then quantize its actual output into the network4 input scale",
                "prebuilt_fixture_is_not_runtime_input": True,
            },
            "scale_provenance": "If activation scales come from pure-PS trace collection, identify that exact trace manifest SHA as the calibration source; host traces remain comparison-only.",
            "acceptance": "Compare final 512-D feature against the original pinned PS reference and apply the existing acceptance threshold; old three images are regression fixtures only.",
            "board_actions_performed": False,
        },
        "fixtures": fixtures,
        "checks": {"constant_block_stride": all(x["bytes"] == stride for x in block_records),
                   "three_frozen_samples": len(fixtures) == 3,
                   "all_block_expected_outputs_present": all(len(x["expected_block_outputs"]) == expected_count for x in fixtures),
                   "parameter_generation_once": True, "pl_execution": False},
    }
    report_path = output / "manifest.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Manifest indexes every emitted file, including each independent fixture.
    report["files"] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path != report_path:
            report["files"][path.relative_to(output).as_posix()] = {
                "bytes": path.stat().st_size, "sha256": sha256(path)}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output.resolve()), "channels": channels,
                      "block_count": expected_count, "parameter_stride_bytes": stride,
                      "parameter_blob_bytes": params_path.stat().st_size,
                      "manifest_sha256": sha256(report_path),
                      "status": report["status"]}, indent=2))


if __name__ == "__main__":
    main()
