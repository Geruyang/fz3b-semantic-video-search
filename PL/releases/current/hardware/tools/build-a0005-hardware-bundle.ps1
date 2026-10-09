[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$bundle = Join-Path $workspace 'releases\current\hardware'
if (Test-Path -LiteralPath $bundle) {
    throw "Bundle target already exists: $bundle"
}
New-Item -ItemType Directory -Path $bundle | Out-Null

$records = [Collections.Generic.List[object]]::new()
$mappings = [Collections.Generic.List[object]]::new()

function Copy-BundleFile {
    param(
        [Parameter(Mandatory=$true)][string]$SourceRelative,
        [Parameter(Mandatory=$true)][string]$DestinationRelative,
        [Parameter(Mandatory=$true)][string]$Purpose
    )
    $src = Join-Path $workspace $SourceRelative
    if (!(Test-Path -LiteralPath $src -PathType Leaf)) { throw "Missing source file: $SourceRelative" }
    $dst = Join-Path $bundle $DestinationRelative
    $parent = Split-Path -Parent $dst
    if (!(Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item -LiteralPath $src -Destination $dst
    $records.Add([ordered]@{
        path = ($DestinationRelative -replace '\\','/')
        source_path = ($SourceRelative -replace '\\','/')
        bytes = (Get-Item -LiteralPath $dst).Length
        sha256 = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()
        purpose = $Purpose
    })
}

function Copy-BundleTree {
    param(
        [Parameter(Mandatory=$true)][string]$SourceRelative,
        [Parameter(Mandatory=$true)][string]$DestinationRelative,
        [Parameter(Mandatory=$true)][string]$Purpose,
        [string[]]$ExcludeRelativeRegex = @()
    )
    $srcRoot = Join-Path $workspace $SourceRelative
    if (!(Test-Path -LiteralPath $srcRoot -PathType Container)) { throw "Missing source directory: $SourceRelative" }
    $copied = 0
    foreach ($file in Get-ChildItem -LiteralPath $srcRoot -Recurse -File | Sort-Object FullName) {
        $rel = $file.FullName.Substring($srcRoot.Length).TrimStart('\') -replace '\\','/'
        $skip = $false
        foreach ($pattern in $ExcludeRelativeRegex) {
            if ($rel -match $pattern) { $skip = $true; break }
        }
        if ($skip) { continue }
        Copy-BundleFile -SourceRelative (Join-Path $SourceRelative ($rel -replace '/','\')) `
            -DestinationRelative (Join-Path $DestinationRelative ($rel -replace '/','\')) -Purpose $Purpose
        $copied++
    }
    $mappings.Add([ordered]@{
        source_path = ($SourceRelative -replace '\\','/')
        bundle_path = ($DestinationRelative -replace '\\','/')
        file_count = $copied
        exclusions = @($ExcludeRelativeRegex)
        purpose = $Purpose
    })
}

function Add-GeneratedText {
    param(
        [Parameter(Mandatory=$true)][string]$DestinationRelative,
        [Parameter(Mandatory=$true)][string]$Content,
        [Parameter(Mandatory=$true)][string]$Purpose
    )
    $dst = Join-Path $bundle $DestinationRelative
    $parent = Split-Path -Parent $dst
    if (!(Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $Content | Set-Content -LiteralPath $dst -Encoding utf8NoBOM
    $records.Add([ordered]@{
        path = ($DestinationRelative -replace '\\','/')
        source_path = "generated:$($DestinationRelative -replace '\\','/')"
        bytes = (Get-Item -LiteralPath $dst).Length
        sha256 = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()
        purpose = $Purpose
    })
}

$cacheExclusions = @('(^|/)private-user(/|$)','(^|/)__pycache__(/|$)','\.pyc$')

# Current source and every source component used by the A0005 transformation.
Copy-BundleTree 'desktop_vlm\hardware\acceleration\experiments\dual_lane_storage_dw7_opt' 'src\a0005' 'A0005 C++ candidate, frozen source pack, constraints, validation and implementation runners' $cacheExclusions
Copy-BundleTree 'desktop_vlm\hardware\acceleration\experiments\pw_half2x' 'src\half2x' 'Complete half-width dual-clock component required by the A0005 transform' $cacheExclusions
Copy-BundleTree 'desktop_vlm\hardware\acceleration\experiments\pw_half2x_fused_alu' 'src\fused-alu' 'Complete fused DSP component and transformation scripts required by A0005' $cacheExclusions

# Official programming/clock transactions and explicit factory recovery entry points.
foreach ($name in @(
    'run_program_cnn_v10_a0005_noila.ps1','program_cnn_v10_a0005_noila.tcl',
    'run_set_pl1_100mhz_for_a0005.ps1','set_pl1_100mhz_for_a0005.tcl',
    'run_restore_factory_cnn_v10.ps1','restore_factory_cnn_v10.tcl'
)) {
    Copy-BundleFile (Join-Path 'desktop_vlm\hardware\acceleration' $name) (Join-Path 'deploy\original-runners' $name) 'Official Vivado/XSDB deployment or recovery runner'
}

# Frozen exact fixtures and functional evidence.
Copy-BundleTree 'artifacts\board-debug-20261007\acceleration\host\cnn-v10.4-a0004-bram-stage-rtl-fixtures-001' 'fixtures\full-rtl' 'Exact A0005 full-RTL input/parameter/expected-output fixtures' @()
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\simulation\cnn-v10-pw-half2x-fused-alu-unisim-002' 'evidence\unisim-fused-leaf' 'Real DSP48E2 fused-leaf cycle miter evidence' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\simulation\cnn-v10.5-a0005-fused-rtl-p3-002' 'evidence\rtl-p3' 'P3 exact-cycle comparison evidence' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\simulation\cnn-v10.5-a0005-fused-rtl-full-001' 'evidence\rtl-full' 'Final nine-case A0005 RTL matrix and receipts' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\hls\cnn-v10.5-a0005-storage-hls-002' 'evidence\hls-cpp' 'Vitis HLS C++ synthesis reports and receipt' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\host\cnn-v10.5-dual-lane-storage-dw7-native-008' 'evidence\native-local' 'Local native storage/DW7 verification' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\host\cnn-v10.5-a0005-whole-native-004' 'evidence\native-whole' 'Whole-kernel native verification' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\host\network10-v10.5-pw2-signed40-proof-003' 'evidence\signed40-proof' 'Per-profile signed40 parameter range proof' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\host\network10-v10.5-pw2-signed40-combined-001' 'evidence\combined-identity' 'A0005 combined parameter identity and guard words' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\host\network10-v10.5-pw2-signed40-integration-001' 'evidence\software-integration' 'Hardware/software contract join receipts' $cacheExclusions

# Generated RTL/IP. Private Tcl application stores are reproducible tool caches and are omitted.
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-fused-hls-ooc-cache-003' 'generated\hls-ip-v1.3' 'Canonical A0005 generated RTL, packaged IP, OOC DCP and reports' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-generated-rtl-structure-002' 'evidence\generated-rtl-structure' 'Generated RTL structural audit' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-hls-ip-apready-patched-002' 'generated\apready-patched' 'Reproducible ap_ready generated-RTL patch stage' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-hls-ip-fused-transform-002' 'generated\fused-transform' 'Reproducible fused DSP generated-RTL transform stage' $cacheExclusions

# Full platform synthesis: retain the checkpoint, exact BD/source snapshot and reports, but not a duplicate HLS-IP tree.
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-fastbufgdiv-platform-synth-001' 'implementation\post-synth' 'Full-platform post-synth checkpoint, BD, constraints, source snapshot and reports' @(
    '(^|/)hls-ip(/|$)','(^|/)private-user(/|$)','(^|/)memory-pressure\.jsonl$'
)

# Adopted placement only: retain the actual route input DCP, applied RQS and reports. Superseded post-opt/post-place DCPs are intentionally omitted.
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-fastbufgdiv-fresh-place-preg-002' 'implementation\adopted-place' 'Adopted PREG-protected post-physopt route input, applied RQS, constraints and reports' @(
    '(^|/)private-user(/|$)','(^|/)half2x-fresh-rqs-post-opt\.dcp$','(^|/)half2x-fresh-rqs-post-place\.dcp$'
)

# Final implementation and bit products.
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-fastbufgdiv-preg-route-bit-002' 'implementation\routed' 'Final routed DCP, route scripts and signoff reports' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\jtag\cnn-v10.5-a0005-fastbufgdiv-preg-finalize-bit-002' 'implementation\final' 'Final bit/bin, canonical platform receipt and signoff reports' $cacheExclusions

# Deployable payloads include the A0005 driver/DTBO, all parameter fixtures, and exact factory recovery bin/KO.
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\host\network10-v10.5-a0005-validation-payload-002' 'deployment\validation-payload' 'Four-profile exact board validation payload' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261008\acceleration\host\network10-v10.5-a0005-deployment-final-001' 'deployment\a0005-final' 'Self-contained A0005 deployment plus exact factory recovery assets' $cacheExclusions

# Board transactions and final board evidence. The superseded interim A0004 restore evidence is not bundled.
Copy-BundleTree 'artifacts\board-debug-20261009\acceleration\jtag\cnn-v10.5-a0005-pl1-100mhz-held-001' 'evidence\board\pl1-held' 'Qualified persistent PL1 100 MHz transaction receipt' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261009\acceleration\jtag\cnn-v10.5-a0005-program-retain-002' 'evidence\board\program-retain' 'Final retained A0005 official PL-only program receipt' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261009\acceleration\network\network10-v10.5-a0005-board-exact-003' 'evidence\board\exact' 'Four-profile bit-exact board validation' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261009\acceleration\network\network10-v10.5-a0005-fullmodel-001' 'evidence\board\fullmodel' 'Final quality and FPS board evidence' $cacheExclusions
Copy-BundleTree 'artifacts\board-debug-20261009\acceleration\network\network10-v10.5-a0005-retain-redeploy-001' 'evidence\board\retained-postflight' 'Final retained A0005 board state and strict identity postflight' $cacheExclusions

# Human-readable final records and the pre-bundle inventory.
Copy-BundleFile 'docs\analysis\2026-10-08-v10.5-storage-dw7-results.md' 'docs\results.md' 'Final engineering results'
Copy-BundleFile 'docs\plans\2026-10-08-dual-lane-storage-dw7-implementation.md' 'docs\implementation.md' 'Implementation and validation contract'
Copy-BundleFile 'docs\handoffs\2026-10-08-v10.5-storage-dw7-validation-continuation.md' 'docs\handoff.md' 'Final continuation/state handoff'
Copy-BundleTree 'artifacts\board-debug-20261009\retention\cnn-v10.5-a0005-local-retention-inventory-001' 'docs\prebundle-inventory' 'Pre-bundle retention inventory and cleanup candidates' @()

# Preserve the exact bundle construction recipe itself.
Copy-BundleFile 'releases\current\build-a0005-hardware-bundle.ps1' 'tools\build-a0005-hardware-bundle.ps1' 'Exact bundle construction recipe'

Add-GeneratedText 'README.md' @'
# Current A0005 hardware release

This is the self-contained retained hardware release for the deployed A0005 candidate. It contains the current C++ and generated RTL, packaged IP, constraints and runners, exact fixtures, the adopted implementation input, final routed DCP, bit/bin, board payloads, factory recovery assets, and final verification evidence.

The bundle is a copy. Creating it did not move or delete source paths and did not touch the board. The board must remain on A0005 until the user explicitly requests restoration. The superseded 175 MHz A0004 bit is deliberately not retained; do not run the former restore-original175 flow. The only retained fallback is the factory recovery version, and it may be used only after a new explicit user request.

Key identities:

- ABI `0x000A0005`, caps `0x00000FFF`
- combined parameter manifest `4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690`
- routed DCP `fea3a0d075e243d22fa874799f93883648ec9def2797b61ff29c47dbf86b61e7`
- bit `a7950894715edd4e0f535b094e4a7866a220bd44f7158d153bb8e927d07bdebc`
- bin `504eb307f338c9151b37023342a8138189447cba47379c9f05506b2538a31c95`

Use `tools/verify-bundle.ps1` before deploying, rebuilding, or deleting the original paths. `manifest.json` records the original path for every copied file. `tools/materialize-original-layout.ps1` is dry-run by default and can recreate those paths after cleanup.

See `REBUILD.md` for the source-to-product flow and the exact retained evidence boundaries.
'@ 'Bundle overview and immutable identities'

Add-GeneratedText 'REBUILD.md' @'
# Rebuild and deployment notes

## Verify first

Run:

```powershell
& .\tools\verify-bundle.ps1
```

The verification checks every payload file against `manifest.json`, including fixtures, generated RTL/IP, checkpoints, bit/bin and recovery assets.

## Restore the original workspace layout

The validation and implementation runners were frozen with workspace-relative input paths. After historical directories are cleaned, preview restoration with:

```powershell
& .\tools\materialize-original-layout.ps1 -WorkspaceRoot E:\AIProject\FPGAVibecoding
```

Apply only when those paths need to be reconstructed:

```powershell
& .\tools\materialize-original-layout.ps1 -WorkspaceRoot E:\AIProject\FPGAVibecoding -Apply
```

The tool refuses to overwrite existing files unless `-Force` is explicitly supplied. Generated bundle documentation is not materialized.

## Source to RTL/IP

The frozen A0005 source pack and HLS/native runners are under `src/a0005`. The complete transformation dependencies are retained under `src/half2x` and `src/fused-alu`. Exact full-RTL fixtures are under `fixtures/full-rtl`.

The canonical packaged IP and generated RTL are under `generated/hls-ip-v1.3`. The ap_ready and fused-leaf transformation stages are retained separately so the generated result remains auditable. Private Tcl application stores and Python caches are deliberately omitted because they are tool caches, not design inputs.

## Platform synthesis and implementation

`implementation/post-synth` contains the full-platform post-synth DCP, exact BD Tcl, clock constraints, guard sources and reports. `implementation/adopted-place` contains the exact PREG-protected post-physopt DCP used as the route input, the actually generated/applied RQS file and its reports. Superseded post-opt and post-place DCPs are omitted.

`implementation/routed/a0005-post-route.dcp` is the final routed checkpoint. `implementation/final` contains bit/bin, canonical full-platform receipt and final timing/DRC/route reports. No old exact-location DCP is required by the retained flow.

## Validation and deployment

`evidence/rtl-full` is the final nine-case RTL matrix. `evidence/unisim-fused-leaf` is the real DSP48E2 cycle miter. Board exactness and FPS evidence are under `evidence/board`.

`deployment/a0005-final` contains the A0005 bit, signed40 candidate driver, DTBO and strict deployment manifest. Its `recovery` directory contains the exact factory bin and factory driver KO. The old 175 MHz A0004 bit is not part of this release. Do not use the historical restore-original175 sequence. Factory restoration is prohibited until the user explicitly asks for it.

The original official Vivado/XSDB scripts are retained under `deploy/original-runners`. Materialize the original layout before using scripts that intentionally bind workspace-relative SHA identities.
'@ 'Self-contained rebuild, verification and deployment instructions'

Add-GeneratedText 'CLEANUP.md' @'
# Cleanup boundary after bundle verification

Run `tools/verify-bundle.ps1` and require `pass: true` before removing any original path.

The bundle contains byte-for-byte copies of every retained source, fixture, generated IP/RTL stage, adopted implementation input, final product and final verification record. Therefore none of the copied historical source/artifact paths must remain at their original locations for data retention. Existing workspace-relative runners can be restored later with `tools/materialize-original-layout.ps1`.

After verification, the root cleanup owner may remove:

1. every original source/artifact path represented by `manifest.json.files[].source_path` except generated entries;
2. the 431 temporary/historical candidate directories listed in `docs/prebundle-inventory/inventory.json`;
3. temporary Vivado/Vitis/xsim `w/` projects, including historical failed candidates;
4. the external bundle-construction script `releases/current/build-a0005-hardware-bundle.ps1`, because an exact copy is inside `tools/`.

The following must remain:

- `releases/current/hardware/` itself;
- the board-side retained A0005 configuration and its PL1 clock ownership until the user explicitly requests a change;
- the factory recovery copy on the SD Data partition. The same factory bin/KO also exist under `deployment/a0005-final/recovery/`.

The old 175 MHz A0004 bit is intentionally outside the retention set and must not be restored as an intermediate default. The allowed steady states are the current A0005 release and, only on explicit user instruction, the factory recovery version.

The persistent official `hw_server` process is not a build artifact and must not be terminated as part of directory cleanup. Recheck that no Vivado, Vitis HLS or xsim process has a file open in a deletion candidate immediately before deletion.

`releases/factory/` and any project material outside the manifest/prebundle inventory are outside this cleanup claim. Delete those only after a separate identity comparison or explicit decision by the root cleanup owner.
'@ 'Exact post-verification cleanup boundary and original-path disposition'

Add-GeneratedText 'tools\verify-bundle.ps1' @'
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifestPath=Join-Path $root 'manifest.json'
$manifest=Get-Content -Raw -LiteralPath $manifestPath|ConvertFrom-Json
$failures=[Collections.Generic.List[string]]::new()
foreach($entry in $manifest.files){
    $path=Join-Path $root ([string]$entry.path -replace '/','\')
    if(!(Test-Path -LiteralPath $path -PathType Leaf)){$failures.Add("missing:$($entry.path)");continue}
    $item=Get-Item -LiteralPath $path
    if($item.Length-ne[long]$entry.bytes){$failures.Add("bytes:$($entry.path)");continue}
    $sha=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if($sha-ne[string]$entry.sha256){$failures.Add("sha256:$($entry.path)")}
}
$productPaths=[ordered]@{
    routed_dcp_sha256='implementation/routed/a0005-post-route.dcp'
    bit_sha256='implementation/final/a0005-post-route.bit'
    bin_sha256='implementation/final/a0005-post-route.bin'
    factory_bin_sha256='deployment/a0005-final/recovery/factory-restore-native.bin'
    factory_ko_sha256='deployment/a0005-final/recovery/fpgadrv.ko'
}
foreach($key in $productPaths.Keys){
    $path=Join-Path $root ($productPaths[$key]-replace'/','\')
    if(!(Test-Path -LiteralPath $path -PathType Leaf)){$failures.Add("product-missing:$key");continue}
    $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if($actual-ne[string]$manifest.products.$key){$failures.Add("product-sha256:$key")}
}
$known=@($manifest.files|ForEach-Object{[string]$_.path})
$extra=@(Get-ChildItem -LiteralPath $root -Recurse -File|ForEach-Object{$_.FullName.Substring($root.Length+1)-replace '\\','/'}|Where-Object{$_-notin$known-and$_-notin@('manifest.json','SHA256SUMS.txt')})
if($extra.Count){$failures.Add("unexpected-files:$($extra-join',')")}
$result=[ordered]@{schema=$manifest.schema;pass=($failures.Count-eq0);checked=@($manifest.files).Count;failures=@($failures);manifest_sha256=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()}
$result|ConvertTo-Json -Depth 5
if($failures.Count){exit 1}
'@ 'Offline byte-for-byte bundle verifier'

Add-GeneratedText 'tools\materialize-original-layout.ps1' @'
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$WorkspaceRoot,
    [switch]$Apply,
    [switch]$Force
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$bundle=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workspace=[IO.Path]::GetFullPath($WorkspaceRoot)
if(!(Test-Path -LiteralPath $workspace -PathType Container)){throw "WorkspaceRoot not found: $workspace"}
$manifest=Get-Content -Raw -LiteralPath (Join-Path $bundle 'manifest.json')|ConvertFrom-Json
$planned=0;$copied=0;$existing=0
foreach($entry in $manifest.files){
    $sourcePath=[string]$entry.source_path
    if($sourcePath.StartsWith('generated:',[StringComparison]::Ordinal)){continue}
    $src=Join-Path $bundle ([string]$entry.path -replace '/','\')
    $dst=[IO.Path]::GetFullPath((Join-Path $workspace ($sourcePath-replace'/','\')))
    if(!$dst.StartsWith($workspace+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw "Refusing path outside workspace: $dst"}
    $planned++
    if(Test-Path -LiteralPath $dst){
        $existing++
        $sha=(Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()
        if($sha-eq[string]$entry.sha256){continue}
        if(!$Force){throw "Existing file differs; use -Force only after review: $dst"}
    }
    if($Apply){
        $parent=Split-Path -Parent $dst
        if(!(Test-Path -LiteralPath $parent)){New-Item -ItemType Directory -Path $parent -Force|Out-Null}
        Copy-Item -LiteralPath $src -Destination $dst -Force:$Force
        $copied++
    }
}
[ordered]@{apply=[bool]$Apply;force=[bool]$Force;planned=$planned;already_present=$existing;copied=$copied}|ConvertTo-Json -Compress
'@ 'Dry-run-first original path materializer for retained files'

$manifest = [ordered]@{
    schema = 'cnn-v10.5-a0005-hardware-release-v1'
    status = 'SELF_CONTAINED_COPY_VERIFIED_NO_DELETE'
    generated_utc = [DateTime]::UtcNow.ToString('o')
    identity = [ordered]@{
        core_id = '0x465A5641'
        core_abi = '0x000A0005'
        guard_caps = '0x00000FFF'
        combined_parameter_manifest_sha256 = '4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690'
        candidate_source_manifest_sha256 = 'f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593'
    }
    products = [ordered]@{
        routed_dcp_sha256 = 'fea3a0d075e243d22fa874799f93883648ec9def2797b61ff29c47dbf86b61e7'
        bit_sha256 = 'a7950894715edd4e0f535b094e4a7866a220bd44f7158d153bb8e927d07bdebc'
        bin_sha256 = '504eb307f338c9151b37023342a8138189447cba47379c9f05506b2538a31c95'
        factory_bin_sha256 = '59e1a6176194eccc05603738ba3c2e71ea25c3c09cdf9dce47ed1ad1ddf5fc2e'
        factory_ko_sha256 = 'a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f'
    }
    mappings = @($mappings)
    files = @($records | Sort-Object path)
    excluded_reproducible_or_superseded_data = @(
        'Vivado/Vitis private-user Tcl application caches',
        'superseded post-opt and post-place DCPs; adopted post-physopt route input is retained',
        'duplicate HLS-IP copy under platform synthesis; canonical generated/hls-ip-v1.3 is retained',
        'interim A0004 restore receipt created before the user requested A0005 retention',
        'temporary w/ projects and historical candidates'
    )
    safety = [ordered]@{
        board_modified = $false
        source_paths_deleted_or_moved = $false
        restore_requires_explicit_user_request = $true
    }
}
$manifestPath = Join-Path $bundle 'manifest.json'
$manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $manifestPath -Encoding utf8NoBOM

$sumPath = Join-Path $bundle 'SHA256SUMS.txt'
$records | Sort-Object path | ForEach-Object { "$($_.sha256)  $($_.path)" } | Set-Content -LiteralPath $sumPath -Encoding ascii

Write-Output ([ordered]@{
    bundle = $bundle
    files = $records.Count
    bytes = ($records | Measure-Object -Property bytes -Sum).Sum
    manifest_sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    sums_sha256 = (Get-FileHash -LiteralPath $sumPath -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json -Compress)
