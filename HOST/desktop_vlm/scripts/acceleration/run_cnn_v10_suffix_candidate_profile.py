#!/usr/bin/env python3
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-suffix-candidate-profile-001"
REMOTE = "/root/network10-v10.1-suffix-candidate-profile-20261007"
WINDOW = "/root/network10-v10.1-board-window"
FIXTURES = "/root/network10-v10.1-ps-opt-20261007/fixtures"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
MODEL_MANIFEST_SHA = "26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed"
CANDIDATE_SHA = "af6394b704a1e56e96b76b821d36342e6ce1f1921835a18ea958d3da6f322bf0"
RUNTIME = "/root/board-debug-acceleration-20261004/runtime/onnxruntime-linux-aarch64-1.16.3"
CANDIDATE = REPO / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix-target-selection-001/suffix-w8a8-qdq-candidate.onnx"

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(client, name, command, report, timeout=180):
    value = helper.run(client, name, command, timeout)
    report["commands"].append(value)
    if value["exit_code"]:
        raise RuntimeError("%s failed: %s %s" %
                           (name, value["stdout"], value["stderr"]))
    return value


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite candidate profile evidence")
    OUT.mkdir(parents=True)
    files = [
        REPO / "desktop_vlm/board/ort_partition_profiler_v1.c",
        REPO / "desktop_vlm/board/profile_cnn_v10_suffix_candidate.py",
        REPO / "desktop_vlm/board/cnn_v10_ps_clients.py",
        CANDIDATE,
    ]
    if digest(CANDIDATE) != CANDIDATE_SHA:
        raise RuntimeError("local suffix candidate SHA mismatch")
    report = {
        "schema": "fz3b-v10.1-suffix-candidate-profile-wrapper-v1",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "boot_id": BOOT, "commands": [], "device_operations": False,
        "factory_pl_and_driver_retained": True,
        "uploads": [{"local": str(path.relative_to(REPO)).replace("\\", "/"),
                     "bytes": path.stat().st_size, "sha256": digest(path)}
                    for path in files],
    }
    client = helper.connect()
    try:
        run(client, "fresh-factory-ps-only-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test -d /sys/module/fpgadrv; test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -c /dev/fpgadrv0; test ! -e /sys/module/cnn_ddr_v10_candidate; "
            "test ! -e /dev/network10_v10; "
            "test -z \"$(pgrep -f '[o]rt_partition_profiler|[p]rofile_cnn_v10_suffix_candidate' || true)\"; "
            "test \"$(sha256sum %s/release/models/manifest.json|cut -d' ' -f1)\" = %s; "
            "mkdir -p %s/src %s/bin %s/results" %
            (BOOT, WINDOW, MODEL_MANIFEST_SHA, REMOTE, REMOTE, REMOTE), report)
        sftp = client.open_sftp()
        try:
            for path in files:
                remote = REMOTE + "/src/" + path.name
                sftp.put(str(path), remote + ".part", confirm=True)
                sftp.posix_rename(remote + ".part", remote)
        finally:
            sftp.close()
        verified = run(client, "source-sha",
            "sha256sum " + " ".join(shlex.quote(REMOTE + "/src/" + path.name)
                                      for path in files), report)
        for path in files:
            if digest(path) not in verified["stdout"]:
                raise RuntimeError("uploaded source SHA mismatch: %s" % path)
        compiled = run(client, "compile-profiler-runner",
            "set -eu; gcc -std=c11 -O2 -Wall -Wextra -Werror "
            "-I{runtime}/include {remote}/src/ort_partition_profiler_v1.c "
            "-L{runtime}/lib -Wl,-rpath,{runtime}/lib -lonnxruntime -lm "
            "-o {remote}/bin/ort_partition_profiler_v1; "
            "sha256sum {remote}/bin/ort_partition_profiler_v1; "
            "file {remote}/bin/ort_partition_profiler_v1".format(
                runtime=RUNTIME, remote=REMOTE), report)
        report["runner_binary_sha256"] = compiled["stdout"].split()[0]
        prefix = REMOTE + "/results/suffix-candidate-ort-profile"
        optimized = REMOTE + "/results/suffix-candidate-optimized.onnx"
        result = REMOTE + "/results/profile-receipt.json"
        command = (
            "set -eu; cd {remote}/src; "
            "env ORT_PARTITION_ALLOW_SPINNING=0 ORT_PARTITION_PREALLOC_OUTPUTS=0 "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH={remote}/src python3 -B "
            "profile_cnn_v10_suffix_candidate.py "
            "--candidate {remote}/src/suffix-w8a8-qdq-candidate.onnx "
            "--expected-candidate-sha256 {candidate_sha} "
            "--manifest {window}/release/models/manifest.json "
            "--expected-manifest-sha256 {manifest_sha} "
            "--runner {remote}/bin/ort_partition_profiler_v1 "
            "--input {fixtures}/image-00/suffix-input.f32 "
            "--input {fixtures}/image-01/suffix-input.f32 "
            "--expected {fixtures}/image-00/suffix-output.f32 "
            "--expected {fixtures}/image-01/suffix-output.f32 "
            "--threads 3 --iterations 3 --profile-prefix {prefix} "
            "--optimized-model {optimized} --output {result}; "
            "sha256sum {result} {optimized}; ls -l {prefix}*.json").format(
                remote=REMOTE, window=WINDOW, candidate_sha=CANDIDATE_SHA,
                manifest_sha=MODEL_MANIFEST_SHA, fixtures=FIXTURES,
                prefix=prefix, optimized=optimized, result=result)
        run(client, "suffix-candidate-profile-three-runs", command, report, timeout=300)
        listed = run(client, "profile-artifact-list",
                     "set -eu; find %s/results -maxdepth 1 -type f -printf '%%f\\n' | sort" % REMOTE,
                     report)
        names = [line.strip() for line in listed["stdout"].splitlines() if line.strip()]
        profiles = [name for name in names
                    if name.startswith("suffix-candidate-ort-profile") and name.endswith(".json")]
        if len(profiles) != 1:
            raise RuntimeError("expected exactly one profile JSON, got %r" % profiles)
        fetch = ["profile-receipt.json", "suffix-candidate-optimized.onnx", profiles[0]]
        sftp = client.open_sftp()
        try:
            for name in fetch:
                sftp.get(REMOTE + "/results/" + name, str(OUT / name))
        finally:
            sftp.close()
        report["artifacts"] = dict((name, {"bytes": (OUT / name).stat().st_size,
                                                 "sha256": digest(OUT / name)})
                                   for name in fetch)
        run(client, "post-profile-factory-state",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
            "test -d /sys/module/fpgadrv; test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test ! -e /sys/module/cnn_ddr_v10_candidate; test ! -e /dev/network10_v10; "
            "test -z \"$(pgrep -f '[o]rt_partition_profiler|[p]rofile_cnn_v10_suffix_candidate' || true)\"; "
            "echo SUFFIX_CANDIDATE_PROFILE_FACTORY_STATE_UNCHANGED" % BOOT, report)
        report["status"] = "PASS_SUFFIX_CANDIDATE_PROFILE_FACTORY_STATE_UNCHANGED"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "wrapper-receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
