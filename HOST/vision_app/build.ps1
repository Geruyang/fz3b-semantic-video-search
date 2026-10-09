param([switch]$SkipBuild,[string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Project '.venv-vision-client\Scripts\python.exe'
$Dist = Join-Path $Project 'deliverables\vision-console'
if ($OutputDirectory) { $Dist = [IO.Path]::GetFullPath($OutputDirectory) }
if (-not $SkipBuild) {
    & $Python -m PyInstaller --noconfirm --windowed --onedir --name FZ3BVisionConsole --paths $Project --hidden-import timm --hidden-import timm.models.layers --hidden-import open_clip --collect-data open_clip --collect-data timm --collect-all transformers --collect-all imageio_ffmpeg --collect-all av --collect-data sacremoses --distpath $Dist --workpath (Join-Path $Project 'artifacts\ps-application-20261009\pyinstaller') --specpath (Join-Path $Project 'artifacts\ps-application-20261009') (Join-Path $PSScriptRoot 'launch.py')
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
}
$App = Join-Path $Dist 'FZ3BVisionConsole'
& $Python (Join-Path $PSScriptRoot 'tools\packaging_fix.py') $App
if ($LASTEXITCODE -ne 0) { throw 'Qt packaging compatibility check failed' }
foreach ($File in @('semantic-contract.json','client-config.json')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $File) -Destination (Join-Path $App $File) -Force
}
$ModelRoot = Join-Path $App 'models'
$OfficialRoot = Join-Path $ModelRoot 'official-mobileclip'
New-Item -ItemType Directory -Path $OfficialRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $Project 'releases\current\model-source\official-mobileclip\mobileclip') -Destination $OfficialRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Project 'releases\current\model-source\mobileclip_s1.pt') -Destination $ModelRoot -Force
$TranslationSource = Join-Path $Project 'releases\application-resources\opus-mt-zh-en'
New-Item -ItemType Directory -Path (Join-Path $App 'translation') -Force | Out-Null
Get-ChildItem -LiteralPath $TranslationSource -File | Copy-Item -Destination (Join-Path $App 'translation') -Force
foreach ($File in @('LICENSE','LICENSE_MODELS','ACKNOWLEDGEMENTS')) {
    Copy-Item -LiteralPath (Join-Path $Project "releases\current\model-source\official-mobileclip\$File") -Destination $OfficialRoot -Force
}
$ConfigPath = Join-Path $App 'client-config.json'
$Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$Config.model_root = 'models'
$Config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ConfigPath -Encoding utf8NoBOM
& $Python -m pip freeze | Set-Content -LiteralPath (Join-Path $App 'build-environment.txt') -Encoding utf8NoBOM
Get-FileHash -LiteralPath (Join-Path $App 'FZ3BVisionConsole.exe') -Algorithm SHA256 | Select-Object Path,Hash
