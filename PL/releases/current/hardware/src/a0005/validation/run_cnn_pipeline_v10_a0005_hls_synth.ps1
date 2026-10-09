[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EvidenceDir,
    [Parameter(Mandatory = $true)][string]$WorkDir,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedCppSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedHppSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedPointwiseSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedBrokerSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedArithmeticSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGeluSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedIdentitySha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedDdrSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedScaleServiceSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedN1Sha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGeluSegmentedSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedPwDspHeaderSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedPwDspModelSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedPwDspJsonSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedPwDspRtlSha256,
    [ValidateRange(2.0,20.0)][double]$ClockNs = 5.0,
    [ValidateRange(0.0,100.0)][double]$ClockUncertaintyPercent = 27.0,
    [string]$VitisRoot = 'D:\Vivado\2026.1\Vitis'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function To-ConfigPath([string]$Path) {
    return ([IO.Path]::GetFullPath($Path) -replace '\\', '/')
}

function Invoke-OwnedHlsProcess([string]$Command,[string]$Log,[string]$MemoryLog,[string]$OwnedWorkDir) {
    $psi = [Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $env:ComSpec
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Arguments = '/d /s /c "' + $Command + '"'
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $psi
    if (!$process.Start()) { throw 'Failed to start owned v++ process tree' }
    try { $process.PriorityClass = [Diagnostics.ProcessPriorityClass]::BelowNormal } catch { }
    $ownedPid = $process.Id
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $pressureCount = 0
    $terminated = $false
    $intensiveMonitoring = $false
    $observedStageFiles = @{}
    $stageFiles = @(
        (Join-Path $OwnedWorkDir 'hls\syn\report\cnn_pipeline_v10_csynth.rpt'),
        (Join-Path $OwnedWorkDir 'hls\syn\verilog\cnn_pipeline_v10.v'),
        (Join-Path $OwnedWorkDir 'hls\syn\verilog\cnn_pipeline_v10.sv')
    )
    while (!$process.WaitForExit(5000)) {
        $newStageBoundary = $false
        foreach ($stageFile in $stageFiles) {
            if (!$observedStageFiles.ContainsKey($stageFile) -and (Test-Path -LiteralPath $stageFile -PathType Leaf)) {
                $observedStageFiles[$stageFile] = $true
                $newStageBoundary = $true
            }
        }
        if (!$intensiveMonitoring -and !$newStageBoundary) { continue }
        $snapshot = Get-FzTaskMemorySnapshot
        ([ordered]@{ owned_pid=$ownedPid; snapshot=$snapshot } | ConvertTo-Json -Compress) |
            Add-Content -LiteralPath $MemoryLog -Encoding utf8
        if ($snapshot.intensive_monitoring_required) { $intensiveMonitoring = $true } else {
            $intensiveMonitoring = $false
            $pressureCount = 0
        }
        if ($intensiveMonitoring -and $snapshot.pressure) { $pressureCount++ } else { $pressureCount = 0 }
        if ($pressureCount -ge 3) {
            $terminated = $true
            & "$env:SystemRoot\System32\taskkill.exe" /PID $ownedPid /T /F *> $null
            $process.WaitForExit()
            break
        }
    }
    $process.WaitForExit()
    @($stdoutTask.GetAwaiter().GetResult(),$stderrTask.GetAwaiter().GetResult()) |
        Set-Content -LiteralPath $Log -Encoding utf8
    [pscustomobject]@{
        owned_pid=$ownedPid
        exit_code=$process.ExitCode
        terminated_for_memory_pressure=$terminated
        peak_working_set_bytes=$process.PeakWorkingSet64
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sources = [ordered]@{
    'cnn_pipeline_v10.cpp'      = Join-Path $scriptDir 'cnn_pipeline_v10.cpp'
    'cnn_pipeline_v10.hpp'      = Join-Path $scriptDir 'cnn_pipeline_v10.hpp'
    'cnn_v10_pointwise.hpp'     = Join-Path $scriptDir 'cnn_v10_pointwise.hpp'
    'cnn_v10_param_broker.hpp'  = Join-Path $scriptDir 'cnn_v10_param_broker.hpp'
    'cnn_v10_arithmetic.hpp'    = Join-Path $scriptDir 'cnn_v10_arithmetic.hpp'
    'cnn_v10_gelu.hpp'          = Join-Path $scriptDir 'cnn_v10_gelu.hpp'
    'cnn_v10_identity.hpp'      = Join-Path $scriptDir 'cnn_v10_identity.hpp'
    'cnn_v10_ddr.hpp'           = Join-Path $scriptDir 'cnn_v10_ddr.hpp'
    'cnn_v10_scale_service.hpp' = Join-Path $scriptDir 'cnn_v10_scale_service.hpp'
    'cnn_v10_n1.hpp'            = Join-Path $scriptDir 'cnn_v10_n1.hpp'
    'cnn_v10_gelu_segmented.hpp'= Join-Path $scriptDir 'cnn_v10_gelu_segmented.hpp'
    'cnn_v10_pw_dsp.hpp'        = Join-Path $scriptDir 'cnn_v10_pw_dsp.hpp'
    'cnn_v10_pw_dsp_model.cpp'  = Join-Path $scriptDir 'cnn_v10_pw_dsp_model.cpp'
    'cnn_v10_pw_dsp16.json'     = Join-Path $scriptDir 'cnn_v10_pw_dsp16.json'
    'cnn_v10_pw_dsp16.v'        = Join-Path $scriptDir 'cnn_v10_pw_dsp16.v'
    'cnn_pipeline_v10_a0005.hpp'= Join-Path $scriptDir 'cnn_pipeline_v10_a0005.hpp'
    'cnn_v10_pointwise_a0005.hpp'=Join-Path $scriptDir 'cnn_v10_pointwise_a0005.hpp'
    'cnn_v10_storage_contract.hpp'=Join-Path $scriptDir 'cnn_v10_storage_contract.hpp'
    'cnn_v10_storage_helpers.hpp'=Join-Path $scriptDir 'cnn_v10_storage_helpers.hpp'
    'cnn_v10_pw2_storage.hpp'   = Join-Path $scriptDir 'cnn_v10_pw2_storage.hpp'
    'candidate-contract.json'   = Join-Path $scriptDir 'candidate-contract.json'
    'candidate-source-manifest.json'=Join-Path $scriptDir 'candidate-source-manifest.json'
}
$expected = [ordered]@{
    'cnn_pipeline_v10.cpp'      = $ExpectedCppSha256.ToLowerInvariant()
    'cnn_pipeline_v10.hpp'      = $ExpectedHppSha256.ToLowerInvariant()
    'cnn_v10_pointwise.hpp'     = $ExpectedPointwiseSha256.ToLowerInvariant()
    'cnn_v10_param_broker.hpp'  = $ExpectedBrokerSha256.ToLowerInvariant()
    'cnn_v10_arithmetic.hpp'    = $ExpectedArithmeticSha256.ToLowerInvariant()
    'cnn_v10_gelu.hpp'          = $ExpectedGeluSha256.ToLowerInvariant()
    'cnn_v10_identity.hpp'      = $ExpectedIdentitySha256.ToLowerInvariant()
    'cnn_v10_ddr.hpp'           = $ExpectedDdrSha256.ToLowerInvariant()
    'cnn_v10_scale_service.hpp' = $ExpectedScaleServiceSha256.ToLowerInvariant()
    'cnn_v10_n1.hpp'            = $ExpectedN1Sha256.ToLowerInvariant()
    'cnn_v10_gelu_segmented.hpp'= $ExpectedGeluSegmentedSha256.ToLowerInvariant()
    'cnn_v10_pw_dsp.hpp'        = $ExpectedPwDspHeaderSha256.ToLowerInvariant()
    'cnn_v10_pw_dsp_model.cpp'  = $ExpectedPwDspModelSha256.ToLowerInvariant()
    'cnn_v10_pw_dsp16.json'     = $ExpectedPwDspJsonSha256.ToLowerInvariant()
    'cnn_v10_pw_dsp16.v'        = $ExpectedPwDspRtlSha256.ToLowerInvariant()
    'cnn_pipeline_v10_a0005.hpp'= '2383f6f6ea9d7d4cfaedebbe2810e05bdb68d452c09f170e4215ad9c180e0d93'
    'cnn_v10_pointwise_a0005.hpp'= 'a5ca1175d671f7bd87babe1fcb8a1ecba955e559aea7ea0c799f5f031b06be05'
    'cnn_v10_storage_contract.hpp'= 'a2634442d410fef0106ce44e6d6a8012786d24f3b0c7af3fc651f8b877fbd32d'
    'cnn_v10_storage_helpers.hpp'= '3c1ad9a3a8dc0f2306ee533bf347b0b2768adbcf3ea276bde1a9d749aeb78d05'
    'cnn_v10_pw2_storage.hpp'   = '94667c1df475de9ced92d4af608deb0d001c2c79481c1ac78ba6fc97dc0302dd'
    'candidate-contract.json'   = 'a65bdd2c50a5f1b5329350e22a67d9fb9ff4731c3517454ae524f667c5dc3f4d'
    'candidate-source-manifest.json'= 'f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593'
}

if (Test-Path -LiteralPath $EvidenceDir) { throw "EvidenceDir must be new: $EvidenceDir" }
if (Test-Path -LiteralPath $WorkDir) { throw "WorkDir must be new: $WorkDir" }
$vpp = Join-Path $VitisRoot 'bin\v++.bat'
if (!(Test-Path -LiteralPath $vpp)) { throw "Official v++ entry point is missing: $vpp" }
$manifest = Join-Path $env:APPDATA 'Xilinx\Vivado\tclapp\manifest.tcl'
$manifestBackup = "$manifest.fzv10-hls-backup"
$expectedManifestSha = 'b5f010dae71150c1d13d04420150bde07e624fb0b0a1ced3949fcd464d8411b6'
if (!(Test-Path -LiteralPath $manifest -PathType Leaf)) { throw "Missing Tcl app manifest: $manifest" }
if (Test-Path -LiteralPath $manifestBackup) { throw "Refusing existing manifest backup: $manifestBackup" }
$otherManifestBackups = @(Get-ChildItem -LiteralPath (Split-Path -Parent $manifest) -File |
    Where-Object { $_.Name -like 'manifest.tcl*backup*' })
if ($otherManifestBackups.Count) { throw 'Another manifest owner exists' }
$manifestShaBefore = Get-Sha256 $manifest
if ($manifestShaBefore -ne $expectedManifestSha) { throw "Unexpected manifest SHA: $manifestShaBefore" }

$activeNames = @('v++', 'vitis-run', 'vitis_hls', 'vivado', 'xcd')
$active = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $activeNames -contains $_.ProcessName })
if ($active.Count) { throw "Refusing a second heavy tool instance: $($active.ProcessName -join ', ')" }

$actual = [ordered]@{}
foreach ($name in $sources.Keys) {
    if (!(Test-Path -LiteralPath $sources[$name])) { throw "Missing source: $($sources[$name])" }
    $actual[$name] = Get-Sha256 $sources[$name]
    if ($actual[$name] -ne $expected[$name]) {
        throw "Frozen source hash mismatch for ${name}: expected $($expected[$name]), got $($actual[$name])"
    }
}

$blackboxMetadata = Get-Content -LiteralPath $sources['cnn_v10_pw_dsp16.json'] -Raw | ConvertFrom-Json
if ([string]$blackboxMetadata.c_function_name -ne 'cnn_v10_pw_dsp16' -or
    [string]$blackboxMetadata.rtl_top_module_name -ne 'cnn_v10_pw_dsp16' -or
    [string]$blackboxMetadata.rtl_performance.latency -ne '8' -or
    [string]$blackboxMetadata.rtl_performance.II -ne '1' -or
    @($blackboxMetadata.c_files).Count -ne 1 -or
    [string]$blackboxMetadata.c_files[0].c_file -ne 'cnn_v10_pw_dsp_model.cpp' -or
    @($blackboxMetadata.rtl_files).Count -ne 1 -or
    [string]$blackboxMetadata.rtl_files[0] -ne 'cnn_v10_pw_dsp16.v') {
    throw 'Unexpected cnn_v10_pw_dsp16 blackbox metadata contract'
}
$productText = Get-Content -LiteralPath $sources['cnn_pipeline_v10.cpp'] -Raw
$apiText = Get-Content -LiteralPath $sources['cnn_pipeline_v10.hpp'] -Raw
$pointwiseText = Get-Content -LiteralPath $sources['cnn_v10_pointwise.hpp'] -Raw
foreach ($includeName in @('cnn_v10_gelu_segmented.hpp','cnn_v10_pw_dsp.hpp')) {
    if ($productText -notmatch ('#include\s+"' + [regex]::Escape($includeName) + '"') -and
        $apiText -notmatch ('#include\s+"' + [regex]::Escape($includeName) + '"') -and
        $pointwiseText -notmatch ('#include\s+"' + [regex]::Escape($includeName) + '"')) {
        throw "Frozen product does not include $includeName"
    }
}
if ($productText -match 'cnn_v10_stage_ring|stage_ring_(reader|writer)|STAGE_DDR' -or
    $apiText -match 'cnn_v10_stage_ring|kStageRingWords') {
    throw 'A0004 product must not retain the removed q3/q7/expanded DDR stage-ring topology'
}
if ($apiText -notmatch '2\s*\*\s*cnn_v10_slot_words\(p\)\s*\+\s*CNN_V10_SCRATCH_WORDS' -or
    $apiText -notmatch 'typedef\s+ap_uint<11>\s+RowReadyToken' -or
    $productText -notmatch 'param_broker<2>\(ar_a' -or
    $productText -notmatch 'write_broker<2>\(aw_a' -or
    $productText -match '(param|write)_broker<5>') {
    throw 'A0004 direct-FIFO arena, 11-bit row token, or two-client activation-broker contract is missing'
}
if ((Get-Content -LiteralPath $sources['cnn_v10_identity.hpp'] -Raw) -notmatch 'kAbiIdentity\s*=\s*0x000A0005u' -or
    (Get-Content -LiteralPath $sources['cnn_v10_identity.hpp'] -Raw) -notmatch '"sw10[.]5"' -or
    (Get-Content -LiteralPath $sources['cnn_v10_n1.hpp'] -Raw) -notmatch 'kN1ArenaWords\s*=\s*69632') {
    throw 'A0004/sw10.4 identity or direct-FIFO N1 arena contract is missing'
}
if ([regex]::Matches($pointwiseText,'cnn_v10_pw_dsp16_call\s*\(').Count -ne 2 -or
    $pointwiseText -notmatch '#define\s+CNN_V10_PW2_COLUMNS_DEPTH\s+1024') {
    throw 'Frozen pointwise source does not bind both DSP call sites and PW2 depth 1024'
}
if ($pointwiseText -notmatch 'typedef\s+(?:::)?cnn_v10_candidate::Pw2StoredColumn\s+Pw2StoredColumn' -or
    (Get-Content -LiteralPath $sources['cnn_v10_storage_contract.hpp'] -Raw) -notmatch 'kPw2StoredSignedBits\s*=\s*40' -or
    (Get-Content -LiteralPath $sources['cnn_v10_identity.hpp'] -Raw) -notmatch 'kGuardCapabilities\s*=\s*0x00000fffu') {
    throw 'A0005 signed40 storage or capability contract is missing'
}

$evidence = [IO.Path]::GetFullPath($EvidenceDir)
$snapshot = Join-Path $evidence 'source-snapshot'
$work = [IO.Path]::GetFullPath($WorkDir)
New-Item -ItemType Directory -Path $snapshot, $work -Force | Out-Null
foreach ($name in $sources.Keys) { Copy-Item -LiteralPath $sources[$name] -Destination (Join-Path $snapshot $name) }

$cpp = To-ConfigPath (Join-Path $snapshot 'cnn_pipeline_v10.cpp')
$include = To-ConfigPath $snapshot
$blackbox = To-ConfigPath (Join-Path $snapshot 'cnn_v10_pw_dsp16.json')
$config = Join-Path $evidence 'cnn-pipeline-v10-synth.cfg'
$clockText = $ClockNs.ToString('0.000000',[Globalization.CultureInfo]::InvariantCulture)
$uncertaintyText = $ClockUncertaintyPercent.ToString('0.###',[Globalization.CultureInfo]::InvariantCulture)
@"
part=xazu3eg-sfvc784-1-i

[hls]
flow_target=vivado
clock=${clockText}ns
clock_uncertainty=${uncertaintyText}%
syn.top=cnn_pipeline_v10
syn.file=$cpp
syn.file_cflags=$cpp,-I$include
syn.blackbox.file=$blackbox
syn.compile.pipeline_loops=0
syn.interface.m_axi_addr64=true
"@ | Set-Content -LiteralPath $config -Encoding ascii

$command = "`"$vpp`" -c --mode hls --config `"$config`" --work_dir `"$work`""
$command | Set-Content -LiteralPath (Join-Path $evidence 'command.txt') -Encoding ascii
$started = (Get-Date).ToUniversalTime()
$exitCode = 999
$errorModeHelper = Join-Path $scriptDir 'task_tool_error_mode.ps1'
$memoryHelper = Join-Path $scriptDir 'task_tool_memory.ps1'
foreach ($helper in @($errorModeHelper,$memoryHelper)) {
    if (!(Test-Path -LiteralPath $helper -PathType Leaf)) { throw "Missing task launch helper: $helper" }
    . $helper
}
$launchMemory = Assert-FzTaskMemoryForLaunch
$previousErrorMode = Enable-FzTaskToolErrorMode
$ownedResult = $null
$manifestMoved = $false
$manifestShaAfter = $null
$manifestRestoredExactly = $false
try {
    Move-Item -LiteralPath $manifest -Destination $manifestBackup
    $manifestMoved = $true
    $ownedResult = Invoke-OwnedHlsProcess -Command $command `
        -Log (Join-Path $evidence 'vpp-hls-synth.log') `
        -MemoryLog (Join-Path $evidence 'memory-pressure.jsonl') `
        -OwnedWorkDir $work
    $exitCode = $ownedResult.exit_code
} finally {
    if ($manifestMoved) {
        if (Test-Path -LiteralPath $manifest) {
            Copy-Item -LiteralPath $manifest -Destination (Join-Path $evidence 'manifest-generated-during-hls.tcl')
            Remove-Item -LiteralPath $manifest -Force
        }
        if (Test-Path -LiteralPath $manifestBackup) { Move-Item -LiteralPath $manifestBackup -Destination $manifest }
        if (Test-Path -LiteralPath $manifest) {
            $manifestShaAfter = Get-Sha256 $manifest
            $manifestRestoredExactly = ($manifestShaAfter -eq $manifestShaBefore)
        }
    }
    Restore-FzTaskToolErrorMode -PreviousMode $previousErrorMode
    $finished = (Get-Date).ToUniversalTime()
}

$processDeadline = (Get-Date).AddSeconds(30)
do {
    $remaining = @(Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $activeNames -contains $_.ProcessName } |
        Select-Object ProcessName, Id, StartTime)
    if (!$remaining.Count -or (Get-Date) -ge $processDeadline) { break }
    Start-Sleep -Milliseconds 500
} while ($true)
$reports = @(Get-ChildItem -LiteralPath $work -Recurse -File -Filter '*_csynth.rpt' -ErrorAction SilentlyContinue)
$rtl = @(Get-ChildItem -LiteralPath $work -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @('cnn_pipeline_v10.v', 'cnn_pipeline_v10.sv') })
$ipZips = @(Get-ChildItem -LiteralPath $work -Recurse -File -Filter '*.zip' -ErrorAction SilentlyContinue)
$xcdLogs = @(Get-ChildItem -LiteralPath $work -Recurse -File -Filter 'xcd.log' -ErrorAction SilentlyContinue)

$eventQuery = [ordered]@{ available = $false; events = @(); error = $null }
try {
    $events = @(Get-WinEvent -FilterHashtable @{ LogName = 'Application'; StartTime = $started.ToLocalTime() } -ErrorAction Stop |
        Where-Object { $_.ProviderName -match 'Application Error|Windows Error Reporting' -and $_.Message -match '(?i)\bxcd\.exe\b' } |
        Select-Object TimeCreated, Id, ProviderName, Message)
    $eventQuery.available = $true
    $eventQuery.events = $events
} catch {
    $eventErrorId = [string]$_.FullyQualifiedErrorId
    $eventErrorMessage = [string]$_.Exception.Message
    if ($eventErrorId -match 'NoMatchingEventsFound' -or
        $eventErrorMessage -match '^No events were found that match the specified selection criteria\.?$') {
        $eventQuery.available = $true
        $eventQuery.events = @()
        $eventQuery.error = $null
    } else { $eventQuery.error = $eventErrorMessage }
}

$logInventory = @()
foreach ($file in @(Get-ChildItem -LiteralPath $work -Recurse -File -Include '*.log','*.rpt' -ErrorAction SilentlyContinue)) {
    $logInventory += [ordered]@{
        path = $file.FullName.Substring($work.Length).TrimStart('\')
        bytes = $file.Length
        sha256 = Get-Sha256 $file.FullName
    }
}
$rtlInventory = @()
foreach ($file in $rtl) {
    $rtlInventory += [ordered]@{ path=$file.FullName; bytes=$file.Length; sha256=Get-Sha256 $file.FullName }
}
$ipInventory = @()
foreach ($file in $ipZips) {
    $ipInventory += [ordered]@{ path=$file.FullName; bytes=$file.Length; sha256=Get-Sha256 $file.FullName }
}

$receipt = [ordered]@{
    schema = 'cnn-pipeline-v10-hls-synth-receipt-v1'
    started_utc = $started.ToString('o')
    finished_utc = $finished.ToString('o')
    official_entry = $vpp
    tool_exit_code = $exitCode
    target_part = 'xazu3eg-sfvc784-1-i'
    clock_ns = $ClockNs
    clock_uncertainty_percent = $ClockUncertaintyPercent
    clock_uncertainty_ns = $ClockNs * $ClockUncertaintyPercent / 100.0
    hls_service_instances = 1
    hls_internal_jobs_control = 'not asserted: Vitis HLS 2026.1 rejects hls.jobs as unknown'
    launch_memory = $launchMemory
    owned_pid = if ($null -ne $ownedResult) { $ownedResult.owned_pid } else { $null }
    peak_working_set_bytes = if ($null -ne $ownedResult) { $ownedResult.peak_working_set_bytes } else { $null }
    terminated_for_memory_pressure = if ($null -ne $ownedResult) { $ownedResult.terminated_for_memory_pressure } else { $false }
    evidence_dir = $evidence
    work_dir = $work
    source_sha256 = $actual
    blackbox_config = [ordered]@{
        option = 'hls.syn.blackbox.file'
        file = $blackbox
        metadata_sha256 = $actual['cnn_v10_pw_dsp16.json']
        native_model_sha256 = $actual['cnn_v10_pw_dsp_model.cpp']
        rtl_sha256 = $actual['cnn_v10_pw_dsp16.v']
    }
    manifest_sha256_before = $manifestShaBefore
    manifest_sha256_after = $manifestShaAfter
    manifest_restored_exactly = $manifestRestoredExactly
    csynth_reports = @($reports.FullName)
    rtl_top_files = $rtlInventory
    ip_zips = $ipInventory
    xcd_logs = @($xcdLogs.FullName)
    heavy_tool_processes_remaining = $remaining
    xcd_application_events = $eventQuery
    log_inventory = $logInventory
    requires_xcd_health_review = $true
    product_gate = [ordered]@{
        tool_exit_zero = ($exitCode -eq 0)
        csynth_report_present = ($reports.Count -gt 0)
        rtl_top_present = ($rtl.Count -gt 0)
        packaged_ip_present = ($ipZips.Count -gt 0)
        no_tool_process_remaining = ($remaining.Count -eq 0)
        no_recorded_xcd_crash = ($eventQuery.available -and $eventQuery.events.Count -eq 0)
        not_terminated_for_memory_pressure = ($null -ne $ownedResult -and !$ownedResult.terminated_for_memory_pressure)
    }
}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence 'receipt.json') -Encoding utf8
$exitCode | Set-Content -LiteralPath (Join-Path $evidence 'exit-code.txt') -Encoding ascii

if (!$manifestRestoredExactly) { exit 99 }
if ($null -ne $ownedResult -and $ownedResult.terminated_for_memory_pressure) { exit 98 }
if ($exitCode -ne 0) { exit $exitCode }
if (!$reports.Count -or !$rtl.Count -or !$ipZips.Count -or $remaining.Count) { exit 96 }
if ($eventQuery.available -and $eventQuery.events.Count) { exit 95 }
exit 0


