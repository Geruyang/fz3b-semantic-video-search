"""Read-only structural analysis of the 36 legacy W16 GELU tables.

The report is descriptive only.  It does not change the table, arithmetic, or
the frozen v7 single-core cache policy.
"""

from __future__ import print_function

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import cnn_w16_contract as w16


PROFILE_BLOCKS = {0: 12, 1: 20, 2: 4}


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _prefix_constant(values):
    end = 1
    while end < values.size and int(values[end]) == int(values[0]):
        end += 1
    return end


def _suffix_affine(values):
    if values.size < 2:
        return 1, 0
    delta = int(values[-1]) - int(values[-2])
    start = values.size - 2
    while start > 0 and int(values[start]) - int(values[start - 1]) == delta:
        start -= 1
    return values.size - start, delta


def _longest_affine(values, required_delta=None, nonzero=False):
    best_start, best_entries, best_delta = 0, 1, 0
    run_start = 0
    run_delta = None
    for index in range(1, values.size):
        delta = int(values[index]) - int(values[index - 1])
        if run_delta is None or delta != run_delta:
            run_start = index - 1
            run_delta = delta
        entries = index - run_start + 1
        eligible = ((required_delta is None or run_delta == required_delta) and
                    (not nonzero or run_delta != 0))
        if eligible and entries > best_entries:
            best_start, best_entries, best_delta = run_start, entries, run_delta
    return {
        "entries": int(best_entries),
        "input_min": int(best_start - 32768),
        "input_max": int(best_start + best_entries - 1 - 32768),
        "output_at_input_min": int(values[best_start]),
        "delta_per_input": int(best_delta),
    }


def analyze_table(table):
    values = np.asarray(table, dtype="<i2").reshape(-1)
    if values.size != 65536:
        raise ValueError("GELU table must contain 65536 int16 entries")
    prefix_count = _prefix_constant(values)
    suffix_count, suffix_delta = _suffix_affine(values)
    suffix_start = values.size - suffix_count
    constant_suffix_count = suffix_count if suffix_delta == 0 else 1
    constant_suffix_start = values.size - constant_suffix_count
    return {
        "constant_prefix": {
            "entries": int(prefix_count),
            "input_min": -32768,
            "input_max": int(prefix_count - 1 - 32768),
            "value": int(values[0]),
        },
        "affine_suffix": {
            "entries": int(suffix_count),
            "input_min": int(suffix_start - 32768),
            "input_max": 32767,
            "output_at_input_min": int(values[suffix_start]),
            "delta_per_input": int(suffix_delta),
        },
        "constant_suffix": {
            "entries": int(constant_suffix_count),
            "input_min": int(constant_suffix_start - 32768),
            "input_max": 32767,
            "value": int(values[-1]),
        },
        "longest_nonconstant_integer_affine_run":
            _longest_affine(values, nonzero=True),
        "longest_exact_unit_slope_run":
            _longest_affine(values, required_delta=1),
        "middle_entries_after_exact_tail_elision":
            int(max(0, values.size - prefix_count - suffix_count)),
        "middle_raw_bytes_after_exact_tail_elision":
            int(2 * max(0, values.size - prefix_count - suffix_count)),
    }


def _block_paths(root):
    joint = root / ("artifacts/board-debug-20261005/acceleration/host/"
                    "network-w16-joint-oracle-001/params")
    preflight = root / ("artifacts/board-debug-20261005/acceleration/host/"
                        "network0-w16-preflight-001/params")
    for profile in (2, 0, 1):
        base = preflight if profile == 2 else joint
        for block in range(PROFILE_BLOCKS[profile]):
            yield profile, block, base / ("profile%d/block-%02d.bin" %
                                          (profile, block))


def build_report(root):
    entries = []
    groups = {}
    for profile, block, path in _block_paths(root):
        fields, stride = w16.layout(w16.PROFILES[profile]["channels"])
        field = next(item for item in fields if item["name"] == "gelu_lut_i16")
        payload = path.read_bytes()
        if len(payload) != stride:
            raise ValueError("%s has unexpected block length" % path)
        table_bytes = payload[field["offset"]:field["offset"] + field["bytes"]]
        digest = _sha256(table_bytes)
        table = np.frombuffer(table_bytes, dtype="<i2")
        block_id = "profile%d/block-%02d" % (profile, block)
        entries.append({
            "block": block_id,
            "profile": profile,
            "block_index": block,
            "source_path": path.relative_to(root).as_posix(),
            "source_sha256": _sha256(payload),
            "table_sha256": digest,
            "table_bytes": len(table_bytes),
            "structure": analyze_table(table),
        })
        groups.setdefault(digest, []).append(block_id)
    unique = []
    by_block = {item["block"]: item for item in entries}
    for digest in sorted(groups):
        blocks = groups[digest]
        unique.append({
            "table_sha256": digest,
            "blocks": blocks,
            "reuse_count": len(blocks),
            "structure": by_block[blocks[0]]["structure"],
        })
    constant_tail_entries = sum(
        item["structure"]["constant_prefix"]["entries"] +
        item["structure"]["constant_suffix"]["entries"] for item in unique)
    unit_runs = [item["structure"]["longest_exact_unit_slope_run"]["entries"]
                 for item in unique]
    return {
        "status": "CNN_SHARED_V7_GELU_TABLE_ANALYSIS",
        "scope": "read-only exact packed W16 tables; no arithmetic or parameter changes",
        "blocks": entries,
        "block_count": len(entries),
        "unique_table_count": len(unique),
        "unique_tables": unique,
        "storage": {
            "unshared_table_bytes": len(entries) * 131072,
            "shared_unique_table_bytes": len(unique) * 131072,
            "exact_table_dedup_saved_bytes":
                (len(entries) - len(unique)) * 131072,
            "exact_constant_tail_entries": int(constant_tail_entries),
            "exact_constant_tail_raw_bytes": int(2 * constant_tail_entries),
            "raw_middle_bytes_after_constant_tail_elision":
                int(len(unique) * 131072 - 2 * constant_tail_entries),
            "longest_exact_unit_slope_run_entries_min": int(min(unit_runs)),
            "longest_exact_unit_slope_run_entries_max": int(max(unit_runs)),
            "tail_elision_is_analysis_only": True,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_report(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output),
                      "block_count": result["block_count"],
                      "unique_table_count": result["unique_table_count"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
