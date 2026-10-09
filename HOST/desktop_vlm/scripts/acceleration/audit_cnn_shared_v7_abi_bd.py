#!/usr/bin/env python3
"""Audit the exported FZV7 HLS ABI against the Linux driver and a BD snapshot.

This is deliberately read-only with respect to the source inputs.  It emits a
machine-readable receipt only after every register, identity, address aperture,
guard wiring marker, and staged overlay value is checked.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET


EXPECTED_REGISTERS = {
    "params_1": 0x10,
    "params_2": 0x14,
    "memory_1": 0x1C,
    "memory_2": 0x20,
    "profile": 0x28,
    "param_base_words": 0x30,
    "params_words": 0x38,
    "memory_words": 0x40,
    "src_words": 0x48,
    "dst_words": 0x50,
    "scratch_words": 0x58,
    "start_row": 0x60,
    "row_count": 0x68,
}

DRIVER_REGISTERS = {
    "params_1": "V7_HLS_PARAMS_LO",
    "params_2": "V7_HLS_PARAMS_HI",
    "memory_1": "V7_HLS_MEMORY_LO",
    "memory_2": "V7_HLS_MEMORY_HI",
    "profile": "V7_HLS_PROFILE",
    "param_base_words": "V7_HLS_PARAM_BASE_WORDS",
    "params_words": "V7_HLS_PARAMS_WORDS",
    "memory_words": "V7_HLS_MEMORY_WORDS",
    "src_words": "V7_HLS_SRC_WORDS",
    "dst_words": "V7_HLS_DST_WORDS",
    "scratch_words": "V7_HLS_SCRATCH_WORDS",
    "start_row": "V7_HLS_START_ROW",
    "row_count": "V7_HLS_ROW_COUNT",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with open(path, "r", encoding="utf-8") as stream:
        return stream.read()


def local_name(tag):
    return tag.split("}")[-1]


def child_text(node, name):
    for child in node:
        if local_name(child.tag) == name:
            return child.text
    raise AssertionError("missing %s in %s" % (name, local_name(node.tag)))


def parse_component(path):
    root = ET.parse(path).getroot()
    buses = []
    ports = []
    registers = {}
    blocks = []
    for node in root.iter():
        kind = local_name(node.tag)
        if kind == "busInterface":
            buses.append(child_text(node, "name"))
        elif kind == "port":
            ports.append(child_text(node, "name"))
        elif kind == "register":
            registers[child_text(node, "name")] = int(
                child_text(node, "addressOffset"), 0
            )
        elif kind == "addressBlock":
            blocks.append(
                {
                    "name": child_text(node, "name"),
                    "base": int(child_text(node, "baseAddress"), 0),
                    "range": int(child_text(node, "range"), 0),
                }
            )
    return {
        "bus_interfaces": buses,
        "ports": ports,
        "registers": registers,
        "address_blocks": blocks,
    }


def parse_defines(path):
    values = {}
    pattern = re.compile(r"^\s*#define\s+([A-Za-z0-9_]+)\s+(0x[0-9A-Fa-f]+|[0-9]+)(?:U|UL|ULL)?\s*$")
    for line in read_text(path).splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = int(match.group(2), 0)
    return values


def require_contains(text, values, label):
    missing = [value for value in values if value not in text]
    if missing:
        raise AssertionError("%s missing markers: %s" % (label, missing))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True)
    parser.add_argument("--driver-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-component-sha256", required=True)
    parser.add_argument("--expected-bit-sha256", required=True)
    parser.add_argument("--expected-ltx-sha256", required=True)
    parser.add_argument("--release-eligible", action="store_true")
    args = parser.parse_args(argv)

    build = os.path.abspath(args.build)
    driver_dir = os.path.abspath(args.driver_dir)
    component = os.path.join(build, "hls-ip", "component.xml")
    header = os.path.join(
        build,
        "hls-ip",
        "drivers",
        "cnn_shared_v7_v1_0",
        "src",
        "xcnn_shared_v7_hw.h",
    )
    regs_header = os.path.join(driver_dir, "network7_v7_regs.h")
    uapi = os.path.join(driver_dir, "network7_v7_uapi.h")
    driver = os.path.join(driver_dir, "network7_v7_driver.c")
    overlay = os.path.join(driver_dir, "network7_v7_single_core_overlay_candidate.dts")
    address_map = os.path.join(build, "address-map.rpt")
    exact_bd = os.path.join(build, "exact-bd.tcl")
    identity_clock = os.path.join(build, "identity-clock.txt")
    bitstream = os.path.join(build, "cnn-shared-v7.bit")
    ltx = os.path.join(build, "cnn-shared-v7.ltx")

    inputs = [
        component,
        header,
        regs_header,
        uapi,
        driver,
        overlay,
        address_map,
        exact_bd,
        identity_clock,
        bitstream,
        ltx,
    ]
    for path in inputs:
        if not os.path.isfile(path):
            raise AssertionError("missing input: %s" % path)

    hashes = {os.path.relpath(path): sha256(path) for path in inputs}
    assert sha256(component) == args.expected_component_sha256.lower()
    assert sha256(bitstream) == args.expected_bit_sha256.lower()
    assert sha256(ltx) == args.expected_ltx_sha256.lower()

    component_data = parse_component(component)
    assert component_data["registers"] == EXPECTED_REGISTERS
    assert component_data["address_blocks"] == [
        {"name": "Reg", "base": 0, "range": 0x10000}
    ]
    assert set(("s_axi_control", "m_axi_g_params", "m_axi_g_memory", "ap_ctrl", "error", "trace")).issubset(
        set(component_data["bus_interfaces"])
    )
    assert set(("ap_start", "ap_done", "ap_idle", "ap_ready", "error", "error_ap_vld", "trace")).issubset(
        set(component_data["ports"])
    )
    assert 0 not in component_data["registers"].values()

    driver_defines = parse_defines(regs_header)
    for register, macro in DRIVER_REGISTERS.items():
        assert driver_defines[macro] == EXPECTED_REGISTERS[register]
    assert driver_defines["V7_CORE_ID"] == 0x465A5637
    assert driver_defines["V7_CORE_ABI"] == 0x00070000
    assert driver_defines["V7_CORE_CAPS"] == 0x000001FF

    exported_defines = parse_defines(header)
    export_names = {
        "params_1": "XCNN_SHARED_V7_CONTROL_ADDR_PARAMS_DATA",
        "memory_1": "XCNN_SHARED_V7_CONTROL_ADDR_MEMORY_DATA",
        "profile": "XCNN_SHARED_V7_CONTROL_ADDR_PROFILE_DATA",
        "param_base_words": "XCNN_SHARED_V7_CONTROL_ADDR_PARAM_BASE_WORDS_DATA",
        "params_words": "XCNN_SHARED_V7_CONTROL_ADDR_PARAMS_WORDS_DATA",
        "memory_words": "XCNN_SHARED_V7_CONTROL_ADDR_MEMORY_WORDS_DATA",
        "src_words": "XCNN_SHARED_V7_CONTROL_ADDR_SRC_WORDS_DATA",
        "dst_words": "XCNN_SHARED_V7_CONTROL_ADDR_DST_WORDS_DATA",
        "scratch_words": "XCNN_SHARED_V7_CONTROL_ADDR_SCRATCH_WORDS_DATA",
        "start_row": "XCNN_SHARED_V7_CONTROL_ADDR_START_ROW_DATA",
        "row_count": "XCNN_SHARED_V7_CONTROL_ADDR_ROW_COUNT_DATA",
    }
    for register, macro in export_names.items():
        assert exported_defines[macro] == EXPECTED_REGISTERS[register]
    assert EXPECTED_REGISTERS["params_2"] == EXPECTED_REGISTERS["params_1"] + 4
    assert EXPECTED_REGISTERS["memory_2"] == EXPECTED_REGISTERS["memory_1"] + 4

    address_text = read_text(address_map)
    address_markers = [
        "/ps/Data/HLS_0 OFFSET=0x00A4000000 RANGE=0x0000010000",
        "/ps/Data/GUARD_0 OFFSET=0x00A4010000 RANGE=0x0000010000",
        "/hls0/Data_m_axi_g_params/DDR_LOW_0_0 OFFSET=0x0000000040000000 RANGE=0x0000000040000000",
        "/hls0/Data_m_axi_g_params/DDR_HIGH_0_0 OFFSET=0x0000000800000000 RANGE=0x0000000040000000",
        "/hls0/Data_m_axi_g_memory/DDR_LOW_0_1 OFFSET=0x0000000040000000 RANGE=0x0000000040000000",
        "/hls0/Data_m_axi_g_memory/DDR_HIGH_0_1 OFFSET=0x0000000800000000 RANGE=0x0000000040000000",
    ]
    require_contains(address_text, address_markers, "address-map")

    identity_text = read_text(identity_clock)
    require_contains(
        identity_text,
        [
            "id=0x465A5637",
            "abi=0x00070000",
            "caps=0x000001FF",
            "cores=1",
            "pl0_measured_hz=101375992",
        ],
        "identity-clock",
    )

    bd_text = read_text(exact_bd)
    bd_markers = [
        "CONFIG.ID_VALUE {0x465A5637}",
        "CONFIG.ABI_VERSION_VALUE {0x00070000}",
        "CONFIG.CAPS_VALUE {0x000001FF}",
        "[get_bd_intf_pins hls0/m_axi_g_params] [get_bd_intf_pins sd0_0/S_AXI]",
        "[get_bd_intf_pins hls0/m_axi_g_memory] [get_bd_intf_pins sd0_1/S_AXI]",
        "[get_bd_pins ack0/In2]",
        "[get_bd_pins rd_ack0/In2]",
        "[get_bd_pins wr_ack0/In2]",
        "assign_bd_address -offset 0xA4000000 -range 0x00010000",
        "assign_bd_address -offset 0xA4010000 -range 0x00010000",
    ]
    require_contains(bd_text, bd_markers, "exact-bd")
    assert bd_text.count("xilinx.com:ip:dfx_axi_shutdown_manager:1.0") == 3, (
        "expected one VLNV availability marker plus two shutdown manager instances"
    )
    assert bd_text.count("create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager:1.0") == 2

    overlay_text = read_text(overlay).lower()
    require_contains(
        overlay_text,
        [
            'compatible = "fz3b,cnn-shared-v7"',
            "0xa4000000 0x0 0x00010000",
            "0xa4010000 0x0 0x00010000",
            "fz3b,core-id = <0x465a5637>",
            "fz3b,abi-version = <0x00070000>",
            "fz3b,arena-low = <0x0 0x40000000 0x0 0x3ff00000>",
            "fz3b,arena-high = <0x8 0x00000000 0x0 0x40000000>",
        ],
        "overlay",
    )

    receipt = {
        "status": "FZV7_HLS004_BUILD_SINGLE002_ABI_BD_PASS",
        "release_eligible": bool(args.release_eligible),
        "board_transition_performed": False,
        "board_load_policy": (
            "ELIGIBLE_ONLY_AFTER_RELEASE_COORDINATION"
            if args.release_eligible
            else "DO_NOT_LOAD_RESOURCE_OPTIMIZATION_PENDING"
        ),
        "identity": {
            "core_id": "0x465A5637",
            "core_abi": "0x00070000",
            "software_abi": 7,
            "caps": "0x000001FF",
            "cores": 1,
        },
        "registers": EXPECTED_REGISTERS,
        "interfaces": {
            "axi_lite": "s_axi_control",
            "axi_params": "m_axi_g_params",
            "axi_memory": "m_axi_g_memory",
            "external_control": ["ap_start", "ap_done", "ap_idle", "ap_ready"],
            "external_error": ["error", "error_ap_vld"],
            "external_trace": "trace",
        },
        "address_map": {
            "hls_control": {"base": "0xA4000000", "range": "0x00010000"},
            "guard": {"base": "0xA4010000", "range": "0x00010000"},
            "params_ddr": [
                {"base": "0x0000000040000000", "range": "0x0000000040000000"},
                {"base": "0x0000000800000000", "range": "0x0000000040000000"},
            ],
            "memory_ddr": [
                {"base": "0x0000000040000000", "range": "0x0000000040000000"},
                {"base": "0x0000000800000000", "range": "0x0000000040000000"},
            ],
        },
        "guard_binding": {
            "shutdown_managers": 2,
            "unused_ack_lane": 2,
            "unused_ack_lane_tied_high": True,
            "params_and_memory_independently_guarded": True,
        },
        "clock_evidence": {
            "source": "build identity-clock.txt",
            "pl0_measured_hz": 101375992,
            "scope": "offline build identity; not a new board measurement",
        },
        "hashes": hashes,
    }

    output = os.path.abspath(args.output)
    directory = os.path.dirname(output)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(output, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"receipt": output, "sha256": sha256(output), "status": receipt["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
