param([string]$Port = 'COM6', [switch]$Restart)
$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Project '.venv-vision-client\Scripts\python.exe'
Push-Location $Project
try {
    $Arguments = @('-m', 'vision_app.tools.manual_start', '--port', $Port)
    if ($Restart) { $Arguments += '--restart' }
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Manual board application start failed; see preceding diagnostics.' }
} finally {
    Pop-Location
}
