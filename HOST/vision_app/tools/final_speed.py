"""Final fixed-input speed; normally drain and restore the application."""
import datetime
import json
from vision_app.tools.board_link import ROOT, open_link, run


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    local = ROOT/'artifacts/ps-application-20261009'/('speed-1p2-'+stamp)
    local.mkdir()
    remote = '/root/fz3b-vision-console-20261009-001'
    destination = remote+'/speed-'+stamp
    client = open_link()
    try:
        print('Fixed 200-frame benchmark: CPU 1199999 kHz, A0005, max_in_flight 4',flush=True)
        run(client,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(client,'if fuser /dev/network10_v10_signed40; then exit 17; fi')
        sftp = client.open_sftp()
        sftp.put(str(ROOT/'vision_app/board_speed.py'),remote+'/vision_app/board_speed.py')
        sftp.close()
        raw = run(client,'cd '+remote+'; LD_LIBRARY_PATH=/root/board-debug-runtime-20261004/runtime/onnxruntime-linux-aarch64-1.16.3/lib python3 -B -m vision_app.board_speed --output '+destination,timeout=330)
        report = json.loads(raw.strip().splitlines()[-1])
        sftp = client.open_sftp()
        sftp.get(destination+'/result.json',str(local/'result.json'))
        sftp.get(destination+'/measured-features.f32',str(local/'measured-features.f32'))
        sftp.close()
        (local/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(report,evidence=str(local))),flush=True)
    finally:
        run(client,'systemctl start fz3b-vision-console.service')
        client.close()


if __name__ == '__main__':
    main()
