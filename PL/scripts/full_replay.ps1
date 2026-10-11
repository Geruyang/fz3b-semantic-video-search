param([Parameter(Mandatory=$true)][string]$Candidate,[Parameter(Mandatory=$true)][Alias("Profile")][int]$SelectedProfile,[int]$Repeat=1,[int]$TokenDenom=2,[int]$DiagnosticBlocks=0,[switch]$FirstPair,[int]$DiagnosticPairs=0,[switch]$Mixed)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$Candidate=(Resolve-Path -LiteralPath $Candidate).Path.Replace('\','/')
$identity=Get-Content "$Candidate/source_manifest.json" -Raw | ConvertFrom-Json
foreach($entry in $identity){
 if($entry.snapshot.Replace('\','/') -notmatch '/(rtl|tb)/([^/]+)$'){throw 'Unexpected candidate source path'}
 $actual=Join-Path $Candidate "$($Matches[1])/$($Matches[2])"
 if((Get-FileHash -LiteralPath $actual).Hash -ne $entry.sha256){throw 'Candidate snapshot SHA mismatch'}
}
$binding=Get-Content "$Candidate/fast_proof_binding.json" -Raw | ConvertFrom-Json
if(!$binding.pass -or !$binding.candidate_source_matches){throw 'Missing FAST model proof binding'}
if((Get-FileHash "$Candidate/fast_proof/receipt.json").Hash -ne $binding.proof_receipt_sha256 -or (Get-FileHash "$Candidate/reference/cnn_dsp_primitives.v").Hash -ne $binding.real_primitives_sha256){throw 'Saved MAC proof receipt/reference mismatch'}
foreach($entry in $binding.copies){
 $actual=Join-Path "$Candidate/fast_proof" (Split-Path $entry.path -Leaf)
 if((Get-FileHash -LiteralPath $actual).Hash -ne $entry.sha256){throw 'Saved MAC proof artifact mismatch'}
}
$artifact="$Candidate/simulation_snapshot"
if(!(Test-Path "$artifact/xsim.dir")){
 New-Item -ItemType Directory -Force $artifact | Out-Null
 $built="$Candidate/simulation/xsim.dir"
 if(!(Test-Path $built)){
  if((Get-FileHash "$root/reports/full/sim/source_manifest.json").Hash -ne (Get-FileHash "$Candidate/source_manifest.json").Hash){throw 'Legacy elaborated binary manifest differs from candidate'}
  $built="$root/reports/full/sim/xsim.dir"
 }
 Copy-Item -LiteralPath $built -Destination "$artifact/xsim.dir" -Recurse
 $binIdentity=@(Get-ChildItem "$artifact/xsim.dir" -Recurse -File | Where-Object {$_.Extension -notin '.log','.jou','.wdb','.ini'} | ForEach-Object {[ordered]@{path=$_.FullName.Replace('\','/');sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}})
 $binIdentity | ConvertTo-Json -Depth 4 | Set-Content "$artifact/binary_manifest.json"
}
if(!(Test-Path "$artifact/binary_manifest.json")){
 $binIdentity=@(Get-ChildItem "$artifact/xsim.dir" -Recurse -File | Where-Object {$_.Extension -notin '.log','.jou','.wdb','.ini'} | ForEach-Object {[ordered]@{path=$_.FullName.Replace('\','/');sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}})
 $binIdentity | ConvertTo-Json -Depth 4 | Set-Content "$artifact/binary_manifest.json"
}
foreach($entry in (Get-Content "$artifact/binary_manifest.json" -Raw | ConvertFrom-Json)){
 $relative=[regex]::Split($entry.path.Replace('\','/'),'/xsim\.dir/')[1]
 $actual=Join-Path "$artifact/xsim.dir" $relative
 if((Get-FileHash -LiteralPath $actual).Hash -ne $entry.sha256){throw 'Saved simulation binary SHA mismatch'}
}
$runMode="p${SelectedProfile}";if($Mixed){$runMode='mixed_3_2_3'}
$runNonce=[guid]::NewGuid().ToString('N').Substring(0,8)
$work="$Candidate/runs/${runMode}_r${Repeat}_$(Get-Date -Format yyyyMMdd-HHmmss-fff)_$runNonce"
New-Item -ItemType Directory -Force $work | Out-Null
Copy-Item -LiteralPath "$artifact/xsim.dir" -Destination "$work/xsim.dir" -Recurse
$fixture="$Candidate/fixtures"
if(!(Test-Path "$Candidate/fixture_binding.json")){& "$PSScriptRoot/full_fixture.ps1" -Candidate $Candidate}
$fixtureBinding=Get-Content "$Candidate/fixture_binding.json" -Raw | ConvertFrom-Json
foreach($entry in $fixtureBinding.entries){
 $actual=Join-Path $fixture "profile$($entry.profile)/$($entry.role).mem"
 if((Get-FileHash -LiteralPath $actual).Hash -ne $entry.sha256){throw 'Candidate fixture SHA mismatch'}
}
@'
for {set step 0} {$step < 2100} {incr step} {
 set before [current_time]
 puts "SIM_STEP_100K $step"
 run 500 us
 set after [current_time]
 if {$before eq $after} {break}
}
quit
'@ | Set-Content "$work/steps.tcl"
Push-Location $work
try {
 if($FirstPair -and $DiagnosticPairs -eq 0){$DiagnosticPairs=1}
 & 'D:/Vivado/2026.1/Vivado/bin/xsim.bat' cnn_full_sim -testplusarg ('"FIXTURE_ROOT='+$fixture+'"') -testplusarg ('"PROFILE='+$SelectedProfile+'"') -testplusarg ('"REPEAT='+$Repeat+'"') -testplusarg '"MAX_CYCLES=200000000"' -testplusarg ('"TOKEN_DENOM='+$TokenDenom+'"') -testplusarg ('"DIAG_BLOCKS='+$DiagnosticBlocks+'"') -testplusarg ('"DIAG_FIRST_PAIR='+$DiagnosticPairs+'"') -testplusarg ('"MIXED='+[int][bool]$Mixed+'"') -tclbatch "$work/steps.tcl" 2>&1 | Tee-Object simulate.log
 $text=Get-Content simulate.log -Raw
 $functional=$text -match 'FULL_FUNCTIONAL_SUITE_PASS|FULL_SUITE_PASS' -and $text -notmatch 'Fatal:'
 $gates=[regex]::Matches($text,'CYCLE_GATE profile=(\d+) target=(\d+) pass=(\d+)')
 $performance=$functional -and $TokenDenom -eq 2 -and $gates.Count -gt 0 -and !(@($gates | Where-Object {$_.Groups[3].Value -ne '1'}).Count)
 $passes=@([regex]::Matches($text,'FULL_PASS profile=(\d+) blocks=(\d+) cycles=(\d+)') | ForEach-Object {[ordered]@{profile=[int]$_.Groups[1].Value;blocks=[int]$_.Groups[2].Value;cycles=[long]$_.Groups[3].Value}})
 [ordered]@{functional_pass=$functional;performance_pass=$performance;qualified=($functional -and $performance);profiles=$passes;profile=$SelectedProfile;repeat=$Repeat;token=@(1,$TokenDenom,32);bdelay=3;diagnostic_blocks=$DiagnosticBlocks;diagnostic_pairs=$DiagnosticPairs;mixed_sequence_verified=($functional -and $Mixed -and $text -match 'MIXED_SEQUENCE_VERIFIED actual_sequence=3,2,3');actual_sequence=@($passes | ForEach-Object {$_.profile});elaboration_configuration_sha256=($(if(Test-Path "$Candidate/elaboration_configuration.json"){(Get-FileHash "$Candidate/elaboration_configuration.json").Hash}else{$null}));elaboration_log_sha256=($(if(Test-Path "$Candidate/elaborate.log"){(Get-FileHash "$Candidate/elaborate.log").Hash}else{$null}));compile_log_sha256=(Get-FileHash "$Candidate/compile.log").Hash;compiled_snapshot_manifest_sha256=(Get-FileHash "$Candidate/simulation_snapshot/binary_manifest.json").Hash;source_manifest_sha256=(Get-FileHash "$Candidate/source_manifest.json").Hash;fast_proof_binding_sha256=(Get-FileHash "$Candidate/fast_proof_binding.json").Hash;fixture_binding_sha256=(Get-FileHash "$Candidate/fixture_binding.json").Hash;log_sha256=(Get-FileHash simulate.log).Hash;board_operations=$false} | ConvertTo-Json -Depth 8 | Set-Content result.json
 if($DiagnosticBlocks -eq 0){& "$PSScriptRoot/full_result.ps1" -Candidate $Candidate -Log "$work/simulate.log" -Profile $SelectedProfile -Repeat $Repeat -TokenDenom $TokenDenom -Mixed:$Mixed}
 if($DiagnosticBlocks -gt 0){
  if($text -notmatch 'DIAGNOSTIC_SUITE_DONE' -or $text -match 'Fatal:'){throw 'Diagnostic run failed'}
  return
 }
 if(!$functional){throw 'Full replay functional failure'}
 if(!$performance){throw 'Full replay functional pass but performance gate failure'}
}finally{Pop-Location}

