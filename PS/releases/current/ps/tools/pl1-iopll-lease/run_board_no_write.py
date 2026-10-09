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
KO_SHA = "3e3643b8cb334b610095311f563cd9019b1acc886fd2c133efec063bf2a6f272"
CLIENT = HERE / "lease_no_write_gate.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


account = re.findall(
    r"默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`", DOC.read_text(encoding="utf-8")
)[0]
env = os.environ.copy()
env.update({"FZ3B_SSH_PASSWORD": account[1], "SSH_ASKPASS": str(ASKPASS),
            "SSH_ASKPASS_REQUIRE": "force", "DISPLAY": "codex-no-write-gate"})
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
        raise RuntimeError("%s failed: %d" % (name, result.returncode))
    return record


started = datetime.datetime.now(datetime.timezone.utc).isoformat()
passed = False
client_result = None
failure = None
try:
    run("preflight", (
        "set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = '%s'; "
        "cd '%s'; test \"$(sha256sum fz3b_pl1_iopll_lease.ko | cut -d' ' -f1)\" = '%s'; "
        "test ! -e /sys/module/fz3b_pl1_iopll_lease; test ! -e /dev/fz3b_pl1_iopll_lease; "
        "test ! -e /sys/module/cnn_ddr_v10_p3_dma_candidate; "
        "test -z \"$(pgrep -f '[o]rt_partition_runner|[b]enchmark_cnn_pipeline_v10|[r]un_cnn_pipeline_v10' || true)\"; "
        "/root/workspace/network10-v10.4-clock-raw-baseline-001/read_fz3b_clock_registers; "
        "grep -E '^[[:space:]]*(pl[0-3]_ref(_div[12])?|iopll|rpll)[[:space:]]' /sys/kernel/debug/clk/clk_summary"
        % (BOOT, REMOTE, KO_SHA)))
    scp = subprocess.run(["scp", "-q"] + common +
                         [str(CLIENT), "%s:%s/%s" % (target, REMOTE, CLIENT.name)],
                         cwd=str(ROOT), env=env, text=True, capture_output=True, timeout=30)
    commands.append({"name": "upload-client", "exit_code": scp.returncode,
                     "stdout": scp.stdout, "stderr": scp.stderr,
                     "source_sha256": sha(CLIENT)})
    if scp.returncode:
        raise RuntimeError("client upload failed")
    run("load-and-no-write-cycle", (
        "set -eu; cd '%s'; python3 -m py_compile lease_no_write_gate.py; "
        "dmesg_before=$(dmesg | wc -l); insmod ./fz3b_pl1_iopll_lease.ko; "
        "test -c /dev/fz3b_pl1_iopll_lease; test \"$(cat /sys/module/fz3b_pl1_iopll_lease/refcnt)\" = 0; "
        "grep -E '^[[:space:]]*(pl[0-3]_ref(_div[12])?|iopll|rpll)[[:space:]]' /sys/kernel/debug/clk/clk_summary > clocks.before; "
        "python3 -B lease_no_write_gate.py --output cycle-result.json; "
        "test \"$(cat /sys/module/fz3b_pl1_iopll_lease/refcnt)\" = 0; "
        "grep -E '^[[:space:]]*(pl[0-3]_ref(_div[12])?|iopll|rpll)[[:space:]]' /sys/kernel/debug/clk/clk_summary > clocks.after; "
        "cmp clocks.before clocks.after; cat cycle-result.json; "
        "rmmod fz3b_pl1_iopll_lease; test ! -e /sys/module/fz3b_pl1_iopll_lease; "
        "test ! -e /dev/fz3b_pl1_iopll_lease; "
        "/root/workspace/network10-v10.4-clock-raw-baseline-001/read_fz3b_clock_registers; "
        "dmesg | tail -n +$((dmesg_before+1)); echo PL1_IOPLL_NO_WRITE_GATE_PASS"
        % REMOTE), timeout=60)
    result_record = run("read-cycle-result", "cat '%s/cycle-result.json'" % REMOTE)
    client_result = json.loads(result_record["stdout"])
    if not client_result.get("pass"):
        raise RuntimeError("client result did not pass")
    passed = True
except Exception as error:
    failure = repr(error)
    run("failure-state-readonly", (
        "set +e; cat '%s/cycle-result.json' 2>/dev/null; "
        "cat /sys/module/fz3b_pl1_iopll_lease/refcnt 2>/dev/null; "
        "/root/workspace/network10-v10.4-clock-raw-baseline-001/read_fz3b_clock_registers"
        % REMOTE), check=False)
finally:
    env["FZ3B_SSH_PASSWORD"] = ""
    receipt = {
        "schema": "fz3b-v10.4-pl1-iopll-lease-board-no-write-gate-v1",
        "pass": passed,
        "hardware_execution": True,
        "clock_write_performed": False,
        "pl_bit_modified": False,
        "boot_id": BOOT,
        "target_ko_sha256": KO_SHA,
        "client_sha256": sha(CLIENT),
        "client_result": client_result,
        "failure": failure,
        "commands": commands,
        "started_utc": started,
        "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    out = HERE / "board-no-write-gate-receipt.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    print(sha(out))
if not passed:
    raise SystemExit(1)
