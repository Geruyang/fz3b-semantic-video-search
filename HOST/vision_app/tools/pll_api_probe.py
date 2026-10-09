"""Read-only generic APLL parameter/mode probe; no CPU owner interruption."""
import datetime
import json
from vision_app.tools.board_link import ROOT,open_link,run

def main():
    client=open_link()
    root='/root/fz3b-vision-console-20261009-001'
    remote=root+'/pll-api-probe'
    report={'read_only':True}
    try:
        run(client,'mkdir -p '+remote)
        report['before']=run(client,root+'/read_clock')
        s=client.open_sftp()
        s.put(str(ROOT/'vision_app/cpu_clock/fz3b_pll_api_probe.c'),remote+'/fz3b_pll_api_probe.c')
        with s.file(remote+'/Makefile','w') as f:f.write('obj-m += fz3b_pll_api_probe.o\n')
        s.close()
        run(client,'LC_ALL=C make -C '+root+'/cpu-clock-build/prepared-headers M='+remote+' ARCH=arm64 modules >'+remote+'/build.log 2>&1; rc=$?; tail -5 '+remote+'/build.log; exit $rc',timeout=180)
        run(client,'insmod '+remote+'/fz3b_pll_api_probe.ko')
        try:report['api']=run(client,'cat /sys/module/fz3b_pll_api_probe/parameters/report')
        finally:run(client,'rmmod fz3b_pll_api_probe')
        report['after']=run(client,root+'/read_clock')
        report['unchanged']=report['before']==report['after']
        if not report['unchanged']:raise RuntimeError('READ-only probe observed clock change')
        print(json.dumps(report,indent=2))
    finally:
        client.close()
        path=ROOT/'artifacts/ps-application-20261009/cpu-clock'/('generic-api-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
