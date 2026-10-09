import ast
import hashlib
import json
import pathlib
import shutil


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PRIOR = (ROOT / "artifacts/board-debug-20261008/acceleration/host/"
         "network10-v10.4-software-snapshot-004/manifest.json")
prior = json.loads(PRIOR.read_text(encoding="utf-8"))
sources = {item["path"] for item in prior["runtime_sources"]}
sources.update({
    "desktop_vlm/board/cnn_ddr_v10_signed40_candidate_runtime.py",
    "desktop_vlm/board/cnn_pipeline_v10_signed40_deployment.py",
    "desktop_vlm/board/cnn_pipeline_v10_signed40_parameters.py",
    "desktop_vlm/board/cnn_pipeline_v10_signed40_runtime.py",
    "desktop_vlm/board/cnn_v10_pw2_signed40_contract.py",
})
runtime = HERE / "runtime"
runtime.mkdir()
records = []
for source_name in sorted(sources):
    source = ROOT / pathlib.PurePosixPath(source_name)
    raw = source.read_bytes()
    ast.parse(raw.decode("utf-8"), filename=source_name, feature_version=(3, 6))
    destination = runtime / source.name
    if destination.exists():
        raise RuntimeError("duplicate runtime basename: %s" % source.name)
    shutil.copyfile(str(source), str(destination))
    records.append({
        "path": "runtime/" + source.name,
        "source_path": source_name,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    })
manifest = {
    "schema": "cnn-v10.5-a0005-software-snapshot-v1",
    "status": "PASS_HOST_PYTHON36_AST_TARGET_PENDING",
    "identity": {
        "core_abi": "0x000A0005", "guard_caps": "0x00000FFF",
        "combined_parameter_manifest_sha256":
            "4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690",
        "deployment_manifest_sha256":
            "6e01472fae50fcab672bf8a6097648630618b8b304c860f0703472cd6ec1d2f3",
    },
    "validation": {
        "focused_tests": "40 passed",
        "python36_ast": "PASS",
        "target_python36_py_compile": "PENDING",
        "board_execution": False,
    },
    "runtime_sources": records,
    "reuse": {
        "base_runtime_snapshot_sha256":
            hashlib.sha256(PRIOR.read_bytes()).hexdigest(),
        "base_runtime_snapshot_path": PRIOR.relative_to(ROOT).as_posix(),
    },
}
raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
(HERE / "manifest.json").write_bytes(raw)
receipt = {
    "schema": "cnn-v10.5-a0005-software-snapshot-receipt-v1",
    "status": "PASS_HOST_TARGET_PENDING", "pass": True,
    "manifest_sha256": hashlib.sha256(raw).hexdigest(),
    "file_count": len(records),
    "payload_bytes": sum(item["bytes"] for item in records),
    "board_operations": False,
}
(HERE / "receipt.json").write_bytes(
    (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(json.dumps(receipt, sort_keys=True))
