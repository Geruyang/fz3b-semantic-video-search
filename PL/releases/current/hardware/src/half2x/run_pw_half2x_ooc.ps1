[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$WorkDir,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedHalf2xSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedPrimitiveSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedWrapperSha256,
    [ValidatePattern('^$|^[0-9a-fA-F]{64}$')][string]$ExpectedTclSha256='',
    [string]$VivadoRoot='D:\Vivado\2026.1\Vivado',
    [double]$MinimumPhysicalGiB=8.0
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$experiment=[IO.Path]::GetFullPath($PSScriptRoot)
$acceleration=[IO.Path]::GetFullPath((Join-Path $experiment '..\..'))
$half2x=Join-Path $experiment 'cnn_v10_pw_dsp16_half2x.v'
$primitive=Join-Path $acceleration 'cnn_v10_pw_dsp16.v'
$wrapper=Join-Path $experiment 'cnn_v10_pw_dsp16_half2x_ooc_wrapper.v'
$tcl=Join-Path $experiment 'pw_half2x_ooc.tcl'
$memoryHelper=Join-Path $acceleration 'task_tool_memory.ps1'
$errorModeHelper=Join-Path $acceleration 'task_tool_error_mode.ps1'
$vivado=Join-Path $VivadoRoot 'bin\vivado.bat'
$evidence=[IO.Path]::GetFullPath($EvidenceDir)
$work=[IO.Path]::GetFullPath($WorkDir)

function Get-Sha256([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Require-File([string]$Path){if(!(Test-Path -LiteralPath $Path -PathType Leaf)){throw "Missing file: $Path"}}
function Write-Utf8NoBom([string]$Path,[string]$Text){[IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))}
function Assert-NoHeavyOwner {
    # A private background XSIM can coexist with this isolated OOC project.
    # Retain a single owner for Vivado/HLS/compile/elaboration processes.
    $heavy=@('vivado','vitis_hls','v++','vitis-run','xcd','xvlog','xelab')
    $active=@(Get-Process -ErrorAction SilentlyContinue|Where-Object{$heavy -contains $_.ProcessName.ToLowerInvariant()})
    if($active.Count){throw "Another AMD heavy-tool owner is active: $($active.ProcessName -join ', ')"}
}

foreach($path in @($half2x,$primitive,$wrapper,$tcl,$memoryHelper,$errorModeHelper,$vivado)){Require-File $path}
if(Test-Path -LiteralPath $evidence){throw "EvidenceDir already exists: $evidence"}
if(Test-Path -LiteralPath $work){throw "WorkDir already exists: $work"}
if((Get-Sha256 $half2x)-ne$ExpectedHalf2xSha256.ToLowerInvariant()){throw 'Half2x RTL SHA mismatch'}
if((Get-Sha256 $primitive)-ne$ExpectedPrimitiveSha256.ToLowerInvariant()){throw 'Primitive RTL SHA mismatch'}
if((Get-Sha256 $wrapper)-ne$ExpectedWrapperSha256.ToLowerInvariant()){throw 'OOC wrapper RTL SHA mismatch'}
if($ExpectedTclSha256 -and (Get-Sha256 $tcl)-ne$ExpectedTclSha256.ToLowerInvariant()){throw 'OOC Tcl SHA mismatch'}
. $memoryHelper
. $errorModeHelper
$null=Enable-FzTaskToolErrorMode
$launchMemory=Assert-FzTaskMemoryForLaunch -MinimumPhysicalGiB $MinimumPhysicalGiB
Assert-NoHeavyOwner

New-Item -ItemType Directory -Path $evidence,$work|Out-Null
$privateRoot=Join-Path $work 'private-profile'
$privateRoaming=Join-Path $privateRoot 'Roaming'
$privateLocal=Join-Path $privateRoot 'Local'
$privateUser=Join-Path $privateRoot 'User'
$privateTclapp=Join-Path $privateRoaming 'Xilinx\Vivado\tclapp'
New-Item -ItemType Directory -Path $privateRoaming,$privateLocal,$privateUser,$privateTclapp -Force|Out-Null
$privateManifest=Join-Path $privateTclapp 'manifest.tcl'
Write-Utf8NoBom $privateManifest "# Task-local empty Vivado Tcl app manifest.`r`n"
$privateManifestInitialSha=Get-Sha256 $privateManifest
$snapshot=Join-Path $evidence 'source-snapshot'
New-Item -ItemType Directory -Path $snapshot|Out-Null
$snapshotPrimitive=Join-Path $snapshot 'cnn_v10_pw_dsp16.v'
$snapshotHalf2x=Join-Path $snapshot 'cnn_v10_pw_dsp16_half2x.v'
$snapshotWrapper=Join-Path $snapshot 'cnn_v10_pw_dsp16_half2x_ooc_wrapper.v'
$snapshotTcl=Join-Path $snapshot 'pw_half2x_ooc.tcl'
Copy-Item -LiteralPath $primitive -Destination $snapshotPrimitive
Copy-Item -LiteralPath $half2x -Destination $snapshotHalf2x
Copy-Item -LiteralPath $wrapper -Destination $snapshotWrapper
Copy-Item -LiteralPath $tcl -Destination $snapshotTcl

$sourceFiles=@($snapshotPrimitive,$snapshotHalf2x,$snapshotWrapper,$snapshotTcl)
$sourceManifest=[ordered]@{
    schema='cnn-v10-pw-half2x-ooc-sources-v1';target_part='xazu3eg-sfvc784-1-i'
    clock_contract=[ordered]@{slow_mhz=200;fast_mhz=400;phase='same-origin coincident rising edges; midpoint fast edge is phase0'}
    general_threads=16;synthesis_threads=8;jobs=1
    files=@($sourceFiles|ForEach-Object{[ordered]@{path=$_;sha256=Get-Sha256 $_}})
}
$sourceManifestPath=Join-Path $evidence 'source-manifest.json'
Write-Utf8NoBom $sourceManifestPath ($sourceManifest|ConvertTo-Json -Depth 8)

$vivadoLog=Join-Path $evidence 'vivado-ooc.log'
$launcherLog=Join-Path $evidence 'vivado-launcher.log'
$launcher=Join-Path $work 'launch-vivado-ooc.cmd'
$args=@('-mode','batch','-nolog','-nojournal','-notrace','-source',$snapshotTcl,'-tclargs',$snapshotPrimitive,$snapshotHalf2x,$snapshotWrapper,$work)
$quoted=@($args|ForEach-Object{if($_ -match '[\s"]'){'"'+($_ -replace '"','\"')+'"'}else{$_}})
Write-Utf8NoBom $launcher ("@echo off`r`ncall `"$vivado`" "+($quoted -join ' ')+" > `"$launcherLog`" 2>&1`r`nset TOOL_EXIT=%ERRORLEVEL%`r`nexit /b %TOOL_EXIT%`r`n")
$childEnvironment=@{APPDATA=$privateRoaming;LOCALAPPDATA=$privateLocal;USERPROFILE=$privateUser;HOME=$privateUser}
$process=Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c ""'+$launcher+'""') -WorkingDirectory $work -WindowStyle Hidden -PassThru -Environment $childEnvironment
try{$process.PriorityClass=[Diagnostics.ProcessPriorityClass]::BelowNormal}catch{}
$process.WaitForExit(); $process.Refresh()
if(Test-Path -LiteralPath $launcherLog){Copy-Item -LiteralPath $launcherLog -Destination $vivadoLog}
$logText=if(Test-Path -LiteralPath $vivadoLog){Get-Content -LiteralPath $vivadoLog -Raw}else{''}
$completeToken=($logText-match'PW_HALF2X_OOC_COMPLETE')
$errorMarker=($logText-match'(?m)^(ERROR:|FATAL:)')

$required=@(
    'pw_half2x-post-synth.dcp','pw_half2x-routed.dcp','pw_half2x-contract.txt',
    'utilization-post-synth.rpt','utilization-post-route.rpt',
    'timing-summary-post-route.rpt','setup-slow_clk-post-route.rpt',
    'hold-slow_clk-post-route.rpt','setup-fast_clk-post-route.rpt',
    'hold-fast_clk-post-route.rpt','setup-slow_clk-to-fast_clk-post-route.rpt',
    'hold-slow_clk-to-fast_clk-post-route.rpt','setup-fast_clk-to-slow_clk-post-route.rpt',
    'hold-fast_clk-to-slow_clk-post-route.rpt','pulse-width-post-route.rpt',
    'clock-interaction-post-route.rpt','cdc-post-route.rpt','check-timing-post-route.rpt',
    'route-status-post-route.rpt','drc-post-route.rpt','clock-utilization-post-route.rpt'
)
$missing=@($required|Where-Object{!(Test-Path -LiteralPath (Join-Path $work $_) -PathType Leaf)})
$timingText=if(Test-Path -LiteralPath (Join-Path $work 'timing-summary-post-route.rpt')){Get-Content -LiteralPath (Join-Path $work 'timing-summary-post-route.rpt') -Raw}else{''}
$timingMatch=[regex]::Match($timingText,'(?m)^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\d+\s+\d+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\d+\s+\d+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\d+\s+\d+\s*$')
$timing=[ordered]@{parsed=$timingMatch.Success;wns_ns=$null;tns_ns=$null;whs_ns=$null;ths_ns=$null;wpws_ns=$null;tpws_ns=$null}
if($timingMatch.Success){
    $timing.wns_ns=[double]::Parse($timingMatch.Groups[1].Value,[Globalization.CultureInfo]::InvariantCulture)
    $timing.tns_ns=[double]::Parse($timingMatch.Groups[2].Value,[Globalization.CultureInfo]::InvariantCulture)
    $timing.whs_ns=[double]::Parse($timingMatch.Groups[3].Value,[Globalization.CultureInfo]::InvariantCulture)
    $timing.ths_ns=[double]::Parse($timingMatch.Groups[4].Value,[Globalization.CultureInfo]::InvariantCulture)
    $timing.wpws_ns=[double]::Parse($timingMatch.Groups[5].Value,[Globalization.CultureInfo]::InvariantCulture)
    $timing.tpws_ns=[double]::Parse($timingMatch.Groups[6].Value,[Globalization.CultureInfo]::InvariantCulture)
}
$routeText=if(Test-Path -LiteralPath (Join-Path $work 'route-status-post-route.rpt')){Get-Content -LiteralPath (Join-Path $work 'route-status-post-route.rpt') -Raw}else{''}
$routeErrorsMatch=[regex]::Match($routeText,'# of nets with routing errors\.+\s*:\s*(\d+)')
$routeErrors=if($routeErrorsMatch.Success){[int]$routeErrorsMatch.Groups[1].Value}else{$null}
$checkText=if(Test-Path -LiteralPath (Join-Path $work 'check-timing-post-route.rpt')){Get-Content -LiteralPath (Join-Path $work 'check-timing-post-route.rpt') -Raw}else{''}
$forbiddenTimingChecks=@('no_clock','constant_clock','pulse_width_clock','unconstrained_internal_endpoints','multiple_clock','generated_clocks','loops','partial_input_delay','partial_output_delay','latch_loops')
$checkTimingViolations=@($forbiddenTimingChecks|Where-Object{$checkText-notmatch("checking "+[regex]::Escape($_)+" \(0\)")})
$drcText=if(Test-Path -LiteralPath (Join-Path $work 'drc-post-route.rpt')){Get-Content -LiteralPath (Join-Path $work 'drc-post-route.rpt') -Raw}else{''}
$drcErrors=([regex]::Matches($drcText,'(?m)^[A-Z0-9_-]+#\d+ Error$')).Count
$artifacts=@(Get-ChildItem -LiteralPath $work -File|Where-Object{$_.Extension -in @('.dcp','.rpt','.txt','.xdc')}|ForEach-Object{[ordered]@{name=$_.Name;size=$_.Length;sha256=Get-Sha256 $_.FullName}})
$timingPass=$timing.parsed -and $timing.wns_ns-ge0 -and $timing.whs_ns-ge0 -and $timing.wpws_ns-ge0
$pass=($process.ExitCode-eq0) -and $completeToken -and -not $errorMarker -and ($missing.Count-eq0) -and $timingPass -and ($routeErrors-eq0) -and ($checkTimingViolations.Count-eq0) -and ($drcErrors-eq0)
$receipt=[ordered]@{
    schema='cnn-v10-pw-half2x-ooc-receipt-v1';pass=$pass;created_utc=(Get-Date).ToUniversalTime().ToString('o')
    target_part='xazu3eg-sfvc784-1-i';top='cnn_v10_pw_dsp16_half2x_ooc_wrapper';general_threads=16;synthesis_threads=8;jobs=1;process_priority='BelowNormal';window_style='Hidden'
    clock_contract=[ordered]@{slow_mhz=200;fast_mhz=400;phase='same-origin coincident rising edges; midpoint fast edge is phase0'}
    source_manifest_sha256=Get-Sha256 $sourceManifestPath;half2x_sha256=Get-Sha256 $snapshotHalf2x;primitive_sha256=Get-Sha256 $snapshotPrimitive;wrapper_sha256=Get-Sha256 $snapshotWrapper;tcl_sha256=Get-Sha256 $snapshotTcl
    launch_memory=$launchMemory;private_environment=$childEnvironment;private_empty_manifest_initial_sha256=$privateManifestInitialSha;tool_exit=$process.ExitCode;complete_token_found=$completeToken;error_marker_found=$errorMarker;missing_required_outputs=$missing;timing=$timing;timing_pass=$timingPass;route_errors=$routeErrors;check_timing_forbidden_violations=$checkTimingViolations;drc_error_violations=$drcErrors;artifacts=$artifacts
}
$receiptPath=Join-Path $evidence 'receipt.json'
Write-Utf8NoBom $receiptPath ($receipt|ConvertTo-Json -Depth 10)
if(!$pass){throw "OOC implementation failed; receipt: $receiptPath"}
Write-Host "PW_HALF2X_OOC_RUNNER_COMPLETE receipt=$receiptPath"
