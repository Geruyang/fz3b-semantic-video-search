import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
import axi_dw_overlay as dw


def test_independent_node_shared_lock_and_fixed_blob_identity():
    source = Path(dw.__file__).read_text()
    assert dw.BASE == Path('/root/board-debug-dw-20261004')
    assert dw.COMPATIBLE == b'fz3b,axi-dw-c2\0'
    assert dw.DTBO_SHA == '378a67929ebd742a3e809db1600aa86523379bf516578df8e554dffc4198a669'
    assert "/root/board-debug-hpm-20261004/state/uio-lifecycle.lock" in source


def test_any_operator_uio_overlap_blocks_dw():
    for identity in ('fz3b-axi-dot-c1', 'fz3b-axi-dw-c2', 'other'):
        with pytest.raises(RuntimeError, match='overlaps'):
            dw.require_uio_aperture_idle({'uio1': {'name': identity, 'maps': {
                'map0': {'addr': '0xa4000000', 'size': '0x10000', 'offset': '0'}}}})


def test_original_uio_maps_and_empty_declared_conflicts_are_allowed():
    dw.require_uio_aperture_idle({'uio0': {'maps': {
        'map0': {'addr': '0xffa00000', 'size': '0x10000', 'offset': '0'}}}})
    with pytest.raises(RuntimeError):
        dw.require_uio_aperture_idle({'uio1': {'maps': {'map0': {'addr': '0xa0000000'}}}})
