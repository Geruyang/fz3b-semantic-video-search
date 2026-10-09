#!/usr/bin/env python3
"""Build short V10 N0 per-block RTL golden files from the frozen oracle.

No product arithmetic is used to create expected data.  Expected HCW tensors
come directly from the independently frozen wide-integer N0 oracle.  An
optional native run is only a cross-check of the generated block-0 fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import cnn_v10_param_contract as v10


ORACLE_MANIFEST = ROOT / "artifacts/board-debug-20261005/acceleration/host/network0-w16-preflight-001/manifest.json"
ORACLE_SHA256 = "9fcc4a05e7668c523f0a94d54ed8731c68582e0958f24bc7589c2f702c9f7326"
PAIRED_MANIFEST = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001/manifest.json"
PAIRED_SHA256 = "83df8803b7a8eb08795c6c19d89538637f850df9044c407b90814d725f0079c4"
FULL_NATIVE_RECEIPT = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-native-full-011/receipt.json"
FULL_NATIVE_RECEIPT_SHA256 = "fc93f24bb5c7a9b4cb81753d27809f64075b880ca9ab9d42351764c138a2c19a"
DEFAULT_OUT = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-n0-block-golden-001"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_json(path: Path, expected_sha256: str) -> dict:
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"manifest hash mismatch: {path}: {actual}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_declared(base: Path, declaration: dict) -> tuple[Path, bytes]:
    path = Path(declaration["path"])
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    raw = path.read_bytes()
    if len(raw) != int(declaration["bytes"]) or sha256(path) != declaration["sha256"]:
        raise ValueError(f"source declaration mismatch: {path}")
    return path, raw


def write_binary(path: Path, raw: bytes, source: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": str(path.resolve()), "bytes": len(raw), "sha256": sha256(path),
        "source": source,
    }


def write_mem128(path: Path, raw: bytes, source: dict) -> dict:
    if len(raw) % 16:
        raise ValueError(f"128-bit alignment required: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        for offset in range(0, len(raw), 16):
            stream.write(f"{int.from_bytes(raw[offset:offset + 16], 'little'):032x}\n")
    decoded = b"".join(
        int(line, 16).to_bytes(16, "little")
        for line in path.read_text(encoding="ascii").splitlines()
    )
    if decoded != raw:
        raise AssertionError(f"readmemh round trip failed: {path}")
    return {
        "path": str(path.resolve()), "bytes": path.stat().st_size,
        "sha256": sha256(path), "word_count": len(raw) // 16,
        "source": source,
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "round_trip_binary_sha256": hashlib.sha256(decoded).hexdigest(),
    }


def source_record(path: Path, raw: bytes, declared_sha256: str | None = None) -> dict:
    actual = hashlib.sha256(raw).hexdigest()
    if declared_sha256 is not None and actual != declared_sha256:
        raise ValueError(f"source payload hash mismatch: {path}")
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": actual}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--native-exe", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")

    oracle = verified_json(ORACLE_MANIFEST, ORACLE_SHA256)
    paired = verified_json(PAIRED_MANIFEST, PAIRED_SHA256)
    native_receipt = verified_json(FULL_NATIVE_RECEIPT, FULL_NATIVE_RECEIPT_SHA256)
    if not native_receipt.get("pass"):
        raise ValueError("freeze011 ABI10.1 native source receipt is not passing")
    case = next(item for item in paired["cases"] if int(item["profile"]) == 2)
    if int(case["blocks"]) != 4 or int(case["slot_words"]) != 32768:
        raise ValueError("unexpected paired profile2 geometry")

    params_path, params_all = read_declared(PAIRED_MANIFEST.parent, case["params"])
    stride_words = v10.stride_words(64)
    stride_bytes = stride_words * 16
    if len(params_all) != stride_bytes * 4:
        raise ValueError("profile2 V10 parameter extent is not four strides")
    params_block0 = params_all[:stride_bytes]
    v10.validate_invocation(2, 1, stride_words, 32768, v10.arena_words(2), 0)
    v10.validate_metadata(params_block0, 2, 0)

    out.mkdir(parents=True)
    profile_dir = out / "profile2"
    params_source = source_record(params_path, params_all, case["params"]["sha256"])
    params_bin = write_binary(profile_dir / "params-block00-v10.1.bin", params_block0,
                              {**params_source, "byte_range": [0, stride_bytes]})
    params_mem = write_mem128(profile_dir / "params-block00.mem", params_block0,
                              {**params_source, "byte_range": [0, stride_bytes]})

    oracle_results = {item["sample_id"]: item for item in oracle["results"]}
    files: dict[str, dict] = {
        "params_block00_bin": params_bin,
        "params_block00_mem": params_mem,
    }
    native_args = ["paired", str(Path(params_bin["path"]))]
    for lane, sample in (("a", "image-00"), ("b", "image-01")):
        result = oracle_results[sample]
        input_decl = result["profile2_input_hcw"]
        input_path, input_raw = read_declared(ORACLE_MANIFEST.parent, input_decl)
        paired_image = next(image for image in case["images"] if image["sample"] == sample)
        if input_decl["sha256"] != paired_image["input"]["sha256"]:
            raise ValueError(f"paired/oracle input identity mismatch: {sample}")
        files[f"input_{lane}"] = write_mem128(
            profile_dir / f"input_{lane}.mem", input_raw,
            source_record(input_path, input_raw, input_decl["sha256"]),
        )
        block_paths = []
        for block, block_result in enumerate(result["blocks"]):
            if int(block_result["index"]) != block:
                raise ValueError(f"non-contiguous oracle block index: {sample}")
            expected_decl = block_result["output_hcw"]
            expected_path, expected_raw = read_declared(ORACLE_MANIFEST.parent, expected_decl)
            record = write_mem128(
                profile_dir / f"expected_{lane}_block{block:02d}.mem", expected_raw,
                source_record(expected_path, expected_raw, expected_decl["sha256"]),
            )
            files[f"expected_{lane}_block{block:02d}"] = record
            block_paths.append(record)
        native_args.extend([
            str(input_path), str(Path(block_paths[0]["source"]["path"])),
        ])

    # paired CLI ordering is params, input A, expected A, input B, expected B.
    native_args = [
        "paired", str(Path(params_bin["path"])),
        files["input_a"]["source"]["path"], files["expected_a_block00"]["source"]["path"],
        files["input_b"]["source"]["path"], files["expected_b_block00"]["source"]["path"],
        "2", "1", "1",
    ]
    native_crosscheck = {"executed": False, "pass": None}
    if args.native_exe is not None:
        native_exe = args.native_exe.resolve()
        if not native_exe.is_file():
            raise FileNotFoundError(native_exe)
        completed = subprocess.run(
            [str(native_exe), *native_args], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=False,
        )
        log = out / "native-block00-crosscheck.log"
        log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
        native_crosscheck = {
            "executed": True, "pass": completed.returncode == 0,
            "exit_code": completed.returncode, "args": native_args,
            "log": {"path": str(log.resolve()), "bytes": log.stat().st_size,
                    "sha256": sha256(log)},
            "product_source_receipt": {
                "path": str(FULL_NATIVE_RECEIPT.resolve()),
                "sha256": FULL_NATIVE_RECEIPT_SHA256,
                "source_sha256": native_receipt["source_sha256"],
            },
        }
        if completed.returncode != 0:
            raise RuntimeError("native block-0 cross-check failed")

    manifest_data = {
        "schema": "cnn-v10.1-n0-per-block-rtl-golden-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "HOST_ABI10_1_INDEPENDENT_ORACLE_READMEMH_FIXTURE_NOT_RTL_EXECUTION",
        "profile": 2,
        "short_case": {
            "block_count": 1, "params_words": stride_words,
            "slot_words": 32768, "arena_words": v10.arena_words(2), "flags": 0,
            "image_a": "image-00", "image_b": "image-01",
        },
        "write_scoreboard": {
            "block00_destination_slot": 1,
            "block00_word_offset": 32768,
            "block00_byte_offset": 32768 * 16,
            "address_rule": "arena_base + 0x80000 + 16*word_index",
            "word_index_range": [0, 32767],
            "compare": "A_WRITE WDATA against expected_a_block00.mem and B_WRITE WDATA against expected_b_block00.mem in accepted-beat order",
            "later_block_slots": {"block01": 0, "block02": 1, "block03": 0},
        },
        "word_format": "one 128-bit lowercase hexadecimal word per line; eight HCW int16 lanes; lane0 is bits[15:0]",
        "golden_origin": "frozen independent HOST wide-integer N0 oracle; no V10 product arithmetic used to generate expected data",
        "source_manifests": {
            "oracle": {"path": str(ORACLE_MANIFEST.resolve()), "sha256": ORACLE_SHA256},
            "v10_paired": {"path": str(PAIRED_MANIFEST.resolve()), "sha256": PAIRED_SHA256},
        },
        "files": files,
        "native_crosscheck": native_crosscheck,
        "limits": {
            "does_not_prove_rtl": True,
            "does_not_prove_timing": True,
            "does_not_authorize_deployment": True,
            "block01_through_block03_exports_are_debug_intermediates": True,
        },
    }
    manifest = out / "manifest.json"
    manifest.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
    receipt_data = {
        "schema": "cnn-v10.1-n0-per-block-rtl-golden-build-receipt-v1",
        "pass": (not native_crosscheck["executed"] or native_crosscheck["pass"]),
        "manifest": {"path": str(manifest.resolve()), "bytes": manifest.stat().st_size,
                     "sha256": sha256(manifest)},
        "builder": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__))},
        "expected_outputs": 8,
        "short_block0_word_count_per_image": 32768,
        "readmemh_round_trip_pass": all(
            record.get("round_trip_binary_sha256") == record.get("payload_sha256")
            for key, record in files.items() if key != "params_block00_bin"
        ),
        "native_crosscheck_pass": native_crosscheck["pass"],
    }
    receipt = out / "receipt.json"
    receipt.write_text(json.dumps(receipt_data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**receipt_data, "receipt_sha256": sha256(receipt)}, indent=2))
    return 0 if receipt_data["pass"] and receipt_data["readmemh_round_trip_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
