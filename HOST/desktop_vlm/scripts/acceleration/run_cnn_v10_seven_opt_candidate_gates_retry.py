#!/usr/bin/env python3
"""Recover the setup-only N1 lifecycle miss and finish quantized short gates."""
from __future__ import print_function
import datetime, hashlib, json, shlex, sys
from pathlib import Path
REPO=Path(r"E:\AIProject\FPGAVibecoding")
OUT=REPO/"artifacts/board-debug-20261007/acceleration/network/network10-v10.1-seven-opt-candidate-gates-002"
REMOTE="/root/network10-v10.1-seven-opt-20261007"; BASE="/root/network10-v10.1-board-window"
BOOT="fd395d2a-974c-4a1a-827d-568452cd8488"
RELEASE="3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
DEPLOY="531cb46623c760df3c09f56cb285e6dff3320da44c1f3570af3e02e98754ea3d"
EXPECTED=("4121608b7bb27060d5babe05dd6ae723d191b4405a0852d55adde876f4ef16b3","7654afe2d025731f18d23268c2109aba3445b2708a8e9ef1a2e49ed84c369adb")
sys.path.insert(0,str(REPO/"artifacts/board-debug-20261004/acceleration/network"));import dma_driver_rebuild as helper
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(c,n,x,r,t=300,allow=False):
 v=helper.run(c,n,x,t);r["commands"].append(v)
 if v["exit_code"] and not allow:raise RuntimeError("%s failed: %s %s"%(n,v["stdout"],v["stderr"]))
 return v
def reload(c,n,r):
 run(c,n,"set -eu; test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; if test -e /sys/module/cnn_ddr_v10_candidate; then /sbin/rmmod cnn_ddr_v10_candidate; fi; /sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko; test -c /dev/network10_v10"%BASE,r)
def cmd(label,args):
 inner=("cd {r}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B benchmark_cnn_pipeline_v10_live.py --bundle-root {b}/release --expected-bundle-sha256 {rel} --deployment-manifest {b}/platform/manifest.json --expected-deployment-sha256 {dep} --runner {r}/bin/ort_partition_runner_v3 --ps-client mixed --native-lib {r}/bin/libcnn_v10_native_quant.so --threads 3 --max-in-flight 3 --warmup-pairs 3 --measured-pairs 10 --timeout-s 300 --input-tensor {b}/inputs/image-00-input.f32 --input-tensor {b}/inputs/image-01-input.f32 --expected-feature-sha256 {s0} --expected-feature-sha256 {s1} --reference-feature {r}/references/image-00-feature.f32 --reference-feature {r}/references/image-01-feature.f32 {a} --output-dir {r}/results/{l}").format(r=REMOTE,b=BASE,rel=RELEASE,dep=DEPLOY,s0=EXPECTED[0],s1=EXPECTED[1],a=args,l=label)
 return "set -eu; env ORT_PARTITION_ALLOW_SPINNING=0 ORT_PARTITION_PREALLOC_OUTPUTS=0 sh -c %s"%shlex.quote(inner)
def main():
 if OUT.exists():raise RuntimeError("refusing overwrite")
 OUT.mkdir(parents=True);src=REPO/"desktop_vlm/board/cnn_v10_n1_native_ctypes.py"
 report={"schema":"fz3b-v10.1-seven-opt-candidate-gates-retry-v1","status":"FAILED","boot_id":BOOT,"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),"commands":[],"source":{"path":src.relative_to(REPO).as_posix(),"sha256":sha(src)}}
 c=helper.connect()
 try:
  s=c.open_sftp()
  try:s.put(str(src),REMOTE+"/runtime/cnn_v10_n1_native_ctypes.py.part",confirm=True);s.posix_rename(REMOTE+"/runtime/cnn_v10_n1_native_ctypes.py.part",REMOTE+"/runtime/cnn_v10_n1_native_ctypes.py")
  finally:s.close()
  run(c,"same-boot-fixed-client-preflight","set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; test \"$(sha256sum %s/runtime/cnn_v10_n1_native_ctypes.py|cut -d' ' -f1)\" = %s; test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; test -z \"$(pgrep -f '[o]rt_partition_runner|[b]enchmark_cnn_pipeline_v10_live' || true)\""%(BOOT,REMOTE,sha(src)),report)
  run(c,"release-setup-only-driver-reference","set -eu; cd %s/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -c \"from cnn_pipeline_v10_bundle import load_v10_release_bundle; from cnn_ddr_v10_runtime import LinuxIoctlV10Transport; b=load_v10_release_bundle('%s/release','%s'); t=LinuxIoctlV10Transport(expected_parameter_manifest_words=b['parameter_manifest_words']); print(t.close())\"; test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\""%(REMOTE,BASE,RELEASE),report)
  groups=[("n1-native-only-10-retry1","--n1-manifest %s/n1-selection/selection.json"%REMOTE),("suffix-w8a8-only-10","--suffix-candidate %s/suffix-selection/selection-manifest.json"%REMOTE),("n1-plus-suffix-10","--n1-manifest %s/n1-selection/selection.json --suffix-candidate %s/suffix-selection/selection-manifest.json"%(REMOTE,REMOTE))]
  for label,args in groups:
   reload(c,"reload-before-"+label,report);run(c,"run-"+label,cmd(label,args),report,1800,allow=True)
  s=c.open_sftp()
  try:
   for label,args in groups:
    d=OUT/label;d.mkdir();s.get(REMOTE+"/results/"+label+"/result.json",str(d/"result.json"));report.setdefault("results",{})[label]={"sha256":sha(d/"result.json")}
  finally:s.close()
  for label in report["results"]:
   j=json.loads((OUT/label/"result.json").read_text());report["results"][label].update(status=j.get("status"),fps=j.get("measured",{}).get("fps_including_fill_and_drain"),error=j.get("error"))
  report["status"]="PASS_CANDIDATE_RESULTS_RECORDED"
 finally:
  c.close();report["finished_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z');raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode();(OUT/"receipt.json").write_bytes(raw);print(json.dumps({"status":report["status"],"sha256":hashlib.sha256(raw).hexdigest()}))
if __name__=='__main__':main()
