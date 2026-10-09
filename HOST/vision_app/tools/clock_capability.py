"""READ-only firmware PLL mode and real parent topology inventory."""
import datetime
import json
from vision_app.tools.board_link import ROOT,open_link,run

PROGRAM='''import json
from vision_app.cpu_clock_service import request
result={'pll':request('diagnostic'),'clocks':[],'cpu':request()}
for i in range(121):
 value=request('diagnostic',i)
 if value['name']:result['clocks'].append(value)
print(json.dumps(result))
'''

def main():
    client=open_link()
    remote='/root/fz3b-vision-console-20261009-001'
    try:
        s=client.open_sftp()
        with s.file(remote+'/clock_capability.py','w') as handle:handle.write(PROGRAM)
        s.close()
        report=json.loads(run(client,'cd '+remote+'; python3 -B clock_capability.py',timeout=120))
        report['raw']=run(client,remote+'/read_clock')
        path=ROOT/'artifacts/ps-application-20261009/cpu-clock'/('capability-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        selected=[c for c in report['clocks'] if c['name'] in ('apll','acpu','ddr_ref','pl0_ref','pl1_ref','pl2_ref','pl3_ref')]
        print(json.dumps(dict(pll=report['pll'],selected=selected,evidence=str(path)),indent=2))
    finally:client.close()

if __name__=='__main__':main()
