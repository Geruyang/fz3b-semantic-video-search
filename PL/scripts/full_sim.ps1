param([Alias("Profile")][int]$SelectedProfile=-1,[int]$Repeat=1,[long]$MaxCycles=200000000,[int]$TokenDenom=2,[switch]$CompileOnly,[switch]$FastModel,[string]$SourceCandidate,[switch]$NoElaborationOptimization)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$tag=Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$candidate=(Join-Path $root "reports/full/candidates/$tag").Replace('\','/')
$work="$candidate/simulation"
New-Item -ItemType Directory -Force $work | Out-Null
$fixture=Join-Path $root 'tb/fixtures/full-rtl'
$fixture=$fixture.Replace('\','/')
$dutRoot="$root/rtl"
if($SourceCandidate){
 $SourceCandidate=(Resolve-Path -LiteralPath $SourceCandidate).Path.Replace('\','/')
 $dutRoot="$SourceCandidate/rtl"
 foreach($entry in (Get-Content "$SourceCandidate/source_manifest.json" -Raw | ConvertFrom-Json)){
  if($entry.snapshot.Replace('\','/') -match '/rtl/([^/]+)$'){
   if((Get-FileHash "$dutRoot/$($Matches[1])").Hash -ne $entry.sha256){throw 'Source candidate RTL SHA mismatch'}
  }
 }
}
Push-Location $work
try {
 $packages=@('cnn_math_pkg.sv','cnn_profile_pkg.sv','cnn_axi_pkg.sv')
 $files=@($packages | ForEach-Object {Join-Path $dutRoot $_})
 $files+=@(Get-ChildItem $dutRoot -File | Where-Object {$_.Extension -in '.sv','.v' -and $_.Name -notin $packages -and $_.Name -notin 'cnn_rtl_bd.sv','pw1_fast_primitives.sv'} | Sort-Object Name | ForEach-Object {$_.FullName})
 if($SourceCandidate -and !$FastModel){$files+="$SourceCandidate/reference/cnn_dsp_primitives.v"}
 if($FastModel){
  $proof=Join-Path $root 'reports/pw1/fast_miter/receipt.json'
  $files=@($files | Where-Object {(Split-Path $_ -Leaf) -ne 'cnn_dsp_primitives.v'})
  $files+=Join-Path $root 'tb/pw1_fast_primitives.sv'
 }
 New-Item -ItemType Directory -Force "$candidate/rtl","$candidate/tb" | Out-Null
 New-Item -ItemType Directory -Force "$candidate/runner_reference" | Out-Null
 $runners=@(Get-ChildItem $PSScriptRoot -Filter 'full*.ps1' -File | ForEach-Object {
  $dest=Join-Path "$candidate/runner_reference" $_.Name
  Copy-Item -LiteralPath $_.FullName -Destination $dest
  [ordered]@{path=$dest;sha256=(Get-FileHash -LiteralPath $dest).Hash}
 })
 $runners | ConvertTo-Json | Set-Content "$candidate/runner_manifest.json"
 & "$PSScriptRoot/full_fixture.ps1" -Candidate $candidate
 $fixture="$candidate/fixtures"
 $identity=@()
 foreach($original in $files){
  $dest=Join-Path "$candidate/rtl" (Split-Path $original -Leaf)
  Copy-Item -LiteralPath $original -Destination $dest
  $h=Get-FileHash -Algorithm SHA256 -LiteralPath $dest
  $identity += [ordered]@{original=$original.Replace('\','/');snapshot=$dest.Replace('\','/');sha256=$h.Hash}
 }
 foreach($name in @('full_ddr.sv','tb_cnn_full.sv')){
  $original=Join-Path "$root/tb" $name;$dest=Join-Path "$candidate/tb" $name
  Copy-Item -LiteralPath $original -Destination $dest
  $h=Get-FileHash -Algorithm SHA256 -LiteralPath $dest
  $identity += [ordered]@{original=$original.Replace('\','/');snapshot=$dest.Replace('\','/');sha256=$h.Hash}
 }
 if($FastModel){
  & "$PSScriptRoot/full_proof.ps1" -Candidate $candidate
  Copy-Item -LiteralPath $proof -Destination "$candidate/fast_miter_receipt.json"
  $proofhash=(Get-FileHash -LiteralPath $proof).Hash
 }else{$proofhash=$null}
 [ordered]@{fast_model=[bool]$FastModel;proof_sha256=$proofhash;production_source_changed=$false;profile=$SelectedProfile;repeat=$Repeat;token=@(1,$TokenDenom,32);bdelay=3} | ConvertTo-Json -Depth 4 | Set-Content "$candidate/run_configuration.json"
 $identity | ConvertTo-Json -Depth 4 | Set-Content "$candidate/source_manifest.json"
 $identity | ConvertTo-Json -Depth 4 | Set-Content source_manifest.json
 $files=@($files | ForEach-Object {Join-Path "$candidate/rtl" (Split-Path $_ -Leaf)})
 $qcacheObserver=[bool](Select-String -LiteralPath "$candidate/rtl/cnn_pw2_stage.sv" -Pattern 'post_state_t post_state' -Quiet)
 $tbDefines=@();if($qcacheObserver){$tbDefines=@('-d','CNN_TB_QCACHE')}
 [ordered]@{qcache_observer=$qcacheObserver;source_input_candidate=$SourceCandidate;compiler_defines=$tbDefines} | ConvertTo-Json | Set-Content "$candidate/testbench_configuration.json"
 & 'D:/Vivado/2026.1/Vivado/bin/xvlog.bat' --sv @tbDefines @files "$candidate/tb/full_ddr.sv" "$candidate/tb/tb_cnn_full.sv" 'D:/Vivado/2026.1/Vivado/data/verilog/src/glbl.v' 2>&1 | Tee-Object compile.log
 if($LASTEXITCODE){throw 'xvlog failed'}
 $elaborationArgs=@('tb_cnn_full','glbl','-L','unisims_ver','-s','cnn_full_sim')
 if($NoElaborationOptimization){$elaborationArgs+=@('--O0')}
 $elaborationArgs+=@('-debug','typical')
 [ordered]@{schema='full-elaboration-configuration-v1';tool='D:/Vivado/2026.1/Vivado/bin/xelab.bat';arguments=$elaborationArgs;optimization_disabled=[bool]$NoElaborationOptimization;production_source_changed=$false} | ConvertTo-Json | Set-Content "$candidate/elaboration_configuration.json"
 & 'D:/Vivado/2026.1/Vivado/bin/xelab.bat' @elaborationArgs 2>&1 | Tee-Object elaborate.log
 if($LASTEXITCODE){throw 'xelab failed'}
 if(!$CompileOnly){
  @'
for {set step 0} {$step < 2100} {incr step} {
 set before [current_time]
 puts "SIM_STEP_100K $step"
 run 500 us
 set after [current_time]
 if {$before eq $after} {break}
}
quit
'@ | Set-Content "$candidate/steps.tcl"
  & 'D:/Vivado/2026.1/Vivado/bin/xsim.bat' cnn_full_sim -testplusarg ('"FIXTURE_ROOT=' + $fixture + '"') -testplusarg ('"PROFILE=' + $SelectedProfile + '"') -testplusarg ('"REPEAT=' + $Repeat + '"') -testplusarg ('"MAX_CYCLES=' + $MaxCycles + '"') -testplusarg ('"TOKEN_DENOM=' + $TokenDenom + '"') -tclbatch "$candidate/steps.tcl" 2>&1 | Tee-Object "p${SelectedProfile}_repeat${Repeat}.log"
  $log=Get-Content "p${SelectedProfile}_repeat${Repeat}.log" -Raw
  $functional=($log -match 'FULL_FUNCTIONAL_SUITE_PASS|FULL_SUITE_PASS') -and ($log -notmatch 'Fatal:')
  $gates=[regex]::Matches($log,'CYCLE_GATE profile=(\d+) target=(\d+) pass=(\d+)')
  $performance=$functional -and $TokenDenom -eq 2 -and $gates.Count -gt 0 -and !(@($gates | Where-Object {$_.Groups[3].Value -ne '1'}).Count)
  [ordered]@{functional_pass=$functional;performance_pass=$performance;qualified=($functional -and $performance);source_manifest_sha256=(Get-FileHash "$candidate/source_manifest.json").Hash;log_sha256=(Get-FileHash "p${SelectedProfile}_repeat${Repeat}.log").Hash;profile=$SelectedProfile;repeat=$Repeat;fast_model=[bool]$FastModel;board_operations=$false} | ConvertTo-Json | Set-Content "$candidate/result.json"
  if(!$functional){throw 'full numerical/protocol simulation failed'}
  if(!$performance){throw 'full numerical/protocol passed but performance gate failed'}
 }
} finally {
 if($candidate){Get-ChildItem -File *.log | Copy-Item -Destination $candidate}
 Pop-Location
}




