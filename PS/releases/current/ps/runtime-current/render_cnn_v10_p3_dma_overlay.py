#!/usr/bin/env python3
"""Render the A0004 overlay source from one final routed platform receipt.

This writes DTS and a provenance receipt only.  It never invokes dtc, applies
an overlay, loads a module, contacts the board, or programs PL.  The resulting
source is loadable (`status = "okay"`) because generation is impossible unless
the final route receipt itself is an exact PASS for the expected A0004 address
map.  DTBO compilation and round-trip verification remain a separate gate.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import pathlib
import sys


REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_cnn_v10_p3_dma_deployment import (  # noqa: E402
    EXPECTED_ADDRESS_MAP, EXPECTED_PLATFORM_IDENTITY,
    _validate_final_platform_receipt)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _checked_sha(value):
    if (not isinstance(value, str) or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("full-platform receipt SHA must be lowercase SHA256")
    return value


def _u32(value):
    return int(value, 16)


def render(full_platform_path, expected_sha256, output_dts, output_receipt):
    source = pathlib.Path(full_platform_path).resolve()
    output = pathlib.Path(output_dts).resolve()
    receipt_path = pathlib.Path(output_receipt).resolve()
    if output.exists() or receipt_path.exists():
        raise ValueError("refusing to overwrite overlay output")
    try:
        relative = source.relative_to(REPO).as_posix()
    except ValueError:
        raise ValueError("full-platform receipt must be inside the workspace")
    raw = source.read_bytes()
    expected = _checked_sha(expected_sha256)
    if _sha(raw) != expected:
        raise ValueError("full-platform receipt SHA mismatch")
    final = _validate_final_platform_receipt(
        {"source_path": relative, "sha256": expected})
    hls = EXPECTED_ADDRESS_MAP["hls_control"]
    guard = EXPECTED_ADDRESS_MAP["guard_identity"]
    text = """/dts-v1/;
/plugin/;

/* Generated from final A0004 routed platform receipt SHA256: %s */
/ {
    fragment@0 {
        target-path = "/amba_pl@0";
        __overlay__ {
            #address-cells = <2>;
            #size-cells = <2>;

            fz3b-cnn-ddr-v10-p3-dma@a4000000 {
                compatible = "fz3b,cnn-ddr-v10-p3-dma-candidate";
                reg = <0x0 0x%08x 0x0 0x%08x
                       0x0 0x%08x 0x0 0x%08x>;
                reg-names = "hls-control", "guard-identity";
                status = "okay";

                fz3b,address-bits = <40>;
                fz3b,data-bits = <128>;
                fz3b,core-id = <0x465a5641>;
                fz3b,abi-version = <0x000a0004>;
                fz3b,factory-handoff-contract = "fpgadrv-unloaded-refcount0-v1";
                fz3b,high-ddr-path-required;
                fz3b,arena-low = <0x0 0x40000000 0x0 0x3ff00000>;
                fz3b,arena-high = <0x8 0x00000000 0x0 0x40000000>;
            };
        };
    };
};
""" % (expected, _u32(hls["base"]), _u32(hls["size"]),
         _u32(guard["base"]), _u32(guard["size"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")
    output.write_bytes(payload)
    receipt = {
        "schema": "cnn-v10.4-a0004-overlay-source-v1",
        "pass": True,
        "status": "DTS_RENDERED_PENDING_DTC_COMPILE_AND_ROUNDTRIP",
        "full_platform_receipt": {"path": relative, "sha256": expected},
        "identity": EXPECTED_PLATFORM_IDENTITY,
        "address_map": final["address_map"],
        "dts": {"path": output.relative_to(REPO).as_posix(),
                "bytes": len(payload), "sha256": _sha(payload)},
        "checks": {"status_okay": True, "dmas_properties_absent": True,
                   "board_operations": False, "dtbo_compiled": False},
    }
    receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    receipt_path.write_bytes(receipt_raw)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-platform-receipt", required=True)
    parser.add_argument("--expected-full-platform-sha256", required=True)
    parser.add_argument("--output-dts", required=True)
    parser.add_argument("--output-receipt", required=True)
    args = parser.parse_args(argv)
    result = render(args.full_platform_receipt,
                    args.expected_full_platform_sha256,
                    args.output_dts, args.output_receipt)
    print(json.dumps({"dts_sha256": result["dts"]["sha256"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
