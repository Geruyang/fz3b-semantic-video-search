# V10.5 A0005 signed40 candidate driver

This is an isolated candidate derived from the proven A0004 direct-WC
transport. It does not modify or replace the A0004 driver. Its module, device,
and compatible are `cnn_ddr_v10_signed40_candidate`,
`/dev/network10_v10_signed40`, and
`fz3b,cnn-ddr-v10-signed40-candidate`.

The UAPI wire version remains 10. The live accelerator identity must be
CORE_ABI `0x000a0005` and GUARD_CAPS `0x00000fff`. Capability bit `0x800`
means `PW2_SIGNED40_APPROVED_PARAMS_V1`; an A0004 runtime cannot accept it.
The eight parameter identity words are the big-endian words of combined
manifest SHA256
`4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690`.

The kernel module checks the live guard identity and combined words. The
Python signed40 admission transport freezes each parameter upload as immutable
bytes, hashes the exact uploaded bytes, admits only the four raw SHA256 values
frozen by the signed40 range proof, and invalidates approval on every writable,
mapped, copy-destination, cached-upload, and free path. A mapped parameter
handle cannot be re-approved until it is freed.

Arena/profile and transfer-v2 behavior remains the A0004 internal-FIFO
contract: 36,864/20,480/69,632/69,632 128-bit words for profiles 0/1/2/3,
direct WC as the default activation path, and cached DMA capability only when
a safe provider with synchronous termination is actually acquired. The
candidate overlay has no guessed `dmas` or `dma-names`.

The saved overlay stays `status = "disabled"`. A deployable DTBO is rendered
into a separate signed deployment package and may become `okay` only after a
matching routed A0005 bitstream, guard identity, target-built KO, full exact
and canary gates, and recovery assets are bound. Existing A0004 artifacts stay
historical and distinct.
