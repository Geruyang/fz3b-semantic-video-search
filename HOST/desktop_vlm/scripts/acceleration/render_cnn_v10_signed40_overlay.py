#!/usr/bin/env python3
"""Render the enabled A0005 overlay from one signed final platform receipt."""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib
import sys


REPO = pathlib.Path(__file__).resolve().parents[3]
BOARD = REPO / "desktop_vlm/board"
sys.path.insert(0, str(BOARD))

from cnn_pipeline_v10_signed40_deployment import (  # noqa: E402
    CANDIDATE_CONTRACT_SHA256, COMBINED_SHA256, IDENTITY,
    SOURCE_MANIFEST_SHA256, _validate_platform)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_sha(value):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("full-platform receipt SHA must be lowercase SHA256")
    return value


def render(full_platform_path, expected_sha256, output_dts, output_receipt):
    source = pathlib.Path(full_platform_path).resolve()
    output = pathlib.Path(output_dts).resolve()
    receipt_path = pathlib.Path(output_receipt).resolve()
    if output.exists() or receipt_path.exists():
        raise ValueError("refusing to overwrite overlay output")
    raw = source.read_bytes()
    expected = checked_sha(expected_sha256)
    if sha(raw) != expected:
        raise ValueError("full-platform receipt SHA mismatch")
    platform = json.loads(raw.decode("utf-8"))
    artifacts = platform.get("artifacts", {})
    synthetic_manifest = {"files": {
        "bitstream": {"sha256": artifacts.get("bitstream", {}).get("sha256")},
        "configuration_bin": {"sha256": artifacts.get("bin", {}).get("sha256")},
    }}
    _validate_platform(platform, synthetic_manifest)
    text = """/dts-v1/;
/plugin/;

/* Generated from final A0005 platform receipt SHA256: %s */
/ {
    fragment@0 {
        target-path = "/amba_pl@0";
        __overlay__ {
            #address-cells = <2>;
            #size-cells = <2>;

            fz3b-cnn-ddr-v10-signed40@a4000000 {
                compatible = "fz3b,cnn-ddr-v10-signed40-candidate";
                reg = <0x0 0xa4000000 0x0 0x00010000
                       0x0 0xa4010000 0x0 0x00010000>;
                reg-names = "hls-control", "guard-identity";
                status = "okay";

                fz3b,address-bits = <40>;
                fz3b,data-bits = <128>;
                fz3b,core-id = <0x465a5641>;
                fz3b,abi-version = <0x000a0005>;
                fz3b,guard-caps = <0x00000fff>;
                fz3b,factory-handoff-contract = "fpgadrv-unloaded-refcount0-v1";
                fz3b,high-ddr-path-required;
                fz3b,arena-low = <0x0 0x40000000 0x0 0x3ff00000>;
                fz3b,arena-high = <0x8 0x00000000 0x0 0x40000000>;
            };
        };
    };
};
""" % expected
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")
    output.write_bytes(payload)
    receipt = {
        "schema": "cnn-v10.5-a0005-overlay-source-v1", "pass": True,
        "status": "DTS_RENDERED_PENDING_DTC_COMPILE_AND_ROUNDTRIP",
        "full_platform_receipt_sha256": expected,
        "identity": dict(IDENTITY,
                         combined_parameter_manifest_sha256=COMBINED_SHA256,
                         candidate_source_manifest_sha256=
                             SOURCE_MANIFEST_SHA256,
                         candidate_contract_sha256=
                             CANDIDATE_CONTRACT_SHA256),
        "dts": {"path": str(output), "bytes": len(payload),
                "sha256": sha(payload)},
        "checks": {"status_okay": True, "dmas_properties_absent": True,
                   "clock_properties_absent": True,
                   "board_operations": False, "dtbo_compiled": False},
    }
    receipt_path.write_bytes(
        (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode())
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-platform-receipt", required=True)
    parser.add_argument("--expected-full-platform-sha256", required=True)
    parser.add_argument("--output-dts", required=True)
    parser.add_argument("--output-receipt", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(render(args.full_platform_receipt,
                            args.expected_full_platform_sha256,
                            args.output_dts, args.output_receipt),
                     sort_keys=True))


if __name__ == "__main__":
    main()
