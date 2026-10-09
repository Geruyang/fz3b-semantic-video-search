[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [Parameter(Mandatory=$true)][string]$TestManifest,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedCppSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedHppSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedPointwiseSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedBrokerSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedArithmeticSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGeluSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedIdentitySha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedDdrSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedScaleServiceSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedN1Sha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGeluSegmentedSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedTbSha256,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*\.cpp$')][string]$TestbenchFile='cnn_pipeline_v10_host_tb.cpp',
    [switch]$CompileO2,
    [string]$VitisRoot='D:\Vivado\2026.1\Vitis',
    [string]$GeneratedRecipeDir='artifacts\board-debug-20261005\acceleration\jtag\cnn-v6-tb-compile-smoke-002\work\hls\csim\build'
)
$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
function Sha([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function Unix([string]$p){([IO.Path]::GetFullPath($p)-replace '\\','/')}
function Safe([string]$n){if($n -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$'){throw "unsafe case $n"};$n}
function Run-Owned([string]$exe,[string[]]$arguments,[string]$log,[int]$timeout=0){
    $psi=[Diagnostics.ProcessStartInfo]::new();$psi.FileName=$exe;$psi.WorkingDirectory=(Get-Location).Path
    $psi.UseShellExecute=$false;$psi.CreateNoWindow=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
    foreach($a in $arguments){[void]$psi.ArgumentList.Add($a)}
    $p=[Diagnostics.Process]::new();$p.StartInfo=$psi;if(!$p.Start()){throw "start failed: $exe"}
    try{$p.PriorityClass=[Diagnostics.ProcessPriorityClass]::BelowNormal}catch{}
    $out=$p.StandardOutput.ReadToEndAsync();$err=$p.StandardError.ReadToEndAsync();$sw=[Diagnostics.Stopwatch]::StartNew()
    $intensive=(Get-FzTaskMemorySnapshot).intensive_monitoring_required;$pressure=0;$memoryStop=$false;$timeoutStop=$false
    while(!$p.WaitForExit(5000)){
        if($intensive){$m=Get-FzTaskMemorySnapshot;$intensive=$m.intensive_monitoring_required;if($m.pressure){$pressure++}else{$pressure=0};if($pressure-ge3){$memoryStop=$true;& "$env:SystemRoot\System32\taskkill.exe" /PID $p.Id /T /F *> $null;$p.WaitForExit();break}}
        if($timeout-gt0-and$sw.Elapsed.TotalSeconds-ge$timeout){$timeoutStop=$true;& "$env:SystemRoot\System32\taskkill.exe" /PID $p.Id /T /F *> $null;$p.WaitForExit();break}
    }
    $p.WaitForExit();@($out.GetAwaiter().GetResult(),$err.GetAwaiter().GetResult())|Set-Content -LiteralPath $log -Encoding utf8
    [pscustomobject]@{pid=$p.Id;exit=$p.ExitCode;wall=$sw.Elapsed.TotalSeconds;peak=$p.PeakWorkingSet64;memory_stop=$memoryStop;timeout_stop=$timeoutStop}
}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$tbName=[IO.Path]::GetFileName($TestbenchFile)
$tbStem=[IO.Path]::GetFileNameWithoutExtension($tbName)
$src=[ordered]@{
 'cnn_pipeline_v10.cpp'=Join-Path $PSScriptRoot 'cnn_pipeline_v10.cpp';'cnn_pipeline_v10.hpp'=Join-Path $PSScriptRoot 'cnn_pipeline_v10.hpp';
 'cnn_v10_pointwise.hpp'=Join-Path $PSScriptRoot 'cnn_v10_pointwise.hpp';'cnn_v10_param_broker.hpp'=Join-Path $PSScriptRoot 'cnn_v10_param_broker.hpp';
 'cnn_v10_arithmetic.hpp'=Join-Path $PSScriptRoot 'cnn_v10_arithmetic.hpp';'cnn_v10_gelu.hpp'=Join-Path $PSScriptRoot 'cnn_v10_gelu.hpp';
 'cnn_v10_identity.hpp'=Join-Path $PSScriptRoot 'cnn_v10_identity.hpp';'cnn_v10_ddr.hpp'=Join-Path $PSScriptRoot 'cnn_v10_ddr.hpp';
 'cnn_v10_scale_service.hpp'=Join-Path $PSScriptRoot 'cnn_v10_scale_service.hpp';'cnn_v10_n1.hpp'=Join-Path $PSScriptRoot 'cnn_v10_n1.hpp';
 'cnn_v10_gelu_segmented.hpp'=Join-Path $PSScriptRoot 'cnn_v10_gelu_segmented.hpp';
 $tbName=Join-Path $PSScriptRoot $tbName}
$exp=[ordered]@{'cnn_pipeline_v10.cpp'=$ExpectedCppSha256;'cnn_pipeline_v10.hpp'=$ExpectedHppSha256;'cnn_v10_pointwise.hpp'=$ExpectedPointwiseSha256;
 'cnn_v10_param_broker.hpp'=$ExpectedBrokerSha256;'cnn_v10_arithmetic.hpp'=$ExpectedArithmeticSha256;'cnn_v10_gelu.hpp'=$ExpectedGeluSha256;
 'cnn_v10_identity.hpp'=$ExpectedIdentitySha256;'cnn_v10_ddr.hpp'=$ExpectedDdrSha256;'cnn_v10_scale_service.hpp'=$ExpectedScaleServiceSha256;
 'cnn_v10_n1.hpp'=$ExpectedN1Sha256;'cnn_v10_gelu_segmented.hpp'=$ExpectedGeluSegmentedSha256;
 $tbName=$ExpectedTbSha256}
if(Test-Path -LiteralPath $EvidenceDir){throw "EvidenceDir must be new: $EvidenceDir"};if(!(Test-Path -LiteralPath $TestManifest -PathType Leaf)){throw "missing manifest"}
$testManifestPath=[IO.Path]::GetFullPath($TestManifest);$testManifestSha=Sha $testManifestPath
$manifest=Get-Content -LiteralPath $testManifestPath -Raw|ConvertFrom-Json;$cases=@($manifest.cases);if(!$cases.Count){throw 'no cases'}
$repeatSwitchCases=@($cases|Where-Object{
 $a=@($_.args|ForEach-Object{[string]$_})
 $a.Count-ge17 -and $a[0]-eq'sequence' -and (($a.Count-1)%8)-eq0
})
if(!$repeatSwitchCases.Count){throw 'native manifest requires a two-or-more-profile sequence case for repeat-without-reset gating'}
# Optional source_manifest entries freeze upcoming DSP-blackbox collateral.
# Schema: {"path":"file","sha256":"64hex","role":"header|native_header|native_source|metadata|rtl"}.
# Paths are safe source-directory-relative paths. native_source entries are
# compiled and linked from the snapshot; the other roles are hashed/copied.
$sourceManifestEntries=@()
if($null-ne$manifest.PSObject.Properties['source_manifest']){$sourceManifestEntries=@($manifest.source_manifest)}
$additionalNativeNames=@();$additionalInventory=@();$allowedRoles=@('header','native_header','native_source','metadata','rtl')
$roleExtensions=@{header=@('.h','.hpp');native_header=@('.h','.hpp');native_source=@('.c','.cc','.cpp');metadata=@('.json');rtl=@('.v','.sv')}
foreach($entry in $sourceManifestEntries){
 if($null-eq$entry.PSObject.Properties['path']-or$null-eq$entry.PSObject.Properties['sha256']-or$null-eq$entry.PSObject.Properties['role']){throw 'source_manifest entry requires path, sha256, and role'}
 $n=([string]$entry.path)-replace'\\','/';$hash=([string]$entry.sha256).ToLowerInvariant();$role=([string]$entry.role).ToLowerInvariant()
 $segments=@($n.Split('/'));if([IO.Path]::IsPathRooted($n)-or$n-notmatch'^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$'-or@($segments|Where-Object{$_-in@('','.', '..')}).Count){throw "unsafe source_manifest path $n"}
 if($hash-notmatch'^[0-9a-f]{64}$'){throw "invalid source_manifest SHA256 for $n"}
 if($allowedRoles-notcontains$role){throw "invalid source_manifest role for $n"}
 if($n-eq'cnn_v10_stage_ring.hpp'){throw 'A0004 source_manifest must not include the retired stage-ring header'}
 $ext=[IO.Path]::GetExtension($n).ToLowerInvariant();if($roleExtensions[$role]-notcontains$ext){throw "source_manifest extension/role mismatch for $n"}
 if($src.Keys-contains$n){throw "duplicate frozen source name $n"}
 $src[$n]=Join-Path $PSScriptRoot ($n-replace'/','\');$exp[$n]=$hash
 if($role-eq'native_source'){$additionalNativeNames+=$n}
 $additionalInventory+=[ordered]@{path=$n;sha256=$hash;role=$role}
}
$dspRoleContract=[ordered]@{
 'cnn_v10_pw_dsp.hpp'='native_header'
 'cnn_v10_pw_dsp_model.cpp'='native_source'
 'cnn_v10_pw_dsp16.json'='metadata'
 'cnn_v10_pw_dsp16.v'='rtl'
}
# These files are optional until their owning product change lands.  Once a
# known file exists, however, its exact role and digest must be frozen by the
# manifest; a generic extension-compatible role is not sufficient.
foreach($n in $dspRoleContract.Keys){
 $candidate=Join-Path $PSScriptRoot $n
 if(Test-Path -LiteralPath $candidate -PathType Leaf){
  $matches=@($additionalInventory|Where-Object{$_.path-eq$n})
  if($matches.Count-ne1){throw "required DSP collateral is absent or duplicated in source_manifest: $n"}
  if($matches[0].role-ne$dspRoleContract[$n]){throw "DSP source_manifest role must be $($dspRoleContract[$n]) for $n"}
 }
}
$detectedDspCollateral=@(Get-ChildItem -LiteralPath $PSScriptRoot -Recurse -File|Where-Object{
 $_.Name-match'(?i)(dsp|blackbox|behavior)' -and $_.FullName-match'(?i)cnn_v10' -and $_.Extension.ToLowerInvariant()-in@('.h','.hpp','.c','.cc','.cpp','.json','.v','.sv')})
$detectedDspRelative=@($detectedDspCollateral|ForEach-Object{[IO.Path]::GetRelativePath($PSScriptRoot,$_.FullName).Replace([char]0x5c,[char]0x2f)})
$unmanifestedDspCollateral=@($detectedDspRelative|Where-Object{$src.Keys-notcontains$_})
if($unmanifestedDspCollateral.Count){throw "DSP/blackbox behavior collateral is present but absent from source_manifest: $($unmanifestedDspCollateral-join', ')"}
$actual=[ordered]@{};foreach($n in $src.Keys){if(!(Test-Path -LiteralPath $src[$n])){throw "missing $n"};$actual[$n]=Sha $src[$n];if($actual[$n]-ne$exp[$n].ToLowerInvariant()){throw "hash mismatch $n"}}
$ev=[IO.Path]::GetFullPath($EvidenceDir);if($ev-match'\s'){throw 'EvidenceDir must not contain whitespace'}
$snap=Join-Path $ev 'source-snapshot';$build=Join-Path $ev 'build';$logs=Join-Path $ev 'case-logs';New-Item -ItemType Directory -Path $snap,$build,$logs -Force|Out-Null
foreach($n in $src.Keys){$dst=Join-Path $snap ($n-replace'/','\');$dstParent=Split-Path -Parent $dst;if(!(Test-Path -LiteralPath $dstParent)){New-Item -ItemType Directory -Path $dstParent -Force|Out-Null};Copy-Item -LiteralPath $src[$n] -Destination $dst;if((Sha $dst)-ne$actual[$n]){throw "source changed while snapshotting $n"}}
$manifestSnapshot=Join-Path $ev 'test-manifest.json';Copy-Item -LiteralPath $testManifestPath -Destination $manifestSnapshot;if((Sha $manifestSnapshot)-ne$testManifestSha){throw 'test manifest changed while snapshotting'}
# Quoted project includes must resolve inside the frozen snapshot.  This keeps
# both direct and nested headers from falling through to the live source tree.
foreach($n in @($src.Keys|Where-Object{[IO.Path]::GetExtension($_).ToLowerInvariant()-in@('.h','.hpp','.c','.cc','.cpp')})){
 $snapshotSource=Join-Path $snap ($n-replace'/','\');$sourceText=Get-Content -LiteralPath $snapshotSource -Raw
 foreach($match in [regex]::Matches($sourceText,'(?m)^\s*#\s*include\s*"([^"]+)"')){
  $included=$match.Groups[1].Value-replace'/','\';$near=Join-Path (Split-Path -Parent $snapshotSource) $included;$rootInclude=Join-Path $snap $included
  if(!(Test-Path -LiteralPath $near -PathType Leaf)-and!(Test-Path -LiteralPath $rootInclude -PathType Leaf)){throw "snapshot include closure missing $included (included by $n)"}
 }
}
# A0004 restores BRAM stage FIFOs and leaves only the residual ring in DDR.
# Refuse an old ABI or a partially migrated snapshot even with valid hashes.
$identityText=Get-Content -LiteralPath (Join-Path $snap 'cnn_v10_identity.hpp') -Raw
$n1Text=Get-Content -LiteralPath (Join-Path $snap 'cnn_v10_n1.hpp') -Raw
$apiText=Get-Content -LiteralPath (Join-Path $snap 'cnn_pipeline_v10.hpp') -Raw
$kernelText=Get-Content -LiteralPath (Join-Path $snap 'cnn_pipeline_v10.cpp') -Raw
$pointwiseText=Get-Content -LiteralPath (Join-Path $snap 'cnn_v10_pointwise.hpp') -Raw
$scaleText=Get-Content -LiteralPath (Join-Path $snap 'cnn_v10_scale_service.hpp') -Raw
if($identityText-notmatch'kAbiIdentity\s*=\s*0x000A0005u' -or $identityText-notmatch'"sw10[.]5"'){throw 'native validation requires A0004/sw10.4 identity'}
if($n1Text-notmatch'kN1ArenaWords\s*=\s*69632'){throw 'native validation requires A0004 N1 arena 69632'}
foreach($pattern in @('p==0[?]16384:p==1[?]8192:p==2[?]32768','p==3[?]1:0','CNN_V10_SCRATCH_CHUNK_WORDS\s*=\s*1024','CNN_V10_SCRATCH_CHUNKS\s*=\s*4')){if($apiText-notmatch$pattern){throw "A0004 profile/arena contract missing $pattern"}}
foreach($pattern in @('typedef\s+ap_uint<11>\s+RowReadyToken','block<32\s*&&\s*row<64','token[.]range\(10,6\)','token[.]range\(5,0\)','2\s*[*]\s*cnn_v10_slot_words\(p\)\s*[+]\s*CNN_V10_SCRATCH_WORDS')){if($apiText-notmatch$pattern){throw "A0004 row-ready/arena contract missing $pattern"}}
if($scaleText-notmatch'typedef\s+ap_int<16>\s+ScaleResponse'){throw 'A0004 scale response must be signed 16-bit'}
if($pointwiseText-notmatch'#define\s+CNN_V10_PW2_COLUMNS_DEPTH\s+1024'){throw 'PW2 columns depth must remain 1024'}; if($pointwiseText-notmatch'typedef\s+(?:::)?cnn_v10_candidate::Pw2StoredColumn\s+Pw2StoredColumn'){throw 'A0005 signed40 PW2 storage binding missing'}; if($identityText-notmatch'kGuardCapabilities\s*=\s*0x00000fffu' -or $identityText-notmatch'kPw2Signed40ApprovedParamsCapability\s*=\s*0x00000800u'){throw 'A0005 capability identity missing'}
foreach($pair in @(@('q3_a',4096),@('q3_b',4096),@('q7_a',8192),@('q7_b',8192),@('expanded_a',2048),@('expanded_b',2048),@('row_ready_a',64),@('row_ready_b',64),@('scale_rsp_a',16),@('scale_rsp_b',16),@('a_read_cmd',2),@('b_read_cmd',2),@('a_write_cmd',2),@('b_write_cmd',2))){
 $pattern='#pragma\s+HLS\s+STREAM\s+variable='+[regex]::Escape([string]$pair[0])+'\s+depth='+[string]$pair[1]
 if($kernelText-notmatch$pattern){throw "A0004 stream depth contract missing $($pair[0])=$($pair[1])"}
}
foreach($pattern in @('a_read_cmd\[2\],b_read_cmd\[2\]','a_write_cmd\[2\],b_write_cmd\[2\]','param_broker<2>\(ar_a','param_broker<2>\(ar_b','write_broker<2>\(aw_a','write_broker<2>\(aw_b')){if($kernelText-notmatch$pattern){throw "A0004 two-client broker contract missing $pattern"}}
if($kernelText-match'(?i)stage_ring|kStageRingWords'){throw 'A0004 product snapshot still contains a stage DDR ring actor'}
$axiPragmas=@([regex]::Matches($kernelText,'(?m)^#pragma\s+HLS\s+INTERFACE\s+mode=m_axi\s+port=.*$')|ForEach-Object{$_.Value})
if($axiPragmas.Count-ne6 -or @($axiPragmas|Where-Object{$_-notmatch'max_(read|write)_burst_length=32'}).Count){throw 'A0004 requires exactly six AXI masters with burst length 32'}
$recipe=if([IO.Path]::IsPathRooted($GeneratedRecipeDir)){[IO.Path]::GetFullPath($GeneratedRecipeDir)}else{[IO.Path]::GetFullPath((Join-Path $root $GeneratedRecipeDir))}
$mk=Join-Path $recipe 'csim.mk';$rules=Join-Path $recipe 'Makefile.rules';if(!(Test-Path $mk)-or!(Test-Path $rules)){throw 'missing official generated recipe'}
$text=Get-Content $mk -Raw;foreach($term in @('-D__HLS_COSIM__','-D__VITIS_HLS__','-fhls-csim','-fhlstoplevel=cnn_pipeline_v6')){if(!$text.Contains($term)){throw "recipe missing $term"}}
if($text.Contains('HLS_STREAM_THREAD_UNSAFE')-or$text.Contains('ALLOW_EMPTY_HLS_STREAM_READS')){throw 'nonblocking stream recipe rejected'}
if(!(Get-Content $rules -Raw).Contains('-lpthread')){throw 'pthread missing'}
$cpp=Unix(Join-Path $snap 'cnn_pipeline_v10.cpp');$tb=Unix(Join-Path $snap $tbName);$inc=Unix $snap
$local=$text.Replace('../../../../source-snapshot/cnn_pipeline_v6_tb.cpp',$tb).Replace('../../../../source-snapshot/cnn_pipeline_v6.cpp',$cpp)
$local=$local.Replace('E:/AIProject/FPGAVibecoding/artifacts/board-debug-20261005/acceleration/jtag/cnn-v6-tb-compile-smoke-002/source-snapshot',$inc).Replace('cnn_pipeline_v6','cnn_pipeline_v10')
$local=$local.Replace('cnn_pipeline_v10_tb',$tbStem)
$local|Set-Content (Join-Path $build 'csim.mk') -Encoding ascii;Copy-Item $rules (Join-Path $build 'Makefile.rules')
$make=Join-Path $VitisRoot 'tps\mingw\10.0.0\win64.o\nt\bin\mingw32-make.exe';$clang=Join-Path $VitisRoot 'win64\tools\clang-16\bin';$bash=Join-Path $VitisRoot 'tps\win64\msys2_bash\usr\bin\bash.exe'
foreach($p in @($make,(Join-Path $clang 'clang++.exe'),$bash)){if(!(Test-Path $p)){throw "missing tool $p"}}
. (Join-Path $PSScriptRoot 'task_tool_error_mode.ps1');. (Join-Path $PSScriptRoot 'task_tool_memory.ps1')
$launch=Assert-FzTaskMemoryForLaunch;$old=$env:PATH;$mode=Enable-FzTaskToolErrorMode;$started=(Get-Date).ToUniversalTime();$buildExit=999;$results=@()
try{
 $runtime=@((Split-Path -Parent $make),(Join-Path $VitisRoot 'bin'),(Join-Path $VitisRoot 'tps\win64'),(Join-Path $VitisRoot 'lib\win64.o'),(Join-Path $VitisRoot 'tps\mingw\6.2.0\win64.o\nt\bin'),(Join-Path $VitisRoot 'tps\mingw\6.2.0\win64.o\nt\libexec\gcc\x86_64-w64-mingw32\6.2.0'),$clang)
 $env:PATH=(($runtime+@($old))-join';');Push-Location $build
 try{
  $makeUnix=Unix $make;$expanded=@(& $bash -c "export PATH=/usr/bin:`$PATH; '$makeUnix' -n VERBOSE=1 -f csim.mk all" 2>&1|%{[string]$_});if($LASTEXITCODE-ne0){throw 'make dry-run failed'}
  $prefix=Unix(Join-Path $clang 'clang++');$commands=@($expanded|?{$_.TrimStart().StartsWith($prefix)}|%{(($_-replace'\s*;\s*\\\s*$','').Trim())});if($commands.Count-ne3){throw "expected 3 generated clang commands, got $($commands.Count)"}
  $compileCommands=@($commands|?{$_-match'\s-c\s'});$linkCommands=@($commands|?{$_-notmatch'\s-c\s'})
  if($compileCommands.Count-ne2-or$linkCommands.Count-ne1){throw 'generated recipe must contain two compile commands and one link command'}
  $kernelCommands=@($compileCommands|?{$_.Contains($cpp)});if($kernelCommands.Count-ne1){throw 'cannot identify frozen kernel compile command'}
  $extraCompileCommands=@();$extraObjects=@();$extraObjectSet=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  foreach($nativeName in $additionalNativeNames){
   $nativePath=Unix(Join-Path $snap $nativeName);$objectName='obj/'+[IO.Path]::GetFileNameWithoutExtension($nativeName)+'.o'
   if(!$extraObjectSet.Add($objectName)-or$objectName-in@('obj/cnn_pipeline_v10.o',"obj/$tbStem.o")){throw "native source object-name collision for $nativeName"}
   $extra=$kernelCommands[0].Replace($cpp,$nativePath);if($extra-eq$kernelCommands[0]){throw "cannot bind snapshot native source $nativeName"}
   $outputMatch=[regex]::Match($extra,'(?<!\S)-o\s+(?:"[^"]+"|\S+)');if(!$outputMatch.Success){throw "cannot identify object output for $nativeName"}
   $extra=$extra.Remove($outputMatch.Index,$outputMatch.Length).Insert($outputMatch.Index,"-o $objectName")
   $extraCompileCommands+=$extra;$extraObjects+=$objectName
  }
  $linkCommand=$linkCommands[0]
  if($extraObjects.Count){$linkOutput=[regex]::Match($linkCommand,'(?<!\S)-o\s+(?:"[^"]+"|\S+)');if(!$linkOutput.Success){throw 'cannot identify generated link output'};$linkCommand=$linkCommand.Insert($linkOutput.Index,(($extraObjects-join' ')+' '))}
  $executionCommands=@($compileCommands)+@($extraCompileCommands)+@($linkCommand)
  if($CompileO2){for($i=0;$i-lt$executionCommands.Count-1;$i++){$executionCommands[$i]+=' -O2'}}
  $executionCommands|Set-Content (Join-Path $ev 'executed-expanded-commands.txt') -Encoding ascii
  New-Item -ItemType Directory -Path (Join-Path $build 'obj') -Force|Out-Null;$buildExit=0
  for($i=0;$i-lt$executionCommands.Count;$i++){$rsp=Join-Path $ev "build-$i.rsp";$executionCommands[$i].Substring($prefix.Length).Trim()|Set-Content $rsp -Encoding ascii;$r=Run-Owned (Join-Path $clang 'clang++.exe') @("@$rsp") (Join-Path $ev "build-$i.log") 600;if($r.exit-ne0-or$r.memory_stop-or$r.timeout_stop){$buildExit=97;break}}
  if($buildExit-eq0){$exe=Join-Path $build 'csim.exe';foreach($case in $cases){$name=Safe([string]$case.name);$args=@($case.args|%{[string]$_});$timeout=if($case.timeout_seconds){[int]$case.timeout_seconds}else{1800};$r=Run-Owned $exe $args (Join-Path $logs "$name.log") $timeout;$expected=if($null-ne$case.expected_exit){[int]$case.expected_exit}else{0};$results+=[ordered]@{name=$name;args=$args;expected_exit=$expected;actual_exit=$r.exit;pass=($r.exit-eq$expected-and!$r.memory_stop-and!$r.timeout_stop);wall_seconds=$r.wall;peak_working_set_bytes=$r.peak;log_sha256=Sha(Join-Path $logs "$name.log")};if(!$results[-1].pass){break}}}
 }finally{Pop-Location}
}finally{$env:PATH=$old;Restore-FzTaskToolErrorMode -PreviousMode $mode;$finished=(Get-Date).ToUniversalTime()}
$receipt=[ordered]@{
 schema='cnn-pipeline-v10-native-csim-receipt-v2';started_utc=$started.ToString('o');finished_utc=$finished.ToString('o')
 source_sha256=$actual;test_manifest_sha256=$testManifestSha;testbench=$tbName;clock='native'
 compiled_from_source_snapshot=$true;snapshot_include_closure_verified=$true
 additional_source_manifest=$additionalInventory;additional_native_sources=$additionalNativeNames
 dsp_source_manifest_contract=$dspRoleContract
 source_manifest_roles=[ordered]@{header='snapshot/include';native_header='snapshot/include';native_source='snapshot/compile/link';metadata='snapshot/hash';rtl='snapshot/hash'}
 contract_expectations=[ordered]@{abi='0x000A0005';software='sw10.5';arena_words=[ordered]@{profile0=36864;profile1=20480;profile2=69632;profile3=69632};residual_ddr_words=4096;stage_transport='bram_fifo';stage_fifo_depths=[ordered]@{q3_a=4096;q3_b=4096;q7_a=8192;q7_b=8192;expanded_a=2048;expanded_b=2048};activation_broker_clients=2;scale_response_bits=16;row_ready=[ordered]@{bits=11;block_bits=5;row_bits=6;depth=64};pw2_columns_depth=1024;axi_masters=6;burst_length=32;command_depth=2;repeat_profile_switch_gate=$true}
 compile_optimization_delta=if($CompileO2){'O2 compile only'}else{'none'};launch_memory=$launch;build_exit=$buildExit;cases=$results
 pass=($buildExit-eq0-and$results.Count-eq$cases.Count-and@($results|?{!$_.pass}).Count-eq0)
}
$receipt|ConvertTo-Json -Depth 8|Set-Content (Join-Path $ev 'receipt.json') -Encoding utf8;if(!$receipt.pass){exit 97}


