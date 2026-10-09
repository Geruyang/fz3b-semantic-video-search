#!/usr/bin/env python3
"""Run the fair 30-pair old-pipe versus selected suffix comparison."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-seven-opt-selected-30-003"
REMOTE = "/root/network10-v10.1-seven-opt-20261007"
BASE = "/root/network10-v10.1-board-window"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
RELEASE = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
DEPLOYMENT = "531cb46623c760df3c09f56cb285e6dff3320da44c1f3570af3e02e98754ea3d"
EXPECTED = ("4121608b7bb27060d5babe05dd6ae723d191b4405a0852d55adde876f4ef16b3",
            "7654afe2d025731f18d23268c2109aba3445b2708a8e9ef1a2e49ed84c369adb")

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


def reload_module(client, label, report):
    run(client, "reload-before-" + label,
        "set -eu; test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; "
        "if test -e /sys/module/cnn_ddr_v10_candidate; then /sbin/rmmod cnn_ddr_v10_candidate; fi; "
        "test ! -e /dev/network10_v10; /sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko; "
        "test -c /dev/network10_v10; test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 1" % BASE,
        report)


def benchmark_command(label, ps_client, runner, candidate_args):
    references = ""
    if candidate_args:
        references = ("--reference-feature {r}/references/image-00-feature.f32 "
                      "--reference-feature {r}/references/image-01-feature.f32").format(r=REMOTE)
    inner = (
        "cd {r}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B "
        "benchmark_cnn_pipeline_v10_live.py --bundle-root {b}/release "
        "--expected-bundle-sha256 {rel} --deployment-manifest {b}/platform/manifest.json "
        "--expected-deployment-sha256 {dep} --runner {runner} --ps-client {client} "
        "--threads 3 --max-in-flight 3 --warmup-pairs 3 --measured-pairs 30 --timeout-s 300 "
        "--input-tensor {b}/inputs/image-00-input.f32 --input-tensor {b}/inputs/image-01-input.f32 "
        "--expected-feature-sha256 {s0} --expected-feature-sha256 {s1} "
        "{args} {refs} --output-dir {r}/results/{label}").format(
            r=REMOTE, b=BASE, rel=RELEASE, dep=DEPLOYMENT, runner=runner,
            client=ps_client, s0=EXPECTED[0], s1=EXPECTED[1], args=candidate_args,
            refs=references, label=label)
    return ("set -eu; env ORT_PARTITION_ALLOW_SPINNING=0 "
            "ORT_PARTITION_PREALLOC_OUTPUTS=0 sh -c %s" % shlex.quote(inner))


def fetch(sftp, label):
    output = OUT / label
    output.mkdir(parents=True)
    records = {}
    for name in ("result.json", "measured-features.f32"):
        remote = REMOTE + "/results/" + label + "/" + name
        local = output / name
        sftp.get(remote, str(local))
        records[name] = {"path": local.relative_to(OUT).as_posix(),
                         "bytes": local.stat().st_size,
                         "sha256": sha(local)}
    return records


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite long comparison evidence")
    OUT.mkdir(parents=True)
    report = {"schema": "fz3b-v10.1-seven-opt-selected-30-v1", "status": "FAILED",
              "boot_id": BOOT,
              "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
              "commands": [], "results": {}}
    updates = [REPO / "desktop_vlm/board/cnn_pipeline_v10_live_runtime.py",
               REPO / "desktop_vlm/board/benchmark_cnn_pipeline_v10_live.py"]
    report["staged_updates"] = [{"path": p.relative_to(REPO).as_posix(),
                                  "sha256": sha(p)} for p in updates]
    groups = [
        ("old-pipe-live-30", "optimized", BASE + "/bin/ort_partition_runner_v2", ""),
        ("suffix-w8a8-only-30", "mixed", REMOTE + "/bin/ort_partition_runner_v3",
         "--native-lib {r}/bin/libcnn_v10_native_quant.so --suffix-candidate "
         "{r}/suffix-selection/selection-manifest.json".format(r=REMOTE)),
    ]
    client = helper.connect()
    try:
        sftp = client.open_sftp()
        try:
            for path in updates:
                remote = REMOTE + "/runtime/" + path.name
                sftp.put(str(path), remote + ".part", confirm=True)
                sftp.posix_rename(remote + ".part", remote)
        finally:
            sftp.close()
        run(client, "preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "grep -qx applied /sys/kernel/config/device-tree/overlays/network10-v10-trace18/status; "
            "test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; "
            "test -z \"$(pgrep -x ort_partition_runner_v2 || true)\"; "
            "test -z \"$(pgrep -x ort_partition_runner_v3 || true)\"; "
            "test \"$(sha256sum %s/runtime/%s|cut -d' ' -f1)\" = %s; "
            "test \"$(sha256sum %s/runtime/%s|cut -d' ' -f1)\" = %s" %
            (BOOT, REMOTE, updates[0].name, sha(updates[0]),
             REMOTE, updates[1].name, sha(updates[1])), report)
        for label, ps_client, runner, args in groups:
            reload_module(client, label, report)
            run(client, "run-" + label,
                benchmark_command(label, ps_client, runner, args), report, 3600)
        sftp = client.open_sftp()
        try:
            for label, unused_a, unused_b, unused_c in groups:
                report["results"][label] = fetch(sftp, label)
        finally:
            sftp.close()
        for label, files in report["results"].items():
            result = json.loads((OUT / files["result.json"]["path"]).read_text(encoding="utf-8"))
            report["results"][label]["status"] = result["status"]
            report["results"][label]["fps"] = result["measured"]["fps_including_fill_and_drain"]
            report["results"][label]["execution_ms"] = result["measured"]["execution_ms"]
        if report["results"]["old-pipe-live-30"]["status"] != "FEATURE_EXACT_PROTOCOL_CLEAN":
            raise RuntimeError("old pipe exact gate failed")
        if report["results"]["suffix-w8a8-only-30"]["status"] != "ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN":
            raise RuntimeError("suffix engineering gate failed")
        report["status"] = "PASS_FAIR_30_PAIR_COMPARISON"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report["status"],
                          "sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
