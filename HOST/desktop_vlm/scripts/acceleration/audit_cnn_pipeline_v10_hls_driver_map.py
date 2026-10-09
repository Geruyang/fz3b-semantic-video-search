#!/usr/bin/env python3
"""Audit a packaged cnn_pipeline_v10 IP against the V10 board-driver map.

This is a read-only evidence extractor.  It does not build HLS, Vivado, a
kernel module, or a device tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


SPIRIT = "{http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009}"

REGISTER_MAP = {
    "PARAMS_PW1": ("V10_HLS_PARAM1_LO", 0x10, 64),
    "PARAMS_PW2": ("V10_HLS_PARAM2_LO", 0x1C, 64),
    "ACTIVATION_A_RD": ("V10_HLS_ACT_A_R_LO", 0x28, 64),
    "ACTIVATION_A_WR": ("V10_HLS_ACT_A_W_LO", 0x34, 64),
    "ACTIVATION_B_RD": ("V10_HLS_ACT_B_R_LO", 0x40, 64),
    "ACTIVATION_B_WR": ("V10_HLS_ACT_B_W_LO", 0x4C, 64),
    "PROFILE": ("V10_HLS_PROFILE", 0x58, 32),
    "BLOCK_COUNT": ("V10_HLS_BLOCK_COUNT", 0x60, 32),
    "PARAMS_WORDS": ("V10_HLS_PARAMS_WORDS", 0x68, 32),
    "SLOT_WORDS": ("V10_HLS_SLOT_WORDS", 0x70, 32),
    "ARENA_WORDS": ("V10_HLS_ARENA_WORDS", 0x78, 32),
    "FLAGS": ("V10_HLS_FLAGS", 0x80, 32),
}

MASTERS = {
    "m_axi_g_param1": "READ_ONLY",
    "m_axi_g_param2": "READ_ONLY",
    "m_axi_g_act_a_r": "READ_ONLY",
    "m_axi_g_act_a_w": "WRITE_ONLY",
    "m_axi_g_act_b_r": "READ_ONLY",
    "m_axi_g_act_b_w": "WRITE_ONLY",
}

OUTPUT_INTERFACES = [
    "protocol_error",
    "trace_a_feed", "trace_a_dw3", "trace_a_dw7", "trace_a_pw1",
    "trace_a_pw2", "trace_a_write",
    "trace_b_feed", "trace_b_dw3", "trace_b_dw7", "trace_b_pw1",
    "trace_b_pw2", "trace_b_write",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def defines(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    pattern = re.compile(r"^#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+)(?:U|UL|ULL)?\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            result[match.group(1)] = int(match.group(2), 0)
    return result


def child_text(node: ET.Element, name: str) -> str:
    return node.findtext(SPIRIT + name, default="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hls-root", type=Path, required=True)
    parser.add_argument("--driver-regs", type=Path, required=True)
    parser.add_argument("--hls-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    hw_header = args.hls_root / "impl/ip/drivers/cnn_pipeline_v10_v1_0/src/xcnn_pipeline_v10_hw.h"
    control_rtl = args.hls_root / "syn/verilog/cnn_pipeline_v10_control_s_axi.v"
    component = args.hls_root / "impl/ip/component.xml"
    inputs = [hw_header, control_rtl, component, args.driver_regs, args.hls_receipt]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise SystemExit("missing input(s): " + ", ".join(missing))

    hw = defines(hw_header)
    driver = defines(args.driver_regs)
    register_checks = {}
    for argument, (driver_name, expected_offset, expected_bits) in REGISTER_MAP.items():
        addr_name = f"XCNN_PIPELINE_V10_CONTROL_ADDR_{argument}_DATA"
        bits_name = f"XCNN_PIPELINE_V10_CONTROL_BITS_{argument}_DATA"
        actual_offset = hw.get(addr_name)
        actual_bits = hw.get(bits_name)
        driver_offset = driver.get(driver_name)
        register_checks[argument.lower()] = {
            "hls_offset": actual_offset,
            "driver_offset": driver_offset,
            "expected_offset": expected_offset,
            "hls_bits": actual_bits,
            "expected_bits": expected_bits,
            "pass": actual_offset == driver_offset == expected_offset and actual_bits == expected_bits,
        }

    tree = ET.parse(component)
    root = tree.getroot()
    interfaces = {}
    for interface in root.findall(f".//{SPIRIT}busInterfaces/{SPIRIT}busInterface"):
        name = child_text(interface, "name")
        parameters = {}
        for parameter in interface.findall(f"./{SPIRIT}parameters/{SPIRIT}parameter"):
            parameters[child_text(parameter, "name")] = child_text(parameter, "value")
        interfaces[name] = parameters

    associated = interfaces.get("ap_clk", {}).get("ASSOCIATED_BUSIF", "")
    associated_set = set(filter(None, associated.split(":")))
    required_associated = {"s_axi_control", *MASTERS.keys()}

    model_parameters = {}
    for parameter in root.findall(f".//{SPIRIT}modelParameters/{SPIRIT}modelParameter"):
        model_parameters[child_text(parameter, "name")] = child_text(parameter, "value")

    master_checks = {}
    for name, mode in MASTERS.items():
        stem = name.removeprefix("m_axi_").upper()
        width = model_parameters.get(f"C_M_AXI_{stem}_DATA_WIDTH")
        address = model_parameters.get(f"C_M_AXI_{stem}_ADDR_WIDTH")
        ident = model_parameters.get(f"C_M_AXI_{stem}_ID_WIDTH")
        actual_mode = interfaces.get(name, {}).get("READ_WRITE_MODE")
        master_checks[name] = {
            "mode": actual_mode,
            "expected_mode": mode,
            "data_width": int(width) if width else None,
            "address_width": int(address) if address else None,
            "id_width": int(ident) if ident else None,
            "clock_associated": name in associated_set,
            "pass": actual_mode == mode and width == "128" and address == "64" and ident == "1" and name in associated_set,
        }

    address_blocks = []
    for block in root.findall(f".//{SPIRIT}memoryMaps//{SPIRIT}addressBlock"):
        address_blocks.append({
            "name": child_text(block, "name"),
            "base": int(child_text(block, "baseAddress"), 0),
            "range": int(child_text(block, "range"), 0),
            "width": int(child_text(block, "width"), 0),
        })

    hls_receipt = json.loads(args.hls_receipt.read_text(encoding="utf-8-sig"))
    checks = {
        "hls_tool_exit_zero": hls_receipt.get("tool_exit_code") == 0,
        "all_registers_match": all(item["pass"] for item in register_checks.values()),
        "six_masters_match": set(MASTERS).issubset(interfaces) and all(item["pass"] for item in master_checks.values()),
        "single_clock_associates_control_and_all_masters": required_associated == associated_set,
        "control_aperture_covers_required_bytes": any(block["base"] == 0 and block["range"] >= 0x84 and block["width"] == 32 for block in address_blocks),
        "protocol_and_twelve_traces_present": all(name in interfaces for name in OUTPUT_INTERFACES),
        "packaged_header_matches_frozen_hls004_map": sha256(hw_header) == "edd8e1e683a06817f6c91843d375d0d29e266372a819a58ea1cd6cc4fb18e3bc",
        "packaged_control_rtl_matches_frozen_hls004_map": sha256(control_rtl) == "ea1748e5979c61e1c5f7d704a0e8577192d4bef938e2bc5396c2c0c07f5c68c4",
    }

    receipt = {
        "schema": "cnn-pipeline-v10-hls-driver-map-audit-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "read-only packaged HLS control/interface map versus V10 candidate driver",
        "result": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "registers": register_checks,
        "masters": master_checks,
        "ap_clk_associated_busif": associated,
        "address_blocks": address_blocks,
        "output_interfaces": {name: name in interfaces for name in OUTPUT_INTERFACES},
        "hls_source_sha256": hls_receipt.get("source_sha256"),
        "files": {
            str(path).replace("\\", "/"): {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in inputs
        },
        "limits": {
            "does_not_validate_rtl_liveness": True,
            "does_not_validate_vivado_bd_address_map": True,
            "does_not_validate_device_tree_binding": True,
            "does_not_authorize_deployment": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": receipt["result"], "output": str(args.output), "checks": checks}, indent=2))
    return 0 if receipt["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
