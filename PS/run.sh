#!/bin/sh
set -eu
cd /root/fz3b-vision-console-20261009-001
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export LD_LIBRARY_PATH=/root/board-debug-runtime-20261004/runtime/onnxruntime-linux-aarch64-1.16.3/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
exec python3 -B -m vision_app.board_agent --config /root/fz3b-vision-console-20261009-001/config.json
