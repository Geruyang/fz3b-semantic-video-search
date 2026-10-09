"""Complete board-only installation snapshot and conservative rollback."""
import json
import shlex
from vision_app.tools.board_link import run

REMOTE = '/root/fz3b-vision-console-20261009-001'
UNITS = ('fz3b-app-r5.service', 'fz3b-vision-console.service')
TARGETS = [REMOTE + '/config.json', REMOTE + '/r5-boot-manifest.json', REMOTE + '/tcm_io.c',
           REMOTE + '/vision_app/libr5_tcm_io.so']
TARGETS += [REMOTE + '/vision_app/' + name for name in ('board_agent.py', 'r5_start.py', 'link_setup.py', 'boot_units.py', 'r5_bridge.py')]
TARGETS += ['/etc/systemd/system/' + name for name in UNITS]


def remote_nodes(client):
    command = "python3 -B -c 'import glob,os,json; print(json.dumps([{\"path\":p,\"realpath\":os.path.realpath(p),\"state\":open(p+\"/state\").read().strip(),\"firmware\":open(p+\"/firmware\").read().strip()} for p in sorted(glob.glob(\"/sys/class/remoteproc/remoteproc*\"))]))'"
    return json.loads(run(client, command))


def backup_state(client, backup):
    run(client, 'mkdir -m 700 ' + shlex.quote(backup))
    state = {'backup': backup, 'files': [], 'units': {}, 'nodes': remote_nodes(client),
             'getty_active': run(client, 'systemctl is-active serial-getty@ttyPS0.service || true').strip() == 'active'}
    sftp = client.open_sftp()
    try:
        for index, path in enumerate(TARGETS):
            saved = backup + '/file-%d' % index
            try:
                sftp.stat(path)
                existed = True
            except IOError as exc:
                if exc.errno != 2:
                    raise
                existed = False
            if existed:
                run(client, 'cp -p -- ' + shlex.quote(path) + ' ' + shlex.quote(saved))
            state['files'].append({'path': path, 'saved': saved, 'existed': existed})
    finally:
        sftp.close()
    for unit in UNITS:
        state['units'][unit] = {'enabled': run(client, 'systemctl is-enabled ' + unit + ' || true').strip() == 'enabled',
                                'active': run(client, 'systemctl is-active ' + unit + ' || true').strip() == 'active'}
    # No secrets in this state index; private config remains inside root-only backup.
    return state


def restore_state(client, state):
    run(client, 'systemctl stop fz3b-vision-console.service', timeout=370)
    run(client, 'if systemctl is-active --quiet fz3b-app-r5.service; then systemctl stop fz3b-app-r5.service; fi')
    run(client, "python3 -B -c 'import fcntl; f=open(\"/run/fz3b-vision-r5-owner.lock\",\"a\"); fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB); f.close()'")
    run(client, 'if fuser /dev/network10_v10_signed40; then exit 17; fi')
    for unit in UNITS:
        if not state['units'][unit]['enabled']:
            run(client, 'systemctl disable ' + unit + ' || true')
    sftp = client.open_sftp()
    try:
        for item in state['files']:
            if item['existed']:
                run(client, 'cp -p -- ' + shlex.quote(item['saved']) + ' ' + shlex.quote(item['path']))
            else:
                try:
                    sftp.remove(item['path'])
                except IOError as exc:
                    if exc.errno != 2:
                        raise
    finally:
        sftp.close()
    run(client, 'systemctl daemon-reload')
    for unit in UNITS:
        if state['units'][unit]['enabled']:
            run(client, 'systemctl enable ' + unit)
    if state['units']['fz3b-app-r5.service']['active']:
        run(client, 'systemctl start fz3b-app-r5.service')
    elif any(node['state'] == 'running' for node in state['nodes']):
        # Restore only the exact manually running cores that existed beforehand.
        previous = state['nodes']
        current = remote_nodes(client)
        if len(previous) != 2 or len(current) != 2:
            raise RuntimeError('unknown R5 owner during rollback; do not force restore')
        for core in range(2):
            old = next((n for n in previous if 'app-r5%d' % core in n['realpath']), None)
            now = next((n for n in current if 'app-r5%d' % core in n['realpath']), None)
            expected = 'fz3b-app-r5%d.elf' % core
            if old is None or now is None or old['firmware'] != expected or old['state'] != 'running' or now['firmware'] != expected or now['state'] not in ('offline', 'running'):
                raise RuntimeError('unknown/partial R5 owner during rollback')
        for node in current:
            if node['state'] == 'offline':
                run(client, 'echo start > ' + shlex.quote(node['path'] + '/state'))
    if state['units']['fz3b-vision-console.service']['active']:
        run(client, 'systemctl start fz3b-vision-console.service')
    else:
        run(client, 'systemctl ' + ('start' if state['getty_active'] else 'stop') + ' serial-getty@ttyPS0.service')
    return {'restored_files': len(state['files']), 'restored_unit_states': state['units'], 'ok': True}
