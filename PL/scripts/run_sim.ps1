param([Parameter(Mandatory=$true)][string]$Top, [string]$VivadoBin = 'D:\Vivado\2026.1\Vivado\bin', [string[]]$Sources = @())
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$work = Join-Path $root "sim/$Top"
New-Item -ItemType Directory -Force -Path $work | Out-Null
if ($Sources.Count -eq 0) {
  $Sources = @((Join-Path $root 'rtl/cnn_axi_pkg.sv'),(Join-Path $root 'rtl/cnn_math_pkg.sv')) + @(Get-ChildItem (Join-Path $root 'rtl') -File | Where-Object { $_.Extension -in '.sv','.v' -and $_.Name -notin 'cnn_axi_pkg.sv','cnn_math_pkg.sv','cnn_rtl_bd.sv' } | ForEach-Object FullName) + @((Join-Path $root "tb/$Top.sv"))
}
$env:XILINX_LOCAL_USER_DATA = Join-Path $work 'user-data'
New-Item -ItemType Directory -Force -Path $env:XILINX_LOCAL_USER_DATA | Out-Null
Push-Location $work
try {
  & (Join-Path $VivadoBin 'xvlog.bat') -sv @Sources
  if ($LASTEXITCODE -ne 0) { throw 'xvlog failed' }
  & (Join-Path $VivadoBin 'xelab.bat') $Top -L unisims_ver -L unimacro_ver -L xpm -s $Top
  if ($LASTEXITCODE -ne 0) { throw 'xelab failed' }
  & (Join-Path $VivadoBin 'xsim.bat') $Top -runall -log "$Top.log"
  if ($LASTEXITCODE -ne 0) { throw 'xsim failed' }
  if (-not (Select-String -LiteralPath "$Top.log" -Pattern 'PASS' -Quiet)) { throw 'Self-check did not emit PASS' }
} finally { Pop-Location }


