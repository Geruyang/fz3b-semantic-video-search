$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$proofRoot=Join-Path $root 'reports/pw1/fast_miter'
$runId=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')+'-'+[guid]::NewGuid().ToString('N')
$work=Join-Path $proofRoot "runs/$runId"
New-Item -ItemType Directory -Force $work | Out-Null
$receiptPath=Join-Path $proofRoot 'receipt.json'
$toolRoot='D:/Vivado/2026.1/Vivado'
$inputs=[ordered]@{
 production_mac="$root/rtl/cnn_pw_mac.sv"
 production_primitives="$root/rtl/cnn_dsp_primitives.v"
 fast_primitives="$root/tb/pw1_fast_primitives.sv"
 miter_testbench="$root/tb/pw1_fast_miter_tb.sv"
 glbl="$toolRoot/data/verilog/src/glbl.v"
 runner=$PSCommandPath
 xvlog_wrapper="$toolRoot/bin/xvlog.bat"
 xelab_wrapper="$toolRoot/bin/xelab.bat"
 xsim_wrapper="$toolRoot/bin/xsim.bat"
 xvlog_executable="$toolRoot/bin/unwrapped/win64.o/xvlog.exe"
 xelab_executable="$toolRoot/bin/unwrapped/win64.o/xelab.exe"
 xsim_executable="$toolRoot/bin/unwrapped/win64.o/xsim.exe"
}
function Get-Binding([string]$role,[string]$path){
 $file=Get-Item -LiteralPath $path
 [ordered]@{role=$role;path=$file.FullName;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash;bytes=$file.Length}
}
$before=@(foreach($key in $inputs.Keys){Get-Binding $key $inputs[$key]})
$commands=[Collections.Generic.List[object]]::new()
$receipt=[ordered]@{schema='pw-mac-fast-miter-v1';run_id=$runId;started_utc=(Get-Date).ToUniversalTime().ToString('o');pass=$false;production_source_changed=$null;inputs=$before;generated_sources=@();commands=@();logs=@();result=$null;failure=$null}
# Invalidate the current proof before starting. Earlier runs remain immutable diagnostics.
$receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $receiptPath
function Invoke-Recorded([string]$exe,[string[]]$arguments,[string]$logName){
 $logPath=Join-Path $work $logName
 & $exe @arguments 2>&1 | Tee-Object -FilePath $logPath
 $code=$LASTEXITCODE
 $commands.Add([ordered]@{executable=$exe;arguments=$arguments;working_directory=$work;exit_code=$code;log_path=$logPath})
 if($code -ne 0){throw "$exe exited $code"}
}
Push-Location $work
try {
 $fast=Get-Content -LiteralPath $inputs.fast_primitives -Raw
 $real=Get-Content -LiteralPath $inputs.production_primitives -Raw
 $leaf='module cnn_pw_dsp16_half2x_fused_alu ('
 if($real.Substring($real.IndexOf($leaf)).Trim() -cne $fast.Substring($fast.IndexOf($leaf)).Trim()){
  throw 'Fast model controller/FIFO suffix differs from production source'
 }
 $receipt.controller_fifo_source_identical=$true
 Set-Content -LiteralPath model_primitives.sv ($fast.Replace('cnn_pw_dsp','cnn_pw_model_dsp'))
 $mac=Get-Content -LiteralPath $inputs.production_mac -Raw
 Set-Content -LiteralPath model_mac.sv ($mac.Replace('cnn_pw_dsp','cnn_pw_model_dsp').Replace('cnn_pw_mac','cnn_pw_mac_model'))
 $receipt.generated_sources=@((Get-Binding 'generated_model_primitives' "$work/model_primitives.sv"),(Get-Binding 'generated_model_mac' "$work/model_mac.sv"))
 Invoke-Recorded $inputs.xvlog_wrapper @('--sv',$inputs.production_primitives,$inputs.production_mac,"$work/model_primitives.sv","$work/model_mac.sv",$inputs.miter_testbench,$inputs.glbl) 'compile.log'
 Invoke-Recorded $inputs.xelab_wrapper @('pw1_fast_miter_tb','glbl','-L','unisims_ver','-s','pw1_fast_miter') 'elaborate.log'
 Invoke-Recorded $inputs.xsim_wrapper @('pw1_fast_miter','-runall') 'simulate.log'
 $matches=@(Select-String -LiteralPath "$work/simulate.log" -Pattern '^PASS FAST/UNISIM EVERY-CYCLE MITER tiles=(\d+) lane_results=(\d+) cycles=(\d+)$')
 if($matches.Count -ne 1){throw 'Fresh run must contain exactly one complete miter PASS record'}
 $match=$matches[0].Matches[0]
 $tiles=[int]$match.Groups[1].Value;$results=[int]$match.Groups[2].Value;$cycles=[int]$match.Groups[3].Value
 if($tiles -ne 1024 -or $results -ne 4096 -or $cycles -lt 1024){throw 'Miter coverage count is incomplete'}
 if(Select-String -LiteralPath "$work/simulate.log" -Pattern 'Fatal:|FAIL |miter mismatch'){throw 'Miter log contains failure diagnostics'}
 $receipt.result=[ordered]@{accepted_tiles=$tiles;lane_results=$results;compared_job_clock_cycles=$cycles;every_cycle_valid_ready_and_valid_data=$true;long_pause_job_cycles=72;random_and_signed_extremes=$true}
 $after=@(foreach($key in $inputs.Keys){Get-Binding $key $inputs[$key]})
 for($i=0;$i -lt $before.Count;$i++){
  if($before[$i].sha256 -cne $after[$i].sha256){throw "Input changed during proof run: $($before[$i].role)"}
 }
 foreach($generated in $receipt.generated_sources){
  if((Get-FileHash -LiteralPath $generated.path -Algorithm SHA256).Hash -cne $generated.sha256){throw "Generated model changed during proof: $($generated.role)"}
 }
 $receipt.inputs_after=$after
 $receipt.production_source_changed=$false
 $receipt.pass=$true
} catch {
 $receipt.failure=$_.Exception.Message
 throw
} finally {
 $receipt.commands=@($commands.ToArray())
 $receipt.logs=@(foreach($name in @('compile.log','elaborate.log','simulate.log')){
  $path=Join-Path $work $name
  if(Test-Path -LiteralPath $path){Get-Binding $name $path}
 })
 $receipt.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
 $json=$receipt | ConvertTo-Json -Depth 12
 Set-Content -LiteralPath "$work/receipt.json" $json
 Set-Content -LiteralPath $receiptPath $json
 Pop-Location
}

