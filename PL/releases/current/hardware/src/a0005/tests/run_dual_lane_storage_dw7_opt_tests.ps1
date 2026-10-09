[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CandidateRoot,
    [Parameter(Mandatory=$true)][string]$CandidateContract,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$CandidateContractSha256,
    [Parameter(Mandatory=$true)][string]$CandidateSourceManifest,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$CandidateSourceManifestSha256,
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [string]$PythonExe='python',
    [string]$VitisRoot='D:\Vivado\2026.1\Vitis',
    [switch]$StaticOnly
)

$ErrorActionPreference='Stop'
$testsRoot=$PSScriptRoot
$requirements=Join-Path $testsRoot 'contract_requirements.json'
$validator=Join-Path $testsRoot 'validate_candidate_contract.py'
$oracle=Join-Path $testsRoot 'oracle_generate.py'
$tb=Join-Path $testsRoot 'tb_dual_lane_storage_dw7_opt.cpp'
$adapterHeader=Join-Path $testsRoot 'candidate_adapter_contract.hpp'
$runner=$PSCommandPath
$accelerationRoot=[IO.Path]::GetFullPath((Join-Path $testsRoot '..\..\..'))

function Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Run-Owned([string]$File,[string[]]$Arguments,[string]$Log) {
    $process=Start-Process -FilePath $File -ArgumentList $Arguments -WindowStyle Hidden `
        -RedirectStandardOutput $Log -RedirectStandardError ($Log+'.stderr') -PassThru
    try {$process.PriorityClass='BelowNormal'} catch {}
    $process.WaitForExit()
    return $process.ExitCode
}

foreach($path in @($CandidateRoot,$CandidateContract,$CandidateSourceManifest,$requirements,$validator,$oracle,$tb,$adapterHeader,$runner)) {
    if(-not(Test-Path -LiteralPath $path)){throw "Missing required input: $path"}
}
$candidateRootPath=[IO.Path]::GetFullPath($CandidateRoot)
$contractPath=[IO.Path]::GetFullPath($CandidateContract)
$manifestPath=[IO.Path]::GetFullPath($CandidateSourceManifest)
if((Sha $contractPath)-ne$CandidateContractSha256.ToLowerInvariant()){throw 'Candidate contract SHA256 mismatch'}
if((Sha $manifestPath)-ne$CandidateSourceManifestSha256.ToLowerInvariant()){throw 'Candidate source manifest SHA256 mismatch'}
if(Test-Path -LiteralPath $EvidenceDir){throw "Refusing to overwrite evidence: $EvidenceDir"}
$evidence=New-Item -ItemType Directory -Path $EvidenceDir
$snapshot=New-Item -ItemType Directory -Path (Join-Path $evidence 'source-snapshot')
$testSnapshot=New-Item -ItemType Directory -Path (Join-Path $snapshot 'tests')
$candidateSnapshot=New-Item -ItemType Directory -Path (Join-Path $snapshot 'candidate')
$build=New-Item -ItemType Directory -Path (Join-Path $evidence 'build')

foreach($path in @($requirements,$validator,$oracle,$tb,$adapterHeader,$runner)) {
    Copy-Item -LiteralPath $path -Destination $testSnapshot
}
Copy-Item -LiteralPath $contractPath -Destination (Join-Path $snapshot 'candidate-contract.json')
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $snapshot 'candidate-source-manifest.json')

$staticReceipt=Join-Path $evidence 'static-contract-receipt.json'
$validateArgs=@(
    (Join-Path $testSnapshot 'validate_candidate_contract.py'),'--requirements',(Join-Path $testSnapshot 'contract_requirements.json'),
    '--candidate-contract',$contractPath,'--candidate-root',$candidateRootPath,
    '--source-manifest',$manifestPath,'--receipt',$staticReceipt
)
if((Run-Owned $PythonExe $validateArgs (Join-Path $evidence 'static-contract.log'))-ne0){throw 'Candidate static contract gate failed'}

$manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
$compileSources=@()
foreach($entry in $manifest.files) {
    $relative=[string]$entry.path
    if([IO.Path]::IsPathRooted($relative)-or$relative.Contains('..')){throw "Unsafe manifest path: $relative"}
    $source=Join-Path $candidateRootPath $relative
    if((Sha $source)-ne([string]$entry.sha256).ToLowerInvariant()){throw "Candidate changed after static gate: $relative"}
    $destination=Join-Path $candidateSnapshot $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination)|Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
    if((Sha $destination)-ne([string]$entry.sha256).ToLowerInvariant()){throw "Snapshot copy mismatch: $relative"}
    if($entry.role-in @('adapter_source','native_source')){$compileSources+=$destination}
}

if($StaticOnly){
    [ordered]@{
        schema='dual-lane-storage-dw7-opt-run-v1';status='STATIC_PASS';pass=$true;native_executed=$false
        candidate_contract_sha256=Sha (Join-Path $snapshot 'candidate-contract.json')
        candidate_source_manifest_sha256=Sha (Join-Path $snapshot 'candidate-source-manifest.json')
        static_contract_receipt_sha256=Sha $staticReceipt
        compiled_roles=@('adapter_source','native_source')
        snapshot_only_roles=@('implementation_source','header')
    }|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $evidence 'receipt.json') -Encoding utf8
    Write-Output 'DUAL_LANE_STORAGE_DW7_OPT_STATIC_PASS'
    exit 0
}

$oracleDir=Join-Path $build 'oracle'
$oracleArgs=@((Join-Path $testSnapshot 'oracle_generate.py'),'--output',$oracleDir)
if((Run-Owned $PythonExe $oracleArgs (Join-Path $evidence 'oracle-generate.log'))-ne0){throw 'Independent oracle generation failed'}
$oracleManifest=Join-Path $oracleDir 'oracle-manifest.json'
if(-not(Test-Path -LiteralPath $oracleManifest)){throw 'Oracle manifest missing'}

$compiler=Join-Path $VitisRoot 'tps\mingw\10.0.0\win64.o\nt\bin\g++.exe'
if(-not(Test-Path -LiteralPath $compiler)){throw "Missing Vitis native compiler: $compiler"}
$exe=Join-Path $build 'dual_lane_storage_dw7_opt_test.exe'
$compileArgs=@(
    '-std=c++17','-O2','-Wall','-Wextra','-Werror',
    '-Wno-unknown-pragmas','-Wno-deprecated-copy','-Wno-comment',
    ('-I'+(Join-Path $VitisRoot 'include')),
    ('-I'+$testSnapshot),('-I'+$candidateSnapshot),
    (Join-Path $testSnapshot 'tb_dual_lane_storage_dw7_opt.cpp')
)
$compileArgs+=@($compileSources)
$compileArgs+=@('-o',$exe)
$oldPath=$env:PATH
$oldVitis=$env:XILINX_VITIS
$errorMode=$null
try {
    . (Join-Path $accelerationRoot 'task_tool_error_mode.ps1')
    $errorMode=Enable-FzTaskToolErrorMode
    $runtime=@(
        (Split-Path -Parent $compiler),(Join-Path $VitisRoot 'bin'),
        (Join-Path $VitisRoot 'tps\win64'),(Join-Path $VitisRoot 'lib\win64.o'),
        (Join-Path $VitisRoot 'tps\mingw\6.2.0\win64.o\nt\bin'),
        (Join-Path $VitisRoot 'tps\mingw\6.2.0\win64.o\nt\libexec\gcc\x86_64-w64-mingw32\6.2.0')
    )
    $env:XILINX_VITIS=$VitisRoot
    $env:PATH=(($runtime+@($oldPath))-join';')
    if((Run-Owned $compiler $compileArgs (Join-Path $evidence 'compile.log'))-ne0){throw 'Native candidate test compile failed'}
    if(-not(Test-Path -LiteralPath $exe)){throw 'Native test executable missing'}
    $nativeLog=Join-Path $evidence 'native-test.log'
    if((Run-Owned $exe @($oracleDir) $nativeLog)-ne0){throw 'Native candidate test failed'}
    $passLine=Select-String -LiteralPath $nativeLog -Pattern '^DUAL_LANE_STORAGE_DW7_OPT_NATIVE_PASS ' | Select-Object -Last 1
    if($null-eq$passLine){throw 'Native PASS token missing'}
} finally {
    $env:PATH=$oldPath
    $env:XILINX_VITIS=$oldVitis
    if($null-ne$errorMode){Restore-FzTaskToolErrorMode -PreviousMode $errorMode}
}

$sourceHashes=@()
Get-ChildItem -LiteralPath $snapshot -Recurse -File|Sort-Object FullName|ForEach-Object {
    $sourceHashes+=[ordered]@{path=$_.FullName.Substring($snapshot.FullName.Length+1).Replace('\','/');sha256=Sha $_.FullName;bytes=$_.Length}
}
$receipt=[ordered]@{
    schema='dual-lane-storage-dw7-opt-run-v1';status='PASS';pass=$true;native_executed=$true
    candidate_id=(Get-Content (Join-Path $snapshot 'candidate-contract.json') -Raw|ConvertFrom-Json).candidate_id
    static_contract_receipt_sha256=Sha $staticReceipt
    oracle_manifest=[ordered]@{path=$oracleManifest;sha256=Sha $oracleManifest}
    compile_log_sha256=Sha (Join-Path $evidence 'compile.log')
    native_log_sha256=Sha $nativeLog
    pass_token=$passLine.Line
    compiled_roles=@('adapter_source','native_source')
    snapshot_only_roles=@('implementation_source','header')
    source_snapshot=$sourceHashes
}
$receipt|ConvertTo-Json -Depth 9|Set-Content -LiteralPath (Join-Path $evidence 'receipt.json') -Encoding utf8
Write-Output $passLine.Line
