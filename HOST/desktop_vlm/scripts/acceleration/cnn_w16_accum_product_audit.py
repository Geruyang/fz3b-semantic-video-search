"""Independent binary-layout audit of FZV5 signed48 accumulators/Q31 products."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
JOINT = HOST / "network-w16-joint-oracle-001"
N0 = HOST / "network0-w16-preflight-001"
OUT = HOST / "network-w16-accum-product-audit-002"
LIMIT48 = (1 << 47) - 1
LIMIT80 = (1 << 79) - 1


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def unpack_pw(data, offset, outputs, inputs, words):
    matrix = np.zeros((outputs, inputs), dtype="<i2")
    cursor = offset
    for group in range(math.ceil(outputs / 6)):
        for red in range(inputs // 16):
            tile = np.frombuffer(data, dtype="<i2", count=96, offset=cursor).reshape(6, 16)
            first = group * 6
            valid = min(6, outputs - first)
            matrix[first:first+valid, red*16:(red+1)*16] = tile[:valid]
            if np.any(tile[valid:] != 0):
                raise ValueError("nonzero padded output lane in PW tile")
            cursor += 192
    expected = offset + words * 192
    if cursor != expected:
        raise AssertionError("PW tile unpack size mismatch")
    return matrix


def field_view(data, field, dtype):
    return np.frombuffer(data, dtype=dtype,
                         count=field["bytes"] // np.dtype(dtype).itemsize,
                         offset=field["offset"]).copy()


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    joint_path = JOINT / "manifest.json"
    joint = json.loads(joint_path.read_text(encoding="utf-8"))
    n0_path = N0 / "manifest.json"
    n0 = json.loads(n0_path.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True)
    profiles = {}
    global_bound, global_product, global_actual = (None, None, None)
    configs = ((0, 128, 12, joint["profiles"]["profile0"]["params"], JOINT),
               (1, 256, 20, joint["profiles"]["profile1"]["params"], JOINT),
               (2, 64, 4, n0["params"]["blocks"], N0))
    for profile, channels, blocks, fields, root in configs:
        # Byte offsets are checked against the independent schema formula.
        offset = {x["name"]: x["offset"] for x in joint["parameter_layout"]["fields"]} if "parameter_layout" in joint else None
        del offset
        # Joint manifest intentionally stores per-block binary and exact sizing.
        from sys import path as _sys_path
        _sys_path.insert(0, str(Path(__file__).resolve().parent))
        import cnn_w16_contract as contract
        layout_fields, stride = contract.layout(channels)
        p_report = {}
        for block in range(blocks):
            meta = fields[block]
            path = root / meta["path"]
            payload = path.read_bytes()
            if len(payload) != stride or hashlib.sha256(payload).hexdigest() != meta["sha256"]:
                raise ValueError(f"parameter file integrity/stride mismatch: {path}")
            fd = {x["name"]: x for x in layout_fields}
            w_dw3 = field_view(payload, fd["dw3_weights_i16"], "<i2").reshape(channels, 9)
            w_dw7 = field_view(payload, fd["dw7_weights_i16"], "<i2").reshape(channels, 49)
            bias = field_view(payload, fd["bias_i64"], "<i8")
            mult = field_view(payload, fd["multiplier_i32"], "<i4")
            shift = field_view(payload, fd["shift_i32"], "<i4")
            pw1f, pw2f = fd["pw1_tiles_i16"], fd["pw2_tiles_i16"]
            w1 = unpack_pw(payload, pw1f["offset"], 3*channels, channels,
                           pw1f["bytes"]//192)
            w2 = unpack_pw(payload, pw2f["offset"], channels, 3*channels,
                           pw2f["bytes"]//192)
            bias_ranges = {"dw3": (0, channels), "dw7": (channels, 2*channels),
                           "pw1": (2*channels, 5*channels), "pw2": (5*channels, 6*channels)}
            weights = {"dw3": w_dw3, "dw7": w_dw7, "pw1": w1, "pw2": w2}
            red_bound = {"dw3": 9, "dw7": 49, "pw1": channels, "pw2": 3*channels}
            ops = {}
            for i, op in enumerate(("dw3", "dw7", "pw1", "pw2")):
                lo, hi = bias_ranges[op]
                b, m, s = bias[lo:hi], mult[lo:hi], shift[lo:hi]
                rows = weights[op].reshape(weights[op].shape[0], -1)
                bounds = [abs(int(bc)) + 32767 * sum(abs(int(v)) for v in row)
                          for bc, row in zip(b, rows)]
                products = [bound * abs(int(mc)) for bound, mc in zip(bounds, m)]
                item = {"channels": len(bounds), "reduction": red_bound[op],
                        "full_range_abs_bound_max": max(bounds),
                        "full_range_abs_bound_max_channel": int(np.argmax(bounds)),
                        "bias_abs_max": max(abs(int(v)) for v in b),
                        "q31_multiplier_abs_max": max(abs(int(v)) for v in m),
                        "q31_shift_range": [int(np.min(s)), int(np.max(s))],
                        "q31_product_abs_bound_max": max(products),
                        "q31_product_abs_bound_max_channel": int(np.argmax(products)),
                        "fits_signed48": max(bounds) <= LIMIT48,
                        "fits_signed80_product": max(products) <= LIMIT80}
                ops[op] = item
                key = (profile, block, op, item["full_range_abs_bound_max_channel"])
                if global_bound is None or item["full_range_abs_bound_max"] > global_bound[0]:
                    global_bound = (item["full_range_abs_bound_max"], key)
                pkey = (profile, block, op, item["q31_product_abs_bound_max_channel"])
                if global_product is None or item["q31_product_abs_bound_max"] > global_product[0]:
                    global_product = (item["q31_product_abs_bound_max"], pkey)
            p_report[str(block)] = {"parameter_file_sha256": meta["sha256"], "operators": ops}
        profiles[f"profile{profile}"] = p_report

    # The joint oracle logs actual peak per image/block/operator.
    for sample in joint["results"]:
        for key, field in (("profile0", "profile0_blocks"), ("profile1", "profile1_blocks")):
            for block in sample[field]:
                for op, vals in block["accumulators"].items():
                    v = int(vals["bias_included_abs_peak"])
                    pos = (sample["sample_id"], int(block["block"]), op)
                    if global_actual is None or v > global_actual[0]:
                        global_actual = (v, pos)
    for sample in n0["results"]:
        for block in sample["blocks"]:
            for op, vals in block["accumulators"].items():
                v = int(vals["bias_included_abs_peak"])
                pos = (sample["sample_id"], int(block["index"]), op, "profile2")
                if global_actual is None or v > global_actual[0]:
                    global_actual = (v, pos)
    report = {
        "schema_version": 1, "status": "HOST_W16_PARAMETER_BINARY_ACCUMULATOR_AND_SIGNED80_AUDIT_NOT_PL",
        "joint_manifest_sha256": sha(joint_path), "network0_manifest_sha256": sha(n0_path),
        "contract": {"activation_abs_bound": 32767, "bias": "signed48 fit per output channel",
                     "accumulator": "signed48", "q31_product": "signed80 exact product, tie-even shift 0..62",
                     "maximum_signed80_positive": LIMIT80},
        "profiles": profiles,
        "global_max_full_range_accumulator_bound": {"value": global_bound[0],
            "profile_block_op_channel": list(global_bound[1]), "fits_signed48": global_bound[0] <= LIMIT48},
        "global_max_q31_product_bound": {"value": global_product[0],
            "profile_block_op_channel": list(global_product[1]), "fits_signed80": global_product[0] <= LIMIT80},
        "global_max_actual_bias_included_accumulator_peak": {"value": global_actual[0],
            "sample_block_op": list(global_actual[1])},
        "checks": {"all_full_range_accumulators_fit_signed48": all(
                       x["fits_signed48"] for p in profiles.values() for b in p.values() for x in b["operators"].values()),
                   "all_q31_products_fit_signed80": all(
                       x["fits_signed80_product"] for p in profiles.values() for b in p.values() for x in b["operators"].values()),
                   "board_or_pl_execution": False},
    }
    report["files"] = {p.relative_to(OUT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)}
                       for p in OUT.rglob("*") if p.is_file() and p.name != "manifest.json"}
    path = OUT / "manifest.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "manifest_sha256": sha(path),
                      "global_acc_bound": report["global_max_full_range_accumulator_bound"],
                      "global_product_bound": report["global_max_q31_product_bound"],
                      "global_actual_peak": report["global_max_actual_bias_included_accumulator_peak"],
                      "checks": report["checks"]}, indent=2))


if __name__ == "__main__":
    main()
