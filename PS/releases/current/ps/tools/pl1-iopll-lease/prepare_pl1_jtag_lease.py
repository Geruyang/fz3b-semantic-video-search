import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import time


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]
KNOWN = ROOT / "artifacts/board-debug-20261004/serial/board-known_hosts"
ASKPASS = HERE.parent / "network10-v10.4-pl-branch-readonly-audit-001/ssh_askpass.cmd"
DOC = ROOT / "docs/hardware/FZ3B/TF-LINUX-INSTALL.md"
HOST = "192.168.1.254"
REMOTE = "/root/workspace/network10-v10.4-pl1-iopll-lease-candidate-001"
BOOT = "3d766e07-9adf-4515-93c3-a9214190f12d"
KO_SHA = "3e3643b8cb334b610095311f563cd9019b1acc886fd2c133efec063bf2a6f272"
HOLDER = HERE / "lease_jtag_hold.py"
JTAG_RECEIPT = ROOT / (
    "artifacts/board-debug-20261008/acceleration/jtag/"
    "cnn-v10-xsdb-pl1-100mhz-shortcycle-review-001/receipt.json")
JTAG_RECEIPT_SHA = "2414bfc27283f8b088b5608eb93049ab93d300df800c8472796d9bec9a9eb7ae"
JTAG_TCL_SHA = "37ac51a44bfea2dc90e73b02192c12444e761f0a65fd1986bbcdb079521a9e0a"
OVERLAY = "/sys/kernel/config/device-tree/overlays/network10-v10.4-a0004-fpd-cmask"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


account = re.findall(
    r"默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`", DOC.read_text(encoding="utf-8")
)[0]
env = os.environ.copy()
env.update({"FZ3B_SSH_PASSWORD": account[1], "SSH_ASKPASS": str(ASKPASS),
            "SSH_ASKPASS_REQUIRE": "force", "DISPLAY": "codex-pl1-lease"})
target = "%s@%s" % (account[0], HOST)
common = ["-o", "BatchMode=no", "-o", "ConnectTimeout=10", "-o",
          "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=%s" % KNOWN]
commands = []


def run(name, command, timeout=60, check=True):
    result = subprocess.run(["ssh", "-T"] + common + [target, command],
                            cwd=str(ROOT), env=env, text=True,
                            capture_output=True, timeout=timeout)
    record = {"name": name, "command": command, "exit_code": result.returncode,
              "stdout": result.stdout, "stderr": result.stderr}
    commands.append(record)
    if check and result.returncode:
        raise RuntimeError("%s failed: %d: %s" %
                           (name, result.returncode, result.stderr.strip()))
    return record


started = datetime.datetime.now(datetime.timezone.utc).isoformat()
passed = False
failure = None
ready = None
baseline_counts = None
held_counts = None
try:
    if sha(JTAG_RECEIPT) != JTAG_RECEIPT_SHA:
        raise RuntimeError("JTAG review receipt identity mismatch")
    review = json.loads(JTAG_RECEIPT.read_text(encoding="utf-8"))
    if not review.get("pass") or review.get("board_executed"):
        raise RuntimeError("JTAG short-cycle review is not a clean offline PASS")
    if review["artifacts"]["transaction_tcl"]["sha256"] != JTAG_TCL_SHA:
        raise RuntimeError("JTAG Tcl identity mismatch")

    preflight = run("preflight", (
        "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = '%s'; "
        "cd '%s'; test \"$(sha256sum fz3b_pl1_iopll_lease.ko | cut -d' ' -f1)\" = '%s'; "
        "test ! -e /sys/module/fz3b_pl1_iopll_lease; test ! -e /dev/fz3b_pl1_iopll_lease; "
        "test ! -e /sys/module/cnn_ddr_v10_p3_dma_candidate; test ! -e /dev/network10_v10_p3_dma; "
        "test -d '%s'; test \"$(cat '%s/status')\" = applied; "
        "test -z \"$(pgrep -f '[o]rt_partition_runner|[b]enchmark_cnn_pipeline_v10|[r]un_cnn_pipeline_v10|[l]ease_jtag_hold' || true)\"; "
        "printf 'prepare='; cat /sys/kernel/debug/clk/iopll/clk_prepare_count; "
        "printf 'enable='; cat /sys/kernel/debug/clk/iopll/clk_enable_count; "
        "/root/workspace/network10-v10.4-clock-raw-baseline-001/read_fz3b_clock_registers; "
        "echo PL1_LEASE_PREFLIGHT_PASS" %
        (BOOT, REMOTE, KO_SHA, OVERLAY, OVERLAY)))
    counts = re.findall(r"^(prepare|enable)=(\d+)$", preflight["stdout"], re.M)
    baseline_counts = dict((key, int(value)) for key, value in counts)
    if set(baseline_counts) != {"prepare", "enable"}:
        raise RuntimeError("missing baseline IOPLL CCF counts")

    scp = subprocess.run(["scp", "-q"] + common +
                         [str(HOLDER), "%s:%s/%s" %
                          (target, REMOTE, HOLDER.name)],
                         cwd=str(ROOT), env=env, text=True,
                         capture_output=True, timeout=30)
    commands.append({"name": "upload-holder", "exit_code": scp.returncode,
                     "stdout": scp.stdout, "stderr": scp.stderr,
                     "source_sha256": sha(HOLDER)})
    if scp.returncode:
        raise RuntimeError("holder upload failed")

    run("start-holder", (
        "set -eu; cd '%s'; python3 -m py_compile lease_jtag_hold.py; "
        "test \"$(sha256sum lease_jtag_hold.py | cut -d' ' -f1)\" = '%s'; "
        "rm -f pl1.ready.json pl1.command pl1.result.json pl1.holder.log pl1.pid; "
        "insmod ./fz3b_pl1_iopll_lease.ko; test -c /dev/fz3b_pl1_iopll_lease; "
        "nohup python3 -B lease_jtag_hold.py --ready pl1.ready.json "
        "--command pl1.command --result pl1.result.json --timeout 900 "
        ">pl1.holder.log 2>&1 & echo $! > pl1.pid; "
        "for i in $(seq 1 100); do test -f pl1.ready.json && break; "
        "kill -0 $(cat pl1.pid); sleep 0.05; done; "
        "test -f pl1.ready.json; kill -0 $(cat pl1.pid); "
        "printf 'prepare='; cat /sys/kernel/debug/clk/iopll/clk_prepare_count; "
        "printf 'enable='; cat /sys/kernel/debug/clk/iopll/clk_enable_count; "
        "cat pl1.ready.json" % (REMOTE, sha(HOLDER))), timeout=30)
    held = run("verify-holder", (
        "set -eu; cd '%s'; kill -0 $(cat pl1.pid); "
        "test -e /sys/module/fz3b_pl1_iopll_lease; "
        "test \"$(cat /sys/module/fz3b_pl1_iopll_lease/refcnt)\" = 1; "
        "printf 'prepare='; cat /sys/kernel/debug/clk/iopll/clk_prepare_count; "
        "printf 'enable='; cat /sys/kernel/debug/clk/iopll/clk_enable_count; "
        "cat pl1.ready.json" % REMOTE))
    counts = re.findall(r"^(prepare|enable)=(\d+)$", held["stdout"], re.M)
    held_counts = dict((key, int(value)) for key, value in counts)
    if held_counts["prepare"] != baseline_counts["prepare"] + 1:
        raise RuntimeError("IOPLL prepare count did not rise by exactly one")
    if held_counts["enable"] != baseline_counts["enable"] + 1:
        raise RuntimeError("IOPLL enable count did not rise by exactly one")
    ready_text = held["stdout"][held["stdout"].find("{"):]
    ready = json.loads(ready_text)
    if ready.get("status") != "READY_FOR_PL1_JTAG_TRANSACTION":
        raise RuntimeError("holder did not reach READY")
    passed = True
except Exception as error:
    failure = repr(error)
    run("failure-state-readonly", (
        "set +e; cd '%s'; cat pl1.ready.json 2>/dev/null; "
        "cat pl1.result.json 2>/dev/null; cat pl1.holder.log 2>/dev/null; "
        "cat /sys/module/fz3b_pl1_iopll_lease/refcnt 2>/dev/null; "
        "printf 'prepare='; cat /sys/kernel/debug/clk/iopll/clk_prepare_count 2>/dev/null; "
        "printf 'enable='; cat /sys/kernel/debug/clk/iopll/clk_enable_count 2>/dev/null"
        % REMOTE), check=False)
finally:
    env["FZ3B_SSH_PASSWORD"] = ""
    receipt = {
        "schema": "fz3b-v10.4-pl1-iopll-jtag-ready-v1",
        "status": "READY_FOR_PL1_JTAG_100MHZ_SHORTCYCLE" if passed else "FAIL",
        "pass": passed,
        "hardware_execution": True,
        "clock_write_performed": False,
        "boot_id": BOOT,
        "target_ko_sha256": KO_SHA,
        "holder_sha256": sha(HOLDER),
        "jtag_review_receipt_sha256": JTAG_RECEIPT_SHA,
        "jtag_tcl_sha256": JTAG_TCL_SHA,
        "baseline_iopll_ccf_counts": baseline_counts,
        "held_iopll_ccf_counts": held_counts,
        "holder_ready": ready,
        "failure": failure,
        "commands": commands,
        "started_utc": started,
        "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    out = HERE / "pl1-jtag-ready-receipt.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    print(sha(out))
if not passed:
    raise SystemExit(1)
