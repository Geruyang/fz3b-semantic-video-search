#!/usr/bin/env python3
"""Repeat the frozen stream-runtime t3/inflight3 30-pair baseline in this window."""
from __future__ import print_function
import datetime, hashlib, json, shlex, sys
from pathlib import Path

REPO=Path(r"E:\AIProject\FPGAVibecoding")
OUT=REPO/"artifacts/board-debug-20261007/acceleration/network/network10-v10.1-frozen-stream-same-window-001"
BASE="/root/network10-v10.1-board-window"
BOOT="fd395d2a-974c-4a1a-827d-568452cd8488"
RELEASE="3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
DEPLOY="531cb46623c760df3c09f56cb285e6dff3320da44c1f3570af3e02e98754ea3d"
LABEL="optimized-pipeline3-t3-30-seven-opt-window"
sys.path.insert(0,str(REPO/"artifacts/board-debug-20261004/acceleration/network"));import dma_driver_rebuild as helper
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(c,n,x,r,t=300):
 v=helper.run(c,n,x,t);r["commands"].append(v)
 if v["exit_code"]:raise RuntimeError("%s failed: %s %s"%(n,v["stdout"],v["stderr"]))
 return v
def main():
 if OUT.exists():raise RuntimeError("refusing overwrite")
 OUT.mkdir(parents=True);r={"schema":"fz3b-v10.1-frozen-stream-same-window-v1","status":"FAILED","boot_id":BOOT,"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),"commands":[]}
 c=helper.connect()
 try:
  run(c,"preflight","set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; grep -qx applied /sys/kernel/config/device-tree/overlays/network10-v10-trace18/status; test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; test \"$(sha256sum %s/runtime/cnn_pipeline_v10_stream_runtime.py|cut -d' ' -f1)\" = d8224c5ab45db18cde22e067b8b94d4c19833711e9a589e67559750822a5d872; test \"$(sha256sum %s/runtime/benchmark_cnn_pipeline_v10_stream.py|cut -d' ' -f1)\" = 2ce3c03ec2312956f6502b59f840b7106a7a1e6d7c7c2489d50cf2b5703e51f6"%(BOOT,BASE,BASE),r)
  run(c,"reload","set -eu; if test -e /sys/module/cnn_ddr_v10_candidate; then /sbin/rmmod cnn_ddr_v10_candidate; fi; /sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko; test -c /dev/network10_v10"%BASE,r)
  inner=("cd {b}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B benchmark_cnn_pipeline_v10_stream.py --bundle-root {b}/release --expected-bundle-sha256 {rel} --deployment-manifest {b}/platform/manifest.json --expected-deployment-sha256 {dep} --runner {b}/bin/ort_partition_runner_v2 --ps-client optimized --schedule pipeline --threads 3 --max-in-flight 3 --warmup-pairs 3 --measured-pairs 30 --timeout-s 300 --input-tensor {b}/inputs/image-00-input.f32 --input-tensor {b}/inputs/image-01-input.f32 --expected-feature-sha256 4121608b7bb27060d5babe05dd6ae723d191b4405a0852d55adde876f4ef16b3 --expected-feature-sha256 7654afe2d025731f18d23268c2109aba3445b2708a8e9ef1a2e49ed84c369adb --output-dir {b}/results-stream/{label}").format(b=BASE,rel=RELEASE,dep=DEPLOY,label=LABEL)
  run(c,"run", "set -eu; env ORT_PARTITION_ALLOW_SPINNING=0 ORT_PARTITION_PREALLOC_OUTPUTS=0 sh -c %s"%shlex.quote(inner),r,3600)
  s=c.open_sftp()
  try:s.get(BASE+"/results-stream/"+LABEL+"/result.json",str(OUT/"result.json"))
  finally:s.close()
  d=json.loads((OUT/"result.json").read_text());r["result"]={"sha256":sha(OUT/"result.json"),"status":d["status"],"fps":d["measured"]["fps_including_fill_and_drain"],"execution_ms":d["measured"]["execution_ms"]}
  if d["status"]!="FEATURE_EXACT_PROTOCOL_CLEAN":raise RuntimeError("frozen stream gate failed")
  r["status"]="PASS_FROZEN_STREAM_SAME_WINDOW"
 finally:
  c.close();r["finished_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z');raw=(json.dumps(r,indent=2,sort_keys=True)+'\n').encode();(OUT/"receipt.json").write_bytes(raw);print(json.dumps({"status":r["status"],"sha256":hashlib.sha256(raw).hexdigest()}))
if __name__=='__main__':main()
