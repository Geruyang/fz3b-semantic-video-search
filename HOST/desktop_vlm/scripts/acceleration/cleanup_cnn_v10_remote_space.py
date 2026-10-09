#!/usr/bin/env python3
"""Reclaim only verified, task-owned obsolete V10 staging on the FZ3B."""
from __future__ import print_function

import datetime
import hashlib
import json
import shlex
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-remote-space-cleanup-001"
BOOT = "fd395d2a-974c-4a1a-827d-568452cd8488"
FACTORY_SHA = "a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f"

DELETE_PATHS = [
    "/root/network10-v10.1-suffix11-selection-20261007",
    "/root/network10-v10.1-suffix6-selection-20261007",
    "/root/network10-v10.1-suffix-candidate-profile-20261007",
    "/root/network10-v10.1-suffix-candidate2-20261007",
    "/root/network10-v10.1-mixed-builder-suffix-20261007",
    "/root/network10-v10.1-ps-mixed2-20261007",
    "/root/network10-v10.2-p3-compile-001",
    "/root/network10-v10.2-p3-compile-002",
    "/root/network10-v10.1-driver-wc-compile-001",
    "/root/network10-v10.1-driver-wc-compile-002",
    "/root/network10-v10.1-n1-native-test-20261007",
    "/root/network10-v10.1-n1-native5-20261007",
    "/root/network10-v10.1-n1-native6-20261007",
]

PROTECTED = {
    "/root/network10-v10.2-p3-window-preupload-001/expected-sha256.txt":
        "99c4253afa3c271dd553d1ce2cd2dbf24426eba7e50fc9335699a899c168ff5a",
    "/root/network10-v10.2-p3-window-preupload-001/driver/cnn_ddr_v10_p3_candidate.ko":
        "b166879d3773f915d361c2579aeac15bd7126ed99243879f5eb063f2c758c5ca",
    "/root/network10-v10.2-p3-window-preupload-001/chain-parameters/manifest.json":
        "c62b9f49b1118916168a2ca7a4a63c56d51bba66a0921523af35d46495bbab99",
    "/root/network10-v10.2-p3-compile-003/driver/cnn_ddr_v10_p3_candidate.ko":
        "b166879d3773f915d361c2579aeac15bd7126ed99243879f5eb063f2c758c5ca",
    "/root/workspace/driver/fpgadrv.ko": FACTORY_SHA,
}

# Each non-reproducible remote result/model is checked against its exact host
# copy before any containing directory is removed.  Source and compiler
# intermediates omitted here remain reproducible from workspace sources and
# their already archived compile receipts.
BACKUPS = [
    ("/root/network10-v10.1-suffix11-selection-20261007/results/profile-receipt.json",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix11-target-selection-001/profile-receipt.json"),
    ("/root/network10-v10.1-suffix11-selection-20261007/results/suffix-candidate-optimized.onnx",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix11-target-selection-001/suffix-candidate-optimized.onnx"),
    ("/root/network10-v10.1-suffix11-selection-20261007/results/target-result.json",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix11-target-selection-001/target-result.json"),
    ("/root/network10-v10.1-suffix11-selection-20261007/src/suffix-w8a8-qdq-candidate.onnx",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix11-target-selection-001/suffix-w8a8-qdq-candidate.onnx"),
    ("/root/network10-v10.1-suffix6-selection-20261007/results/profile-receipt.json",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix6-target-selection-001/profile-receipt.json"),
    ("/root/network10-v10.1-suffix6-selection-20261007/results/suffix-candidate-optimized.onnx",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix6-target-selection-001/suffix-candidate-optimized.onnx"),
    ("/root/network10-v10.1-suffix6-selection-20261007/results/target-result.json",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix6-target-selection-001/target-result.json"),
    ("/root/network10-v10.1-suffix6-selection-20261007/src/suffix-w8a8-qdq-candidate.onnx",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix6-target-selection-001/suffix-w8a8-qdq-candidate.onnx"),
    ("/root/network10-v10.1-suffix-candidate-profile-20261007/results/profile-receipt.json",
     "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-suffix-candidate-profile-001/profile-receipt.json"),
    ("/root/network10-v10.1-suffix-candidate-profile-20261007/results/suffix-candidate-optimized.onnx",
     "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-suffix-candidate-profile-001/suffix-candidate-optimized.onnx"),
    ("/root/network10-v10.1-suffix-candidate-profile-20261007/results/suffix-candidate-ort-profile_2021-08-31_22-36-49.json",
     "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-suffix-candidate-profile-001/suffix-candidate-ort-profile_2021-08-31_22-36-49.json"),
    ("/root/network10-v10.1-suffix-candidate-profile-20261007/src/suffix-w8a8-qdq-candidate.onnx",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix-target-selection-002/suffix-w8a8-qdq-candidate.onnx"),
    ("/root/network10-v10.1-suffix-candidate2-20261007/results/result.json",
     "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-suffix-candidate-target-002/result.json"),
    ("/root/network10-v10.1-suffix-candidate2-20261007/src/candidate.onnx",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix-target-selection-002/suffix-w8a8-qdq-candidate.onnx"),
    ("/root/network10-v10.1-mixed-builder-suffix-20261007/selection/suffix-w8a8-qdq-candidate.onnx",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix-target-selection-002/suffix-w8a8-qdq-candidate.onnx"),
    ("/root/network10-v10.1-mixed-builder-suffix-20261007/selection/target-result.json",
     "artifacts/board-debug-20261007/acceleration/host/cnn-v10-suffix-target-selection-002/v1-target-result.json"),
    ("/root/network10-v10.1-ps-mixed2-20261007/results/profile-receipt.json",
     "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-suffix-profile-002/profile-receipt.json"),
    ("/root/network10-v10.1-ps-mixed2-20261007/results/suffix-optimized.onnx",
     "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-suffix-profile-002/suffix-optimized.onnx"),
    ("/root/network10-v10.1-ps-mixed2-20261007/results/suffix-ort-profile_2021-08-31_21-53-50.json",
     "artifacts/board-debug-20261007/acceleration/network/network10-v10.1-suffix-profile-002/suffix-ort-profile_2021-08-31_21-53-50.json"),
]

RECOVER = [
    ("/root/network10-v10.1-suffix11-selection-20261007/results/suffix-candidate-ort-profile_2021-09-01_00-10-51.json",
     "recovered-evidence/suffix11-target-ort-profile.json"),
    ("/root/network10-v10.1-suffix6-selection-20261007/results/suffix-candidate-ort-profile_2021-09-01_00-11-40.json",
     "recovered-evidence/suffix6-target-ort-profile.json"),
]

sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(client, name, command, report, timeout=180):
    result = helper.run(client, name, command, timeout)
    report["commands"].append(result)
    if result["exit_code"]:
        raise RuntimeError("%s failed: %s\n%s" %
                           (name, result["stdout"], result["stderr"]))
    return result


def main():
    if OUT.exists():
        raise RuntimeError("refusing to overwrite remote cleanup evidence")
    OUT.mkdir(parents=True)
    backup_records = []
    for remote, local_rel in BACKUPS:
        local = REPO / local_rel
        if not local.is_file():
            raise ValueError("missing host backup: %s" % local_rel)
        backup_records.append({"remote_path": remote, "host_path": local_rel,
                               "bytes": local.stat().st_size, "sha256": sha(local)})
    report = {
        "schema": "fz3b-v10.2-task-owned-remote-space-cleanup-v1",
        "status": "RUNNING",
        "boot_id": BOOT,
        "mode": "delete_only_exact_verified_task_owned_obsolete_directories",
        "protected_paths": PROTECTED,
        "delete_paths": DELETE_PATHS,
        "host_backup_checks": backup_records,
        "recovered_evidence": [],
        "commands": [],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    client = helper.connect()
    try:
        protected_checks = "; ".join(
            "test \"$(sha256sum {path}|cut -d' ' -f1)\" = {digest}".format(
                path=shlex.quote(path), digest=digest)
            for path, digest in sorted(PROTECTED.items()))
        candidate_checks = "; ".join(
            "test -d {path}; test ! -L {path}; test \"$(realpath {path})\" = {path}".format(
                path=shlex.quote(path)) for path in DELETE_PATHS)
        run(client, "cleanup-preflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test ! -e /sys/module/cnn_ddr_v10_p3_candidate; "
            "test ! -e /dev/network10_v10_p3; {protected}; {candidates}; "
            "df -Pk /root; df -i /root".format(
                boot=BOOT, protected=protected_checks, candidates=candidate_checks), report)
        sftp = client.open_sftp()
        try:
            for remote, local_rel in RECOVER:
                local = OUT / local_rel
                local.parent.mkdir(parents=True, exist_ok=True)
                sftp.get(remote, str(local))
                report["recovered_evidence"].append({
                    "remote_path": remote,
                    "host_path": local.relative_to(REPO).as_posix(),
                    "bytes": local.stat().st_size,
                    "sha256": sha(local),
                })
        finally:
            sftp.close()
        all_checks = list(backup_records) + report["recovered_evidence"]
        remote_backup_checks = "; ".join(
            "test \"$(sha256sum {path}|cut -d' ' -f1)\" = {digest}".format(
                path=shlex.quote(item["remote_path"]), digest=item["sha256"])
            for item in all_checks)
        run(client, "host-backup-sha-matches",
            "set -eu; %s; echo HOST_BACKUP_SHA_MATCH_PASS" % remote_backup_checks,
            report, 600)
        for index, path in enumerate(DELETE_PATHS):
            run(client, "delete-%02d" % index,
                "set -eu; p={path}; test -d \"$p\"; test ! -L \"$p\"; "
                "du -sk \"$p\"; rm -rf -- \"$p\"; test ! -e \"$p\"".format(
                    path=shlex.quote(path)), report, 300)
        run(client, "cleanup-postflight",
            "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = {boot}; "
            "test -d /sys/module/fpgadrv; test -c /dev/fpgadrv0; "
            "test \"$(cat /sys/module/fpgadrv/refcnt)\" = 0; "
            "test -z \"$(fuser /dev/fpgadrv0 2>/dev/null || true)\"; "
            "test ! -e /sys/module/cnn_ddr_v10_p3_candidate; "
            "test ! -e /dev/network10_v10_p3; {protected}; "
            "test -d /root/network10-v10.1-board-window; "
            "test -d /root/network10-v10.1-ps-opt-20261007; "
            "test -d /root/network10-v10.1-ps-software-ab6-20261007; "
            "test -d /root/network10-v10.1-seven-opt-20261007; "
            "test -d /root/board-debug-kernel-20261004; "
            "df -Pk /root; df -hT /root; df -i /root; "
            "echo FACTORY_AND_P3_PROTECTED_STATE_PASS".format(
                boot=BOOT, protected=protected_checks), report)
        report["status"] = "PASS_VERIFIED_TASK_OWNED_REMOTE_SPACE_CLEANUP"
    finally:
        client.close()
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (OUT / "receipt.json").write_bytes(raw)
        print(json.dumps({"status": report.get("status", "FAILED"),
                          "receipt_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
