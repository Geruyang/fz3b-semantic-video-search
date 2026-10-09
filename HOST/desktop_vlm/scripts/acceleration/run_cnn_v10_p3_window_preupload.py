#!/usr/bin/env python3
"""Stage the ABI10.2 software window while keeping factory PL/driver active."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-p3-window-preupload-002"
REMOTE = "/root/network10-v10.2-p3-window-preupload-002"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
FACTORY_DRIVER_SHA = "a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f"
RUNNER_SHA = "0a8a94e2d553508baa958a741ea8d0e5c9f68d1f2a589d75d64860c825fc4f96"
COMBINED_SHA = "c62b9f49b1118916168a2ca7a4a63c56d51bba66a0921523af35d46495bbab99"
KO_SHA = "b166879d3773f915d361c2579aeac15bd7126ed99243879f5eb063f2c758c5ca"

RUNTIME = [
    "cnn_ddr_v6_runtime.py", "cnn_ddr_v10_runtime.py", "activation_buffers.py",
    "cnn_ddr_v5_runtime.py", "partition_s1.py", "run_cnn_pipeline_v7_fixed.py",
    "cnn_pipeline_v10_bundle.py", "cnn_pipeline_v10_deployment.py",
    "cnn_pipeline_v10_chain_deployment.py", "cnn_ddr_v10_p3_runtime.py",
    "cnn_pipeline_v10_p3_chain_parameters.py", "cnn_pipeline_v10_p3_runtime.py",
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
    "cnn_pipeline_v10_suffix_capture.py", "evaluate_cnn_v10_p3_suffix_domain.py",
]
SCRIPT_RUNTIME = ["cnn_shared_v7_contract.py", "cnn_shared_v7_multicore_plan.py",
                  "cnn_shared_v7_scheduler.py"]

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_tree(entries, local_root, remote_root):
    for path in sorted(local_root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
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
        raise RuntimeError("%s failed: %s\n%s" %
                           (name, result["stdout"], result["stderr"]))
    return result


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite P3 preupload evidence")
    OUT.mkdir(parents=True)
    entries = []
    for name in RUNTIME:
        entries.append((REPO / "desktop_vlm/board" / name,
                        REMOTE + "/runtime/" + name))
    for name in SCRIPT_RUNTIME:
        entries.append((REPO / "desktop_vlm/scripts/acceleration" / name,
                        REMOTE + "/runtime/" + name))
    add_tree(entries, REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-p3-chain-parameters-002",
             REMOTE + "/chain-parameters")
    add_tree(entries, REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix11-target-selection-001",
             REMOTE + "/suffix11-selection")
    add_tree(entries, REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix6-target-selection-001",
             REMOTE + "/suffix6-selection")
    compile_dir = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-p3-driver-compile-003"
    for name in ("cnn_ddr_v10_p3_candidate.ko", "Module.symvers", "receipt.json"):
        entries.append((compile_dir / name, REMOTE + "/driver/" + name))
    seen = set()
    files = []
    for path, remote in entries:
        if not path.is_file() or remote in seen:
            raise ValueError("invalid or duplicate staging entry: %s -> %s" % (path, remote))
        seen.add(remote)
        files.append({"local_repo_path": path.relative_to(REPO).as_posix(),
                      "remote_path": remote, "bytes": path.stat().st_size,
                      "sha256": sha(path)})
    if (sha(compile_dir / "cnn_ddr_v10_p3_candidate.ko") != KO_SHA or
            sha(REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-p3-chain-parameters-002/manifest.json") != COMBINED_SHA):
        raise ValueError("P3 KO or combined parameter identity mismatch")
    report = {
        "schema": "fz3b-v10.2-p3-software-window-preupload-v1",
        "status": "RUNNING", "boot_id": BOOT, "remote_root": REMOTE,
        "mode": "preupload_compile_import_only_no_module_or_pl_state_change",
        "files": files, "commands": [],
        "ready_for_programming": False,
        "missing_final_hardware_gates": [
            "all RTL normal/P3/stress receipts", "full-platform route receipt",
            "final address-map receipt", "final timing/clock receipt",
            "final guard validation receipt", "A0002 bitstream/LTX/DTBO",
            "root independent deployment audit"],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    try:
        run(client, "factory-preupload-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test \"$(sha256sum /root/workspace/driver/fpgadrv.ko|cut -d' ' -f1)\" = {factory}; "
            "test ! -e /sys/module/cnn_ddr_v10_p3_candidate; test ! -e /dev/network10_v10_p3; "
            "test ! -e {remote}; mkdir -p {remote}".format(
                boot=BOOT, factory=FACTORY_DRIVER_SHA, remote=REMOTE), report)
        sftp = client.open_sftp()
        try:
            for index, ((path, remote), identity) in enumerate(zip(entries, files)):
                # Keep remote path parsing POSIX-only.  pathlib.Path follows the
                # Windows host here and can turn a remote absolute path into a
                # host-flavoured parent.
                mkdirs(sftp, remote.rsplit("/", 1)[0])
                temporary = remote + ".part"
                sftp.put(str(path), temporary, confirm=True)
                sftp.posix_rename(temporary, remote)
                if index and index % 20 == 0:
                    print(json.dumps({"uploaded": index, "total": len(entries)}, sort_keys=True))
        finally:
            sftp.close()
        expected_lines = []
        for item in files:
            expected_lines.append("%s  %s" % (item["sha256"], item["remote_path"]))
        expected_path = OUT / "expected-sha256.txt"
        # sha256sum reads the file on Linux; force LF rather than the Windows
        # text-mode newline so the final path character is never a stray CR.
        expected_path.write_bytes(("\n".join(expected_lines) + "\n").encode("ascii"))
        sftp = client.open_sftp()
        try:
            sftp.put(str(expected_path), REMOTE + "/expected-sha256.txt.part", confirm=True)
            sftp.posix_rename(REMOTE + "/expected-sha256.txt.part", REMOTE + "/expected-sha256.txt")
        finally:
            sftp.close()
        run(client, "uploaded-sha256",
            "set -eu; cd /; sha256sum -c %s/expected-sha256.txt" % REMOTE,
            report, 600)
        run(client, "python36-syntax-import-and-assets",
            "set -eu; cd {remote}/runtime; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -c \"import glob; [compile(open(p,'rb').read(),p,'exec') for p in glob.glob('*.py')]; print('P3_RUNTIME_PY36_SYNTAX_PASS')\"; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -c \"import benchmark_cnn_pipeline_v10_live as b; import cnn_pipeline_v10_suffix_capture as c; import evaluate_cnn_v10_p3_suffix_domain as e; import cnn_pipeline_v10_p3_runtime as p; import cnn_ddr_v10_p3_runtime as d; assert d.CORE_ABI==0x000A0002; print('P3_RUNTIME_IMPORT_PASS')\"; "
            "test ! -e __pycache__; "
            "test \"$(sha256sum /root/network10-v10.1-ps-software-ab6-20261007/bin/ort_partition_runner_v3|cut -d' ' -f1)\" = {runner}; "
            "test \"$(sha256sum {remote}/driver/cnn_ddr_v10_p3_candidate.ko|cut -d' ' -f1)\" = {ko}; "
            "test \"$(sha256sum {remote}/chain-parameters/manifest.json|cut -d' ' -f1)\" = {combined}; "
            "echo P3_PREUPLOAD_ASSETS_PASS".format(
                remote=REMOTE, runner=RUNNER_SHA, ko=KO_SHA, combined=COMBINED_SHA), report)
        run(client, "factory-preupload-postflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test ! -e /sys/module/cnn_ddr_v10_p3_candidate; test ! -e /dev/network10_v10_p3; "
            "echo FACTORY_UNCHANGED_P3_PREUPLOAD_ONLY".format(boot=BOOT), report)
        report["status"] = "PASS_P3_SOFTWARE_PREUPLOAD_FACTORY_UNCHANGED_NOT_READY_FOR_PROGRAMMING"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
