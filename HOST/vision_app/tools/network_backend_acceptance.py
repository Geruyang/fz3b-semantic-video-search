"""No network writes: parser, mocked cmdlets, helper dry-run/permission denial."""
import base64
import copy
import ctypes
import json
from pathlib import Path
from vision_app import host_network as n

MOCK = r'''
$global:fake = [pscustomobject]@{
    dhcp='Disabled'; duplicate=$false; calls=@()
    ips=@([pscustomobject]@{InterfaceIndex=14;IPAddress='169.254.220.34';PrefixLength=16;PrefixOrigin='WellKnown';SkipAsSource=$false;AddressState='Preferred'})
}
function Get-NetAdapter { param([switch]$Physical)
    [pscustomobject]@{ifIndex=14;InterfaceGuid=[guid]'9566f5c3-ae17-4e8a-b58f-ae308d0e57aa';Name='test';InterfaceDescription='test';MacAddress='D8-43-AE-BD-40-FE';MediaType='802.3';Status='Up'}
}
function Get-NetIPInterface { param($InterfaceIndex,$AddressFamily,$PolicyStore)
    [pscustomobject]@{InterfaceIndex=14;Dhcp=$global:fake.dhcp}
}
function Get-NetIPAddress { param($InterfaceIndex,$AddressFamily,$PolicyStore,$IPAddress)
    @($global:fake.ips | Where-Object { (-not $IPAddress -or $_.IPAddress -eq $IPAddress) -and (-not $InterfaceIndex -or $_.InterfaceIndex -eq $InterfaceIndex) })
}
function Get-NetRoute { param($AddressFamily) @() }
function Set-NetIPInterface { param($InterfaceIndex,$AddressFamily,$Dhcp,$PolicyStore)
    if($InterfaceIndex -ne 14 -or $AddressFamily -ne 'IPv4' -or $PolicyStore -ne 'ActiveStore'){throw 'WRONG SCOPE'}
    $global:fake.calls += 'DHCP:' + $Dhcp
    $global:fake.dhcp=$Dhcp
}
function Remove-NetIPAddress { param($InterfaceIndex,$AddressFamily,$IPAddress,$PolicyStore,$Confirm)
    if($InterfaceIndex -ne 14 -or $AddressFamily -ne 'IPv4' -or $PolicyStore -ne 'ActiveStore'){throw 'WRONG SCOPE'}
    $global:fake.calls += 'REMOVE:' + $IPAddress
    $global:fake.ips=@($global:fake.ips | Where-Object IPAddress -ne $IPAddress)
}
function Set-NetIPAddress { param($InterfaceIndex,$AddressFamily,$IPAddress,$SkipAsSource,$PolicyStore)
    if($InterfaceIndex -ne 14 -or $AddressFamily -ne 'IPv4' -or $PolicyStore -ne 'ActiveStore'){throw 'WRONG SCOPE'}
    $global:fake.calls += 'SET:' + $IPAddress
}
function New-NetIPAddress { param($InterfaceIndex,$AddressFamily,$IPAddress,$PrefixLength,$SkipAsSource,$PolicyStore)
    if($InterfaceIndex -ne 14 -or $AddressFamily -ne 'IPv4' -or $PolicyStore -ne 'ActiveStore'){throw 'WRONG SCOPE'}
    $global:fake.calls += 'ADD:' + $IPAddress
    # Model removal of an automatic local address when a manual address arrives.
    $global:fake.ips=@($global:fake.ips | Where-Object PrefixOrigin -ne 'WellKnown')
    $state='Preferred'
    if($global:fake.duplicate){$state='Duplicate';$global:fake.duplicate=$false}
    $global:fake.ips += [pscustomobject]@{InterfaceIndex=14;IPAddress=$IPAddress;PrefixLength=[int]$PrefixLength;PrefixOrigin='Manual';SkipAsSource=[bool]$SkipAsSource;AddressState=$state}
}
'''


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / 'artifacts/ps-application-20261009/host-network'
    output.mkdir(exist_ok=True)
    before = n.inventory()
    report = {'ok': False, 'host_network_writes': False, 'cases': []}
    nic = {'guid':'9566f5c3-ae17-4e8a-b58f-ae308d0e57aa','index':14,'mac':'D8-43-AE-BD-40-FE','name':'test','media':'802.3','dhcp':'Disabled','default_route':False,
           'addresses':[{'ip':'169.254.220.34','prefix':16,'origin':'WellKnown','skip':False}]}
    for action, duplicate in [('static',False),('static',True),('dhcp',False),('restore',False)]:
        current = copy.deepcopy(nic)
        request = n.make_request(current, action, '192.168.1.10', '24', '192.168.1.254', nic if action == 'restore' else None)
        encoded = base64.b64encode(json.dumps(request).encode()).decode()
        script = MOCK + ('$global:fake.duplicate=$true\n' if duplicate else '') + n.INVENTORY_PS + n.MUTATION_PS.replace('__REQUEST__', encoded)
        result = n.powershell(script)
        if duplicate:
            assert not result['ok'] and result['rollback'] == 'PASS', result
        else:
            assert result['ok'], result
            if action == 'static':
                assert any(a['ip'] == '192.168.1.10' for a in result['after']['addresses'])
            if action == 'restore':
                assert any(a['ip'] == '169.254.220.34' for a in result['after']['addresses'])
        report['cases'].append({'action':action,'duplicate':duplicate,'result':result})
    # Parse the exact real mutation script without invoking it.
    request = n.make_request(before[0], 'static', '192.168.1.10', '24', '192.168.1.254')
    payload = base64.b64encode(json.dumps(request).encode()).decode()
    source = base64.b64encode((n.INVENTORY_PS + n.MUTATION_PS.replace('__REQUEST__', payload)).encode()).decode()
    parser_script = "[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding $false; $tokens=$null; $parseErrors=$null; $text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + source + "')); [void][System.Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$parseErrors); @{errors=@($parseErrors | ForEach-Object Message)} | ConvertTo-Json -Compress"
    parsed = n.powershell(parser_script)
    assert not parsed['errors'], parsed
    dry = dict(request, dry_run=True)
    path = n.create_job(dry, output)
    assert n.admin_main(path) == 0
    report['dry_run'] = json.loads(path.with_name('result.json').read_text(encoding='utf-8'))
    report['is_admin'] = bool(ctypes.windll.shell32.IsUserAnAdmin())
    if not report['is_admin']:
        path = n.create_job(request, output)
        assert n.admin_main(path) == 1
        denied = json.loads(path.with_name('result.json').read_text(encoding='utf-8'))
        assert not denied['changed'] and '管理员' in denied['error']
        report['unprivileged_write_denied'] = denied
    # This acceptance must never invoke a real mutation, even on an admin host.
    assert [n.fingerprint(x) for x in before] == [n.fingerprint(x) for x in n.inventory()]
    report['ok'] = True
    (output / 'backend-acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok':True,'mock_cases':len(report['cases']),'parser_errors':0,'is_admin':report['is_admin'],'host_network_writes':False}))


if __name__ == '__main__':
    main()
