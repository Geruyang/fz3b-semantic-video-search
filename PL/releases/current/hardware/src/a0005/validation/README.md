# A0005 unified validation

This directory contains the reproducible validation entry points for the
combined A0005 storage candidate. `prepare_source_pack.ps1` copies every
candidate and unchanged dependency into a private source pack, verifies their
SHA-256 values, and derives the native/HLS runners from the already-qualified
A0004 entries. The derived runners replace only the identity and storage
contract gates needed by this candidate.

The generated `source-pack` directory is validation input and is intentionally
kept separate from the product tree. Evidence is written below
`artifacts/board-debug-20261008/acceleration`.
