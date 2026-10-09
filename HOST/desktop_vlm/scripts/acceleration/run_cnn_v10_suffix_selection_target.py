#!/usr/bin/env python3
"""Run a frozen suffix candidate on the factory-state FZ3B CPU only.

This stages a candidate, measures FP32 and candidate ORT 1.16.3 execution,
and captures the optimized graph plus a short ORT profile.  It never touches
PL configuration or kernel modules.
"""
from __future__ import print_function

import argparse
import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
WINDOW = "/root/network10-v10.1-board-window"
FIXTURES = "/root/network10-v10.1-ps-opt-20261007/fixtures"
BASE = "/root/network10-v10.1-ps-software-ab6-20261007"
RUNTIME = "/root/board-debug-acceleration-20261004/runtime/onnxruntime-linux-aarch64-1.16.3"
MODEL_MANIFEST_SHA = "26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed"

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path):
    path = Path(path)
    return {"path": str(path.relative_to(REPO)).replace("\\", "/"),
            "bytes": path.stat().st_size, "sha256": digest(path)}


def run(client, name, command, report, timeout=180):
    value = helper.run(client, name, command, timeout)
    report["commands"].append(value)
    if value["exit_code"]:
        raise RuntimeError("%s failed:\n%s\n%s" %
                           (name, value["stdout"], value["stderr"]))
    return value


def candidate_from_receipt(receipt, candidate_sha):
    candidate = receipt.get("candidate", {})
    if candidate.get("sha256") == candidate_sha:
        return candidate
    for value in receipt.get("files", {}).values():
        if isinstance(value, dict) and value.get("sha256") == candidate_sha:
            return value
    raise ValueError("candidate SHA is not bound by host receipt")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--host-receipt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--remote", required=True)
    args = parser.parse_args(argv)
    candidate = Path(args.candidate).resolve()
    host_receipt_path = Path(args.host_receipt).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    output.mkdir(parents=True)
    candidate_sha = digest(candidate)
    source_receipt_raw = host_receipt_path.read_bytes()
    source_receipt = json.loads(source_receipt_raw.decode("utf-8"))
    if "PASS" not in str(source_receipt.get("status", "")):
        raise ValueError("host receipt is not passing")
    candidate_record = candidate_from_receipt(source_receipt, candidate_sha)
    selected = source_receipt.get("selection", {}).get("preserved_selected_nodes")
    if selected is None:
        selected = source_receipt.get("graph_identity", {}).get("selected_node_names")
    if not isinstance(selected, list) or not selected:
        raise ValueError("host receipt does not bind selected node names")
    normalized = {
        "schema": "cnn-v10.1-suffix-host-candidate-normalized-v1",
        "status": "PASS",
        "candidate_label": args.label,
        "source_receipt_sha256": hashlib.sha256(source_receipt_raw).hexdigest(),
        "selection": {"preserved_selected_nodes": selected},
        "files": {"suffix-w8a8-qdq-candidate.onnx": {
            "bytes": candidate.stat().st_size, "sha256": candidate_sha}},
        "quality_gate": (source_receipt.get("quality_gate") or
                         source_receipt.get("host_quality_gate")),
        "p3_domain": "UNTESTED_REAL_CAPTURE_REQUIRED",
    }
    normalized_raw = (json.dumps(normalized, indent=2, sort_keys=True) + "\n").encode("utf-8")
    normalized_path = output / "host-receipt.json"
    normalized_path.write_bytes(normalized_raw)
    scripts = [
        REPO / "desktop_vlm/board/benchmark_cnn_v10_suffix_candidate.py",
        REPO / "desktop_vlm/board/profile_cnn_v10_suffix_candidate.py",
        REPO / "desktop_vlm/board/cnn_v10_ps_shm_clients.py",
        REPO / "desktop_vlm/board/cnn_v10_ps_clients.py",
        REPO / "desktop_vlm/board/ort_partition_profiler_v1.c",
    ]
    staged = scripts + [candidate, normalized_path]
    report = {
        "schema": "fz3b-v10.1-suffix-selection-target-wrapper-v1",
        "status": "RUNNING", "label": args.label, "boot_id": BOOT,
        "device_operations": False, "factory_pl_and_driver_retained": True,
        "candidate_sha256": candidate_sha,
        "host_source_receipt": record(host_receipt_path),
        "uploads": [record(path) for path in staged], "commands": [],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    remote = args.remote.rstrip("/")
    try:
        run(client, "factory-ps-only-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -c /dev/fpgadrv0; test ! -e /dev/network10_v10; "
            "test ! -e /dev/network10_v10_p3; "
            "test -z \"$(pgrep -f '[o]rt_partition_runner|[o]rt_partition_profiler' || true)\"; "
            "test \"$(sha256sum {window}/release/models/manifest.json|cut -d' ' -f1)\" = {manifest}; "
            "mkdir -p {remote}/src {remote}/bin {remote}/results".format(
                boot=BOOT, window=WINDOW, manifest=MODEL_MANIFEST_SHA, remote=remote), report)
        remote_names = {}
        sftp = client.open_sftp()
        try:
            for path in scripts:
                remote_path = remote + "/src/" + path.name
                sftp.put(str(path), remote_path + ".part", confirm=True)
                sftp.posix_rename(remote_path + ".part", remote_path)
                remote_names[path] = remote_path
            for path, name in ((candidate, "suffix-w8a8-qdq-candidate.onnx"),
                               (normalized_path, "host-receipt.json")):
                remote_path = remote + "/src/" + name
                sftp.put(str(path), remote_path + ".part", confirm=True)
                sftp.posix_rename(remote_path + ".part", remote_path)
                remote_names[path] = remote_path
        finally:
            sftp.close()
        checked = run(client, "uploaded-sha256",
                      "sha256sum " + " ".join(shlex.quote(remote_names[path])
                                                for path in staged), report)
        for path in staged:
            if digest(path) not in checked["stdout"]:
                raise RuntimeError("uploaded SHA mismatch: %s" % path)
        run(client, "target-ort116-quality-and-timing",
            "set -eu; cd {remote}/src; env ORT_PARTITION_ALLOW_SPINNING=0 "
            "ORT_PARTITION_PREALLOC_OUTPUTS=0 PYTHONDONTWRITEBYTECODE=1 "
            "PYTHONPATH={remote}/src:{base}/src:{window}/runtime python3 -B "
            "benchmark_cnn_v10_suffix_candidate.py --runner {base}/bin/ort_partition_runner_v3 "
            "--source-model {window}/release/models/suffix.onnx "
            "--candidate-model {remote}/src/suffix-w8a8-qdq-candidate.onnx "
            "--candidate-receipt {remote}/src/host-receipt.json "
            "--fixture-root {fixtures}/image-00 --fixture-root {fixtures}/image-01 "
            "--threads 3 --warmup-rounds 3 --measured-rounds 10 "
            "--output {remote}/results/target-result.json".format(
                remote=remote, base=BASE, window=WINDOW, fixtures=FIXTURES), report, 600)
        compiled = run(client, "compile-profile-runner",
            "set -eu; gcc -std=c11 -O2 -Wall -Wextra -Werror -I{runtime}/include "
            "{remote}/src/ort_partition_profiler_v1.c -L{runtime}/lib "
            "-Wl,-rpath,{runtime}/lib -lonnxruntime -lm "
            "-o {remote}/bin/ort_partition_profiler_v1; "
            "sha256sum {remote}/bin/ort_partition_profiler_v1; file {remote}/bin/ort_partition_profiler_v1".format(
                runtime=RUNTIME, remote=remote), report)
        report["profile_runner_sha256"] = compiled["stdout"].split()[0]
        prefix = remote + "/results/suffix-candidate-ort-profile"
        run(client, "target-ort116-three-run-profile",
            "set -eu; cd {remote}/src; env ORT_PARTITION_ALLOW_SPINNING=0 "
            "ORT_PARTITION_PREALLOC_OUTPUTS=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH={remote}/src "
            "python3 -B profile_cnn_v10_suffix_candidate.py "
            "--candidate {remote}/src/suffix-w8a8-qdq-candidate.onnx "
            "--expected-candidate-sha256 {candidate_sha} "
            "--manifest {window}/release/models/manifest.json "
            "--expected-manifest-sha256 {manifest_sha} "
            "--runner {remote}/bin/ort_partition_profiler_v1 "
            "--input {fixtures}/image-00/suffix-input.f32 --input {fixtures}/image-01/suffix-input.f32 "
            "--expected {fixtures}/image-00/suffix-output.f32 --expected {fixtures}/image-01/suffix-output.f32 "
            "--threads 3 --iterations 3 --profile-prefix {prefix} "
            "--optimized-model {remote}/results/suffix-candidate-optimized.onnx "
            "--output {remote}/results/profile-receipt.json".format(
                remote=remote, candidate_sha=candidate_sha, window=WINDOW,
                manifest_sha=MODEL_MANIFEST_SHA, fixtures=FIXTURES, prefix=prefix), report, 420)
        listed = run(client, "profile-artifact-list",
                     "find %s/results -maxdepth 1 -type f -printf '%%f\\n' | sort" % remote,
                     report)
        names = [value.strip() for value in listed["stdout"].splitlines() if value.strip()]
        profiles = [name for name in names if name.startswith("suffix-candidate-ort-profile")
                    and name.endswith(".json")]
        if len(profiles) != 1:
            raise RuntimeError("expected one profile JSON, got %r" % profiles)
        fetch = ["target-result.json", "profile-receipt.json",
                 "suffix-candidate-optimized.onnx", profiles[0]]
        sftp = client.open_sftp()
        try:
            for name in fetch:
                sftp.get(remote + "/results/" + name, str(output / name))
        finally:
            sftp.close()
        report["artifacts"] = dict((name, {"bytes": (output / name).stat().st_size,
                                                "sha256": digest(output / name)})
                                   for name in fetch)
        run(client, "factory-ps-only-postflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -c /dev/fpgadrv0; test ! -e /dev/network10_v10; "
            "test ! -e /dev/network10_v10_p3; "
            "test -z \"$(pgrep -f '[o]rt_partition_runner|[o]rt_partition_profiler' || true)\"; "
            "echo FACTORY_PS_ONLY_UNCHANGED".format(boot=BOOT), report)
        report["status"] = "PASS_TARGET_ORT116_QUALITY_TIMING_PROFILE_FACTORY_UNCHANGED"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (output / "wrapper-receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
