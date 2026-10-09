#!/usr/bin/env python3
"""Run short same-window V10 PS candidate gates on the frozen trace18 PL."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-seven-opt-candidate-gates-001"
REMOTE = "/root/network10-v10.1-seven-opt-20261007"
BASE = "/root/network10-v10.1-board-window"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
RELEASE_SHA = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
DEPLOYMENT_SHA = "531cb46623c760df3c09f56cb285e6dff3320da44c1f3570af3e02e98754ea3d"
EXPECTED = ("4121608b7bb27060d5babe05dd6ae723d191b4405a0852d55adde876f4ef16b3",
            "7654afe2d025731f18d23268c2109aba3445b2708a8e9ef1a2e49ed84c369adb")

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(client, name, command, report, timeout=300, allow_failure=False):
    value = helper.run(client, name, command, timeout)
    report["commands"].append(value)
    if value["exit_code"] and not allow_failure:
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


def reload_module(client, name, report):
    run(client, name,
        "set -eu; test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; "
        "if test -e /sys/module/cnn_ddr_v10_candidate; then "
        "/sbin/rmmod cnn_ddr_v10_candidate; fi; test ! -e /dev/network10_v10; "
        "/sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko; "
        "test -c /dev/network10_v10; test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 1" % BASE,
        report)


def command(label, ps_client, runner, candidate_args="", deliver=False):
    inner = (
        "cd {remote}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B "
        "benchmark_cnn_pipeline_v10_live.py --bundle-root {base}/release "
        "--expected-bundle-sha256 {release} --deployment-manifest {base}/platform/manifest.json "
        "--expected-deployment-sha256 {deployment} --runner {runner} "
        "--ps-client {ps_client} --threads 3 --max-in-flight 3 "
        "--warmup-pairs 3 --measured-pairs 10 --timeout-s 300 "
        "--input-tensor {base}/inputs/image-00-input.f32 "
        "--input-tensor {base}/inputs/image-01-input.f32 "
        "--expected-feature-sha256 {sha0} --expected-feature-sha256 {sha1} "
        "{candidates} {refs} {deliver} --output-dir {remote}/results/{label}").format(
            remote=REMOTE, base=BASE, release=RELEASE_SHA,
            deployment=DEPLOYMENT_SHA, runner=runner, ps_client=ps_client,
            sha0=EXPECTED[0], sha1=EXPECTED[1], candidates=candidate_args,
            refs=("--reference-feature %s/references/image-00-feature.f32 "
                  "--reference-feature %s/references/image-01-feature.f32" %
                  (REMOTE, REMOTE)) if candidate_args else "",
            deliver="--deliver-jsonl --delivery-queue-capacity 4" if deliver else "",
            label=label)
    return "set -eu; env ORT_PARTITION_ALLOW_SPINNING=0 ORT_PARTITION_PREALLOC_OUTPUTS=0 sh -c %s" % shlex.quote(inner)


def fetch(sftp, label):
    directory = OUT / label
    directory.mkdir(parents=True)
    records = {}
    for name in ("result.json", "measured-features.f32", "measured-live.jsonl"):
        remote = REMOTE + "/results/" + label + "/" + name
        local = directory / name
        try:
            sftp.get(remote, str(local))
        except IOError:
            continue
        records[name] = {"path": local.relative_to(OUT).as_posix(),
                         "bytes": local.stat().st_size, "sha256": sha(local)}
    return records


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite candidate gate evidence")
    OUT.mkdir(parents=True)
    report = {"schema": "fz3b-v10.1-seven-opt-candidate-gates-v1",
              "status": "FAILED", "boot_id": BOOT,
              "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
              "commands": [], "results": {}}
    updates = [
        (REPO / "desktop_vlm/board/cnn_pipeline_v10_live_runtime.py",
         REMOTE + "/runtime/cnn_pipeline_v10_live_runtime.py"),
        (REPO / "desktop_vlm/board/benchmark_cnn_pipeline_v10_live.py",
         REMOTE + "/runtime/benchmark_cnn_pipeline_v10_live.py"),
    ]
    report["staged_updates"] = [
        {"path": path.relative_to(REPO).as_posix(), "remote": remote,
         "bytes": path.stat().st_size, "sha256": sha(path)}
        for path, remote in updates]
    client = helper.connect()
    try:
        sftp = client.open_sftp()
        try:
            for path, remote in updates:
                mkdirs(sftp, remote.rsplit("/", 1)[0])
                temporary = remote + ".part"
                sftp.put(str(path), temporary, confirm=True)
                sftp.posix_rename(temporary, remote)
        finally:
            sftp.close()
        actual_updates = run(client, "updated-live-benchmark-sha",
            "sha256sum " + " ".join(shlex.quote(item["remote"])
                                      for item in report["staged_updates"]),
            report)["stdout"]
        for item in report["staged_updates"]:
            if item["sha256"] + "  " + item["remote"] not in actual_updates:
                raise RuntimeError("staged update SHA mismatch")
        run(client, "same-window-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "grep -qx applied /sys/kernel/config/device-tree/overlays/network10-v10-trace18/status; "
            "test -d /sys/module/cnn_ddr_v10_candidate; "
            "test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; "
            "test -z \"$(pgrep -f '[b]enchmark_cnn_pipeline_v10_live|[o]rt_partition_runner' || true)\"; "
            "mkdir -p %s/references; python3 -c \"p=open('%s/results/exact-shm-native-live-10/measured-features.f32','rb').read(); assert len(p)==20*2048; open('%s/references/image-00-feature.f32','wb').write(p[:2048]); open('%s/references/image-01-feature.f32','wb').write(p[2048:4096])\"; "
            "test \"$(sha256sum %s/references/image-00-feature.f32|cut -d' ' -f1)\" = %s; "
            "test \"$(sha256sum %s/references/image-01-feature.f32|cut -d' ' -f1)\" = %s" %
            (BOOT, REMOTE, REMOTE, REMOTE, REMOTE, REMOTE, EXPECTED[0], REMOTE, EXPECTED[1]), report)
        groups = [
            ("old-pipe-live-10", "optimized", BASE + "/bin/ort_partition_runner_v2", "", False, False),
            ("exact-shm-native-delivery-10", "mixed", REMOTE + "/bin/ort_partition_runner_v3",
             "--native-lib %s/bin/libcnn_v10_native_quant.so" % REMOTE, True, False),
            ("n1-native-only-10", "mixed", REMOTE + "/bin/ort_partition_runner_v3",
             "--native-lib %s/bin/libcnn_v10_native_quant.so --n1-manifest %s/n1-selection/selection.json" % (REMOTE, REMOTE), False, True),
            ("suffix-w8a8-only-10", "mixed", REMOTE + "/bin/ort_partition_runner_v3",
             "--native-lib %s/bin/libcnn_v10_native_quant.so --suffix-candidate %s/suffix-selection/selection-manifest.json" % (REMOTE, REMOTE), False, True),
            ("n1-plus-suffix-10", "mixed", REMOTE + "/bin/ort_partition_runner_v3",
             "--native-lib %s/bin/libcnn_v10_native_quant.so --n1-manifest %s/n1-selection/selection.json --suffix-candidate %s/suffix-selection/selection-manifest.json" % (REMOTE, REMOTE, REMOTE), False, True),
        ]
        for label, ps_client, runner, candidates, deliver, allow_failure in groups:
            reload_module(client, "reload-before-" + label, report)
            result = run(client, "run-" + label,
                         command(label, ps_client, runner, candidates, deliver),
                         report, 1800, allow_failure=allow_failure)
            if result["exit_code"] and not allow_failure:
                raise RuntimeError("unexpected candidate failure: %s" % label)
        sftp = client.open_sftp()
        try:
            for label, unused_a, unused_b, unused_c, unused_d, unused_e in groups:
                report["results"][label] = fetch(sftp, label)
        finally:
            sftp.close()
        for label, files in report["results"].items():
            if "result.json" not in files:
                raise RuntimeError("missing candidate result: %s" % label)
            value = json.loads((OUT / files["result.json"]["path"]).read_text(encoding="utf-8"))
            report["results"][label]["status"] = value.get("status")
            report["results"][label]["fps"] = value.get("measured", {}).get(
                "fps_including_fill_and_drain")
        expected_pass = {"old-pipe-live-10", "exact-shm-native-delivery-10"}
        if any(report["results"][label]["status"] not in
               ("FEATURE_EXACT_PROTOCOL_CLEAN", "ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN")
               for label in expected_pass):
            raise RuntimeError("a required short candidate gate failed")
        report["status"] = "PASS_SHORT_CANDIDATE_GATES_COMBINATION_RECORDED"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report["status"], "sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
