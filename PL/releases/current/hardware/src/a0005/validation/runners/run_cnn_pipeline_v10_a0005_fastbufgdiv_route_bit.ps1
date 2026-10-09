[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [ValidateSet('A0005_ROUTE_AND_BIT_APPROVED')][string]$OwnerReleaseToken,
    [string]$PlaceEvidenceDir='artifacts/board-debug-20261008/acceleration/jtag/cnn-v10.5-a0005-fastbufgdiv-fresh-place-001',
    [int[]]$AllowedVivadoPid=@(),
    [string]$VivadoRoot='D:\Vivado\2026.1\Vivado'
)

Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Need([string]$Path){if(!(Test-Path -LiteralPath $Path -PathType Leaf)){throw "Missing file: $Path"}}
function WriteUtf8([string]$Path,[string]$Text){[IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))}

if($OwnerReleaseToken-ne'A0005_ROUTE_AND_BIT_APPROVED'){
    throw 'Route/bit requires explicit owner release token A0005_ROUTE_AND_BIT_APPROVED'
}

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..\..\..'))
$tcl=Join-Path $PSScriptRoot 'route_bit_cnn_pipeline_v10_a0005_fastbufgdiv.tcl'
$placeEvidence=[IO.Path]::GetFullPath($(if([IO.Path]::IsPathRooted($PlaceEvidenceDir)){$PlaceEvidenceDir}else{Join-Path $repo $PlaceEvidenceDir}))
$inputDcp=Join-Path $placeEvidence 'half2x-fresh-rqs-post-physopt.dcp'
$placeStatus=Join-Path $placeEvidence 'fresh-rqs-place-status.rpt'
$launchContract=Join-Path $placeEvidence 'launch-contract.json'
$placeTcl=Join-Path $placeEvidence 'place-a0005-fresh.tcl'
$expectedInputDcpSha='c0216b79efb22ec4964a1f4c14edf5cd155034bec929bb5db1cd200f37bb18dd'
$expectedPlaceStatusSha='e4ffa2329b29ad073ecb82fcd572c01c8450e3157b76c8aaafae6bc1eb62d09a'
$expectedLaunchContractSha='c0b71d18ca916177df34c9755ce5594f19b30b5cac9ff8f154083351797ceb13'
$expectedPlaceTclSha='da6c721a3238501e6c795c020f5c9c04fc8491945b481e9e0c434b00d8dade16'
$vivado=Join-Path $VivadoRoot 'bin\vivado.bat'
foreach($file in @($tcl,$inputDcp,$placeStatus,$launchContract,$placeTcl,$vivado)){Need $file}
if((Sha $inputDcp)-ne$expectedInputDcpSha){throw 'A0005 post-physopt DCP SHA mismatch'}
if((Sha $placeStatus)-ne$expectedPlaceStatusSha){throw 'A0005 place status SHA mismatch'}
if((Sha $launchContract)-ne$expectedLaunchContractSha){throw 'A0005 place launch-contract SHA mismatch'}
if((Sha $placeTcl)-ne$expectedPlaceTclSha){throw 'A0005 place Tcl snapshot SHA mismatch'}

$statusText=Get-Content -LiteralPath $placeStatus -Raw
foreach($token in @(
    'status=HALF2X_FUSED_ALU_PL1_BALANCED_RQS_PLACE_COMPLETE',
    'synth_dcp_sha256=879d19b56e7b50d3cb89c3c3ea0afe20df3f43c92b06af9424e3082fd34d19d0',
    'half2x_unit_count=16','clock_topology=mmcm_fast_plus_bufgce_div_v1',
    'incremental_reference_used=false','applied_suggestion_count=6','failed_suggestion_count=4',
    'maximum_congestion_level=5','level5_or_worse_window_count=4','route_launched=false'
)){
    if(!$statusText.Contains($token)){throw "A0005 place status lacks frozen token: $token"}
}

$evidence=[IO.Path]::GetFullPath($EvidenceDir)
if(Test-Path -LiteralPath $evidence){throw 'EvidenceDir must be new'}
$existing=@(Get-Process -Name vivado -ErrorAction SilentlyContinue)
$unexpected=@($existing|Where-Object{$AllowedVivadoPid-notcontains$_.Id})
if($unexpected.Count){throw "Unexpected Vivado owner active: $($unexpected.Id -join ',')"}

New-Item -ItemType Directory -Path $evidence|Out-Null
$snapshotDir=Join-Path $evidence 'source-snapshot'
New-Item -ItemType Directory -Path $snapshotDir|Out-Null
$runnerSnapshot=Join-Path $snapshotDir 'run_cnn_pipeline_v10_a0005_fastbufgdiv_route_bit.ps1'
$tclSnapshot=Join-Path $snapshotDir 'route_bit_cnn_pipeline_v10_a0005_fastbufgdiv.tcl'
Copy-Item -LiteralPath $PSCommandPath -Destination $runnerSnapshot
Copy-Item -LiteralPath $tcl -Destination $tclSnapshot
Copy-Item -LiteralPath $placeStatus -Destination (Join-Path $snapshotDir 'fresh-rqs-place-status.rpt')
Copy-Item -LiteralPath $launchContract -Destination (Join-Path $snapshotDir 'place-launch-contract.json')
Copy-Item -LiteralPath $placeTcl -Destination (Join-Path $snapshotDir 'place-a0005-fresh.tcl')
$sourceHashes=[ordered]@{
    runner=Sha $runnerSnapshot;tcl=Sha $tclSnapshot;input_dcp=$expectedInputDcpSha
    place_status=Sha (Join-Path $snapshotDir 'fresh-rqs-place-status.rpt')
    place_launch_contract=Sha (Join-Path $snapshotDir 'place-launch-contract.json')
    place_tcl=Sha (Join-Path $snapshotDir 'place-a0005-fresh.tcl')
}
if($sourceHashes.runner-ne(Sha $PSCommandPath)-or$sourceHashes.tcl-ne(Sha $tcl)){throw 'Launch script snapshot hash mismatch'}

$privateUser=Join-Path $evidence 'private-user'
$privateRoaming=Join-Path $privateUser 'AppData\Roaming'
$privateLocal=Join-Path $privateUser 'AppData\Local'
$manifest=Join-Path $privateRoaming 'Xilinx\Vivado\tclapp\manifest.tcl'
New-Item -ItemType Directory -Path (Split-Path -Parent $manifest),$privateLocal -Force|Out-Null
WriteUtf8 $manifest "::tclapp::load_app -namespace {aldec::activehdl} aldec::activehdl`r`n"
if((Sha $manifest)-ne'b5f010dae71150c1d13d04420150bde07e624fb0b0a1ced3949fcd464d8411b6'){throw 'Private Vivado manifest SHA mismatch'}

$stdout=Join-Path $evidence 'vivado.stdout.log'
$nativeLog=Join-Path $evidence 'vivado.log'
$journal=Join-Path $evidence 'vivado.jou'
$cmd=Join-Path $evidence 'invoke-vivado.cmd'
$arguments=@('-mode','batch','-log',$nativeLog,'-journal',$journal,'-notrace','-source',$tclSnapshot,'-tclargs',$inputDcp,$expectedInputDcpSha,$evidence)
$quoted=@($arguments|ForEach-Object{if($_-match'[\s",]'){('"'+($_-replace'"','\"')+'"')}else{$_}})
WriteUtf8 $cmd ("@echo off`r`ncall `"$vivado`" "+($quoted-join' ')+" > `"$stdout`" 2>&1`r`nexit /b %ERRORLEVEL%`r`n")

$launch=[ordered]@{
    schema='cnn-v10.5-a0005-fastbufgdiv-route-bit-launch-v1';owner_release_token=$OwnerReleaseToken
    board_accessed=$false;hardware_programming_requested=$false;ltx_requested=$false
    route_requested=$true;bit_requested=$true;bin_requested=$true
    route_mode='nonincremental_from_frozen_post_physopt';route_directive='MoreGlobalIterations';jobs=1
    threads=[ordered]@{general_supported=16;synth_supported=8;implementation_effective=8}
    input=[ordered]@{post_phys_dcp=$inputDcp;post_phys_dcp_sha256=$expectedInputDcpSha;place_status_sha256=$expectedPlaceStatusSha;place_launch_contract_sha256=$expectedLaunchContractSha;place_tcl_sha256=$expectedPlaceTclSha}
    required_gates=@('16 fused units','128 fused DSP48E2 PREG=1','single MMCM M12/D1/O3','sibling BUFGCE_DIV 1/2','four setup and hold classes >= 0','pulse >= 0','check_timing 0','unrouted 0','routing errors 0','Error/Critical-Warning DRC 0','no debug core','no LTX')
    exactloc_applied_by_route_script=$false;incremental_reference=$null
    source_snapshot=[ordered]@{runner=$runnerSnapshot;runner_sha256=$sourceHashes.runner;tcl=$tclSnapshot;tcl_sha256=$sourceHashes.tcl}
    allowed_existing_vivado=@($existing|ForEach-Object{$_.Id});created_utc=[DateTime]::UtcNow.ToString('o')
}
WriteUtf8 (Join-Path $evidence 'launch-contract.json') (($launch|ConvertTo-Json -Depth 10)+"`n")

$environment=@{APPDATA=$privateRoaming;LOCALAPPDATA=$privateLocal;USERPROFILE=$privateUser;HOME=$privateUser}
$start=Get-Date
$process=Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c ""'+$cmd+'""') -WorkingDirectory $evidence -WindowStyle Hidden -Environment $environment -PassThru
try{$process.PriorityClass=[Diagnostics.ProcessPriorityClass]::AboveNormal}catch{}
WriteUtf8 (Join-Path $evidence 'owned-process.json') (([ordered]@{pid=$process.Id;start_utc=$process.StartTime.ToUniversalTime().ToString('o');priority='AboveNormal'}|ConvertTo-Json)+"`n")
$process.WaitForExit();$process.Refresh()
$end=Get-Date

$required=@(
    'a0005-post-route.dcp','a0005-post-route.bit','a0005-post-route.bin','a0005-route-bit-status.rpt',
    'timing-summary-post-route.rpt','route-status-post-route.rpt','pulse-width-post-route.rpt',
    'check-timing-post-route.rpt','drc-post-route.rpt','clocks-post-route.rpt','clock-interaction-post-route.rpt',
    'slow200-to-slow200-setup-post-route.rpt','slow200-to-slow200-hold-post-route.rpt',
    'fast400-to-fast400-setup-post-route.rpt','fast400-to-fast400-hold-post-route.rpt',
    'slow200-to-fast400-setup-post-route.rpt','slow200-to-fast400-hold-post-route.rpt',
    'fast400-to-slow200-setup-post-route.rpt','fast400-to-slow200-hold-post-route.rpt',
    'congestion-post-route.rpt','cdc-post-route.rpt','bus-skew-post-route.rpt','utilization-post-route.rpt'
)
$missing=@($required|Where-Object{!(Test-Path -LiteralPath (Join-Path $evidence $_) -PathType Leaf)})
$logText=if(Test-Path -LiteralPath $stdout){Get-Content -LiteralPath $stdout -Raw}else{''}
$token=$logText.Contains('A0005_ROUTE_BIT_PASS')
$errorMarker=($logText-match'(?m)^(ERROR:|FATAL:)')
$ltx=@(Get-ChildItem -LiteralPath $evidence -Filter '*.ltx' -File -ErrorAction SilentlyContinue)
$pass=($process.ExitCode-eq0-and$token-and!$errorMarker-and!$missing.Count-and!$ltx.Count)
$outputs=@(Get-ChildItem -LiteralPath $evidence -File|ForEach-Object{[ordered]@{name=$_.Name;bytes=$_.Length;sha256=Sha $_.FullName}})
$receipt=[ordered]@{
    schema='cnn-v10.5-a0005-fastbufgdiv-route-bit-receipt-v1';pass=$pass
    scope='Offline route/bit/bin signoff only; no board access and no LTX'
    tool_exit=$process.ExitCode;completion_token_found=$token;error_marker_found=$errorMarker;missing_outputs=$missing;ltx_count=$ltx.Count
    threads=[ordered]@{general_supported=16;synth_supported=8;implementation_effective=8;jobs=1}
    input=[ordered]@{post_phys_dcp_sha256=$expectedInputDcpSha;place_status_sha256=$expectedPlaceStatusSha;place_launch_contract_sha256=$expectedLaunchContractSha;place_tcl_sha256=$expectedPlaceTclSha}
    source_snapshot_sha256=$sourceHashes;incremental_reference=$null;exactloc_applied_by_route_script=$false
    board_accessed=$false;hardware_programmed=$false
    started_utc=$start.ToUniversalTime().ToString('o');finished_utc=$end.ToUniversalTime().ToString('o');elapsed_seconds=($end-$start).TotalSeconds
    outputs=$outputs
}
WriteUtf8 (Join-Path $evidence 'receipt.json') (($receipt|ConvertTo-Json -Depth 10)+"`n")
if(!$pass){throw "A0005 route/bit failed: $(Join-Path $evidence 'receipt.json')"}
Write-Output "A0005_ROUTE_BIT_RUNNER_COMPLETE receipt=$(Join-Path $evidence 'receipt.json')"
