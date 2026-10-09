[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$HlsRtlDir,
    [Parameter(Mandatory=$true)][string]$FixtureRoot,
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$WorkDir,
    [Parameter(Mandatory=$true)][string]$SourcePackDir,
    [string]$CandidateSourceManifest='',
    [ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSourceManifestSha256='f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593',
    [string]$CandidateContract='',
    [ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedCandidateContractSha256='a65bdd2c50a5f1b5329350e22a67d9fb9ff4731c3517454ae524f667c5dc3f4d',
    [Parameter(Mandatory=$true)][string]$CombinedParameterManifest,
    [ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedCombinedParameterManifestSha256='4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690',
    [Parameter(Mandatory=$true)][string]$FusedLeafRtl,
    [string]$HlsSynthesisReceipt='',
    [string]$HlsApReadyPatchReceipt='',
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedFusedLeafRtlSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGeneratedRtlDigest,
    [Parameter(Mandatory=$true)][string]$TransformReceipt,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedTransformReceiptSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedTransformOutputInventorySha256,
    [string]$FrozenStructureAuditReceipt='',
    [string]$FusedUnisimMiterReceipt='artifacts/board-debug-20261008/acceleration/simulation/cnn-v10-pw-half2x-fused-alu-unisim-002/receipt.json',
    [string]$VivadoRoot='D:\Vivado\2026.1\Vivado',
    [string]$Python='python',
    [int]$ElaborationThreads=2,
    [ValidateRange(1,8)][int]$MaxParallelCases=3,
    [double]$MinimumPhysicalGiB=12.0,
    [string]$ReuseXsimDir='',
    [int]$AllowedVivadoPid=0,
    [string[]]$CaseNames=@(),
    [int]$ExpectedCollectorCases=9
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..\..\..'))
$hls=[IO.Path]::GetFullPath($HlsRtlDir)
$fixture=[IO.Path]::GetFullPath($FixtureRoot)
$evidence=[IO.Path]::GetFullPath($EvidenceDir)
$work=[IO.Path]::GetFullPath($WorkDir)
$sourcePack=[IO.Path]::GetFullPath($SourcePackDir)
$sourceManifest=[IO.Path]::GetFullPath($(if([string]::IsNullOrWhiteSpace($CandidateSourceManifest)){Join-Path $sourcePack 'candidate-source-manifest.json'}else{$CandidateSourceManifest}))
$candidateContractPath=[IO.Path]::GetFullPath($(if([string]::IsNullOrWhiteSpace($CandidateContract)){Join-Path $sourcePack 'candidate-contract.json'}else{$CandidateContract}))
$combinedManifest=[IO.Path]::GetFullPath($CombinedParameterManifest)
$hlsReceipt=[IO.Path]::GetFullPath($(if([string]::IsNullOrWhiteSpace($HlsSynthesisReceipt)){Join-Path $repo 'artifacts\board-debug-20261008\acceleration\hls\cnn-v10.5-a0005-storage-hls-002\receipt.json'}else{$HlsSynthesisReceipt}))
$expectedHlsReceipt='4ac9288f1aac5bc2fc1026cde28b85d8ba80c8b82145788377b48b5f65ef8317'
$requiredGeneratedDigest='ef373560fbb68e8719d5497b0d259b8a6dab734b2f88744f9d3505f8143af711'
$requiredFusedLeaf='2b541de975975b5e05060287b2052ce1dc1375b83e601e79a59b79be4dc0efdf'
$requiredApReadyPatchReceipt='daad747738b8b30538842eb290faf6d6e0b0c30020a08d814a264668ee2409f6'
$requiredTransformReceipt='20e66aa3b462e7318a3b4b74565cfc417bbba5c699cdc7db242bec2330fd9457'
$requiredTransformInventory='14c93f4ae5653b4fc89bf769809697716bea5962cdd96315a43544e49eef3953'
$requiredStructureReceipt='da0e0d8dc5bcec87d9d8ff1664d9f984fea94ac37c18c5076a2e1255327a4802'
$apReadyPatchReceipt=[IO.Path]::GetFullPath($(if([string]::IsNullOrWhiteSpace($HlsApReadyPatchReceipt)){Join-Path $repo 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-hls-ip-apready-patched-002\receipt.json'}else{$HlsApReadyPatchReceipt}))
$frozenStructureReceipt=[IO.Path]::GetFullPath($(if([string]::IsNullOrWhiteSpace($FrozenStructureAuditReceipt)){Join-Path $repo 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-generated-rtl-structure-002\receipt.json'}else{$FrozenStructureAuditReceipt}))
$expectedSourceManifest=$ExpectedSourceManifestSha256.ToLowerInvariant()
$expectedCandidateContract=$ExpectedCandidateContractSha256.ToLowerInvariant()
$expectedCombinedManifest=$ExpectedCombinedParameterManifestSha256.ToLowerInvariant()
$fusedLeafSource=[IO.Path]::GetFullPath($FusedLeafRtl)
$expectedFusedLeaf=$ExpectedFusedLeafRtlSha256.ToLowerInvariant()
$fixtureManifest=Join-Path $fixture 'manifest.json'
$acceleration=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..'))
$halfExperiment=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\pw_half2x'))
$fusedExperiment=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\pw_half2x_fused_alu'))
$bindingGenerator=Join-Path $halfExperiment 'generate_cnn_v10_half2x_tb_binding.py'
$modelPatcher=Join-Path $fusedExperiment 'patch_fused_alu_vector_model.py'
$collector=Join-Path $PSScriptRoot 'collect_cnn_pipeline_v10_a0005_rtl_results.py'
$structureAuditor=Join-Path $PSScriptRoot 'audit_cnn_pipeline_v10_a0005_generated_rtl.py'
$memoryHelper=Join-Path $acceleration 'task_tool_memory.ps1'
$transformReceiptPath=[IO.Path]::GetFullPath($TransformReceipt)
$miterReceiptPath=[IO.Path]::GetFullPath($FusedUnisimMiterReceipt)
$expectedMiterReceiptSha='d98b0ed12c8de5c6a39dbf2c50ff47df63f5fe61f315d5f5934df12d8b3091f1'
$xvlog=Join-Path $VivadoRoot 'bin\xvlog.bat'
$xelab=Join-Path $VivadoRoot 'bin\xelab.bat'
$xsim=Join-Path $VivadoRoot 'bin\xsim.bat'
$glblSource=Join-Path $VivadoRoot 'data\verilog\src\glbl.v'

function Get-Sha256([string]$Path){
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Require-File([string]$Path){if(!(Test-Path -LiteralPath $Path -PathType Leaf)){throw "Missing file: $Path"}}
function Require-Dir([string]$Path){if(!(Test-Path -LiteralPath $Path -PathType Container)){throw "Missing directory: $Path"}}
function Write-Utf8NoBom([string]$Path,[string]$Text){
    [IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))
}
function Get-CanonicalInventoryDigest([string]$Root){
    $records=@(Get-ChildItem -LiteralPath $Root -File -Recurse|Where-Object{
        $_.Extension.ToLowerInvariant() -in @('.v','.sv','.vh','.dat','.mem','.hex')
    }|ForEach-Object{
        $relative=$_.FullName.Substring($Root.Length).TrimStart('\','/').Replace('\','/')
        [ordered]@{path=$relative;sha256=Get-Sha256 $_.FullName}
    })
    if(!$records.Count){throw "Empty RTL inventory: $Root"}
    # Python json sort_keys/inventory ordering is Unicode-codepoint/ordinal.
    # PowerShell Sort-Object is culture-aware even with -CaseSensitive, so use
    # StringComparer.Ordinal to stay byte-for-byte compatible with collector.
    $comparison=[System.Comparison[object]]{
        param($left,$right)
        [StringComparer]::Ordinal.Compare([string]$left.path,[string]$right.path)
    }
    $comparer=[System.Collections.Generic.Comparer[object]]::Create($comparison)
    # Casting inline creates a temporary array and leaves $records in its
    # filesystem enumeration order.  Sort the array that is subsequently
    # serialized so this matches Python's canonical path ordering.
    $recordArray=[object[]]$records
    [Array]::Sort($recordArray,$comparer)
    $records=$recordArray
    $json=$records|ConvertTo-Json -Compress -Depth 4
    $bytes=[Text.Encoding]::UTF8.GetBytes($json)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}
    finally{$sha.Dispose()}
}
function Invoke-HiddenTool([string]$Name,[string]$Executable,[string[]]$Arguments,[string]$Log){
    $quoted=@($Arguments|ForEach-Object{if($_ -match '[\s"]'){'"'+($_ -replace '"','\"')+'"'}else{$_}})
    $cmd=Join-Path $work "$Name.cmd"
    # Every AMD launcher used here is a .bat file.  CALL is required when a
    # batch file invokes another batch file; otherwise control never reaches
    # the explicit exit-code propagation below and a failed tool can look
    # successful to Start-Process.
    Write-Utf8NoBom $cmd ("@echo off`r`ncall `"$Executable`" "+($quoted -join ' ')+" > `"$Log`" 2>&1`r`nset TOOL_EXIT=%ERRORLEVEL%`r`nexit /b %TOOL_EXIT%`r`n")
    $process=Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c ""'+$cmd+'""') `
        -WorkingDirectory $work -WindowStyle Hidden -PassThru
    try{$process.PriorityClass=[Diagnostics.ProcessPriorityClass]::AboveNormal}catch{}
    $process.WaitForExit()
    $process.Refresh()
    $exitCode=$process.ExitCode
    $logText=if(Test-Path -LiteralPath $Log){Get-Content -LiteralPath $Log -Raw}else{''}
    $toolError=($logText-match'(?m)^ERROR:')
    if($exitCode-eq0 -and $toolError){$exitCode=1}
    [ordered]@{name=$Name;exit_code=$exitCode;log=$Log;log_sha256=$(if(Test-Path -LiteralPath $Log){Get-Sha256 $Log}else{$null});error_marker_found=$toolError}
}
function Start-HiddenCase([object]$Case,[string]$Executable,[string[]]$Arguments,
                          [string]$CaseWork,[string]$LauncherLog,[string]$XsimLog,
                          [double]$MemoryUsedPercent){
    # xsim.bat performs another command-line parse.  Quote every argument and
    # use forward slashes so drive-qualified plusarg values such as
    # FIXTURE_ROOT=E:/... remain one token through both parsers.
    $quoted=@($Arguments|ForEach-Object{
        $normalized=([string]$_).Replace('\','/')
        '"'+($normalized -replace '"','\"')+'"'
    })
    $cmd=Join-Path $CaseWork 'xsim-launch.cmd'
    Write-Utf8NoBom $cmd ("@echo off`r`ncall `"$Executable`" "+($quoted -join ' ')+" > `"$LauncherLog`" 2>&1`r`nset TOOL_EXIT=%ERRORLEVEL%`r`nexit /b %TOOL_EXIT%`r`n")
    $process=Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c ""'+$cmd+'""') `
        -WorkingDirectory $CaseWork -WindowStyle Hidden -PassThru
    try{$process.PriorityClass=[Diagnostics.ProcessPriorityClass]::AboveNormal}catch{}
    [pscustomobject]@{
        case=$Case;process=$process;work_dir=$CaseWork;launcher_log=$LauncherLog
        xsim_log=$XsimLog;started_utc=(Get-Date).ToUniversalTime().ToString('o')
        memory_used_percent_at_launch=$MemoryUsedPercent
    }
}
function Assert-NoHeavyOwner {
    # Independent XSIM jobs own private snapshots and may coexist with the
    # preserved historical UNISIM run.  Compile/elaborate and Vivado/HLS remain
    # single-owner.
    $names=@('vivado','vitis_hls','v++','xelab','xvlog')
    $active=@(Get-Process -ErrorAction SilentlyContinue|Where-Object{$names -contains $_.ProcessName.ToLowerInvariant()})
    if($AllowedVivadoPid-gt0){
        $active=@($active|Where-Object{!($_.ProcessName-eq'vivado'-and$_.Id-eq$AllowedVivadoPid)})
    }
    if($active.Count){throw "Another AMD heavy-tool owner is active: $($active.ProcessName -join ',')"}
}

if($ElaborationThreads -lt 1 -or $ElaborationThreads -gt 2){throw 'ElaborationThreads must be 1 or 2'}
foreach($path in @($hls,$fixture,$sourcePack)){Require-Dir $path}
foreach($path in @($sourceManifest,$candidateContractPath,$combinedManifest,$hlsReceipt,$apReadyPatchReceipt,$frozenStructureReceipt,$fixtureManifest,$bindingGenerator,$modelPatcher,$collector,$structureAuditor,$memoryHelper,$fusedLeafSource,$transformReceiptPath,$miterReceiptPath,$xvlog,$xelab,$xsim,$glblSource)){Require-File $path}
. $memoryHelper
if(Test-Path -LiteralPath $evidence){throw "EvidenceDir already exists: $evidence"}
if(Test-Path -LiteralPath $work){throw "WorkDir already exists: $work"}
if((Get-Sha256 $sourceManifest)-ne$expectedSourceManifest){throw 'A0005 source manifest SHA mismatch'}
if((Get-Sha256 $candidateContractPath)-ne$expectedCandidateContract){throw 'A0005 candidate contract SHA mismatch'}
if((Get-Sha256 $combinedManifest)-ne$expectedCombinedManifest){throw 'A0005 combined parameter manifest SHA mismatch'}
if((Get-Sha256 $hlsReceipt)-ne$expectedHlsReceipt){throw 'A0005 HLS002 receipt SHA mismatch'}
if((Get-Sha256 $apReadyPatchReceipt)-ne$requiredApReadyPatchReceipt){throw 'A0005 ap_ready patched002 receipt SHA mismatch'}
$apReadyPatchJson=Get-Content -LiteralPath $apReadyPatchReceipt -Raw|ConvertFrom-Json
if(!$apReadyPatchJson.pass-or$apReadyPatchJson.schema-ne'cnn-v10.3-hls-ap-ctrl-none-ready-patch-v1'-or[int]$apReadyPatchJson.actual_replacements-ne12-or@($apReadyPatchJson.remaining_callers).Count-ne0-or@($apReadyPatchJson.invalid_ready_signal_references).Count-ne0){throw 'A0005 ap_ready patched002 receipt contract mismatch'}
if($ExpectedGeneratedRtlDigest.ToLowerInvariant()-ne$requiredGeneratedDigest-or$expectedFusedLeaf-ne$requiredFusedLeaf-or$ExpectedTransformReceiptSha256.ToLowerInvariant()-ne$requiredTransformReceipt-or$ExpectedTransformOutputInventorySha256.ToLowerInvariant()-ne$requiredTransformInventory){throw 'A0005 transformed RTL identity parameters are not the frozen HLS002 fused result'}
if((Get-Sha256 $frozenStructureReceipt)-ne$requiredStructureReceipt){throw 'A0005 frozen generated-RTL structure receipt SHA mismatch'}
$frozenStructureJson=Get-Content -LiteralPath $frozenStructureReceipt -Raw|ConvertFrom-Json
if(!$frozenStructureJson.pass-or$frozenStructureJson.bindings.rtl_rom_digest-ne$requiredGeneratedDigest-or$frozenStructureJson.bindings.fused_leaf_sha256-ne$requiredFusedLeaf-or[int]$frozenStructureJson.structure.fused_leaf_instances-ne16-or@($frozenStructureJson.structure.pw1_tdp_banks|Where-Object{[int]$_.bank_count-ne8}).Count-or@($frozenStructureJson.structure.dw7_fixed_banks|Where-Object{[int]$_.bank_count-ne16}).Count-or@($frozenStructureJson.structure.pw2_fifo_w160_d1024_files).Count-ne2){throw 'A0005 frozen generated-RTL structure receipt contract mismatch'}
$hlsReceiptJson=Get-Content -LiteralPath $hlsReceipt -Raw|ConvertFrom-Json
if($hlsReceiptJson.schema-ne'cnn-pipeline-v10-hls-synth-receipt-v1'-or[int]$hlsReceiptJson.tool_exit_code-ne0-or[double]$hlsReceiptJson.clock_ns-ne5.0-or[double]$hlsReceiptJson.clock_uncertainty_percent-ne27.0-or$hlsReceiptJson.source_sha256.'candidate-source-manifest.json'-ne$expectedSourceManifest-or@($hlsReceiptJson.product_gate.psobject.Properties|Where-Object{!([bool]$_.Value)}).Count){throw 'A0005 HLS002 receipt contract mismatch'}
$contractJson=Get-Content -LiteralPath $candidateContractPath -Raw|ConvertFrom-Json
if($contractJson.identity.core_abi-ne'0x000A0005'-or$contractJson.identity.software-ne'sw10.5'-or$contractJson.identity.guard_caps-ne'0x00000fff'-or$contractJson.identity.combined_parameter_manifest_sha256-ne$expectedCombinedManifest){throw 'A0005 identity/capability/combined-manifest contract mismatch'}
$sourceJson=Get-Content -LiteralPath $sourceManifest -Raw|ConvertFrom-Json
if($sourceJson.schema-ne'dual-lane-storage-dw7-opt-source-manifest-v1'-or@($sourceJson.files).Count-ne8){throw 'A0005 source manifest schema or member count mismatch'}
$sourcePackManifest=Join-Path $sourcePack 'source-pack-manifest.json'
Require-File $sourcePackManifest
if((Get-Sha256 $sourcePackManifest)-ne'3ef628201ffe36d17c86607b002c25bea6bb968813afdf1fb702dedd023b9dfa'){throw 'A0005 source-pack manifest SHA mismatch'}
$sourcePackJson=Get-Content -LiteralPath $sourcePackManifest -Raw|ConvertFrom-Json
foreach($property in $sourcePackJson.files.psobject.Properties){$path=Join-Path $sourcePack $property.Name;Require-File $path;if((Get-Sha256 $path)-ne([string]$property.Value).ToLowerInvariant()){throw "A0005 source-pack member changed: $($property.Name)"}}
if((Get-Sha256 $fusedLeafSource)-ne$expectedFusedLeaf){throw 'Fused transformed leaf RTL SHA mismatch'}
if((Get-Sha256 $miterReceiptPath)-ne$expectedMiterReceiptSha){throw 'Fused UNISIM miter receipt SHA mismatch'}
$miterJson=Get-Content -LiteralPath $miterReceiptPath -Raw|ConvertFrom-Json
if(!$miterJson.pass -or $miterJson.schema-ne'cnn-v10-pw-half2x-fused-alu-clock-tree-receipt-v1' -or
   $miterJson.fused_leaf_sha256-ne'514d1b1134f9c84999ed131527c9d3700778b688897bdeccaa3b66811080f482' -or
   $miterJson.primitive_sha256-ne'278af8d1a70e8812fae70ac2cb1b9c637b9325d9f1276474c722e17771b07248'){
    throw 'Fused UNISIM miter receipt contract mismatch'
}
if((Get-Sha256 $transformReceiptPath)-ne$ExpectedTransformReceiptSha256.ToLowerInvariant()){throw 'Fused transform receipt SHA mismatch'}
$transformJson=Get-Content -LiteralPath $transformReceiptPath -Raw|ConvertFrom-Json
if(!$transformJson.pass -or $transformJson.schema-ne'cnn-v10-pw-half2x-fused-alu-generated-rtl-transform-v1' -or $transformJson.output_inventory_sha256-ne$ExpectedTransformOutputInventorySha256.ToLowerInvariant() -or $transformJson.output_component_sha256-ne'dc8f2691742fca33866102895e20a0e2bcb635caa308f0913074aabc33f768f2' -or !$transformJson.checks.leaf_instances_16){throw 'Fused transform receipt does not bind the requested generated RTL IP'}
$patchedIpFromReceipt=[IO.Path]::GetFullPath((Join-Path ([string]$apReadyPatchJson.rtl_dir) '..\..'))
if([IO.Path]::GetFullPath([string]$transformJson.source_ip)-ne$patchedIpFromReceipt){throw 'Fused transform002 source does not match the ap_ready patched002 IP tree'}
$fixtureJson=Get-Content -LiteralPath $fixtureManifest -Raw|ConvertFrom-Json
if($fixtureJson.schema-ne'cnn-v10.4-a0004-bram-stage-rtl-fixtures-v1'){throw 'Fixture manifest is not the frozen A0004 full-profile schema approved for A0005 reuse'}
$launchMemory=Assert-FzTaskMemoryForLaunch -MinimumPhysicalGiB $MinimumPhysicalGiB
Assert-NoHeavyOwner

New-Item -ItemType Directory -Path $evidence,$work|Out-Null
$rtlSnapshot=Join-Path $evidence 'rtl-snapshot'
$tbSnapshot=Join-Path $evidence 'tb-snapshot'
New-Item -ItemType Directory -Path $rtlSnapshot,$tbSnapshot|Out-Null
$freezeSnapshot=Join-Path $evidence 'candidate-source-manifest.json'
Copy-Item -LiteralPath $sourceManifest -Destination $freezeSnapshot
Copy-Item -LiteralPath $candidateContractPath -Destination (Join-Path $evidence 'candidate-contract.json')
Copy-Item -LiteralPath $combinedManifest -Destination (Join-Path $evidence 'combined-parameter-manifest.json')
Copy-Item -LiteralPath $hlsReceipt -Destination (Join-Path $evidence 'hls002-receipt.json')
Copy-Item -LiteralPath $apReadyPatchReceipt -Destination (Join-Path $evidence 'apready-patched002-receipt.json')
Copy-Item -LiteralPath $transformReceiptPath -Destination (Join-Path $evidence 'fused-transform002-receipt.json')
Copy-Item -LiteralPath $frozenStructureReceipt -Destination (Join-Path $evidence 'frozen-structure-audit-receipt.json')
$generated=@(Get-ChildItem -LiteralPath $hls -File|Where-Object{$_.Extension -in @('.v','.sv','.vh','.dat')}|Sort-Object Name)
if(!($generated|Where-Object{$_.Name-eq'cnn_pipeline_v10.v'})){throw 'Generated top cnn_pipeline_v10.v is absent'}
if(!($generated|Where-Object{$_.Name-eq'cnn_pipeline_v10_control_s_axi.v'})){throw 'Generated control RTL is absent'}
if(!($generated|Where-Object{$_.Extension-eq'.dat'})){throw 'Generated ROM .dat inventory is empty'}
foreach($file in $generated){Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $rtlSnapshot $file.Name)}
$dspSnapshot=Join-Path $rtlSnapshot 'cnn_v10_pw_dsp16.v'
if(Test-Path -LiteralPath $dspSnapshot){
    if((Get-Sha256 $dspSnapshot)-ne$expectedFusedLeaf){throw 'Generated fused leaf RTL conflicts with the transformed component binding'}
}else{Copy-Item -LiteralPath $fusedLeafSource -Destination $dspSnapshot}
$actualRtlDigest=Get-CanonicalInventoryDigest $rtlSnapshot
if($actualRtlDigest-ne$ExpectedGeneratedRtlDigest.ToLowerInvariant()){
    throw "Generated RTL/ROM canonical digest mismatch: $actualRtlDigest"
}
$structureAudit=Join-Path $evidence 'a0005-generated-rtl-structure-audit.json'
& $Python $structureAuditor --rtl-root $rtlSnapshot --expected-digest $ExpectedGeneratedRtlDigest `
    --expected-fused-leaf-sha256 $expectedFusedLeaf --source-manifest $sourceManifest `
    --source-manifest-sha256 $expectedSourceManifest --candidate-contract $candidateContractPath `
    --candidate-contract-sha256 $expectedCandidateContract --combined-manifest $combinedManifest `
    --combined-manifest-sha256 $expectedCombinedManifest --output $structureAudit
if($LASTEXITCODE-ne0){throw 'A0005 generated RTL structure gate failed'}
$actualDspSnapshot=Join-Path $evidence 'cnn_v10_pw_dsp16-actual-unisim.v'
Copy-Item -LiteralPath $dspSnapshot -Destination $actualDspSnapshot
$modelManifest=Join-Path $evidence 'vector-model-transform.json'
& $Python $modelPatcher --source $actualDspSnapshot --output $dspSnapshot --manifest $modelManifest --miter-receipt $miterReceiptPath --suffix _fused_model_unused
if($LASTEXITCODE-ne0){throw 'Verification-only vector fast-actor model transform failed'}
# The full kernel still instantiates the unsuffixed leaf.  Convert the renamed
# verification copy back to the original module names only after the patcher
# has proven that all DSP48E2 templates are gone.
$modelText=Get-Content -LiteralPath $dspSnapshot -Raw
$modelText=$modelText.Replace('_fused_model_unused','')
Write-Utf8NoBom $dspSnapshot $modelText
if((Get-Content -LiteralPath $dspSnapshot -Raw)-match'DSP48E2\s*#\s*\('){throw 'Verification RTL still contains DSP48E2'}
$simulationRtlDigest=Get-CanonicalInventoryDigest $rtlSnapshot
$rtlVerilog=@(Get-ChildItem -LiteralPath $rtlSnapshot -File -Filter '*.v')
$stageActors=@($rtlVerilog|Where-Object{$_.Name-match'(?i)stage_ring_(reader|writer)'})
if($stageActors.Count){throw "A0005 generated RTL still contains stage-ring actors: $($stageActors.Name -join ', ')"}
$chainPath=Join-Path $rtlSnapshot 'cnn_pipeline_v10_p_anonymous_namespace_chain.v'
Require-File $chainPath
$chainText=Get-Content -LiteralPath $chainPath -Raw
foreach($stale in @('param_broker_5','write_broker_5')){if($chainText-match$stale){throw "A0005 generated RTL contains stale five-client broker: $stale"}}
foreach($bundle in @('g_act_a_r','g_act_b_r')){if($chainText-notmatch("param_broker_2[^`r`n]*"+$bundle)){throw "A0005 generated RTL lacks two-client activation read broker for $bundle"}}
foreach($bundle in @('g_act_a_w','g_act_b_w')){if($chainText-notmatch("write_broker_2[^`r`n]*"+$bundle)){throw "A0005 generated RTL lacks two-client activation write broker for $bundle"}}
$readBrokerText=@(Get-ChildItem -LiteralPath $rtlSnapshot -File -Filter 'cnn_pipeline_v10_param_broker_2*.v'|ForEach-Object{Get-Content -LiteralPath $_.FullName -Raw}) -join "`n"
$writeBrokerText=@(Get-ChildItem -LiteralPath $rtlSnapshot -File -Filter 'cnn_pipeline_v10_write_broker_2*.v'|ForEach-Object{Get-Content -LiteralPath $_.FullName -Raw}) -join "`n"
if($readBrokerText-notmatch'ended_count[^\r\n]*==\s*32.d2'){throw 'A0005 generated activation read broker does not end at client count 2'}
if($writeBrokerText-notmatch'done[^\r\n]*==\s*32.d2'){throw 'A0005 generated activation write broker does not end at client count 2'}
$fifoTypes=[ordered]@{'fifo_w16_d4096'=2;'fifo_w16_d8192'=2;'fifo_w16_d2048'=2;'fifo_w16_d16'=6;'fifo_w11_d64'=2}
foreach($name in $fifoTypes.Keys){$count=[regex]::Matches($chainText,[regex]::Escape($name)).Count;if($count-lt[int]$fifoTypes[$name]){throw "A0005 generated RTL FIFO contract missing $name count>=$($fifoTypes[$name]); got $count"}}
foreach($dat in Get-ChildItem -LiteralPath $rtlSnapshot -File -Filter '*.dat'){
    Copy-Item -LiteralPath $dat.FullName -Destination (Join-Path $work $dat.Name)
}
$tbNames=@('tb_cnn_v10_fixture_pkg.sv','tb_cnn_v10_shared_ddr.sv','tb_cnn_v10_fifo_probe.sv')
foreach($name in $tbNames){Copy-Item -LiteralPath (Join-Path $acceleration $name) -Destination (Join-Path $tbSnapshot $name)}
$halfTbNames=@('tb_cnn_pipeline_v10_half2x_common.sv','tb_cnn_pipeline_v10_half2x_shared.sv','tb_cnn_pipeline_v10_half2x_reject.sv')
foreach($name in $halfTbNames){Copy-Item -LiteralPath (Join-Path $halfExperiment $name) -Destination (Join-Path $tbSnapshot $name)}
$tbNames+=$halfTbNames
$glblSnapshot=Join-Path $tbSnapshot 'glbl.v'
Copy-Item -LiteralPath $glblSource -Destination $glblSnapshot
$binding=Join-Path $tbSnapshot 'tb_cnn_v10_generated_binding.svh'
& $Python $bindingGenerator --top (Join-Path $rtlSnapshot 'cnn_pipeline_v10.v') --control (Join-Path $rtlSnapshot 'cnn_pipeline_v10_control_s_axi.v') --output $binding
if($LASTEXITCODE-ne0){throw "Binding generator failed: $LASTEXITCODE"}
Require-File $binding

$sourceList=@()
$sourceList+=Get-ChildItem -LiteralPath $rtlSnapshot -File|Where-Object{$_.Extension -in @('.v','.sv')}|Sort-Object Name|ForEach-Object{$_.FullName.Replace('\','/')}
$sourceList+=$tbNames|ForEach-Object{(Join-Path $tbSnapshot $_).Replace('\','/')}
$sourceList+=$glblSnapshot.Replace('\','/')
$sourceFile=Join-Path $evidence 'source-files.f'
$sourceList|Set-Content -LiteralPath $sourceFile -Encoding ascii

$steps=@()
if([string]::IsNullOrWhiteSpace($ReuseXsimDir)){
    $xsimDir=Join-Path $work 'xsim.dir'
    $steps+=Invoke-HiddenTool 'xvlog' $xvlog @('--sv','-d','CNN_V10_BINDING_READY','-i',$tbSnapshot,'-i',$rtlSnapshot,'-f',$sourceFile) (Join-Path $evidence 'xvlog.log')
    if($steps[-1].exit_code-ne0){throw 'xvlog failed'}
    $steps+=Invoke-HiddenTool 'xelab-shared' $xelab @('-mt',"$ElaborationThreads",'-O3','--debug','off','--timescale','1ns/1ps','-L','unisims_ver','--top','tb_cnn_pipeline_v10_half2x_shared','--top','glbl','--snapshot','v10_a0005_fused_shared') (Join-Path $evidence 'xelab-shared.log')
    if($steps[-1].exit_code-ne0){throw 'shared xelab failed'}
    $steps+=Invoke-HiddenTool 'xelab-reject' $xelab @('-mt',"$ElaborationThreads",'-O3','--debug','off','--timescale','1ns/1ps','-L','unisims_ver','--top','tb_cnn_pipeline_v10_half2x_reject','--top','glbl','--snapshot','v10_a0005_fused_reject') (Join-Path $evidence 'xelab-reject.log')
    if($steps[-1].exit_code-ne0){throw 'reject xelab failed'}
}else{
    $xsimDir=[IO.Path]::GetFullPath($ReuseXsimDir)
    Require-Dir $xsimDir
    foreach($snapshot in @('v10_a0005_fused_shared','v10_a0005_fused_reject')){
        Require-Dir (Join-Path $xsimDir $snapshot)
    }
    $steps+=[ordered]@{name='xvlog-xelab-reuse';exit_code=0;log=$null;log_sha256=$null;error_marker_found=$false;source_xsim_dir=$xsimDir}
}

$cases=@(
    [ordered]@{name='p3-baseline';snapshot='v10_a0005_fused_shared';args=@('PROFILE=3','REPEAT=0','STRESS=0')},
    [ordered]@{name='p2-repeat-switch-p3';snapshot='v10_a0005_fused_shared';args=@('PROFILE=2','REPEAT=1','STRESS=0','SECOND_PROFILE=3','SECOND_SWAPPED=1')},
    [ordered]@{name='p0-baseline';snapshot='v10_a0005_fused_shared';args=@('PROFILE=0','REPEAT=0','STRESS=0')},
    [ordered]@{name='p1-baseline';snapshot='v10_a0005_fused_shared';args=@('PROFILE=1','REPEAT=0','STRESS=0')},
    [ordered]@{name='p3-strong-pressure';snapshot='v10_a0005_fused_shared';args=@('PROFILE=3','REPEAT=0','STRESS=2')},
    [ordered]@{name='reject-gelu-span256-normal';snapshot='v10_a0005_fused_reject';args=@('PROFILE=0','ERROR_KIND=gelu_span256_normal')},
    [ordered]@{name='reject-gelu-span256-p3-dw';snapshot='v10_a0005_fused_reject';args=@('PROFILE=3','ERROR_KIND=gelu_span256_p3_dw')},
    [ordered]@{name='reject-gelu-span256-p3-pw';snapshot='v10_a0005_fused_reject';args=@('PROFILE=3','ERROR_KIND=gelu_span256_p3_pw')}
)
if($CaseNames.Count){
    $requested=@($CaseNames|ForEach-Object{[string]$_})
    $cases=@($cases|Where-Object{$requested-contains$_.name})
    $available=@($cases|ForEach-Object{$_.name})
    $missing=@($requested|Where-Object{$_-notin$available})
    if($missing.Count){throw "Unknown requested case(s): $($missing -join ', ')"}
}
if(!$cases.Count){throw 'No RTL cases selected'}
$logs=@()
$running=@()
$nextCase=0
$caseFailures=@()
$memoryGatePercent=90.0
$memoryGateWaits=0
$peakMemoryUsedPercent=0.0
$caseEvidenceRoot=Join-Path $evidence 'cases'
$caseWorkRoot=Join-Path $work 'cases'
New-Item -ItemType Directory -Path $caseEvidenceRoot,$caseWorkRoot|Out-Null
while($nextCase-lt$cases.Count -or $running.Count){
    $loopMemory=Get-FzTaskMemorySnapshot
    $peakMemoryUsedPercent=[Math]::Max($peakMemoryUsedPercent,[double]$loopMemory.memory_load_percent)
    foreach($job in @($running)){
        if(!$job.process.HasExited){continue}
        $exitCode=$job.process.ExitCode
        $logExists=Test-Path -LiteralPath $job.xsim_log -PathType Leaf
        $text=if($logExists){Get-Content -LiteralPath $job.xsim_log -Raw}else{''}
        $errorMarker=$text-match'(?m)^(Fatal:|ERROR:)'
        $passToken=$text-match'CNN_PIPELINE_V10_(SHARED|REJECT)_PASS'
        $casePass=($exitCode-eq0 -and $logExists -and !$errorMarker -and $passToken)
        $finishedUtc=(Get-Date).ToUniversalTime().ToString('o')
        $caseResult=[ordered]@{
            schema='cnn-v10.5-a0005-rtl-case-result-v1';name=$job.case.name
            snapshot=$job.case.snapshot;pass=$casePass;exit_code=$exitCode
            started_utc=$job.started_utc;finished_utc=$finishedUtc
            work_dir=$job.work_dir;launcher_log=$job.launcher_log;xsim_log=$job.xsim_log
            launcher_log_sha256=$(if(Test-Path -LiteralPath $job.launcher_log){Get-Sha256 $job.launcher_log}else{$null})
            xsim_log_sha256=$(if($logExists){Get-Sha256 $job.xsim_log}else{$null})
            memory_used_percent_at_launch=$job.memory_used_percent_at_launch
            error_marker_found=$errorMarker;pass_token_found=$passToken
        }
        $caseResultPath=Join-Path (Split-Path -Parent $job.xsim_log) 'result.json'
        Write-Utf8NoBom $caseResultPath (($caseResult|ConvertTo-Json -Depth 6)+"`n")
        $steps+=[ordered]@{
            name=('xsim-'+$job.case.name);exit_code=$exitCode;log=$job.xsim_log
            log_sha256=$caseResult.xsim_log_sha256;work_dir=$job.work_dir
            result=$caseResultPath;result_sha256=Get-Sha256 $caseResultPath
        }
        if($casePass){$logs+=$job.xsim_log}else{$caseFailures+=$job.case.name}
        $running=@($running|Where-Object{$_ -ne $job})
    }

    if($caseFailures.Count){
        if($running.Count){Start-Sleep -Seconds 5;continue}
        break
    }

    $launched=$false
    while($nextCase-lt$cases.Count -and $running.Count-lt$MaxParallelCases){
        $memory=Get-FzTaskMemorySnapshot
        $peakMemoryUsedPercent=[Math]::Max($peakMemoryUsedPercent,[double]$memory.memory_load_percent)
        if($memory.memory_load_percent-ge$memoryGatePercent){
            $memoryGateWaits++
            break
        }
        $case=$cases[$nextCase]
        $caseWork=Join-Path $caseWorkRoot $case.name
        $caseEvidence=Join-Path $caseEvidenceRoot $case.name
        New-Item -ItemType Directory -Path $caseWork,$caseEvidence|Out-Null
        foreach($dat in Get-ChildItem -LiteralPath $rtlSnapshot -File -Filter '*.dat'){
            Copy-Item -LiteralPath $dat.FullName -Destination (Join-Path $caseWork $dat.Name)
        }
        # xsim rewrites xsim_script.tcl and opens the snapshot .dbg database.
        # Concurrent processes therefore require private copies even when they
        # reuse the same successful xvlog/xelab result.
        $caseXsimDir=Join-Path $caseWork 'xsim.dir'
        New-Item -ItemType Directory -Path $caseXsimDir|Out-Null
        Copy-Item -Path (Join-Path $xsimDir '*') -Destination $caseXsimDir -Recurse -Force
        $log=Join-Path $caseEvidence 'xsim.log'
        $launcherLog=Join-Path $caseEvidence 'launcher.log'
        $arguments=@($case.snapshot,'--xsimdir',$caseXsimDir,
                     '--log',$log,'--wdb',(Join-Path $caseWork 'waves.wdb'),'--onerror','quit',
                     '-testplusarg',"FIXTURE_ROOT=$fixture",'-testplusarg','TOKEN_NUMER=1',
                     '-testplusarg','TOKEN_DENOM=2','-testplusarg','TOKEN_BURST=32',
                     '-testplusarg','B_DELAY=3')
        foreach($value in $case.args){$arguments+=@('-testplusarg',$value)}
        $arguments+='--runall'
        $running+=Start-HiddenCase $case $xsim $arguments $caseWork $launcherLog $log ([double]$memory.memory_load_percent)
        $nextCase++
        $launched=$true
    }
    if($nextCase-lt$cases.Count -or $running.Count){
        if(!$launched){Start-Sleep -Seconds 5}else{Start-Sleep -Milliseconds 250}
    }
}
if($caseFailures.Count){throw "xsim case failure(s): $($caseFailures -join ', ')"}

$resultPath=Join-Path $evidence 'rtl-results.json'
$collectArgs=@($collector,'--dut-rtl-root',$rtlSnapshot,'--tb-root',$tbSnapshot,
               '--ddr-model',(Join-Path $tbSnapshot 'tb_cnn_v10_shared_ddr.sv'),
               '--fixture-manifest',$fixtureManifest,'--source-freeze-manifest',$freezeSnapshot,
               '--expected-source-freeze-sha256',$expectedSourceManifest,
               '--candidate-contract',$candidateContractPath,
               '--expected-candidate-contract-sha256',$expectedCandidateContract,
               '--dsp-rtl',$dspSnapshot,
               '--clock-period-ns','5.0','--model-limited','--output',$resultPath)
foreach($name in $tbNames){$collectArgs+=@('--tb-source',(Join-Path $tbSnapshot $name))}
$collectArgs+=@('--tb-source',$binding)
$collectArgs+=@('--tb-source',$glblSnapshot)
foreach($log in $logs){$collectArgs+=@('--log',$log)}
& $Python @collectArgs
if($LASTEXITCODE-ne0){throw "Result collector failed: $LASTEXITCODE"}
Require-File $resultPath
$result=Get-Content -LiteralPath $resultPath -Raw|ConvertFrom-Json
$pass=(@($result.cases).Count-eq$ExpectedCollectorCases -and
       @($steps|Where-Object{$_.exit_code-ne0}).Count-eq0 -and
       $result.source.dut_rtl_sha256-eq$simulationRtlDigest -and
       $actualRtlDigest-eq$ExpectedGeneratedRtlDigest.ToLowerInvariant())
$receipt=[ordered]@{
    schema='cnn-v10.5-a0005-fused-alu-layered-rtl-simulation-run-receipt-v1';pass=$pass
    generated_utc=(Get-Date).ToUniversalTime().ToString('o');board_operations=$false
    execution=[ordered]@{
        scheduling='bounded_parallel';serial_cases=($MaxParallelCases-eq1)
        max_parallel_cases=$MaxParallelCases;case_count=$cases.Count
        elaboration_threads=$ElaborationThreads;compile_and_elaborate_jobs=1
        process_priority='AboveNormal';window_style='Hidden'
        shared_read_only_xsim_snapshot=(Join-Path $work 'xsim.dir')
        independent_case_workdirs=$true;independent_case_logs=$true
    }
    memory_gate=[ordered]@{
        launch_pause_used_percent=$memoryGatePercent
        behavior='pause_new_case_launches_and_wait; never terminate running cases'
        admission_available_physical_gib=[Math]::Round([double]$launchMemory.available_physical_gib,3)
        memory_helper_sha256=Get-Sha256 $memoryHelper
        wait_samples=$memoryGateWaits
        peak_sampled_used_percent=[Math]::Round($peakMemoryUsedPercent,3)
    }
    inputs=[ordered]@{hls_rtl=$hls;hls002_receipt_sha256=$expectedHlsReceipt;apready_patched002_receipt_sha256=$requiredApReadyPatchReceipt;fixture_manifest_sha256=Get-Sha256 $fixtureManifest;candidate_source_manifest_sha256=$expectedSourceManifest;candidate_contract_sha256=$expectedCandidateContract;combined_parameter_manifest_sha256=$expectedCombinedManifest;frozen_structure_audit_receipt_sha256=$requiredStructureReceipt;structure_audit_sha256=Get-Sha256 $structureAudit;actual_fused_leaf_rtl_sha256=$expectedFusedLeaf;transform_receipt_sha256=Get-Sha256 $transformReceiptPath;transform_output_inventory_sha256=$requiredTransformInventory;fused_unisim_miter_receipt_sha256=Get-Sha256 $miterReceiptPath;actual_generated_rtl_rom_digest=$actualRtlDigest;verification_generated_rtl_rom_digest=$simulationRtlDigest;fused_model_transform_sha256=Get-Sha256 $modelManifest}
    contract=[ordered]@{abi='0x000A0005';software='sw10.5';guard_caps='0x00000fff';combined_parameter_manifest_sha256=$expectedCombinedManifest;external_axi_masters=6;activation_broker_clients=2;broker_end_count=2;stage_ddr_actors=0;legacy_stage_ddr_accesses_expected=0;residual_ddr_words=4096;residual_wrap_required=$true;stage_fifo_depths=[ordered]@{q3_a=4096;q3_b=4096;q7_a=8192;q7_b=8192;expanded_a=2048;expanded_b=2048};scale_response_bits=16;scale_response_depth=16;row_ready_bits=11;row_ready_depth=64;pw2_columns_depth=1024;burst_length=32;command_depth=2;repeat_without_reset_gate=$true;pw1_physical_banks=8;dw7_fixed_physical_reads=16;pw2_packed_width_bits=160}
    verification_boundary=[ordered]@{model='fused-identity cycle-equivalent replacement of cnn_v10_pw_dsp8_fast_fused_alu internals';actual_dual_clock_wrapper_preserved=$true;actual_unisim_leaf=$actualDspSnapshot;synthesis_input_allowed=$false}
    snapshots=[ordered]@{rtl=$rtlSnapshot;tb=$tbSnapshot;actual_generated_rtl_rom_digest=$actualRtlDigest;verification_generated_rtl_rom_digest=$result.source.dut_rtl_sha256;tb_digest=$result.source.tb_sha256;glbl_sha256=Get-Sha256 $glblSnapshot}
    steps=$steps;results=[ordered]@{path=$resultPath;sha256=Get-Sha256 $resultPath;case_count=@($result.cases).Count}
}
$receiptPath=Join-Path $evidence 'receipt.json'
Write-Utf8NoBom $receiptPath (($receipt|ConvertTo-Json -Depth 12)+"`n")
if(!$pass){exit 1}
