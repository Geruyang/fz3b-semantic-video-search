import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn_v10_mixed_n1_mask_search import expanded_masks


def test_expanded_masks_preserve_existing_channels_and_follow_error_rank():
    scores = np.arange(128, dtype=np.float64)
    frozen = [101, 125, 122, 81, 40, 78, 124]
    masks = expanded_masks(scores, frozen)
    for size in (16, 32, 64):
        assert len(masks[size]) == size
        assert set(frozen).issubset(masks[size])
    additions = [c for c in masks[16] if c not in frozen]
    assert additions == [116, 117, 118, 119, 120, 121, 123, 126, 127]
    assert masks[16] == sorted(masks[16])
