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
