from copy import deepcopy
import pytest
from desktop_vlm.gallery import build_gallery, load_gallery, query_gallery


def image_items(tmp_path):
    paths = [tmp_path / "cup.jpg", tmp_path / "phone.jpg"]
    for i, p in enumerate(paths): p.write_bytes(bytes([i]))
    return [{"item_id": "cup", "label": "杯子", "path": paths[0]}, {"item_id": "phone", "label": "手机", "path": paths[1]}]


def test_gallery_ties_exclude_and_identity(tmp_path, encoder, identity):
    items = image_items(tmp_path)
    path = tmp_path / "gallery.npz"
    gid = build_gallery(encoder, items, path)
    loaded = load_gallery(path, identity)
    assert loaded["gallery_id"] == gid
    assert [r["item_id"] for r in query_gallery(encoder, items[0]["path"], loaded)] == ["cup", "phone"]
    assert [r["item_id"] for r in query_gallery(encoder, items[0]["path"], loaded, exclude_same_image=True)] == ["phone"]
    other = deepcopy(identity)
    other["preprocess"] = {"changed": True}
    with pytest.raises(ValueError): load_gallery(path, other)


def test_empty_duplicate_all_excluded(tmp_path, encoder, identity):
    with pytest.raises(ValueError): build_gallery(encoder, [], tmp_path / "g.npz")
    items = image_items(tmp_path)
    with pytest.raises(ValueError): build_gallery(encoder, [items[0], items[0]], tmp_path / "g.npz")
    build_gallery(encoder, [items[0]], tmp_path / "g.npz")
    with pytest.raises(ValueError, match="eligible"):
        query_gallery(encoder, items[0]["path"], load_gallery(tmp_path / "g.npz", identity), exclude_same_image=True)
