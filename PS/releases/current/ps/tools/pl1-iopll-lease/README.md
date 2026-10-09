# PL1 IOPLL lease candidate

This candidate holds a Linux CCF reference on IOPLL while an external,
reviewed JTAG transaction uses the otherwise disabled PL1 clock branch.  It
does not write any clock register.  Entry is restricted to the proven A0004
rollback state:

- PL0 `0x01010802` (RPLL / 8 / 1, enabled)
- PL1, PL2 and PL3 `0x00052000` (reset-default, disabled)

The transaction may temporarily change PL1 to `0x01010F00` (IOPLL / 15 / 1,
enabled), but `FINALIZE` and FD release remain blocked until all four branch
registers, IOPLL, RPLL and DDR protection state are restored exactly.  The
required rollback order is: program the original PL0 A0004 bit, restore PL1
to `0x00052000`, verify all protected raw values, then finalize and drop the
IOPLL lease.

This directory is an offline candidate.  It does not prove target kernel
compilation or any real PL1 clock write.
