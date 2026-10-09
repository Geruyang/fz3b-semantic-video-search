[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ProjectDir,
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$HlsIpDir,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ComponentSha,
    [Parameter(Mandatory=$true)][string]$ChainParameterManifest,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ChainParameterManifestSha,
    [Parameter(Mandatory=$true)][string]$BoardInventoryReceipt,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$BoardInventoryReceiptSha,
    [ValidateRange(50.0,250.0)][double]$CandidateMHz=200.0,
    [ValidatePattern('^[0-9]+([.][0-9]+)?,[0-9]+([.][0-9]+)?,[0-9]+([.][0-9]+)?,[0-9]+([.][0-9]+)?,[0-9]+([.][0-9]+)?,[0-9]+([.][0-9]+)?$')]
    [string]$ClockContract='99999001,100000000,12,1,6,3',
    [ValidateSet('release','release-guard-only','release-no-ila','full-master-ila')][string]$DebugProfile='release-no-ila',
    [ValidateSet(1024,2048,4096,8192,16384,32768,65536,131072)][int]$NativeIlaDepth=1024,
    [int[]]$AllowedVivadoPid=@(),
    [switch]$ValidateOnly,
    [switch]$SynthesisOnly
)

$ErrorActionPreference='Stop'
$requiredId='0x465A5641'
$requiredAbi='0x000A0004'
$requiredCaps='0x000007FF'
$requiredChainManifestSha='e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9'
$synthesisThreads=16
$synthDesignThreads=8
$implementationThreads=16
$jobs=8
# The user explicitly selected full-speed execution for this build.  Vivado
# 2026.1 accepts general.maxThreads=16 and caps synth.maxThreads at 8.  Memory is
# recorded at phase boundaries but is not used to block or terminate this run.
$activeToolNames=@('vivado','vitis_hls','vitis-run','v++','xcd')

function Get-Sha256([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-TextSha256([string]$Text) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try {([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))-replace'-','').ToLowerInvariant()}
    finally {$sha.Dispose()}
}

function Get-PlatformStageState([string[]]$Roots) {
    $stageFiles=@()
    $runmeFiles=@()
    foreach($root in $Roots) {
        if(!(Test-Path -LiteralPath $root -PathType Container)){continue}
        $stageFiles+=@(Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object{$_.Extension.ToLowerInvariant() -in @('.dcp','.rpt')})
        $runmeFiles+=@(Get-ChildItem -LiteralPath $root -Recurse -File -Filter runme.log -ErrorAction SilentlyContinue |
            Where-Object{$_.FullName -match '[\\/][^\\/]*(synth_1|impl_1)[\\/]runme[.]log$'})
    }
    $phaseMarkers=@()
    $highRiskSynthesisActive=$false
    foreach($runme in ($runmeFiles|Sort-Object FullName -Unique)) {
        $tail=@(Get-Content -LiteralPath $runme.FullName -Tail 2048 -ErrorAction SilentlyContinue)
        $marker=$tail |
            Where-Object{$_ -match '^(Start|Starting|Finished|Phase |Command:|synth_design completed|opt_design completed|place_design completed|route_design completed)'} |
            Select-Object -Last 1
        if($null-ne$marker){$phaseMarkers+="$($runme.FullName)|$marker"}
        if($runme.FullName -match '[\\/][^\\/]*synth_1[\\/]runme[.]log$') {
            $started=($tail -match '(?i)(^Start |^Starting|Command:.*synth|synth_design)')
            $finished=($tail -match '(?i)(synth_design completed successfully|Finished.*synth_design|Exiting Vivado)')
            # A dependency synth process can allocate heavily before Vivado
            # prints its first `Start ...` marker.  Treat any nonempty,
            # nonterminal synth runme.log as active so that gap is sampled too.
            if(($started-or$tail.Count)-and!$finished){$highRiskSynthesisActive=$true}
        }
    }
    # A report/checkpoint creation is a stage boundary.  Do not sample on every
    # append while a report is being written.
    $stageNames=@($stageFiles|Select-Object -ExpandProperty FullName|Sort-Object -Unique)
    [pscustomobject]@{
        signature=(($stageNames -join ';')+'||'+($phaseMarkers -join ';'))
        dcp_report_count=$stageNames.Count
        phase_markers=$phaseMarkers
        high_risk_synthesis_active=$highRiskSynthesisActive
    }
}

function Invoke-OwnedVivado(
    [string]$Vivado,
    [string[]]$Arguments,
    [string]$Stdout,
    [string]$Stderr,
    [string]$MemoryLog,
    [string[]]$StageRoots,
    [hashtable]$Environment
) {
    # Start-Process joins a string[] before launching a .bat file.  Quote every
    # element explicitly so Vivado receives the comma-bearing clock contract
    # as one Tcl argument and preserves the exact -tclargs cardinality.
    $argumentLine=($Arguments|ForEach-Object{'"'+($_ -replace '"','""')+'"'})-join' '
    $commandFile=Join-Path (Split-Path -Parent $Stdout) 'invoke-vivado.cmd'
    $commandLines=@(
        '@echo off',
        ('call "'+$Vivado+'" '+$argumentLine+' 1>"'+$Stdout+'" 2>"'+$Stderr+'"'),
        'exit /b %errorlevel%'
    )
    [IO.File]::WriteAllLines($commandFile,$commandLines,(New-Object Text.ASCIIEncoding))
    $launchTime=[DateTime]::Now.AddSeconds(-2)
    $process=Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c ""'+$commandFile+'""') `
        -WindowStyle Hidden -Environment $Environment -PassThru
    try{$process.PriorityClass=[Diagnostics.ProcessPriorityClass]::Normal}catch{}
    try{$process.ProcessorAffinity=[IntPtr]0xffff}catch{}
    $priorityAtLaunch=try{$process.PriorityClass.ToString()}catch{$null}
    $affinityAtLaunch=try{[long]$process.ProcessorAffinity}catch{$null}
    $samples=New-Object Collections.Generic.List[object]
    $terminated=$false
    $lastStageSignature=(Get-PlatformStageState -Roots $StageRoots).signature
    $vivadoPids=New-Object 'Collections.Generic.HashSet[int]'
    $vivadoPeakWorkingSet=0L
    $vivadoPriority=$null
    $vivadoAffinity=$null
    while($true) {
        if(!$process.HasExited){[void]$process.WaitForExit(5000)}else{Start-Sleep -Seconds 5}
        $vivadoChildren=@(Get-Process vivado -ErrorAction SilentlyContinue|Where-Object{
            try{$_.StartTime-ge$launchTime}catch{$false}
        })
        foreach($child in $vivadoChildren) {
            [void]$vivadoPids.Add($child.Id)
            try{$child.PriorityClass=[Diagnostics.ProcessPriorityClass]::Normal}catch{}
            try{$child.ProcessorAffinity=[IntPtr]0xffff}catch{}
            try{if($child.WorkingSet64-gt$vivadoPeakWorkingSet){$vivadoPeakWorkingSet=$child.WorkingSet64}}catch{}
            try{$vivadoPriority=$child.PriorityClass.ToString()}catch{}
            try{$vivadoAffinity=[long]$child.ProcessorAffinity}catch{}
        }
        if($process.HasExited-and!$vivadoChildren.Count){break}
        $stage=Get-PlatformStageState -Roots $StageRoots
        $stageBoundary=($stage.signature-ne$lastStageSignature)
        if(!$stageBoundary-and!$stage.high_risk_synthesis_active){continue}
        $memory=Get-FzTaskMemorySnapshot
        $samples.Add($memory)
        ([pscustomobject]@{
            memory=$memory
            stage_boundary=$stageBoundary
            dcp_report_count=$stage.dcp_report_count
            phase_markers=$stage.phase_markers
            high_risk_synthesis_active=$stage.high_risk_synthesis_active
        }|ConvertTo-Json -Depth 5 -Compress)|Add-Content -LiteralPath $MemoryLog -Encoding utf8
        $lastStageSignature=$stage.signature
    }
    if(!$process.HasExited){$process.WaitForExit()}
    $memorySampleArray=[object[]]$samples
    $vivadoPidArray=[int[]]$vivadoPids
    [pscustomobject]@{
        pid=$process.Id
        exit_code=$process.ExitCode
        peak_working_set_bytes=$process.PeakWorkingSet64
        terminated_for_memory_pressure=$terminated
        memory_samples=$memorySampleArray
        priority_class=$priorityAtLaunch
        processor_affinity=$affinityAtLaunch
        vivado_process_ids=$vivadoPidArray
        vivado_peak_working_set_bytes=$vivadoPeakWorkingSet
        vivado_priority_class=$vivadoPriority
        vivado_processor_affinity=$vivadoAffinity
    }
}

$sourceDir=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$launcherPath=$MyInvocation.MyCommand.Path
$buildScript=Join-Path $PSScriptRoot 'build_cnn_pipeline_v10_half2x.tcl'
$memoryHelper=Join-Path $sourceDir 'task_tool_memory.ps1'
$errorModeHelper=Join-Path $sourceDir 'task_tool_error_mode.ps1'
$tracePack=Join-Path $sourceDir 'fzv10_trace_pack.sv'
$vivado='D:\Vivado\2026.1\Vivado\bin\vivado.bat'
$manifest=Join-Path $env:APPDATA 'Xilinx\Vivado\tclapp\manifest.tcl'
$globalManifest=$manifest
$manifestBackup="$manifest.cnn-v10-platform-build-backup"
$expectedManifestSha='b5f010dae71150c1d13d04420150bde07e624fb0b0a1ced3949fcd464d8411b6'
$project=[IO.Path]::GetFullPath($ProjectDir)
$evidence=[IO.Path]::GetFullPath($EvidenceDir)
$hlsIp=[IO.Path]::GetFullPath($HlsIpDir)
$chainManifest=[IO.Path]::GetFullPath($ChainParameterManifest)
$boardInventory=[IO.Path]::GetFullPath($BoardInventoryReceipt)
$component=Join-Path $hlsIp 'component.xml'
$hlsPatchReceipt=Join-Path $hlsIp 'ap-ready-export-patch-receipt.json'
$componentExpected=$ComponentSha.ToLowerInvariant()
$chainManifestExpected=$ChainParameterManifestSha.ToLowerInvariant()
$boardInventoryExpected=$BoardInventoryReceiptSha.ToLowerInvariant()
$candidateText=$CandidateMHz.ToString('0.######',[Globalization.CultureInfo]::InvariantCulture)
$runScope=if($ValidateOnly){'validate-only'}elseif($SynthesisOnly){'synth-only'}else{'full'}
$debugProfileContract=switch($DebugProfile) {
    'release-no-ila' {[ordered]@{guard_ila_count=0;pipeline_ila_count=0;trace_pack_present=$false;mmio_trace_count=0;platform_trace_mmio_register_count=0;hls_ap_none_trace_port_count=12;trace_outputs_connected=$false;trace_output_transport='ap_none';debug_hub_count=0;ltx_required=$false}}
    'release-guard-only' {[ordered]@{guard_ila_count=1;pipeline_ila_count=0;trace_pack_present=$false;mmio_trace_count=0;platform_trace_mmio_register_count=0;hls_ap_none_trace_port_count=12;trace_outputs_connected=$false;trace_output_transport='ap_none';debug_hub_count=$null;ltx_required=$true}}
    default {[ordered]@{guard_ila_count=1;pipeline_ila_count=1;trace_pack_present=$true;mmio_trace_count=0;platform_trace_mmio_register_count=0;hls_ap_none_trace_port_count=12;trace_outputs_connected=$true;trace_output_transport='ap_none';debug_hub_count=$null;ltx_required=$true}}
}

foreach($path in @($launcherPath,$buildScript,$memoryHelper,$errorModeHelper,$tracePack,$vivado,$manifest,$component,$hlsPatchReceipt,$chainManifest,$boardInventory)) {
    if(!(Test-Path -LiteralPath $path -PathType Leaf)){throw "Missing required file: $path"}
}
if((Test-Path -LiteralPath $project) -or (Test-Path -LiteralPath $evidence)) {
    throw 'ProjectDir and EvidenceDir must both be new'
}
if($project-match'\s'-or$evidence-match'\s'-or$hlsIp-match'\s') {
    throw 'ProjectDir, EvidenceDir, and HlsIpDir must not contain whitespace'
}
$clockFields=@($ClockContract.Split(','))
if($clockFields.Count-ne6){throw 'ClockContract must contain BD_HZ,LIVE_HZ,M,D,O_slow,O_fast'}
foreach($field in $clockFields) {
    $parsed=0.0
    if(![double]::TryParse($field,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$parsed)-or$parsed-le0) {
        throw 'ClockContract fields must be positive invariant-culture numbers'
    }
}
$componentActual=Get-Sha256 $component
if($componentActual-ne$componentExpected){throw 'HLS component.xml SHA256 mismatch'}
$hlsPatch=Get-Content -LiteralPath $hlsPatchReceipt -Raw | ConvertFrom-Json
if(!$hlsPatch.pass-or$hlsPatch.actual_replacements-ne12-or@($hlsPatch.remaining_callers).Count-ne0-or@($hlsPatch.invalid_ready_signal_references).Count-ne0) {
    throw 'Exported HLS IP ap_ready compatibility patch receipt is not an exact 12-port PASS'
}
$chainManifestActual=Get-Sha256 $chainManifest
if($chainManifestExpected-ne$requiredChainManifestSha){throw 'Unexpected A0004 chain parameter manifest identity'}
if($chainManifestActual-ne$chainManifestExpected){throw 'Combined chain parameter manifest SHA256 mismatch'}
$boardInventoryActual=Get-Sha256 $boardInventory
if($boardInventoryActual-ne$boardInventoryExpected){throw 'Fresh board inventory receipt SHA256 mismatch'}
$sourceHashesAtLaunch=[ordered]@{
    launcher=Get-Sha256 $launcherPath
    build_tcl=Get-Sha256 $buildScript
    memory_helper=Get-Sha256 $memoryHelper
    error_mode_helper=Get-Sha256 $errorModeHelper
    trace_pack=Get-Sha256 $tracePack
    hls_component=$componentActual
    hls_ap_ready_patch_receipt=Get-Sha256 $hlsPatchReceipt
    chain_parameter_manifest=$chainManifestActual
    board_inventory_receipt=$boardInventoryActual
}
$otherBackups=@(Get-ChildItem -LiteralPath (Split-Path -Parent $manifest) -File |
    Where-Object{$_.Name-like'manifest.tcl*backup*'})
if($otherBackups.Count){throw 'Another manifest quarantine owner or stale backup exists'}
$allowedVivado=@{}
foreach($pidValue in $AllowedVivadoPid) {
    $allowed=Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if($null-eq$allowed-or$allowed.ProcessName-ne'vivado'){throw "AllowedVivadoPid $pidValue is not a live Vivado process"}
    $allowedVivado[[int]$pidValue]=$true
}
$activeBefore=@(Get-Process -ErrorAction SilentlyContinue|Where-Object{$activeToolNames-contains$_.ProcessName})
$unexpectedBefore=@($activeBefore|Where-Object{!($_.ProcessName-eq'vivado'-and$allowedVivado.ContainsKey([int]$_.Id))})
if($unexpectedBefore.Count){throw 'An unapproved official AMD heavy-tool owner is active'}
$manifestBefore=Get-Sha256 $manifest
if($manifestBefore-ne$expectedManifestSha){throw 'Unexpected Vivado Tcl app manifest SHA256'}

. $memoryHelper
. $errorModeHelper
$launchMemory=Get-FzTaskMemorySnapshot
$previousErrorMode=Enable-FzTaskToolErrorMode
$startedUtc=[DateTime]::UtcNow.ToString('o')
$tempRoot=Join-Path ([IO.Path]::GetTempPath()) ('cnn-v10-platform-'+[Guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $tempRoot)
$tempStdout=Join-Path $tempRoot 'vivado.stdout.log'
$tempStderr=Join-Path $tempRoot 'vivado.stderr.log'
$tempMemory=Join-Path $tempRoot 'memory-pressure.jsonl'
$tempGeneratedManifest=Join-Path $tempRoot 'manifest-generated-during-build.tcl'
$privateProfile=$evidence+'-private-user'
if(Test-Path -LiteralPath $privateProfile){throw 'Private Vivado profile path must be new'}
$privateAppData=Join-Path $privateProfile 'AppData\Roaming'
$privateLocalAppData=Join-Path $privateProfile 'AppData\Local'
[void](New-Item -ItemType Directory -Path (Join-Path $privateAppData 'Xilinx\Vivado\tclapp') -Force)
[void](New-Item -ItemType Directory -Path $privateLocalAppData -Force)
# Keep this profile truly fresh. Vivado initializes its own XilinxTclStore;
# pre-seeding only part of that store prevents appinit package discovery.
$manifest=Join-Path $privateAppData 'Xilinx\Vivado\tclapp\manifest.tcl'
[IO.File]::WriteAllText($manifest,"::tclapp::load_app -namespace {aldec::activehdl} aldec::activehdl`r`n",(New-Object Text.UTF8Encoding($false)))
if((Get-Sha256 $manifest) -ne 'b5f010dae71150c1d13d04420150bde07e624fb0b0a1ced3949fcd464d8411b6'){throw 'Private Vivado Tcl-app manifest bytes changed'}
$owned=$null
$caught=$null
$manifestRestored=$false
$manifestAfter=$null
$quarantineGeneratedManifestCaptured=$false
$childEnvironment=@{
    APPDATA=$privateAppData
    LOCALAPPDATA=$privateLocalAppData
    USERPROFILE=$privateProfile
    HOME=$privateProfile
}
if($ValidateOnly){$childEnvironment.FZV10_VALIDATE_ONLY='1'}

try {
    $arguments=@(
        '-mode','batch','-nojournal','-nolog','-notrace','-source',$buildScript,'-tclargs',
        $project,$evidence,$hlsIp,$componentExpected,$chainManifest,$chainManifestExpected,$boardInventory,$boardInventoryExpected,$requiredId,$requiredAbi,$requiredCaps,
        $candidateText,$ClockContract,$DebugProfile,[string]$NativeIlaDepth,$(if($ValidateOnly){'synth-only'}else{$runScope})
    )
    $owned=Invoke-OwnedVivado -Vivado $vivado -Arguments $arguments -Stdout $tempStdout -Stderr $tempStderr `
        -MemoryLog $tempMemory -StageRoots @($project,$evidence) -Environment $childEnvironment
} catch {
    $caught=$_.Exception.Message
} finally {
    try {
        if(Test-Path -LiteralPath $manifest -PathType Leaf) {
            Copy-Item -LiteralPath $manifest -Destination $tempGeneratedManifest
            $quarantineGeneratedManifestCaptured=$true
        }
    } catch {
        if($null-eq$caught){$caught="Failed to preserve generated quarantine manifest: $($_.Exception.Message)"}
    }
    try {
        if(Test-Path -LiteralPath $globalManifest -PathType Leaf) {
            $manifestAfter=Get-Sha256 $globalManifest
            $manifestRestored=($manifestAfter-eq$manifestBefore)
        }
    } catch {$manifestRestored=$false}
    Restore-FzTaskToolErrorMode -PreviousMode $previousErrorMode
}

if(!(Test-Path -LiteralPath $evidence -PathType Container)) {
    [void](New-Item -ItemType Directory -Path $evidence)
}
foreach($item in @(
    @($tempStdout,'vivado.stdout.log'),
    @($tempStderr,'vivado.stderr.log'),
    @($tempMemory,'memory-pressure.jsonl'),
    @($tempGeneratedManifest,'manifest-generated-during-build.tcl')
)) {
    if(Test-Path -LiteralPath $item[0] -PathType Leaf) {
        Move-Item -LiteralPath $item[0] -Destination (Join-Path $evidence $item[1])
    }
}
Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue

$stdoutPath=Join-Path $evidence 'vivado.stdout.log'
$buildCompleteToken=if($ValidateOnly){$null}elseif($SynthesisOnly){'CNN_PIPELINE_V10_SYNTH_ONLY_COMPLETE_OFFLINE_CANDIDATE'}else{'CNN_PIPELINE_V10_BUILD_COMPLETE_OFFLINE_CANDIDATE'}
$buildCompleteFound=$false
if($ValidateOnly) {
    $buildCompleteFound=Test-Path -LiteralPath (Join-Path $evidence 'validate-only-run-status.rpt') -PathType Leaf
} elseif(Test-Path -LiteralPath $stdoutPath -PathType Leaf) {
    $buildCompleteFound=[bool](Select-String -LiteralPath $stdoutPath -SimpleMatch $buildCompleteToken -Quiet)
}
$requiredOutputs=@('clock-domain-candidate.rpt','address-map.rpt','interface-widths.rpt','v10-abi-wiring.rpt','exact-bd.tcl')
if($ValidateOnly) {
    # The validate-only gate proves BD generation and clock/reset/metadata
    # contracts without launching synthesis or implementation.
    $requiredOutputs+='validate-only-run-status.rpt'
} elseif($SynthesisOnly) {
    $requiredOutputs+=@('post-synth-utilization.rpt','post-synth-timing.rpt')
    $requiredOutputs+=@('synth-only-run-status.rpt','cnn-pipeline-v10-candidate-post-synth.dcp')
} else {
    $requiredOutputs+=@('post-synth-utilization.rpt','post-synth-timing.rpt')
    $requiredOutputs+=@(
        'implemented-clock-candidates.rpt','clocks.rpt','clock-interaction.rpt','post-route-timing.rpt','pulse-width.rpt','timing-exceptions.rpt','check-timing.rpt',
        'route-status.rpt','post-route-utilization-hierarchical.rpt','post-route-drc.rpt','methodology.rpt',
        'cdc.rpt','bus-skew.rpt','implemented-debug-profile.rpt','cnn-pipeline-v10-candidate-post-route.dcp',
        'cnn-pipeline-v10-candidate.bit','cnn-pipeline-v10-candidate.bin'
    )
    if($debugProfileContract.ltx_required){$requiredOutputs+='cnn-pipeline-v10-candidate.ltx'}
}
$missingOutputs=@($requiredOutputs|Where-Object{!(Test-Path -LiteralPath (Join-Path $evidence $_) -PathType Leaf)})
$implementedDebugProfilePath=Join-Path $evidence 'implemented-debug-profile.rpt'
$implementedDebugProfileFields=[ordered]@{}
$implementedDebugProfileCheckPassed=$true
$implementedDebugProfileCheckReason=if($ValidateOnly){'not applicable to validate-only run'}elseif($SynthesisOnly){'not applicable to synth-only run'}else{'implemented debug profile report matches contract'}
if(!$SynthesisOnly -and !$ValidateOnly) {
    if(Test-Path -LiteralPath $implementedDebugProfilePath -PathType Leaf) {
        foreach($line in Get-Content -LiteralPath $implementedDebugProfilePath) {
            if($line-match'^([^=]+)=(.*)$'){$implementedDebugProfileFields[$Matches[1]]=$Matches[2]}
        }
    }
    if($DebugProfile-eq'release-no-ila') {
        $requiredDebugFields=@('debug_profile','guard_ila_count','pipeline_ila_count','trace_pack_present','debug_hub_count','mmio_trace_count','platform_trace_mmio_register_count','hls_ap_none_trace_port_count','trace_outputs_connected','trace_output_transport')
        $missingDebugFields=@($requiredDebugFields|Where-Object{!$implementedDebugProfileFields.Contains($_)})
        $implementedDebugProfileCheckPassed=(!$missingDebugFields.Count-and
            $implementedDebugProfileFields.debug_profile-eq'release-no-ila'-and
            $implementedDebugProfileFields.guard_ila_count-eq'0'-and
            $implementedDebugProfileFields.pipeline_ila_count-eq'0'-and
            $implementedDebugProfileFields.trace_pack_present-eq'0'-and
            $implementedDebugProfileFields.debug_hub_count-eq'0'-and
            $implementedDebugProfileFields.mmio_trace_count-eq'0'-and
            $implementedDebugProfileFields.platform_trace_mmio_register_count-eq'0'-and
            $implementedDebugProfileFields.hls_ap_none_trace_port_count-eq'12'-and
            $implementedDebugProfileFields.trace_outputs_connected-eq'false'-and
            $implementedDebugProfileFields.trace_output_transport-eq'ap_none')
        if(!$implementedDebugProfileCheckPassed) {
            $implementedDebugProfileCheckReason="release-no-ila implemented report mismatch; missing=$($missingDebugFields -join ',')"
        }
    }
}
$implementedGuardIlaCount=if($implementedDebugProfileFields.Contains('guard_ila_count')){[int]$implementedDebugProfileFields.guard_ila_count}else{$null}
$implementedPipelineIlaCount=if($implementedDebugProfileFields.Contains('pipeline_ila_count')){[int]$implementedDebugProfileFields.pipeline_ila_count}else{$null}
$implementedTracePackPresent=if($implementedDebugProfileFields.Contains('trace_pack_present')){$implementedDebugProfileFields.trace_pack_present-eq'1'}else{$null}
$implementedMmioTraceCount=if($implementedDebugProfileFields.Contains('mmio_trace_count')){[int]$implementedDebugProfileFields.mmio_trace_count}else{$null}
$implementedPlatformTraceMmioRegisterCount=if($implementedDebugProfileFields.Contains('platform_trace_mmio_register_count')){[int]$implementedDebugProfileFields.platform_trace_mmio_register_count}else{$null}
$implementedHlsApNoneTracePortCount=if($implementedDebugProfileFields.Contains('hls_ap_none_trace_port_count')){[int]$implementedDebugProfileFields.hls_ap_none_trace_port_count}else{$null}
$implementedTraceOutputsConnected=if($implementedDebugProfileFields.Contains('trace_outputs_connected')){$implementedDebugProfileFields.trace_outputs_connected-eq'true'}else{$null}
$implementedTraceOutputTransport=if($implementedDebugProfileFields.Contains('trace_output_transport')){[string]$implementedDebugProfileFields.trace_output_transport}else{$null}
$implementedDebugHubCount=if($implementedDebugProfileFields.Contains('debug_hub_count')){[int]$implementedDebugProfileFields.debug_hub_count}else{$null}
$threadEvidence=@()
$threadLogs=@($stdoutPath)
if(Test-Path -LiteralPath $project -PathType Container) {
    $threadLogs+=@(Get-ChildItem -LiteralPath $project -Recurse -File -Filter runme.log -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FullName)
}
foreach($threadLog in ($threadLogs|Where-Object{Test-Path -LiteralPath $_ -PathType Leaf}|Sort-Object -Unique)) {
    foreach($match in @(Select-String -LiteralPath $threadLog -Pattern 'maxThreads|multi-thread|Using up to|maximum of [0-9]+ processes|Running with [0-9]+ threads|with [0-9]+ threads' -CaseSensitive:$false -ErrorAction SilentlyContinue)) {
        $threadEvidence+=[pscustomobject]@{
            path=$threadLog
            line_number=$match.LineNumber
            line=$match.Line.Trim()
        }
    }
}
$activeAfter=@(Get-Process -ErrorAction SilentlyContinue|Where-Object{$activeToolNames-contains$_.ProcessName})
$remaining=@($activeAfter|Where-Object{!($_.ProcessName-eq'vivado'-and$allowedVivado.ContainsKey([int]$_.Id))}|
    Select-Object Id,ProcessName,StartTime)
$allowedRemaining=@($activeAfter|Where-Object{$_.ProcessName-eq'vivado'-and$allowedVivado.ContainsKey([int]$_.Id)}|
    Select-Object Id,ProcessName,StartTime)
$outputHashes=@()
foreach($file in @(Get-ChildItem -LiteralPath $evidence -Recurse -File -ErrorAction SilentlyContinue|
    Where-Object{$_.Name-ne'receipt.json'}|Sort-Object FullName)) {
    $outputHashes+=[pscustomobject]@{
        relative_path=$file.FullName.Substring($evidence.Length).TrimStart('\','/')
        bytes=$file.Length
        sha256=Get-Sha256 $file.FullName
    }
}
$peakMemoryLoad=[double]$launchMemory.memory_load_percent
if($null-ne$owned-and$owned.memory_samples.Count) {
    $peakMemoryLoad=[double](($owned.memory_samples|Measure-Object memory_load_percent -Maximum).Maximum)
    if($launchMemory.memory_load_percent-gt$peakMemoryLoad){$peakMemoryLoad=[double]$launchMemory.memory_load_percent}
}
$sourceHashes=[ordered]@{
    launcher=[ordered]@{path=$launcherPath;sha256_at_launch=$sourceHashesAtLaunch.launcher;sha256_after_run=Get-Sha256 $launcherPath}
    build_tcl=[ordered]@{path=$buildScript;sha256_at_launch=$sourceHashesAtLaunch.build_tcl;sha256_after_run=Get-Sha256 $buildScript}
    memory_helper=[ordered]@{path=$memoryHelper;sha256_at_launch=$sourceHashesAtLaunch.memory_helper;sha256_after_run=Get-Sha256 $memoryHelper}
    error_mode_helper=[ordered]@{path=$errorModeHelper;sha256_at_launch=$sourceHashesAtLaunch.error_mode_helper;sha256_after_run=Get-Sha256 $errorModeHelper}
    trace_pack=[ordered]@{path=$tracePack;sha256_at_launch=$sourceHashesAtLaunch.trace_pack;sha256_after_run=Get-Sha256 $tracePack}
    hls_component=[ordered]@{path=$component;expected_sha256=$componentExpected;sha256_at_launch=$sourceHashesAtLaunch.hls_component;sha256_after_run=Get-Sha256 $component}
    hls_ap_ready_patch_receipt=[ordered]@{path=$hlsPatchReceipt;sha256_at_launch=$sourceHashesAtLaunch.hls_ap_ready_patch_receipt;sha256_after_run=Get-Sha256 $hlsPatchReceipt}
    board_inventory_receipt=[ordered]@{path=$boardInventory;expected_sha256=$boardInventoryExpected;sha256_at_launch=$sourceHashesAtLaunch.board_inventory_receipt;sha256_after_run=Get-Sha256 $boardInventory}
}
$hlsPayloadInventory=@()
foreach($file in @(Get-ChildItem -LiteralPath $hlsIp -Recurse -File | Where-Object{$_.Extension.ToLowerInvariant() -in @('.xml','.v','.dat','.json')} | Sort-Object FullName)) {
    $hlsPayloadInventory+=[ordered]@{
        relative_path=$file.FullName.Substring($hlsIp.Length).TrimStart('\','/')
        bytes=$file.Length
        sha256=Get-Sha256 $file.FullName
    }
}
$hlsPayloadCanonical=($hlsPayloadInventory|ForEach-Object{"$($_.relative_path)|$($_.bytes)|$($_.sha256)"})-join"`n"
$pass=($null-ne$owned-and$owned.exit_code-eq0-and[string]::IsNullOrEmpty($caught)-and!$owned.terminated_for_memory_pressure-and
    $manifestRestored-and!$remaining.Count-and$buildCompleteFound-and!$missingOutputs.Count-and$implementedDebugProfileCheckPassed)
$receipt=[ordered]@{
    schema='cnn-pipeline-v10-platform-build-v1'
    started_utc=$startedUtc
    finished_utc=[DateTime]::UtcNow.ToString('o')
    scope='Offline FZ3B platform candidate build; no board action'
    target_part_candidate='xazu3eg-sfvc784-1-i'
    board_verified=$false
    project_dir=$project
    evidence_dir=$evidence
    hls_ip_dir=$hlsIp
    hls_ip_payload_file_count=$hlsPayloadInventory.Count
    hls_ip_payload_canonical_sha256=(Get-TextSha256 $hlsPayloadCanonical)
    hls_ip_payload_inventory=$hlsPayloadInventory
    chain_parameter_manifest=[ordered]@{path=$chainManifest;expected_sha256=$chainManifestExpected;sha256_at_launch=$sourceHashesAtLaunch.chain_parameter_manifest;sha256_after_run=Get-Sha256 $chainManifest}
    board_inventory_receipt=[ordered]@{path=$boardInventory;expected_sha256=$boardInventoryExpected;sha256_at_launch=$sourceHashesAtLaunch.board_inventory_receipt;sha256_after_run=Get-Sha256 $boardInventory}
    forced_identity=[ordered]@{id=$requiredId;abi=$requiredAbi;caps=$requiredCaps}
    candidate_mhz=[double]$CandidateMHz
    clock_contract=$ClockContract
    debug_profile=$DebugProfile
    native_ila_depth=$NativeIlaDepth
    debug_profile_contract=$debugProfileContract
    expected_guard_ila_count=$debugProfileContract.guard_ila_count
    expected_pipeline_ila_count=$debugProfileContract.pipeline_ila_count
    expected_trace_pack_present=$debugProfileContract.trace_pack_present
    expected_mmio_trace_count=$debugProfileContract.mmio_trace_count
    expected_platform_trace_mmio_register_count=$debugProfileContract.platform_trace_mmio_register_count
    expected_hls_ap_none_trace_port_count=$debugProfileContract.hls_ap_none_trace_port_count
    expected_trace_outputs_connected=$debugProfileContract.trace_outputs_connected
    expected_trace_output_transport=$debugProfileContract.trace_output_transport
    expected_debug_hub_count=$debugProfileContract.debug_hub_count
    ltx_required=$debugProfileContract.ltx_required
    ltx_present=(Test-Path -LiteralPath (Join-Path $evidence 'cnn-pipeline-v10-candidate.ltx') -PathType Leaf)
    guard_ila_count=$implementedGuardIlaCount
    pipeline_ila_count=$implementedPipelineIlaCount
    trace_pack_present=$implementedTracePackPresent
    mmio_trace_count=$implementedMmioTraceCount
    platform_trace_mmio_register_count=$implementedPlatformTraceMmioRegisterCount
    hls_ap_none_trace_port_count=$implementedHlsApNoneTracePortCount
    trace_outputs_connected=$implementedTraceOutputsConnected
    trace_output_transport=$implementedTraceOutputTransport
    debug_hub_count=$implementedDebugHubCount
    implemented_debug_profile_report=[ordered]@{path=$implementedDebugProfilePath;fields=$implementedDebugProfileFields;check_passed=$implementedDebugProfileCheckPassed;check_reason=$implementedDebugProfileCheckReason}
    run_scope=$runScope
    synthesis_threads=$synthesisThreads
    synth_design_threads=$synthDesignThreads
    implementation_threads=$implementationThreads
    synthesis_thread_parameter_requested=$synthesisThreads
    synthesis_thread_parameter_readback_expected=$synthesisThreads
    synth_design_thread_parameter_requested=$synthDesignThreads
    synth_design_thread_parameter_readback_expected=$synthDesignThreads
    implementation_thread_parameter_requested=$implementationThreads
    implementation_thread_parameter_readback_expected=$implementationThreads
    thread_parameter_requested=16
    thread_parameter_readback_expected=16
    thread_parameter_scope='maximum requested across synthesis and implementation phases'
    algorithm_thread_log_evidence=$threadEvidence
    jobs=$jobs
    requested_process_priority='Normal'
    actual_process_priority=if($null-ne$owned){$owned.priority_class}else{$null}
    requested_processor_affinity=65535
    actual_processor_affinity=if($null-ne$owned){$owned.processor_affinity}else{$null}
    vivado_process_ids=if($null-ne$owned){$owned.vivado_process_ids}else{@()}
    actual_vivado_priority=if($null-ne$owned){$owned.vivado_priority_class}else{$null}
    actual_vivado_processor_affinity=if($null-ne$owned){$owned.vivado_processor_affinity}else{$null}
    actual_vivado_peak_working_set_bytes=if($null-ne$owned){$owned.vivado_peak_working_set_bytes}else{$null}
    launch_minimum_physical_gib=$null
    launch_budget_basis='User explicitly requested full-speed general16/synth8/implementation16 and disabled memory admission and automatic pressure termination for this build; phase memory snapshots remain observational.'
    concurrency_limit_threshold_percent=$null
    intensive_monitoring_threshold_percent=$null
    emergency_stop_threshold_percent=$null
    launch_memory=$launchMemory
    peak_memory_load_percent=$peakMemoryLoad
    owned_peak_working_set_bytes=if($null-ne$owned){$owned.peak_working_set_bytes}else{$null}
    owned_pid=if($null-ne$owned){$owned.pid}else{$null}
    tool_exit_code=if($null-ne$owned){$owned.exit_code}else{$null}
    tool_exception=$caught
    terminated_for_memory_pressure=if($null-ne$owned){$owned.terminated_for_memory_pressure}else{$false}
    manifest_sha256_before=$manifestBefore
    manifest_sha256_after=$manifestAfter
    manifest_restored_exactly=$manifestRestored
    quarantine_generated_manifest_captured=$quarantineGeneratedManifestCaptured
    heavy_tool_processes_remaining=$remaining
    allowed_external_vivado_processes=$allowedRemaining
    build_complete_token=$buildCompleteToken
    build_complete_token_found=$buildCompleteFound
    required_outputs=$requiredOutputs
    missing_required_outputs=$missingOutputs
    source_hashes=$sourceHashes
    actual_outputs=$outputHashes
    pass=$pass
}
$receipt|ConvertTo-Json -Depth 9|Set-Content -LiteralPath (Join-Path $evidence 'receipt.json') -Encoding utf8

if(!$manifestRestored){exit 99}
if($null-ne$owned-and$owned.terminated_for_memory_pressure){exit 98}
if($null-eq$owned){exit 97}
if($owned.exit_code-ne0){exit $owned.exit_code}
if($null-ne$caught-or!$buildCompleteFound-or$missingOutputs.Count-or$remaining.Count-or!$implementedDebugProfileCheckPassed){exit 96}
exit 0
