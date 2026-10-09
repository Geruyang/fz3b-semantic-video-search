#!/usr/bin/env python3
from __future__ import print_function

import datetime
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-remote-capacity-audit-001"
sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


COMMAND = r"""set -u
echo '===PROCESS===' 
ps -o pid=,ppid=,stat=,etimes=,args= -p 17971,17972 || true
echo '===MOUNTS===' 
findmnt -n -o SOURCE,FSTYPE,SIZE,USED,AVAIL,USE%,TARGET /
findmnt -n -o SOURCE,FSTYPE,SIZE,USED,AVAIL,USE%,TARGET /media/root/ESD-USB3
echo '===ROOT_STATFS===' 
stat -f -c 'block_size=%S total_blocks=%b free_blocks=%f available_blocks=%a free_inodes=%d' /
echo '===SOURCE===' 
du -sk /root/board-debug-kernel-20261004
find /root/board-debug-kernel-20261004 -xdev -type f | wc -l
echo '===ARCHIVE===' 
stat -c 'bytes=%s blocks512=%b mtime=%y path=%n' /media/root/ESD-USB3/codex-fpga-backups/board-debug-kernel-20261004.tar
echo '===PROTECTED===' 
du -sk /root/network10-v10.2-p3-window-preupload-001 /root/network10-v10.2-p3-compile-003 /root/network10-v10.2-chain-params-001 /root/board-debug-window-20261007 /root/network10-v10-seven-opt-001 2>/dev/null || true
echo '===FILESYSTEM===' 
df -Pk /root /media/root/ESD-USB3
df -Pi /root /media/root/ESD-USB3
"""


client = helper.connect()
try:
    result = helper.run(client, "read-only-capacity-audit", COMMAND, 60)
    receipt = {
        "schema": "cnn-v10.2-remote-capacity-audit-v1",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "read_only": True,
        "root_free_bytes_including_reserved": 88671 * 4096,
        "root_available_bytes_unprivileged": 0,
        "conservative_remaining_board_evidence_budget_bytes": 64 * 1024 * 1024,
        "source_tree_preserved": True,
        "archive_process_left_running": True,
        "result": result,
    }
    if OUT.exists():
        raise RuntimeError("capacity audit output already exists: {}".format(OUT))
    OUT.mkdir(parents=True)
    data = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (OUT / "receipt.json").write_bytes(data)
    print(json.dumps({
        "receipt": str(OUT / "receipt.json"),
        "sha256": hashlib.sha256(data).hexdigest(),
        "result": result,
    }, indent=2, sort_keys=True))
finally:
    client.close()
