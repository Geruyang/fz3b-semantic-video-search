#!/usr/bin/env python3
"""Run quality-only P3 boundary injection through the real remaining pipeline."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
from pathlib import Path

import run_cnn_v10_wc_live_and_ab as common


OUT = common.REPO / (
    "artifacts/board-debug-20261007/acceleration/network/"
    "network10-v10.2-p3-oracle-fullmodel-quality-001")
P3 = common.REPO / (
    "artifacts/board-debug-20261007/acceleration/host/"
    "cnn-v10-n1-p3-full-w16-002")
P3_SHA = "47cb1bc9c4232fb9dee6a0b46fd29f96859bac253ae7bd6ec1fbdd37c1a5533a"


def _command(label, suffix):
    suffix_arg = ("--suffix-candidate %s/suffix-selection/selection-manifest.json" %
                  common.REMOTE) if suffix else ""
    inner = (
        "cd {r}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B "
        "benchmark_cnn_v10_p3_oracle_quality.py "
        "--p3-oracle-manifest {r}/p3-oracle/manifest.json "
        "--bundle-root {b}/release --expected-bundle-sha256 {rel} "
        "--deployment-manifest {b}/platform/manifest.json "
        "--expected-deployment-sha256 {dep} --runner {r}/bin/ort_partition_runner_v3 "
        "--ps-client mixed --native-lib {r}/bin/libcnn_v10_native_quant.so {suffix} "
        "--threads 3 --max-in-flight 3 --warmup-pairs 3 --measured-pairs 10 "
        "--timeout-s 300 --device /dev/network10_v10 "
        "--input-tensor {b}/inputs/image-00-input.f32 "
        "--input-tensor {b}/inputs/image-01-input.f32 "
        "--expected-feature-sha256 {s0} --expected-feature-sha256 {s1} "
        "--reference-feature {r}/references/image-00-feature.f32 "
        "--reference-feature {r}/references/image-01-feature.f32 "
        "--output-dir {r}/results/{label}"
    ).format(r=common.REMOTE, b=common.BASE, rel=common.RELEASE,
             dep=common.DEPLOY, suffix=suffix_arg, s0=common.EXPECTED[0],
             s1=common.EXPECTED[1], label=label)
    return ("set -eu; env ORT_PARTITION_ALLOW_SPINNING=0 "
            "ORT_PARTITION_PREALLOC_OUTPUTS=0 sh -c %s" % shlex.quote(inner))


def main():
    if OUT.exists():
        raise RuntimeError("refusing overwrite")
    OUT.mkdir(parents=True)
    receipt = {"schema": "fz3b-v10.2-p3-oracle-fullmodel-quality-v1",
               "status": "FAILED", "boot_id": common.BOOT,
               "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
               "p3_manifest_sha256": P3_SHA,
               "hardware_execution": False, "performance_valid": False,
               "commands": [], "runs": {}}
    wrapper = common.REPO / "desktop_vlm/board/benchmark_cnn_v10_p3_oracle_quality.py"
    client = common.helper.connect()
    try:
        common.run(client, "quality-window-preflight",
                   "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; "
                   "grep -qx applied %s/status; test -d /sys/module/cnn_ddr_v10_candidate; "
                   "test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 0; "
                   "test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"" %
                   (common.BOOT, common.BASE_OVERLAY), receipt)
        sftp = client.open_sftp()
        try:
            common.upload(sftp, wrapper, common.REMOTE + "/runtime/" + wrapper.name)
            for path in P3.iterdir():
                if path.is_file():
                    common.upload(sftp, path, common.REMOTE + "/p3-oracle/" + path.name)
        finally:
            sftp.close()
        common.run(client, "p3-oracle-sha-python36",
                   "set -eu; test \"$(sha256sum %s/p3-oracle/manifest.json|cut -d' ' -f1)\" = %s; "
                   "cd %s/runtime; PYTHONDONTWRITEBYTECODE=1 python3 -B -m py_compile %s" %
                   (common.REMOTE, P3_SHA, common.REMOTE, wrapper.name), receipt)
        for index, suffix in enumerate((False, True)):
            if index == 0:
                name = "reload-base-before-p3-only"
            else:
                name = "reload-base-before-p3-suffix"
            common.run(client, name,
                       "set -eu; test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 0; "
                       "test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; "
                       "/sbin/rmmod cnn_ddr_v10_candidate; "
                       "/sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko" % common.BASE,
                       receipt)
            variant = "p3-plus-suffix" if suffix else "p3-only"
            label = "quality-oracle-%s-short10" % variant
            outcome = common.run(client, "run-" + label, _command(label, suffix),
                                 receipt, 1800, allow=True)
            result_path = OUT / (variant + "-result.json")
            sftp = client.open_sftp()
            try:
                sftp.get(common.REMOTE + "/results/" + label + "/result.json",
                         str(result_path))
            finally:
                sftp.close()
            value = json.loads(result_path.read_text(encoding="utf-8"))
            measured = value.get("measured", {})
            features = measured.get("features", [])
            receipt["runs"][variant] = {
                "command_exit_code": outcome["exit_code"],
                "status": value.get("status"),
                "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                "feature_protocol_pass": measured.get("feature_protocol_pass"),
                "min_cosine": min((item.get("cosine", 1.0) for item in features),
                                  default=None),
                "max_relative_l2": max((item.get("relative_l2", 0.0)
                                         for item in features), default=None),
                "reported_fps_invalid_for_p3": measured.get(
                    "fps_including_fill_and_drain"),
                "error": value.get("error"),
            }
        receipt["status"] = "PASS_P3_ORACLE_QUALITY_GATES_RECORDED"
    finally:
        client.close()
        receipt["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": receipt["status"],
                          "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
