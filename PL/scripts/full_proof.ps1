param([Parameter(Mandatory=$true)][string]$Candidate)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
function Resolve-ProofInput([string]$value){
 $normalized=$value.Replace('\','/')
 $mark='/rtl_optim/'
 $at=$normalized.IndexOf($mark,[StringComparison]::OrdinalIgnoreCase)
 if($at -ge 0){return (Join-Path $root $normalized.Substring($at+$mark.Length))}
 return $value
}
$proofPath=Join-Path $root 'reports/pw1/fast_miter/receipt.json'
$proofText=Get-Content -LiteralPath $proofPath -Raw
$proof=$proofText | ConvertFrom-Json
if($proof.schema -ne 'pw-mac-fast-miter-v1' -or !$proof.pass -or $proof.production_source_changed -or !$proof.controller_fifo_source_identical){throw 'MAC miter proof status invalid'}
if($proof.result.accepted_tiles -ne 1024 -or $proof.result.lane_results -ne 4096 -or $proof.result.compared_job_clock_cycles -ne 3413 -or !$proof.result.every_cycle_valid_ready_and_valid_data){throw 'MAC miter proof coverage invalid'}
foreach($cmd in $proof.commands){if($cmd.exit_code -ne 0){throw 'MAC miter command failed'}}
foreach($entry in @($proof.inputs)+@($proof.generated_sources)+@($proof.logs)+@($proof.inputs_after)){
 if((Get-FileHash -Algorithm SHA256 -LiteralPath (Resolve-ProofInput $entry.path)).Hash -ne $entry.sha256){throw "MAC proof SHA mismatch: $($entry.role)"}
}
$mac=$proof.inputs | Where-Object role -eq 'production_mac'
$fast=$proof.inputs | Where-Object role -eq 'fast_primitives'
$real=$proof.inputs | Where-Object role -eq 'production_primitives'
if((Get-FileHash "$Candidate/rtl/cnn_pw_mac.sv").Hash -ne $mac.sha256 -or (Get-FileHash "$Candidate/rtl/pw1_fast_primitives.sv").Hash -ne $fast.sha256){throw 'Candidate MAC/fast arithmetic does not match miter'}
$dest=Join-Path $Candidate 'fast_proof'
New-Item -ItemType Directory -Force $dest,"$Candidate/reference" | Out-Null
Copy-Item -Force -LiteralPath $proofPath -Destination "$dest/receipt.json"
Copy-Item -Force -LiteralPath (Resolve-ProofInput $real.path) -Destination "$Candidate/reference/cnn_dsp_primitives.v"
$copies=@()
foreach($entry in @($proof.generated_sources)+@($proof.logs)+@($proof.inputs | Where-Object {$_.role -in 'miter_testbench','runner','production_mac','fast_primitives','glbl'})){
 $target=Join-Path $dest (Split-Path $entry.path -Leaf)
 Copy-Item -Force -LiteralPath (Resolve-ProofInput $entry.path) -Destination $target
 $hash=(Get-FileHash -LiteralPath $target).Hash
 if($hash -ne $entry.sha256){throw 'Copied proof source changed'}
 $copies += [ordered]@{role=$entry.role;path=$target.Replace('\','/');sha256=$hash}
}
[ordered]@{schema='full-fast-model-proof-binding-v1';pass=$true;proof_run_id=$proof.run_id;proof_receipt_sha256=(Get-FileHash "$dest/receipt.json").Hash;production_mac_sha256=$mac.sha256;real_primitives_sha256=$real.sha256;fast_primitives_sha256=$fast.sha256;all_current_input_generated_log_hashes_checked=$true;candidate_source_matches=$true;copies=$copies} | ConvertTo-Json -Depth 8 | Set-Content "$Candidate/fast_proof_binding.json"


