#!/usr/bin/env python3
"""POSIX target smoke for the mmap client's timeout, reap, and ownership."""
from __future__ import print_function

import json
import os
import pathlib
import tempfile
import time

import numpy as np

from cnn_v10_ps_shm_clients import ShmOrtPartitionClient


CONTRACT = {
    "inputs": [{"name": "x", "shape": [1, 2], "dtype": "float32", "bytes": 8}],
    "outputs": [{"name": "y", "shape": [1, 2], "dtype": "float32", "bytes": 8}],
}


def _runner(root, slow):
    path = pathlib.Path(root) / ("slow-runner" if slow else "normal-runner")
    source = """#!/usr/bin/env python3
import json,mmap,struct,sys,time
fd=int(sys.argv[2]); mm=mmap.mmap(fd,80,access=mmap.ACCESS_WRITE)
print(json.dumps({\"kind\":\"ready\",\"protocol\":3,\"api_version\":16,\"ort_version\":\"1.16.3\",\"threads\":2,\"load_ms\":0.1,\"allow_spinning\":False,\"preallocated_outputs\":False,\"input_bytes\":8,\"output_bytes\":8,\"inputs\":[{\"name\":\"x\",\"shape\":[1,2],\"dtype\":\"float32\",\"bytes\":8}],\"outputs\":[{\"name\":\"y\",\"shape\":[1,2],\"dtype\":\"float32\",\"bytes\":8}]}),flush=True)
while True:
 p=sys.stdin.buffer.read(8)
 if not p: break
 if len(p)!=8: sys.exit(3)
 rid=struct.unpack('<Q',p)[0]
 if SLOW: time.sleep(1.0)
 a,b=struct.unpack_from('<ff',mm,64); struct.pack_into('<ff',mm,72,a+1,b+1)
 print(json.dumps({\"kind\":\"result\",\"request_id\":rid,\"run_ms\":0.25}),flush=True)
""".replace("SLOW", "True" if slow else "False")
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return str(path)


def main():
    if os.name != "posix":
        raise RuntimeError("target smoke requires POSIX inherited descriptors")
    with tempfile.TemporaryDirectory() as root:
        normal = ShmOrtPartitionClient(
            [_runner(root, False), "unused", "2"], CONTRACT, threads=2,
            request_timeout=1.0, reap_timeout=0.2)
        try:
            first, unused = normal.infer([np.asarray([[2, 4]], dtype=np.float32)])
            second, unused = normal.infer([np.asarray([[5, 7]], dtype=np.float32)])
            if first["y"].tolist() != [[3.0, 5.0]] or second["y"].tolist() != [[6.0, 8.0]]:
                raise RuntimeError("shared client output mismatch")
            if first["y"].tolist() != [[3.0, 5.0]] or not first["y"].flags.owndata:
                raise RuntimeError("shared client did not return an independent output")
        finally:
            normal.close()
        slow = ShmOrtPartitionClient(
            [_runner(root, True), "unused", "2"], CONTRACT, threads=2,
            request_timeout=0.1, reap_timeout=0.1)
        process = slow.process
        started = time.monotonic()
        try:
            slow.infer([np.asarray([[1, 2]], dtype=np.float32)])
            raise RuntimeError("slow child unexpectedly completed")
        except TimeoutError as error:
            elapsed = time.monotonic() - started
            if process.poll() is None or not slow._closed or elapsed > 1.0:
                raise RuntimeError("timeout did not bound and reap the child")
            print(json.dumps({"status": "PASS_SHM_INDEPENDENT_OUTPUT_TIMEOUT_REAP",
                              "elapsed_s": elapsed, "error": str(error)}, sort_keys=True))


if __name__ == "__main__":
    main()
