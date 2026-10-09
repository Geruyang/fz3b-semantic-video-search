"""Build ABI10.1 parameter files and a paired two-image native/RTL manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import cnn_v10_pack as packer
import cnn_v10_param_contract as v10

OUT = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001"
V9_RECEIPT = ROOT / "artifacts/board-debug-20261005/acceleration/jtag/cnn-v9-native-full-002/receipt.json"

SOURCES = {
    0: ROOT / "artifacts/board-debug-20261005/acceleration/host/root-v5-full-fixtures-001/profile0",
    1: ROOT / "artifacts/board-debug-20261005/acceleration/host/root-v5-full-fixtures-001/profile1",
    2: ROOT / "artifacts/board-debug-20261005/acceleration/host/root-v5-profile2-full-fixtures-001/profile2",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_meta(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    OUT.mkdir(parents=True)
    cases = []
    repacks = []
    for profile in (2, 0, 1):
        cfg = v10.profile_config(profile)
        blocks = cfg["max_blocks"]
        src_root = SOURCES[profile]
        source_params = src_root / f"params-{blocks}-blocks.bin"
        output_params = OUT / f"profile{profile}-params-{blocks}-blocks-v10.1.bin"
        repacks.append(packer.repack_file(source_params, output_params, profile, blocks))
        images = []
        for sample in ("image-00", "image-01"):
            input_path = src_root / sample / "input-hcw.i16"
            expected_path = src_root / sample / f"expected-{blocks}-blocks-hcw.i16"
            images.append({"sample": sample, "input": file_meta(input_path),
                           "expected": file_meta(expected_path)})
        cases.append({
            "name": f"paired-p{profile}-full-image00-image01",
            "profile": profile, "blocks": blocks, "params": file_meta(output_params),
            "params_words": blocks * v10.stride_words(cfg["channels"]),
            "slot_words": cfg["slot_words"], "arena_words": v10.arena_words(profile),
            "flags": 0, "images": images,
            "golden_rule": "both outputs must be byte-exact to the independently frozen FZV5 host-wide integer oracle",
        })

    v9_receipt = json.loads(V9_RECEIPT.read_text(encoding="utf-8-sig"))
    base = ROOT / "desktop_vlm/hardware/acceleration"
    v9_frozen = []
    for name, expected in v9_receipt["source_sha256"].items():
        path = base / name
        actual = sha(path)
        if actual != expected:
            raise RuntimeError(f"V9 changed before V10 fixture build: {name}")
        v9_frozen.append({"path": str(path.resolve()), "sha256": actual})

    manifest = {
        "schema": "cnn-v10.1-paired-fixtures-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "HOST_ABI10_1_PAIRED_GOLDEN_NOT_PL",
        "board_operations": False,
        "identity": {"core": f"0x{v10.CORE_IDENTITY:08X}",
                     "abi": f"0x{v10.ABI_IDENTITY:08X}", "software": v10.SOFTWARE_IDENTITY},
        "compute_contract": {"dw3_macs_per_core": 4, "dw7_macs_per_core": 16,
                             "pw1_macs_per_core": 64, "pw2_macs_per_core": 64,
                             "pw1_tile": "output-group outer, reduction inner; tile is 4 outputs x 16 inputs",
                             "pw2_tile": "reduction outer, output-group inner; tile is 4 outputs x 16 inputs",
                             "numeric": "signed INT16; signed48 accumulator; signed80 exact product; ties-even; clamp [-32767,32767]"},
        "parameter_contract": {"compact_gelu_entries": v10.GELU_STORAGE_ENTRIES,
                               "compact_gelu_words": v10.GELU_STORAGE_WORDS,
                               "stride_words": {str(p): v10.stride_words(cfg["channels"])
                                                for p, cfg in v10.PROFILE_CONFIG.items()}},
        "arena_contract": "per image: slot0, slot1, then 4096 128-bit-word residual ring; A and B use independent backing arenas",
        "repacked_parameters": repacks,
        "cases": cases,
        "golden_provenance": {"kind": "existing frozen host-wide integer fixtures previously passed by V9 native CSIM",
                              "v9_native_receipt": file_meta(V9_RECEIPT)},
        "v9_frozen_sources": v9_frozen,
        "sources": [file_meta(Path(__file__)), file_meta(HERE / "cnn_v10_pack.py"),
                    file_meta(HERE / "cnn_v10_param_contract.py")],
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    receipt = {"schema": "cnn-v10.1-paired-fixture-build-receipt-v1", "pass": True,
               "manifest": file_meta(manifest_path), "v9_sources_unchanged": True,
               "profiles": [2, 0, 1], "paired_images": ["image-00", "image-01"]}
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
