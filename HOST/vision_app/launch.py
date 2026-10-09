import sys
import traceback
from pathlib import Path

if __name__ == '__main__':
    try:
        admin_request = len(sys.argv) == 3 and sys.argv[1] == '--network-admin'
        if getattr(sys, 'frozen', False) and not admin_request:
            stream = open(Path(sys.executable).with_name('client-runtime.log'), 'a', encoding='utf-8', buffering=1)
            sys.stdout = sys.stderr = stream
            print('Starting Vision Console')
        if admin_request:
            from vision_app.host_network import admin_main
            raise SystemExit(admin_main(sys.argv[2]))
        else:
            from vision_app.client import main
            raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
