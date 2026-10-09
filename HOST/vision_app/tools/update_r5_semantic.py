"""Promote semantic R5 workers and native score readback with exact rollback."""
import datetime
import hashlib
import json
from vision_app.tools.board_link import ROOT,open_link,run
REMOTE='/root/fz3b-vision-console-20261009-001'

def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    c=open_link();report={'ok':False};backup=REMOTE+'/semantic-r5-backup-'+stamp
    paths=['/lib/firmware/fz3b-app-r50.elf','/lib/firmware/fz3b-app-r51.elf',REMOTE+'/vision_app/libr5_tcm_io.so',REMOTE+'/vision_app/r5_bridge.py',REMOTE+'/r5-boot-manifest.json']
    drained=False;promoted=False
    try:
        s=c.open_sftp();s.put(str(ROOT/'vision_app/r5/tcm_io.c'),REMOTE+'/semantic_tcm_io.c');s.close()
        run(c,'gcc -O2 -Wall -Wextra -Werror -fPIC -shared '+REMOTE+'/semantic_tcm_io.c -o '+REMOTE+'/semantic_tcm_io.so')
        run(c,'mkdir -m700 '+backup)
        for i,path in enumerate(paths):run(c,'cp -p '+path+' '+backup+'/file-%d'%i)
        run(c,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(c,'if fuser /dev/network10_v10_signed40; then exit 17; fi')
        run(c,'systemctl stop fz3b-app-cpu-clock.service fz3b-app-r5.service')
        if run(c,'cat /sys/class/remoteproc/remoteproc0/state /sys/class/remoteproc/remoteproc1/state').splitlines()!=['offline','offline']:raise RuntimeError('R5 stop not verified')
        drained=True;promoted=True
        s=c.open_sftp()
        try:
            manifest=json.loads(s.file(paths[4]).read().decode())
            for core in (0,1):s.put(str(ROOT/'artifacts/ps-application-20261009/r5'/('fz3b-app-r5%d.elf'%core)),paths[core])
            s.put(str(ROOT/'vision_app/r5_bridge.py'),paths[3])
        finally:s.close()
        run(c,'cp -p '+REMOTE+'/semantic_tcm_io.so '+paths[2])
        for item in manifest['files']:
            if item['path'] in paths[:3]:item['sha256']=run(c,'sha256sum '+item['path']).split()[0]
        s=c.open_sftp()
        try:
            with s.file(paths[4],'w') as f:f.write(json.dumps(manifest,indent=2))
        finally:s.close()
        run(c,'systemctl start fz3b-app-r5.service')
        report['ready']=json.loads(run(c,'cat /run/fz3b-r5-ready.json'));assert report['ready']['ok']
        # Compare actual R5 integer scores against CPU full precision.
        program='''import json,numpy as np
from vision_app.r5_bridge import R5Bridge
from vision_app.state import normalized
r=R5Bridge();rng=np.random.RandomState(123);q=normalized(rng.normal(size=(16,512)))
items=[dict(id=str(i),label=str(i),text=str(i)) for i in range(16)]
errors=[]
try:
 for i in range(20):
  x=normalized(rng.normal(size=(1,512)))[0];exact=q.dot(x)
  result=r.match(x,.02,(items,q,1,{'contract_id':'test'}))
  scores=np.asarray([next(v['score'] for v in result['ranking'] if v['id']==str(j)) for j in range(16)])
  errors.append(float(np.max(np.abs(scores-exact))))
  assert np.max(np.abs(scores-exact))<.0015
  assert {v['id'] for v in result['ranking'] if v['score']>=.02}=={str(j) for j in range(16) if exact[j]>=.02}
 r.request(0,12,0);r.request(0,13,0);r.request(0,14,1)
 print(json.dumps(dict(ok=True,max_error=max(errors),frames=20,status=r.status())))
finally:r.close()
'''
        s=c.open_sftp()
        try:
            with s.file(REMOTE+'/semantic_r5_check.py','w') as f:f.write(program)
        finally:s.close()
        report['semantic_test']=json.loads(run(c,'cd '+REMOTE+'; python3 -B semantic_r5_check.py'))
        assert report['semantic_test']['ok'];report['ok']=True
    except BaseException as exc:
        report['error']=str(exc)
        if drained and promoted:
            run(c,'systemctl stop fz3b-app-r5.service')
            if run(c,'cat /sys/class/remoteproc/remoteproc0/state /sys/class/remoteproc/remoteproc1/state').splitlines()!=['offline','offline']:raise RuntimeError('R5 rollback stop not verified')
            for i,path in enumerate(paths):run(c,'cp -p '+backup+'/file-%d '%i+path)
            run(c,'systemctl start fz3b-app-r5.service');report['rollback']=json.loads(run(c,'cat /run/fz3b-r5-ready.json'))
        raise
    finally:
        if report['ok'] or report.get('rollback',{}).get('ok'):run(c,'systemctl start fz3b-app-cpu-clock.service fz3b-vision-console.service')
        report['backup']=backup
        target=ROOT/'artifacts/semantic-video-20261009';target.mkdir(exist_ok=True)
        (target/('r5-'+stamp+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');c.close()
    print(json.dumps(report['semantic_test']))

if __name__=='__main__':main()
