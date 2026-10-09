import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from axi_dot_overlay import mmio_owners, original_uio_unchanged, parse_iomem_conflicts, validate_parent, require_uio_aperture_idle


def test_aperture_check_rejects_cross_operator_and_partial_overlaps():
    for name in ('fz3b-axi-dot-c1', 'fz3b-axi-dw-c2', 'unrelated'):
        for address, size in (('0xa4000000', '0x10000'), ('0xa3fff000', '0x2000'), ('0xa400ffff', '1')):
            entry = {'uio1': {'name': name, 'maps': {'map0': {'addr': address, 'size': size, 'offset': '0'}}}}
            with pytest.raises(RuntimeError, match='overlaps'):
                require_uio_aperture_idle(entry)


def test_aperture_check_allows_original_pmon_and_disjoint_maps():
    require_uio_aperture_idle({'uio0': {'maps': {
        'map0': {'addr': '0xffa00000', 'size': '0x10000', 'offset': '0'},
        'map1': {'addr': '0xffffffc87c4f3000', 'size': '4096', 'offset': '0'}}}})
    require_uio_aperture_idle({'uio2': {'maps': {'map0': {'addr': '0xa4010000', 'size': '4096', 'offset': '0'}}}})


@pytest.mark.parametrize('mapping', [
    {}, {'addr': 'garbage', 'size': '4096', 'offset': '0'},
    {'addr': '0xffa00000', 'size': '0', 'offset': '0'},
    {'addr': '0xffa00000', 'size': '4096', 'offset': '4096'},
    {'addr': '0xffffffffffffffff', 'size': '2', 'offset': '0'}, 'unreadable'])
def test_aperture_check_does_not_treat_incomplete_metadata_as_idle(mapping):
    with pytest.raises(RuntimeError):
        require_uio_aperture_idle({'uio1': {'maps': {'map0': mapping}}})


def test_iomem_full_and_partial_conflicts_only():
    text = 'a0000000-a000ffff : fpgadrv\n a4000000-a400ffff : owned\n a3ffffff-a4000000 : partial\n a4010000-a401ffff : next\n'
    assert parse_iomem_conflicts(text) == [' a4000000-a400ffff : owned', ' a3ffffff-a4000000 : partial']
    assert parse_iomem_conflicts('a0000000-a000ffff : fpgadrv\n') == []


def test_parent_identity_requires_known_cells_and_empty_ranges():
    good = {'#address-cells': bytes.fromhex('00000002'), '#size-cells': bytes.fromhex('00000002'), 'ranges': b''}
    validate_parent(good)
    for name in good:
        changed = dict(good)
        changed[name] = b'wrong'
        with pytest.raises(RuntimeError):
            validate_parent(changed)


def test_existing_uio_identity_must_remain_exact():
    old = {'uio0': {'name': 'axi-pmon', 'maps': {'map0': 'FFA00000'}}}
    current = dict(old, uio1={'name': 'fz3b-axi-dot-c1'})
    assert original_uio_unchanged(old, current, 'uio1')
    assert not original_uio_unchanged(old, current)
    changed = dict(current, uio0={'name': 'unexpected'})
    assert not original_uio_unchanged(old, changed, 'uio1')


def test_owner_scan_detects_fd_and_mapping_and_preserves_errors(tmp_path, monkeypatch):
    import os
    device = tmp_path / 'device'
    device.write_text('')
    proc = tmp_path / 'proc'
    pid = proc / '123'
    (pid / 'fd').mkdir(parents=True)
    (pid / 'comm').write_text('accessor\n')
    (pid / 'fd/1').write_text('')
    (pid / 'maps').write_text('1000-2000 rw-s 00000000 00:00 1 ' + str(device) + '\n')
    monkeypatch.setattr(os, 'readlink', lambda path: str(device))
    owners, errors = mmio_owners(str(device), proc)
    assert [entry.get('fd') for entry in owners] == ['1', None]
    assert errors == []
    (pid / 'maps').unlink()
    owners, errors = mmio_owners(str(device), proc)
    assert len(owners) == 1 and len(errors) == 1


def test_owner_scan_clean_case(tmp_path):
    device = tmp_path / 'device'
    device.write_text('')
    proc = tmp_path / 'proc'
    pid = proc / '124'
    (pid / 'fd').mkdir(parents=True)
    (pid / 'comm').write_text('unrelated\n')
    (pid / 'maps').write_text('')
    assert mmio_owners(str(device), proc) == ([], [])
