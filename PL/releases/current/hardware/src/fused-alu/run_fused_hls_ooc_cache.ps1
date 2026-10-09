param(
  [Parameter(Mandatory=$true)][string]$InputIpDir,
  [Parameter(Mandatory=$true)][string]$WorkDir,
  [Parameter(Mandatory=$true)][string]$EvidenceDir,
  [Parameter(Mandatory=$true)][string]$CacheDir,
  [string]$VivadoBat='D:\Vivado\2026.1\Vivado\bin\vivado.bat'
)
$ErrorActionPreference='Stop'
$rtlDigest='019f9edadd7c3d85b330ec51078117a6586839276783a955ae8e45fbed60ba18'
$leafSha='2b541de975975b5e05060287b2052ce1dc1375b83e601e79a59b79be4dc0efdf'
$oldCacheId='bb03f320fa66fdbd'
$script=Join-Path $PSScriptRoot 'build_fused_hls_ooc_cache.tcl'
foreach($p in @($InputIpDir,$script,$VivadoBat)){if(-not(Test-Path -LiteralPath $p)){throw "Missing input: $p"}}
$live=@(Get-Process vivado,vitis_hls -ErrorAction SilentlyContinue)
if($live.Count -ne 0){throw "Refusing second heavy owner: $($live.Id -join ',')"}
New-Item -ItemType Directory -Force -Path $WorkDir,$EvidenceDir,$CacheDir | Out-Null
$privateUser=Join-Path $EvidenceDir 'private-user';$privateRoaming=Join-Path $privateUser 'AppData\Roaming';$privateLocal=Join-Path $privateUser 'AppData\Local'
$privateManifest=Join-Path $privateRoaming 'Xilinx\Vivado\tclapp\manifest.tcl'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $privateManifest),$privateLocal|Out-Null
[IO.File]::WriteAllText($privateManifest,"::tclapp::load_app -namespace {aldec::activehdl} aldec::activehdl`r`n",(New-Object Text.UTF8Encoding($false)))
$childEnvironment=@{APPDATA=$privateRoaming;LOCALAPPDATA=$privateLocal;USERPROFILE=$privateUser;HOME=$privateUser}
$log=Join-Path $EvidenceDir 'vivado.stdout.log'
$args=@('-mode','batch','-nojournal','-nolog','-source',$script,'-tclargs',(Resolve-Path $InputIpDir).Path,(Resolve-Path $WorkDir).Path,(Resolve-Path $EvidenceDir).Path,(Resolve-Path $CacheDir).Path,$oldCacheId,$rtlDigest)
$p=Start-Process -FilePath $VivadoBat -ArgumentList $args -WindowStyle Hidden -Environment $childEnvironment -PassThru -RedirectStandardOutput $log -RedirectStandardError (Join-Path $EvidenceDir 'vivado.stderr.log')
$p.PriorityClass='BelowNormal'; $p.WaitForExit(); $exit=$p.ExitCode
$token=Select-String -LiteralPath $log -SimpleMatch 'CNN_V10_FUSED_HLS_OOC_CACHE_PASS' -Quiet
if($exit -ne 0 -or -not $token){throw "Vivado fused OOC/cache failed exit=$exit token=$token; see $log"}
$id=@{}; Get-Content (Join-Path $EvidenceDir 'cache-identity.txt') | ForEach-Object {$k,$v=$_ -split '=',2;$id[$k]=$v}
if($id.new_cache_id -eq $oldCacheId){throw 'New cache ID aliases old half cache ID'}
$dcp=Join-Path $EvidenceDir 'cnn_pipeline_v10_fused_hls_0.dcp'
$cacheEntry=Join-Path $CacheDir (Join-Path $id.new_cache_id.Substring(0,1) (Join-Path $id.new_cache_id.Substring(1,1) $id.new_cache_id))
if(-not(Test-Path (Join-Path $cacheEntry 'cnn_pipeline_v10_fused_hls_0.dcp')) -or -not(Test-Path (Join-Path $cacheEntry ($id.new_cache_id+'.xci')))){throw 'Remote cache entry is incomplete'}
$packagedComponent=Join-Path $WorkDir 'hls-ip-fused-cache-identity\component.xml'
$receipt=[ordered]@{
 schema='cnn-v10-pw-half2x-fused-alu-hls-ooc-cache-v1'; status='PASS'; pass=$true; tool_exit=$exit
 canonical_rtl_digest=$rtlDigest; fused_leaf_sha256=$leafSha
 input_ip_dir=(Resolve-Path $InputIpDir).Path; input_component_sha256=(Get-FileHash (Join-Path $InputIpDir 'component.xml') -Algorithm SHA256).Hash.ToLower()
 old_cache_id=$oldCacheId; new_cache_id=$id.new_cache_id; identity_method=$id.identity_method; effective_vlnv=$id.effective_vlnv
 packaged_component=[ordered]@{path=(Resolve-Path $packagedComponent).Path;sha256=(Get-FileHash $packagedComponent -Algorithm SHA256).Hash.ToLower();core_revision=$id.new_core_revision}
 ooc_dcp=[ordered]@{path=(Resolve-Path $dcp).Path;bytes=(Get-Item $dcp).Length;sha256=(Get-FileHash $dcp -Algorithm SHA256).Hash.ToLower()}
 remote_cache_dir=(Resolve-Path $CacheDir).Path; remote_cache_files=@(Get-ChildItem $CacheDir -Recurse -File).Count
 source=[ordered]@{tcl_sha256=(Get-FileHash $script -Algorithm SHA256).Hash.ToLower();runner_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLower()}
 logs=[ordered]@{stdout_sha256=(Get-FileHash $log -Algorithm SHA256).Hash.ToLower();identity_sha256=(Get-FileHash (Join-Path $EvidenceDir 'cache-identity.txt') -Algorithm SHA256).Hash.ToLower();cache_report_sha256=(Get-FileHash (Join-Path $EvidenceDir 'ip-cache-report.rpt') -Algorithm SHA256).Hash.ToLower()}
}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $EvidenceDir 'receipt.json') -Encoding utf8
Write-Output "CNN_V10_FUSED_HLS_OOC_CACHE_RUNNER_PASS cache_id=$($id.new_cache_id)"
