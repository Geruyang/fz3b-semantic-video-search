from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn_v10_n1_native_mask_bundle import _selection_descriptor


def test_host_prepared_selection_is_explicitly_target_pending_and_keeps_abi_paths(tmp_path):
    for name in ("native-manifest.json", "libcnn_v10_n1_native.so", "n1-params.bin",
                 "target-receipt.json", "target-result.json"):
        (tmp_path / name).write_bytes(name.encode("ascii"))
    manifest = {"pw_fp32_channels": list(range(16)),
        "input": {"logical_pl_scale_value_f64": 1.0},
        "output": {"logical_pl_scale_value_f64": 2.0}}
    record = _selection_descriptor(tmp_path, manifest, "params-sha", "library-sha", "model-sha")
    assert record["schema"] == "cnn-v10.1-n1-w8a16-selection-v1"
    assert record["status"] == "HOST_PREPARED_TARGET_GATE_PENDING"
    assert record["native_manifest"]["path"] == "native-manifest.json"
    assert record["native_library"]["path"] == "libcnn_v10_n1_native.so"
    assert record["packed_parameters"]["path"] == "n1-params.bin"
    assert record["precision"]["sensitive_channel_count"] == 16
    assert "NOT_ELIGIBLE" in record["runtime_eligibility"]
