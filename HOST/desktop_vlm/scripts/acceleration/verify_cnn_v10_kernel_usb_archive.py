#!/usr/bin/env python3
from __future__ import print_function

import datetime
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(r"E:\AIProject\FPGAVibecoding")
OUT = REPO / "artifacts/board-debug-20261007/acceleration/network/network10-v10.2-kernel-tree-usb-archive-001"
sys.path.insert(0, str(REPO / "artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper


ARCHIVE = "/media/root/ESD-USB3/codex-fpga-backups/board-debug-kernel-20261004.tar"
SOURCE = "/root/board-debug-kernel-20261004"
COMMAND = """set -eu
test -d {source}
test -s {archive}
if ps -eo args= | grep -F 'tar -cpf {archive}' | grep -v grep >/dev/null; then
  echo ARCHIVE_WRITER_STILL_RUNNING >&2
  exit 71
fi
echo ARCHIVE_BYTES=$(stat -c %s {archive})
echo ARCHIVE_ENTRIES=$(tar -tf {archive} | wc -l)
DIFF=$(tar -df {archive} -C /root 2>&1) || {{ printf '%s\n' "$DIFF" >&2; exit 72; }}
test -z "$DIFF" || {{ printf '%s\n' "$DIFF" >&2; exit 73; }}
sha256sum {archive}
echo SOURCE_KIB=$(du -sk {source} | awk '{{print $1}}')
echo SOURCE_FILES=$(find {source} -xdev -type f | wc -l)
stat -f -c 'ROOT_BLOCK_SIZE=%S ROOT_FREE_BLOCKS=%f ROOT_AVAILABLE_BLOCKS=%a' /
df -Pk /media/root/ESD-USB3
echo KERNEL_TREE_ARCHIVE_VERIFIED
""".format(source=SOURCE, archive=ARCHIVE)


client = helper.connect()
try:
    result = helper.run(client, "verify-kernel-tree-usb-archive", COMMAND, 1800)
finally:
    client.close()

if result["exit_code"] != 0 or "KERNEL_TREE_ARCHIVE_VERIFIED" not in result["stdout"]:
    raise RuntimeError(json.dumps(result, indent=2, sort_keys=True))
receipt = {
    "schema": "cnn-v10.2-kernel-tree-usb-archive-v1",
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "pass": True,
    "read_only_verification": True,
    "source_preserved": True,
    "source": SOURCE,
    "archive": ARCHIVE,
    "result": result,
}
if OUT.exists():
    raise RuntimeError("archive receipt output already exists: {}".format(OUT))
OUT.mkdir(parents=True)
raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
(OUT / "receipt.json").write_bytes(raw)
print(json.dumps({
    "receipt": str(OUT / "receipt.json"),
    "sha256": hashlib.sha256(raw).hexdigest(),
    "remote_stdout": result["stdout"],
}, indent=2, sort_keys=True))
