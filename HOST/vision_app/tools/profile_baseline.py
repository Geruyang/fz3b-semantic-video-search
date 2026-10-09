"""A matched real-camera baseline at raw-verified original 1.0667GHz."""
import datetime
import json
import subprocess
import sys
from vision_app.tools.board_link import ROOT, open_link, run

def main():
    remote='/root/fz3b-vision-console-20261009-001'
    client=open_link()
    record={'ok':False,'default_changed':False,'pl_changed':False}
    try:
        run(client,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(client,'systemctl stop fz3b-app-cpu-clock.service')
        record['baseline_raw']=run(client,remote+'/read_clock')
        if '0xFD1A0060 0x03000100' not in record['baseline_raw']:raise RuntimeError('baseline raw not restored')
        s=client.open_sftp()
        s.put(str(ROOT/'vision_app/diagnostic_baseline.py'),remote+'/vision_app/diagnostic_baseline.py')
        s.close()
        run(client,'systemd-run --unit=fz3b-vision-profile-baseline --property=WorkingDirectory='+remote+' --property=TimeoutStopSec=360 --property=SendSIGKILL=no --setenv=LD_LIBRARY_PATH=/root/board-debug-runtime-20261004/runtime/onnxruntime-linux-aarch64-1.16.3/lib /usr/bin/python3 -B -m vision_app.diagnostic_baseline')
        subprocess.run([sys.executable,'-m','vision_app.tools.live_smoke','--seconds','75'],cwd=str(ROOT),check=True)
        record['ok']=True
    finally:
        try:
            run(client,'systemctl stop fz3b-vision-profile-baseline.service',timeout=370)
            record['restored_raw']=run(client,remote+'/read_clock')
        finally:
            run(client,'systemctl start fz3b-app-cpu-clock.service; systemctl start fz3b-vision-console.service')
            record['default_after']=json.loads(run(client,'cd '+remote+'; python3 -B -m vision_app.cpu_clock_service --status'))
            client.close()
            path=ROOT/'artifacts/ps-application-20261009'/('profile-baseline-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
            path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
