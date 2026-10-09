"""Private reversible fine-clock cycle; installed CPU service stays unchanged."""
import datetime
import json
from vision_app.tools.board_link import ROOT,open_link,run
REMOTE='/root/fz3b-vision-console-20261009-001'

def reader_source():
    source=(ROOT/'releases/current/ps/tools/clock-raw-reader/read_fz3b_clock_registers.c').read_text()
    source=source.replace('{UINT64_C(0xFD1A0020), "CRF_APB.APLL_CTRL"},',
        '{UINT64_C(0xFD1A0020), "CRF_APB.APLL_CTRL"},\n'+
        '{UINT64_C(0xFD1A0024), "CRF_APB.APLL_CFG"},\n'+
        '{UINT64_C(0xFD1A0028), "CRF_APB.APLL_FRAC_CFG"},')
    source=source.replace('{UINT64_C(0xFF5E00C0), "CRL_APB.PL0_REF_CTRL"},',
        '{UINT64_C(0xFF5E00C0), "CRL_APB.PL0_REF_CTRL"},\n'+
        '\n'.join('{UINT64_C(0x%08X), "CRL_APB.PL%d_REF_CTRL"},'%(0xFF5E00C0+4*i,i) for i in (1,2,3)))
    source=source.replace('{UINT64_C(0xFD1A0038), "CRF_APB.VPLL_CTRL"},',
        '{UINT64_C(0xFD1A0038), "CRF_APB.VPLL_CTRL"},\n'+
        '{UINT64_C(0xFD1A003C), "CRF_APB.VPLL_CFG"},\n'+
        '{UINT64_C(0xFD1A0040), "CRF_APB.VPLL_FRAC_CFG"},')
    return source

PROGRAM='''import json,subprocess,time
from vision_app.fine_clock_probe_service import Lease
class FineLease(Lease):
 def read_raw(self):return subprocess.check_output(['./read_clock_fine']).decode('ascii')
def raw():return subprocess.check_output(['./read_clock_fine']).decode('ascii')
def protected(value):
 lines=[]
 for s in value.splitlines():
  if 'VPLL_' in s or 'ACPU_CTRL' in s:continue
  if 'PLL_STATUS' in s:
   parts=s.split();parts[1]='0x%08X'%(int(parts[1],16)&~0x24);s=' '.join(parts)
  lines.append(s)
 return lines
report={'raw_before':raw(),'steps':[],'ok':False}
lease=None
try:
 lease=FineLease()
 report['initial']=lease.status()
 report['topology']=[lease.diagnostic(i) for i in range(151)]
 for khz in (1200000,800000,600000,1000000,1200000,800000,1000000,600000,1200000):
  at=time.monotonic();state=lease.set(khz);value=raw()
  assert protected(value)==protected(report['raw_before']), 'protected branch changed'
  report['steps'].append(dict(khz=khz,state=state,raw=value,elapsed_ms=(time.monotonic()-at)*1000))
  time.sleep(.05)
 report['ok']=True
except BaseException as exc:report['error']=type(exc).__name__+': '+str(exc)
finally:
 if lease:
  try:lease.close()
  except BaseException as exc:report['ok']=False;report['close_error']=str(exc)
 report['raw_after']=raw()
 report['restored_exactly']=report['raw_after']==report['raw_before']
 report['ok']=report['ok'] and report['restored_exactly']
print(json.dumps(report))
'''

def main():
    client=open_link();record={'ok':False,'pl_changed':False}
    path=ROOT/'artifacts/ps-application-20261009/cpu-clock'/('fine-probe-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    try:
        s=client.open_sftp()
        try:
            s.put(str(ROOT/'vision_app/cpu_clock_service.py'),REMOTE+'/vision_app/fine_clock_probe_service.py')
            s.put(str(ROOT/'vision_app/frequency.py'),REMOTE+'/vision_app/frequency.py')
            for filename,data in [('read_clock_fine.c',reader_source()),('fine_probe.py',PROGRAM)]:
                with s.file(REMOTE+'/'+filename,'w') as handle:handle.write(data)
        finally:s.close()
        run(client,'gcc -O2 -Wall -Wextra -Werror '+REMOTE+'/read_clock_fine.c -o '+REMOTE+'/read_clock_fine')
        run(client,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(client,'if fuser /dev/network10_v10_signed40; then exit 17; fi')
        run(client,'systemctl stop fz3b-app-cpu-clock.service')
        record['baseline']=run(client,REMOTE+'/read_clock_fine')
        run(client,'rmmod fz3b_cpu_clock')
        run(client,'insmod '+REMOTE+'/cpu-clock-build/fz3b_cpu_clock.ko')
        record.update(json.loads(run(client,'cd '+REMOTE+'; python3 -B fine_probe.py',timeout=120)))
        record['logs']=run(client,'dmesg | tail -25')
        if not record.get('restored_exactly'):raise RuntimeError('fine clock restoration failed; refusing unload')
        run(client,'rmmod fz3b_cpu_clock')
        run(client,'systemctl start fz3b-app-cpu-clock.service fz3b-vision-console.service')
        record['production_restored']=run(client,'systemctl is-active fz3b-app-cpu-clock.service fz3b-vision-console.service').splitlines()==['active','active']
        if not record['ok']:raise RuntimeError(record.get('error','fine clock probe failed'))
        print(json.dumps(dict(ok=True,steps=len(record['steps']),restored_exactly=True,path=str(path))))
    except BaseException as exc:
        record['tool_error']=str(exc)
        raise
    finally:
        path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');client.close()

if __name__=='__main__':main()
