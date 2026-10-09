import json

import numpy as np
import pytest

from cnn_pipeline_v10_suffix_capture import wrap_suffix_capture_client


class FakeClient(object):
    header = {"backend": "fake"}
    outputs_have_independent_lifetime = True
    validates_tensor_finiteness = True

    def __init__(self):
        self.closed = False
        self.calls = 0

    def infer(self, tensors):
        self.calls += 1
        return {"features": np.zeros((1, 512), dtype="<f4")}, 1.0

    def close(self):
        self.closed = True
        return {"closed": True}


def value(number):
    return np.full((1, 256, 16, 16), number, dtype="<f4")


def test_capture_preserves_first_distinct_order_and_summary_after_close(tmp_path):
    base = FakeClient()
    client = wrap_suffix_capture_client(base, tmp_path / "capture", max_distinct=2)
    assert client.header == base.header
    assert client.outputs_have_independent_lifetime is True
    assert client.validates_tensor_finiteness is True
    client.infer([value(3)])
    client.infer([value(7)])
    client.infer([value(3)])
    client.close()
    summary = client.capture_summary()
    assert summary["status"] == "CAPTURE_COMPLETE"
    assert summary["performance_valid"] is False
    assert summary["distinct_count"] == 2
    assert summary["infer_calls"] == 3
    assert [item["first_infer_call"] for item in summary["records"]] == [0, 1]
    manifest = json.loads((tmp_path / "capture" / "manifest.json").read_text())
    assert manifest["records"] == summary["records"]
    assert (tmp_path / "capture" / "suffix-input-00.f32").read_bytes() == value(3).tobytes()
    assert (tmp_path / "capture" / "suffix-input-01.f32").read_bytes() == value(7).tobytes()


def test_capture_rejects_third_distinct_and_invalid_inputs(tmp_path):
    client = wrap_suffix_capture_client(FakeClient(), tmp_path / "capture", 2)
    client.infer([value(1)])
    client.infer([value(2)])
    with pytest.raises(RuntimeError, match="distinct-input bound"):
        client.infer([value(3)])
    bad = value(1)
    bad.reshape(-1)[0] = np.nan
    with pytest.raises(ValueError, match="finite contiguous"):
        client.infer([bad])


def test_capture_directory_and_post_close_are_fail_closed(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        wrap_suffix_capture_client(FakeClient(), existing, 2)
    client = wrap_suffix_capture_client(FakeClient(), tmp_path / "capture", 2)
    client.close()
    with pytest.raises(RuntimeError, match="closed"):
        client.infer([value(1)])
