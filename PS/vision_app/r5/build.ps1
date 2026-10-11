$ErrorActionPreference='Stop'
$Compiler='D:\Vivado\2026.1\Vitis\gnu\armr5\nt\gcc-arm-none-eabi\bin\armr5-none-eabi-gcc.exe'
$Output=Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'build\r5'
New-Item -ItemType Directory -Force -Path $Output | Out-Null
foreach ($Core in 0,1) {
 & $Compiler -mcpu=cortex-r5 -marm -O2 -Wall -Wextra -Werror -ffreestanding -fno-builtin -nostdlib "-DCORE_ID=$Core" (Join-Path $PSScriptRoot 'start.S') (Join-Path $PSScriptRoot 'worker.c') "-Wl,-T,$PSScriptRoot\tcm.ld" '-Wl,--build-id=none' -o (Join-Path $Output "fz3b-app-r5$Core.elf")
 if ($LASTEXITCODE -ne 0) { throw 'R5 firmware compile failed' }
}
& 'D:\Vivado\2026.1\Vivado\bin\dtc.exe' -@ -I dts -O dtb -o (Join-Path $Output 'tcm-split-overlay.dtbo') (Join-Path $PSScriptRoot 'tcm-split-overlay.dts')
if ($LASTEXITCODE -ne 0) { throw 'R5 overlay compile failed' }
