"""Run the application factory against frozen tensors with controlled close."""
import json
from vision_app.tools.board_link import ROOT, open_link, run

c = open_link()
remote = '/root/fz3b-vision-console-20261009-001'
try:
    run(c, 'systemctl stop fz3b-vision-console.service', timeout=370)
    s = c.open_sftp()
    s.put(str(ROOT / 'vision_app/board_validate.py'), remote + '/vision_app/board_validate.py')
    s.close()
    command = 'cd ' + remote + '; LD_LIBRARY_PATH=/root/board-debug-runtime-20261004/runtime/onnxruntime-linux-aarch64-1.16.3/lib python3 -B -m vision_app.board_validate'
    raw = run(c, command, timeout=330)
    report = json.loads(raw.strip().splitlines()[-1])
    (ROOT / 'artifacts/ps-application-20261009/fixed-factory-regression.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
finally:
    run(c, 'systemctl start fz3b-vision-console.service')
    c.close()
