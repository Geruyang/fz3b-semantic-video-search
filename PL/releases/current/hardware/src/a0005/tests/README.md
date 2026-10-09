# Dual-lane storage and DW7 optimization test gate

This directory is verification-only. It does not contain or modify the
candidate implementation. The gate is intended to run once after all three
candidate changes and their adapter are complete.

## Frozen contracts

PW1 merges adjacent logical banks `2p` and `2p+1` into one true-dual-port
physical bank. For the candidate's `BANK_DEPTH`, each old logical bank spans
two rows and therefore has address depth `2*BANK_DEPTH`:

```text
physical_bank = logical_bank >> 1
port          = logical_bank & 1
address       = port * (2 * BANK_DEPTH) + old_address
0 <= old_address < 2 * BANK_DEPTH
```

The resulting physical bank depth is `4*BANK_DEPTH`. The oracle exhausts every
old address for `BANK_DEPTH=64` (128 old entries, two rows) and a
`BANK_DEPTH=1` boundary shape. It rejects bank 16, old address
`2*BANK_DEPTH`, and a zero-depth configuration. Every simultaneous 16-lane
access occupies all eight physical banks and both ports without aliasing.

Normal DW7 tests `source_x = xb + lane + dx` for `dx=-3..3`, widths 16, 32 and
64, every 16-pixel block, and first/interior/last channels. P3 tests
`source_x = 2*(xb+lane)+dx` for all four eight-pixel blocks of its 64-pixel
input. Both modes call the candidate fixed-read helper once for each of the 16
existing physical banks. Invalid x/y padding retains that fixed bank, issues
only a safe address inside the current channel row, and is masked to zero.
Normal then selects 16 values from `bank_values[(lane+dx)&15]`. P3 selects
eight values from `bank_values[(2*lane+dx)&15]`, and each selected value feeds
two multiplier outputs. DW7 does not merge its 16 banks or introduce a port
split.

Signed40 packed4 uses lane-major little-bit order: lane 0 occupies bits 39:0,
then lanes 1, 2 and 3, exported as five little-endian 32-bit words. Unpack must
sign-extend each 40-bit lane. Any input outside `[-2^39,2^39-1]` rejects the
whole transaction and leaves the destination words unchanged.

## Future candidate adapter

The candidate supplies one thin adapter source implementing the declarations
in `candidate_adapter_contract.hpp`. The adapter must call
`pw1_physical_location`, `dw7_fixed_bank_read`,
`dw7_normal_source_bank`, and `dw7_p3_source_bank`; it must not duplicate their
formulas. A source manifest freezes every adapter, candidate implementation
source and header:

```json
{
  "schema": "dual-lane-storage-dw7-opt-source-manifest-v1",
  "files": [
    {"path": "tests/candidate_adapter.cpp", "role": "adapter_source", "sha256": "..."},
    {"path": "candidate/cnn_pipeline_v10.cpp", "role": "implementation_source", "sha256": "..."},
    {"path": "candidate/storage.hpp", "role": "header", "sha256": "..."}
  ]
}
```

The candidate contract copies `contract_requirements.json` exactly and adds a
non-empty `candidate_id`. The runner first validates and snapshots every hash,
then generates independent TSV oracles, compiles only `adapter_source` and
`native_source` files from the snapshot, and runs one native executable.
`implementation_source` is hash-bound and snapshotted but is deliberately not
linked into this small helper gate.

## Coverage matrix

| Candidate change | Normal coverage | Boundary/error coverage | Required observation |
|---|---|---|---|
| PW1 16→8 TDP banks | Banks 0–15, every old address, two logical rows | First/last address, bank 16, address `2*BANK_DEPTH`, depth 0 | Adjacent pairing, exact bank/port/high-address split; all 16 logical lanes cover 8 banks × 2 ports without alias |
| DW7 normal reorder | Widths 16/32/64, all blocks, channels 0/1/63/127, `dx=-3..3` | Left/right and y padding, chunk crossings | 16 unique fixed-bank reads, legal safe address, then exact 16-lane source selection |
| DW7 P3 reorder | Channels 0/1/31/63, blocks 0/8/16/24, `dx=-3..3` | Left/right and y padding | 16 unique fixed-bank reads, then eight source selections each duplicated to two multiplier outputs |
| signed40 packed4 | Zero, min/max, signed32 crossings, bit patterns, 64 deterministic random vectors | Underflow/overflow in each of four lanes | Exact 160 bits, exact sign extension, atomic rejection |

No tests or tools were launched when this gate was authored.
