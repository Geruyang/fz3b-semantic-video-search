param([Parameter(Mandatory=$true)][string]$Candidate)
$ErrorActionPreference='Stop'
$baseline=@(18820869,29923059,7984637,1539314)
$rows=@();$receipts=@();$complete=$true;$functional=$true;$performance=$true
for($p=0;$p -lt 4;$p++){
 $file="$Candidate/p${p}_r1_result.json"
 if(Test-Path $file){
  $r=Get-Content $file -Raw | ConvertFrom-Json
  $receipts += $r
  $cycles=$r.profiles[0].cycles
  $rows += [ordered]@{profile=$p;status='complete';functional_pass=$r.functional_pass;performance_pass=$r.performance_pass;cycles=$cycles;baseline_cycles=$baseline[$p];change_pct=[Math]::Round(100*($cycles/$baseline[$p]-1),5);receipt_sha256=(Get-FileHash $file).Hash}
  $functional=$functional -and $r.functional_pass;$performance=$performance -and $r.performance_pass
 }else{
  $complete=$false
  $rows += [ordered]@{profile=$p;status='pending';functional_pass=$null;performance_pass=$null;cycles=$null;baseline_cycles=$baseline[$p]}
 }
}
$mixedVerified=$false;$mixedHash=$null;$sameBindings=$complete
if(Test-Path "$Candidate/mixed_3_2_3_result.json"){
 $mixed=Get-Content "$Candidate/mixed_3_2_3_result.json" -Raw | ConvertFrom-Json
 $mixedVerified=$mixed.functional_pass -and $mixed.performance_pass -and $mixed.qualified -and $mixed.mixed_sequence_verified -and ($mixed.actual_sequence -join ',') -eq '3,2,3'
 $mixedHash=(Get-FileHash "$Candidate/mixed_3_2_3_result.json").Hash
 $receipts += $mixed
}
foreach($field in @('source_manifest_sha256','compiled_snapshot_manifest_sha256','compile_log_sha256','fast_proof_binding_sha256','fixture_binding_sha256')){
 $values=@($receipts | ForEach-Object {$_.$field} | Select-Object -Unique)
 if($values.Count -ne 1 -or !$values[0]){$sameBindings=$false}
}
[ordered]@{schema='full-rtl-profile-matrix-summary-v2';qualification_scope='host_simulation_matrix_and_mixed_sequence';complete=$complete;functional_matrix_pass=($complete -and $functional);performance_matrix_pass=($complete -and $performance);qualified=($complete -and $functional -and $performance -and $mixedVerified -and $sameBindings);physical_qualification_verified=$false;same_candidate_bindings=$sameBindings;mixed_repeat_without_reset_verified=$mixedVerified;mixed_sequence_verified=$mixedVerified;mixed_receipt_sha256=$mixedHash;test_only_fast_model=$true;board_operations=$false;rows=$rows} | ConvertTo-Json -Depth 8 | Set-Content "$Candidate/summary.json"
