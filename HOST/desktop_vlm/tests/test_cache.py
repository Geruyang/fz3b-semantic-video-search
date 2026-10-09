from copy import deepcopy
import json
import numpy as np
import pytest
from desktop_vlm import cache
from desktop_vlm.matching import cosine_scores


def test_cold_hot_and_order(tmp_path, encoder, identity, prompts):
    path = tmp_path / "texts.npz"
    cache_id = cache.build_text_cache(encoder, prompts, path)
    loaded = cache.load_text_cache(path, identity, prompts)
    assert loaded["cache_id"] == cache_id
    cold = cosine_scores([[1, 0, 0]], encoder.encode_texts([p["text"] for p in prompts]))
    np.testing.assert_allclose(cold, cosine_scores([[1, 0, 0]], loaded["features"]), atol=1e-6)
    with pytest.raises(ValueError):
        cache.load_text_cache(path, identity, list(reversed(prompts)))


@pytest.mark.parametrize("field", ["model", "weight_sha256", "code_revision", "code_sha256", "tokenizer", "preprocess", "dimension", "dtype", "normalization", "dependencies", "device", "reparameterized"])
def test_full_identity_required(field, tmp_path, encoder, identity, prompts):
    path = tmp_path / "texts.npz"
    cache.build_text_cache(encoder, prompts, path)
    other = deepcopy(identity)
    other[field] = {"changed": True} if isinstance(other[field], dict) else (False if field == "reparameterized" else "changed")
    if field == "reparameterized":
        other[field] = True
    with pytest.raises(ValueError):
        cache.load_text_cache(path, other)


def test_atomic_replace_failure_preserves_old(tmp_path, encoder, identity, prompts, monkeypatch):
    path = tmp_path / "texts.npz"
    cache.build_text_cache(encoder, prompts, path)
    before = path.read_bytes()
    def denied(*args):
        raise OSError("injected atomic replacement failure")
    monkeypatch.setattr(cache.os, "replace", denied)
    with pytest.raises(OSError):
        cache.build_text_cache(encoder, list(reversed(prompts)), path)
    assert path.read_bytes() == before
    assert cache.load_text_cache(path, identity)["prompts"] == prompts
    assert not list(tmp_path.glob("*.tmp"))


def test_validation_failure_preserves_old(tmp_path, encoder, prompts, monkeypatch):
    path = tmp_path / "texts.npz"
    cache.build_text_cache(encoder, prompts, path)
    before = path.read_bytes()
    def rejected(*args):
        raise ValueError("injected readback failure")
    monkeypatch.setattr(cache, "load_text_cache", rejected)
    with pytest.raises(ValueError):
        cache.build_text_cache(encoder, prompts, path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("mode", ["nan", "zero", "dimension", "dtype", "metadata"])
def test_corruption_rejected(mode, tmp_path, encoder, identity, prompts):
    path = tmp_path / "texts.npz"
    cache.build_text_cache(encoder, prompts, path)
    with np.load(path, allow_pickle=False) as data:
        features, metadata = data["features"].copy(), data["metadata"].copy()
    if mode == "nan": features[0, 0] = np.nan
    if mode == "zero": features[0] = 0
    if mode == "dimension": features = features[:, :2]
    if mode == "dtype": features = features.astype(np.float64)
    if mode == "metadata":
        obj = json.loads(metadata.item())
        obj["items"].reverse()
        metadata = np.array(json.dumps(obj))
    np.savez(path, features=features, metadata=metadata)
    with pytest.raises(ValueError):
        cache.load_text_cache(path, identity)
