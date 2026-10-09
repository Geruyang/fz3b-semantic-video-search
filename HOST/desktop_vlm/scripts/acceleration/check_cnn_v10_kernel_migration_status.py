#!/usr/bin/env python3
from __future__ import print_function
import json
import sys
from pathlib import Path

REPO = Path(r"E:\AIProject\FPGAVibecoding")
sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper

client = helper.connect()
try:
    result = helper.run(
        client, "read-only-migration-status",
        "set -eu; pgrep -af 'tar|sha256sum' || true; "
        "stat -c '%s %y' /media/root/ESD-USB3/codex-fpga-backups/board-debug-kernel-20261004.tar; "
        "df -Pk /root /media/root/ESD-USB3; "
        "stat -f -c 'ROOT_BLOCK_SIZE=%S ROOT_TOTAL_BLOCKS=%b ROOT_FREE_BLOCKS=%f ROOT_AVAILABLE_BLOCKS=%a' /root", 30)
    print(json.dumps(result, indent=2, sort_keys=True))
finally:
    client.close()
