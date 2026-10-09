import numpy as np
import pytest
from desktop_vlm.model import MobileCLIPEncoder, OFFICIAL_REVISION, S1_WEIGHT_SHA256
from desktop_vlm.cache import validate_identity, build_text_cache


def test_pinned_source_weight_and_no_fallback(tmp_path):
    assert len(OFFICIAL_REVISION) == 40 and len(S1_WEIGHT_SHA256) == 64
    with pytest.raises(ValueError, match="checkout"):
        MobileCLIPEncoder(official_repo=tmp_path, weights=tmp_path / "missing.pt")
    with pytest.raises(ValueError, match="s1 only"):
        MobileCLIPEncoder(official_repo=tmp_path, weights=tmp_path / "missing.pt", model_name="mobileclip_s0")


def test_identity_complete(identity):
    validate_identity(identity)
    del identity["tokenizer"]
    with pytest.raises(ValueError, match="incomplete"):
        validate_identity(identity)


def test_encoder_wrong_shape_fails_before_publish(tmp_path, encoder, prompts, monkeypatch):
    monkeypatch.setattr(encoder, "encode_texts", lambda _: np.ones((2, 4), dtype=np.float32))
    with pytest.raises(ValueError, match="contract"):
        build_text_cache(encoder, prompts, tmp_path / "bad.npz")
    assert not (tmp_path / "bad.npz").exists()
