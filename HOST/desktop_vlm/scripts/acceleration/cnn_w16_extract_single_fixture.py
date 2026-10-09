"""Extract one real FP32-source W16 profile/block fixture from a joint run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
JOINT = HOST / "network-w16-joint-oracle-001"
OUT = HOST / "network4-w16-profile1-block0-fixture-003"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(out, rel, data, dtype=None, shape=None):
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    item = {"path": rel.replace("\\", "/"), "bytes": len(data), "sha256": sha(path)}
    if dtype is not None:
        item["dtype"], item["shape"] = dtype, list(shape)
    return item


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    joint_path = JOINT / "manifest.json"
    joint = json.loads(joint_path.read_text(encoding="utf-8"))
    image = next(x for x in joint["results"] if x["sample_id"] == "image-00")
    param_path = JOINT / "params/profile1/block-00.bin"
    input_path = JOINT / image["profile1_input_i16"]["path"]
    output_path = JOINT / image["profile1_blocks"][0]["output"]["path"]
    if sha(param_path) != joint["profiles"]["profile1"]["params"][0]["sha256"]:
        raise ValueError("profile1 block0 parameter checksum does not match joint manifest")
    q = np.fromfile(output_path, dtype="<i2").reshape(256, 16, 16)
    q_hcw = np.ascontiguousarray(q.transpose(1, 0, 2), dtype="<i2")
    OUT.mkdir(parents=True)
    params_meta = write(OUT, "params-profile1-block0.bin", param_path.read_bytes())
    input_meta = write(OUT, "image-00/input-hcw.i16le", input_path.read_bytes(), "<i2", (16, 256, 16))
    output_meta = write(OUT, "image-00/expected-add-hcw.i16le", q_hcw.tobytes(), "<i2", (16, 256, 16))
    chw_meta = write(OUT, "image-00/expected-add-chw.i16le", output_path.read_bytes(), "<i2", (256, 16, 16))
    manifest = {
        "schema_version": 1, "status": "HOST_REAL_FP32_SOURCE_W16_PROFILE1_BLOCK0_NOT_PL",
        "abi": {"magic": "FZV5", "version": 0x00050000, "flags": 0},
        "profile": 1, "block_index": 0, "block_count": 1,
        "source": {"joint_manifest_sha256": sha(joint_path),
                   "source_model_sha256": joint["source_hashes"]["model_sha256"],
                   "n3_input_provenance": "actual prefix + full N2 W16 + real network3 bridge from joint HOST chain",
                   "parameter_provenance": "FP32 source per-output symmetric INT16 quantization from joint oracle",
                   "expected_output_provenance": "same independent W16 oracle profile1 block0 Add"},
        "parameters": {"path": params_meta["path"], "bytes": params_meta["bytes"], "sha256": params_meta["sha256"],
                       "stride_bytes": 976912, "parameter_words_128b": 61057},
        "activation_layout": {"dtype": "<i2", "serialization": "HCW", "slots": 2,
                              "slot_bytes": 131072, "input": input_meta, "expected_output": output_meta,
                              "expected_output_chw": chw_meta},
        "claims": {"host_only": True, "pl_execution": False,
                   "true_fp32_source_w16_weights": True,
                   "valid_for_bit_exact_kernel_check": True,
                   "quality": "single block only; see joint manifest for full quality evaluation"},
    }
    manifest["files"] = {p.relative_to(OUT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)}
                         for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    path = OUT / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "manifest_sha256": sha(path),
                      "params": str(OUT / "params-profile1-block0.bin"), "params_sha256": sha(OUT / "params-profile1-block0.bin"),
                      "input": str(OUT / "image-00/input-hcw.i16le"), "input_sha256": sha(OUT / "image-00/input-hcw.i16le"),
                      "expected": str(OUT / "image-00/expected-add-hcw.i16le"), "expected_sha256": sha(OUT / "image-00/expected-add-hcw.i16le"),
                      "stride_bytes": 976912, "parameter_words_128b": 61057,
                      "activation_bytes": input_meta["bytes"]}, indent=2))


if __name__ == "__main__":
    main()
