#!/usr/bin/env python3
"""Match the MobileCLIP-S1 PIL resize/center-crop/to-tensor path on Python 3.6."""
import hashlib
import json
import os
import sys

import numpy as np
import PIL
from PIL import Image


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def preprocess(path):
    image = Image.open(path).convert("RGB")
    width, height = image.size
    short, long = min(width, height), max(width, height)
    new_short = 256
    new_long = int(new_short * long / short)
    if width <= height:
        resized = image.resize((new_short, new_long), Image.BILINEAR)
    else:
        resized = image.resize((new_long, new_short), Image.BILINEAR)
    left = int(round((resized.size[0] - 256) / 2.0))
    top = int(round((resized.size[1] - 256) / 2.0))
    crop = resized.crop((left, top, left + 256, top + 256))
    array = np.asarray(crop, dtype=np.uint8).astype(np.float32) / np.float32(255.0)
    chw = np.transpose(array, (2, 0, 1)).copy()
    return chw, {"source_size": [width, height], "resized_size": list(resized.size),
                 "crop_xywh": [left, top, 256, 256], "layout": "NCHW",
                 "shape": [1, 3, 256, 256], "dtype": "little-endian-float32"}


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: preprocess_s1.py INPUT_IMAGE OUTPUT_NCHW.f32")
    source, target = argv[1:]
    data, info = preprocess(source)
    data.astype("<f4", copy=False).tofile(target)
    info.update({"source": os.path.abspath(source), "source_sha256": sha256(source),
                 "output": os.path.abspath(target), "output_bytes": os.path.getsize(target),
                 "output_sha256": sha256(target), "pil_version": PIL.__version__,
                 "numpy_version": np.__version__})
    print(json.dumps(info, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv)
