"""Build the frozen three-image and 3+30 FZV5 board runtime configs."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "artifacts/board-debug-20261004/host/s1-onnx-001"
OUT = ROOT / "artifacts/board-debug-20261005/acceleration/host/network5-v5-runtime-configs-001"
MODEL_MANIFEST_SHA256 = "26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frame(frame_id, image_index):
    name = "image-%02d-input.f32" % image_index
    return {"frame_id": frame_id, "image": {"path": "inputs/" + name, "sha256": sha(OUT / "inputs" / name)}}


def write(name, preset, frames, max_in_flight):
    payload = {
        "schema_version": 1,
        "model_manifest_sha256": MODEL_MANIFEST_SHA256,
        "expected_ort_version": "1.16.3",
        "parameter_manifest_words": [0] * 8,
        "thread_preset": preset,
        "pipeline_options": {"queue_capacity": 2, "max_in_flight": max_in_flight,
                             "run_timeout_s": 300.0, "cleanup_timeout_s": 5.0},
        "frames": frames,
    }
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": name, "bytes": path.stat().st_size, "sha256": sha(path),
            "thread_preset": preset, "frames": len(frames)}


def main():
    if OUT.exists():
        raise FileExistsError(str(OUT))
    (OUT / "inputs").mkdir(parents=True)
    inputs = []
    for index in range(3):
        name = "image-%02d-input.f32" % index
        shutil.copyfile(SOURCE / name, OUT / "inputs" / name)
        inputs.append({"path": "inputs/" + name, "bytes": (OUT / "inputs" / name).stat().st_size,
                       "sha256": sha(OUT / "inputs" / name)})
    three = [frame(index, index) for index in range(3)]
    benchmark = [frame(index, index) for index in range(3)]
    benchmark += [frame(100 + index, index % 3) for index in range(30)]
    configs = [
        write("serial4-three-image.json", "serial4", three, 1),
        write("serial4-benchmark-33.json", "serial4", benchmark, 1),
        write("matched1_3-benchmark-33.json", "matched1_3", benchmark, 2),
    ]
    manifest = {"schema_version": 1, "status": "FZV5_BOARD_RUNTIME_CONFIGS_FROZEN",
                "model_manifest_sha256": MODEL_MANIFEST_SHA256,
                "inputs": inputs, "configs": configs,
                "benchmark_policy": {"warmup_frames": 3, "measured_frames": 30,
                                     "measured_ids": list(range(100, 130)),
                                     "image_rotation": [0, 1, 2]},
                "thread_consistency_manifest_sha256": "20fca1314e81642cba309307932e443908baf8473bfc7a101fa2cc8c6d033e02"}
    path = OUT / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "manifest_sha256": sha(path), "configs": configs}, indent=2))


if __name__ == "__main__":
    main()
