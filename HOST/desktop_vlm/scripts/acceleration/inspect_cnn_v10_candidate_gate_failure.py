#!/usr/bin/env python3
from __future__ import print_function
import datetime, hashlib, json, sys
from pathlib import Path
REPO=Path(r"E:\AIProject\FPGAVibecoding")
OUT=REPO/"artifacts/board-debug-20261007/acceleration/network/network10-v10.1-seven-opt-candidate-gates-recovery-001"
REMOTE="/root/network10-v10.1-seven-opt-20261007"
sys.path.insert(0,str(REPO/"artifacts/board-debug-20261004/acceleration/network"))
import dma_driver_rebuild as helper
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    report={"schema":"fz3b-v10.1-candidate-gate-failure-inspection-v1","commands":[],"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')}
    client=helper.connect()
    try:
        command=("set +e; echo BOOT=$(cat /proc/sys/kernel/random/boot_id); "
                 "echo REFCNT=$(cat /sys/module/cnn_ddr_v10_candidate/refcnt 2>/dev/null); "
                 "echo FUSER=$(fuser /dev/network10_v10 2>/dev/null); "
                 "ps -eo pid,ppid,state,comm,args | grep -E 'benchmark_cnn_pipeline_v10_live|ort_partition_runner' | grep -v grep; "
                 "test -f %s/results/n1-native-only-10/result.json; echo RESULT_EXISTS=$?"%REMOTE)
        result=helper.run(client,"inspect-after-n1-failure",command,60);report["commands"].append(result)
        sftp=client.open_sftp()
        try:sftp.get(REMOTE+"/results/n1-native-only-10/result.json",str(OUT/"n1-result.json"))
        finally:sftp.close()
        report["n1_result_sha256"]=hashlib.sha256((OUT/"n1-result.json").read_bytes()).hexdigest()
        report["status"]="INSPECTED_NO_MUTATION"
    finally:
        client.close();report["finished_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
        raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode();(OUT/"receipt.json").write_bytes(raw);print(hashlib.sha256(raw).hexdigest())
if __name__=='__main__':main()
