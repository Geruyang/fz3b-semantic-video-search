#!/usr/bin/env python3
"""Fail-closed static audit for an already transformed fused-ALU HLS IP."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

RTL_SUFFIXES = {".v", ".sv", ".vh", ".dat", ".mem", ".hex"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_inventory(root: Path) -> tuple[list[dict[str, object]], str]:
    entries = [
        {"path": p.relative_to(root).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size}
        for p in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if p.is_file() and p.suffix.lower() in RTL_SUFFIXES
    ]
    digest_records = [{"path": x["path"], "sha256": x["sha256"]} for x in entries]
    payload = json.dumps(digest_records, separators=(",", ":"), sort_keys=True).encode()
    return entries, hashlib.sha256(payload).hexdigest()


def module_counts(rtl_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    pattern = re.compile(r"(?m)^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b")
    for path in sorted(rtl_root.glob("*.v")):
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            counts[name] = counts.get(name, 0) + 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", required=True, type=Path)
    ap.add_argument("--transform-receipt", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    ip = args.ip.resolve()
    rtl = ip / "hdl" / "verilog"
    receipt = json.loads(args.transform_receipt.read_text(encoding="utf-8"))
    entries, rtl_digest = canonical_inventory(rtl)
    counts = module_counts(rtl)
    leaf = (rtl / "cnn_v10_pw_dsp16.v").read_text(encoding="utf-8")
    component = ip / "component.xml"
    ET.parse(component)
    checks = {
        "transform_pass": receipt.get("pass") is True,
        "transform_schema": receipt.get("schema") == "cnn-v10-pw-half2x-fused-alu-generated-rtl-transform-v1",
        "direct_leaf_instances_16": receipt.get("analysis", {}).get("direct_leaf_instances") == 16,
        "unique_module_definitions": all(value == 1 for value in counts.values()),
        "product_wrapper_once": counts.get("cnn_v10_pw_dsp16") == 1,
        "fullwidth_reference_once": counts.get("cnn_v10_pw_dsp16_fullwidth_reference") == 1,
        "fused_leaf_once": counts.get("cnn_v10_pw_dsp16_half2x_fused_alu") == 1,
        "fused_fast_once": counts.get("cnn_v10_pw_dsp8_fast_fused_alu") == 1,
        "wrapper_targets_fused": len(re.findall(r"\bcnn_v10_pw_dsp16_half2x_fused_alu\s+fused_half2x\s*\(", leaf)) == 1,
        "latency8_due_pipe": "reg [6:0] due_valid_pipe;" in leaf and "wire result_due = due_valid_pipe[6];" in leaf,
        "ii1_accept": "if (slow_ce && in_valid)" in leaf,
        "opmode_0x195": "9'h195" in leaf,
        "areg_breg2": ".AREG(EXTRA_AB_REG ? 2 : 1)" in leaf and ".BREG(EXTRA_AB_REG ? 2 : 1)" in leaf,
        "rtl_inventory_nonempty": len(entries) > 0,
    }
    result = {
        "schema": "cnn-v10-pw-half2x-fused-alu-static-audit-v1",
        "pass": all(checks.values()),
        "ip": str(ip),
        "transform_receipt": str(args.transform_receipt.resolve()),
        "transform_receipt_sha256": sha(args.transform_receipt),
        "component_sha256": sha(component),
        "rtl_inventory_digest": rtl_digest,
        "rtl_inventory_count": len(entries),
        "rtl_inventory": entries,
        "module_count": len(counts),
        "checks": checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not result["pass"]:
        raise SystemExit("fused transform static audit failed")
    print(f"CNN_V10_FUSED_ALU_STATIC_AUDIT_PASS rtl_digest={rtl_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
