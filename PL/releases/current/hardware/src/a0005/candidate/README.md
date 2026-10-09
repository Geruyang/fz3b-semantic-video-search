# A0005 dual-lane storage and DW7 candidate

This directory is an isolated source candidate derived from the frozen A0004
half2x fused-ALU design.  It does not replace the product A0004 sources.

The candidate combines three changes before any verification run:

1. PW1 uses eight true-dual-port physical banks for sixteen logical lanes.
2. DW7 performs one fixed read per physical bank and rearranges the values
   after the reads for both normal and P3 operation.
3. Normal-profile PW2 persistent accumulation and its 1024-deep result FIFO
   store four signed-40 lanes in 160 bits.  DSP and post-processing arithmetic
   remain signed-48.  P3 continues to use the PW1 48-bit `AccColumn` path.

Candidate identity is `CORE_ABI=0x000A0005`, software `sw10.5`, and guard caps
`0x00000fff`.  Capability bit `0x00000800` means that the loaded parameter blob
belongs to the signed40-approved set described by
`parameter_compatibility.pw2_signed40_v1` in the combined manifest.  The
hardware source does not scan the full parameter blob per job; immutable blob
identity and generation binding belong to the loader/driver contract.

The frozen A0005 combined parameter manifest SHA-256 is
`4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690`.
Its eight BE32 guard words are `4a32c937 3e783ac5 72a5d337 4b316181
a4d52ae9 a92ec45f 8b13d763 ef028690`.  Platform synthesis and software
admission must bind this identity together with ABI A0005 and caps `0xfff`.

No simulation, HLS, Vivado synthesis, implementation, or board action is
implied by the source files in this directory.
