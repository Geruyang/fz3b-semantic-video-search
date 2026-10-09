[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$WorkspaceRoot,
    [switch]$Apply,
    [switch]$Force
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$bundle=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workspace=[IO.Path]::GetFullPath($WorkspaceRoot)
if(!(Test-Path -LiteralPath $workspace -PathType Container)){throw "WorkspaceRoot not found: $workspace"}
$manifest=Get-Content -Raw -LiteralPath (Join-Path $bundle 'manifest.json')|ConvertFrom-Json
$planned=0;$copied=0;$existing=0
foreach($entry in $manifest.files){
    $sourcePath=[string]$entry.source_path
    if($sourcePath.StartsWith('generated:',[StringComparison]::Ordinal)){continue}
    $src=Join-Path $bundle ([string]$entry.path -replace '/','\')
    $dst=[IO.Path]::GetFullPath((Join-Path $workspace ($sourcePath-replace'/','\')))
    if(!$dst.StartsWith($workspace+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw "Refusing path outside workspace: $dst"}
    $planned++
    if(Test-Path -LiteralPath $dst){
        $existing++
        $sha=(Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()
        if($sha-eq[string]$entry.sha256){continue}
        if(!$Force){throw "Existing file differs; use -Force only after review: $dst"}
    }
    if($Apply){
        $parent=Split-Path -Parent $dst
        if(!(Test-Path -LiteralPath $parent)){New-Item -ItemType Directory -Path $parent -Force|Out-Null}
        Copy-Item -LiteralPath $src -Destination $dst -Force:$Force
        $copied++
    }
}
[ordered]@{apply=[bool]$Apply;force=[bool]$Force;planned=$planned;already_present=$existing;copied=$copied}|ConvertTo-Json -Compress
