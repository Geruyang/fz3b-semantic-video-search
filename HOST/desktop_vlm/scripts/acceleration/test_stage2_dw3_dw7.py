"""Contract tests for the pinned DW3->DW7 split and board collector ABI."""
import json
from pathlib import Path
import sys

import pytest

from split_stage2_dw3_dw7 import sha256
from verify_stage2_dw3_dw7_collection import _compare


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "desktop_vlm"))
from board.collect_stage2_dw3_dw7 import load_split, stage_contract

SPLIT = ROOT / "artifacts/board-debug-20261004/acceleration/host/stage2-dw3-dw7-003"
SPLIT_SHA256 = "bc02f542e5fdb58f440f851cdb76fe2bcb466f58fcb1f17c8de3f108d102132a"


def test_frozen_split_is_two_contiguous_depthwise_ops_and_pins_inputs():
    manifest = load_split(SPLIT, SPLIT_SHA256)
    assert manifest["boundary"]["dw3_contract"]["kernel_shape"] == [3, 3]
    assert manifest["boundary"]["dw7_contract"]["kernel_shape"] == [7, 7]
    assert manifest["boundary"]["dw3_contract"]["group"] == 128
    assert manifest["boundary"]["dw7_contract"]["group"] == 128
    assert [item["sha256"] for item in manifest["three_old_preprocessed_inputs"]] == [
        "bb1d68f60f660ef824270dac40b0211df4c235d58944bafcc831845c17809e51",
        "32693e16acc4ee99beef72f25546e3b19fbbc8fcdd0988df3884bc63da115c8d",
        "eaec02ff7d4ac81ca3f3e01f88395f56bc8c997f8a224d721dff3dcad756c0e0",
    ]
    assert manifest["host_reference"]["status"] == \
        "INDEPENDENT_HOST_ORT_ONLY_NOT_ACTUAL_BOARD_PS_GOLDEN"
    assert manifest["collector"]["source_sha256"] == sha256(
        ROOT / "desktop_vlm/board/collect_stage2_dw3_dw7.py")
    assert manifest["collector"]["partition_client_source_sha256"] == \
        sha256(ROOT / "desktop_vlm/board/partition_s1.py")
    assert manifest["collector"]["partition_runner_binary_sha256"] == \
        "fe53666be409e9693a899bd08c29fe51f002f9a9894475c2e412b021c19e955c"
    assert all(item["full_model_feature_max_abs"] == 0.0
               for item in manifest["host_reference"]["samples"])


def test_split_rejects_manifest_sha_change():
    with pytest.raises(ValueError, match="trusted command argument"):
        load_split(SPLIT, "0" * 64)


def test_collector_contract_derives_exact_shapes_and_byte_counts():
    manifest = json.loads((SPLIT / "manifest.json").read_text(encoding="utf-8"))
    prefix = stage_contract(manifest["stages"]["prefix"])
    region = stage_contract(manifest["stages"]["region"])
    assert prefix["inputs"] == [{"name": "image", "shape": (1, 3, 256, 256),
                                  "bytes": 786432}]
    assert region["outputs"][0]["bytes"] == 524288
    assert len(region["outputs"]) == 2


def test_collector_contract_rejects_malformed_tensor_metadata():
    record = {"inputs": [{"name": "x", "shape": [1, 3, 256, 256],
                          "dtype": "<f4", "bytes": 12}], "outputs": []}
    with pytest.raises(ValueError, match="invalid stage tensor contract"):
        stage_contract(record)


def test_host_comparison_reports_exactness_without_promoting_provenance():
    import numpy as np
    reference = np.asarray([1.0, -2.0], dtype="<f4")
    exact = _compare(reference, reference.copy())
    near = _compare(reference, np.asarray([1.0, -1.999999], dtype="<f4"))
    assert exact["exact_bytes_match"] is True
    assert near["exact_bytes_match"] is False
    assert near["max_abs"] > 0
    assert "provenance" not in near

