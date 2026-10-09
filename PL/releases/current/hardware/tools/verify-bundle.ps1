[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifestPath=Join-Path $root 'manifest.json'
$manifest=Get-Content -Raw -LiteralPath $manifestPath|ConvertFrom-Json
$failures=[Collections.Generic.List[string]]::new()
foreach($entry in $manifest.files){
    $path=Join-Path $root ([string]$entry.path -replace '/','\')
    if(!(Test-Path -LiteralPath $path -PathType Leaf)){$failures.Add("missing:$($entry.path)");continue}
    $item=Get-Item -LiteralPath $path
    if($item.Length-ne[long]$entry.bytes){$failures.Add("bytes:$($entry.path)");continue}
    $sha=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if($sha-ne[string]$entry.sha256){$failures.Add("sha256:$($entry.path)")}
}
$productPaths=[ordered]@{
    routed_dcp_sha256='implementation/routed/a0005-post-route.dcp'
    bit_sha256='implementation/final/a0005-post-route.bit'
    bin_sha256='implementation/final/a0005-post-route.bin'
    factory_bin_sha256='deployment/a0005-final/recovery/factory-restore-native.bin'
    factory_ko_sha256='deployment/a0005-final/recovery/fpgadrv.ko'
}
foreach($key in $productPaths.Keys){
    $path=Join-Path $root ($productPaths[$key]-replace'/','\')
    if(!(Test-Path -LiteralPath $path -PathType Leaf)){$failures.Add("product-missing:$key");continue}
    $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if($actual-ne[string]$manifest.products.$key){$failures.Add("product-sha256:$key")}
}
$known=@($manifest.files|ForEach-Object{[string]$_.path})
$extra=@(Get-ChildItem -LiteralPath $root -Recurse -File|ForEach-Object{$_.FullName.Substring($root.Length+1)-replace '\\','/'}|Where-Object{$_-notin$known-and$_-notin@('manifest.json','SHA256SUMS.txt')})
if($extra.Count){$failures.Add("unexpected-files:$($extra-join',')")}
$result=[ordered]@{schema=$manifest.schema;pass=($failures.Count-eq0);checked=@($manifest.files).Count;failures=@($failures);manifest_sha256=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()}
$result|ConvertTo-Json -Depth 5
if($failures.Count){exit 1}
