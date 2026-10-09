#!/usr/bin/env python3
"""Target-only proof that a stalled pipe write obeys the request deadline."""
from __future__ import print_function

import json
import os
import stat
import sys
import tempfile
import time

import numpy as np

from cnn_v10_ps_clients import OptimizedOrtPartitionClient


CONTRACT = {
    "inputs": [{"name": "input", "shape": [1, 262144],
                "dtype": "<f4", "bytes": 1048576}],
    "outputs": [{"name": "output", "shape": [1, 1],
                 "dtype": "<f4", "bytes": 4}],
}


def main():
    directory = tempfile.mkdtemp(prefix="cnn-v10-ps-timeout-")
    runner = os.path.join(directory, "blocked_runner.py")
    source = """#!/usr/bin/env python3
import json, time
print(json.dumps({
  'kind':'ready','ort_version':'1.16.3','api_version':16,'threads':4,
  'load_ms':0.0,'allow_spinning':False,'preallocated_outputs':True,
  'input_bytes':1048576,'output_bytes':4,
  'inputs':[{'name':'input','shape':[1,262144],'dtype':'float32','bytes':1048576}],
  'outputs':[{'name':'output','shape':[1,1],'dtype':'float32','bytes':4}]
}), flush=True)
time.sleep(60)
"""
    with open(runner, "w") as stream:
        stream.write(source)
    os.chmod(runner, os.stat(runner).st_mode | stat.S_IXUSR)
    client = OptimizedOrtPartitionClient(
        [sys.executable, runner], CONTRACT, threads=4,
        startup_timeout=2.0, request_timeout=0.25, reap_timeout=0.25,
        allow_spinning=0, preallocate_outputs=1)
    started = time.monotonic()
    caught = None
    try:
        client.infer([np.zeros((1, 262144), dtype="<f4")])
    except TimeoutError as error:
        caught = error
    elapsed = time.monotonic() - started
    if caught is None:
        raise AssertionError("blocked input write did not time out")
    if elapsed >= 2.0:
        raise AssertionError("timeout/reap took too long: %.6fs" % elapsed)
    if not client._closed or client.process.poll() is None:
        raise AssertionError("timed-out client was not closed and reaped")
    print(json.dumps({"status": "PASS_NONBLOCKING_WRITE_DEADLINE_AND_REAP",
                      "elapsed_s": elapsed,
                      "error": str(caught)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
