"""Explicit pinned official MobileCLIP-S1 adapter for research experiments.

No weights download, random fallback or alternate model backend is provided.
"""
from copy import deepcopy
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from typing import Protocol

import numpy as np
from PIL import Image

from .cache import canonical_json, sha256_file
from .matching import normalize_rows

OFFICIAL_REVISION = "48faa0fea4b08d74188b3841771aca6ff2c92852"
S1_WEIGHT_SHA256 = "1270fab6ea23bacbd61cea564bd521a7e875fdb0fcb6d31382bccf4d973b71a6"


class Encoder(Protocol):
    def encode_images(self, images) -> np.ndarray: ...
    def encode_texts(self, texts) -> np.ndarray: ...
    def identity(self) -> dict: ...


class MobileCLIPEncoder:
    def __init__(self, *, official_repo, weights, device="cpu", model_name="mobileclip_s1", reparameterize=True, cpu_threads=4):
        if model_name != "mobileclip_s1":
            raise ValueError("this experimental adapter targets mobileclip_s1 only")
        root, weight = Path(official_repo).resolve(), Path(weights).resolve()
        if not (root / "mobileclip" / "__init__.py").is_file():
            raise ValueError("explicit official repository checkout is missing")
        if not weight.is_file():
            raise ValueError("explicit S1 weights are missing; no implicit download")
        if sha256_file(weight) != S1_WEIGHT_SHA256:
            raise ValueError("weights differ from the locked official S1 SHA256")
        revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
        if revision != OFFICIAL_REVISION:
            raise ValueError("official source revision differs from locked revision")
        tracked_changes = subprocess.run(["git", "-C", str(root), "diff", "HEAD", "--", "mobileclip"], check=True, text=True, capture_output=True).stdout
        if tracked_changes:
            raise ValueError("official tracked MobileCLIP source is modified")
        files = sorted(p for p in (root / "mobileclip").rglob("*") if p.is_file() and p.suffix in {".py", ".json"})
        source_hashes = {p.relative_to(root).as_posix(): sha256_file(p) for p in files}
        source_digest = hashlib.sha256(canonical_json(source_hashes).encode()).hexdigest()
        existing = sys.modules.get("mobileclip")
        if existing is not None and Path(existing.__file__).resolve() != root / "mobileclip" / "__init__.py":
            raise ValueError("another mobileclip checkout is already imported")
        sys.path.insert(0, str(root))
        try:
            torch = importlib.import_module("torch")
            official = importlib.import_module("mobileclip")
            clip_tokenizer = importlib.import_module("open_clip.tokenizer")
        except ImportError as exc:
            raise RuntimeError(f"official model dependency missing: {exc}") from exc
        if Path(official.__file__).resolve() != root / "mobileclip" / "__init__.py":
            raise ValueError("mobileclip import did not resolve to explicit checkout")
        if type(cpu_threads) is not int or cpu_threads <= 0:
            raise ValueError("cpu_threads must be positive")
        if device == "cpu":
            torch.set_num_threads(cpu_threads)
        config = json.loads((root / "mobileclip" / "configs" / "mobileclip_s1.json").read_text())
        # Keep torch.load explicitly restricted even when caller environment differs.
        state = torch.load(str(weight), map_location="cpu", weights_only=True)
        model, _, self.preprocess = official.create_model_and_transforms(model_name, pretrained=None, reparameterize=False, device=device)
        model.load_state_dict(state, strict=True)
        del state
        model.eval()
        if reparameterize:
            model = official.reparameterize_model(model)
        self.model, self.tokenizer, self.torch, self.device = model.eval(), official.get_tokenizer(model_name), torch, device
        self.dimension = config["embed_dim"]
        dependencies = {p: importlib.metadata.version(p) for p in ("torch", "torchvision", "timm", "open-clip-torch", "numpy", "Pillow", "ftfy", "regex")}
        bpe = Path(clip_tokenizer.default_bpe())
        self._identity = {
            "schema_version": 1, "backend": "official-mobileclip-pytorch", "model": model_name,
            "weight_sha256": S1_WEIGHT_SHA256, "code_revision": revision, "code_sha256": source_digest,
            "tokenizer": {"implementation": "mobileclip.ClipTokenizer/open_clip.SimpleTokenizer", "context_length": config["text_cfg"]["context_length"], "bpe_sha256": sha256_file(bpe), "module_sha256": sha256_file(clip_tokenizer.__file__)},
            "preprocess": {"rgb": True, "resize_short_side": config["image_cfg"]["image_size"], "crop": [256, 256], "interpolation": "BILINEAR", "antialias": True, "to_tensor": "float32/255", "mean": None, "std": None, "official_transform_repr": repr(self.preprocess)},
            "dimension": self.dimension, "dtype": "float32", "normalization": {"encoder": "raw-float32", "persisted": "l2-float32-v1"},
            "dependencies": dependencies, "device": str(device), "reparameterized": bool(reparameterize),
        }

    def identity(self):
        return deepcopy(self._identity)

    def preprocess_image(self, image):
        if isinstance(image, (str, Path)):
            with Image.open(image) as opened:
                return self.preprocess(opened.convert("RGB"))
        if not isinstance(image, Image.Image):
            raise ValueError("images must be PIL images or explicit paths")
        return self.preprocess(image.convert("RGB"))

    def _features(self, tensor, count):
        features = tensor.detach().to(device="cpu", dtype=self.torch.float32).numpy()
        if features.shape != (count, self.dimension):
            raise ValueError("official model returned unexpected feature shape")
        normalize_rows(features)
        return features

    def encode_images(self, images):
        images = list(images)
        if not images:
            raise ValueError("no images")
        # batch=1 keeps image activation memory bounded; output preserves input order.
        rows = []
        with self.torch.inference_mode():
            for image in images:
                tensor = self.preprocess_image(image).unsqueeze(0).to(self.device)
                rows.append(self._features(self.model.encode_image(tensor), 1))
        return np.concatenate(rows, axis=0)

    def encode_texts(self, texts):
        texts = list(texts)
        if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("texts must be nonempty strings")
        with self.torch.inference_mode():
            tokens = self.tokenizer(texts).to(self.device)
            return self._features(self.model.encode_text(tokens), len(texts))
