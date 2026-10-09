[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$WorkDir,
    [string]$VitisRoot='D:\Vivado\2026.1\Vitis'
)

$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function Sha([string]$p) { (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant() }
function ConfigPath([string]$p) { ([IO.Path]::GetFullPath($p)).Replace('\','/') }

$here=Split-Path -Parent $MyInvocation.MyCommand.Path
$root=[IO.Path]::GetFullPath((Join-Path $here '..\..\..\..\..'))
$evidence=[IO.Path]::GetFullPath($EvidenceDir)
$work=[IO.Path]::GetFullPath($WorkDir)
if(Test-Path -LiteralPath $evidence){throw 'EvidenceDir must be new'}
if(Test-Path -LiteralPath $work){throw 'WorkDir must be new'}
if(@(Get-Process vivado,vitis_hls,vitis-run,v++,xcd -ErrorAction SilentlyContinue).Count){throw 'AMD heavy tool slot occupied'}
New-Item -ItemType Directory -Path $evidence,$work | Out-Null
$snapshot=Join-Path $evidence 'source-snapshot'
New-Item -ItemType Directory -Path $snapshot | Out-Null
$names=@(
    'pw_half2x_blackbox_smoke.cpp',
    'cnn_v10_pw_dsp_half2x.hpp',
    'cnn_v10_pw_dsp_half2x_model.cpp',
    'cnn_v10_pw_dsp16_half2x.json',
    'cnn_v10_pw_dsp16_half2x_hls.v',
    'cnn_v10_pw_dsp16_half2x.v'
)
foreach($name in $names){Copy-Item -LiteralPath (Join-Path $here $name) -Destination (Join-Path $snapshot $name)}
Copy-Item -LiteralPath (Join-Path $root 'desktop_vlm\hardware\acceleration\cnn_v10_pw_dsp16.v') -Destination (Join-Path $snapshot 'cnn_v10_pw_dsp16.v')
$source=[ordered]@{}
foreach($file in Get-ChildItem -LiteralPath $snapshot -File){$source[$file.Name]=Sha $file.FullName}

$cfg=Join-Path $evidence 'hls.cfg'
$cpp=ConfigPath (Join-Path $snapshot 'pw_half2x_blackbox_smoke.cpp')
$bb=ConfigPath (Join-Path $snapshot 'cnn_v10_pw_dsp16_half2x.json')
$inc=ConfigPath $snapshot
@"
part=xazu3eg-sfvc784-1-i

[hls]
flow_target=vivado
clock=5.000ns
clock_uncertainty=27%
syn.top=pw_half2x_blackbox_smoke
syn.file=$cpp
syn.file_cflags=$cpp,-I$inc
syn.blackbox.file=$bb
syn.compile.pipeline_loops=0
"@ | Set-Content -LiteralPath $cfg -Encoding ascii

$vpp=Join-Path $VitisRoot 'bin\v++.bat'
if(!(Test-Path -LiteralPath $vpp)){throw 'Official v++ entry is missing'}
$manifest=Join-Path $env:APPDATA 'Xilinx\Vivado\tclapp\manifest.tcl'
$backup="$manifest.pw-half2x-smoke-backup"
if(!(Test-Path -LiteralPath $manifest)){throw 'Vivado Tcl app manifest missing'}
if(Test-Path -LiteralPath $backup){throw 'Existing manifest owner'}
$manifestBefore=Sha $manifest
$stdout=Join-Path $evidence 'vpp.stdout.log'
$stderr=Join-Path $evidence 'vpp.stderr.log'
$scriptDir=[IO.Path]::GetFullPath((Join-Path $here '..\..'))
. (Join-Path $scriptDir 'task_tool_error_mode.ps1')
$previous=Enable-FzTaskToolErrorMode
$started=(Get-Date).ToUniversalTime()
$p=$null
try{
    Move-Item -LiteralPath $manifest -Destination $backup
    $args=@('-c','--mode','hls','--config',$cfg,'--work_dir',$work)
    $p=Start-Process -FilePath $vpp -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    try{$p.PriorityClass=[Diagnostics.ProcessPriorityClass]::AboveNormal}catch{}
    $p.WaitForExit();$p.Refresh();$exit=$p.ExitCode
} finally {
    if(Test-Path -LiteralPath $manifest){Copy-Item -LiteralPath $manifest -Destination (Join-Path $evidence 'manifest-generated.tcl');Remove-Item -LiteralPath $manifest -Force}
    if(Test-Path -LiteralPath $backup){Move-Item -LiteralPath $backup -Destination $manifest}
    Restore-FzTaskToolErrorMode -PreviousMode $previous
}
$finished=(Get-Date).ToUniversalTime()
$manifestAfter=Sha $manifest
$top=@(Get-ChildItem -LiteralPath $work -Recurse -File | Where-Object Name -eq 'pw_half2x_blackbox_smoke.v')
$reports=@(Get-ChildItem -LiteralPath $work -Recurse -File -Filter '*_csynth.rpt')
$pass=($exit -eq 0 -and $top.Count -ge 1 -and $reports.Count -gt 0 -and $manifestAfter -eq $manifestBefore)
$receipt=[ordered]@{
    schema='cnn-v10-pw-half2x-hls-clock-smoke-v1';pass=$pass;exit_code=$exit
    started_utc=$started.ToString('o');finished_utc=$finished.ToString('o')
    target_part='xazu3eg-sfvc784-1-i';clock_ns=5.0;clock_uncertainty_percent=27
    source_sha256=$source;manifest_sha256_before=$manifestBefore;manifest_sha256_after=$manifestAfter
    rtl_top=@($top|ForEach-Object{[ordered]@{path=$_.FullName;bytes=$_.Length;sha256=Sha $_.FullName}})
    csynth_reports=@($reports.FullName);work_dir=$work
}
$receipt|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $evidence 'receipt.json') -Encoding utf8
if(!$pass){throw 'Half2x HLS clock-port smoke failed'}
$receipt|ConvertTo-Json -Depth 8 -Compress
