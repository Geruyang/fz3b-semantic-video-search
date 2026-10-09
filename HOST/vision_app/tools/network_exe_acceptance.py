"""Permission denial through CreateProcess, only from a verified standard token."""
import ctypes
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import pefile
from vision_app import host_network as n


def main():
    root = Path(__file__).resolve().parents[2]
    executable = root/'deliverables/vision-console/FZ3BVisionConsole/FZ3BVisionConsole.exe'
    # CreateProcess does not perform UAC elevation. Refuse this test from an
    # administrator token, and verify the compiled executable is asInvoker.
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('Permission-denial acceptance requires a non-admin token; no request executed')
    pe = pefile.PE(str(executable))
    try:
        manifests = [pe.get_data(lang.data.struct.OffsetToData,lang.data.struct.Size)
                     for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries if entry.id == 24
                     for item in entry.directory.entries for lang in item.directory.entries]
        if len(manifests) != 1:
            raise RuntimeError('Unexpected executable manifest')
        element = ET.fromstring(manifests[0]).find('.//{urn:schemas-microsoft-com:asm.v3}requestedExecutionLevel')
        if element is None or element.attrib.get('level') != 'asInvoker':
            raise RuntimeError('Executable may elevate; no request executed')
    finally:
        pe.close()
    before = n.inventory()
    request = n.make_request(before[0], 'static', '192.168.1.10', '24', '192.168.1.254')
    output = root/'artifacts/ps-application-20261009/host-network'
    path = n.create_job(request, output)
    # shell=False means CreateProcess, never ShellExecute/runas/Start-Process.
    child = subprocess.run([str(executable),'--network-admin',str(path)], shell=False,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
    result = json.loads(path.with_name('result.json').read_text(encoding='utf-8'))
    assert child.returncode == 1 and not result['changed'] and '管理员' in result['error'], result
    assert [n.fingerprint(x) for x in before] == [n.fingerprint(x) for x in n.inventory()]
    receipt = {'ok':True,'is_admin':False,'manifest':'asInvoker','launch':'CreateProcess, shell=False',
               'permission_denied':result,'host_network_writes':False}
    (output/'exe-permission-denial.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:receipt[k] for k in ('ok','is_admin','manifest','launch','host_network_writes')}))


if __name__ == '__main__':
    main()
