#!/usr/bin/env python3
"""Stage the final PS candidates, load trace18 software, and run exact baseline."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-seven-opt-software-window-003"
REMOTE = "/root/network10-v10.1-seven-opt-20261007"
BASE = "/root/network10-v10.1-board-window"
OVERLAY = "/sys/kernel/config/device-tree/overlays/network10-v10-trace18"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
PROGRAM_RECEIPT = REPO / "artifacts/board-debug-20261007/acceleration/jtag/cnn-v10-trace18-seven-opt-program-001/receipt.json"
PROGRAM_SHA = "7ec67150dbde21fba30a213b56bc42fc8c63f2440850d525be3a57a459aac02e"
RELEASE_SHA = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
DEPLOYMENT_SHA = "531cb46623c760df3c09f56cb285e6dff3320da44c1f3570af3e02e98754ea3d"
KO_SHA = "88824b57251a224368df1dc48b8f087b3ec85babe85e5b97032bbd95df8e4c93"
DTBO_SHA = "4ea1f668cad6b916a260cf433c1a8f97c5825aeea21bcaba0f60dbf7e574ea07"

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(client, name, command, report, timeout=300):
    value = helper.run(client, name, command, timeout)
    report["commands"].append(value)
    if value["exit_code"]:
        raise RuntimeError("%s failed: %s %s" %
                           (name, value["stdout"], value["stderr"]))
    return value


def mkdirs(sftp, path):
    current = ""
    for part in path.strip("/").split("/"):
        current += "/" + part
        try:
            sftp.stat(current)
        except IOError:
            sftp.mkdir(current)


def benchmark_command(label):
    inner = (
        "cd {remote}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B "
        "benchmark_cnn_pipeline_v10_live.py "
        "--bundle-root {base}/release --expected-bundle-sha256 {release} "
        "--deployment-manifest {base}/platform/manifest.json "
        "--expected-deployment-sha256 {deployment} "
        "--runner {remote}/bin/ort_partition_runner_v3 --ps-client mixed "
        "--native-lib {remote}/bin/libcnn_v10_native_quant.so "
        "--threads 3 --max-in-flight 3 --warmup-pairs 3 --measured-pairs 10 "
        "--timeout-s 300 --input-tensor {base}/inputs/image-00-input.f32 "
        "--input-tensor {base}/inputs/image-01-input.f32 "
        "--expected-feature-sha256 4121608b7bb27060d5babe05dd6ae723d191b4405a0852d55adde876f4ef16b3 "
        "--expected-feature-sha256 7654afe2d025731f18d23268c2109aba3445b2708a8e9ef1a2e49ed84c369adb "
        "--output-dir {remote}/results/{label}").format(
            remote=REMOTE, base=BASE, release=RELEASE_SHA,
            deployment=DEPLOYMENT_SHA, label=label)
    return "set -eu; env ORT_PARTITION_ALLOW_SPINNING=0 ORT_PARTITION_PREALLOC_OUTPUTS=0 sh -c %s" % shlex.quote(inner)


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite software-window evidence")
    if sha(PROGRAM_RECEIPT) != PROGRAM_SHA:
        raise RuntimeError("JTAG program receipt identity mismatch")
    OUT.mkdir(parents=True)
    selection = REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-n1-native-selection-001"
    entries = [
        (REPO / "desktop_vlm/board/cnn_pipeline_v10_mixed_runtime.py",
         REMOTE + "/runtime/cnn_pipeline_v10_mixed_runtime.py"),
        (REPO / "desktop_vlm/board/cnn_v10_n1_native_ctypes.py",
         REMOTE + "/runtime/cnn_v10_n1_native_ctypes.py"),
        (REPO / "desktop_vlm/board/cnn_pipeline_v10_live_runtime.py",
         REMOTE + "/runtime/cnn_pipeline_v10_live_runtime.py"),
        (REPO / "desktop_vlm/board/cnn_pipeline_v10_delivery.py",
         REMOTE + "/runtime/cnn_pipeline_v10_delivery.py"),
        (REPO / "desktop_vlm/board/benchmark_cnn_pipeline_v10_live.py",
         REMOTE + "/runtime/benchmark_cnn_pipeline_v10_live.py"),
    ]
    for path in sorted(selection.iterdir()):
        if path.is_file():
            entries.append((path, REMOTE + "/n1-selection/" + path.name))
    files = [{"path": path.relative_to(REPO).as_posix(), "remote": remote,
              "bytes": path.stat().st_size, "sha256": sha(path)}
             for path, remote in entries]
    report = {"schema": "fz3b-v10.1-seven-opt-software-window-v1",
              "status": "FAILED", "boot_id": BOOT,
              "program_receipt_sha256": PROGRAM_SHA,
              "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
              "files": files, "commands": []}
    client = helper.connect()
    try:
        run(client, "post-program-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test \"$(cat /sys/class/fpga_manager/fpga0/state)\" = operating; "
            "test ! -e /sys/module/fpgadrv; test ! -e /dev/fpgadrv0; "
            "test ! -e /sys/module/cnn_ddr_v10_candidate; test ! -e /dev/network10_v10; "
            "test ! -e %s; test -z \"$(pgrep -f '[b]enchmark_cnn_pipeline_v10_live|[o]rt_partition_runner' || true)\"; "
            "test \"$(sha256sum %s/driver/cnn_ddr_v10_candidate.ko|cut -d' ' -f1)\" = %s; "
            "test \"$(sha256sum %s/platform/platform/network10_v10_trace18.dtbo|cut -d' ' -f1)\" = %s" %
            (BOOT, OVERLAY, BASE, KO_SHA, BASE, DTBO_SHA), report)
        sftp = client.open_sftp()
        try:
            for record, (path, remote) in zip(files, entries):
                mkdirs(sftp, remote.rsplit("/", 1)[0])
                temporary = remote + ".part"
                sftp.put(str(path), temporary, confirm=True)
                sftp.posix_rename(temporary, remote)
                if sftp.stat(remote).st_size != record["bytes"]:
                    raise RuntimeError("remote extent mismatch: %s" % remote)
        finally:
            sftp.close()
        quoted = " ".join(shlex.quote(item["remote"]) for item in files)
        actual = run(client, "updated-files-sha", "sha256sum " + quoted,
                     report, 300)["stdout"]
        for item in files:
            expected_line = item["sha256"] + "  " + item["remote"]
            if expected_line not in actual:
                raise RuntimeError("remote SHA mismatch: %s" % item["remote"])
        run(client, "python36-and-n1-selection",
            "set -eu; cd %s/runtime; test \"$(python3 -c 'import sys;print(\"%%d.%%d\"%%sys.version_info[:2])')\" = 3.6; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -m py_compile cnn_pipeline_v10_mixed_runtime.py cnn_v10_n1_native_ctypes.py cnn_pipeline_v10_live_runtime.py cnn_pipeline_v10_delivery.py benchmark_cnn_pipeline_v10_live.py; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -c \"from cnn_pipeline_v10_mixed_runtime import build_v10_mixed_components; c,s,k,e=build_v10_mixed_components('%s/release/models','%s/release/models/manifest.json','26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed','%s/bin/ort_partition_runner_v3',threads=3,n1_manifest='%s/n1-selection/selection.json',native_lib='%s/bin/libcnn_v10_native_quant.so'); assert e['active_quantized_partitions']==['n1']; [getattr(x,'close')() for x in c.values() if callable(getattr(x,'close',None))]; print('N1_SELECTION_PASS')\"" %
            (REMOTE, BASE, BASE, REMOTE, REMOTE, REMOTE), report, 300)
        run(client, "apply-base-overlay",
            "set -eu; mkdir %s; cat %s/platform/platform/network10_v10_trace18.dtbo > %s/dtbo; "
            "grep -qx applied %s/status; test \"$(tr '\\000' '\\n' < /proc/device-tree/amba_pl@0/fz3b-cnn-ddr-v10@a4000000/compatible)\" = fz3b,cnn-ddr-v10" %
            (OVERLAY, BASE, OVERLAY, OVERLAY), report)
        run(client, "load-base-module",
            "set -eu; /sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko; "
            "test -c /dev/network10_v10; test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 1" % BASE,
            report)
        run(client, "exact-shm-native-live-10pair",
            benchmark_command("exact-shm-native-live-10"), report, 1800)
        sftp = client.open_sftp()
        try:
            local = OUT / "exact-shm-native-live-10-result.json"
            sftp.get(REMOTE + "/results/exact-shm-native-live-10/result.json", str(local))
        finally:
            sftp.close()
        result = json.loads(local.read_text(encoding="utf-8"))
        if result.get("status") != "FEATURE_EXACT_PROTOCOL_CLEAN":
            raise RuntimeError("exact baseline result did not pass")
        report["exact_result"] = {"path": local.relative_to(OUT).as_posix(),
                                  "sha256": sha(local),
                                  "fps": result["measured"]["fps_including_fill_and_drain"]}
        report["status"] = "PASS_EXACT_BASELINE_V10_QUIESCED"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report["status"], "sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
