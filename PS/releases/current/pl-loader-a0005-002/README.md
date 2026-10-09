# FZ3B V10.5 PS FPGA loader

This isolated candidate uses the ZynqMP Linux FPGA Manager for full-PL loads.
It accepts only the Bootgen Linux/PCAP word-order A0005 payload and holds the
IOPLL lease FD for the entire A0005 lifetime.  PL1 changes are limited to
`0x00052000 <-> 0x01010f00`; PL0/PL2/PL3, IOPLL, RPLL, CRL PLL status, and DDR
must remain at the frozen values.

The root-only daemon exposes a mode-0600 Unix socket with `status`,
`switch-a0005`, and explicit `switch-factory` commands.  It refuses an active
inference owner and never performs an automatic factory rollback after a
failed A0005 programming attempt.  The service starts after `rc-local.service`
so it can safely remove the factory driver installed by the vendor boot flow.

The factory PCAP payload is an exact 32-bit word swap of the frozen native
factory image.  It remains board-unqualified until the explicit round-trip
test succeeds; it is never used as an automatic fallback.
