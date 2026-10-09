#!/usr/bin/env python3
"""Qualify the isolated WC driver and compare the selected suffix workload."""
from __future__ import print_function
import datetime, hashlib, json, os, shlex, shutil, sys
from pathlib import Path

REPO=Path(r"E:\AIProject\FPGAVibecoding")
OUT=REPO/"artifacts/board-debug-20261007/acceleration/network/network10-v10.1-wc-live-ab-002"
REMOTE="/root/network10-v10.1-seven-opt-20261007"; BASE="/root/network10-v10.1-board-window"
ASSETS=REMOTE+"/wc-live-assets"; WC_OVERLAY="/sys/kernel/config/device-tree/overlays/network10-v10-wc-experiment"
BASE_OVERLAY="/sys/kernel/config/device-tree/overlays/network10-v10-trace18"
BOOT="fd395d2a-974c-4a1a-827d-568452cd8488"
RELEASE="3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
DEPLOY="531cb46623c760df3c09f56cb285e6dff3320da44c1f3570af3e02e98754ea3d"
FIXTURE_SHA="83df8803b7a8eb08795c6c19d89538637f850df9044c407b90814d725f0079c4"
WC_MANIFEST_SHA="cb9ec8b44eef04276d422690ee3cb00721fd6fbfdd31d475c045862cc27e0239"
KO_SHA="362d2cfcc21fd572592a08eef6c2e26dda1ae98958eb14d8fe3241174f202243"
DTBO_SHA="f7c4443f7eba18d02214138afa2f63062cccfa47dcf15606921f3570ba9e662e"
EXPECTED=("4121608b7bb27060d5babe05dd6ae723d191b4405a0852d55adde876f4ef16b3","7654afe2d025731f18d23268c2109aba3445b2708a8e9ef1a2e49ed84c369adb")
FIXTURE_ROOT=REPO/"artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001"
OFFLINE=REPO/"artifacts/board-debug-20261007/acceleration/host/network10-v10.1-wc-driver-experiment-001"
sys.path.insert(0,str(REPO/"artifacts/board-debug-20261004/acceleration/network"));import dma_driver_rebuild as helper

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def record(path,root):
 p=Path(path);return {"path":p.relative_to(root).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)}
def run(c,n,x,r,t=300,allow=False):
 v=helper.run(c,n,x,t);r["commands"].append(v)
 if v["exit_code"] and not allow:raise RuntimeError("%s failed: %s %s"%(n,v["stdout"],v["stderr"]))
 return v
def mkdirs(s,path):
 cur=""
 for part in path.strip('/').split('/'):
  cur+="/"+part
  try:s.stat(cur)
  except IOError:s.mkdir(cur)
def upload(s,local,remote):
 mkdirs(s,remote.rsplit('/',1)[0]);s.put(str(local),remote+".part",confirm=True);s.posix_rename(remote+".part",remote)
def artifact_relative(raw_path):
 parts=raw_path.replace('\\','/').split('/');i=parts.index('artifacts');return '/'.join(parts[i:])
def fixture_uploads():
 m=json.loads((FIXTURE_ROOT/"manifest.json").read_text());items=[(FIXTURE_ROOT/"manifest.json",ASSETS+"/artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001/manifest.json"),(FIXTURE_ROOT/"receipt.json",ASSETS+"/artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001/receipt.json")]
 links=[]
 for case in m["cases"]:
  prof=case["profile"];dest=ASSETS+"/"+artifact_relative(case["params"]["path"]);links.append((dest,BASE+"/release/params/profile%d.bin"%prof,case["params"]["sha256"]))
  for image in case["images"]:
   for key in ("input","expected"):
    rec=image[key];items.append((Path(rec["path"]),ASSETS+"/"+artifact_relative(rec["path"])))
 return items,links
def reserved_receipt():
 return {"schema":"cnn-pipeline-v10.1-wc-reserved-memory-receipt-v1","status":"PASS_RESERVED_MEMORY_LOW_HIGH_NO_MAP","target":{"kernel_release":"4.14.0-xilinx-v2018.3","device":"/dev/network10_v10_wc_candidate","module":"cnn_ddr_v10_wc_candidate","compatible":"fz3b,cnn-ddr-v10-wc-candidate"},"boot_id":BOOT,"completed_gate":"same_boot_reserved_memory_low_high_no_map_exact_ranges","reserved_ranges":{"low":{"reg":[0x40000000,0x40000000],"no_map":True},"high":{"reg":[0x800000000,0x40000000],"no_map":True}},"system_ram_ranges":[{"start":0,"size":0x40000000},{"start":0x840000000,"size":0x40000000}]}
def write_json(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def benchmark(label,device,qualification=None,deliver=False):
 q=""
 if qualification:q="--wc-qualification {p} --expected-wc-qualification-sha256 {s}".format(p=qualification[0],s=qualification[1])
 inner=("cd {r}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B benchmark_cnn_pipeline_v10_live.py --bundle-root {b}/release --expected-bundle-sha256 {rel} --deployment-manifest {b}/platform/manifest.json --expected-deployment-sha256 {dep} --runner {r}/bin/ort_partition_runner_v3 --ps-client mixed --native-lib {r}/bin/libcnn_v10_native_quant.so --suffix-candidate {r}/suffix-selection/selection-manifest.json --threads 3 --max-in-flight 3 --warmup-pairs 3 --measured-pairs 30 --timeout-s 300 --device {dev} {q} --input-tensor {b}/inputs/image-00-input.f32 --input-tensor {b}/inputs/image-01-input.f32 --expected-feature-sha256 {s0} --expected-feature-sha256 {s1} --reference-feature {r}/references/image-00-feature.f32 --reference-feature {r}/references/image-01-feature.f32 {delivery} --output-dir {r}/results/{label}").format(r=REMOTE,b=BASE,rel=RELEASE,dep=DEPLOY,dev=device,q=q,s0=EXPECTED[0],s1=EXPECTED[1],delivery="--deliver-jsonl --delivery-queue-capacity 4" if deliver else "",label=label)
 return "set -eu; env ORT_PARTITION_ALLOW_SPINNING=0 ORT_PARTITION_PREALLOC_OUTPUTS=0 sh -c %s"%shlex.quote(inner)
def main():
 if OUT.exists():raise RuntimeError("refusing overwrite")
 OUT.mkdir(parents=True);r={"schema":"fz3b-v10.1-wc-live-ab-v1","status":"FAILED","boot_id":BOOT,"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),"commands":[],"results":{}}
 live_src=REPO/"desktop_vlm/board/cnn_v10_wc_live_qualification.py";wc_helper=REPO/"desktop_vlm/board/cnn_pipeline_v10_wc_deployment.py"
 items,links=fixture_uploads();c=helper.connect()
 try:
  run(c,"trace18-and-reserved-preflight","set -eu; test \"$(cat /proc/sys/kernel/random/boot_id)\" = %s; test -e /proc/device-tree/reserved-memory/buffer@0/no-map; test -e /proc/device-tree/reserved-memory/buffer@1/no-map; test \"$(od -An -v -tx1 /proc/device-tree/reserved-memory/buffer@0/reg|tr -d ' \\n')\" = 00000000400000000000000040000000; test \"$(od -An -v -tx1 /proc/device-tree/reserved-memory/buffer@1/reg|tr -d ' \\n')\" = 00000008000000000000000040000000; grep -Fqx '00000000-3fffffff : System RAM' /proc/iomem; grep -Fqx '840000000-87fffffff : System RAM' /proc/iomem; if test -d /sys/module/cnn_ddr_v10_wc_candidate; then grep -qx applied %s/status; test ! -d /sys/module/cnn_ddr_v10_candidate; test -c /dev/network10_v10_wc_candidate; test -z \"$(fuser /dev/network10_v10_wc_candidate 2>/dev/null || true)\"; elif test -d /sys/module/cnn_ddr_v10_candidate; then grep -qx applied %s/status; test \"$(cat /sys/module/cnn_ddr_v10_candidate/refcnt)\" = 0; test -z \"$(fuser /dev/network10_v10 2>/dev/null || true)\"; else exit 1; fi"%(BOOT,WC_OVERLAY,BASE_OVERLAY),r)
  s=c.open_sftp()
  try:
   upload(s,live_src,REMOTE+"/runtime/"+live_src.name);upload(s,wc_helper,REMOTE+"/runtime/"+wc_helper.name)
   for local,remote in items:upload(s,local,remote)
  finally:s.close()
  for dest,src,digest in links:
   run(c,"link-fixture-param-"+Path(dest).stem,"set -eu; mkdir -p %s; ln -sfn %s %s; test \"$(sha256sum %s|cut -d' ' -f1)\" = %s"%(shlex.quote(dest.rsplit('/',1)[0]),shlex.quote(src),shlex.quote(dest),shlex.quote(dest),digest),r)
  run(c,"prepare-wc-driver","set -eu; if test -d /sys/module/cnn_ddr_v10_wc_candidate; then grep -qx applied %s/status; test -c /dev/network10_v10_wc_candidate; test -z \"$(fuser /dev/network10_v10_wc_candidate 2>/dev/null || true)\"; else /sbin/rmmod cnn_ddr_v10_candidate; test ! -e /dev/network10_v10; rmdir %s; test ! -e %s; mkdir %s; cat %s/wc-package/platform/network10_v10_overlay_wc_experiment.dtbo > %s/dtbo; grep -qx applied %s/status; /sbin/insmod %s/wc-package/driver/cnn_ddr_v10_wc_candidate.ko; test -c /dev/network10_v10_wc_candidate; fi; test \"$(sha256sum %s/wc-package/driver/cnn_ddr_v10_wc_candidate.ko|cut -d' ' -f1)\" = %s"%(WC_OVERLAY,BASE_OVERLAY,BASE_OVERLAY,WC_OVERLAY,REMOTE,WC_OVERLAY,WC_OVERLAY,REMOTE,REMOTE,KO_SHA),r)
  fixture_remote=ASSETS+"/artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001"
  live_remote=REMOTE+"/results/wc-live-test-receipt.json"
  cmd=("set -eu; cd {r}/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B cnn_v10_wc_live_qualification.py --bundle-root {b}/release --expected-bundle-sha256 {rel} --fixture-root {f} --expected-fixture-manifest-sha256 {fs} --asset-root {a} --driver-module {r}/wc-package/driver/cnn_ddr_v10_wc_candidate.ko --expected-driver-module-sha256 {ko} --dtbo {r}/wc-package/platform/network10_v10_overlay_wc_experiment.dtbo --expected-dtbo-sha256 {dtbo} --device /dev/network10_v10_wc_candidate --output-receipt {out}").format(r=REMOTE,b=BASE,rel=RELEASE,f=fixture_remote,fs=FIXTURE_SHA,a=ASSETS,ko=KO_SHA,dtbo=DTBO_SHA,out=live_remote)
  run(c,"wc-live-qualification",cmd,r,1800)
  run(c,"wc-post-live-rmmod-proof","set -eu; test \"$(cat /sys/module/cnn_ddr_v10_wc_candidate/refcnt)\" = 0; test -z \"$(fuser /dev/network10_v10_wc_candidate 2>/dev/null || true)\"; /sbin/rmmod cnn_ddr_v10_wc_candidate; test ! -e /dev/network10_v10_wc_candidate; test ! -e /sys/module/cnn_ddr_v10_wc_candidate",r)
  s=c.open_sftp()
  try:s.get(live_remote,str(OUT/"live-test-receipt.json"));s.get(live_remote.replace('.json','.details.json'),str(OUT/"live-test-receipt.details.json"))
  finally:s.close()
  live=json.loads((OUT/"live-test-receipt.json").read_text());
  if live["status"]!="PASS_WC_LIVE_TRANSFER_AND_FUNCTIONAL_GATES":raise RuntimeError("WC live receipt failed")
  write_json(OUT/"reserved-memory-receipt.json",reserved_receipt())
  qual=OUT/"qualification";shutil.copytree(OFFLINE,qual/"offline")
  shutil.copy2(OUT/"live-test-receipt.json",qual/"receipts/live-test-receipt.json");shutil.copy2(OUT/"reserved-memory-receipt.json",qual/"receipts/reserved-memory-receipt.json")
  q={"schema":"cnn-pipeline-v10.1-wc-driver-qualification-v1","status":"PASS_BOARD_QUALIFIED","target":live["target"],"boot_id":BOOT,"offline_manifest":record(qual/"offline/manifest.json",qual),"files":{"driver_module":record(qual/"offline/driver/cnn_ddr_v10_wc_candidate.ko",qual),"overlay_dtbo":record(qual/"offline/platform/network10_v10_overlay_wc_experiment.dtbo",qual),"live_test_receipt":record(qual/"receipts/live-test-receipt.json",qual),"reserved_memory_receipt":record(qual/"receipts/reserved-memory-receipt.json",qual)}};write_json(qual/"qualification.json",q);qsha=sha(qual/"qualification.json")
  s=c.open_sftp()
  try:
   for p in qual.rglob('*'):
    if p.is_file():upload(s,p,REMOTE+"/wc-qualification/"+p.relative_to(qual).as_posix())
  finally:s.close()
  qremote=REMOTE+"/wc-qualification/qualification.json"
  run(c,"target-qualification-loader","set -eu; cd %s/runtime; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -c \"from cnn_pipeline_v10_wc_deployment import load_v10_wc_qualification as l;q=l('%s','%s','%s/platform/manifest.json','%s','%s');assert q['live_gates_completed'] and q['target']['device']=='/dev/network10_v10_wc_candidate';print('WC_QUALIFICATION_PASS',q['manifest_sha256'])\""%(REMOTE,qremote,qsha,BASE,DEPLOY,RELEASE),r)
  run(c,"reload-wc-for-performance","set -eu; /sbin/insmod %s/wc-package/driver/cnn_ddr_v10_wc_candidate.ko; test -c /dev/network10_v10_wc_candidate"%REMOTE,r)
  run(c,"run-wc-suffix30",benchmark("wc-suffix-w8a8-30","/dev/network10_v10_wc_candidate",(qremote,qsha),False),r,3600)
  s=c.open_sftp()
  try:s.get(REMOTE+"/results/wc-suffix-w8a8-30/result.json",str(OUT/"wc-suffix-w8a8-30-result.json"))
  finally:s.close()
  wc=json.loads((OUT/"wc-suffix-w8a8-30-result.json").read_text());wcfps=wc["measured"]["fps_including_fill_and_drain"]
  if wc["status"]!="ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN":raise RuntimeError("WC suffix30 gate failed")
  # The final delivery run uses whichever driver won the no-sink same-window comparison.
  basefps=2.7647195438974035
  selected="wc" if wcfps>basefps else "base"
  if selected=="wc":
   run(c,"reload-selected-wc","set -eu; /sbin/rmmod cnn_ddr_v10_wc_candidate; /sbin/insmod %s/wc-package/driver/cnn_ddr_v10_wc_candidate.ko"%REMOTE,r);dev="/dev/network10_v10_wc_candidate";qualarg=(qremote,qsha)
  else:
   run(c,"switch-wc-to-base","set -eu; /sbin/rmmod cnn_ddr_v10_wc_candidate; rmdir %s; mkdir %s; cat %s/platform/platform/network10_v10_trace18.dtbo > %s/dtbo; grep -qx applied %s/status; /sbin/insmod %s/driver/cnn_ddr_v10_candidate.ko"%(WC_OVERLAY,BASE_OVERLAY,BASE,BASE_OVERLAY,BASE_OVERLAY,BASE),r);dev="/dev/network10_v10";qualarg=None
  label="selected-%s-suffix-w8a8-jsonl-30"%selected
  run(c,"run-selected-jsonl30",benchmark(label,dev,qualarg,True),r,3600)
  s=c.open_sftp()
  try:
   s.get(REMOTE+"/results/"+label+"/result.json",str(OUT/(label+"-result.json")));s.get(REMOTE+"/results/"+label+"/measured-live.jsonl",str(OUT/(label+"-measured-live.jsonl")))
  finally:s.close()
  delivery=json.loads((OUT/(label+"-result.json")).read_text())
  if delivery["status"]!="ENGINEERING_FEATURE_REGRESSION_PROTOCOL_CLEAN":raise RuntimeError("selected JSONL gate failed")
  r["qualification"]={"path":"qualification/qualification.json","sha256":qsha,"live_receipt_sha256":sha(OUT/"live-test-receipt.json"),"details_sha256":sha(OUT/"live-test-receipt.details.json")};r["results"]={"base_suffix_no_sink_fps":basefps,"wc_suffix_no_sink":{"sha256":sha(OUT/"wc-suffix-w8a8-30-result.json"),"fps":wcfps,"status":wc["status"]},"selected":selected,"selected_jsonl":{"sha256":sha(OUT/(label+"-result.json")),"jsonl_sha256":sha(OUT/(label+"-measured-live.jsonl")),"fps":delivery["measured"]["fps_including_fill_and_drain"],"status":delivery["status"]}};r["status"]="PASS_WC_QUALIFIED_AB_AND_SELECTED_DELIVERY"
 finally:
  c.close();r["finished_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z');raw=(json.dumps(r,indent=2,sort_keys=True)+'\n').encode();(OUT/"receipt.json").write_bytes(raw);print(json.dumps({"status":r["status"],"sha256":hashlib.sha256(raw).hexdigest()}))
if __name__=='__main__':main()
