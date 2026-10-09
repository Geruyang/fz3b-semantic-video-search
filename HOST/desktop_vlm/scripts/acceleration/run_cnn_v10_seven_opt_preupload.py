#!/usr/bin/env python3
"""Stage the frozen PS candidates, prove live no-map, then unload factory."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-seven-opt-preupload-001"
REMOTE = "/root/network10-v10.1-seven-opt-20261007"
BOARD_WINDOW = "/root/network10-v10.1-board-window"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
BASE_DEPLOYMENT_SHA = "531cb46623c760df3c09f56cb285e6dff3320da44c1f3570af3e02e98754ea3d"
RELEASE_SHA = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
FACTORY_DRIVER_SHA = "a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f"
FACTORY_BIT_SHA = "59e1a6176194eccc05603738ba3c2e71ea25c3c09cdf9dce47ed1ad1ddf5fc2e"
TRACE18_BIT_SHA = "8bfeb3ee66fb717628c532bf44b4573c6db0ab0e1f0c1cec87b45c218778ead6"
TRACE18_LTX_SHA = "441a7baa66d77746a4e1fee8ebe7a140917f799f9de461928be6af7bd4dcb864"
RUNNER_V3_SHA = "0a8a94e2d553508baa958a741ea8d0e5c9f68d1f2a589d75d64860c825fc4f96"
NATIVE_QUANT_SHA = "055b65885600fca6bcd85f7d1ba5a5e821a2eb678888d7ac340b726b65faa059"

RUNTIME = [
    "cnn_ddr_v6_runtime.py", "cnn_ddr_v10_runtime.py", "activation_buffers.py",
    "cnn_ddr_v5_runtime.py", "partition_s1.py", "run_cnn_pipeline_v7_fixed.py",
    "cnn_pipeline_v10_bundle.py", "cnn_pipeline_v10_deployment.py",
    "cnn_pipeline_v10_paired_runtime.py", "run_cnn_pipeline_v10_board_window.py",
    "run_cnn_pipeline_v10_full.py", "bounded_pipeline.py", "preprocess_s1.py",
    "cnn_pipeline_v6.py", "cnn_pipeline_v6_runtime.py", "cnn_pipeline_v7_adapter.py",
    "cnn_pipeline_v7_normal_backend.py", "cnn_shared_v7_multicore_linux.py",
    "cnn_shared_v7_probe.py", "benchmark_cnn_pipeline_v10_full.py",
    "benchmark_cnn_pipeline_v10_stream.py", "cnn_pipeline_v10_stream_runtime.py",
    "cnn_pipeline_v10_live_runtime.py", "cnn_pipeline_v10_delivery.py",
    "benchmark_cnn_pipeline_v10_live.py", "cnn_v10_ps_clients.py",
    "cnn_v10_ps_shm_clients.py", "cnn_v10_native_quant.py",
    "cnn_v10_native_quant_ctypes.py", "cnn_pipeline_v10_mixed_runtime.py",
    "cnn_pipeline_v10_wc_deployment.py",
]
SCRIPT_RUNTIME = ["cnn_shared_v7_contract.py", "cnn_shared_v7_multicore_plan.py",
                  "cnn_shared_v7_scheduler.py"]

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_tree(entries, local_root, remote_root):
    for path in sorted(local_root.rglob("*")):
        if path.is_file():
            entries.append((path, remote_root + "/" + path.relative_to(local_root).as_posix()))


def mkdirs(sftp, path):
    current = ""
    for part in path.strip("/").split("/"):
        current += "/" + part
        try:
            sftp.stat(current)
        except IOError:
            sftp.mkdir(current)


def run(client, name, command, report, timeout=180):
    result = helper.run(client, name, command, timeout)
    report["commands"].append(result)
    if result["exit_code"]:
        raise RuntimeError("%s failed: %s %s" %
                           (name, result["stdout"], result["stderr"]))
    return result


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite seven-optimization preupload evidence")
    OUT.mkdir(parents=True)
    entries = []
    for name in RUNTIME:
        entries.append((REPO / "desktop_vlm/board" / name,
                        REMOTE + "/runtime/" + name))
    for name in SCRIPT_RUNTIME:
        entries.append((REPO / "desktop_vlm/scripts/acceleration" / name,
                        REMOTE + "/runtime/" + name))
    add_tree(entries,
             REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix-target-selection-002",
             REMOTE + "/suffix-selection")
    add_tree(entries,
             REPO / "artifacts/board-debug-20261007/acceleration/host/network10-v10.1-wc-driver-experiment-001",
             REMOTE + "/wc-package")
    local = []
    remote_seen = set()
    for path, remote in entries:
        if not path.is_file() or remote in remote_seen:
            raise ValueError("invalid or duplicate staging entry: %s -> %s" % (path, remote))
        remote_seen.add(remote)
        local.append({"local_repo_path": path.relative_to(REPO).as_posix(),
                      "remote_path": remote, "bytes": path.stat().st_size,
                      "sha256": sha(path)})
    deployment = REPO / "artifacts/board-debug-20261007/acceleration/host/network10-v10.1-platform-deployment-001"
    deployment_manifest = json.loads((deployment / "manifest.json").read_text(encoding="utf-8"))
    expected_local = {
        "deployment_manifest": (deployment / "manifest.json", BASE_DEPLOYMENT_SHA),
        "trace18_bit": (deployment / deployment_manifest["files"]["bitstream"]["path"], TRACE18_BIT_SHA),
        "trace18_ltx": (deployment / deployment_manifest["files"]["ltx"]["path"], TRACE18_LTX_SHA),
        "factory_bit": (deployment / deployment_manifest["files"]["factory_bitstream"]["path"], FACTORY_BIT_SHA),
        "factory_driver": (deployment / deployment_manifest["files"]["factory_driver"]["path"], FACTORY_DRIVER_SHA),
    }
    local_assets = {}
    for name, (path, expected) in expected_local.items():
        if not path.is_file() or sha(path) != expected:
            raise ValueError("local recovery/deployment identity mismatch: %s" % name)
        local_assets[name] = {"path": path.relative_to(REPO).as_posix(),
                              "bytes": path.stat().st_size, "sha256": expected}
    report = {
        "schema": "fz3b-v10.1-seven-optimization-preupload-and-factory-unload-v1",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "boot_id": BOOT, "remote_root": REMOTE, "files": local,
        "local_deployment_and_recovery_assets": local_assets,
        "commands": [], "factory_unload_for_trace18": True,
    }
    client = helper.connect()
    try:
        run(client, "fresh-factory-and-no-map-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test \"$(sha256sum /root/workspace/driver/fpgadrv.ko|cut -d' ' -f1)\" = %s; "
            "test ! -e /sys/module/cnn_ddr_v10_candidate; test ! -e /dev/network10_v10; "
            "test ! -e /sys/module/cnn_ddr_v10_wc_candidate; test ! -e /dev/network10_v10_wc_candidate; "
            "test -z \"$(pgrep -f '[b]enchmark_cnn_pipeline_v10_live|[o]rt_partition_runner' || true)\"; "
            "test -e /proc/device-tree/reserved-memory/buffer@0/no-map; "
            "test -e /proc/device-tree/reserved-memory/buffer@1/no-map; "
            "test \"$(od -An -v -tx1 /proc/device-tree/reserved-memory/buffer@0/reg|tr -d ' \\n')\" = 00000000400000000000000040000000; "
            "test \"$(od -An -v -tx1 /proc/device-tree/reserved-memory/buffer@1/reg|tr -d ' \\n')\" = 00000008000000000000000040000000; "
            "grep -Fqx '00000000-3fffffff : System RAM' /proc/iomem; "
            "grep -Fqx '840000000-87fffffff : System RAM' /proc/iomem; "
            "test \"$(findmnt -n -o FSTYPE /dev/shm)\" = tmpfs; "
            "test \"$(df -Pk /dev/shm|awk 'NR==2 {print $4}')\" -gt 8192; "
            "test \"$(sha256sum %s/release/manifest.json|cut -d' ' -f1)\" = %s; "
            "test \"$(sha256sum %s/platform/manifest.json|cut -d' ' -f1)\" = %s; "
            "mkdir -p %s/runtime %s/bin %s/suffix-selection %s/wc-package %s/results; "
            "echo FRESH_FACTORY_NOMAP_RECOVERY_PREFLIGHT_PASS" %
            (BOOT, FACTORY_DRIVER_SHA, BOARD_WINDOW, RELEASE_SHA,
             BOARD_WINDOW, BASE_DEPLOYMENT_SHA, REMOTE, REMOTE, REMOTE, REMOTE, REMOTE), report)
        sftp = client.open_sftp()
        try:
            for record, (path, remote) in zip(local, entries):
                mkdirs(sftp, remote.rsplit("/", 1)[0])
                temporary = remote + ".part"
                sftp.put(str(path), temporary, confirm=True)
                sftp.posix_rename(temporary, remote)
                if sftp.stat(remote).st_size != record["bytes"]:
                    raise RuntimeError("remote upload extent mismatch: %s" % remote)
        finally:
            sftp.close()
        # Reuse the already compiled and target-tested exact binaries, but
        # copy them into this immutable window so their identity is explicit.
        run(client, "copy-frozen-runner-and-native-library",
            "set -eu; cp /root/network10-v10.1-ps-software-ab6-20261007/bin/ort_partition_runner_v3 %s/bin/; "
            "cp /root/network10-v10.1-ps-software-ab6-20261007/bin/libcnn_v10_native_quant.so %s/bin/; "
            "test \"$(sha256sum %s/bin/ort_partition_runner_v3|cut -d' ' -f1)\" = %s; "
            "test \"$(sha256sum %s/bin/libcnn_v10_native_quant.so|cut -d' ' -f1)\" = %s" %
            (REMOTE, REMOTE, REMOTE, RUNNER_V3_SHA, REMOTE, NATIVE_QUANT_SHA), report)
        quoted = " ".join(shlex.quote(item["remote_path"]) for item in local)
        hashes = run(client, "remote-sha256", "sha256sum " + quoted, report, 600)
        actual = {}
        for line in hashes["stdout"].splitlines():
            value, path = line.split(None, 1)
            actual[path.lstrip(" *")] = value
        for item in local:
            if actual.get(item["remote_path"]) != item["sha256"]:
                raise RuntimeError("remote SHA mismatch: %s" % item["remote_path"])
        names = " ".join(shlex.quote(name) for name in RUNTIME + SCRIPT_RUNTIME)
        run(client, "python36-compile-import-and-selection-preflight",
            "set -eu; cd %s/runtime; "
            "test \"$(python3 -c 'import sys;print(\"%%d.%%d\"%%sys.version_info[:2])')\" = 3.6; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -m py_compile %s; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -c \""
            "from cnn_pipeline_v10_mixed_runtime import build_v10_mixed_components; "
            "c,s,k,e=build_v10_mixed_components('%s/release/models','%s/release/models/manifest.json',"
            "'26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed',"
            "'%s/bin/ort_partition_runner_v3',threads=3,"
            "suffix_candidate='%s/suffix-selection/selection-manifest.json',"
            "native_lib='%s/bin/libcnn_v10_native_quant.so'); "
            "[x.close() for x in c.values()]; "
            "assert e['active_quantized_partitions']==['suffix']; "
            "print('MIXED_SELECTION_PASS',e['suffix_candidate']['target_integer_kernel_contract'])\"" %
            (REMOTE, names, BOARD_WINDOW, BOARD_WINDOW, REMOTE, REMOTE, REMOTE), report, 300)
        report["factory_unload_started_utc"] = datetime.datetime.now(
            datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        run(client, "normal-factory-driver-unload",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test -d /sys/module/fpgadrv; test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "/sbin/rmmod fpgadrv; test ! -e /sys/module/fpgadrv; test ! -e /dev/fpgadrv0; "
            "echo FACTORY_DRIVER_NORMAL_UNLOAD_PASS" % BOOT, report)
        run(client, "fresh-ready-for-jtag",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test ! -e /sys/module/fpgadrv; test ! -e /dev/fpgadrv0; "
            "test ! -e /sys/module/cnn_ddr_v10_candidate; test ! -e /dev/network10_v10; "
            "test ! -e /sys/module/cnn_ddr_v10_wc_candidate; test ! -e /dev/network10_v10_wc_candidate; "
            "test -z \"$(pgrep -f '[b]enchmark_cnn_pipeline_v10_live|[o]rt_partition_runner' || true)\"; "
            "test -e /proc/device-tree/reserved-memory/buffer@0/no-map; "
            "test -e /proc/device-tree/reserved-memory/buffer@1/no-map; "
            "cat /sys/class/fpga_manager/fpga0/state; ip -brief address show eth0; "
            "echo SEVEN_OPT_SOFTWARE_STAGED_READY_FOR_JTAG_TRACE18" % BOOT, report)
        report["status"] = "PASS_SOFTWARE_STAGED_FACTORY_UNLOADED_READY_FOR_JTAG"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
