[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$ReadyReceipt,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedReadyReceiptSha256,
    [int]$AllowedHwServerPid=0,
    [string]$VivadoRoot='D:\Vivado\2026.1'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$tcl=Join-Path $PSScriptRoot 'set_pl1_100mhz_for_a0005.tcl'
$expectedTcl='2dd30f588b8d3a03dd9f0b6b5b1e352b601d502cb75cd276db1ac73ccff3421b'
$xsdb=Join-Path $VivadoRoot 'Vitis\bin\xsdb.bat'
$hwServer=Join-Path $VivadoRoot 'Vivado\bin\hw_server.bat'
$readyPath=[IO.Path]::GetFullPath($ReadyReceipt)
$evidence=[IO.Path]::GetFullPath($EvidenceDir)
foreach($p in @($tcl,$xsdb,$hwServer,$readyPath)){if(!(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing exact input: $p"}}
if((Sha $tcl)-ne$expectedTcl){throw 'Frozen PL1 hold Tcl SHA mismatch'}
if((Sha $readyPath)-ne$ExpectedReadyReceiptSha256.ToLowerInvariant()){throw 'Fresh READY receipt SHA mismatch'}
$ready=Get-Content -Raw -LiteralPath $readyPath|ConvertFrom-Json
if($ready.pass-ne$true-or!([string]$ready.status).StartsWith('READY_FOR_', [StringComparison]::Ordinal)){throw 'Fresh network receipt is not READY'}
if(Test-Path -LiteralPath $evidence){throw 'EvidenceDir must be new'}
$existingListeners=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue|Where-Object{$_.LocalPort-eq3121})
if($existingListeners.Count){
    if($AllowedHwServerPid-eq0-or$existingListeners.Count-ne1-or$existingListeners[0].OwningProcess-ne$AllowedHwServerPid){throw 'TCP 3121 already has a listener; refusing ambiguous ownership'}
    $allowed=Get-Process -Id $AllowedHwServerPid -ErrorAction Stop
    if($allowed.ProcessName-ne'hw_server'-or$allowed.Path-ne(Join-Path $VivadoRoot 'Vivado\bin\unwrapped\win64.o\hw_server.exe')){throw 'AllowedHwServerPid is not the exact official hw_server'}
}
New-Item -ItemType Directory -Path $evidence|Out-Null
$stdout=Join-Path $evidence 'xsdb.stdout.log';$stderr=Join-Path $evidence 'xsdb.stderr.log'
$hsout=Join-Path $evidence 'hw_server.stdout.log';$hserr=Join-Path $evidence 'hw_server.stderr.log'
$hw=$null;$listenerPid=$null;$xs=$null;$xsExit=$null;$caught=$null;$started=[DateTime]::UtcNow
try{
    if(!$existingListeners.Count){
        $hw=Start-Process -FilePath $hwServer -ArgumentList @('-s','tcp::3121') -WindowStyle Hidden -RedirectStandardOutput $hsout -RedirectStandardError $hserr -PassThru
        $listening=$false
        for($i=0;$i-lt60;$i++){
            Start-Sleep -Milliseconds 250
            $listener=Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue|Where-Object{$_.LocalPort-eq3121}|Select-Object -First 1
            if($listener){$listenerPid=$listener.OwningProcess;$listening=$true;break}
            if($hw.HasExited){throw "Owned hw_server exited early code=$($hw.ExitCode)"}
        }
        if(!$listening){throw 'Owned hw_server did not listen on TCP 3121'}
    }
    $xs=Start-Process -FilePath $xsdb -ArgumentList @($tcl) -WorkingDirectory $evidence -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -Wait
    $xsExit=$xs.ExitCode
}catch{$caught=$_.Exception.Message}
finally{
    if($listenerPid){Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue}
    if($hw-and!$hw.HasExited){Stop-Process -Id $hw.Id -Force -ErrorAction SilentlyContinue;$hw.WaitForExit(10000)|Out-Null}
}
$outText=if(Test-Path $stdout){Get-Content -Raw $stdout}else{''};$errText=if(Test-Path $stderr){Get-Content -Raw $stderr}else{''}
$pass=($xsExit-eq0-and$outText.Contains('READY_PL1_100MHZ_HELD PL1=0x01010F00 PL0_UNCHANGED=1 HALT=0 RESET=0 DOWNLOAD=0 FORCE=0 AIB=0')-and!$outText.Contains('TRANSACTION_ERROR=')-and[string]::IsNullOrWhiteSpace($errText)-and$null-eq$caught)
$receipt=[ordered]@{
    schema='cnn-v10.5-a0005-pl1-100mhz-held-v1';status=if($pass){'READY_PL1_100MHZ_HELD'}else{'FAIL'};pass=$pass
    started_utc=$started.ToString('o');finished_utc=[DateTime]::UtcNow.ToString('o');transaction_started=(Test-Path $stdout)-and$outText.Contains('XSDB_A0005_PL1_100MHZ_HOLD_BEGIN');caught_exception=$caught
    fresh_network_ready=[ordered]@{path=$readyPath;sha256=$ExpectedReadyReceiptSha256.ToLowerInvariant();status=$ready.status}
    clock_transaction=[ordered]@{pl0='0x01010802';pl1_entry='0x00052000';pl1_target_gated='0x00010F00';pl1_target_enabled='0x01010F00';pl2='0x00052000';pl3='0x00052000';iopll='0x00015A00';rpll='0x00013000';ddr='0x01000200';pll_status='0x0000001B';double_read_checks=$true;success_leaves_pl1_enabled=$true;failure_attempts_exact_restore=$true}
    cpu=[ordered]@{a53_0_required='Running';halt=$false;reset=$false};prohibited_actions=[ordered]@{download=$false;force=$false;aib_write=$false}
    source=[ordered]@{tcl_path=$tcl;tcl_sha256=Sha $tcl;runner_sha256=Sha $MyInvocation.MyCommand.Path}
    transport=[ordered]@{reused_official_hw_server=($existingListeners.Count-eq1);allowed_hw_server_pid=$AllowedHwServerPid}
    tool=[ordered]@{xsdb_exit_code=$xsExit;stdout_sha256=if(Test-Path $stdout){Sha $stdout}else{$null};stderr_sha256=if(Test-Path $stderr){Sha $stderr}else{$null};hw_server_stdout_sha256=if(Test-Path $hsout){Sha $hsout}else{$null};hw_server_stderr_sha256=if(Test-Path $hserr){Sha $hserr}else{$null}}
}
$receipt|ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $evidence 'receipt.json') -Encoding utf8NoBOM
if(!$pass){throw "A0005 PL1 persistent 100 MHz transaction failed; receipt=$(Join-Path $evidence 'receipt.json')"}
Write-Output($receipt|ConvertTo-Json -Depth 10 -Compress)
