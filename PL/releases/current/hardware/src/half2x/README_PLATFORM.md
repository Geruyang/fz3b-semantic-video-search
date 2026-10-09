# Half-width 2x-clock platform candidate

This directory contains the isolated A0004 half-width PW experiment.  The
platform candidate keeps the AXI/control fabric at 200 MHz and drives the
verified half-width PW leaf from one related 400 MHz output of the same MMCM.

The frozen A0004 175.371 MHz bitstream and the independent full-width strict
200 MHz experiment are not modified.  No file in this directory authorizes a
board download; a matching PS PL0=100 MHz readiness receipt is required first.

