"""Fresh TCM firmware load after normal application/CPU/R5 service drain."""
import datetime
import hashlib
import json
from vision_app.tools.board_link import ROOT,open_link,run
REMOTE='/root/fz3b-vision-console-20261009-001'

def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    client=open_link();record={'ok':False,'pl_changed':False,'rollback_errors':[],'startup_errors':[]}
    backup=REMOTE+'/r5-frequency-backup-'+stamp
    record['backup']=backup
    files=['/lib/firmware/fz3b-app-r50.elf','/lib/firmware/fz3b-app-r51.elf',REMOTE+'/r5-boot-manifest.json']
    backup_complete=drained=promoted=qualified=False
    prior=[]
    def offline():
        if run(client,'cat /sys/class/remoteproc/remoteproc0/state /sys/class/remoteproc/remoteproc1/state').splitlines()!=['offline','offline']:
            raise RuntimeError('both R5 cores must be offline')
    def start_qualified():
        run(client,'systemctl start fz3b-app-r5.service')
        ready=json.loads(run(client,'cat /run/fz3b-r5-ready.json'))
        if not ready['ok']:raise RuntimeError('R5 qualification failed')
        return ready
    try:
        prior=[unit for unit in ('fz3b-app-cpu-clock.service','fz3b-vision-console.service')
               if run(client,'systemctl is-active '+unit+' || true').strip()=='active']
        run(client,'mkdir -m700 '+backup)
        for i,path in enumerate(files):run(client,'cp -p '+path+' '+backup+'/file-%d'%i)
        backup_complete=True
        run(client,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(client,'systemctl stop fz3b-app-cpu-clock.service')
        run(client,'systemctl stop fz3b-app-r5.service')
        offline();drained=True
        s=client.open_sftp()
        try:
            with s.file(files[2]) as handle:manifest=json.loads(handle.read().decode())
            promoted=True
            for core in (0,1):
                name='fz3b-app-r5%d.elf'%core;local=ROOT/'artifacts/ps-application-20261009/r5'/name
                s.put(str(local),'/lib/firmware/'+name)
                for item in manifest['files']:
                    if item['path']=='/lib/firmware/'+name:item['sha256']=hashlib.sha256(local.read_bytes()).hexdigest()
            with s.file(files[2],'w') as handle:handle.write(json.dumps(manifest,indent=2))
        finally:s.close()
        record['boot_ready']=start_qualified();qualified=True
        program='''from vision_app.r5_bridge import R5Bridge
r=R5Bridge()
try:
 assert all(r.request(0,10,k)==1 for k in (600000,800000,1000000,1200000,599999,1199999))
 for k in (601000,799000,1199000):
  try:r.request(0,10,k)
  except ValueError:pass
  else:raise AssertionError('invalid frequency accepted')
finally:r.close()
print('PASS')
'''
        s=client.open_sftp()
        try:
            with s.file(REMOTE+'/r5_four_check.py','w') as handle:handle.write(program)
        finally:s.close()
        record['commands']=run(client,'cd '+REMOTE+'; python3 -B r5_four_check.py').strip()
        record['manifest']=manifest
        record['ok']=record['commands']=='PASS' and record['boot_ready']['ok']
    except BaseException as exc:
        record['error']=str(exc)
        qualified=False
        if backup_complete and drained:
            try:
                # Only restore files after both cores stop; no forced teardown.
                run(client,'systemctl stop fz3b-app-r5.service');offline()
                if promoted:
                    for i,path in enumerate(files):run(client,'cp -p '+backup+'/file-%d '%i+path)
                record['rollback_ready']=start_qualified();qualified=True
            except BaseException as error:
                record['rollback_errors'].append(str(error))
                record['rollback_blocked']='R5 restoration/qualification not proven; CPU/app kept stopped'
        elif backup_complete:
            record['rollback_blocked']='owner drain not proven; no firmware change or restart attempted'
    finally:
        if qualified:
            for unit in prior:
                try:run(client,'systemctl start '+unit)
                except BaseException as error:record['startup_errors'].append(str(error));record['ok']=False
        try:client.close()
        finally:
            (ROOT/'artifacts/ps-application-20261009/r5'/('frequency-'+stamp+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    if not record['ok']:raise RuntimeError(record.get('error') or str(record['startup_errors']))
    print(json.dumps(dict(ok=True,backup=backup)))

if __name__=='__main__':main()
