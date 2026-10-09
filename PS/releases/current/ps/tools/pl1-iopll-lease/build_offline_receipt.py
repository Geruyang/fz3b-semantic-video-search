import hashlib
import json
import pathlib
import subprocess
import sys


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


test = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", str(HERE),
     "-p", "test_contract.py", "-v"],
    cwd=str(ROOT), text=True, capture_output=True,
)
files = {
    name: sha(HERE / name)
    for name in (
        "fz3b_pl1_iopll_lease.c",
        "fz3b_pl1_iopll_lease_uapi.h",
        "Makefile",
        "test_contract.py",
        "README.md",
    )
}
receipt = {
    "schema": "fz3b-v10.4-pl1-iopll-lease-offline-gate-v1",
    "pass": test.returncode == 0,
    "hardware_writes": False,
    "target_kernel_compile": False,
    "target_board_execution": False,
    "selected_branch": "PL1",
    "entry_branch_raw": ["0x01010802", "0x00052000", "0x00052000", "0x00052000"],
    "target_pl1_raw": "0x01010F00",
    "expected_target_hz": 99999999,
    "rollback_order": [
        "program original A0004 PL0 175 MHz bit",
        "restore PL1 to 0x00052000",
        "verify PL0..PL3, IOPLL, RPLL, PLL_STATUS and DDR exact",
        "FINALIZE and release IOPLL CCF lease",
    ],
    "source_sha256": files,
    "read_only_evidence": {
        "jtag_receipt": {
            "path": "artifacts/board-debug-20261008/acceleration/jtag/cnn-v10-xsdb-pl-clock-branches-readonly-001/receipt.json",
            "sha256": "832e2b01b0dd41703d56c6396628f049b55f4ac6abfee632d20c88726e6d3a8c",
        },
        "linux_ccf_receipt": {
            "path": "artifacts/board-debug-20261008/acceleration/network/network10-v10.4-pl-branch-readonly-audit-001/receipt.json",
            "sha256": "c08001acd8a96fcc52295d8a0c747a90b343ff8a6d4c4d199cf6059fd2ec08b5",
        },
        "a0004_bd": {
            "path": "w/v104p4noila175/cnn_pipeline_v10.srcs/sources_1/bd/cnn_pipeline_v10_shell/cnn_pipeline_v10_shell.bd",
            "sha256": sha(ROOT / "w/v104p4noila175/cnn_pipeline_v10.srcs/sources_1/bd/cnn_pipeline_v10_shell/cnn_pipeline_v10_shell.bd"),
            "pl_enable": [1, 0, 0, 0],
        },
    },
    "tests": {
        "command": "python -m unittest discover -s <candidate> -p test_contract.py -v",
        "exit_code": test.returncode,
        "stdout": test.stdout,
        "stderr": test.stderr,
    },
}
out = HERE / "offline-gate-receipt.json"
out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(out)
print(sha(out))
raise SystemExit(0 if receipt["pass"] else 1)
