"""Create the compact native/RTL TB index for frozen v7 stripe fixtures."""

import argparse
import hashlib
import json
from pathlib import Path

import cnn_shared_v7_contract as contract
import cnn_shared_v7_fixtures as fixtures


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file(root, path):
    path = Path(path)
    absolute = root / path
    return {"path": path.as_posix(), "bytes": absolute.stat().st_size,
            "sha256": sha256(absolute)}


def build(root, fixture_dir, output_dir):
    root, fixture_dir, output_dir = Path(root), Path(fixture_dir), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("refusing to overwrite %s" % output_dir)
    fixture_manifest_path = fixture_dir / "manifest.json"
    fixture_manifest = json.loads(fixture_manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True)
    cases = []
    # Put the requested p2 top-boundary case first for the first native smoke.
    for profile in (2, 0, 1):
        profile_data = fixture_manifest["profiles"][str(profile)]
        profile_dir = fixture_dir / ("profile%d" % profile)
        by_start = {int(item["start_row"]): item
                    for item in profile_data["selected_stripes"]}
        for start in fixtures.selected_stripe_starts(int(profile_data["width"])):
            item = by_start[start]
            stripe_dir = profile_dir / ("stripe-%02d" % start)
            descriptor = contract.validate_descriptor(
                fixtures.native_tb_descriptor(profile, start))
            expected = {}
            for name in ("q3_scratch", "q7_dst", "pw1", "gelu", "pw2",
                         "scale", "residual", "output"):
                expected[name] = _file(root, (stripe_dir / item["files"][name]["path"])
                                      .relative_to(root))
            cases.append({
                "case_id": "p%d-block00-image00-stripe%02d" % (profile, start),
                "profile": profile, "block_index": 0, "sample_id": "image-00",
                "descriptor": descriptor,
                "q3_global_row_origin": int(item["q3_start_row"]),
                "q3_global_row_end": int(item["q3_end_row"]),
                "params": _file(root, (profile_dir / "params-block00.bin").relative_to(root)),
                "source_full_hcw": _file(root, (profile_dir / "source-full-hcw.i16le")
                                         .relative_to(root)),
                "expected": expected,
                "canary": {
                    "require_unchanged_outside_dst_target_rows": True,
                    "require_unchanged_after_actual_scratch_extent": True,
                    "require_all_write_responses_before_completion": True,
                },
            })
    sequences = []
    for profile in (0, 1, 2):
        profile_data = fixture_manifest["profiles"][str(profile)]
        width = int(profile_data["width"])
        profile_dir = fixture_dir / ("profile%d" % profile)
        sequences.append({
            "case_id": "p%d-block00-image00-full-stripe-sequence" % profile,
            "profile": profile, "block_index": 0, "sample_id": "image-00",
            "descriptors": [contract.validate_descriptor(
                fixtures.native_tb_descriptor(profile, start))
                for start in range(0, width, 4)],
            "params": _file(root, (profile_dir / "params-block00.bin").relative_to(root)),
            "source_full_hcw": _file(root, (profile_dir / "source-full-hcw.i16le")
                                     .relative_to(root)),
            "expected_full_hcw": _file(root, (profile_dir / "expected-block00-hcw.i16le")
                                       .relative_to(root)),
            "initial_dst": "canary; only the submitted four rows may change per call",
            "scratch_reuse": "same private 80KiB capacity; actual extent follows each descriptor",
        })
    manifest = {
        "schema_version": 1,
        "status": "CNN_SHARED_V7_NATIVE_TB_FIXTURES_READY",
        "pl_execution": False,
        "source_fixture_manifest": _file(root, fixture_manifest_path.relative_to(root)),
        "first_required_case": cases[0]["case_id"],
        "layout": {
            "word_bits": 128, "activation": "signed i16 HCW little-endian",
            "scratch": "q3 HCW local rows with q3_global_row_origin",
            "offsets": "nonzero 128-bit word offsets with guard gaps",
        },
        "cases": cases,
        "full_block_sequences": sequences,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    receipt = {
        "status": "CNN_SHARED_V7_NATIVE_TB_MANIFEST_COMPLETED",
        "manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
        "manifest_sha256": sha256(manifest_path),
        "stripe_case_count": len(cases),
        "full_block_sequence_count": len(sequences),
        "first_required_case": cases[0]["case_id"],
    }
    receipt_path = output_dir / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    return receipt_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--fixtures", default=(
        "artifacts/board-debug-20261005/acceleration/host/"
        "cnn-shared-v7-stripe-fixtures-001"))
    parser.add_argument("--output", default=(
        "artifacts/board-debug-20261005/acceleration/host/"
        "cnn-shared-v7-native-tb-fixtures-001"))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    fixture_dir = Path(args.fixtures)
    output_dir = Path(args.output)
    if not fixture_dir.is_absolute():
        fixture_dir = root / fixture_dir
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    print(build(root, fixture_dir, output_dir))


if __name__ == "__main__":
    main()

