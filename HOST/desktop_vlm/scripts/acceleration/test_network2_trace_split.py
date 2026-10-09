"""Contract tests for the 12-block network.2 trace split and PS collector."""
import importlib.util
from pathlib import Path

import pytest

from build_network2_trace_split import TRACE_LABELS, block_node_names


ROOT = Path(__file__).resolve().parents[3]
COLLECTOR = ROOT / "desktop_vlm/board/collect_network2_block_traces.py"
SPLIT = ROOT / "artifacts/board-debug-20261005/acceleration/host/network2-trace-split-002"
SPLIT_SHA256 = "9f7a16199470b7846437475113d91bf9e8a2cdb183ee3dc1806befb89105d1bf"


def _load_collector():
    spec = importlib.util.spec_from_file_location("collect_network2_block_traces", COLLECTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_node_contract_is_complete_and_block_specific():
    all_names = set()
    for index in range(12):
        names = block_node_names(index)
        assert tuple(names) == TRACE_LABELS
        assert all("network.2.%d" % index in value for value in names.values())
        assert not (set(names.values()) & all_names)
        all_names.update(names.values())


def test_stage_contract_accepts_expected_shapes_and_rejects_dtype():
    collector = _load_collector()
    record = {"inputs": [{"name": "x", "shape": [1, 128, 32, 32],
                           "dtype": "<f4", "bytes": 524288}],
              "outputs": [{"name": "y", "shape": [1, 384, 32, 32],
                            "dtype": "<f4", "bytes": 1572864}]}
    parsed = collector.stage_contract(record)
    assert parsed["inputs"][0]["shape"] == (1, 128, 32, 32)
    record["outputs"][0]["dtype"] = ">f4"
    with pytest.raises(ValueError, match="little-endian"):
        collector.stage_contract(record)


def test_stage_contract_rejects_byte_count_mismatch():
    collector = _load_collector()
    record = {"inputs": [{"name": "x", "shape": [1, 128, 32, 32],
                           "dtype": "<f4", "bytes": 4}],
              "outputs": []}
    with pytest.raises(ValueError, match="invalid tensor contract"):
        collector.stage_contract(record)


def test_frozen_split_has_suffix_and_strict_add_to_next_input_names():
    collector = _load_collector()
    manifest = collector.load_split(SPLIT, SPLIT_SHA256)
    assert manifest["stages"]["suffix"]["outputs"] == [
        {"bytes": 2048, "dtype": "<f4", "name": "features", "shape": [1, 512]}]
    assert len(manifest["blocks"]) == 12
    for index in range(11):
        assert manifest["blocks"][index]["outputs"]["add"] == \
            manifest["blocks"][index + 1]["input"]


def test_frozen_host_trace_inventory_hashes_and_continuity_are_exact():
    collector = _load_collector()
    manifest = collector.load_split(SPLIT, SPLIT_SHA256)
    assert len(manifest["host_reference"]["samples"]) == 3
    for sample in manifest["host_reference"]["samples"]:
        records = {(item["block"], item["label"]): item for item in sample["files"]}
        assert len(records) == 12 * 8
        for record in records.values():
            path = SPLIT / record["path"]
            assert path.stat().st_size == record["bytes"]
            assert collector.sha256(path) == record["sha256"]
        for index in range(11):
            add_path = SPLIT / records[(index, "add")]["path"]
            next_path = SPLIT / records[(index + 1, "input")]["path"]
            assert add_path.read_bytes() == next_path.read_bytes()
