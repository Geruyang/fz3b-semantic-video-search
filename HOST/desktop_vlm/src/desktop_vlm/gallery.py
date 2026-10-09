"""Version-bound semantic gallery. Similarity does not imply object identity."""
from pathlib import Path

import numpy as np

from .cache import _atomic_write, _load_artifact, sha256_file, validate_identity
from .matching import cosine_scores, normalize_rows, rank_scores


def _validate_items(items):
    if not isinstance(items, list) or not items:
        raise ValueError("gallery is empty")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"item_id", "label", "image_sha256"}:
            raise ValueError("malformed gallery item")
        if any(not isinstance(v, str) or not v.strip() for v in item.values()):
            raise ValueError("gallery item fields must be nonempty strings")
        if item["item_id"] in seen:
            raise ValueError("duplicate gallery item_id")
        sha = item["image_sha256"]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("invalid gallery image SHA256")
        seen.add(item["item_id"])
    return items


def build_gallery(encoder, items, output):
    """Input items have item_id, label and path; filenames can be Chinese labels."""
    if not isinstance(items, list) or not items:
        raise ValueError("gallery image list is empty")
    metadata_items, paths = [], []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"item_id", "label", "path"}:
            raise ValueError("gallery build requires item_id, label, path")
        path = Path(item["path"])
        metadata_items.append({"item_id": item["item_id"], "label": item["label"], "image_sha256": sha256_file(path)})
        paths.append(path)
    _validate_items(metadata_items)
    identity = validate_identity(encoder.identity())
    encoded = np.asarray(encoder.encode_images(paths))
    if encoded.dtype != np.float32 or encoded.shape != (len(items), identity["dimension"]):
        raise ValueError("encoder violated float32 [N,D] contract")
    features = normalize_rows(encoded)
    metadata = {"schema_version": 1, "kind": "gallery", "identity": identity, "items": metadata_items}
    return _atomic_write(output, metadata, features, lambda p: load_gallery(p, identity))


def load_gallery(path, expected_identity):
    metadata, features = _load_artifact(path, expected_identity, "gallery")
    items = _validate_items(metadata["items"])
    return {"gallery_id": metadata["artifact_id"], "identity": metadata["identity"], "items": items, "features": features}


def query_gallery(encoder, image, gallery, top_k=5, exclude_same_image=False):
    if gallery["identity"] != encoder.identity():
        raise ValueError("gallery/query model identity mismatch")
    _validate_items(gallery["items"])
    indices = list(range(len(gallery["items"])))
    if exclude_same_image:
        query_sha = sha256_file(image)
        indices = [i for i in indices if gallery["items"][i]["image_sha256"] != query_sha]
    if not indices:
        raise ValueError("gallery has no eligible entries after same-image exclusion")
    scores = cosine_scores(encoder.encode_images([image]), gallery["features"][indices])[0]
    order = rank_scores(scores, top_k)
    return [{**gallery["items"][indices[i]], "cosine": float(scores[i])} for i in order]
