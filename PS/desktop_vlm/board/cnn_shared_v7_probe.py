"""Board-side single-core exact probe for the FZV7 shared stripe engine.

The probe deliberately covers only one physical core.  It runs all stripes of
profile 2, 0, and 1 in one driver generation, preserving profile-switch and
state-reuse evidence.  Multi-core scheduling is a separate gate.
"""

from __future__ import print_function

import argparse
import ctypes
import hashlib
import json
import os
import struct
import time


IDENTITY = struct.Struct("<28I2Q8I")
ALLOC = struct.Struct("<QQIIII")
FREE = struct.Struct("<II")
TRANSFER = struct.Struct("<IIQQQ")
SUBMIT = struct.Struct("<12I")
STATUS = struct.Struct("<15I")

CORE_ID = 0x465A5637
CORE_ABI = 0x00070000
GUARD_CAPS = 0x000001FF
ABI_VERSION = 7
PROFILE_COUNT = 3
CANARY_BYTE = 0xA5


def _ioc(direction, number, size):
    return ((direction << 30) | (size << 16) | (ord("Y") << 8) | number)


IOC_GET_IDENTITY = _ioc(2, 0x40, IDENTITY.size)
IOC_ALLOC = _ioc(3, 0x41, ALLOC.size)
IOC_FREE = _ioc(1, 0x42, FREE.size)
IOC_UPLOAD = _ioc(1, 0x43, TRANSFER.size)
IOC_DOWNLOAD = _ioc(1, 0x44, TRANSFER.size)
IOC_SUBMIT = _ioc(1, 0x45, SUBMIT.size)
IOC_GET_STATUS = _ioc(2, 0x46, STATUS.size)
IOC_QUIESCE = _ioc(0, 0x47, 0)


STATUS_NAMES = (
    "completed_jobs", "protocol_error", "flags", "profile",
    "guard_status", "guard_acks", "ar_total", "rlast_total", "aw_total",
    "wlast_total", "b_total", "reset_generation", "guard_error_flags",
    "job_cycles_lo", "job_cycles_hi",
)


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _load_checked(root, item):
    path = os.path.join(root, item["path"].replace("/", os.sep))
    with open(path, "rb") as stream:
        payload = stream.read()
    if len(payload) != int(item["bytes"]):
        raise ValueError("byte count mismatch for %s" % item["path"])
    if sha256_bytes(payload) != item["sha256"]:
        raise ValueError("SHA256 mismatch for %s" % item["path"])
    return payload


def load_plan(root, manifest_path, expected_sha256):
    with open(manifest_path, "rb") as stream:
        raw = stream.read()
    if sha256_bytes(raw) != expected_sha256:
        raise ValueError("native fixture manifest SHA256 mismatch")
    manifest = json.loads(raw.decode("utf-8-sig"))
    sequences = manifest.get("full_block_sequences", [])
    if len(sequences) != 3:
        raise ValueError("probe requires exactly three full-block sequences")
    seen_profiles = set()
    plan = []
    for sequence in sequences:
        profile = int(sequence["profile"])
        if profile in seen_profiles or profile not in (0, 1, 2):
            raise ValueError("profile sequence set is invalid")
        seen_profiles.add(profile)
        descriptors = sequence["descriptors"]
        width = int(descriptors[0]["width"])
        expected_rows = list(range(0, width, 4))
        if [int(item["start_row"]) for item in descriptors] != expected_rows:
            raise ValueError("stripe descriptors do not cover the block in order")
        if any(int(item["row_count"]) != 4 for item in descriptors):
            raise ValueError("production probe requires four-row stripes")
        if any(int(item["profile"]) != profile for item in descriptors):
            raise ValueError("descriptor profile differs from sequence")
        params = _load_checked(root, sequence["params"])
        source = _load_checked(root, sequence["source_full_hcw"])
        expected = _load_checked(root, sequence["expected_full_hcw"])
        if len(source) != len(expected):
            raise ValueError("source/output tensor byte counts differ")
        plan.append({"sequence": sequence, "params": params,
                     "source": source, "expected": expected})
    if seen_profiles != set((0, 1, 2)):
        raise ValueError("profile sequence set is incomplete")
    return plan


def expected_job_metrics(descriptor):
    channels = int(descriptor["channels"])
    width = int(descriptor["width"])
    rows = int(descriptor["row_count"])
    spatial_tiles = width * rows // 16
    pw_bytes = 12 * channels * channels * spatial_tiles
    return {
        "pw_weight_read_bytes": pw_bytes,
        "pw_weight_read_128b_beats": pw_bytes // 16,
        "gelu_lookups": 3 * channels * width * rows,
    }


class V7Device(object):
    def __init__(self, path):
        self._fcntl = __import__("fcntl")
        self.fd = os.open(path, os.O_RDWR | getattr(os, "O_CLOEXEC", 0))

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _mutable_ioctl(self, command, packed):
        data = bytearray(packed)
        self._fcntl.ioctl(self.fd, command, data, True)
        return bytes(data)

    def identity(self):
        values = IDENTITY.unpack(self._mutable_ioctl(
            IOC_GET_IDENTITY, bytes(IDENTITY.size)))
        result = {
            "core_id": values[0], "core_abi": values[1],
            "guard_caps": values[2], "abi_version": values[3],
            "caps": values[4], "address_bits": values[5],
            "data_bits": values[6], "arena_count": values[7],
            "profile_count": values[8],
            "blocks": list(values[9:12]), "channels": list(values[12:15]),
            "widths": list(values[15:18]),
            "block_stride_words": list(values[18:21]),
            "tensor_words": list(values[21:24]),
            "row_words": list(values[24:27]),
            "arena_bytes": list(values[28:30]),
            "software_parameter_manifest_words": list(values[30:38]),
        }
        if (result["core_id"], result["core_abi"], result["guard_caps"],
                result["abi_version"], result["profile_count"]) != (
                CORE_ID, CORE_ABI, GUARD_CAPS, ABI_VERSION, PROFILE_COUNT):
            raise RuntimeError("FZV7 identity mismatch")
        return result

    def status(self):
        values = STATUS.unpack(self._mutable_ioctl(
            IOC_GET_STATUS, bytes(STATUS.size)))
        result = dict(zip(STATUS_NAMES, values))
        result["job_cycles"] = ((result["job_cycles_hi"] << 32) |
                                result["job_cycles_lo"])
        return result

    def alloc(self, size, alignment=65536, flags=1):
        values = ALLOC.unpack(self._mutable_ioctl(
            IOC_ALLOC, ALLOC.pack(size, alignment, flags, 0, 0, 0)))
        return {"bytes": values[0], "alignment": values[1],
                "flags": values[2], "handle": values[3],
                "arena_index": values[4]}

    def free(self, handle):
        self._fcntl.ioctl(self.fd, IOC_FREE, FREE.pack(handle, 0))

    def upload(self, handle, offset, payload):
        buffer_ = ctypes.create_string_buffer(payload)
        packed = TRANSFER.pack(handle, 0, offset, len(payload),
                               ctypes.addressof(buffer_))
        self._fcntl.ioctl(self.fd, IOC_UPLOAD, packed)

    def download(self, handle, offset, size):
        buffer_ = ctypes.create_string_buffer(size)
        packed = TRANSFER.pack(handle, 0, offset, size,
                               ctypes.addressof(buffer_))
        self._fcntl.ioctl(self.fd, IOC_DOWNLOAD, packed)
        return buffer_.raw

    def submit(self, descriptor, params_handle, memory_handle):
        values = [int(descriptor[name]) for name in (
            "profile", "param_base_words", "params_words", "memory_words",
            "src_words", "dst_words", "scratch_words", "start_row",
            "row_count")]
        values.extend((params_handle, memory_handle, 0))
        self._fcntl.ioctl(self.fd, IOC_SUBMIT, SUBMIT.pack(*values))

    def quiesce(self):
        self._fcntl.ioctl(self.fd, IOC_QUIESCE, 0)


def _status_delta(before, after):
    result = {}
    for name in ("completed_jobs", "ar_total", "rlast_total", "aw_total",
                 "wlast_total", "b_total"):
        result[name] = (int(after[name]) - int(before[name])) & 0xFFFFFFFF
    if result["completed_jobs"] != 1:
        raise RuntimeError("completed job counter did not advance exactly once")
    if not result["ar_total"] or not result["aw_total"]:
        raise RuntimeError("job did not issue both read and write traffic")
    if int(after["ar_total"]) != int(after["rlast_total"]):
        raise RuntimeError("read counters are not balanced")
    if not (int(after["aw_total"]) == int(after["wlast_total"]) ==
            int(after["b_total"])):
        raise RuntimeError("write counters are not balanced")
    if after["protocol_error"] or after["guard_error_flags"]:
        raise RuntimeError("guard reported a protocol error")
    return result


def execute_plan(device, plan):
    identity = device.identity()
    handles = []
    jobs = []
    completed_sequences = []
    quiesced = False
    try:
        for item in plan:
            sequence = item["sequence"]
            descriptors = sequence["descriptors"]
            memory_bytes = int(descriptors[0]["memory_words"]) * 16
            params_alloc = device.alloc(len(item["params"]))
            memory_alloc = device.alloc(memory_bytes)
            handles.extend((params_alloc["handle"], memory_alloc["handle"]))
            device.upload(params_alloc["handle"], 0, item["params"])
            canary = bytes(bytearray([CANARY_BYTE])) * memory_bytes
            device.upload(memory_alloc["handle"], 0, canary)
            src_offset = int(descriptors[0]["src_words"]) * 16
            dst_offset = int(descriptors[0]["dst_words"]) * 16
            scratch_offset = int(descriptors[0]["scratch_words"]) * 16
            scratch_capacity = max(int(d["scratch_required_words"])
                                   for d in descriptors) * 16
            device.upload(memory_alloc["handle"], src_offset, item["source"])
            expected_memory = bytearray(canary)
            expected_memory[src_offset:src_offset + len(item["source"])] = item["source"]
            row_bytes = int(descriptors[0]["row_words"]) * 16
            for descriptor in descriptors:
                device.upload(memory_alloc["handle"], scratch_offset,
                              bytes(bytearray([CANARY_BYTE])) * scratch_capacity)
                expected_memory[scratch_offset:scratch_offset + scratch_capacity] = \
                    bytes(bytearray([CANARY_BYTE])) * scratch_capacity
                before = device.status()
                started_ns = time.time_ns() if hasattr(time, "time_ns") else int(time.time() * 1e9)
                device.submit(descriptor, params_alloc["handle"],
                              memory_alloc["handle"])
                ended_ns = time.time_ns() if hasattr(time, "time_ns") else int(time.time() * 1e9)
                after = device.status()
                delta = _status_delta(before, after)
                start = int(descriptor["start_row"]) * row_bytes
                count = int(descriptor["row_count"]) * row_bytes
                expected_memory[dst_offset + start:dst_offset + start + count] = \
                    item["expected"][start:start + count]
                actual = device.download(memory_alloc["handle"], 0, memory_bytes)
                scratch_bytes = int(descriptor["scratch_required_words"]) * 16
                expected_compare = bytearray(expected_memory)
                expected_compare[scratch_offset:scratch_offset + scratch_bytes] = \
                    actual[scratch_offset:scratch_offset + scratch_bytes]
                if actual != bytes(expected_compare):
                    mismatch = next(i for i, pair in enumerate(zip(actual, expected_compare))
                                    if pair[0] != pair[1])
                    raise RuntimeError("memory/canary mismatch at byte %d" % mismatch)
                metrics = expected_job_metrics(descriptor)
                metrics.update({
                    "case_id": sequence["case_id"],
                    "profile": int(descriptor["profile"]),
                    "start_row": int(descriptor["start_row"]),
                    "row_count": int(descriptor["row_count"]),
                    "wall_ns": ended_ns - started_ns,
                    "status_before": before,
                    "status_after": after,
                    "counter_delta": delta,
                    "actual_params_ar_beats": None,
                    "actual_gelu_trace_segments": None,
                    "actual_counter_scope": "guard transactions, not AXI beats",
                    "scratch_sha256": sha256_bytes(
                        actual[scratch_offset:scratch_offset + scratch_bytes]),
                })
                jobs.append(metrics)
            final = device.download(memory_alloc["handle"], dst_offset,
                                    len(item["expected"]))
            if final != item["expected"]:
                raise RuntimeError("stitched full-block output mismatch")
            completed_sequences.append({
                "case_id": sequence["case_id"], "profile": sequence["profile"],
                "output_sha256": sha256_bytes(final),
                "expected_sha256": sha256_bytes(item["expected"]),
                "stripe_count": len(descriptors),
            })
        device.quiesce()
        quiesced = True
        for handle in reversed(handles):
            device.free(handle)
        handles = []
        return {"status": "CNN_SHARED_V7_SINGLE_CORE_ALL_STRIPES_PASS",
                "identity": identity, "jobs": jobs,
                "completed_sequences": completed_sequences,
                "cleanup": {"quiesced": True, "handles_freed": True},
                "scope": "one physical core; no multi-core claim"}
    finally:
        if handles and not quiesced:
            try:
                device.quiesce()
                quiesced = True
            except Exception:
                pass
        if quiesced:
            for handle in reversed(handles):
                try:
                    device.free(handle)
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/network7_v7")
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = {"status": "CNN_SHARED_V7_SINGLE_CORE_INCOMPLETE",
              "started_unix_ns": int(time.time() * 1e9)}
    device = None
    try:
        plan = load_plan(args.root, args.manifest,
                         args.expected_manifest_sha256.lower())
        device = V7Device(args.device)
        report.update(execute_plan(device, plan))
    except Exception as error:
        report["error"] = "%s: %s" % (type(error).__name__, error)
        raise
    finally:
        if device is not None:
            device.close()
        report["finished_unix_ns"] = int(time.time() * 1e9)
        parent = os.path.dirname(args.output)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(args.output, "w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")


if __name__ == "__main__":
    main()
