from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "desktop_vlm" / "board"))

from cnn_v10_mixed_suffix import inspect_suffix
from cnn_v10_mixed_suffix_tool import _hot_groups


MODEL = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-release-bundle-003/models/suffix.onnx"


def test_real_suffix_graph_and_sensitive_fp32_operator_contract():
    contract = inspect_suffix(MODEL)
    assert contract["node_count"] == 248
    assert contract["operator_counts"]["BatchNormalization"] == 4
    assert contract["independent_layer_normalization_nodes"] == 0
    assert len(contract["quantization_candidate_node_names"]) == 37
    assert len(contract["fp32_sensitive_node_names"]) == 27


def test_hotspot_search_screens_individual_convs_and_convffn_regions():
    groups = _hot_groups(MODEL)
    ids = [group["id"] for group in groups]
    assert sum(group_id.startswith("conv-node:") for group_id in ids) == 20
    assert sum(group_id.startswith("matmul-node:") for group_id in ids) == 16
    assert {f"convffn-block-{i}" for i in range(4)} <= set(ids)
    assert not any("/model/head/MatMul" in " ".join(group["new_nodes"]) for group in groups)

