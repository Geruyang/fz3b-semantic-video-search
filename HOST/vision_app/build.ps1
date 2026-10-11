param([switch]$SkipBuild,[string]$OutputDirectory,[string]$ConfigPath,[string]$Python)
$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Workspace = [IO.Path]::GetFullPath((Join-Path $Project '..\..\..'))
if (-not $Python) { $Python = Join-Path $Project '.venv-vision-client\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Create the HOST virtual environment from requirements.txt, or supply -Python.' }
$Dist = Join-Path $Workspace '.build\client\dist'
$PublishedApp = Join-Path $Workspace 'deliverables\vision-console\FZ3BVisionConsole'
if ($OutputDirectory) { $Dist = [IO.Path]::GetFullPath($OutputDirectory) }
$App = Join-Path $Dist 'FZ3BVisionConsole'
if ([IO.Path]::GetFullPath($App).TrimEnd('\') -eq [IO.Path]::GetFullPath($PublishedApp).TrimEnd('\')) { throw 'Build to a staging directory before publishing; preserved model assets must not be overwritten.' }
if (-not $SkipBuild) {
    & $Python -c "import importlib.util,pathlib; packages=['open_clip','timm','transformers','av']; assert all(importlib.util.find_spec(p) is not None for p in packages), 'Install all requirements before building'; spec=importlib.util.find_spec('open_clip'); assert pathlib.Path(spec.submodule_search_locations[0],'bpe_simple_vocab_16e6.txt.gz').is_file(), 'Incomplete open_clip installation'"
    if ($LASTEXITCODE -ne 0) { throw 'Build dependencies are incomplete; finish installation before building.' }
    & $Python -m PyInstaller --noconfirm --windowed --onedir --name FZ3BVisionConsole --paths $Project --hidden-import timm --hidden-import timm.models.layers --hidden-import open_clip --collect-data open_clip --collect-data timm --collect-all transformers --collect-all imageio_ffmpeg --collect-all av --collect-data sacremoses --distpath $Dist --workpath (Join-Path $Workspace '.build\client\work') --specpath (Join-Path $Workspace '.build\client') (Join-Path $PSScriptRoot 'launch.py')
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
}
$App = Join-Path $Dist 'FZ3BVisionConsole'
& $Python (Join-Path $PSScriptRoot 'tools\packaging_fix.py') $App
if ($LASTEXITCODE -ne 0) { throw 'Qt packaging compatibility check failed' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'semantic-contract.json') -Destination $App -Force
if (-not $ConfigPath) { $ConfigPath = Join-Path $PSScriptRoot 'client-config.json' }
if (-not (Test-Path -LiteralPath $ConfigPath)) { $ConfigPath = Join-Path $Workspace 'deliverables\vision-console\FZ3BVisionConsole\client-config.json' }
if (-not (Test-Path -LiteralPath $ConfigPath)) { $ConfigPath = Join-Path $PSScriptRoot 'client-config.example.json' }
$Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$Config.PSObject.Properties.Remove('token')
$Config.model_root = 'models'
$Config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $App 'client-config.json') -Encoding utf8NoBOM
$ModelRoot = Join-Path $App 'models'
$OfficialRoot = Join-Path $ModelRoot 'official-mobileclip'
New-Item -ItemType Directory -Path $OfficialRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PublishedApp 'models\official-mobileclip\mobileclip') -Destination $OfficialRoot -Recurse -Force
$Weights = Join-Path $PublishedApp 'models\mobileclip_s1.pt'
Copy-Item -LiteralPath $Weights -Destination $ModelRoot -Force
$TranslationSource = Join-Path $PublishedApp 'translation'
New-Item -ItemType Directory -Path (Join-Path $App 'translation') -Force | Out-Null
Get-ChildItem -LiteralPath $TranslationSource -File | Copy-Item -Destination (Join-Path $App 'translation') -Force
foreach ($File in @('LICENSE','LICENSE_MODELS','ACKNOWLEDGEMENTS')) {
    Copy-Item -LiteralPath (Join-Path $PublishedApp "models\official-mobileclip\$File") -Destination $OfficialRoot -Force
}
& $Python -m pip freeze | Set-Content -LiteralPath (Join-Path $App 'build-environment.txt') -Encoding utf8NoBOM
Get-FileHash -LiteralPath (Join-Path $App 'FZ3BVisionConsole.exe') -Algorithm SHA256 | Select-Object Path,Hash
