"""Create a reproducible receipt for the V10 host packer and frozen fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V9_RECEIPT = ROOT / "artifacts/board-debug-20261005/acceleration/jtag/cnn-v9-native-full-002/receipt.json"
PAIR = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001/manifest.json"
RTL = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-rtl-fixtures-001/manifest.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def meta(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha(path)}


def readmem_roundtrip(manifest: dict) -> int:
    checked = 0
    for case in manifest["cases"]:
        for item in case["files"].values():
            digest = hashlib.sha256(); words = 0
            with Path(item["path"]).open("r", encoding="ascii") as stream:
                for line in stream:
                    text = line.strip()
                    if len(text) != 32:
                        raise ValueError("readmem line is not one 128-bit hexadecimal word")
                    digest.update(int(text, 16).to_bytes(16, "little")); words += 1
            if digest.hexdigest() != item["source"]["sha256"] or words != item["word_count"]:
                raise ValueError("readmem roundtrip mismatch")
            checked += 1
    return checked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.evidence_dir.resolve()
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}")
    out.mkdir(parents=True)
    started = datetime.now(timezone.utc)
    test = HERE / "test_cnn_v10_param_contract.py"
    proc = subprocess.run([sys.executable, str(test)], cwd=ROOT,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / "host-tests.log").write_text(proc.stdout, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError("V10 host contract tests failed")
    rtl_manifest = json.loads(RTL.read_text(encoding="utf-8"))
    mem_count = readmem_roundtrip(rtl_manifest)
    v9 = json.loads(V9_RECEIPT.read_text(encoding="utf-8-sig"))
    v9_files = []
    base = ROOT / "desktop_vlm/hardware/acceleration"
    for name, expected in v9["source_sha256"].items():
        path = base / name; actual = sha(path)
        if actual != expected:
            raise RuntimeError(f"V9 source changed: {name}")
        v9_files.append({"path": str(path.resolve()), "sha256": actual})
    sources = [HERE / name for name in (
        "cnn_v10_param_contract.py", "cnn_v10_pack.py",
        "test_cnn_v10_param_contract.py", "build_cnn_v10_paired_fixtures.py",
        "build_cnn_v10_paired_rtl_fixtures.py", "audit_cnn_v10_host_contract.py")]
    receipt = {
        "schema": "cnn-v10.1-host-contract-audit-v1",
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "pass": True,
        "scope": "host parameter repack, ABI gate, frozen paired golden, readmem adapter; no HLS/RTL/route/board claim",
        "host_tests": {"exit_code": proc.returncode, "log": meta(out / "host-tests.log")},
        "readmem_roundtrip": {"files": mem_count, "pass": True},
        "paired_manifest": meta(PAIR),
        "rtl_fixture_manifest": meta(RTL),
        "source_files": [meta(path) for path in sources],
        "v9_sources_unchanged": True,
        "v9_source_files": v9_files,
        "native_v10_kernel_status": "pending separate O2 CSIM receipt",
        "board_operations": False,
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": True, "receipt": meta(out / "receipt.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
