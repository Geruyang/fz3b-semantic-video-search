"""Build a self-contained offline bundle for complete v7 normal-block chains."""

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

import cnn_shared_v7_contract as contract


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entry(path):
    path = Path(path)
    return {"path": path.as_posix(), "bytes": path.stat().st_size,
            "sha256": sha256(path)}


def _link_or_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(str(source), str(target))
        return "hardlink"
    except OSError:
        shutil.copyfile(str(source), str(target))
        return "copy"


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _source_files(golden_root, profile, block_count):
    profile_root = Path(golden_root) / "image-00" / ("profile%d" % profile)
    paths = [profile_root / "input-hcw.i16le"]
    paths.extend(profile_root / ("block-%02d-add-hcw.i16le" % index)
                  for index in range(block_count))
    for path in paths:
        if not path.is_file():
            raise ValueError("missing frozen activation fixture: %s" % path)
    return paths


def _copy_item(root, target_root, source):
    relative = Path(source).relative_to(root)
    target = target_root / relative.name
    method = _link_or_copy(source, target)
    entry = _entry(target)
    entry["source"] = str(relative).replace("\\", "/")
    entry["materialization"] = method
    return entry


def build_bundle(repository_root, runtime_root, golden_root, output_root):
    repository_root = Path(repository_root).resolve()
    runtime_root = Path(runtime_root).resolve()
    golden_root = Path(golden_root).resolve()
    output_root = Path(output_root).resolve()
    if output_root.exists():
        raise FileExistsError("refusing to overwrite %s" % output_root)
    runtime_manifest_path = runtime_root / "manifest.json"
    golden_manifest_path = golden_root / "manifest.json"
    runtime_manifest = _load_json(runtime_manifest_path)
    golden_manifest = _load_json(golden_manifest_path)
    output_root.mkdir(parents=True)
    profiles = {}
    files = {}
    for profile in (0, 1, 2):
        spec = contract.profile_spec(profile)
        runtime_profile = runtime_manifest["profiles"][str(profile)]
        count = int(runtime_profile["block_count"])
        if count != spec["blocks"]:
            raise ValueError("frozen profile %d block count mismatch" % profile)
        if int(runtime_profile["parameter_words_per_block"]) != spec["stride_words"]:
            raise ValueError("frozen profile %d parameter stride mismatch" % profile)
        params_source = runtime_root / runtime_profile["parameter_file"]["path"]
        params_target = output_root / ("params-profile%d.bin" % profile)
        method = _link_or_copy(params_source, params_target)
        params_entry = _entry(params_target)
        params_entry["source"] = str(params_source.relative_to(repository_root)).replace("\\", "/")
        params_entry["materialization"] = method
        if params_entry["bytes"] != count * spec["stride_words"] * 16:
            raise ValueError("profile %d combined parameter size mismatch" % profile)
        files[params_entry["path"]] = params_entry

        activation_sources = _source_files(golden_root, profile, count)
        activation_entries = []
        for index, source in enumerate(activation_sources):
            relative_source = source.relative_to(golden_root).as_posix()
            indexed = golden_manifest.get("files", {}).get(relative_source)
            if indexed is None:
                raise ValueError("golden manifest omits %s" % relative_source)
            if sha256(source) != indexed["sha256"] or source.stat().st_size != int(indexed["bytes"]):
                raise ValueError("golden manifest integrity mismatch for %s" % relative_source)
            target = output_root / ("profile%d" % profile) / source.name
            method = _link_or_copy(source, target)
            entry = _entry(target)
            entry["source"] = str(source.relative_to(repository_root)).replace("\\", "/")
            entry["materialization"] = method
            files[entry["path"]] = entry
            activation_entries.append(entry)

        tensor_words = spec["channels"] * spec["width"] * spec["width"] // 8
        src_words = 256
        dst_words = src_words + tensor_words + 128
        scratch_words = dst_words + tensor_words + 256
        scratch_capacity = 10 * spec["channels"] * spec["width"] // 8
        memory_words = scratch_words + scratch_capacity + 128
        block_records = []
        for block_index in range(count):
            src_slot, dst_slot = (block_index & 1), (1 - (block_index & 1))
            block_src = src_words if src_slot == 0 else dst_words
            block_dst = src_words if dst_slot == 0 else dst_words
            descriptors = []
            for start_row in range(0, spec["width"], 4):
                descriptor = contract.validate_descriptor({
                    "profile": profile,
                    "param_base_words": block_index * spec["stride_words"],
                    "params_words": count * spec["stride_words"],
                    "memory_words": memory_words,
                    "src_words": block_src,
                    "dst_words": block_dst,
                    "scratch_words": scratch_words,
                    "start_row": start_row,
                    "row_count": 4,
                })
                descriptor["block_index"] = block_index
                descriptor["scratch_capacity_words"] = scratch_capacity
                descriptors.append(descriptor)
            block_records.append({
                "block_index": block_index,
                "source": activation_entries[0] if block_index == 0 else activation_entries[block_index],
                "expected": activation_entries[block_index + 1],
                "src_slot": src_slot, "dst_slot": dst_slot,
                "src_words": block_src, "dst_words": block_dst,
                "descriptors": descriptors,
            })
        profiles[str(profile)] = {
            "profile": profile, "network": runtime_profile["network"],
            "channels": spec["channels"], "width": spec["width"],
            "block_count": count, "stride_words": spec["stride_words"],
            "params": params_entry, "input": activation_entries[0],
            "blocks": block_records,
            "scratch_capacity_words": scratch_capacity,
            "scratch_capacity_rows": 10,
            "memory_words": memory_words,
        }
    manifest = {
        "schema_version": 1,
        "status": "CNN_SHARED_V7_NORMAL_CHAIN_BUNDLE_READY",
        "execution_scope": "normal v7 block chain on one core; excludes stem, suffix, end-to-end FPS",
        "block_count_note": "Frozen profile counts are 0=12, 1=20, 2=4; profile 1 has 20 blocks and profile 2 has 4 blocks, so no per-profile 12-block override was applied.",
        "source_artifacts": {
            "runtime_manifest_sha256": sha256(runtime_manifest_path),
            "golden_manifest_sha256": sha256(golden_manifest_path),
        },
        "frozen_profile_counts": {"0": 12, "1": 20, "2": 4},
        "files": files,
        "profiles": profiles,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    receipt = {"status": "CNN_SHARED_V7_NORMAL_CHAIN_BUNDLE_COMPLETED",
               "manifest": "manifest.json", "manifest_sha256": sha256(manifest_path),
               "profile_block_counts": {"0": 12, "1": 20, "2": 4},
               "total_blocks": 36,
               "total_stripes": sum(profiles[str(p)]["width"] // 4 *
                                    profiles[str(p)]["block_count"] for p in (0, 1, 2))}
    (output_root / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    root_default = Path(__file__).resolve().parents[3]
    host_default = "artifacts/board-debug-20261005/acceleration/host"
    parser.add_argument("--root", default=str(root_default))
    parser.add_argument("--runtime", default=host_default + "/network-w16-runtime-bundles-001")
    parser.add_argument("--golden", default=host_default + "/network-w16-same-board-golden-001")
    parser.add_argument("--output", default=host_default + "/cnn-shared-v7-normal-chain-bundle-001")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    runtime = Path(args.runtime)
    golden = Path(args.golden)
    output = Path(args.output)
    if not runtime.is_absolute():
        runtime = root / runtime
    if not golden.is_absolute():
        golden = root / golden
    if not output.is_absolute():
        output = root / output
    print(json.dumps(build_bundle(root, runtime, golden, output), sort_keys=True))


if __name__ == "__main__":
    main()
