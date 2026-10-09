#!/usr/bin/env python3
"""Target-qualify N1 mask16/mask32 packages and run four short full-model gates."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import shutil
from pathlib import Path

import run_cnn_v10_wc_live_and_ab as common


OUT = common.REPO / (
    "artifacts/board-debug-20261007/acceleration/network/"
    "network10-v10.1-n1-refined-short-002")
SOURCE = common.REPO / (
    "artifacts/board-debug-20261007/acceleration/host/"
    "cnn-v10-n1-ps-mask-bundles-001")
MODEL_MANIFEST_SHA = "26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed"
MASKS = ("mask16", "mask32")


def _utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _record(path):
    path = Path(path)
    return {"path": path.name, "bytes": path.stat().st_size,
            "sha256": _sha(path)}


def _target_command(mask, remote):
    native_manifest = SOURCE / mask / "packed/native-manifest.json"
    expected = _sha(native_manifest)
    return (
        "set -eu; cd {r}/runtime; env ORT_PARTITION_ALLOW_SPINNING=0 "
        "ORT_PARTITION_PREALLOC_OUTPUTS=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. "
        "python3 -B target_cnn_v10_n1_native.py "
        "--manifest {m}/native-manifest.json --expected-manifest-sha256 {sha} "
        "--native-lib {m}/libcnn_v10_n1_native.so "
        "--model-root {b}/release/models --model-manifest {b}/release/models/manifest.json "
        "--expected-model-manifest-sha256 {modelsha} --runner {r}/bin/ort_partition_runner_v3 "
        "--fixture-root /root/network10-v10.1-ps-opt-20261007/fixtures/image-00 "
        "--fixture-root /root/network10-v10.1-ps-opt-20261007/fixtures/image-01 "
        "--oracle-output {m}/image-00-output.f32 --oracle-output {m}/image-01-output.f32 "
        "--threads 3 --warmup 1 --measured 3 --output {m}/target-result-live.json"
    ).format(r=common.REMOTE, b=common.BASE, m=remote, sha=expected,
             modelsha=MODEL_MANIFEST_SHA)


def _benchmark(label, selection, suffix):
    suffix_arg = ("--suffix-candidate %s/suffix-selection/selection-manifest.json" %
                  common.REMOTE) if suffix else ""
    inner = (
        "cd {r}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B "
        "benchmark_cnn_pipeline_v10_live.py --bundle-root {b}/release "
        "--expected-bundle-sha256 {rel} --deployment-manifest {b}/platform/manifest.json "
        "--expected-deployment-sha256 {dep} --runner {r}/bin/ort_partition_runner_v3 "
        "--ps-client mixed --native-lib {r}/bin/libcnn_v10_native_quant.so "
        "--n1-manifest {selection} {suffix} --threads 3 --max-in-flight 3 "
        "--warmup-pairs 3 --measured-pairs 10 --timeout-s 300 --device /dev/network10_v10 "
        "--input-tensor {b}/inputs/image-00-input.f32 "
        "--input-tensor {b}/inputs/image-01-input.f32 "
        "--expected-feature-sha256 {s0} --expected-feature-sha256 {s1} "
        "--reference-feature {r}/references/image-00-feature.f32 "
        "--reference-feature {r}/references/image-01-feature.f32 "
        "--output-dir {r}/results/{label}"
    ).format(r=common.REMOTE, b=common.BASE, rel=common.RELEASE,
             dep=common.DEPLOY, selection=selection, suffix=suffix_arg,
             s0=common.EXPECTED[0], s1=common.EXPECTED[1], label=label)
    return ("set -eu; env ORT_PARTITION_ALLOW_SPINNING=0 "
            "ORT_PARTITION_PREALLOC_OUTPUTS=0 sh -c %s" % shlex.quote(inner))


def _materialize_selection(mask, target_result, target_command):
    source = SOURCE / mask / "packed"
    destination = OUT / mask
    shutil.copytree(source, destination)
    result_path = destination / "target-result.json"
    result_path.write_bytes(target_result)
    manifest_sha = _sha(destination / "native-manifest.json")
    library_sha = _sha(destination / "libcnn_v10_n1_native.so")
    params_sha = _sha(destination / "n1-params.bin")
    target = json.loads(target_result.decode("utf-8"))
    if (target.get("status") != "PASS_TARGET_NEON_SCALAR_EXACT_FP32_GELU_GATE" or
            target.get("manifest_sha256") != manifest_sha or
            target.get("library_sha256") != library_sha):
        raise RuntimeError("%s target result identity/status mismatch" % mask)
    receipt = {
        "schema": "fz3b-v10.1-n1-native-target-wrapper-v2",
        "status": "PASS_TARGET_N1_NATIVE_PTHREAD_NEON_TRACE18_UNCHANGED",
        "boot_id": common.BOOT,
        "device_operations": False,
        "trace18_pl_retained": True,
        "target_command": target_command,
        "final_bundle": {"manifest_sha256": manifest_sha,
                         "library_sha256": library_sha,
                         "params_sha256": params_sha,
                         "source_sha256": json.loads(
                             (destination / "native-manifest.json").read_text(
                                 encoding="utf-8"))["native_abi"]["source_sha256"]},
        "result": {"bytes": len(target_result),
                   "sha256": hashlib.sha256(target_result).hexdigest()},
    }
    common.write_json(destination / "target-receipt.json", receipt)
    selection_path = destination / "selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["status"] = "PASS"
    selection["target_receipt"] = _record(destination / "target-receipt.json")
    selection["target_result"] = _record(result_path)
    selection["runtime_eligibility"] = "PASS_TARGET_PROVEN"
    common.write_json(selection_path, selection)
    return destination, selection_path


def main():
    if OUT.exists():
        raise RuntimeError("refusing overwrite")
    OUT.mkdir(parents=True)
    receipt = {"schema": "fz3b-v10.1-n1-refined-short-v1",
               "status": "FAILED", "boot_id": common.BOOT,
               "started_utc": _utc(), "commands": [], "masks": {}}
    target_script = common.REPO / "desktop_vlm/board/tests/target_cnn_v10_n1_native.py"
    runtime_files = [
        common.REPO / "desktop_vlm/board/cnn_pipeline_v10_mixed_runtime.py",
        common.REPO / "desktop_vlm/board/cnn_pipeline_v10_live_runtime.py",
        common.REPO / "desktop_vlm/board/cnn_pipeline_v10_delivery.py",
        common.REPO / "desktop_vlm/board/benchmark_cnn_pipeline_v10_live.py",
        target_script,
    ]
    client = common.helper.connect()
    try:
        common.run(client, "same-boot-base-quiesced-preflight",
                   "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
                   "test \"$(cat /sys/class/fpga_manager/fpga0/state)\" = operating; "
                   "grep -qx applied %s/status; test -d /sys/module/cnn_ddr_v10_candidate; "
                   "test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 0; "
                   "test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"" %
                   (common.BOOT, common.BASE_OVERLAY), receipt)
        sftp = client.open_sftp()
        try:
            for path in runtime_files:
                common.upload(sftp, path, common.REMOTE + "/runtime/" + path.name)
            for mask in MASKS:
                remote = common.REMOTE + "/n1-refined2/" + mask
                for path in (SOURCE / mask / "packed").iterdir():
                    if path.is_file():
                        common.upload(sftp, path, remote + "/" + path.name)
                common.upload(sftp, SOURCE / mask / ("image-00-ps-%s-output.f32" % mask),
                              remote + "/image-00-output.f32")
                common.upload(sftp, SOURCE / mask / ("image-01-ps-%s-output.f32" % mask),
                              remote + "/image-01-output.f32")
        finally:
            sftp.close()
        common.run(client, "python36-runtime-compile",
                   "set -eu; cd %s/runtime; PYTHONDONTWRITEBYTECODE=1 python3 -B -m py_compile %s" %
                   (common.REMOTE, " ".join(path.name for path in runtime_files)), receipt)

        materialized = {}
        for mask in MASKS:
            remote = common.REMOTE + "/n1-refined2/" + mask
            command = _target_command(mask, remote)
            common.run(client, "target-" + mask, command, receipt, 900)
            sftp = client.open_sftp()
            try:
                with sftp.open(remote + "/target-result-live.json", "rb") as stream:
                    raw = stream.read()
            finally:
                sftp.close()
            destination, selection = _materialize_selection(mask, raw, command)
            validated = remote + "/validated"
            sftp = client.open_sftp()
            try:
                for path in destination.iterdir():
                    if path.is_file():
                        common.upload(sftp, path, validated + "/" + path.name)
            finally:
                sftp.close()
            materialized[mask] = (destination, validated + "/selection.json")

        common.run(client, "reload-base-for-short-gates",
                   "set -eu; /sbin/rmmod cnn_ddr_v10_candidate; "
                   "/sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko; "
                   "test -c /dev/network10_v10" % common.BASE, receipt)
        for mask in MASKS:
            mask_record = {"selection_sha256": _sha(materialized[mask][0] / "selection.json"),
                           "runs": {}}
            receipt["masks"][mask] = mask_record
            for suffix in (False, True):
                variant = "combined-suffix" if suffix else "n1-only"
                label = "n1-%s-%s-short10" % (mask, variant)
                command = _benchmark(label, materialized[mask][1], suffix)
                outcome = common.run(client, "run-" + label, command, receipt, 1800, allow=True)
                remote_result = common.REMOTE + "/results/" + label + "/result.json"
                local_result = OUT / mask / (variant + "-result.json")
                sftp = client.open_sftp()
                try:
                    sftp.get(remote_result, str(local_result))
                finally:
                    sftp.close()
                value = json.loads(local_result.read_text(encoding="utf-8"))
                features = value.get("measured", {}).get("features", [])
                mask_record["runs"][variant] = {
                    "command_exit_code": outcome["exit_code"],
                    "status": value.get("status"),
                    "result_sha256": _sha(local_result),
                    "fps": value.get("measured", {}).get("fps_including_fill_and_drain"),
                    "min_cosine": min((item.get("cosine", 1.0) for item in features),
                                      default=None),
                    "max_relative_l2": max((item.get("relative_l2", 0.0)
                                             for item in features), default=None),
                    "feature_protocol_pass": value.get("measured", {}).get(
                        "feature_protocol_pass"),
                }
                if not suffix and not mask_record["runs"][variant]["feature_protocol_pass"]:
                    raise RuntimeError("%s N1-only full-model engineering gate failed" % mask)
        receipt["status"] = "PASS_REFINED_N1_TARGET_AND_SHORT_GATES_RECORDED"
    finally:
        client.close()
        receipt["finished_utc"] = _utc()
        raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": receipt["status"],
                          "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
