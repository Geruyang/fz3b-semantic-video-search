#!/usr/bin/env python3
"""Run the target-ORT portions of the P3-domain host prediction.

The board remains on factory PL/driver.  This helper only uploads small tensor
fixtures and invokes PS ONNX Runtime partitions; it never opens a PL device.
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
EVIDENCE = REPO / ("artifacts/board-debug-20261007/acceleration/host/"
                   "cnn-v10-p3-domain-host-prediction-001")
REMOTE = "/root/network10-v10.2-p3-domain-host-prediction-001"
PREUPLOAD = "/root/network10-v10.2-p3-window-preupload-001"
MODEL_ROOT = "/root/network10-v10.1-board-window/release/models"
RUNNER = "/root/network10-v10.1-ps-software-ab6-20261007/bin/ort_partition_runner_v3"
REFERENCES = "/root/network10-v10.1-seven-opt-20261007/references"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
MODEL_MANIFEST_SHA = "26d2f61e40566381bf44eb0821170e04cbc4c00e361064dba87958808afbb8ed"
RUNNER_SHA = "0a8a94e2d553508baa958a741ea8d0e5c9f68d1f2a589d75d64860c825fc4f96"

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path):
    path = Path(path)
    return {"path": path.relative_to(REPO).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def mkdirs(sftp, remote):
    current = ""
    for part in remote.strip("/").split("/"):
        current += "/" + part
        try:
            sftp.stat(current)
        except IOError:
            sftp.mkdir(current)


def upload(sftp, local, remote):
    mkdirs(sftp, remote.rsplit("/", 1)[0])
    sftp.put(str(local), remote + ".part", confirm=True)
    sftp.posix_rename(remote + ".part", remote)


def run(client, name, command, receipt, timeout=300):
    result = helper.run(client, name, command, timeout)
    receipt["commands"].append(result)
    if result["exit_code"]:
        raise RuntimeError("%s failed: %s\n%s" %
                           (name, result["stdout"], result["stderr"]))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("n3", "suffix-base", "suffix"), required=True)
    args = parser.parse_args(argv)
    output = EVIDENCE / ("target-" + args.phase + "-receipt.json")
    if output.exists():
        raise RuntimeError("refusing to overwrite %s" % output)
    worker = REPO / "desktop_vlm/board/run_cnn_v10_partition_once.py"
    receipt = {
        "schema": "fz3b-v10.2-p3-domain-target-stage-v1",
        "status": "RUNNING", "phase": args.phase, "boot_id": BOOT,
        "hardware_execution": False, "performance_valid": False,
        "factory_pl_and_driver_retained": True,
        "worker": record(worker), "commands": [], "artifacts": {},
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    try:
        run(client, "factory-ps-only-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test ! -e /dev/network10_v10; test ! -e /dev/network10_v10_p3; "
            "test \"$(sha256sum {runner}|cut -d' ' -f1)\" = {runner_sha}; "
            "test \"$(sha256sum {models}/manifest.json|cut -d' ' -f1)\" = {manifest}; "
            "mkdir -p {remote}/src {remote}/inputs {remote}/outputs".format(
                boot=BOOT, runner=RUNNER, runner_sha=RUNNER_SHA,
                models=MODEL_ROOT, manifest=MODEL_MANIFEST_SHA, remote=REMOTE),
            receipt)
        sftp = client.open_sftp()
        try:
            upload(sftp, worker, REMOTE + "/src/" + worker.name)
            inputs = []
            if args.phase == "n3":
                inputs = [EVIDENCE / "outputs" / ("image-%02d-n3-input.f32" % i)
                          for i in range(2)]
            else:
                inputs = [EVIDENCE / "outputs" / ("image-%02d-suffix-input.f32" % i)
                          for i in range(2)]
            for path in inputs:
                upload(sftp, path, REMOTE + "/inputs/" + path.name)
            if args.phase != "n3":
                for index in range(2):
                    remote_ref = REFERENCES + "/image-%02d-feature.f32" % index
                    local_ref = EVIDENCE / "outputs" / ("image-%02d-reference-feature.f32" % index)
                    sftp.get(remote_ref, str(local_ref))
        finally:
            sftp.close()
        checked = run(client, "uploaded-sha256",
            "sha256sum {worker} {inputs}".format(
                worker=shlex.quote(REMOTE + "/src/" + worker.name),
                inputs=" ".join(shlex.quote(REMOTE + "/inputs/" + path.name)
                                for path in inputs)), receipt)
        if sha(worker) not in checked["stdout"]:
            raise RuntimeError("worker upload SHA mismatch")
        for path in inputs:
            if sha(path) not in checked["stdout"]:
                raise RuntimeError("input upload SHA mismatch")

        variants = [("n3", "network3-bridge", None, None)] if args.phase == "n3" else (
            [("suffix-fp32", "suffix", None, None)] if args.phase == "suffix-base" else [
            ("suffix11", "suffix",
             PREUPLOAD + "/suffix11-selection/suffix-w8a8-qdq-candidate.onnx",
             "a63c35ea73338adc74ca2898363ad3c07f2e1abcc157d80eab9b29ebf26139ac"),
            ("suffix6", "suffix",
             PREUPLOAD + "/suffix6-selection/suffix-w8a8-qdq-candidate.onnx",
             "dbfee69facc6d7a0021d54899bfa8e4c906fa58d3077df2bf15da65dd4f47303"),
        ])
        for label, partition, override, override_sha in variants:
            input_args = []
            output_paths = []
            for path in inputs:
                remote_input = REMOTE + "/inputs/" + path.name
                remote_output = REMOTE + "/outputs/%s-%s" % (label, path.name)
                input_args.extend(["--input", remote_input, "--output", remote_output])
                output_paths.append(remote_output)
            command = ["python3", "-B", REMOTE + "/src/" + worker.name,
                       "--model-root", MODEL_ROOT,
                       "--manifest", MODEL_ROOT + "/manifest.json",
                       "--expected-manifest-sha256", MODEL_MANIFEST_SHA,
                       "--partition", partition, "--runner", RUNNER,
                       "--threads", "3"]
            if override is not None:
                command += ["--model-override", override,
                            "--expected-model-sha256", override_sha]
            report_remote = REMOTE + "/outputs/%s-report.json" % label
            command += input_args + ["--report", report_remote]
            shell = ("set -eu; cd {runtime}; env ORT_PARTITION_ALLOW_SPINNING=0 "
                     "ORT_PARTITION_PREALLOC_OUTPUTS=0 PYTHONDONTWRITEBYTECODE=1 "
                     "PYTHONPATH={runtime} {command}").format(
                         runtime=PREUPLOAD + "/runtime",
                         command=" ".join(shlex.quote(value) for value in command))
            run(client, "run-" + label, shell, receipt, 600)
            sftp = client.open_sftp()
            try:
                local_report = EVIDENCE / "outputs" / (label + "-target-report.json")
                sftp.get(report_remote, str(local_report))
                receipt["artifacts"][label + "-report"] = record(local_report)
                for index, remote_output in enumerate(output_paths):
                    local_output = EVIDENCE / "outputs" / (
                        "image-%02d-%s-output.f32" % (index, label))
                    sftp.get(remote_output, str(local_output))
                    receipt["artifacts"]["%s-image-%02d" % (label, index)] = record(local_output)
            finally:
                sftp.close()
        run(client, "factory-ps-only-postflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test ! -e /dev/network10_v10; test ! -e /dev/network10_v10_p3; "
            "test -z \"$(pgrep -f '[o]rt_partition_runner' || true)\"; "
            "echo FACTORY_PS_ONLY_UNCHANGED".format(boot=BOOT), receipt)
        receipt["status"] = "PASS_TARGET_ORT_PS_ONLY_FACTORY_UNCHANGED"
    finally:
        client.close()
        receipt["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
        output.write_bytes(raw)
        print(json.dumps({"status": receipt.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()},
                         sort_keys=True))


if __name__ == "__main__":
    main()
