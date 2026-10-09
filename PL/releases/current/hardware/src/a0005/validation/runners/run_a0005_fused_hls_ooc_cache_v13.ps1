param(
  [Parameter(Mandatory=$true)][string]$InputIpDir,
  [Parameter(Mandatory=$true)][string]$WorkDir,
  [Parameter(Mandatory=$true)][string]$EvidenceDir,
  [Parameter(Mandatory=$true)][string]$CacheDir,
  [string]$VivadoBat='D:\Vivado\2026.1\Vivado\bin\vivado.bat'
)
$ErrorActionPreference='Stop'
$rtlDigest='ef373560fbb68e8719d5497b0d259b8a6dab734b2f88744f9d3505f8143af711'
$leafSha='2b541de975975b5e05060287b2052ce1dc1375b83e601e79a59b79be4dc0efdf'
$oldCacheId='bb03f320fa66fdbd'
$v11CacheId='f9f312cb538ccb2e'
$v12CacheId='3ee230f7a9b2909b'
$script=Join-Path $PSScriptRoot 'build_a0005_fused_hls_ooc_cache_v13.tcl'
foreach($p in @($InputIpDir,$script,$VivadoBat)){if(-not(Test-Path -LiteralPath $p)){throw "Missing input: $p"}}
$live=@(Get-Process vivado,vitis_hls -ErrorAction SilentlyContinue)
if($live.Count -ne 0){throw "Refusing second heavy owner: $($live.Id -join ',')"}
New-Item -ItemType Directory -Force -Path $WorkDir,$EvidenceDir,$CacheDir | Out-Null
$WorkDir=[IO.Path]::GetFullPath($WorkDir)
$EvidenceDir=[IO.Path]::GetFullPath($EvidenceDir)
$CacheDir=[IO.Path]::GetFullPath($CacheDir)
$privateUser=Join-Path $EvidenceDir 'private-user';$privateRoaming=Join-Path $privateUser 'AppData\Roaming';$privateLocal=Join-Path $privateUser 'AppData\Local'
$privateManifest=Join-Path $privateRoaming 'Xilinx\Vivado\tclapp\manifest.tcl'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $privateManifest),$privateLocal|Out-Null
[IO.File]::WriteAllText($privateManifest,"::tclapp::load_app -namespace {aldec::activehdl} aldec::activehdl`r`n",(New-Object Text.UTF8Encoding($false)))
$childEnvironment=@{APPDATA=$privateRoaming;LOCALAPPDATA=$privateLocal;USERPROFILE=$privateUser;HOME=$privateUser}
$log=Join-Path $EvidenceDir 'vivado.stdout.log'
$args=@('-mode','batch','-nojournal','-nolog','-source',$script,'-tclargs',(Resolve-Path $InputIpDir).Path,(Resolve-Path $WorkDir).Path,(Resolve-Path $EvidenceDir).Path,(Resolve-Path $CacheDir).Path,$oldCacheId,$v11CacheId,$v12CacheId,$rtlDigest)
$p=Start-Process -FilePath $VivadoBat -ArgumentList $args -WindowStyle Hidden -Environment $childEnvironment -PassThru -RedirectStandardOutput $log -RedirectStandardError (Join-Path $EvidenceDir 'vivado.stderr.log')
$p.PriorityClass='BelowNormal'; $p.WaitForExit(); $exit=$p.ExitCode
$token=Select-String -LiteralPath $log -SimpleMatch 'CNN_V10_FUSED_HLS_OOC_CACHE_PASS' -Quiet
if($exit -ne 0 -or -not $token){throw "Vivado fused OOC/cache failed exit=$exit token=$token; see $log"}
$id=@{}; Get-Content (Join-Path $EvidenceDir 'cache-identity.txt') | ForEach-Object {$k,$v=$_ -split '=',2;$id[$k]=$v}
if($id.new_cache_id -in @($oldCacheId,$v11CacheId,$v12CacheId)){throw 'New A0005 v1.3 cache ID aliases a historical A0004 cache ID'}
if($id.effective_vlnv -ne 'xilinx.com:hls:cnn_pipeline_v10:1.3' -or $id.identity_method -ne 'version_1_3'){throw 'Unexpected A0005 fused v1.3 package identity'}
$status=@{}; Get-Content (Join-Path $EvidenceDir 'ooc-status.txt') | ForEach-Object {$k,$v=$_ -split '=',2;$status[$k]=$v}
if($status.synthesis_strategy -ne 'Vivado Synthesis Defaults' -or $status.ap_clk_period_ns -ne '5.000' -or $status.pw_fast_clk_period_ns -ne '2.500'){throw 'Default-strategy or dual-clock OOC contract mismatch'}
$dcp=Join-Path $EvidenceDir 'cnn_pipeline_v10_fused_hls_0.dcp'
$cacheEntry=Join-Path $CacheDir (Join-Path $id.new_cache_id.Substring(0,1) (Join-Path $id.new_cache_id.Substring(1,1) $id.new_cache_id))
if(-not(Test-Path (Join-Path $cacheEntry 'cnn_pipeline_v10_fused_hls_0.dcp')) -or -not(Test-Path (Join-Path $cacheEntry ($id.new_cache_id+'.xci')))){throw 'Remote cache entry is incomplete'}
$packagedComponent=Join-Path $WorkDir 'hls-ip-fused-cache-identity\component.xml'
$effectiveXdc=Join-Path $EvidenceDir 'cnn_pipeline_v10_ooc_effective.xdc'
$requiredReports=@('utilization-post-synth.rpt','timing-post-synth.rpt','report-clocks.rpt','report-clock-interaction.rpt','timing-slow-to-slow.rpt','timing-fast-to-fast.rpt','timing-slow-to-fast.rpt','timing-fast-to-slow.rpt','clock-contract.rpt')
foreach($name in $requiredReports){if(-not(Test-Path -LiteralPath (Join-Path $EvidenceDir $name) -PathType Leaf)){throw "Missing OOC report: $name"}}
$frozenPackage=Join-Path $EvidenceDir 'hls-ip-v1.3'
if(Test-Path -LiteralPath $frozenPackage){throw "Refusing to overwrite frozen package: $frozenPackage"}
Copy-Item -LiteralPath (Join-Path $WorkDir 'hls-ip-fused-cache-identity') -Destination $frozenPackage -Recurse
$packagedComponentSha=(Get-FileHash $packagedComponent -Algorithm SHA256).Hash.ToLower()
$packageManifest=[ordered]@{
 schema='cnn-v10.5-a0005-pw-half2x-fused-alu-package-identity-v1';status='PASS';pass=$true
 vlnv=$id.effective_vlnv;old_cache_id=$oldCacheId;v11_cache_id=$v11CacheId;v12_cache_id=$v12CacheId;new_cache_id=$id.new_cache_id
 component_sha256=$packagedComponentSha;canonical_rtl_digest=$rtlDigest;leaf_sha256=$leafSha
 synthesis_strategy=$status.synthesis_strategy
 ooc_clock_contract=[ordered]@{ap_clk_period_ns=5.0;pw_fast_clk_period_ns=2.5;phase='aligned';async_clock_groups=$false;false_paths=$false;xdc_sha256=(Get-FileHash $effectiveXdc -Algorithm SHA256).Hash.ToLower()}
}
$packageManifestPath=Join-Path $EvidenceDir 'package-identity-manifest.json'
$packageManifest|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $packageManifestPath -Encoding utf8
$receipt=[ordered]@{
 schema='cnn-v10.5-a0005-pw-half2x-fused-alu-hls-ooc-cache-v1'; status='PASS'; pass=$true; tool_exit=$exit
 canonical_rtl_digest=$rtlDigest; fused_leaf_sha256=$leafSha
 input_ip_dir=(Resolve-Path $InputIpDir).Path; input_component_sha256=(Get-FileHash (Join-Path $InputIpDir 'component.xml') -Algorithm SHA256).Hash.ToLower()
 old_cache_id=$oldCacheId; v11_cache_id=$v11CacheId;v12_cache_id=$v12CacheId;new_cache_id=$id.new_cache_id; identity_method=$id.identity_method; effective_vlnv=$id.effective_vlnv
 synthesis_strategy=[ordered]@{requested='Vivado Synthesis Defaults';effective=$status.synthesis_strategy}
 ooc_clock_contract=[ordered]@{ap_clk_period_ns=5.0;pw_fast_clk_period_ns=2.5;phase='aligned';async_clock_groups=$false;false_paths=$false;effective_xdc=[ordered]@{path=(Resolve-Path $effectiveXdc).Path;sha256=(Get-FileHash $effectiveXdc -Algorithm SHA256).Hash.ToLower()}}
 packaged_component=[ordered]@{path=(Resolve-Path $packagedComponent).Path;sha256=$packagedComponentSha;core_revision=$id.new_core_revision;frozen_package=(Resolve-Path $frozenPackage).Path;package_identity_manifest=[ordered]@{path=(Resolve-Path $packageManifestPath).Path;sha256=(Get-FileHash $packageManifestPath -Algorithm SHA256).Hash.ToLower()}}
 ooc_dcp=[ordered]@{path=(Resolve-Path $dcp).Path;bytes=(Get-Item $dcp).Length;sha256=(Get-FileHash $dcp -Algorithm SHA256).Hash.ToLower()}
 remote_cache_dir=(Resolve-Path $CacheDir).Path; remote_cache_files=@(Get-ChildItem $CacheDir -Recurse -File).Count
 reports=[ordered]@{utilization_sha256=(Get-FileHash (Join-Path $EvidenceDir 'utilization-post-synth.rpt') -Algorithm SHA256).Hash.ToLower();timing_summary_sha256=(Get-FileHash (Join-Path $EvidenceDir 'timing-post-synth.rpt') -Algorithm SHA256).Hash.ToLower();clocks_sha256=(Get-FileHash (Join-Path $EvidenceDir 'report-clocks.rpt') -Algorithm SHA256).Hash.ToLower();clock_interaction_sha256=(Get-FileHash (Join-Path $EvidenceDir 'report-clock-interaction.rpt') -Algorithm SHA256).Hash.ToLower();slow_to_slow_sha256=(Get-FileHash (Join-Path $EvidenceDir 'timing-slow-to-slow.rpt') -Algorithm SHA256).Hash.ToLower();fast_to_fast_sha256=(Get-FileHash (Join-Path $EvidenceDir 'timing-fast-to-fast.rpt') -Algorithm SHA256).Hash.ToLower();slow_to_fast_sha256=(Get-FileHash (Join-Path $EvidenceDir 'timing-slow-to-fast.rpt') -Algorithm SHA256).Hash.ToLower();fast_to_slow_sha256=(Get-FileHash (Join-Path $EvidenceDir 'timing-fast-to-slow.rpt') -Algorithm SHA256).Hash.ToLower()}
 source=[ordered]@{tcl_sha256=(Get-FileHash $script -Algorithm SHA256).Hash.ToLower();runner_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLower()}
 logs=[ordered]@{stdout_sha256=(Get-FileHash $log -Algorithm SHA256).Hash.ToLower();identity_sha256=(Get-FileHash (Join-Path $EvidenceDir 'cache-identity.txt') -Algorithm SHA256).Hash.ToLower();cache_report_sha256=(Get-FileHash (Join-Path $EvidenceDir 'ip-cache-report.rpt') -Algorithm SHA256).Hash.ToLower()}
}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $EvidenceDir 'receipt.json') -Encoding utf8
Write-Output "CNN_V10_FUSED_HLS_OOC_CACHE_RUNNER_PASS cache_id=$($id.new_cache_id)"
