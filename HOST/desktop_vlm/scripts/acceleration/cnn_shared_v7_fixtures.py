"""Build v7 stripe fixtures from frozen W16 blobs and image-00 goldens."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

import cnn_shared_v7_contract as contract
import cnn_shared_v7_oracle as oracle


JOINT_SHA = "4d02889c23aa989dab76e4c5c0fd07143ed164a34fbe455901b566abd2767e4b"
P2_SHA = "9fcc4a05e7668c523f0a94d54ed8731c68582e0958f24bc7589c2f702c9f7326"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_stripe_starts(width):
    width = int(width)
    if width < 8 or width % 4:
        raise ValueError("normal v7 width must be a multiple of four")
    return [0, width // 2, width - 4]


def native_tb_descriptor(profile, start_row):
    """Return a nonzero/gapped arena layout for native and RTL testbenches."""
    spec = contract.PROFILE_SPECS[int(profile)]
    tensor_words = spec["channels"] * spec["width"] * spec["width"] // 8
    src_words = 256
    dst_words = src_words + tensor_words + 128
    scratch_words = dst_words + tensor_words + 256
    return {
        "profile": int(profile),
        "param_base_words": 0,
        "params_words": spec["stride_words"],
        "memory_words": scratch_words + 5120 + 128,
        "src_words": src_words,
        "dst_words": dst_words,
        "scratch_words": scratch_words,
        "start_row": int(start_row),
        "row_count": 4,
    }


def canonical_sources(root):
    root = Path(root)
    host = root / "artifacts/board-debug-20261005/acceleration/host"
    joint = host / "network-w16-joint-oracle-001"
    p2 = host / "network0-w16-preflight-001"
    return {
        0: {
            "root": joint, "manifest": joint / "manifest.json",
            "manifest_sha256": JOINT_SHA, "channels": 128, "width": 32,
            "params": joint / "params/profile0/block-00.bin",
            "input_hcw": joint / "image-00/profile0/input-hcw.i16le",
            "expected_block0_chw": joint / "image-00/profile0/block-00-add-chw.i16le",
        },
        1: {
            "root": joint, "manifest": joint / "manifest.json",
            "manifest_sha256": JOINT_SHA, "channels": 256, "width": 16,
            "params": joint / "params/profile1/block-00.bin",
            "input_hcw": joint / "image-00/profile1/input-hcw.i16le",
            "expected_block0_chw": joint / "image-00/profile1/block-00-add-chw.i16le",
        },
        2: {
            "root": p2, "manifest": p2 / "manifest.json",
            "manifest_sha256": P2_SHA, "channels": 64, "width": 64,
            "params": p2 / "params/profile2/block-00.bin",
            "input_hcw": p2 / "image-00/profile2/input-hcw.i16le",
            "expected_block0_chw": p2 / "image-00/profile2/block-00-add-chw.i16le",
        },
    }


def _manifest_entry(record, path):
    manifest = json.loads(record["manifest"].read_text(encoding="utf-8"))
    relative = path.relative_to(record["root"]).as_posix()
    entry = manifest.get("files", {}).get(relative)
    if entry is None:
        # Params are also indexed in profile/params sections, but current frozen
        # manifests include every payload in files.  Reject if that changes.
        raise ValueError("canonical manifest omits %s" % relative)
    return entry


def _verify_record(record):
    if sha256(record["manifest"]) != record["manifest_sha256"]:
        raise ValueError("canonical manifest SHA mismatch")
    for name in ("params", "input_hcw", "expected_block0_chw"):
        path = record[name]
        entry = _manifest_entry(record, path)
        if path.stat().st_size != int(entry["bytes"]) or sha256(path) != entry["sha256"]:
            raise ValueError("canonical %s integrity mismatch" % name)


def _save_array(directory, name, value, dtype, layout):
    array = np.ascontiguousarray(value, dtype=dtype)
    path = directory / name
    path.write_bytes(array.tobytes(order="C"))
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "dtype": dtype,
        "shape": list(array.shape),
        "layout": layout,
    }


def _hcw(value, dtype):
    return np.ascontiguousarray(np.asarray(value, dtype=dtype).transpose(1, 0, 2),
                                dtype=dtype)


def _load_hcw(path, channels, width):
    raw = np.fromfile(str(path), dtype="<i2")
    if raw.size != channels * width * width:
        raise ValueError("canonical HCW input has wrong element count")
    return np.ascontiguousarray(raw.reshape(width, channels, width).transpose(1, 0, 2),
                                dtype="<i2")


def build_fixtures(root, output):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError("refusing to overwrite %s" % output)
    sources = canonical_sources(root)
    output.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "status": "CNN_SHARED_V7_OFFLINE_STRIPE_FIXTURES",
        "pl_execution": False,
        "arithmetic": "legacy W16 signed48/signed80 Q31 ties-even clip[-32767,32767]",
        "stripe_contract": {
            "row_count": 4, "dw3_source_halo": 4, "q3_scratch_halo": 3,
            "residual": "DW3 quantized q3", "tile_pixels": 16,
            "expanded_ddr": False,
        },
        "profiles": {},
    }
    for profile in (0, 1, 2):
        record = sources[profile]
        _verify_record(record)
        channels, width = record["channels"], record["width"]
        directory = output / ("profile%d" % profile)
        directory.mkdir()
        params_path = directory / "params-block00.bin"
        source_path = directory / "source-full-hcw.i16le"
        shutil.copyfile(str(record["params"]), str(params_path))
        shutil.copyfile(str(record["input_hcw"]), str(source_path))
        params = oracle.decode_w16_block(params_path.read_bytes(), profile)
        source = _load_hcw(source_path, channels, width)
        expected = np.fromfile(str(record["expected_block0_chw"]), dtype="<i2").reshape(
            channels, width, width)
        stitched = np.empty_like(expected)
        selected = set(selected_stripe_starts(width))
        stripe_records = []
        for start in range(0, width, 4):
            result = oracle.execute_stripe(source, params, start, 4, tile_pixels=16)
            stitched[:, start:start + 4, :] = result["output"]
            if start not in selected:
                continue
            stripe_dir = directory / ("stripe-%02d" % start)
            stripe_dir.mkdir()
            files = {
                "q3_scratch": _save_array(stripe_dir, "q3-scratch-hcw.i16le",
                                           _hcw(result["q3_scratch"], "<i2"), "<i2", "HCW"),
                "q7_dst": _save_array(stripe_dir, "q7-dst-hcw.i16le",
                                      _hcw(result["dw7"], "<i2"), "<i2", "HCW"),
                "pw1": _save_array(stripe_dir, "pw1-hcw.i16le",
                                   _hcw(result["pw1"], "<i2"), "<i2", "HCW"),
                "gelu": _save_array(stripe_dir, "gelu-hcw.i16le",
                                    _hcw(result["gelu"], "<i2"), "<i2", "HCW"),
                "pw2": _save_array(stripe_dir, "pw2-hcw.i16le",
                                   _hcw(result["pw2"], "<i2"), "<i2", "HCW"),
                "scale": _save_array(stripe_dir, "scale-hcw.i64le",
                                     _hcw(result["scale"], "<i8"), "<i8", "HCW"),
                "residual": _save_array(stripe_dir, "residual-hcw.i64le",
                                        _hcw(result["residual"], "<i8"), "<i8", "HCW"),
                "output": _save_array(stripe_dir, "output-hcw.i16le",
                                      _hcw(result["output"], "<i2"), "<i2", "HCW"),
            }
            tensor_words = channels * width * width // 8
            descriptor = contract.validate_descriptor({
                "profile": profile,
                "param_base_words": 0,
                "params_words": contract.PROFILE_SPECS[profile]["stride_words"],
                "memory_words": 2 * tensor_words + 5120,
                "src_words": 0,
                "dst_words": tensor_words,
                "scratch_words": 2 * tensor_words,
                "start_row": start,
                "row_count": 4,
            })
            stripe_metadata = {
                "profile": profile, "block_index": 0, "sample_id": "image-00",
                "start_row": start, "row_count": 4,
                "q3_start_row": result["q3_start_row"],
                "q3_end_row": result["q3_end_row"],
                "descriptor": descriptor,
                "files": files,
            }
            metadata_path = stripe_dir / "metadata.json"
            metadata_path.write_text(json.dumps(stripe_metadata, indent=2, sort_keys=True) + "\n",
                                     encoding="utf-8")
            stripe_metadata["metadata"] = {
                "path": metadata_path.name, "bytes": metadata_path.stat().st_size,
                "sha256": sha256(metadata_path),
            }
            stripe_records.append(stripe_metadata)
        if not np.array_equal(stitched, expected):
            mismatch = np.flatnonzero(stitched.reshape(-1) != expected.reshape(-1))
            raise AssertionError("profile%d stripe stitch mismatch at %d" %
                                 (profile, int(mismatch[0])))
        stitched_entry = _save_array(directory, "stitched-block00-hcw.i16le",
                                     _hcw(stitched, "<i2"), "<i2", "HCW")
        expected_hcw = _hcw(expected, "<i2")
        expected_entry = _save_array(directory, "expected-block00-hcw.i16le",
                                     expected_hcw, "<i2", "HCW")
        manifest["profiles"][str(profile)] = {
            "channels": channels, "width": width, "block_index": 0,
            "canonical_manifest": str(record["manifest"].relative_to(root)).replace("\\", "/"),
            "canonical_manifest_sha256": record["manifest_sha256"],
            "canonical_params_sha256": sha256(record["params"]),
            "canonical_input_sha256": sha256(record["input_hcw"]),
            "canonical_expected_chw_sha256": sha256(record["expected_block0_chw"]),
            "params_copy_sha256": sha256(params_path),
            "source_copy_sha256": sha256(source_path),
            "full_block_stitch_exact": True,
            "stitched": stitched_entry,
            "expected": expected_entry,
            "selected_stripes": stripe_records,
            "resource_model": contract.resource_model(profile),
        }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    receipt = {
        "status": "CNN_SHARED_V7_FIXTURES_COMPLETED",
        "manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
        "manifest_sha256": sha256(manifest_path),
        "profiles": [0, 1, 2],
        "selected_stripes_per_profile": 3,
        "full_block_stitch_exact": True,
    }
    receipt_path = output / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    return receipt_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--output", default=(
        "artifacts/board-debug-20261005/acceleration/host/"
        "cnn-shared-v7-stripe-fixtures-001"))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    print(build_fixtures(root, output))


if __name__ == "__main__":
    main()

