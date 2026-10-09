"""Adversarial capture-verifier tests; synthetic data is never board evidence."""
import csv
import importlib.util
from pathlib import Path
import struct

import pytest


SOURCE = Path(__file__).resolve().parents[2] / "hardware/acceleration/check_dw_capture.py"
SPEC = importlib.util.spec_from_file_location("dw_capture_checker", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIELDS = ("report_event", "report_job", "report_index", "report_actual",
          "report_expected", "completed", "failures", "rounds",
          "accepted_weights", "accepted_pixels")


def make_capture(tmp_path):
    # Include both signed extremes; fixture is independent of the captured ROM.
    golden = [((i * 1_000_003) % (1 << 32)) - (1 << 31) for i in range(6144)]
    for image in range(3):
        (tmp_path / f"sample-{image:02d}-output-chw.i32").write_bytes(
            struct.pack("<2048i", *golden[image * 2048:(image + 1) * 2048]))
    rows = []
    for i in range(8192):
        position = i + 511
        job, index = divmod(position % 6144, 1024)
        value = golden[job * 1024 + index] & 0xffffffff
        rows.append([1, job, index, value, value, (0xffffff00 + i) & 0xffffffff,
                     0, position // 6144, 49, 1024])
    return rows


def write_capture(tmp_path, rows):
    path = tmp_path / "synthetic.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["u_selftest/" + name for name in FIELDS])
        writer.writerow(["HEX"] * len(FIELDS))
        writer.writerows([[format(value, "x") for value in row] for row in rows])
    return path


def test_good_signed_values_and_completion_wrap(tmp_path):
    rows = make_capture(tmp_path)
    result = MODULE.check_capture(write_capture(tmp_path, rows), tmp_path)
    assert result["distinct_job_indices"] == 6144
    assert result["completed_contiguous_mod32"]


@pytest.mark.parametrize("mutation", ["matching_wrong_rom", "duplicate_completion",
                                     "bad_round", "event_low", "failure_flag",
                                     "wrong_weights", "missing_row", "pixel_regression"])
def test_corrupt_capture_rejected(tmp_path, mutation):
    rows = make_capture(tmp_path)
    if mutation == "matching_wrong_rom":
        # Actual == reported expected is insufficient: both can be wrong.
        rows[600][3] ^= 1
        rows[600][4] ^= 1
    elif mutation == "duplicate_completion":
        rows[600][5] = rows[599][5]
    elif mutation == "bad_round":
        rows[600][7] += 1
    elif mutation == "event_low":
        rows[600][0] = 0
    elif mutation == "failure_flag":
        rows[600][6] = 1
    elif mutation == "wrong_weights":
        rows[600][8] = 48
    elif mutation == "missing_row":
        rows.pop(600)
    elif mutation == "pixel_regression":
        rows[600][9] = 1023
    with pytest.raises(ValueError):
        MODULE.check_capture(write_capture(tmp_path, rows), tmp_path)
