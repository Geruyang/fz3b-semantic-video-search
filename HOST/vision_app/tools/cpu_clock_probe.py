"""Short reversible CPU PM cycle; no application/model/PL changes."""
import datetime
import json
from vision_app.tools.board_link import ROOT, open_link, run

REMOTE='/root/fz3b-vision-console-20261009-001'
PROBE='''import json, time
from vision_app.cpu_clock_service import Lease
def raw():
 import subprocess
 return subprocess.check_output(['./read_clock']).decode()
report={'raw_before':raw()}
lease=Lease()
try:
 report['initial']=lease.status()
 report['steps']=[]
 for khz in (1199999,599999,399999,299999,1199999):
  state=lease.set(khz)
  report['steps'].append(dict(khz=khz,state=state,raw=raw()))
  time.sleep(.2)
finally:lease.close()
report['raw_after']=raw()
report['restored_exactly']=report['raw_before']==report['raw_after']
if not report['restored_exactly']:raise RuntimeError('CPU baseline restoration failed')
print(json.dumps(report))
'''

def main():
    raise RuntimeError('Historical 300/400MHz probe disabled; current range is 600-1200MHz. Use cpu_api_acceptance or the private fine_clock_probe qualification.')
    client=open_link()
    try:
        run(client,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(client,'if fuser /dev/network10_v10_signed40; then exit 17; fi')
        s=client.open_sftp()
        s.put(str(ROOT/'vision_app/cpu_clock_service.py'),REMOTE+'/vision_app/cpu_clock_service.py')
        source=(ROOT/'releases/current/ps/tools/clock-raw-reader/read_fz3b_clock_registers.c').read_text()
        source=source.replace('{UINT64_C(0xFF5E00C0), "CRL_APB.PL0_REF_CTRL"},',
          '{UINT64_C(0xFF5E00C0), "CRL_APB.PL0_REF_CTRL"},\n'+
          '\n'.join('{UINT64_C(0x%08X), "CRL_APB.PL%d_REF_CTRL"},'%(0xFF5E00C0+4*i,i) for i in (1,2,3)))
        with s.file(REMOTE+'/read_clock.c','w') as f:f.write(source)
        with s.file(REMOTE+'/cpu_clock_probe.py','w') as f:f.write(PROBE)
        s.close()
        exports=run(client,"grep -E ' (zynqmp_pm_get_eemi_ops|clk_get_parent|clk_get_rate|of_clk_get_from_provider|__clk_get_name)$' /proc/kallsyms || true")
        print(exports,flush=True)
        run(client,'gcc -O2 -Wall -Wextra -Werror '+REMOTE+'/read_clock.c -o '+REMOTE+'/read_clock')
        run(client,'insmod '+REMOTE+'/cpu-clock/fz3b_cpu_clock.ko')
        report=json.loads(run(client,'cd '+REMOTE+'; python3 -B cpu_clock_probe.py'))
        report['exports']=exports
        report['module_logs']=run(client,'dmesg | tail -15')
        path=ROOT/'artifacts/ps-application-20261009/cpu-clock'/('probe-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        run(client,'systemctl start fz3b-vision-console.service')
        client.close()

if __name__=='__main__':main()
