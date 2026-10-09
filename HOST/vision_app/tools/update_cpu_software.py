"""Promote reviewed CPU close verification and app statistics after exact drain."""
import datetime
import json
from vision_app.tools.board_link import ROOT, open_link, run

def main():
    remote='/root/fz3b-vision-console-20261009-001'
    client=open_link()
    report={'ok':False}
    try:
        run(client,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(client,'systemctl stop fz3b-app-cpu-clock.service')
        run(client,'if fuser /dev/network10_v10_signed40 /dev/fz3b_cpu_clock; then exit 17; fi')
        report['restored_raw']=run(client,remote+'/read_clock')
        if '0xFD1A0060 0x03000100' not in report['restored_raw']:raise RuntimeError('CPU close restoration failed')
        s=client.open_sftp()
        try:
            for name in ('cpu_clock_service.py','board_agent.py','camera.py','prefetch.py'):
                run(client,'cp -p '+remote+'/vision_app/'+name+' '+remote+'/vision_app/'+name+'.before-close-verification')
                s.put(str(ROOT/'vision_app'/name),remote+'/vision_app/'+name)
        finally:s.close()
        run(client,'systemctl start fz3b-app-cpu-clock.service')
        # Exercise the new daemon's independent close/restoration verification.
        run(client,'systemctl stop fz3b-app-cpu-clock.service')
        report['new_daemon_restored_raw']=run(client,remote+'/read_clock')
        if report['new_daemon_restored_raw']!=report['restored_raw']:raise RuntimeError('CPU close not exact')
        run(client,'systemctl start fz3b-app-cpu-clock.service; systemctl start fz3b-vision-console.service')
        report['clock']=json.loads(run(client,'cd '+remote+'; python3 -B -m vision_app.cpu_clock_service --status'))
        report['ok']=report['clock']['verified'] and report['clock']['actual_hz']==1199999988
        print(json.dumps(report,indent=2))
    finally:
        client.close()
        path=ROOT/'artifacts/ps-application-20261009/cpu-clock'/('close-verification-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
