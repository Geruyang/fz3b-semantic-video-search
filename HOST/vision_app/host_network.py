"""Windows-only, interface-scoped IPv4 configuration with a separate UAC helper."""
import argparse
import base64
import ctypes
from ctypes import wintypes
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


INVENTORY_PS = r'''
$ErrorActionPreference = 'Stop'
$WarningPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
function Get-NicState($adapter) {
    $index = [int]$adapter.ifIndex
    $policy = Get-NetIPInterface -AddressFamily IPv4 -PolicyStore ActiveStore | Where-Object InterfaceIndex -eq $index | Select-Object -First 1
    $ips = @(Get-NetIPAddress -AddressFamily IPv4 -PolicyStore ActiveStore | Where-Object InterfaceIndex -eq $index)
    $routes = @(Get-NetRoute | Where-Object { $_.InterfaceIndex -eq $index -and $_.DestinationPrefix -in @('0.0.0.0/0', '::/0') })
    return [pscustomobject]@{
        guid = $adapter.InterfaceGuid.ToString().Trim('{}').ToLowerInvariant()
        index = $index; name = $adapter.Name; description = $adapter.InterfaceDescription
        mac = $adapter.MacAddress; media = $adapter.MediaType.ToString(); status = $adapter.Status.ToString()
        dhcp = $(if ($policy -and $null -ne $policy.Dhcp) { $policy.Dhcp.ToString() } else { 'Unknown' }); default_route = ($routes.Count -gt 0)
        addresses = @($ips | ForEach-Object { [pscustomobject]@{
            ip = $_.IPAddress; prefix = [int]$_.PrefixLength; origin = $_.PrefixOrigin.ToString()
            skip = [bool]$_.SkipAsSource; state = $_.AddressState.ToString()
        } })
    }
}
function Get-WiredAdapters {
    return @(Get-NetAdapter -Physical | Where-Object { $_.MediaType.ToString() -eq '802.3' })
}
'''

MUTATION_PS = r'''
$request = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__REQUEST__')) | ConvertFrom-Json
$selectedAdapters = @(Get-WiredAdapters | Where-Object { $_.InterfaceGuid.ToString().Trim('{}').ToLowerInvariant() -eq $request.target.guid })
if ($selectedAdapters.Count -ne 1) { throw 'Selected physical Ethernet adapter disappeared.' }
$adapter = $selectedAdapters[0]
$index = [int]$adapter.ifIndex
$before = Get-NicState $adapter
if ($index -ne $request.target.index -or $before.mac -ne $request.target.mac -or $before.default_route) { throw 'Interface identity or default route changed.' }
function Address-Key($state) {
    return (@($state.addresses | ForEach-Object { "$($_.ip)/$($_.prefix)/$($_.origin)/$($_.skip)" } | Sort-Object) -join ';')
}
if ($before.dhcp -ne $request.expected.dhcp -or (Address-Key $before) -ne (Address-Key $request.expected)) { throw 'Network configuration changed. Refresh and retry.' }
function Restore-IPv4($saved) {
    $live = @(Get-WiredAdapters | Where-Object { $_.InterfaceGuid.ToString().Trim('{}').ToLowerInvariant() -eq $request.target.guid })
    if ($live.Count -ne 1 -or $live[0].ifIndex -ne $index -or $live[0].MacAddress -ne $request.target.mac) { throw 'Adapter identity changed; refuse rollback to another interface.' }
    Set-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4 -Dhcp Disabled -PolicyStore ActiveStore
    @(Get-NetIPAddress -AddressFamily IPv4 -PolicyStore ActiveStore | Where-Object { $_.InterfaceIndex -eq $index -and $_.PrefixOrigin.ToString() -eq 'Manual' }) | ForEach-Object {
        Remove-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -IPAddress $_.IPAddress -PolicyStore ActiveStore -Confirm:$false
    }
    $restoreAddresses = @($saved.addresses | Where-Object { $_.origin -eq 'Manual' -or $saved.dhcp -eq 'Disabled' })
    foreach ($ip in $restoreAddresses) {
        $present = @(Get-NetIPAddress -AddressFamily IPv4 -PolicyStore ActiveStore | Where-Object { $_.InterfaceIndex -eq $index -and $_.IPAddress -eq $ip.ip })
        if ($present.Count -eq 0) {
            New-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -IPAddress $ip.ip -PrefixLength $ip.prefix -SkipAsSource ([bool]$ip.skip) -PolicyStore ActiveStore | Out-Null
        } elseif ($present[0].PrefixLength -ne $ip.prefix) { throw 'Restored address mask does not match.' }
    }
    if ($saved.dhcp -eq 'Enabled') { Set-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4 -Dhcp Enabled -PolicyStore ActiveStore }
    $deadline = [DateTime]::UtcNow.AddSeconds(12)
    do {
        $verified = Get-NicState $adapter
        $complete = ($verified.dhcp -eq $saved.dhcp)
        foreach ($wanted in $restoreAddresses) {
            $found = @($verified.addresses | Where-Object { $_.ip -eq $wanted.ip -and $_.prefix -eq $wanted.prefix -and $_.skip -eq $wanted.skip -and $_.state -eq 'Preferred' })
            if ($found.Count -ne 1) { $complete = $false }
        }
        if ($complete) { break }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $complete) { throw 'Restored IPv4 configuration did not become usable before deadline.' }
}
$changed = $false
try {
    switch ($request.action) {
        'static' {
            $same = @($before.addresses | Where-Object { $_.ip -eq $request.address -and $_.prefix -eq $request.prefix -and -not $_.skip })
            if ($before.dhcp -eq 'Disabled' -and $same.Count -gt 0) { break }
            $changed = $true
            Set-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4 -Dhcp Disabled -PolicyStore ActiveStore
            $existing = @(Get-NetIPAddress -AddressFamily IPv4 -PolicyStore ActiveStore | Where-Object { $_.InterfaceIndex -eq $index -and $_.IPAddress -eq $request.address })
            if ($existing.Count -gt 0) {
                if ($existing[0].PrefixLength -ne $request.prefix) { throw 'Address already exists with a different subnet mask.' }
                Set-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -IPAddress $request.address -SkipAsSource $false -PolicyStore ActiveStore
            } else {
                New-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -IPAddress $request.address -PrefixLength $request.prefix -SkipAsSource $false -PolicyStore ActiveStore | Out-Null
            }
            $deadline = [DateTime]::UtcNow.AddSeconds(12)
            do {
                $address = Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -IPAddress $request.address -PolicyStore ActiveStore
                if ($address.AddressState.ToString() -eq 'Duplicate') { throw 'Duplicate IPv4 address detected.' }
                if ($address.AddressState.ToString() -eq 'Preferred') { break }
                Start-Sleep -Milliseconds 200
            } while ([DateTime]::UtcNow -lt $deadline)
            if ($address.AddressState.ToString() -ne 'Preferred') { throw 'IPv4 address is not usable yet.' }
        }
        'dhcp' { $changed = $true; Restore-IPv4 ([pscustomobject]@{dhcp='Enabled';addresses=@()}) }
        'restore' { $changed = $true; Restore-IPv4 $request.restore }
        default { throw 'Unsupported network operation.' }
    }
    $after = Get-NicState $adapter
    if ($request.action -eq 'dhcp' -and $after.dhcp -ne 'Enabled') { throw 'DHCP readback does not match.' }
    if ($request.action -eq 'restore' -and $after.dhcp -ne $request.restore.dhcp) { throw 'Restored DHCP readback does not match.' }
    if ($request.action -eq 'restore') {
        foreach ($ip in @($request.restore.addresses | Where-Object { $_.origin -eq 'Manual' -or $request.restore.dhcp -eq 'Disabled' })) {
            if (@($after.addresses | Where-Object { $_.ip -eq $ip.ip -and $_.prefix -eq $ip.prefix }).Count -ne 1) { throw 'Restored IPv4 readback does not match.' }
        }
    }
    [pscustomobject]@{ok=$true;changed=$changed;before=$before;after=$after;action=$request.action} | ConvertTo-Json -Depth 8 -Compress
} catch {
    $failure = $_.Exception.Message
    $rollback = 'not needed'
    if ($changed) {
        try { Restore-IPv4 $before; $rollback = 'PASS' } catch { $rollback = 'FAILED: ' + $_.Exception.Message }
    }
    [pscustomobject]@{ok=$false;changed=$changed;error=$failure;rollback=$rollback;before=$before} | ConvertTo-Json -Depth 8 -Compress
}
'''


def powershell(script, timeout=30):
    if os.name != 'nt':
        raise RuntimeError('主机网口设置仅支持 Windows')
    directory = ctypes.create_unicode_buffer(32768)
    ctypes.windll.kernel32.GetSystemDirectoryW(directory, len(directory))
    binary = Path(directory.value) / 'WindowsPowerShell/v1.0/powershell.exe'
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run([str(binary), '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace').strip() or 'Windows 网络命令失败')
    return json.loads(result.stdout.decode('utf-8-sig'))


def inventory():
    result = powershell(INVENTORY_PS + '\n$states = @(Get-WiredAdapters | ForEach-Object { Get-NicState $_ }); ConvertTo-Json -InputObject $states -Depth 6 -Compress')
    return result if isinstance(result, list) else [result]


def identity(nic):
    if type(nic.get('index')) is not int or not 0 < nic['index'] < 2147483648:
        raise ValueError('网口索引无效，请刷新')
    guid = str(uuid.UUID(nic['guid'].strip('{}')))
    mac = nic['mac'].upper().replace(':', '-')
    if not re.fullmatch(r'(?:[0-9A-F]{2}-){5}[0-9A-F]{2}', mac):
        raise ValueError('网口 MAC 身份无效')
    return {'guid': guid, 'index': nic['index'], 'mac': mac}


def ipv4(address, prefix, board=''):
    ip = ipaddress.IPv4Address(address)
    network = ipaddress.IPv4Network('0.0.0.0/' + str(prefix))
    count = network.prefixlen
    actual = ipaddress.IPv4Network(str(ip) + '/' + str(count), strict=False)
    if not 1 <= count <= 30 or ip.is_unspecified or ip.is_loopback or ip.is_multicast or ip.is_reserved or ip in (actual.network_address, actual.broadcast_address):
        raise ValueError('请输入有效主机 IPv4 和连续掩码（前缀 1–30）')
    if board and ip == ipaddress.IPv4Address(board):
        raise ValueError('主机地址不能与板卡地址相同')
    if board and ipaddress.IPv4Address(board) not in actual:
        raise ValueError('主机与板卡地址应在同一子网')
    return str(ip), count


def fingerprint(nic):
    values = dict(identity(nic), dhcp=nic['dhcp'], addresses=sorted([
        (a['ip'], a['prefix'], a['origin'], bool(a['skip'])) for a in nic['addresses']]))
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def check_nic(nic):
    identity(nic)
    if nic.get('media') != '802.3':
        raise ValueError('只能配置物理有线网口')
    if nic.get('default_route'):
        raise ValueError('所选网口有默认网关，请选择专用板卡直连网口')
    if nic.get('dhcp') not in ('Enabled', 'Disabled'):
        raise ValueError('无法读取 DHCP 状态，请先在系统启用该网口')


def make_request(nic, action, address='', mask='24', board='', backup=None):
    check_nic(nic)
    if action not in ('static', 'dhcp', 'restore'):
        raise ValueError('未知网络设置操作')
    request = {'version': 1, 'action': action, 'store': 'ActiveStore', 'target': identity(nic), 'expected': nic,
               'fingerprint': fingerprint(nic), 'board_ip': board}
    if action == 'static':
        request['address'], request['prefix'] = ipv4(address, mask, board)
        for existing in nic['addresses']:
            if existing['ip'] == request['address'] and existing['prefix'] != request['prefix']:
                raise ValueError('该地址已使用不同掩码，请先恢复配置')
    if action == 'restore':
        if backup is None or identity(backup)['guid'] != request['target']['guid']:
            raise ValueError('恢复记录不属于这个网口')
        check_nic(backup)
        if len(backup['addresses']) > 32:
            raise ValueError('恢复地址数量异常')
        for entry in backup['addresses']:
            ipv4(entry['ip'], entry['prefix'])
        request['restore'] = backup
    return request


def validate_request(request, nics):
    if request.get('version') != 1 or request.get('store') != 'ActiveStore':
        raise ValueError('网络请求版本或作用范围无效')
    target = identity(request['target'])
    matches = [nic for nic in nics if identity(nic)['guid'] == target['guid']]
    if len(matches) != 1 or identity(matches[0]) != target:
        raise ValueError('网口身份已变化，请刷新')
    nic = matches[0]
    check_nic(nic)
    if fingerprint(nic) != request['fingerprint']:
        raise ValueError('网口配置已变化，请刷新后再操作')
    # Validate again in the elevated process; JSON is data, never shell code.
    clean = make_request(nic, request['action'], request.get('address', ''), request.get('prefix', 24), request.get('board_ip', ''), request.get('restore'))
    if fingerprint(request['expected']) != fingerprint(nic):
        raise ValueError('请求中的原始网口配置不匹配，请刷新')
    return clean['target']


def history_root():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FZ3BVisionConsole/network'


def last_backup(guid, root=None):
    root = Path(root) if root else history_root()
    receipts = sorted(root.glob('*/result.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in receipts:
        try:
            result = json.loads(path.read_text(encoding='utf-8'))
            if result.get('ok') and result.get('changed') and result['before']['guid'] == guid:
                return result['before']
        except (OSError, ValueError, KeyError):
            continue
    return None


def create_job(request, root=None):
    folder = (Path(root) if root else history_root()) / uuid.uuid4().hex
    folder.mkdir(parents=True)
    path = folder / 'request.json'
    path.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
    return path


def elevate(request_path):
    class ExecuteInfo(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('fMask', wintypes.ULONG), ('hwnd', wintypes.HWND),
                    ('lpVerb', wintypes.LPCWSTR), ('lpFile', wintypes.LPCWSTR), ('lpParameters', wintypes.LPCWSTR),
                    ('lpDirectory', wintypes.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', wintypes.HINSTANCE),
                    ('lpIDList', ctypes.c_void_p), ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY),
                    ('dwHotKey', wintypes.DWORD), ('hIcon', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]
    frozen = getattr(sys, 'frozen', False)
    arguments = ['--network-admin', str(request_path)] if frozen else ['-m', 'vision_app.host_network', '--admin', str(request_path)]
    directory = Path(sys.executable).parent if frozen else Path(__file__).resolve().parents[1]
    info = ExecuteInfo()
    info.cbSize, info.fMask, info.lpVerb, info.lpFile = ctypes.sizeof(info), 0x40 | 0x400, 'runas', sys.executable
    info.lpParameters, info.lpDirectory, info.nShow = subprocess.list2cmdline(arguments), str(directory), 0
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.ShellExecuteExW.argtypes, shell.ShellExecuteExW.restype = [ctypes.POINTER(ExecuteInfo)], wintypes.BOOL
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == 1223:
            return {'ok': False, 'cancelled': True, 'error': '已取消管理员授权，网口未修改'}
        raise ctypes.WinError(error)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        # This runs in a QThread. Never kill a helper halfway through a write.
        kernel.WaitForSingleObject(info.hProcess, 0xffffffff)
    finally:
        kernel.CloseHandle(info.hProcess)
    result_path = Path(request_path).with_name('result.json')
    if not result_path.exists():
        raise RuntimeError('管理员助手未返回结果；修改前记录保存在 ' + str(request_path.parent))
    return json.loads(result_path.read_text(encoding='utf-8'))


def admin_main(path):
    path = Path(path).resolve()
    result = {'ok': False, 'changed': False}
    mutex, acquired = None, False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes, kernel.CreateMutexW.restype = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD
    kernel.ReleaseMutex.argtypes = kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        if path.stat().st_size > 131072:
            raise ValueError('网络请求超过长度限制')
        request = json.loads(path.read_text(encoding='utf-8'))
        dry_run = request.get('dry_run') is True
        if not dry_run and not ctypes.windll.shell32.IsUserAnAdmin():
            raise PermissionError('需要管理员授权，尚未修改网口')
        mutex = kernel.CreateMutexW(None, False, 'Local\\FZ3BVisionConsole.NetworkConfig')
        wait = kernel.WaitForSingleObject(mutex, 0)
        acquired = wait in (0, 0x80)
        if not acquired:
            raise RuntimeError('另一项主机网口配置正在进行')
        nics = inventory()
        validate_request(request, nics)
        before = next(n for n in nics if n['guid'] == request['target']['guid'])
        path.with_name('before.json').write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding='utf-8')
        if dry_run:
            result = {'ok': True, 'changed': False, 'dry_run': True, 'before': before, 'action': request['action']}
        else:
            encoded = base64.b64encode(json.dumps(request, ensure_ascii=False).encode('utf-8')).decode('ascii')
            # Cmdlet failures execute rollback inside PowerShell; no process timeout.
            result = powershell(INVENTORY_PS + MUTATION_PS.replace('__REQUEST__', encoded), timeout=None)
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        if acquired:
            kernel.ReleaseMutex(mutex)
        if mutex:
            kernel.CloseHandle(mutex)
        path.with_name('result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--admin')
    args = parser.parse_args()
    raise SystemExit(admin_main(args.admin) if args.admin else 0)
