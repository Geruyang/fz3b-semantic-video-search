#!/usr/bin/env python3
"""Validate a future candidate's static contract and exact source manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


ROLES = {"adapter_source", "native_source", "implementation_source", "header"}
REQUIRED_ADAPTER_CALLS = (
    "pw1_physical_location",
    "dw7_fixed_bank_read",
    "dw7_normal_source_bank",
    "dw7_p3_source_bank",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--candidate-contract", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    requirements = json.loads(args.requirements.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate_contract.read_text(encoding="utf-8"))
    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    if candidate.get("schema") != requirements.get("schema"):
        raise SystemExit("candidate contract schema mismatch")
    for section in ("pw1", "dw7", "packed_accumulator"):
        if candidate.get(section) != requirements.get(section):
            raise SystemExit(f"candidate contract differs in {section}")
    if not isinstance(candidate.get("candidate_id"), str) or not candidate["candidate_id"]:
        raise SystemExit("candidate_id is required")
    if manifest.get("schema") != "dual-lane-storage-dw7-opt-source-manifest-v1":
        raise SystemExit("source manifest schema mismatch")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise SystemExit("source manifest is empty")
    if sum(1 for entry in entries if entry.get("role") == "adapter_source") != 1:
        raise SystemExit("source manifest must contain exactly one adapter_source")
    if sum(1 for entry in entries if entry.get("role") == "implementation_source") < 1:
        raise SystemExit("source manifest must bind at least one implementation_source")

    checked = []
    seen = set()
    for entry in entries:
        relative = PurePosixPath(entry.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts or str(relative) in ("", "."):
            raise SystemExit(f"unsafe manifest path: {relative}")
        if str(relative) in seen:
            raise SystemExit(f"duplicate manifest path: {relative}")
        seen.add(str(relative))
        if entry.get("role") not in ROLES:
            raise SystemExit(f"invalid role for {relative}")
        expected = entry.get("sha256", "").lower()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise SystemExit(f"invalid SHA256 for {relative}")
        path = args.candidate_root.joinpath(*relative.parts).resolve()
        root = args.candidate_root.resolve()
        if root not in path.parents:
            raise SystemExit(f"manifest path escapes candidate root: {relative}")
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"source hash mismatch: {relative}")
        if entry["role"] == "adapter_source":
            adapter_text = path.read_text(encoding="utf-8")
            missing = [name for name in REQUIRED_ADAPTER_CALLS if name not in adapter_text]
            if missing:
                raise SystemExit(
                    "adapter_source must call candidate helpers: " + ", ".join(missing)
                )
        checked.append({"path": str(relative), "role": entry["role"], "sha256": expected})

    receipt = {
        "schema": "dual-lane-storage-dw7-opt-static-gate-v1",
        "status": "PASS",
        "pass": True,
        "candidate_id": candidate["candidate_id"],
        "requirements_sha256": sha256(args.requirements),
        "candidate_contract_sha256": sha256(args.candidate_contract),
        "source_manifest_sha256": sha256(args.source_manifest),
        "files": checked,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
