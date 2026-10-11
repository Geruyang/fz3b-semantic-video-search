param([Parameter(Mandatory=$true)][string]$Candidate,[Parameter(Mandatory=$true)][string]$Log,[Parameter(Mandatory=$true)][Alias("Profile")][int]$SelectedProfile,[int]$Repeat=1,[int]$TokenDenom=2,[switch]$Mixed)
$ErrorActionPreference='Stop'
$text=Get-Content -LiteralPath $Log -Raw
$passes=@([regex]::Matches($text,'FULL_PASS profile=(\d+) blocks=(\d+) cycles=(\d+)') | ForEach-Object {[ordered]@{profile=[int]$_.Groups[1].Value;blocks=[int]$_.Groups[2].Value;cycles=[long]$_.Groups[3].Value}})
$expected=$Repeat;if($SelectedProfile -lt 0){$expected=4*$Repeat}
if($Mixed){$expected=3}
$functional=($text -match 'FULL_FUNCTIONAL_SUITE_PASS|FULL_SUITE_PASS') -and ($text -notmatch 'Fatal:') -and $passes.Count -eq $expected
$gates=[regex]::Matches($text,'CYCLE_GATE profile=(\d+) target=(\d+) pass=(\d+)')
$performance=$functional -and $TokenDenom -eq 2 -and $gates.Count -eq $expected -and !(@($gates | Where-Object {$_.Groups[3].Value -ne '1'}).Count)
$proof=Get-Content "$Candidate/fast_proof_binding.json" -Raw | ConvertFrom-Json
$fixtures=Get-Content "$Candidate/fixture_binding.json" -Raw | ConvertFrom-Json
$sequence=@($passes | ForEach-Object {$_.profile})
$mixedVerified=$Mixed -and $functional -and ($sequence -join ',') -eq '3,2,3' -and $text -match 'MIXED_SEQUENCE_VERIFIED actual_sequence=3,2,3'
$resultPath="$Candidate/p${SelectedProfile}_r${Repeat}_result.json";if($Mixed){$resultPath="$Candidate/mixed_3_2_3_result.json"}
[ordered]@{schema='full-rtl-simulation-result-v1';qualification_scope='selected_profile_host_simulation';complete_profile_matrix_verified=(!$Mixed -and $SelectedProfile -lt 0 -and $functional);mixed_repeat_without_reset_verified=($mixedVerified -or (!$Mixed -and $SelectedProfile -lt 0 -and $Repeat -ge 2 -and $functional));mixed_sequence_verified=$mixedVerified;actual_sequence=$sequence;functional_pass=$functional;performance_pass=$performance;qualified=($functional -and $performance -and $proof.pass -and $fixtures.pass);profiles=$passes;selected_profile=$SelectedProfile;repeat=$Repeat;token=@(1,$TokenDenom,32);bdelay=3;test_only_fast_model=$true;proof_binding_pass=$proof.pass;fixture_binding_pass=$fixtures.pass;elaboration_configuration_sha256=($(if(Test-Path "$Candidate/elaboration_configuration.json"){(Get-FileHash "$Candidate/elaboration_configuration.json").Hash}else{$null}));elaboration_log_sha256=($(if(Test-Path "$Candidate/elaborate.log"){(Get-FileHash "$Candidate/elaborate.log").Hash}else{$null}));compile_log_sha256=(Get-FileHash "$Candidate/compile.log").Hash;compiled_snapshot_manifest_sha256=(Get-FileHash "$Candidate/simulation_snapshot/binary_manifest.json").Hash;source_manifest_sha256=(Get-FileHash "$Candidate/source_manifest.json").Hash;fast_proof_binding_sha256=(Get-FileHash "$Candidate/fast_proof_binding.json").Hash;fixture_binding_sha256=(Get-FileHash "$Candidate/fixture_binding.json").Hash;log_sha256=(Get-FileHash -LiteralPath $Log).Hash;board_operations=$false} | ConvertTo-Json -Depth 8 | Set-Content $resultPath



