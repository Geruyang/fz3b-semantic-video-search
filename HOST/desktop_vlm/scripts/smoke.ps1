param(
  [Parameter(Mandatory=$true)][string]$Python,
  [Parameter(Mandatory=$true)][string]$OfficialRepo,
  [Parameter(Mandatory=$true)][string]$Weights,
  [Parameter(Mandatory=$true)][string]$Image,
  [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $projectDir 'src'
$env:TORCH_FORCE_WEIGHTS_ONLY_LOAD = '1'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$cachePath = Join-Path $OutputDirectory 'texts.npz'
$promptsPath = Join-Path $projectDir 'configs/prompts.en-zh.json'
& $Python -B -m desktop_vlm doctor
if ($LASTEXITCODE -ne 0) { throw 'doctor failed' }
& $Python -B -m desktop_vlm cache-text --official-repo $OfficialRepo --weights $Weights --prompts $promptsPath --output $cachePath --json (Join-Path $OutputDirectory 'cache.json')
if ($LASTEXITCODE -ne 0) { throw 'cache-text failed' }
& $Python -B -m desktop_vlm match --official-repo $OfficialRepo --weights $Weights --image $Image --cache $cachePath --prompts $promptsPath --top-k 5 --json (Join-Path $OutputDirectory 'match.json')
if ($LASTEXITCODE -ne 0) { throw 'match failed' }
