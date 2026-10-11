param([Parameter(Mandatory=$true)][string]$Candidate)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$fixture=Join-Path $root 'tb/fixtures/full-rtl'
if(!(Test-Path "$fixture/manifest.json")){throw 'The final RTL fixture manifest is missing.'}
$m=Get-Content "$fixture/manifest.json" -Raw | ConvertFrom-Json
$entries=@()
foreach($case in $m.cases){
 $p=$case.profile
 New-Item -ItemType Directory -Force "$Candidate/fixtures/profile$p" | Out-Null
 foreach($file in $case.files.PSObject.Properties){
  $src="$fixture/profile$p/$($file.Name).mem"
  $hash=(Get-FileHash -LiteralPath $src).Hash
  if($hash -ne $file.Value.sha256 -or ($null -ne $file.Value.bytes -and (Get-Item -LiteralPath $src).Length -ne $file.Value.bytes)){throw "Frozen fixture identity mismatch P$p $($file.Name)"}
  $dst="$Candidate/fixtures/profile$p/$($file.Name).mem"
  Copy-Item -Force -LiteralPath $src -Destination $dst
  if((Get-FileHash -LiteralPath $dst).Hash -ne $hash){throw 'Copied fixture SHA mismatch'}
  $entries+=[ordered]@{profile=$p;role=$file.Name;original=$src.Replace('\','/');snapshot=$dst.Replace('\','/');sha256=$hash;words=$file.Value.word_count}
 }
}
Copy-Item -Force -LiteralPath "$fixture/manifest.json" -Destination "$Candidate/fixtures/manifest.json"
Copy-Item -Force -LiteralPath "$fixture/receipt.json" -Destination "$Candidate/fixtures/receipt.json"
[ordered]@{schema='full-rtl-frozen-fixture-binding-v1';pass=$true;identity=$m.abi_identity;original_manifest_sha256=(Get-FileHash "$fixture/manifest.json").Hash;entries=$entries} | ConvertTo-Json -Depth 8 | Set-Content "$Candidate/fixture_binding.json"

