"""Convert the frozen V10 paired binaries to 128-bit $readmemh fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import cnn_v10_param_contract as v10

SOURCE_MANIFEST = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001/manifest.json"
SOURCE_SHA256 = "83df8803b7a8eb08795c6c19d89538637f850df9044c407b90814d725f0079c4"
OUT = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-rtl-fixtures-001"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_mem128(source: Path, destination: Path) -> dict:
    size = source.stat().st_size
    if size % 16:
        raise ValueError(f"128-bit alignment required: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with source.open("rb") as inp, destination.open("w", encoding="ascii", newline="\n") as out:
        while True:
            word = inp.read(16)
            if not word:
                break
            if len(word) != 16:
                raise ValueError("short final 128-bit word")
            out.write(f"{int.from_bytes(word, 'little'):032x}\n")
            count += 1
    return {"path": str(destination.resolve()), "bytes": destination.stat().st_size,
            "sha256": sha(destination), "word_count": count,
            "source": {"path": str(source.resolve()), "bytes": size, "sha256": sha(source)}}


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    if sha(SOURCE_MANIFEST) != SOURCE_SHA256:
        raise ValueError("frozen ABI10.1 paired manifest SHA mismatch")
    source = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True)
    cases = []
    for case in source["cases"]:
        profile = int(case["profile"])
        case_dir = OUT / f"profile{profile}"
        params_bin = Path(case["params"]["path"])
        files = {"params": write_mem128(params_bin, case_dir / "params.mem")}
        for lane, image in zip(("a", "b"), case["images"]):
            files[f"input_{lane}"] = write_mem128(Path(image["input"]["path"]),
                                                   case_dir / f"input_{lane}.mem")
            files[f"expected_{lane}"] = write_mem128(Path(image["expected"]["path"]),
                                                      case_dir / f"expected_{lane}.mem")
        cfg = v10.profile_config(profile)
        if files["params"]["word_count"] != int(case["params_words"]):
            raise AssertionError("params.mem word count mismatch")
        for name in ("input_a", "input_b", "expected_a", "expected_b"):
            if files[name]["word_count"] != cfg["slot_words"]:
                raise AssertionError(f"{name} word count mismatch")
        cases.append({"name": case["name"], "profile": profile,
                      "blocks": case["blocks"], "params_words": case["params_words"],
                      "slot_words": case["slot_words"], "arena_words": case["arena_words"],
                      "flags": 0, "files": files})
    result = {
        "schema": "cnn-v10.1-paired-rtl-fixtures-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "HOST_ABI10_1_READMEMH_FIXTURES_NOT_RTL_EXECUTION",
        "board_operations": False,
        "source_manifest": {"path": str(SOURCE_MANIFEST.resolve()),
                            "sha256": sha(SOURCE_MANIFEST)},
        "word_format": "one 128-bit lowercase hexadecimal word per line; source bytes interpreted little-endian",
        "cases": cases,
        "reject_contract": [
            {"kind": "top_descriptor", "mutations": ["profile", "block_count", "params_words", "slot_words", "arena_words", "flags"],
             "expected_protocol_error": 1, "activation_accesses": 0},
            {"kind": "metadata", "mutation": "set first signed shift to 63 in params_pw1 or params_pw2",
             "expected_protocol_error": 2, "activation_accesses": 0},
            {"kind": "compact_gelu_aligned_tail", "mutation": "replace first compact lane at tail_start with 32766",
             "expected_protocol_error": 2, "activation_accesses": 0},
        ],
    }
    manifest = OUT / "manifest.json"
    manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    receipt = {"schema": "cnn-v10.1-paired-rtl-fixture-build-receipt-v1", "pass": True,
               "manifest": {"path": str(manifest.resolve()), "bytes": manifest.stat().st_size,
                            "sha256": sha(manifest)},
               "source_sha256": sha(Path(__file__)), "cases": len(cases)}
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
