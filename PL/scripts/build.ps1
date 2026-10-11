param([string]$Vivado = 'D:\Vivado\2026.1\Vivado\bin\vivado.bat', [switch]$CreateOnly, [switch]$SynthOnly, [string]$ProjectDirectory = '', [string]$SourceDirectory = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path -LiteralPath $Vivado)) { throw "Vivado not found: $Vivado. Supply -Vivado." }
$entry = if ($CreateOnly) { 'create_project.tcl' } else { 'build.tcl' }
$buildProject = if ($ProjectDirectory) { $ProjectDirectory } else { Join-Path $root 'project-final-008' }
$reportDir = Join-Path (Join-Path $root 'reports/platform') (Split-Path $buildProject -Leaf)
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot $entry) -Destination (Join-Path $reportDir "$entry.executed.tcl") -Force
$env:XILINX_LOCAL_USER_DATA = Join-Path $reportDir 'user-data'
New-Item -ItemType Directory -Force -Path $env:XILINX_LOCAL_USER_DATA | Out-Null
$manifestRoot = if ($SourceDirectory) { $SourceDirectory } elseif (Test-Path -LiteralPath (Join-Path $buildProject 'source_snapshot')) { Join-Path $buildProject 'source_snapshot' } else { $root }
$sources = Get-ChildItem -LiteralPath (Join-Path $manifestRoot 'rtl'),(Join-Path $manifestRoot 'platform'),(Join-Path $manifestRoot 'constraints'),$PSScriptRoot -File | Where-Object { $_.Extension -in '.sv','.v','.xdc','.tcl','.ps1' }
$manifest = $sources | ForEach-Object { @{ path = $_.FullName; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower() } }
$manifest | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $reportDir 'source_manifest.json')
$buildArgs = @($buildProject)
if ($SynthOnly) { $buildArgs += 'synth-only' }
if ($SourceDirectory) {
  if (-not $CreateOnly) { throw '-SourceDirectory is only supported with -CreateOnly for a new immutable project.' }
  $buildArgs += $SourceDirectory
}
& $Vivado -mode batch -source (Join-Path $PSScriptRoot $entry) -log (Join-Path $reportDir "$entry.log") -journal (Join-Path $reportDir "$entry.jou") -tclargs @buildArgs
if ($LASTEXITCODE -ne 0) { throw "Vivado failed ($LASTEXITCODE); see reports/platform." }
if (-not $CreateOnly -and -not $SynthOnly -and -not (Test-Path -LiteralPath (Join-Path $reportDir 'signoff.txt'))) { throw 'No successful routed signoff receipt.' }




if (-not $CreateOnly -and -not $SynthOnly) {
  $receiptPath = Join-Path $reportDir 'route_receipt.json'
  if (-not (Test-Path -LiteralPath $receiptPath)) { throw 'No machine-readable routed signoff receipt.' }
  $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
  $snapshotHash = (Get-FileHash -LiteralPath (Join-Path $buildProject 'source_snapshot/SHA256SUMS.txt') -Algorithm SHA256).Hash.ToLower()
  if ($receipt.status -ne 'ROUTED_SIGNOFF_PASS' -or $receipt.source_snapshot_sha256 -ne $snapshotHash) { throw 'Receipt does not match this immutable source capture.' }
}
