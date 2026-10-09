import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]
KNOWN = ROOT / "artifacts/board-debug-20261004/serial/board-known_hosts"
ASKPASS = HERE.parent / "network10-v10.4-pl-branch-readonly-audit-001/ssh_askpass.cmd"
DOC = ROOT / "docs/hardware/FZ3B/TF-LINUX-INSTALL.md"
HOST = "192.168.1.254"
REMOTE = "/root/workspace/network10-v10.4-pl1-iopll-lease-candidate-001"
BOOT = "3d766e07-9adf-4515-93c3-a9214190f12d"
READY = HERE / "pl1-jtag-ready-receipt-002.json"
READY_SHA = "9f2c47dd2e4689952fa941d2aee2ad6f6b502b9d1702da7fefc76bd7d5fbe553"
JTAG_RECEIPT = ROOT / (
    "artifacts/board-debug-20261008/acceleration/jtag/"
    "cnn-v10-xsdb-pl1-100mhz-shortcycle-transaction-002/receipt.json")
JTAG_RECEIPT_SHA = "2783f428091b2d694a1d77bb6245d4cc561d379936f815a55698496e9c610922"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


account = re.findall(
    r"默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`", DOC.read_text(encoding="utf-8")
)[0]
env = os.environ.copy()
env.update({"FZ3B_SSH_PASSWORD": account[1], "SSH_ASKPASS": str(ASKPASS),
            "SSH_ASKPASS_REQUIRE": "force", "DISPLAY": "codex-pl1-finalize"})
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


passed = False
failure = None
holder_result = None
try:
    if sha(READY) != READY_SHA:
        raise RuntimeError("READY receipt identity mismatch")
    if sha(JTAG_RECEIPT) != JTAG_RECEIPT_SHA:
        raise RuntimeError("JTAG transaction receipt identity mismatch")
    jtag = json.loads(JTAG_RECEIPT.read_text(encoding="utf-8"))
    transaction = jtag.get("clock_transaction", {})
    if (not jtag.get("pass") or not jtag.get("transaction_started") or
            not transaction.get("double_read_checks") or
            not transaction.get("pl0_unchanged") or
            not transaction.get("pl1_restored") or
            transaction.get("pl1_entry_final") != "0x00052000"):
        raise RuntimeError("JTAG transaction does not prove exact PL1 restoration")

    run("request-finalize", (
        "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = '%s'; "
        "cd '%s'; kill -0 $(cat pl1b.pid); test ! -e pl1b.command; "
        "printf 'FINALIZE\\n' > pl1b.command; "
        "for i in $(seq 1 200); do test -f pl1b.result.json && break; sleep 0.05; done; "
        "test -f pl1b.result.json; "
        "for i in $(seq 1 100); do ! kill -0 $(cat pl1b.pid) 2>/dev/null && break; sleep 0.05; done; "
        "cat pl1b.result.json; cat pl1b.holder.log" % (BOOT, REMOTE)), timeout=30)
    result = run("cleanup-and-verify", (
        "set -eu; cd '%s'; cat pl1b.result.json; "
        "test \"$(cat /sys/module/fz3b_pl1_iopll_lease/refcnt)\" = 0; "
        "printf 'prepare='; cat /sys/kernel/debug/clk/iopll/clk_prepare_count; "
        "printf 'enable='; cat /sys/kernel/debug/clk/iopll/clk_enable_count; "
        "/root/workspace/network10-v10.4-clock-raw-baseline-001/read_fz3b_clock_registers; "
        "rmmod fz3b_pl1_iopll_lease; "
        "test ! -e /sys/module/fz3b_pl1_iopll_lease; test ! -e /dev/fz3b_pl1_iopll_lease; "
        "echo PL1_LEASE_FINALIZE_CLEAN_PASS" % REMOTE))
    first = result["stdout"].find("{")
    end = result["stdout"].find("}\nprepare=", first)
    holder_result = json.loads(result["stdout"][first:end + 1])
    if not holder_result.get("pass") or holder_result.get("status") != "PASS_FINALIZED":
        raise RuntimeError("holder did not finalize cleanly")
    if "prepare=13\nenable=9" not in result["stdout"]:
        raise RuntimeError("IOPLL CCF counts did not return to baseline")
    passed = True
except Exception as error:
    failure = repr(error)
    run("failure-state-readonly", (
        "set +e; cd '%s'; cat pl1b.result.json 2>/dev/null; cat pl1b.holder.log 2>/dev/null; "
        "cat /sys/module/fz3b_pl1_iopll_lease/refcnt 2>/dev/null; "
        "printf 'prepare='; cat /sys/kernel/debug/clk/iopll/clk_prepare_count 2>/dev/null; "
        "printf 'enable='; cat /sys/kernel/debug/clk/iopll/clk_enable_count 2>/dev/null"
        % REMOTE), check=False)
finally:
    env["FZ3B_SSH_PASSWORD"] = ""
    receipt = {
        "schema": "fz3b-v10.4-pl1-iopll-jtag-shortcycle-postflight-v1",
        "status": "PASS_PL1_100MHZ_SHORTCYCLE_RESTORED" if passed else "FAIL",
        "pass": passed,
        "jtag_connected": True,
        "clock_write_performed": True,
        "ready_receipt_sha256": READY_SHA,
        "jtag_transaction_receipt_sha256": JTAG_RECEIPT_SHA,
        "holder_result": holder_result,
        "failure": failure,
        "commands": commands,
        "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    out = HERE / "pl1-jtag-shortcycle-postflight-receipt.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    print(sha(out))
if not passed:
    raise SystemExit(1)
