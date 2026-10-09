[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ActualHalf2xRtl,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedActualSha256,
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$WorkDir,
    [string]$VivadoRoot='D:\Vivado\2026.1\Vivado'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$experiment=[IO.Path]::GetFullPath($PSScriptRoot)
$actual=[IO.Path]::GetFullPath($ActualHalf2xRtl)
$evidence=[IO.Path]::GetFullPath($EvidenceDir)
$work=[IO.Path]::GetFullPath($WorkDir)
$patcher=Join-Path $experiment 'patch_half2x_vector_fastmodel.py'
$tb=Join-Path $experiment 'tb_cnn_v10_pw_half2x_vector_miter.sv'
$xvlog=Join-Path $VivadoRoot 'bin\xvlog.bat'
$xelab=Join-Path $VivadoRoot 'bin\xelab.bat'
$xsim=Join-Path $VivadoRoot 'bin\xsim.bat'
$glbl=Join-Path $VivadoRoot 'data\verilog\src\glbl.v'
function Sha([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function Req([string]$p){if(!(Test-Path -LiteralPath $p -PathType Leaf)){throw "Missing file: $p"}}
function WriteUtf8([string]$p,[string]$s){[IO.File]::WriteAllText($p,$s,(New-Object Text.UTF8Encoding($false)))}
function RunTool([string]$name,[string]$exe,[string[]]$argv,[string]$log){
    $q=@($argv|ForEach-Object{'"'+(([string]$_).Replace('\','/')-replace'"','\"')+'"'})
    $cmd=Join-Path $work "$name.cmd"
    WriteUtf8 $cmd ("@echo off`r`ncall `"$exe`" "+($q-join' ')+" > `"$log`" 2>&1`r`nset E=%ERRORLEVEL%`r`nexit /b %E%`r`n")
    $p=Start-Process $env:ComSpec -ArgumentList('/d /s /c ""'+$cmd+'""') -WorkingDirectory $work -WindowStyle Hidden -PassThru
    try{$p.PriorityClass=[Diagnostics.ProcessPriorityClass]::BelowNormal}catch{}
    $p.WaitForExit();$p.Refresh();$t=if(Test-Path $log){Get-Content $log -Raw}else{''}
    [ordered]@{name=$name;exit_code=$p.ExitCode;log=$log;sha256=$(if(Test-Path $log){Sha $log}else{$null});error=($t-match'(?m)^(ERROR:|FATAL:)')}
}
foreach($p in @($actual,$patcher,$tb,$xvlog,$xelab,$xsim,$glbl)){Req $p}
if((Sha $actual)-ne$ExpectedActualSha256.ToLowerInvariant()){throw 'Actual half2x RTL SHA mismatch'}
if(Test-Path $evidence){throw "Evidence exists: $evidence"};if(Test-Path $work){throw "Work exists: $work"}
New-Item -ItemType Directory -Path $evidence,$work|Out-Null
$snap=Join-Path $evidence 'source-snapshot';New-Item -ItemType Directory $snap|Out-Null
$actualSnap=Join-Path $snap 'cnn_v10_pw_dsp16_actual.v'
$modelSnap=Join-Path $snap 'cnn_v10_pw_dsp16_vector_model.v'
$tbSnap=Join-Path $snap 'tb_cnn_v10_pw_half2x_vector_miter.sv'
$glblSnap=Join-Path $snap 'glbl.v'
Copy-Item $actual $actualSnap;Copy-Item $tb $tbSnap;Copy-Item $glbl $glblSnap
$modelManifest=Join-Path $evidence 'vector-model-transform.json'
& python $patcher --source $actualSnap --output $modelSnap --manifest $modelManifest
if($LASTEXITCODE-ne0){throw 'Vector fastmodel patch failed'}
$steps=@()
$steps+=RunTool xvlog $xvlog @('--sv',$actualSnap,$modelSnap,$tbSnap,$glblSnap) (Join-Path $evidence 'xvlog.log')
if($steps[-1].exit_code-ne0 -or $steps[-1].error){throw 'xvlog failed'}
$steps+=RunTool xelab $xelab @('-mt','8','-O3','--debug','off','--timescale','1ns/1ps','-L','unisims_ver','--top','tb_cnn_v10_pw_half2x_vector_miter','--top','glbl','--snapshot','pw_half2x_vector_miter') (Join-Path $evidence 'xelab.log')
if($steps[-1].exit_code-ne0 -or $steps[-1].error){throw 'xelab failed'}
$steps+=RunTool xsim $xsim @('pw_half2x_vector_miter','--xsimdir',(Join-Path $work 'xsim.dir'),'--log',(Join-Path $evidence 'xsim.log'),'--onerror','quit','--runall') (Join-Path $evidence 'xsim-launcher.log')
$sim=if(Test-Path (Join-Path $evidence 'xsim.log')){Get-Content (Join-Path $evidence 'xsim.log') -Raw}else{''}
$pass=($steps[-1].exit_code-eq0 -and $sim-match'CNN_V10_PW_HALF2X_VECTOR_MITER_PASS' -and $sim-notmatch'(?m)^(Fatal:|ERROR:)')
$receipt=[ordered]@{
    schema='cnn-v10-pw-half2x-vector-miter-receipt-v1';pass=$pass;verification_only=$true;synthesis_allowed=$false
    created_utc=(Get-Date).ToUniversalTime().ToString('o');actual_sha256=Sha $actualSnap
    model_sha256=Sha $modelSnap;tb_sha256=Sha $tbSnap;transform_sha256=Sha $modelManifest
    contract=[ordered]@{slow_mhz=200;fast_mhz=400;phase='same-origin';latency_enabled_slow_cycles=8;ii=1;actual_dual_clock_wrapper_preserved=$true;replaced='cnn_v10_pw_dsp8_fast internals only'}
    coverage=@('back-to-back','random CE and valid','reset with CE0','reset with CE1','long CE hold','signed extrema cadence','fast partial cycle-by-cycle')
    steps=$steps
}
$receiptPath=Join-Path $evidence 'receipt.json';WriteUtf8 $receiptPath (($receipt|ConvertTo-Json -Depth 10)+"`n")
if(!$pass){throw "Half2x vector miter failed: $receiptPath"}
Write-Host "PW_HALF2X_VECTOR_MITER_PASS receipt=$receiptPath"
