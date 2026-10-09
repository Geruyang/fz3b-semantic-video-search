"""User-approved TCM-only dual-R5 qualification via the existing kernel driver."""
import json
import hashlib
from vision_app.tools.board_link import ROOT, open_link, run


def main():
    local = ROOT / 'artifacts/ps-application-20261009/r5'
    remote = '/root/fz3b-vision-console-20261009-001'
    client = open_link()
    record = {'uses_external_ddr': False, 'pl_changed': False, 'firmware': [], 'status': 'STARTED', 'authorization': 'User explicitly approved this dual R5 overlay/start/TCM mailbox operation on 2026-10-09'}
    try:
        record['a0005_before'] = json.loads(run(client, 'python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status'))
        guard = "python3 -c 'import os,mmap,struct; f=os.open(\"/dev/mem\",os.O_RDONLY|os.O_SYNC); m=mmap.mmap(f,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0xff9a0000); assert all(struct.unpack_from(\"<I\",m,a)[0]&1==0 for a in [0x100,0x200]), \"RPU already running\"; m.close(); os.close(f)'"
        run(client, guard)
        sftp = client.open_sftp()
        for i in range(2):
            name = 'fz3b-app-r5%d.elf' % i
            sftp.put(str(local / name), '/lib/firmware/' + name)
            record['firmware'].append({'name': name, 'sha256': hashlib.sha256((local / name).read_bytes()).hexdigest()})
        sftp.put(str(local / 'tcm-split-overlay.dtbo'), remote + '/tcm-split-overlay.dtbo')
        sftp.put(str(ROOT / 'vision_app/r5_bridge.py'), remote + '/vision_app/r5_bridge.py')
        sftp.put(str(ROOT / 'vision_app/r5/tcm_io.c'), remote + '/tcm_io.c')
        sftp.close()
        run(client, 'gcc -O2 -Wall -Wextra -Werror -shared -fPIC ' + remote + '/tcm_io.c -o ' + remote + '/vision_app/libr5_tcm_io.so')
        record['overlay'] = run(client, 'set -eu; modprobe zynqmp_r5_remoteproc; if ! test -d /sys/kernel/config/device-tree/overlays/fz3b-app-r5; then mkdir /sys/kernel/config/device-tree/overlays/fz3b-app-r5; cat ' + remote + '/tcm-split-overlay.dtbo > /sys/kernel/config/device-tree/overlays/fz3b-app-r5/dtbo; fi; cat /sys/kernel/config/device-tree/overlays/fz3b-app-r5/status; for p in /sys/class/remoteproc/remoteproc*; do readlink -f "$p"; cat "$p/state"; done')
        record['start'] = run(client, 'set -eu; for p in /sys/class/remoteproc/remoteproc*; do case "$(readlink -f "$p")" in *app-r50*) echo fz3b-app-r50.elf > "$p/firmware"; echo start > "$p/state";; *app-r51*) echo fz3b-app-r51.elf > "$p/firmware"; echo start > "$p/state";; esac; done; for p in /sys/class/remoteproc/remoteproc*; do readlink -f "$p"; cat "$p/state"; done')
        probe = "cd " + remote + "; python3 -B -c 'from vision_app.r5_bridge import R5Bridge; import json,zlib; r=R5Bridge(); assert r.request(0,1,123)==123; assert r.request(1,1,456)==456; data=bytes(range(256))*400; assert r.crc(data)==zlib.crc32(data)&0xffffffff; assert r.request(0,10,599999)==1; r.telemetry(1066666,123456,29.1,777); print(json.dumps(r.status())); r.close()'"
        record['mailbox_validation'] = json.loads(run(client, probe))
        record['a0005_after'] = json.loads(run(client, 'python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status'))
        record['status'] = 'PASS'
        print(json.dumps(record['mailbox_validation']))
    except BaseException as exc:
        record['status'], record['error'] = 'FAIL', str(exc)
        print(run(client, 'dmesg | tail -40'))
        # Stop only our two new instances, keeping the board and A0005 alive.
        run(client, 'for p in /sys/class/remoteproc/remoteproc*; do case "$(readlink -f "$p")" in *app-r5*) if test "$(cat "$p/state")" = running; then echo stop > "$p/state"; fi;; esac; done')
        raise
    finally:
        client.close()
        (local / 'deployment-result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
