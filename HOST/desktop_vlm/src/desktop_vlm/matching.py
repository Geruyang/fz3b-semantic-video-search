"""Finite row vectors, cosine scores and stable ranking (no probabilities)."""
import numpy as np


def normalize_rows(x):
    """Accept nonempty [N,D]; return float32 unless input is float64.

    Norms use float64 accumulation to avoid overflow/underflow. Reject zero,
    nonfinite and malformed vectors instead of silently emitting a prediction.
    """
    source = np.asarray(x)
    if source.ndim != 2 or 0 in source.shape or source.dtype.kind not in "fiu":
        raise ValueError("features must be a nonempty numeric [N,D] matrix")
    dtype = np.float64 if source.dtype == np.float64 else np.float32
    values = source.astype(np.float64)
    if not np.isfinite(values).all():
        raise ValueError("features contain NaN or infinity")
    scale = np.max(np.abs(values), axis=1, keepdims=True)
    if np.any(scale == 0):
        raise ValueError("zero feature vector")
    scaled = values / scale
    normalized = scaled / np.sqrt(np.sum(scaled * scaled, axis=1, keepdims=True))
    return normalized.astype(dtype)


def cosine_scores(query, candidates):
    """Return [N,M] for nonempty query [N,D] and candidate [M,D]."""
    q, c = normalize_rows(query), normalize_rows(candidates)
    if q.shape[1] != c.shape[1]:
        raise ValueError("query/candidate feature dimensions differ")
    return np.clip(q @ c.T, -1.0, 1.0)


def rank_scores(scores, top_k):
    """Return candidate indices for one [M] score row; ties keep input order."""
    row = np.asarray(scores)
    if row.ndim != 1 or not row.size or row.dtype.kind not in "fiu" or not np.isfinite(row).all():
        raise ValueError("scores must be a nonempty finite numeric [M] row")
    if isinstance(top_k, (bool, np.bool_)) or not isinstance(top_k, (int, np.integer)) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    return np.argsort(-row.astype(np.float64), kind="stable")[:min(int(top_k), row.size)].tolist()
