#!/usr/bin/env python3
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import shutil
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-n1-native-target-005"
REMOTE = "/root/network10-v10.1-n1-native5-20261007"
WINDOW = "/root/network10-v10.1-board-window"
SEVEN = "/root/network10-v10.1-seven-opt-20261007"
FIX = "/root/network10-v10.1-ps-opt-20261007/fixtures"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
MODEL_SHA = "26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed"
INPUT_BUNDLE = REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-n1-native-bundle-004-input"
FINAL_BUNDLE = REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-n1-native-bundle-004"
ORACLE = REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-mixed-n1-native-oracle-003"
SOURCE = REPO / "desktop_vlm/board/cnn_v10_n1_native.c"
SOURCES = [
    REPO / "desktop_vlm/board/tests/target_cnn_v10_n1_native.py",
    REPO / "desktop_vlm/board/cnn_v10_n1_native_ctypes.py",
    REPO / "desktop_vlm/board/cnn_pipeline_v10_mixed_runtime.py",
    REPO / "desktop_vlm/board/cnn_v10_ps_shm_clients.py",
    REPO / "desktop_vlm/board/cnn_v10_native_quant.py",
    REPO / "desktop_vlm/board/cnn_v10_native_quant_ctypes.py",
    REPO / "desktop_vlm/board/activation_buffers.py",
]

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(client, name, command, report, timeout=180):
    value = helper.run(client, name, command, timeout)
    report["commands"].append(value)
    if value["exit_code"]:
        raise RuntimeError("%s failed: %s\n%s" %
                           (name, value["stdout"], value["stderr"]))
    return value


def main():
    if OUT.exists() or FINAL_BUNDLE.exists():
        raise RuntimeError("refusing to overwrite N1 target evidence/bundle")
    OUT.mkdir(parents=True)
    oracle_files = [ORACLE / ("image-%02d-mixed-fp32-fallback.f32" % i)
                    for i in (0, 1)]
    upload_sources = [SOURCE] + SOURCES
    files = upload_sources + [INPUT_BUNDLE / "manifest.json",
                              INPUT_BUNDLE / "n1-params.bin"] + oracle_files
    report = {
        "schema": "fz3b-v10.1-n1-native-target-wrapper-v2",
        "commands": [], "boot_id": BOOT, "device_operations": False,
        "trace18_pl_retained_without_driver": True,
        "uploads": [{"name": path.name, "bytes": path.stat().st_size,
                     "sha256": sha(path)} for path in files],
        "started_utc": datetime.datetime.now(
            datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    try:
        run(client, "preflight-trace18-no-driver",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test ! -e /sys/module/fpgadrv; test ! -e /dev/fpgadrv0; "
            "test ! -e /sys/module/cnn_ddr_v10_candidate; test ! -e /dev/network10_v10; "
            "test ! -e /sys/module/cnn_ddr_v10_wc_candidate; test ! -e /dev/network10_v10_wc_candidate; "
            "test \"$(findmnt -n -o FSTYPE /dev/shm)\" = tmpfs; "
            "test -z \"$(pgrep -f '[o]rt_partition_runner|[t]arget_cnn_v10_n1' || true)\"; "
            "test \"$(cat /sys/class/fpga_manager/fpga0/state)\" = operating; "
            "mkdir -p %s/src %s/bundle %s/oracle %s/results" %
            (BOOT, REMOTE, REMOTE, REMOTE, REMOTE), report)
        remote_paths = []
        sftp = client.open_sftp()
        try:
            for path in upload_sources:
                target = REMOTE + "/src/" + path.name
                sftp.put(str(path), target + ".part", confirm=True)
                sftp.posix_rename(target + ".part", target)
                remote_paths.append((path, target))
            for path in (INPUT_BUNDLE / "manifest.json", INPUT_BUNDLE / "n1-params.bin"):
                target = REMOTE + "/bundle/" + path.name
                sftp.put(str(path), target + ".part", confirm=True)
                sftp.posix_rename(target + ".part", target)
                remote_paths.append((path, target))
            for path in oracle_files:
                target = REMOTE + "/oracle/" + path.name
                sftp.put(str(path), target + ".part", confirm=True)
                sftp.posix_rename(target + ".part", target)
                remote_paths.append((path, target))
        finally:
            sftp.close()
        checked = run(client, "uploaded-sha",
            "sha256sum " + " ".join(shlex.quote(target)
                                      for unused, target in remote_paths), report)
        for path, unused in remote_paths:
            if sha(path) not in checked["stdout"]:
                raise RuntimeError("target SHA mismatch: %s" % path.name)
        target_source = REMOTE + "/src/" + SOURCE.name
        target_lib = REMOTE + "/bundle/libcnn_v10_n1_native.so"
        build = run(client, "compile-aarch64-neon-pthread-library",
            "set -eu; gcc -std=c99 -O3 -fPIC -shared -fno-fast-math "
            "-ffp-contract=off -march=armv8-a+simd -pthread -Wall -Wextra -Werror "
            "{src} -o {lib} -lm; file {lib}; "
            "nm -D --defined-only {lib} | grep 'cnn_v10_n1_'; sha256sum {lib}".format(
                src=shlex.quote(target_source), lib=shlex.quote(target_lib)), report, 300)
        for symbol in ("cnn_v10_n1_infer_int16_hcw", "cnn_v10_n1_infer_int16_hcw_scalar",
                       "cnn_v10_n1_infer_int16_hcw_profile"):
            if symbol not in build["stdout"]:
                raise RuntimeError("target N1 library lacks %s" % symbol)
        FINAL_BUNDLE.mkdir(parents=True)
        shutil.copy2(str(INPUT_BUNDLE / "n1-params.bin"),
                     str(FINAL_BUNDLE / "n1-params.bin"))
        shutil.copy2(str(SOURCE), str(FINAL_BUNDLE / SOURCE.name))
        sftp = client.open_sftp()
        try:
            sftp.get(target_lib, str(FINAL_BUNDLE / "libcnn_v10_n1_native.so"))
        finally:
            sftp.close()
        manifest = json.loads((INPUT_BUNDLE / "manifest.json").read_text(encoding="utf-8"))
        manifest["native_abi"]["library_path"] = "libcnn_v10_n1_native.so"
        manifest["native_abi"]["library_sha256"] = sha(
            FINAL_BUNDLE / "libcnn_v10_n1_native.so")
        manifest["native_abi"]["source_path"] = SOURCE.name
        manifest["native_abi"]["source_sha256"] = sha(SOURCE)
        manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        final_manifest = FINAL_BUNDLE / "manifest.json"
        final_manifest.write_bytes(manifest_raw)
        sftp = client.open_sftp()
        try:
            sftp.put(str(final_manifest), REMOTE + "/bundle/manifest.json.part", confirm=True)
            sftp.posix_rename(REMOTE + "/bundle/manifest.json.part",
                              REMOTE + "/bundle/manifest.json")
        finally:
            sftp.close()
        manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
        result = REMOTE + "/results/result.json"
        run(client, "target-n1-neon-pthread-stage-profile",
            "set -eu; cd {remote}/src; env ORT_PARTITION_ALLOW_SPINNING=0 "
            "ORT_PARTITION_PREALLOC_OUTPUTS=0 PYTHONDONTWRITEBYTECODE=1 "
            "PYTHONPATH={remote}/src:{window}/runtime python3 -B "
            "target_cnn_v10_n1_native.py --manifest {remote}/bundle/manifest.json "
            "--expected-manifest-sha256 {manifest_sha} "
            "--native-lib {remote}/bundle/libcnn_v10_n1_native.so "
            "--model-root {window}/release/models "
            "--model-manifest {window}/release/models/manifest.json "
            "--expected-model-manifest-sha256 {model_sha} "
            "--runner {seven}/bin/ort_partition_runner_v3 "
            "--fixture-root {fix}/image-00 --fixture-root {fix}/image-01 "
            "--oracle-output {remote}/oracle/image-00-mixed-fp32-fallback.f32 "
            "--oracle-output {remote}/oracle/image-01-mixed-fp32-fallback.f32 "
            "--threads 3 --warmup 1 --measured 3 --output {result}".format(
                remote=REMOTE, window=WINDOW, manifest_sha=manifest_sha,
                model_sha=MODEL_SHA, seven=SEVEN, fix=FIX, result=result),
            report, 900)
        sftp = client.open_sftp()
        try:
            sftp.get(result, str(OUT / "result.json"))
        finally:
            sftp.close()
        result_record = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
        if result_record.get("status") != "PASS_TARGET_NEON_SCALAR_EXACT_FP32_GELU_GATE":
            raise RuntimeError("N1 target gate did not pass")
        run(client, "postflight-trace18-no-driver",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test ! -e /sys/module/fpgadrv; test ! -e /dev/fpgadrv0; "
            "test ! -e /sys/module/cnn_ddr_v10_candidate; test ! -e /dev/network10_v10; "
            "test ! -e /sys/module/cnn_ddr_v10_wc_candidate; test ! -e /dev/network10_v10_wc_candidate; "
            "test -z \"$(pgrep -f '[o]rt_partition_runner|[t]arget_cnn_v10_n1' || true)\"; "
            "echo N1_NATIVE_TARGET_TRACE18_UNCHANGED_NO_DRIVER" % BOOT, report)
        report["result"] = {"bytes": (OUT / "result.json").stat().st_size,
                            "sha256": sha(OUT / "result.json")}
        report["final_bundle"] = {
            "path": str(FINAL_BUNDLE.relative_to(REPO)).replace("\\", "/"),
            "manifest_sha256": manifest_sha,
            "library_sha256": sha(FINAL_BUNDLE / "libcnn_v10_n1_native.so"),
            "source_sha256": sha(SOURCE),
            "params_sha256": sha(FINAL_BUNDLE / "n1-params.bin"),
        }
        report["status"] = "PASS_TARGET_N1_NATIVE_PTHREAD_NEON_TRACE18_UNCHANGED"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(
            datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest(),
                          "bundle": report.get("final_bundle")}, sort_keys=True))


if __name__ == "__main__":
    main()
