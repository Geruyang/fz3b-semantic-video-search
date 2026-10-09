[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [ValidateSet('A0005_ROUTE_AND_BIT_APPROVED')][string]$OwnerReleaseToken,
    [string]$RouteEvidenceDir='artifacts/board-debug-20261008/acceleration/jtag/cnn-v10.5-a0005-fastbufgdiv-preg-route-bit-002',
    [string]$VivadoRoot='D:\Vivado\2026.1\Vivado'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Need([string]$Path){if(!(Test-Path -LiteralPath $Path -PathType Leaf)){throw "Missing file: $Path"}}
function WriteUtf8([string]$Path,[string]$Text){[IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))}
if($OwnerReleaseToken-ne'A0005_ROUTE_AND_BIT_APPROVED'){throw 'Final bit generation requires owner release token'}

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..\..\..'))
$routeEvidence=[IO.Path]::GetFullPath($(if([IO.Path]::IsPathRooted($RouteEvidenceDir)){$RouteEvidenceDir}else{Join-Path $repo $RouteEvidenceDir}))
$routedDcp=Join-Path $routeEvidence 'a0005-post-route.dcp'
$routeReceipt=Join-Path $routeEvidence 'receipt.json'
$routeTiming=Join-Path $routeEvidence 'timing-summary-post-route.rpt'
$routeStatus=Join-Path $routeEvidence 'route-status-post-route.rpt'
$expectedDcpSha='fea3a0d075e243d22fa874799f93883648ec9def2797b61ff29c47dbf86b61e7'
$expectedReceiptSha='1b065f48adae899ae2cdf4c4546a18dc24a18c77269f8759222b19ace52a7604'
$expectedTimingSha='4b85b6b25f9847f3c709d33ae15ff8780951feb40ed7828ea21e2a888715e378'
$expectedRouteStatusSha='1df17d18884b8ac79f9970c3fcd056a4a1ed37af2c2c880a162c10847506c1b6'
$tcl=Join-Path $PSScriptRoot 'finalize_bit_cnn_pipeline_v10_a0005_fastbufgdiv_preg_routed.tcl'
$vivado=Join-Path $VivadoRoot 'bin\vivado.bat'
foreach($file in @($routedDcp,$routeReceipt,$routeTiming,$routeStatus,$tcl,$vivado)){Need $file}
foreach($pair in @(@($routedDcp,$expectedDcpSha),@($routeReceipt,$expectedReceiptSha),@($routeTiming,$expectedTimingSha),@($routeStatus,$expectedRouteStatusSha))){
    if((Sha $pair[0])-ne$pair[1]){throw "Frozen routed evidence SHA mismatch: $($pair[0])"}
}

$evidence=[IO.Path]::GetFullPath($EvidenceDir)
if(Test-Path -LiteralPath $evidence){throw 'EvidenceDir must be new'}
$existing=@(Get-Process -Name vivado -ErrorAction SilentlyContinue)
if($existing.Count){throw "Unexpected Vivado owner active: $($existing.Id -join ',')"}
New-Item -ItemType Directory -Path $evidence|Out-Null
$snapshot=Join-Path $evidence 'source-snapshot'; New-Item -ItemType Directory -Path $snapshot|Out-Null
$runnerSnapshot=Join-Path $snapshot 'run_finalize_bit_cnn_pipeline_v10_a0005_fastbufgdiv_preg_routed.ps1'
$tclSnapshot=Join-Path $snapshot 'finalize_bit_cnn_pipeline_v10_a0005_fastbufgdiv_preg_routed.tcl'
Copy-Item $PSCommandPath $runnerSnapshot
Copy-Item $tcl $tclSnapshot
$runnerSha=Sha $runnerSnapshot; $tclSha=Sha $tclSnapshot

$privateUser=Join-Path $evidence 'private-user'; $roaming=Join-Path $privateUser 'AppData\Roaming'; $local=Join-Path $privateUser 'AppData\Local'
$manifest=Join-Path $roaming 'Xilinx\Vivado\tclapp\manifest.tcl'
New-Item -ItemType Directory -Path (Split-Path $manifest),$local -Force|Out-Null
WriteUtf8 $manifest "::tclapp::load_app -namespace {aldec::activehdl} aldec::activehdl`r`n"

$stdout=Join-Path $evidence 'vivado.stdout.log'; $native=Join-Path $evidence 'vivado.log'; $journal=Join-Path $evidence 'vivado.jou'; $cmd=Join-Path $evidence 'invoke-vivado.cmd'
$args=@('-mode','batch','-log',$native,'-journal',$journal,'-notrace','-source',$tclSnapshot,'-tclargs',$routedDcp,$expectedDcpSha,$evidence)
$quoted=@($args|ForEach-Object{if($_-match'[\s",]'){('"'+($_-replace'"','\"')+'"')}else{$_}})
WriteUtf8 $cmd ("@echo off`r`ncall `"$vivado`" "+($quoted-join' ')+" > `"$stdout`" 2>&1`r`nexit /b %ERRORLEVEL%`r`n")
$contract=[ordered]@{schema='cnn-v10.5-a0005-preg-routed-finalize-bit-launch-v1';route_rerun=$false;board_accessed=$false;ltx_requested=$false;input_routed_dcp=$routedDcp;input_routed_dcp_sha256=$expectedDcpSha;route_attempt_receipt_sha256=$expectedReceiptSha;route_timing_sha256=$expectedTimingSha;route_status_sha256=$expectedRouteStatusSha;runner_sha256=$runnerSha;tcl_sha256=$tclSha;created_utc=[DateTime]::UtcNow.ToString('o')}
WriteUtf8 (Join-Path $evidence 'launch-contract.json') (($contract|ConvertTo-Json -Depth 8)+"`n")
$environment=@{APPDATA=$roaming;LOCALAPPDATA=$local;USERPROFILE=$privateUser;HOME=$privateUser}
$start=Get-Date
$proc=Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c ""'+$cmd+'""') -WorkingDirectory $evidence -WindowStyle Hidden -Environment $environment -PassThru
try{$proc.PriorityClass=[Diagnostics.ProcessPriorityClass]::AboveNormal}catch{}
$proc.WaitForExit();$proc.Refresh();$end=Get-Date

$required=@('a0005-post-route.bit','a0005-post-route.bin','a0005-route-bit-status.rpt','timing-summary-post-route.rpt','route-status-post-route.rpt','pulse-width-post-route.rpt','check-timing-post-route.rpt','drc-post-route.rpt','clocks-post-route.rpt','clock-interaction-post-route.rpt','slow200-to-slow200-setup-post-route.rpt','slow200-to-slow200-hold-post-route.rpt','fast400-to-fast400-setup-post-route.rpt','fast400-to-fast400-hold-post-route.rpt','slow200-to-fast400-setup-post-route.rpt','slow200-to-fast400-hold-post-route.rpt','fast400-to-slow200-setup-post-route.rpt','fast400-to-slow200-hold-post-route.rpt','congestion-post-route.rpt','cdc-post-route.rpt','bus-skew-post-route.rpt','utilization-post-route.rpt')
$missing=@($required|Where-Object{!(Test-Path (Join-Path $evidence $_) -PathType Leaf)})
$log=if(Test-Path $stdout){Get-Content $stdout -Raw}else{''}; $token=$log.Contains('A0005_ROUTE_BIT_PASS'); $errors=($log-match'(?m)^(ERROR:|FATAL:)')
$ltx=@(Get-ChildItem $evidence -Filter '*.ltx' -File -ErrorAction SilentlyContinue)
$pass=($proc.ExitCode-eq0-and$token-and!$errors-and!$missing.Count-and!$ltx.Count)
$artifacts=@([ordered]@{name='a0005-post-route.dcp';path=$routedDcp;bytes=(Get-Item $routedDcp).Length;sha256=$expectedDcpSha})
$artifacts+=@(Get-ChildItem $evidence -File|ForEach-Object{[ordered]@{name=$_.Name;path=$_.FullName;bytes=$_.Length;sha256=Sha $_.FullName}})
$receipt=[ordered]@{schema='cnn-v10.5-a0005-preg-routed-finalize-bit-receipt-v1';pass=$pass;tool_exit=$proc.ExitCode;route_rerun=$false;board_accessed=$false;hardware_programmed=$false;completion_token_found=$token;error_marker_found=$errors;missing_outputs=$missing;ltx_count=$ltx.Count;input=[ordered]@{routed_dcp_sha256=$expectedDcpSha;route_attempt_receipt_sha256=$expectedReceiptSha;route_timing_sha256=$expectedTimingSha;route_status_sha256=$expectedRouteStatusSha};source=[ordered]@{runner_sha256=$runnerSha;tcl_sha256=$tclSha};started_utc=$start.ToUniversalTime().ToString('o');finished_utc=$end.ToUniversalTime().ToString('o');elapsed_seconds=($end-$start).TotalSeconds;artifacts=$artifacts}
WriteUtf8 (Join-Path $evidence 'receipt.json') (($receipt|ConvertTo-Json -Depth 10)+"`n")
if(!$pass){throw "A0005 routed-DCP bit finalization failed: $(Join-Path $evidence 'receipt.json')"}
