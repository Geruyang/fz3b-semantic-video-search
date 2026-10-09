[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$ReadyReceipt,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedReadyReceiptSha256,
    [int]$AllowedVivadoPid=0,
    [string]$VivadoRoot='D:\Vivado\2026.1\Vivado'
)

$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

function Get-Sha256([string]$Path) {
    for ($attempt=1; $attempt -le 120; $attempt++) {
        try { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
        catch [System.IO.IOException] {
            if ($attempt -eq 120) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
    throw "Unreachable SHA256 retry state for $Path"
}

function Assert-JsonProperty($Object, [string]$Name) {
    if ($null -eq $Object.PSObject.Properties[$Name]) { throw "Missing JSON property: $Name" }
    return $Object.$Name
}

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$bundle=Join-Path $root 'artifacts\board-debug-20261008\acceleration\host\network10-v10.5-a0005-deployment-final-001'
$manifest=Join-Path $bundle 'manifest.json'
$bit=Join-Path $bundle 'platform\cnn-v10.5-a0005.bit'
$factory=Join-Path $bundle 'recovery\factory-restore-native.bin'
$tcl=Join-Path $PSScriptRoot 'program_cnn_v10_a0005_noila.tcl'
$vivado=Join-Path $VivadoRoot 'bin\vivado.bat'
$hwServer=Join-Path $VivadoRoot 'bin\hw_server.bat'
$readyReceiptPath=[IO.Path]::GetFullPath($ReadyReceipt)
$evidence=[IO.Path]::GetFullPath($EvidenceDir)
$programOutput=Join-Path $evidence 'program-output'
$expected=[ordered]@{
    manifest='6e01472fae50fcab672bf8a6097648630618b8b304c860f0703472cd6ec1d2f3'
    bit='a7950894715edd4e0f535b094e4a7866a220bd44f7158d153bb8e927d07bdebc'
    factory='59e1a6176194eccc05603738ba3c2e71ea25c3c09cdf9dce47ed1ad1ddf5fc2e'
}

foreach ($path in @($manifest,$bit,$factory,$tcl,$vivado,$hwServer,$readyReceiptPath)) {
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing exact input: $path" }
}
foreach ($pair in @(
    @($manifest,$expected.manifest),
    @($bit,$expected.bit),
    @($factory,$expected.factory),
    @($readyReceiptPath,$ExpectedReadyReceiptSha256.ToLowerInvariant())
)) {
    if ((Get-Sha256 $pair[0]) -ne $pair[1]) { throw "SHA mismatch: $($pair[0])" }
}

$parsed=Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ((Assert-JsonProperty $parsed 'status') -ne 'READY_FOR_BOARD_VALIDATION') { throw 'Deployment manifest is not READY' }
if ($parsed.identity.core_id -ne '0x465A5641' -or $parsed.identity.core_abi -ne '0x000A0005' -or $parsed.identity.guard_caps -ne '0x00000FFF') { throw 'Deployment identity mismatch' }
if ($parsed.combined_parameter_manifest_sha256 -ne '4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690') { throw 'Combined manifest mismatch' }
if ($parsed.debug_profile.mode -ne 'release-no-ila' -or
    $parsed.debug_profile.guard_ila_count -ne 0 -or
    $parsed.debug_profile.pipeline_ila_count -ne 0 -or
    $parsed.debug_profile.debug_hub_count -ne 0 -or
    $parsed.debug_profile.trace_pack_present -ne $false -or
    $parsed.debug_profile.mmio_trace_count -ne 0 -or
    $parsed.debug_profile.platform_trace_mmio_register_count -ne 0 -or
    $parsed.debug_profile.hls_ap_none_trace_port_count -ne 12 -or
    $parsed.debug_profile.trace_outputs_connected -ne $false -or
    $parsed.debug_profile.trace_output_transport -ne 'ap_none' -or
    $parsed.debug_profile.ltx_required -ne $false) { throw 'Debug profile is not canonical release-no-ila/ap_none-unconnected' }
if ($parsed.files.bitstream.sha256 -ne $expected.bit -or $parsed.files.factory_bitstream.sha256 -ne $expected.factory) { throw 'Manifest artifact identity mismatch' }
if (@(Get-ChildItem -LiteralPath $bundle -Recurse -File -Filter '*.ltx').Count -ne 0) { throw 'release-no-ila bundle must not contain LTX files' }
foreach ($gate in @('full_platform_route_pass','all_rtl_profiles_pass','rtl_stress_pass','guard_six_master_pass','restore_assets_verified')) {
    if ($parsed.gates.$gate -ne $true) { throw "Required deployment gate is false: $gate" }
}

$ready=Get-Content -LiteralPath $readyReceiptPath -Raw | ConvertFrom-Json
if ($null -ne $ready.PSObject.Properties['pass'] -and $ready.pass -ne $true) { throw 'Fresh ready receipt does not pass' }
$readyStatus=[string](Assert-JsonProperty $ready 'status')
if (!$readyStatus.StartsWith('READY_FOR_JTAG',[StringComparison]::Ordinal)) { throw "Fresh receipt is not READY_FOR_JTAG: $readyStatus" }

if (Test-Path -LiteralPath $evidence) { throw 'EvidenceDir must be new' }
$amdBefore=@(Get-Process vivado,vitis_hls,vitis-run,v++,xcd -ErrorAction SilentlyContinue)
$allowedBefore=@()
if ($AllowedVivadoPid -ne 0) {
    $allowedBefore=@($amdBefore | Where-Object {$_.Id -eq $AllowedVivadoPid})
    if ($allowedBefore.Count -ne 1 -or $allowedBefore[0].ProcessName -ne 'vivado' -or
        $allowedBefore[0].Path -ne (Join-Path $VivadoRoot 'bin\unwrapped\win64.o\vivado.exe')) {
        throw 'AllowedVivadoPid does not identify exactly one official Vivado process'
    }
}
$unexpectedBefore=@($amdBefore | Where-Object {$_.Id -ne $AllowedVivadoPid})
if ($unexpectedBefore.Count) { throw "AMD hardware/programming tool slot occupied: $($unexpectedBefore.Id -join ',')" }
New-Item -ItemType Directory -Path $evidence | Out-Null
$privateAppData=Join-Path $evidence 'private-appdata'
$privateLocalAppData=Join-Path $evidence 'private-appdata-local'
New-Item -ItemType Directory -Path $privateAppData,$privateLocalAppData | Out-Null
$childEnvironment=@{APPDATA=$privateAppData;LOCALAPPDATA=$privateLocalAppData}
$stdout=Join-Path $evidence 'vivado.stdout.log'
$stderr=Join-Path $evidence 'vivado.stderr.log'
$hsout=Join-Path $evidence 'hw_server.stdout.log'
$hserr=Join-Path $evidence 'hw_server.stderr.log'

$ownedServer=$null
if (!(Test-NetConnection localhost -Port 3121 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    $ownedServer=Start-Process -FilePath $hwServer -ArgumentList @('-s','tcp::3121') -WindowStyle Hidden -PassThru -RedirectStandardOutput $hsout -RedirectStandardError $hserr -Environment $childEnvironment
    try { $ownedServer.PriorityClass=[Diagnostics.ProcessPriorityClass]::AboveNormal } catch {}
    $readyServer=$false
    for ($i=0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-NetConnection localhost -Port 3121 -InformationLevel Quiet -WarningAction SilentlyContinue) { $readyServer=$true; break }
    }
    if (!$readyServer) {
        if (!$ownedServer.HasExited) { $ownedServer.Kill($true) }
        throw 'hw_server did not become ready'
    }
}

$started=Get-Date
$args=@('-mode','batch','-source',$tcl,'-nojournal','-nolog','-notrace','-tclargs',$bit,$factory,$programOutput)
$p=Start-Process -FilePath $vivado -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr -Environment $childEnvironment
try { $p.PriorityClass=[Diagnostics.ProcessPriorityClass]::AboveNormal } catch {}
$p.WaitForExit()
$p.Refresh()
$vivadoExitCode=$p.ExitCode
$p.Dispose()
if ($null -ne $ownedServer -and !$ownedServer.HasExited) { $ownedServer.Kill($true); $ownedServer.WaitForExit() }
Start-Sleep -Seconds 2

$endMarker=(Test-Path -LiteralPath $stdout) -and (Select-String -LiteralPath $stdout -SimpleMatch 'CNN_V10_A0005_NOILA_PROGRAM_END RC=0 MODIFIED=1 FACTORY_RESTORED=0' -Quiet)
$programMarker=(Test-Path -LiteralPath $stdout) -and (Select-String -LiteralPath $stdout -SimpleMatch 'CNN_V10_A0005_NOILA_PROGRAM_OK ILA_COUNT=0 MODIFIED=1 FACTORY_RESTORED=0' -Quiet)
$active=@(Get-Process vivado,vitis_hls,vitis-run,v++,xcd -ErrorAction SilentlyContinue)
$unexpectedActive=@($active | Where-Object {$_.Id -ne $AllowedVivadoPid})
$allowedStillPresent=@($active | Where-Object {$_.Id -eq $AllowedVivadoPid})
$pass=($vivadoExitCode -eq 0 -and $endMarker -and $programMarker -and
       $unexpectedActive.Count -eq 0 -and
       (($AllowedVivadoPid -eq 0) -or $allowedStillPresent.Count -eq 1))
$receipt=[ordered]@{
    schema='cnn-v10.5-a0005-noila-program-v1'
    pass=$pass
    exit_code=$vivadoExitCode
    started=$started.ToString('o')
    finished=(Get-Date).ToString('o')
    target='localhost:3121/xilinx_tcf/Digilent/210251190311 xczu3_0 14710093'
    command='program_hw_devices -mpsoc_reset no'
    ps_reset=$false
    deployment_manifest=[ordered]@{path=$manifest;sha256=$expected.manifest}
    fresh_ready_receipt=[ordered]@{path=$readyReceiptPath;sha256=$ExpectedReadyReceiptSha256.ToLowerInvariant();status=$readyStatus}
    bit=[ordered]@{path=$bit;bytes=(Get-Item -LiteralPath $bit).Length;sha256=$expected.bit}
    debug_profile=$parsed.debug_profile
    factory_fallback=[ordered]@{path=$factory;bytes=(Get-Item -LiteralPath $factory).Length;sha256=$expected.factory}
    source=[ordered]@{tcl_sha256=Get-Sha256 $tcl;runner_sha256=Get-Sha256 $MyInvocation.MyCommand.Path}
    logs=[ordered]@{stdout_sha256=Get-Sha256 $stdout;stderr_sha256=Get-Sha256 $stderr}
    exact_zero_ilas_found=$programMarker
    factory_restored=$false
    allowed_concurrent_vivado_pid=$AllowedVivadoPid
    allowed_concurrent_vivado_present_after=($allowedStillPresent.Count -eq 1)
    unexpected_residual_amd_processes=@($unexpectedActive | ForEach-Object {"$($_.ProcessName):$($_.Id)"})
}
$receipt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $evidence 'receipt.json') -Encoding utf8
if (!$pass) { throw 'A0005 PL programming failed; inspect Tcl log and whether the automatic factory fallback succeeded' }
Write-Output ($receipt | ConvertTo-Json -Depth 10 -Compress)

