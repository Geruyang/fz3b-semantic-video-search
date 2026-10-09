import numpy as np
import pytest
from desktop_vlm.matching import cosine_scores, normalize_rows, rank_scores


def test_known_cosines_and_stable_ties():
    scores = cosine_scores([[1, 0]], [[1, 0], [0, 1], [-1, 0], [1, 0]])[0]
    np.testing.assert_allclose(scores, [1, 0, -1, 1], atol=1e-6)
    assert rank_scores(scores, 9) == [0, 3, 1, 2]


@pytest.mark.parametrize("bad", [[[0, 0]], [[float("nan"), 1]], [[float("inf"), 1]], [], [1, 2]])
def test_invalid_features(bad):
    with pytest.raises(ValueError):
        normalize_rows(bad)


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_invalid_k(bad):
    with pytest.raises(ValueError):
        rank_scores([1, 0], bad)


def test_dimensions_and_dtype():
    with pytest.raises(ValueError):
        cosine_scores([[1, 0]], [[1, 0, 0]])
    assert normalize_rows(np.array([[1, 2]], dtype=np.float64)).dtype == np.float64
    assert normalize_rows([[1, 2]]).dtype == np.float32
    np.testing.assert_allclose(normalize_rows([[1e300, 1e300]]), [[2 ** -0.5] * 2], atol=1e-6)
