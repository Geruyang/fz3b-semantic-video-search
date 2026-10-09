[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [string]$SynthEvidenceDir='artifacts/board-debug-20261008/acceleration/jtag/cnn-v10.5-a0005-fastbufgdiv-platform-synth-001',
    [int[]]$AllowedVivadoPid=@(),
    [string]$VivadoRoot='D:\Vivado\2026.1\Vivado'
)

Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Need([string]$Path){if(!(Test-Path -LiteralPath $Path -PathType Leaf)){throw "Missing file: $Path"}}
function WriteUtf8([string]$Path,[string]$Text){[IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))}

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..\..\..'))
$script=Join-Path $PSScriptRoot 'place_cnn_pipeline_v10_a0005_fastbufgdiv_fresh.tcl'
$synthEvidence=[IO.Path]::GetFullPath($(if([IO.Path]::IsPathRooted($SynthEvidenceDir)){$SynthEvidenceDir}else{Join-Path $repo $SynthEvidenceDir}))
$synthDcp=Join-Path $synthEvidence 'cnn-pipeline-v10-candidate-post-synth.dcp'
$synthReceipt=Join-Path $synthEvidence 'receipt.json'
$expectedDcpSha='879d19b56e7b50d3cb89c3c3ea0afe20df3f43c92b06af9424e3082fd34d19d0'
$expectedReceiptSha='0d0d67bf20b6f5a0d4c82703782bb272184811a1a14722ac887f1eb70fc72bfa'
$vivado=Join-Path $VivadoRoot 'bin\vivado.bat'
foreach($file in @($script,$synthDcp,$synthReceipt,$vivado)){Need $file}
if((Sha $synthDcp)-ne$expectedDcpSha){throw 'A0005 platform post-synth DCP SHA mismatch'}
if((Sha $synthReceipt)-ne$expectedReceiptSha){throw 'A0005 platform synth receipt SHA mismatch'}
$synthJson=Get-Content -LiteralPath $synthReceipt -Raw|ConvertFrom-Json
if(!$synthJson.pass-or$synthJson.schema-ne'cnn-v10.5-a0005-half2x-fused-fastbufgdiv-platform-synth-only-v1'-or
   $synthJson.a0005_candidate.source_manifest_sha256-ne'f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593'-or
   $synthJson.a0005_candidate.generated_rtl_rom_digest-ne'ef373560fbb68e8719d5497b0d259b8a6dab734b2f88744f9d3505f8143af711'-or
   $synthJson.ip_cache.effective_vlnv-ne'xilinx.com:hls:cnn_pipeline_v10:1.3'-or
   $synthJson.ip_cache.expected_cache_id-ne'19da3790f4593648'-or
   [double]$synthJson.candidate_mhz-ne200.0-or$synthJson.clock_contract-ne'99999001,100000000,12,1,6,3'){
    throw 'A0005 platform synth receipt contract mismatch'
}

$evidence=[IO.Path]::GetFullPath($EvidenceDir)
if(Test-Path -LiteralPath $evidence){throw 'EvidenceDir must be new'}
$existing=@(Get-Process -Name vivado -ErrorAction SilentlyContinue)
$unexpected=@($existing|Where-Object{$AllowedVivadoPid-notcontains$_.Id})
if($unexpected.Count){throw "Unexpected Vivado owner active: $($unexpected.Id -join ',')"}

New-Item -ItemType Directory -Path $evidence|Out-Null
$snapshotDir=Join-Path $evidence 'source-snapshot'
New-Item -ItemType Directory -Path $snapshotDir|Out-Null
$runnerSnapshot=Join-Path $snapshotDir 'run_cnn_pipeline_v10_a0005_fastbufgdiv_fresh_place.ps1'
$tclSnapshot=Join-Path $snapshotDir 'place_cnn_pipeline_v10_a0005_fastbufgdiv_fresh.tcl'
Copy-Item -LiteralPath $PSCommandPath -Destination $runnerSnapshot
Copy-Item -LiteralPath $script -Destination $tclSnapshot
Copy-Item -LiteralPath $synthReceipt -Destination (Join-Path $snapshotDir 'platform-synth-receipt.json')
$sourceHashes=[ordered]@{runner=Sha $runnerSnapshot;tcl=Sha $tclSnapshot;synth_receipt=Sha (Join-Path $snapshotDir 'platform-synth-receipt.json');synth_dcp=$expectedDcpSha}
if($sourceHashes.runner-ne(Sha $PSCommandPath)-or$sourceHashes.tcl-ne(Sha $script)){throw 'Launch script snapshot hash mismatch'}

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
$arguments=@('-mode','batch','-log',$nativeLog,'-journal',$journal,'-notrace','-source',$tclSnapshot,'-tclargs',$synthDcp,$expectedDcpSha,$synthReceipt,$expectedReceiptSha,$evidence)
$quoted=@($arguments|ForEach-Object{if($_-match'[\s",]'){('"'+($_-replace'"','\"')+'"')}else{$_}})
WriteUtf8 $cmd ("@echo off`r`ncall `"$vivado`" "+($quoted-join' ')+" > `"$stdout`" 2>&1`r`nexit /b %ERRORLEVEL%`r`n")

$launch=[ordered]@{
    schema='cnn-v10.5-a0005-fastbufgdiv-fresh-place-launch-v1'
    board_accessed=$false;route_launched=$false;bitstream_written=$false
    implementation_mode='fresh_nonincremental';jobs=1
    threads=[ordered]@{general_supported=16;synth_supported=8;implementation_effective=8}
    source=[ordered]@{synth_evidence=$synthEvidence;synth_dcp=$synthDcp;synth_dcp_sha256=$expectedDcpSha;synth_receipt=$synthReceipt;synth_receipt_sha256=$expectedReceiptSha;source_manifest_sha256='f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593';rtl_rom_digest='ef373560fbb68e8719d5497b0d259b8a6dab734b2f88744f9d3505f8143af711';hls_vlnv='xilinx.com:hls:cnn_pipeline_v10:1.3';cache_id='19da3790f4593648'}
    requested_directives=[ordered]@{opt_design='Explore';place_design='Explore';net_delay_weight='high';phys_opt_design='AggressiveExplore'}
    historical_rqs_used=$false;incremental_reference=$null;exactloc_or_pblock_used=$false
    script_snapshot=[ordered]@{runner=$runnerSnapshot;runner_sha256=$sourceHashes.runner;tcl=$tclSnapshot;tcl_sha256=$sourceHashes.tcl}
    allowed_existing_vivado=@($existing|ForEach-Object{$_.Id})
    created_utc=[DateTime]::UtcNow.ToString('o')
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
    'a0005-opened-post-synth.dcp','a0005-fresh-post-opt.dcp','a0005-fresh-post-place.dcp','a0005-fresh-post-physopt.dcp',
    'a0005-current-design-qor-suggestions.rpt','a0005-current-design-qor-suggestions.rqs','a0005-fresh-place-status.rpt',
    'clocks-post-physopt.rpt','clock-interaction-post-physopt.rpt','timing-summary-post-physopt.rpt',
    'slow200-to-slow200-setup-post-physopt.rpt','slow200-to-slow200-hold-post-physopt.rpt',
    'fast400-to-fast400-setup-post-physopt.rpt','fast400-to-fast400-hold-post-physopt.rpt',
    'slow200-to-fast400-setup-post-physopt.rpt','slow200-to-fast400-hold-post-physopt.rpt',
    'fast400-to-slow200-setup-post-physopt.rpt','fast400-to-slow200-hold-post-physopt.rpt',
    'pulse-width-post-physopt.rpt','check-timing-post-physopt.rpt','congestion-post-physopt.rpt','drc-post-physopt.rpt',
    'utilization-post-physopt.rpt','utilization-hierarchical-post-physopt.rpt','route-status-post-physopt.rpt',
    'timing-constraints-before-place.xdc','timing-constraints-post-physopt.xdc'
)
$missing=@($required|Where-Object{!(Test-Path -LiteralPath (Join-Path $evidence $_) -PathType Leaf)})
$logText=if(Test-Path -LiteralPath $stdout){Get-Content -LiteralPath $stdout -Raw}else{''}
$token=$logText.Contains('A0005_FRESH_PLACE_COMPLETE route=false')
$errorMarker=($logText-match'(?m)^(ERROR:|FATAL:)')
$pass=($process.ExitCode-eq0-and$token-and!$errorMarker-and!$missing.Count)
$outputs=@(Get-ChildItem -LiteralPath $evidence -File|ForEach-Object{[ordered]@{name=$_.Name;bytes=$_.Length;sha256=Sha $_.FullName}})
$receipt=[ordered]@{
    schema='cnn-v10.5-a0005-fastbufgdiv-fresh-place-receipt-v1';pass=$pass
    scope='Offline fresh nonincremental post-synth placement only; no route, bitstream, or board access'
    tool_exit=$process.ExitCode;completion_token_found=$token;error_marker_found=$errorMarker;missing_outputs=$missing
    threads=[ordered]@{general_supported=16;synth_supported=8;implementation_effective=8;jobs=1}
    input=[ordered]@{synth_dcp_sha256=$expectedDcpSha;synth_receipt_sha256=$expectedReceiptSha}
    source_snapshot_sha256=$sourceHashes;route_launched=$false;bitstream_written=$false;board_accessed=$false
    started_utc=$start.ToUniversalTime().ToString('o');finished_utc=$end.ToUniversalTime().ToString('o');elapsed_seconds=($end-$start).TotalSeconds
    outputs=$outputs
}
WriteUtf8 (Join-Path $evidence 'receipt.json') (($receipt|ConvertTo-Json -Depth 10)+"`n")
if(!$pass){throw "A0005 fresh placement failed: $(Join-Path $evidence 'receipt.json')"}
Write-Output "A0005_FRESH_PLACE_RUNNER_COMPLETE receipt=$(Join-Path $evidence 'receipt.json')"
