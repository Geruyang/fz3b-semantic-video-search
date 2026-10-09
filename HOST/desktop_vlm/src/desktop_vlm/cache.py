"""Single-file NPZ + UTF-8 JSON, integrity checked before atomic replacement."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

import numpy as np

from .matching import normalize_rows
from .prompts import validate_prompts

IDENTITY_FIELDS = {"schema_version", "backend", "model", "weight_sha256", "code_revision", "code_sha256", "tokenizer", "preprocess", "dimension", "dtype", "normalization", "dependencies", "device", "reparameterized"}


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_identity(identity):
    if not isinstance(identity, dict) or not IDENTITY_FIELDS.issubset(identity):
        raise ValueError("incomplete model identity")
    if identity["schema_version"] != 1 or identity["dtype"] != "float32":
        raise ValueError("unsupported identity schema or dtype")
    if type(identity["dimension"]) is not int or identity["dimension"] <= 0:
        raise ValueError("invalid identity dimension")
    for key in ("backend", "model", "code_revision", "device"):
        if not isinstance(identity[key], str) or not identity[key]:
            raise ValueError(f"identity {key} missing")
    for key in ("weight_sha256", "code_sha256"):
        if not isinstance(identity[key], str) or len(identity[key]) != 64 or any(c not in "0123456789abcdef" for c in identity[key]):
            raise ValueError(f"invalid identity {key}")
    for key in ("tokenizer", "preprocess", "normalization", "dependencies"):
        if not isinstance(identity[key], dict) or not identity[key]:
            raise ValueError(f"identity {key} missing")
    if type(identity["reparameterized"]) is not bool:
        raise ValueError("reparameterized must be boolean")
    canonical_json(identity)
    return identity


def _feature_matrix(features, identity, count):
    values = np.asarray(features)
    if values.dtype != np.dtype("float32") or values.shape != (count, identity["dimension"]):
        raise ValueError("feature dtype/shape does not match metadata")
    normalize_rows(values)  # validates finite/nonzero without silently fixing data
    if not np.allclose(np.linalg.norm(values.astype(np.float64), axis=1), 1.0, atol=1e-5, rtol=0):
        raise ValueError("persisted feature rows must be L2 normalized")
    return np.ascontiguousarray(values, dtype=np.float32)


def _digest(metadata, features):
    payload = {key: value for key, value in metadata.items() if key != "artifact_id"}
    h = hashlib.sha256(canonical_json(payload).encode("utf-8"))
    h.update(np.asarray(features, dtype="<f4").tobytes(order="C"))
    return h.hexdigest()


def _load_artifact(path, expected_identity, kind):
    validate_identity(expected_identity)
    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != {"metadata", "features"}:
                raise ValueError("unexpected archive members")
            raw = archive["metadata"]
            if raw.shape != () or raw.dtype.kind != "U":
                raise ValueError("metadata must be a scalar JSON string")
            metadata = json.loads(str(raw.item()))
            features = archive["features"].copy()
        if not isinstance(metadata, dict) or metadata.get("schema_version") != 1 or metadata.get("kind") != kind:
            raise ValueError("unsupported artifact metadata")
        validate_identity(metadata.get("identity"))
        if canonical_json(metadata["identity"]) != canonical_json(expected_identity):
            raise ValueError("model identity mismatch; explicitly rebuild the complete artifact")
        if not isinstance(metadata.get("items"), list) or not metadata["items"]:
            raise ValueError("empty/malformed artifact items")
        values = _feature_matrix(features, metadata["identity"], len(metadata["items"]))
        if metadata.get("artifact_id") != _digest(metadata, values):
            raise ValueError("artifact integrity mismatch")
        return metadata, values
    except (OSError, EOFError, KeyError, TypeError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {kind}: {exc}") from exc


def _atomic_write(path, metadata, features, validator):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(metadata)
    metadata["artifact_id"] = _digest(metadata, features)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            np.savez_compressed(handle, metadata=np.array(canonical_json(metadata)), features=features)
            handle.flush()
            os.fsync(handle.fileno())
        validator(temporary)  # complete semantic readback before publishing
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return metadata["artifact_id"]


def build_text_cache(encoder, prompts, output):
    items = validate_prompts(prompts)
    identity = validate_identity(encoder.identity())
    encoded = np.asarray(encoder.encode_texts([p["text"] for p in items]))
    if encoded.dtype != np.float32 or encoded.shape != (len(items), identity["dimension"]):
        raise ValueError("encoder violated float32 [N,D] contract")
    features = normalize_rows(encoded)
    metadata = {"schema_version": 1, "kind": "text-cache", "identity": identity, "items": items}
    return _atomic_write(output, metadata, features, lambda path: load_text_cache(path, identity, items))


def load_text_cache(path, expected_identity, expected_prompts=None):
    metadata, features = _load_artifact(path, expected_identity, "text-cache")
    items = validate_prompts(metadata["items"])
    if expected_prompts is not None and items != validate_prompts(expected_prompts):
        raise ValueError("prompt descriptions/order/labels differ; rebuild complete cache")
    return {"cache_id": metadata["artifact_id"], "identity": metadata["identity"], "prompts": items, "features": features}
