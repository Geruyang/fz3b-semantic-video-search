#!/usr/bin/env python3
"""Fail-closed structural audit for generated A0005 RTL/ROM.

This audit is intentionally separate from numerical simulation.  It checks
that HLS emitted the storage topology approved for A0005 before either XSIM or
platform synthesis may consume the snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(root: Path) -> tuple[str, list[dict[str, object]]]:
    records = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file() and path.suffix.lower() in {".v", ".sv", ".vh", ".dat", ".mem", ".hex"}:
            records.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            })
    payload = json.dumps(
        [{"path": item["path"], "sha256": item["sha256"]} for item in records],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), records


def module_bank_counts(files: list[Path], name_pattern: str, signal: str) -> list[dict[str, object]]:
    found = []
    pattern = re.compile(rf"\breg\s+{signal}(?:_\d+)?_ce0\s*;")
    for path in files:
        if not re.search(name_pattern, path.name):
            continue
        count = len(pattern.findall(path.read_text(encoding="utf-8", errors="replace")))
        if count:
            found.append({"file": path.name, "bank_count": count})
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtl-root", type=Path, required=True)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--expected-fused-leaf-sha256", required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-manifest-sha256", required=True)
    parser.add_argument("--candidate-contract", type=Path, required=True)
    parser.add_argument("--candidate-contract-sha256", required=True)
    parser.add_argument("--combined-manifest", type=Path, required=True)
    parser.add_argument("--combined-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.rtl_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"RTL root missing: {root}")
    for path, expected, label in (
        (args.source_manifest, args.source_manifest_sha256, "source manifest"),
        (args.candidate_contract, args.candidate_contract_sha256, "candidate contract"),
        (args.combined_manifest, args.combined_manifest_sha256, "combined manifest"),
    ):
        if not path.is_file() or sha256(path).lower() != expected.lower():
            raise SystemExit(f"{label} SHA256 mismatch")

    contract = json.loads(args.candidate_contract.read_text(encoding="utf-8"))
    identity = contract.get("identity", {})
    if (identity.get("core_abi"), identity.get("software"), identity.get("guard_caps")) != (
        "0x000A0005", "sw10.5", "0x00000fff"
    ):
        raise SystemExit("candidate identity is not A0005/sw10.5/0x00000fff")
    if identity.get("combined_parameter_manifest_sha256") != args.combined_manifest_sha256.lower():
        raise SystemExit("candidate contract does not bind the combined manifest")

    digest, inventory = canonical_digest(root)
    if digest != args.expected_digest.lower():
        raise SystemExit(f"canonical RTL/ROM digest mismatch: {digest}")
    verilog = [root / item["path"] for item in inventory if Path(str(item["path"])).suffix.lower() in {".v", ".sv"}]
    names = {path.name for path in verilog}
    if "cnn_pipeline_v10.v" not in names or "cnn_pipeline_v10_control_s_axi.v" not in names:
        raise SystemExit("generated top/control RTL is incomplete")
    if not any(Path(str(item["path"])).suffix.lower() == ".dat" for item in inventory):
        raise SystemExit("generated ROM .dat inventory is empty")

    fused_leaf = root / "cnn_v10_pw_dsp16.v"
    if not fused_leaf.is_file() or sha256(fused_leaf) != args.expected_fused_leaf_sha256.lower():
        raise SystemExit("generated snapshot does not bind the fused leaf")
    all_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in verilog)
    if "pw_fast_clk" not in all_text or "pw_fast_rst" not in all_text:
        raise SystemExit("generated RTL lacks the 400 MHz pointwise clock/reset ports")
    leaf_instances = len(re.findall(r"(?m)^\s*cnn_v10_pw_dsp16\s+\w+\s*\(", all_text))
    if leaf_instances < 16:
        raise SystemExit(f"expected at least 16 fused leaf instances, got {leaf_instances}")

    pw1_banks = module_bank_counts(
        verilog, r"pointwise_compute_[01]_false_256_s[.]v$", "row")
    if not pw1_banks or any(item["bank_count"] != 8 for item in pw1_banks):
        raise SystemExit(f"PW1 TDP physical-bank contract failed: {pw1_banks}")
    dw7_banks = module_bank_counts(
        verilog, r"depthwise_compute_[01]_7_16_true_s[.]v$", "rows")
    if not dw7_banks or any(item["bank_count"] != 16 for item in dw7_banks):
        raise SystemExit(f"DW7 fixed 16-bank contract failed: {dw7_banks}")

    fifo160 = sorted(name for name in names if "fifo_w160_d1024" in name)
    fifo192 = sorted(name for name in names if "fifo_w192_d1024" in name)
    if len(fifo160) < 2:
        raise SystemExit(f"PW2 packed signed40 storage is missing: {fifo160}")
    if fifo192:
        raise SystemExit(f"legacy PW2 192-bit storage remains: {fifo192}")

    receipt = {
        "schema": "cnn-v10.5-a0005-generated-rtl-structure-audit-v1",
        "status": "PASS",
        "pass": True,
        "identity": {"core_abi": "0x000A0005", "software": "sw10.5", "guard_caps": "0x00000fff"},
        "bindings": {
            "source_manifest_sha256": args.source_manifest_sha256.lower(),
            "candidate_contract_sha256": args.candidate_contract_sha256.lower(),
            "combined_manifest_sha256": args.combined_manifest_sha256.lower(),
            "rtl_rom_digest": digest,
            "fused_leaf_sha256": args.expected_fused_leaf_sha256.lower(),
        },
        "clock_contract": {"slow_mhz": 200, "fast_mhz": 400, "related": True},
        "structure": {
            "fused_leaf_instances": leaf_instances,
            "pw1_tdp_banks": pw1_banks,
            "dw7_fixed_banks": dw7_banks,
            "pw2_fifo_w160_d1024_files": fifo160,
            "legacy_fifo_w192_d1024_files": fifo192,
        },
        "inventory": inventory,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
