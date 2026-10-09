"""Explicit synthetic encoder fixtures test contracts, never true S1 success."""
from copy import deepcopy
import numpy as np
import pytest


@pytest.fixture
def identity():
    return {"schema_version": 1, "backend": "synthetic-test-only", "model": "synthetic-test-only", "weight_sha256": "a" * 64, "code_revision": "fixture-1", "code_sha256": "b" * 64, "tokenizer": {"name": "fixture"}, "preprocess": {"name": "fixture"}, "dimension": 3, "dtype": "float32", "normalization": {"encoder": "raw-float32", "persisted": "l2-float32-v1"}, "dependencies": {"fixture": "1"}, "device": "cpu", "reparameterized": False}


@pytest.fixture
def prompts():
    return [{"id": "one", "text": "a cup", "label": "杯子"}, {"id": "two", "text": "a phone", "label": "手机"}]


@pytest.fixture
def encoder(identity):
    class SyntheticEncoder:
        def identity(self):
            return deepcopy(identity)

        def encode_texts(self, texts):
            return np.array([[1, 0, 0] if "cup" in text else [0, 1, 0] for text in texts], dtype=np.float32)

        def encode_images(self, images):
            return np.array([[1, 0, 0] for _ in images], dtype=np.float32)
    return SyntheticEncoder()
