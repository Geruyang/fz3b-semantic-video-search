$ErrorActionPreference='Stop'
& python (Join-Path $PSScriptRoot 'preflight_reference.py') --run
if($LASTEXITCODE){throw 'Preflight bound verification failed'}
