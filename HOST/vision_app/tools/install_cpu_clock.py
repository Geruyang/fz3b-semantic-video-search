"""Board-only CPU service installation with exact application file rollback."""
import datetime
import hashlib
import json
import shlex
from vision_app.boot_units import application_unit, cpu_unit
from vision_app.tools.board_link import ROOT, open_link, run
from vision_app.tools.fine_clock_probe import reader_source

REMOTE='/root/fz3b-vision-console-20261009-001'
UNIT='fz3b-app-cpu-clock.service'

def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=REMOTE+'/cpu-install-backup-'+stamp
    files=[REMOTE+'/config.json', '/etc/systemd/system/fz3b-vision-console.service',
           '/etc/systemd/system/'+UNIT, REMOTE+'/cpu-clock/fz3b_cpu_clock.ko',
           REMOTE+'/cpu-clock/fz3b_cpu_clock.ko.sha256']
    files += [REMOTE+'/vision_app/'+name for name in ('cpu_clock_service.py','board_agent.py','camera.py','boot_units.py','frequency.py')]
    files += [REMOTE+'/read_clock',REMOTE+'/read_clock.c']
    record={'ok':False,'files':[],'pl_changed':False,'backup':backup}
    client=open_link()
    try:
        record['before_raw']=run(client,REMOTE+'/read_clock')
        record['cpu_unit_before']={key:run(client,'systemctl is-'+key+' '+UNIT+' || true').strip() for key in ('active','enabled')}
        run(client,'mkdir -m 700 '+backup)
        s=client.open_sftp()
        try:
            for i,path in enumerate(files):
                try:s.stat(path);exists=True
                except IOError as exc:
                    if exc.errno!=2:raise
                    exists=False
                saved=backup+'/file-%d'%i
                if exists:run(client,'cp -p -- '+shlex.quote(path)+' '+saved)
                record['files'].append(dict(path=path,saved=saved,exists=exists))
            config=json.loads(s.file(REMOTE+'/config.json').read().decode())
        finally:s.close()
        run(client,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(client,'if fuser /dev/network10_v10_signed40; then exit 17; fi')
        run(client,'if systemctl is-active --quiet '+UNIT+'; then systemctl stop '+UNIT+'; fi')
        run(client,'if test -e /dev/fz3b_cpu_clock; then rmmod fz3b_cpu_clock; fi')
        record['baseline_full']=run(client,REMOTE+'/read_clock_fine')
        s=client.open_sftp()
        try:
            for name in ('cpu_clock_service.py','board_agent.py','camera.py','boot_units.py','frequency.py'):
                s.put(str(ROOT/'vision_app'/name),REMOTE+'/vision_app/'+name)
            with s.file(REMOTE+'/read_clock.c','w') as f:f.write(reader_source())
            module=ROOT/'artifacts/ps-application-20261009/cpu-clock/fz3b_cpu_clock.ko'
            s.put(str(module),REMOTE+'/cpu-clock/fz3b_cpu_clock.ko')
            config.update(cpu_control_socket='/run/fz3b-cpu-clock/control.sock',default_cpu_khz=1199999)
            for path,data,mode in (
              (REMOTE+'/cpu-clock/fz3b_cpu_clock.ko.sha256',hashlib.sha256(module.read_bytes()).hexdigest()+'\n',0o600),
              (REMOTE+'/config.json',json.dumps(config),0o600),
              ('/etc/systemd/system/'+UNIT,cpu_unit(REMOTE),0o644),
              ('/etc/systemd/system/fz3b-vision-console.service',application_unit(REMOTE,boot=True,cpu_clock=True),0o644)):
                with s.file(path,'w') as f:f.write(data)
                s.chmod(path,mode)
        finally:s.close()
        run(client,'gcc -O2 -Wall -Wextra -Werror '+REMOTE+'/read_clock.c -o '+REMOTE+'/read_clock')
        run(client,'systemd-analyze verify /etc/systemd/system/'+UNIT+' /etc/systemd/system/fz3b-vision-console.service')
        run(client,'systemctl daemon-reload; systemctl enable '+UNIT+'; systemctl start '+UNIT)
        record['clock']=json.loads(run(client,'cd '+REMOTE+'; python3 -B -m vision_app.cpu_clock_service --status'))
        if not record['clock']['verified'] or record['clock']['actual_hz']!=1199999988:raise RuntimeError('actual 1.2GHz not verified')
        record['after_raw']=run(client,REMOTE+'/read_clock')
        before=[v for v in record['baseline_full'].splitlines() if 'ACPU_CTRL' not in v]
        after=[v for v in record['after_raw'].splitlines() if 'ACPU_CTRL' not in v]
        if before!=after:raise RuntimeError('non-CPU clock changed')
        run(client,'systemctl start fz3b-vision-console.service')
        record['services']=run(client,'systemctl is-active '+UNIT+' fz3b-vision-console.service').splitlines()
        record['ok']=record['services']==['active','active']
        if not record['ok']:raise RuntimeError('application not active')
        print(json.dumps({k:record[k] for k in ('ok','clock','services','backup')},indent=2))
    except BaseException as exc:
        record['error']=str(exc)
        # Each rollback step is independently attempted and retained in evidence.
        record['rollback_errors']=[]
        safe=True
        try:
            for action in ('systemctl stop fz3b-vision-console.service','systemctl stop '+UNIT,
                           'if fuser /dev/network10_v10_signed40 /dev/fz3b_cpu_clock; then exit 17; fi'):
                run(client,action,timeout=370)
        except BaseException as error:
            safe=False
            record['rollback_errors'].append(str(error))
        if safe:
            try:run(client,'if test -e /dev/fz3b_cpu_clock; then rmmod fz3b_cpu_clock; fi')
            except BaseException as error:
                safe=False
                record['rollback_errors'].append(str(error))
        if not safe:
            record['rollback_blocked']='owner drain not verified; refusing file restoration or forced teardown'
            raise
        actions = [('cp -p -- '+item['saved']+' '+shlex.quote(item['path'])) if item['exists'] else ('rm -f -- '+shlex.quote(item['path'])) for item in record['files']]
        actions += ['systemctl daemon-reload', 'systemctl '+('enable' if record.get('cpu_unit_before',{}).get('enabled')=='enabled' else 'disable')+' '+UNIT]
        if record.get('cpu_unit_before',{}).get('active')=='active':actions.append('systemctl start '+UNIT)
        actions.append('systemctl start fz3b-vision-console.service')
        for action in actions:
            try:run(client,action,timeout=370)
            except BaseException as error:record['rollback_errors'].append(str(error))
        raise
    finally:
        client.close()
        (ROOT/'artifacts/ps-application-20261009/cpu-clock'/('install-'+stamp+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
