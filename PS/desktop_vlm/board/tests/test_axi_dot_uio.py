import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from axi_dot_client import AxiDotBusyError, AxiDotClient, AxiDotProtocolError
from axi_dot_uio import (AxiDotUioBusError, AxiDotUioIdentityError,
                         AxiDotUioProtocolError, AxiDotUioTimeoutError,
                         AxiDotUioProcessError, AxiDotUioAccessor, EXPECTED_COMPATIBLE)
from axi_dot_uio_smoke import FIXTURE_SHA256, load_jobs
import axi_dot_uio


class FakeClock(object):
    def __init__(self):
        self.now = 0.0
        self.hang = False

    def monotonic(self):
        return self.now

    def wait_readable(self, _fd, timeout):
        if self.hang:
            self.now += timeout
            return False
        return True


def make_sysfs(tmp_path, index=1, variation=None):
    root = tmp_path / "sys-class-uio"
    dev_root = tmp_path / "dev"
    firmware_root = tmp_path / "firmware" / "devicetree" / "base"
    node = root / ("uio%d" % index)
    device = node / "device"
    of_node = device / "of_node"
    device_target = tmp_path / "platform-device" / (
        "wrong-device" if variation == "device_basename" else "a4000000.fz3b-axi-dot-c1")
    of_node_target = firmware_root / "amba_pl@0" / "fz3b-axi-dot-c1@a4000000"
    if variation == "of_path":
        of_node_target = firmware_root / "wrong-bus" / "fz3b-axi-dot-c1@a4000000"
    maps = node / "maps" / "map0"
    for directory in (device / "driver" / "uio_pdrv_genirq", of_node, maps, dev_root,
                      device_target, of_node_target):
        directory.mkdir(parents=True, exist_ok=True)
    (node / "name").write_text("not-the-uio-name\n" if variation == "name" else "fz3b-axi-dot-c1\n")
    (of_node_target / "compatible").write_bytes(
        (b"wrong,compatible\x00" if variation == "compatible" else EXPECTED_COMPATIBLE.encode("ascii") + b"\x00"))
    (of_node_target / "reg").write_bytes(
        b"\x00" * 16 if variation == "reg" else bytes.fromhex("00000000a40000000000000000010000"))
    if variation == "driver":
        bad = device / "driver" / "other_driver"
        bad.mkdir()
        import shutil
        shutil.rmtree(device / "driver" / "uio_pdrv_genirq")
        (device / "driver").mkdir(exist_ok=True)
        # Keep the driver path itself named as the wrong driver.
        (device / "driver" / "other_driver").mkdir(exist_ok=True)
    attrs = {"addr": "0xa4000000", "size": "0x10000", "offset": "0x0"}
    if variation == "base":
        attrs["addr"] = "0xa4001000"
    elif variation == "size":
        attrs["size"] = "0x2000"
    elif variation == "offset":
        attrs["offset"] = "0x1000"
    for name, value in attrs.items():
        (maps / name).write_text(value + "\n")
    (node / "dev").write_text("242:1\n")
    (dev_root / ("uio%d" % index)).write_bytes(b"test node")
    if variation == "missing_of_node":
        import shutil
        shutil.rmtree(of_node)
    return str(root), str(dev_root)


def make_realpath_reader(sysfs_root, index=1, variation=None):
    driver = "other_driver" if variation == "driver" else "uio_pdrv_genirq"
    driver_path = os.path.normpath(os.path.join(sysfs_root, "uio%d" % index, "device", "driver"))
    device_path = os.path.normpath(os.path.join(sysfs_root, "uio%d" % index, "device"))
    tmp_path = Path(sysfs_root).parent
    device_target = tmp_path / "platform-device" / (
        "wrong-device" if variation == "device_basename" else "a4000000.fz3b-axi-dot-c1")
    firmware_root = tmp_path / "firmware" / "devicetree" / "base"
    of_node_path = os.path.normpath(os.path.join(sysfs_root, "uio%d" % index, "device", "of_node"))
    of_node_target = firmware_root / ("wrong-bus" if variation == "of_path" else "amba_pl@0") / "fz3b-axi-dot-c1@a4000000"
    if variation == "missing_of_node":
        of_node_target = tmp_path / "missing-of-node"

    def resolve(path):
        normalized = os.path.normpath(path)
        if normalized == device_path:
            return str(device_target)
        if normalized == of_node_path:
            return str(of_node_target)
        if normalized == driver_path:
            return os.path.join(os.path.dirname(driver_path), "driver", driver)
        return os.path.realpath(path)
    return resolve


def firmware_root_for(sysfs_root):
    return str(Path(sysfs_root).parent / "firmware" / "devicetree" / "base")


def make_helper(tmp_path, mode="normal", marker=None):
    script = tmp_path / "fake_uio_helper.py"
    marker_path = str(marker) if marker else ""
    source = r'''import json, os, sys
mode = sys.argv[1]
index = int(sys.argv[2])
marker = MARKER
ready = {"protocol":"axi-dot-uio-v1", "uio_index":index,
         "name":"fz3b-axi-dot-c1", "driver":"uio_pdrv_genirq",
         "map_addr":"0xa4000000", "map_size":65536, "map_offset":0,
         "compatible":"fz3b,axi-dot-c1", "dev_major":242, "dev_minor":1}
if mode == "bad_metadata":
    ready["map_size"] = 8192
sys.stdout.write(json.dumps(ready) + "\n")
sys.stdout.flush()
if mode == "exit_after_startup":
    sys.exit(9)
registers = {0:0x465a4331, 8:(1 if mode == "busy" else 0), 12:1,
             16:0, 20:0, 24:0}
for line in sys.stdin:
    fields = line.strip().split()
    if not fields:
        continue
    if marker and fields[0] == "W":
        with open(marker, "a") as stream:
            stream.write(line)
    if mode == "hang" and fields[0] == "R":
        sys.exit(0)
    if fields[0] == "R" and len(fields) == 2:
        offset = int(fields[1], 16)
        value = 0 if mode == "wrong_id" and offset == 0 else registers.get(offset, 0)
        sys.stdout.write("OK +0000001\n" if mode == "bad_read_token" else "OK %08x\n" % value)
    elif fields[0] == "W" and len(fields) == 3:
        if mode == "slverr":
            sys.stdout.write("ERR SLVERR\n")
        elif mode == "write_payload":
            sys.stdout.write("OK 00000000\n")
        else:
            sys.stdout.write("OK\n")
    else:
        sys.stdout.write("ERR BAD_COMMAND\n")
    sys.stdout.flush()
'''.replace("MARKER", repr(marker_path)).replace("MODE", repr(mode))
    # mode is also supplied as argv so the child fixture can be reused with
    # a static script path and still exercise different pipe replies.
    script.write_text(source, encoding="utf-8")
    return [sys.executable, str(script), mode]


def make_accessor(tmp_path, mode="normal", variation=None, index=1, clock=None,
                  dev_identity=(True, 242, 1), marker=None):
    sysfs_root, dev_root = make_sysfs(tmp_path, index=index, variation=variation)
    helper = make_helper(tmp_path, mode=mode, marker=marker)
    timeout_clock = clock or FakeClock()
    return AxiDotUioAccessor(index, helper_command=helper, sysfs_root=sysfs_root,
                              dev_root=dev_root,
                              firmware_root=firmware_root_for(sysfs_root),
                              devstat_reader=lambda _path: dev_identity,
                              wait_readable=timeout_clock.wait_readable,
                              clock=timeout_clock.monotonic,
                              realpath_fn=make_realpath_reader(sysfs_root, index, variation)), timeout_clock


def test_valid_sysfs_identity_and_helper_pipe_read_write(tmp_path):
    marker = tmp_path / "writes.txt"
    accessor, _clock = make_accessor(tmp_path, marker=marker)
    try:
        assert accessor.read32(0) == 0x465A4331
        accessor.write32(4, 3, 1)
        assert marker.read_text().strip() == "W 00000004 00000003"
    finally:
        accessor.close()


@pytest.mark.parametrize("variation", ["name", "base", "size", "offset", "driver", "compatible", "missing_of_node",
                                       "device_basename", "of_path", "reg"])
def test_wrong_sysfs_identity_is_rejected_before_helper_start(tmp_path, variation):
    helper_marker = tmp_path / "helper-started"
    helper = make_helper(tmp_path, marker=helper_marker)
    sysfs_root, dev_root = make_sysfs(tmp_path, variation=variation)
    with pytest.raises(AxiDotUioIdentityError):
        AxiDotUioAccessor(1, helper_command=helper, sysfs_root=sysfs_root,
                          dev_root=dev_root, firmware_root=firmware_root_for(sysfs_root),
                          devstat_reader=lambda _path: (True, 242, 1),
                          wait_readable=lambda _fd, _timeout: True,
                          realpath_fn=make_realpath_reader(sysfs_root, 1, variation))
    assert not helper_marker.exists()


def test_uio0_and_major_minor_mismatch_are_rejected(tmp_path):
    sysfs_root, dev_root = make_sysfs(tmp_path, index=0)
    with pytest.raises(ValueError, match="uio0"):
        AxiDotUioAccessor(0, helper_command=[sys.executable, "missing"],
                          sysfs_root=sysfs_root, dev_root=dev_root)

    sysfs_root, dev_root = make_sysfs(tmp_path)
    with pytest.raises(AxiDotUioIdentityError, match="major/minor"):
        AxiDotUioAccessor(1, helper_command=[sys.executable, "missing"],
                          sysfs_root=sysfs_root, dev_root=dev_root,
                          firmware_root=firmware_root_for(sysfs_root),
                          devstat_reader=lambda _path: (True, 242, 2),
                          realpath_fn=make_realpath_reader(sysfs_root))


def test_helper_metadata_is_independently_checked(tmp_path):
    sysfs_root, dev_root = make_sysfs(tmp_path)
    helper = make_helper(tmp_path, mode="bad_metadata")
    with pytest.raises(AxiDotUioIdentityError, match="map_size"):
        AxiDotUioAccessor(1, helper_command=helper, sysfs_root=sysfs_root,
                          dev_root=dev_root, devstat_reader=lambda _path: (True, 242, 1),
                          firmware_root=firmware_root_for(sysfs_root),
                          wait_readable=lambda _fd, _timeout: True,
                          realpath_fn=make_realpath_reader(sysfs_root))


def test_offsets_wstrb_and_reserved_values_are_checked_before_pipe_write(tmp_path):
    marker = tmp_path / "writes.txt"
    accessor, _clock = make_accessor(tmp_path, marker=marker)
    try:
        with pytest.raises(ValueError, match="read offset"):
            accessor.read32(0x2)
        with pytest.raises(ValueError, match="read offset"):
            accessor.read32(0x10000)
        with pytest.raises(ValueError, match="WSTRB"):
            accessor.write32(4, 3, 3)
        with pytest.raises(ValueError, match="reserved"):
            accessor.write32(4, 0x10003, 1)
        with pytest.raises(ValueError, match="upper reserved"):
            accessor.write32(0x1000, 0x00010001, 3)
        assert not marker.exists()
    finally:
        accessor.close()


def test_wrong_helper_read_value_fails_high_level_client_without_start(tmp_path):
    marker = tmp_path / "writes.txt"
    accessor, _clock = make_accessor(tmp_path, mode="wrong_id", marker=marker)
    try:
        client = AxiDotClient(accessor.read32, accessor.write32)
        with pytest.raises(AxiDotProtocolError, match="device ID mismatch"):
            client.run([(1, 1)])
        assert not marker.exists()
    finally:
        accessor.close()


def test_busy_job_is_preserved_through_client_integration(tmp_path):
    marker = tmp_path / "writes.txt"
    accessor, _clock = make_accessor(tmp_path, mode="busy", marker=marker)
    try:
        client = AxiDotClient(accessor.read32, accessor.write32)
        with pytest.raises(AxiDotBusyError):
            client.run([(5, 7)])
        assert not marker.exists()
    finally:
        accessor.close()


def test_timeout_uses_injected_clock_without_real_sleep_or_retry(tmp_path):
    clock = FakeClock()
    accessor, _clock = make_accessor(tmp_path, mode="hang", clock=clock)
    try:
        clock.hang = True
        with pytest.raises(AxiDotUioTimeoutError, match="may still be blocked"):
            accessor.read32(0)
        assert accessor._poisoned
    finally:
        accessor.close()


def test_helper_slverr_and_child_pipe_eof_are_explicit(tmp_path):
    accessor, _clock = make_accessor(tmp_path, mode="slverr")
    try:
        with pytest.raises(AxiDotUioBusError, match="SLVERR"):
            accessor.write32(4, 3, 1)
    finally:
        accessor.close()


def test_child_exit_and_pipe_eof_are_reported_as_transport_failure(tmp_path):
    accessor, _clock = make_accessor(tmp_path, mode="exit_after_startup")
    try:
        with pytest.raises(AxiDotUioBusError, match="closed its response pipe"):
            accessor.read32(0)
    finally:
        accessor.close()


def test_read_token_requires_exact_uint32_hex_and_poisons_pipe(tmp_path):
    accessor, _clock = make_accessor(tmp_path, mode="bad_read_token")
    try:
        with pytest.raises(AxiDotUioProtocolError, match="malformed uint32"):
            accessor.read32(0)
        assert accessor._poisoned
        with pytest.raises(AxiDotUioBusError, match="unusable"):
            accessor.read32(0)
    finally:
        accessor.close()


def test_write_rejects_unexpected_response_payload_and_poisons_pipe(tmp_path):
    accessor, _clock = make_accessor(tmp_path, mode="write_payload")
    try:
        with pytest.raises(AxiDotUioProtocolError, match="unexpected payload"):
            accessor.write32(4, 3, 1)
        assert accessor._poisoned
        with pytest.raises(AxiDotUioBusError, match="unusable"):
            accessor.read32(0)
    finally:
        accessor.close()


def test_boolean_wstrb_is_rejected_before_pipe_write(tmp_path):
    marker = tmp_path / "writes.txt"
    accessor, _clock = make_accessor(tmp_path, marker=marker)
    try:
        with pytest.raises(ValueError, match="integer mask"):
            accessor.write32(4, 1, True)
        assert not marker.exists()
    finally:
        accessor.close()


class _NeverExitProcess(object):
    def __init__(self):
        self.stdin = _Closable()
        self.stdout = _Closable()
        self.stderr = _Closable()
        self.wait_calls = 0

    def poll(self):
        return None

    def wait(self, timeout=None):
        self.wait_calls += 1
        raise axi_dot_uio.subprocess.TimeoutExpired("fake-helper", timeout)

    def terminate(self):
        pass

    def kill(self):
        pass


class _Closable(object):
    def close(self):
        pass


def test_close_reports_unreaped_helper_and_keeps_overlay_blocked():
    accessor = AxiDotUioAccessor.__new__(AxiDotUioAccessor)
    accessor._closed = False
    accessor.process = _NeverExitProcess()
    with pytest.raises(AxiDotUioProcessError, match="do not remove the overlay"):
        accessor.close()
    assert accessor.process.wait_calls == 3
    assert accessor._closed is False


def test_frozen_smoke_fixture_is_pinned_and_scalar_validated():
    fixture_path = (Path(__file__).resolve().parents[3] / "artifacts" /
                    "board-debug-20261004" / "acceleration" / "host" /
                    "axi-dot-jobs-001.json")
    jobs = load_jobs(str(fixture_path))
    assert len(jobs) == 18
    assert FIXTURE_SHA256 == "9071cf690a7046275111060d83e425a47f10857e126ffcd766bff2e2d7d27b89"


def test_frozen_smoke_fixture_rejects_modified_bytes(tmp_path):
    altered = tmp_path / "jobs.json"
    altered.write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="SHA256"):
        load_jobs(str(altered))

