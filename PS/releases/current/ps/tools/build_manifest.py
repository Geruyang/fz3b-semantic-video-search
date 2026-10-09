from __future__ import print_function

import datetime
import hashlib
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.json"
HASH_FILE = ROOT / "manifest.sha256"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    excluded = {MANIFEST, HASH_FILE}
    files = []
    for path in sorted(p for p in ROOT.rglob("*") if p.is_file() and p not in excluded):
        files.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    manifest = {
        "schema": "fz3b-network10-v10.5-a0005-current-ps-release-v1",
        "status": "FROZEN",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "identity": {
            "core_id": "0x465A5641",
            "core_abi": "0x000A0005",
            "guard_caps": "0x00000FFF",
            "software_uapi": 10,
            "combined_parameter_manifest_sha256": "4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690",
            "deployment_manifest_sha256": "6e01472fae50fcab672bf8a6097648630618b8b304c860f0703472cd6ec1d2f3",
            "bitstream_sha256": "a7950894715edd4e0f535b094e4a7866a220bd44f7158d153bb8e927d07bdebc",
        },
        "runtime": {
            "driver_job_hz": 199999998,
            "pw_local_hz": 399999996,
            "device": "/dev/network10_v10_signed40",
            "ps_schedule": "split",
            "front_threads": 1,
            "suffix_threads": 3,
            "max_in_flight": 4,
        },
        "board_paths": {
            "current_runtime": "/root/network10-v10.5-a0005-retained-current",
            "payload": "/root/workspace/network10-v10.5-a0005-board-validation-001",
            "lease": "/root/workspace/network10-v10.4-pl1-iopll-lease-candidate-001",
            "clock_reader": "/root/workspace/network10-v10.4-clock-raw-baseline-001",
            "factory_backup": "/root/workspace/factory-backups/network10-factory-20261009-a0005-retained",
        },
        "validated_results": {
            "exact_receipt_sha256": "8183b27341e36cc46cabaf051ce57a6f756ebef129ea6392426bad0263224e3f",
            "fair30_fps": 3.9040067841352677,
            "stable100_fps": 4.097891941292624,
            "fullmodel_receipt_sha256": "0b5cb7bff6c104757021aab54efbe1c404bcda7231cfcfd73d7c074faf4449a5",
            "min_feature_cosine": 0.9990328381,
            "max_feature_relative_l2": 0.0442316415,
        },
        "external_platform_dependencies": {
            "kernel_release": "4.14.0-xilinx-v2018.3",
            "glibc_sha256": "8136ae20c45cb7984d46a1d2f1fd6158990e42bcbfbdc350d70f6b1e41dccddd",
            "libstdcxx_sha256": "b907165b025fd2a17acad58755269b2b00e9fe667f34fdbb6ca64952b8cbfa03",
            "note": "Kernel/glibc/libstdc++ remain BSP platform dependencies; ONNX Runtime 1.16.3 is included in runtime-libs.",
        },
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
    }
    data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    MANIFEST.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    HASH_FILE.write_text(digest + "  manifest.json\n", encoding="ascii")
    print(str(MANIFEST))
    print(digest)
    print(len(files), manifest["total_bytes"])


if __name__ == "__main__":
    main()
