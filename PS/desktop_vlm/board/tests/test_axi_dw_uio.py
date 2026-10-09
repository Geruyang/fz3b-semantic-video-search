import json
import os
import struct
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from axi_dw_uio import (AxiDwUioAccessor, AxiDwUioBusError,
                        AxiDwUioIdentityError, AxiDwUioProtocolError,
                        AxiDwUioTimeoutError, _load_abi)
from axi_dw_uio_smoke import MANIFEST_SHA256, load_manifest, run_manifest


def make_sysfs(tmp_path, variation=None):
    root = tmp_path / "sys-class-uio"
    dev_root = tmp_path / "dev"
    firmware_root = tmp_path / "firmware" / "devicetree" / "base"
    node = root / "uio1"
    device = node / "device"
    of_node = device / "of_node"
    maps = node / "maps" / "map0"
    device_target = tmp_path / "platform-device" / (
        "wrong-node" if variation == "device" else "a4000000.fz3b-axi-dw-c2")
    of_node_target = firmware_root / "amba_pl@0" / "fz3b-axi-dw-c2@a4000000"
    if variation == "ofpath":
        of_node_target = firmware_root / "wrong-bus" / "fz3b-axi-dw-c2@a4000000"
    for directory in (device / "driver" / "uio_pdrv_genirq", of_node, maps, dev_root,
                      device_target, of_node_target):
        directory.mkdir(parents=True, exist_ok=True)
    (node / "name").write_text("wrong-name\n" if variation == "name" else "fz3b-axi-dw-c2\n")
    (of_node_target / "compatible").write_bytes(
        b"wrong,compatible\x00" if variation == "compatible" else b"fz3b,axi-dw-c2\x00")
    (of_node_target / "reg").write_bytes(
        bytes.fromhex("00000000a40000000000000000010000") if variation != "reg" else b"\x00" * 16)
    attrs = {"addr": "0xa4000000", "size": "0x10000", "offset": "0x0"}
    if variation == "base":
        attrs["addr"] = "0xa4001000"
    for key, value in attrs.items():
        (maps / key).write_text(value + "\n")
    (node / "dev").write_text("242:2\n")
    (dev_root / "uio1").write_bytes(b"fake char device")
    return str(root), str(dev_root), str(firmware_root)


def realpath_reader(sysfs_root, firmware_root, variation=None):
    device_path = os.path.normpath(os.path.join(sysfs_root, "uio1", "device"))
    of_node_path = os.path.normpath(os.path.join(device_path, "of_node"))
    driver_path = os.path.normpath(os.path.join(device_path, "driver"))
    temp_root = Path(sysfs_root).parent
    device_target = temp_root / "platform-device" / (
        "wrong-node" if variation == "device" else "a4000000.fz3b-axi-dw-c2")
    of_node_target = Path(firmware_root) / ("wrong-bus" if variation == "ofpath" else "amba_pl@0") / "fz3b-axi-dw-c2@a4000000"
    def resolve(path):
        path = os.path.normpath(path)
        if path == device_path:
            return str(device_target)
        if path == of_node_path:
            return str(of_node_target)
        if path == driver_path:
            return str(Path(device_path) / "driver" / "uio_pdrv_genirq")
        return os.path.realpath(path)
    return resolve


def helper_script(tmp_path, mode="normal", marker=None):
    path = tmp_path / "fake_dw_helper.py"
    marker_value = str(marker) if marker else ""
    source = r'''import json, os, struct, sys, time
mode = sys.argv[1]
ready = {"protocol":"axi-dw-uio-v1", "abi":"FZC2-dw7-v1",
         "abi_sha256":"0366ab415fc2c0262a20694237245269af1e4023a3f3f38cc0b077b31f62d2ae", "uio_index":1,
         "name":"fz3b-axi-dw-c2", "driver":"uio_pdrv_genirq",
         "compatible":"fz3b,axi-dw-c2", "map_addr":"0xa4000000",
         "map_size":65536, "map_offset":0, "dev_major":242, "dev_minor":2,
         "device_basename":"a4000000.fz3b-axi-dw-c2",
         "of_node":"/sys/firmware/devicetree/base/amba_pl@0/fz3b-axi-dw-c2@a4000000",
         "reg":"00000000a40000000000000000010000", "mmio_identity_verified":False}
if "--identity-only" in sys.argv:
    identity = {"protocol":"axi-dw-uio-v1", "abi":"FZC2-dw7-v1",
                "abi_sha256":"0366ab415fc2c0262a20694237245269af1e4023a3f3f38cc0b077b31f62d2ae",
                "uio_index":1, "name":"fz3b-axi-dw-c2", "driver":"uio_pdrv_genirq",
                "compatible":"fz3b,axi-dw-c2", "map_addr":"0xa4000000",
                "map_size":65536, "map_offset":0, "dev_major":242, "dev_minor":2,
                "device_basename":"a4000000.fz3b-axi-dw-c2",
                "of_node":"/sys/firmware/devicetree/base/amba_pl@0/fz3b-axi-dw-c2@a4000000",
                "reg":"00000000a40000000000000000010000",
                "mmio_identity_verified":True, "id":0x465A4332, "shape":0x00072020,
                "status":0, "job_id":0, "output_count":0, "pixel_count":0,
                "weight_count":0, "cycles":0}
    if mode == "bad_identity": identity["job_id"] = 1
    if mode == "bad_status": identity["status"] = 1
    if mode == "bad_count_baseline": identity["pixel_count"] = 2
    if mode == "bad_cycles_baseline": identity["cycles"] = 3
    sys.stdout.write(json.dumps(identity) + "\n"); sys.stdout.flush()
    sys.exit(0 if mode != "bad_identity" else 3)
if mode == "bad_ready": ready["abi"] = "wrong"
if mode == "long_ready": ready["padding"] = "x" * 70000
sys.stdout.write(json.dumps(ready) + "\n"); sys.stdout.flush()
marker = MARKER
job_id = 16 if mode == "start_at_17" else 0
expected_request_id = 1
while True:
    header = sys.stdin.buffer.read(12)
    if not header: break
    if len(header) != 12 or header[:4] != b"DWJ2": sys.exit(10)
    request_id, payload_len = struct.unpack("<II", header[4:])
    if payload_len != 1073: sys.exit(11)
    payload = sys.stdin.buffer.read(payload_len)
    if len(payload) != payload_len: sys.exit(12)
    if request_id != expected_request_id: sys.exit(15)
    if marker:
        with open(marker, "ab") as out: out.write(header + payload)
    if mode == "hang": continue
    if mode == "wrong_request": request_id = (request_id + 1) & 0xffffffff
    if mode == "float_request": request_id = float(request_id)
    if mode == "fail": sys.exit(13)
    weights = struct.unpack("<49b", payload[:49])
    pixels = struct.unpack("<1024b", payload[49:])
    outputs = []
    for y in range(32):
        for x in range(32):
            acc = 0
            for ky in range(7):
                iy = y + ky - 3
                for kx in range(7):
                    ix = x + kx - 3
                    if 0 <= iy < 32 and 0 <= ix < 32:
                        acc += weights[ky * 7 + kx] * pixels[iy * 32 + ix]
            outputs.append(acc)
    job_id = (job_id + 1) & 0xffffffff
    expected_request_id = (expected_request_id + 1) & 0xffffffff
    meta = {"request_id":request_id, "job_id":job_id, "weight_count":49,
            "pixel_count":1024, "output_count":1024, "cycles":1234}
    if mode == "bad_count": meta["output_count"] = 1023
    if mode == "float_count": meta["output_count"] = 1024.0
    if mode == "bool_cycles": meta["cycles"] = True
    if mode == "short_output":
        sys.stdout.buffer.write((json.dumps(meta) + "\n").encode() + struct.pack("<i", outputs[0]))
        sys.stdout.buffer.flush(); sys.exit(14)
    if mode == "fragmented":
        frame = (json.dumps(meta) + "\n").encode() + struct.pack("<1024i", *outputs)
        for start in range(0, len(frame), 137):
            sys.stdout.buffer.write(frame[start:start + 137])
            sys.stdout.buffer.flush()
            time.sleep(0.0005)
        continue
    sys.stdout.buffer.write((json.dumps(meta) + "\n").encode() + struct.pack("<1024i", *outputs))
    sys.stdout.buffer.flush()
'''.replace("MARKER", repr(marker_value))
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return [sys.executable, str(path), mode]


class FakePipeWait(object):
    def __init__(self, marker=None, hang_after_request=False):
        self.marker = marker
        self.hang_after_request = hang_after_request
        self.now = 0.0

    def monotonic(self):
        return self.now

    def wait_readable(self, _fd, timeout):
        if self.hang_after_request and self.marker and self.marker.exists():
            self.now += timeout
            return False
        return True


def make_accessor(tmp_path, mode="normal", variation=None, marker=None, timeout=1.0):
    sysfs_root, dev_root, firmware_root = make_sysfs(tmp_path, variation)
    if mode == "hang" and marker is None:
        marker = tmp_path / "frames.bin"
    pipe_wait = FakePipeWait(marker, hang_after_request=(mode == "hang"))
    return AxiDwUioAccessor(1, helper_command=helper_script(tmp_path, mode, marker),
                            sysfs_root=sysfs_root, dev_root=dev_root,
                            firmware_root=firmware_root,
                            devstat_reader=lambda _path: (True, 242, 2),
                            realpath_fn=realpath_reader(sysfs_root, firmware_root, variation),
                            wait_readable=pipe_wait.wait_readable, clock=pipe_wait.monotonic,
                            read_timeout_s=timeout)


def make_identity_accessor(tmp_path, mode="normal"):
    sysfs_root, dev_root, firmware_root = make_sysfs(tmp_path)
    return AxiDwUioAccessor(1, helper_command=helper_script(tmp_path, mode),
                            sysfs_root=sysfs_root, dev_root=dev_root,
                            firmware_root=firmware_root,
                            devstat_reader=lambda _path: (True, 242, 2),
                            realpath_fn=realpath_reader(sysfs_root, firmware_root),
                            wait_readable=lambda _fd, _timeout: True,
                            identity_only=True)


def reference_depthwise(weights, pixels):
    result = []
    for y in range(32):
        for x in range(32):
            total = 0
            for ky in range(7):
                iy = y + ky - 3
                for kx in range(7):
                    ix = x + kx - 3
                    if 0 <= iy < 32 and 0 <= ix < 32:
                        total += weights[ky * 7 + kx] * pixels[iy * 32 + ix]
            result.append(total)
    return result


def test_fixed_identity_and_two_tasks_share_one_binary_helper(tmp_path):
    marker = tmp_path / "frames.bin"
    accessor = make_accessor(tmp_path, marker=marker)
    try:
        weights = [-128, -1] + [i - 24 for i in range(47)]
        pixels = [127 if i % 2 else -128 for i in range(1024)]
        first = accessor.run([weights[i:i + 7] for i in range(0, 49, 7)],
                             [pixels[i:i + 32] for i in range(0, 1024, 32)])
        second = accessor.run([1] * 49, [1] * 1024)
        assert first["outputs"] == struct.pack("<1024i", *reference_depthwise(weights, pixels))
        assert first["output_shape"] == (32, 32)
        assert first["outputs_dtype"] == "<i4"
        assert (first["weight_count"], first["pixel_count"], first["output_count"]) == (49, 1024, 1024)
        assert first["request_id"] == 1 and second["request_id"] == 2
        assert first["job_id"] == 1 and second["job_id"] == 2
        frame = marker.read_bytes()
        assert frame[:4] == b"DWJ2"
        assert struct.unpack("<II", frame[4:12]) == (1, 1073)
        assert frame[12:14] == b"\x80\xff"
        assert len(frame) == 2 * (12 + 1073)
    finally:
        accessor.close()


@pytest.mark.parametrize("variation", ["name", "base", "compatible", "reg", "device", "ofpath"])
def test_wrong_device_tree_or_uio_identity_fails_before_helper(tmp_path, variation):
    marker = tmp_path / "frames.bin"
    sysfs_root, dev_root, firmware_root = make_sysfs(tmp_path, variation)
    with pytest.raises(AxiDwUioIdentityError):
        AxiDwUioAccessor(1, helper_command=helper_script(tmp_path, marker=marker),
                         sysfs_root=sysfs_root, dev_root=dev_root, firmware_root=firmware_root,
                         devstat_reader=lambda _path: (True, 242, 2),
                         realpath_fn=realpath_reader(sysfs_root, firmware_root, variation))
    assert not marker.exists()


@pytest.mark.parametrize("field,value", [("weights", [0] * 48), ("pixels", [0] * 1023),
                                          ("weights", [128] + [0] * 48),
                                          ("pixels", [-129] + [0] * 1023),
                                          ("weights", [True] + [0] * 48),
                                          ("pixels", [1.0] + [0] * 1023)])
def test_invalid_input_rejected_before_any_request_is_sent(tmp_path, field, value):
    marker = tmp_path / "frames.bin"
    accessor = make_accessor(tmp_path, marker=marker)
    weights, pixels = [0] * 49, [0] * 1024
    if field == "weights":
        weights = value
    else:
        pixels = value
    try:
        with pytest.raises(ValueError):
            accessor.run(weights, pixels)
        assert not marker.exists()
    finally:
        accessor.close()


def test_int8_numpy_fast_validation_handles_signed_extremes_under_numpy2():
    values = np.array([-128, -1, 0, 127] + [0] * 45, dtype=np.int8)
    encoded = AxiDwUioAccessor._validate_int8_vector(values, 49, "weights")
    assert encoded[:4] == b"\x80\xff\x00\x7f"
    assert len(encoded) == 49


def test_exact_2d_int8_matrix_and_noncontiguous_view_preserve_row_major_bytes():
    base = np.zeros((7, 14), dtype=np.int8)
    matrix = base[:, ::2]
    matrix[0, 0], matrix[0, 1], matrix[6, 6] = -128, -1, 127
    assert matrix.shape == (7, 7)
    assert not matrix.flags.c_contiguous
    actual = AxiDwUioAccessor._validate_int8_vector(
        matrix, 49, "weights", rows=7, columns=7)
    assert actual == matrix.tobytes(order="C")


@pytest.mark.parametrize("values", [
    np.ones(49, dtype=np.uint8),
    np.ones(49, dtype=np.float32),
    np.ones(49, dtype=np.bool_),
    np.ones(49, dtype=object),
    np.ones((1, 49), dtype=np.int8),
])
def test_array_fastpath_rejects_unsigned_float_bool_and_wrong_shape(values):
    with pytest.raises(ValueError):
        AxiDwUioAccessor._validate_int8_vector(values, 49, "weights",
                                               rows=7, columns=7)


def test_list_fallback_converts_integral_scalar_before_range_and_encoding():
    values = list(np.array([-128, -1, 0, 127], dtype=np.int8))
    assert AxiDwUioAccessor._validate_int8_vector(values, 4, "weights") == b"\x80\xff\x00\x7f"


def test_bad_helper_metadata_is_rejected_during_startup(tmp_path):
    with pytest.raises(AxiDwUioIdentityError, match="abi"):
        make_accessor(tmp_path, mode="bad_ready")


def test_json_line_limit_is_preserved_with_bulk_reads(tmp_path):
    with pytest.raises(AxiDwUioProtocolError, match="line exceeded limit"):
        make_accessor(tmp_path, mode="long_ready")


def test_bulk_buffer_preserves_coalesced_json_and_binary_across_requests(tmp_path):
    accessor = make_accessor(tmp_path)
    observed_buffer_lengths = []
    original = accessor._read_buffered

    def observe(deadline, minimum):
        original(deadline, minimum)
        observed_buffer_lengths.append(len(accessor._rx_buffer))

    accessor._read_buffered = observe
    try:
        first = accessor.run([0] * 49, [0] * 1024)
        second = accessor.run([1] * 49, [1] * 1024)
        assert (first["request_id"], second["request_id"]) == (1, 2)
        assert len(first["outputs"]) == len(second["outputs"]) == 4096
        assert max(observed_buffer_lengths) >= 4096
        assert accessor._rx_buffer == bytearray()
    finally:
        accessor.close()


def test_bulk_buffer_reassembles_fragmented_json_and_binary(tmp_path):
    accessor = make_accessor(tmp_path, mode="fragmented")
    try:
        result = accessor.run([2] * 49, [3] * 1024)
        assert result["request_id"] == 1
        assert result["outputs"][0:4] == struct.pack("<i", 16 * 2 * 3)
        assert len(result["outputs"]) == 4096
    finally:
        accessor.close()


@pytest.mark.parametrize("reader_name,cached,expected", [
    ("_read_exact", b"data", (4, 1.0)),
    ("_read_line_with_deadline", b"ready\n", (1.0,)),
])
def test_cached_response_bytes_do_not_bypass_expired_deadline(
        tmp_path, reader_name, cached, expected):
    accessor = make_accessor(tmp_path)
    accessor._rx_buffer.extend(cached)
    accessor._clock = lambda: 2.0
    try:
        with pytest.raises(AxiDwUioTimeoutError):
            getattr(accessor, reader_name)(*expected)
        assert accessor.poisoned
    finally:
        accessor.close()


def test_identity_only_reads_and_reports_real_reset_baseline_then_closes(tmp_path):
    accessor = make_identity_accessor(tmp_path)
    assert accessor.identity["mmio_identity_verified"] is True
    assert [accessor.identity[key] for key in ("id", "shape", "status", "job_id",
                                                "output_count", "pixel_count",
                                                "weight_count", "cycles")] == [
        0x465A4332, 0x00072020, 0, 0, 0, 0, 0, 0]
    assert accessor.identity["uio_index"] == 1
    assert accessor._closed
    with pytest.raises(AxiDwUioBusError, match="identity-only"):
        accessor.run([0] * 49, [0] * 1024)


@pytest.mark.parametrize("mode,field", [("bad_identity", "job_id"),
                                         ("bad_status", "status"),
                                         ("bad_count_baseline", "pixel_count"),
                                         ("bad_cycles_baseline", "cycles")])
def test_identity_only_nonreset_baseline_is_rejected(tmp_path, mode, field):
    with pytest.raises(AxiDwUioIdentityError, match=field):
        make_identity_accessor(tmp_path, mode=mode)


@pytest.mark.parametrize("mode,error", [("wrong_request", AxiDwUioProtocolError),
                                         ("float_request", AxiDwUioProtocolError),
                                         ("bad_count", AxiDwUioProtocolError),
                                         ("float_count", AxiDwUioProtocolError),
                                         ("bool_cycles", AxiDwUioProtocolError),
                                         ("short_output", AxiDwUioBusError),
                                         ("fail", AxiDwUioBusError)])
def test_bad_metadata_or_response_poisons_client(tmp_path, mode, error):
    accessor = make_accessor(tmp_path, mode=mode)
    try:
        with pytest.raises(error):
            accessor.run([1] * 49, [1] * 1024)
        assert accessor.poisoned
        with pytest.raises(AxiDwUioBusError):
            accessor.run([1] * 49, [1] * 1024)
    finally:
        accessor.close()


def test_response_deadline_poisons_without_retry_or_cpu_fallback(tmp_path):
    marker = tmp_path / "frames.bin"
    accessor = make_accessor(tmp_path, mode="hang", timeout=0.05, marker=marker)
    send = accessor._write_all
    def send_then_mark(payload):
        send(payload)
        marker.write_bytes(b"request-sent")
    accessor._write_all = send_then_mark
    try:
        with pytest.raises(AxiDwUioTimeoutError):
            accessor.run([1] * 49, [1] * 1024)
        assert accessor.poisoned
    finally:
        accessor.close()


def test_signed_i32_result_bytes_are_fixed_width_little_endian(tmp_path):
    accessor = make_accessor(tmp_path)
    try:
        result = accessor.run([127] * 49, [127] * 1024)
        outputs = struct.unpack("<1024i", result["outputs"])
        assert len(result["outputs"]) == 4096
        assert outputs[16 * 32 + 16] == 49 * 127 * 127
        assert outputs[0] == 16 * 127 * 127
    finally:
        accessor.close()


def test_first_job_id_may_be_current_hardware_value_then_must_increment(tmp_path):
    accessor = make_accessor(tmp_path, mode="start_at_17")
    try:
        first = accessor.run([0] * 49, [0] * 1024)
        second = accessor.run([0] * 49, [0] * 1024)
        assert (first["job_id"], second["job_id"]) == (17, 18)
        assert accessor.last_job_id == 18
        assert accessor.next_request_id == 3
    finally:
        accessor.close()


def test_frozen_ten_job_manifest_and_fake_end_to_end(tmp_path):
    manifest = (Path(__file__).resolve().parents[3] / "artifacts" /
                "board-debug-20261004" / "acceleration" / "host" /
                "dw-jobs-001" / "manifest.json")
    jobs = load_manifest(str(manifest))
    assert len(jobs) == 10
    accessor = make_accessor(tmp_path)
    try:
        results = run_manifest(accessor, jobs)
        assert len(results) == 10
        assert [item["job_id"] for item in results] == list(range(1, 11))
        assert [item["request_id"] for item in results] == list(range(1, 11))
    finally:
        accessor.close()


def test_frozen_manifest_tampering_is_rejected(tmp_path):
    altered = tmp_path / "manifest.json"
    altered.write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="SHA256"):
        load_manifest(str(altered))
    assert MANIFEST_SHA256 == "409fd10559f23a0b167624a977c61ae65dd237eb2eb840288a383e1a85a0b9e8"


def test_c_helper_has_mmio_free_codec_and_sequence_selftests():
    source = (Path(__file__).resolve().parents[1] / "axi_dw_uio_accessor.c").read_text()
    assert "return (uint32_t)byte;" in source
    assert "input_word(payload[i])" in source
    assert "input_word(payload[49u + i])" in source
    assert "--codec-selftest" in source and "--protocol-selftest" in source
    assert "volatile uint32_t memory_words[4]" in source
    assert "mmio_write(memory_words" in source
    assert "validate_request_header(header, expected_request_id, &request_id)" in source
    assert source.index("read_exact(STDIN_FILENO, payload") < source.index(
        "validate_request_header(header, expected_request_id, &request_id)") < source.index(
        "execute_request(regs, request_id, payload)")


def test_frozen_abi_sha_and_fields_are_pinned(tmp_path):
    abi_path = (Path(__file__).resolve().parents[2] / "hardware" /
                "acceleration" / "axi_dw_abi.json")
    abi = _load_abi(str(abi_path))
    assert abi["abi"] == "FZC2-dw7-v1"
    altered = tmp_path / "axi_dw_abi.json"
    altered.write_bytes(abi_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SHA256"):
        _load_abi(str(altered))
