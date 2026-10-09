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
