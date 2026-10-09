[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$WorkDir,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedHalf2xSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedPrimitiveSha256,
    [ValidatePattern('^$|^[0-9a-fA-F]{64}$')][string]$ExpectedTbSha256='',
    [int]$AllowedVivadoPid=0,
    [string]$VivadoRoot='D:\Vivado\2026.1\Vivado',
    [double]$MinimumPhysicalGiB=4.0
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$experiment=[IO.Path]::GetFullPath($PSScriptRoot)
$acceleration=[IO.Path]::GetFullPath((Join-Path $experiment '..\..'))
$half2x=Join-Path $experiment 'cnn_v10_pw_dsp16_half2x.v'
$primitive=Join-Path $acceleration 'cnn_v10_pw_dsp16.v'
$tb=Join-Path $experiment 'tb_cnn_v10_pw_dsp16_half2x.sv'
$memoryHelper=Join-Path $acceleration 'task_tool_memory.ps1'
$errorModeHelper=Join-Path $acceleration 'task_tool_error_mode.ps1'
$xvlog=Join-Path $VivadoRoot 'bin\xvlog.bat'
$xelab=Join-Path $VivadoRoot 'bin\xelab.bat'
$xsim=Join-Path $VivadoRoot 'bin\xsim.bat'
$glbl=Join-Path $VivadoRoot 'data\verilog\src\glbl.v'
$evidence=[IO.Path]::GetFullPath($EvidenceDir)
$work=[IO.Path]::GetFullPath($WorkDir)

function Get-Sha256([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Require-File([string]$Path){if(!(Test-Path -LiteralPath $Path -PathType Leaf)){throw "Missing file: $Path"}}
function Write-Utf8NoBom([string]$Path,[string]$Text){[IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))}
function Assert-NoHeavyOwner {
    # Independent xsim jobs use private work/xsim.dir trees and may coexist.
    # Compilation/elaboration and Vivado/HLS still retain a single owner.
    $heavy=@('vivado','vitis_hls','v++','vitis-run','xcd','xvlog','xelab')
    $active=@(Get-Process -ErrorAction SilentlyContinue|Where-Object{$heavy -contains $_.ProcessName.ToLowerInvariant()})
    $unexpected=@($active|Where-Object{!($AllowedVivadoPid-gt0-and$_.ProcessName-eq'vivado'-and$_.Id-eq$AllowedVivadoPid)})
    if($unexpected.Count){throw "Another AMD heavy-tool owner is active: $($unexpected.ProcessName -join ', ')"}
    if($AllowedVivadoPid-gt0-and!(@($active|Where-Object{$_.ProcessName-eq'vivado'-and$_.Id-eq$AllowedVivadoPid}).Count)) {
        throw "Allowed Vivado PID is absent: $AllowedVivadoPid"
    }
}
function Invoke-HiddenTool([string]$Name,[string]$Executable,[string[]]$Arguments,[string]$Log){
    $quoted=@($Arguments|ForEach-Object{if($_ -match '[\s"]'){'"'+($_ -replace '"','\"')+'"'}else{$_}})
    $cmd=Join-Path $work "$Name.cmd"
    Write-Utf8NoBom $cmd ("@echo off`r`ncall `"$Executable`" "+($quoted -join ' ')+" > `"$Log`" 2>&1`r`nset TOOL_EXIT=%ERRORLEVEL%`r`nexit /b %TOOL_EXIT%`r`n")
    $process=Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c ""'+$cmd+'""') -WorkingDirectory $work -WindowStyle Hidden -PassThru
    try{$process.PriorityClass=[Diagnostics.ProcessPriorityClass]::BelowNormal}catch{}
    $process.WaitForExit(); $process.Refresh()
    $text=if(Test-Path -LiteralPath $Log){Get-Content -LiteralPath $Log -Raw}else{''}
    [ordered]@{name=$Name;exit_code=$process.ExitCode;log=$Log;log_sha256=$(if(Test-Path -LiteralPath $Log){Get-Sha256 $Log}else{$null});error_marker_found=($text-match'(?m)^(ERROR:|FATAL:)')}
}

foreach($path in @($half2x,$primitive,$tb,$memoryHelper,$errorModeHelper,$xvlog,$xelab,$xsim,$glbl)){Require-File $path}
if(Test-Path -LiteralPath $evidence){throw "EvidenceDir already exists: $evidence"}
if(Test-Path -LiteralPath $work){throw "WorkDir already exists: $work"}
if((Get-Sha256 $half2x)-ne$ExpectedHalf2xSha256.ToLowerInvariant()){throw 'Half2x RTL SHA mismatch'}
if((Get-Sha256 $primitive)-ne$ExpectedPrimitiveSha256.ToLowerInvariant()){throw 'Primitive RTL SHA mismatch'}
if($ExpectedTbSha256 -and (Get-Sha256 $tb)-ne$ExpectedTbSha256.ToLowerInvariant()){throw 'Testbench SHA mismatch'}
. $memoryHelper
. $errorModeHelper
$null=Enable-FzTaskToolErrorMode
$launchMemory=Assert-FzTaskMemoryForLaunch -MinimumPhysicalGiB $MinimumPhysicalGiB
Assert-NoHeavyOwner

New-Item -ItemType Directory -Path $evidence,$work|Out-Null
$snapshot=Join-Path $evidence 'source-snapshot'
New-Item -ItemType Directory -Path $snapshot|Out-Null
$snapshotPrimitive=Join-Path $snapshot 'cnn_v10_pw_dsp16.v'
$snapshotHalf2x=Join-Path $snapshot 'cnn_v10_pw_dsp16_half2x.v'
$snapshotTb=Join-Path $snapshot 'tb_cnn_v10_pw_dsp16_half2x.sv'
$snapshotGlbl=Join-Path $snapshot 'glbl.v'
Copy-Item -LiteralPath $primitive -Destination $snapshotPrimitive
Copy-Item -LiteralPath $half2x -Destination $snapshotHalf2x
Copy-Item -LiteralPath $tb -Destination $snapshotTb
Copy-Item -LiteralPath $glbl -Destination $snapshotGlbl

$sourceFiles=@($snapshotPrimitive,$snapshotHalf2x,$snapshotTb,$snapshotGlbl)
$sourceManifest=[ordered]@{
    schema='cnn-v10-pw-half2x-unisim-sources-v1'
    clock_contract=[ordered]@{slow_mhz=200;fast_mhz=400;phase='same-origin coincident rising edges; midpoint fast edge is phase0'}
    files=@($sourceFiles|ForEach-Object{[ordered]@{path=$_;sha256=Get-Sha256 $_}})
}
Write-Utf8NoBom (Join-Path $evidence 'source-manifest.json') ($sourceManifest|ConvertTo-Json -Depth 8)

$xvlogLog=Join-Path $evidence 'xvlog.log'
$xelabLog=Join-Path $evidence 'xelab.log'
$xsimLauncherLog=Join-Path $evidence 'xsim-launcher.log'
$xsimLog=Join-Path $evidence 'xsim.log'
$wdb=Join-Path $evidence 'pw-half2x-unisim.wdb'
$tools=@()
$tools+=Invoke-HiddenTool 'xvlog' $xvlog @('--sv',$snapshotPrimitive,$snapshotHalf2x,$snapshotTb,$snapshotGlbl) $xvlogLog
if($tools[-1].exit_code-ne0 -or $tools[-1].error_marker_found){throw 'xvlog failed'}
$tools+=Invoke-HiddenTool 'xelab' $xelab @('-mt','8','-O3','--debug','off','--timescale','1ns/1ps','-L','unisims_ver','--top','tb_cnn_v10_pw_dsp16_half2x','--top','glbl','--snapshot','pw_half2x_unisim') $xelabLog
if($tools[-1].exit_code-ne0 -or $tools[-1].error_marker_found){throw 'xelab failed'}
$tools+=Invoke-HiddenTool 'xsim' $xsim @('pw_half2x_unisim','--xsimdir',(Join-Path $work 'xsim.dir'),'--log',$xsimLog,'--wdb',$wdb,'--onerror','quit','--runall') $xsimLauncherLog

$simText=if(Test-Path -LiteralPath $xsimLog){Get-Content -LiteralPath $xsimLog -Raw}else{''}
$passToken=($simText-match'CNN_V10_PW_HALF2X_UNISIM_PASS')
$fatalMarker=($simText-match'(?m)^(FATAL:|ERROR:|\$fatal)')
$allToolsPassed=(@($tools|Where-Object{$_.exit_code-ne0 -or $_.error_marker_found}).Count-eq0)
$wdbPresent=Test-Path -LiteralPath $wdb
# The design is elaborated with --debug off for throughput.  XSIM is allowed
# to omit the WDB in that mode, so the functional gate is the simulator exit,
# PASS token, and absence of fatal/error markers.  Record any WDB as optional
# collateral rather than turning its absence into a false product failure.
$pass=$allToolsPassed -and $passToken -and -not $fatalMarker
$outputs=@(Get-ChildItem -LiteralPath $evidence -File|ForEach-Object{[ordered]@{name=$_.Name;size=$_.Length;sha256=Get-Sha256 $_}})
$receipt=[ordered]@{
    schema='cnn-v10-pw-half2x-unisim-receipt-v1';pass=$pass;created_utc=(Get-Date).ToUniversalTime().ToString('o')
    target_part='xazu3eg-sfvc784-1-i';simulation='UNISIM functional';elaboration_threads=8;process_priority='BelowNormal';window_style='Hidden'
    source_manifest_sha256=Get-Sha256 (Join-Path $evidence 'source-manifest.json');half2x_sha256=Get-Sha256 $snapshotHalf2x;primitive_sha256=Get-Sha256 $snapshotPrimitive;tb_sha256=Get-Sha256 $snapshotTb
    checks=@('continuous II=1','signed extrema and prior','exact code and ordering','inclusive latency=8','random full-cycle CE pause','mid-transaction CE pause','mid-transaction synchronous reset','bounded result FIFO/deadline assertions')
    launch_memory=$launchMemory;tools=$tools;pass_token_found=$passToken;fatal_marker_found=$fatalMarker;wdb_required=$false;wdb_present=$wdbPresent;outputs=$outputs
}
$receiptPath=Join-Path $evidence 'receipt.json'
Write-Utf8NoBom $receiptPath ($receipt|ConvertTo-Json -Depth 10)
if(!$pass){throw "UNISIM simulation failed; receipt: $receiptPath"}
Write-Host "PW_HALF2X_UNISIM_COMPLETE receipt=$receiptPath"
