#!/usr/bin/env python3
"""Generate the V10 RTL-testbench binding from a frozen HLS top/control pair."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


READ_BUNDLES = {
    "g_param1": 0,
    "g_param2": 1,
    "g_act_a_r": 2,
    "g_act_b_r": 3,
}
WRITE_BUNDLES = {"g_act_a_w": 0, "g_act_b_w": 1}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def top_ports(text: str) -> list[str]:
    match = re.search(r"module\s+cnn_pipeline_v10\s*\((.*?)\);", text, re.S)
    if not match:
        raise ValueError("cnn_pipeline_v10 module declaration not found")
    ports = []
    for line in match.group(1).splitlines():
        port = line.strip().rstrip(",").strip()
        if port:
            ports.append(port)
    if not ports or len(ports) != len(set(ports)):
        raise ValueError("empty or duplicate top port list")
    return ports


def read_mapping(index: int, suffix: str) -> str:
    mapped = {
        "ARVALID": f"rd_arvalid[{index}]", "ARREADY": f"rd_arready[{index}]",
        "ARADDR": f"rd_araddr[{index}]", "ARID": f"rd_arid[{index}][0]",
        "ARLEN": f"rd_arlen[{index}]", "ARSIZE": f"rd_arsize[{index}]",
        "ARBURST": f"rd_arburst[{index}]",
        "RVALID": f"rd_rvalid[{index}]", "RREADY": f"rd_rready[{index}]",
        "RDATA": f"rd_rdata[{index}]", "RLAST": f"rd_rlast[{index}]",
        "RID": f"rd_rid[{index}][0]", "RRESP": f"rd_rresp[{index}]",
        "RUSER": "1'b0", "AWREADY": "1'b0", "WREADY": "1'b0",
        "BVALID": "1'b0", "BRESP": "2'b00", "BID": "1'b0", "BUSER": "1'b0",
    }
    open_outputs = {"AWVALID", "AWADDR", "AWID", "AWLEN", "AWSIZE", "AWBURST",
                    "AWLOCK", "AWCACHE", "AWPROT", "AWQOS", "AWREGION", "AWUSER",
                    "WVALID", "WDATA", "WSTRB", "WLAST", "WID", "WUSER", "BREADY",
                    "ARLOCK", "ARCACHE", "ARPROT", "ARQOS", "ARREGION", "ARUSER"}
    if suffix in mapped:
        return mapped[suffix]
    if suffix in open_outputs:
        return ""
    raise ValueError(f"unmapped read-bundle suffix {suffix}")


def write_mapping(index: int, suffix: str) -> str:
    mapped = {
        "AWVALID": f"wr_awvalid[{index}]", "AWREADY": f"wr_awready[{index}]",
        "AWADDR": f"wr_awaddr[{index}]", "AWID": f"wr_awid[{index}][0]",
        "AWLEN": f"wr_awlen[{index}]", "AWSIZE": f"wr_awsize[{index}]",
        "AWBURST": f"wr_awburst[{index}]",
        "WVALID": f"wr_wvalid[{index}]", "WREADY": f"wr_wready[{index}]",
        "WDATA": f"wr_wdata[{index}]", "WSTRB": f"wr_wstrb[{index}]",
        "WLAST": f"wr_wlast[{index}]",
        "BVALID": f"wr_bvalid[{index}]", "BREADY": f"wr_bready[{index}]",
        "BRESP": f"wr_bresp[{index}]", "BID": f"wr_bid[{index}][0]", "BUSER": "1'b0",
        "ARREADY": "1'b0", "RVALID": "1'b0", "RDATA": "128'b0",
        "RLAST": "1'b0", "RID": "1'b0", "RUSER": "1'b0", "RRESP": "2'b00",
    }
    open_outputs = {"AWLOCK", "AWCACHE", "AWPROT", "AWQOS", "AWREGION", "AWUSER",
                    "WID", "WUSER", "ARVALID", "ARADDR", "ARID", "ARLEN", "ARSIZE",
                    "ARBURST", "ARLOCK", "ARCACHE", "ARPROT", "ARQOS", "ARREGION",
                    "ARUSER", "RREADY"}
    if suffix in mapped:
        return mapped[suffix]
    if suffix in open_outputs:
        return ""
    raise ValueError(f"unmapped write-bundle suffix {suffix}")


def parse_control(text: str) -> dict[str, int]:
    wanted = {
        "PARAMS_PW1": ("V10_CTL_PARAMS1_LO", "V10_CTL_PARAMS1_HI"),
        "PARAMS_PW2": ("V10_CTL_PARAMS2_LO", "V10_CTL_PARAMS2_HI"),
        "ACTIVATION_A_RD": ("V10_CTL_ACT_A_RD_LO", "V10_CTL_ACT_A_RD_HI"),
        "ACTIVATION_A_WR": ("V10_CTL_ACT_A_WR_LO", "V10_CTL_ACT_A_WR_HI"),
        "ACTIVATION_B_RD": ("V10_CTL_ACT_B_RD_LO", "V10_CTL_ACT_B_RD_HI"),
        "ACTIVATION_B_WR": ("V10_CTL_ACT_B_WR_LO", "V10_CTL_ACT_B_WR_HI"),
        "PROFILE": ("V10_CTL_PROFILE",), "BLOCK_COUNT": ("V10_CTL_BLOCKS",),
        "PARAMS_WORDS": ("V10_CTL_PARAMS_WORDS",), "SLOT_WORDS": ("V10_CTL_SLOT_WORDS",),
        "ARENA_WORDS": ("V10_CTL_ARENA_WORDS",), "FLAGS": ("V10_CTL_FLAGS",),
    }
    result: dict[str, int] = {}
    for rtl_name, tb_names in wanted.items():
        match = re.search(rf"ADDR_{rtl_name}_DATA_0\s*=\s*8'h([0-9a-fA-F]+)", text)
        if not match:
            raise ValueError(f"control address missing for {rtl_name}")
        base = int(match.group(1), 16)
        for offset, tb_name in enumerate(tb_names):
            result[tb_name] = base + 4 * offset
    return result


def generate(top: Path, control: Path) -> str:
    top_text = top.read_text(encoding="utf-8", errors="strict")
    ports = top_ports(top_text)
    ids = [int(value) for value in re.findall(r"C_M_AXI_[A-Z0-9_]+_ID_WIDTH\s*=\s*(\d+)", top_text)]
    if not ids or set(ids) != {1}:
        raise ValueError(f"expected frozen one-bit AXI IDs, got {sorted(set(ids))}")
    addresses = parse_control(control.read_text(encoding="utf-8", errors="strict"))
    simple = {
        "ap_clk": "clk", "ap_rst_n": "rst_n", "ap_start": "ap_start",
        "pw_fast_clk": "fast_clk", "pw_fast_rst": "fast_rst",
        "ap_done": "ap_done", "ap_idle": "ap_idle", "ap_ready": "ap_ready",
        "protocol_error": "protocol_error", "protocol_error_ap_vld": "protocol_vld",
        "trace_a_feed": "trace_value[0]", "trace_a_dw3": "trace_value[1]",
        "trace_a_dw7": "trace_value[2]", "trace_a_pw1": "trace_value[3]",
        "trace_a_pw2": "trace_value[4]", "trace_a_write": "trace_value[5]",
        "trace_b_feed": "trace_value[6]", "trace_b_dw3": "trace_value[7]",
        "trace_b_dw7": "trace_value[8]", "trace_b_pw1": "trace_value[9]",
        "trace_b_pw2": "trace_value[10]", "trace_b_write": "trace_value[11]",
        "s_axi_control_AWVALID": "ctl_awvalid", "s_axi_control_AWREADY": "ctl_awready",
        "s_axi_control_AWADDR": "ctl_awaddr[7:0]", "s_axi_control_WVALID": "ctl_wvalid",
        "s_axi_control_WREADY": "ctl_wready", "s_axi_control_WDATA": "ctl_wdata",
        "s_axi_control_WSTRB": "ctl_wstrb", "s_axi_control_ARVALID": "1'b0",
        "s_axi_control_ARREADY": "", "s_axi_control_ARADDR": "8'b0",
        "s_axi_control_RVALID": "", "s_axi_control_RREADY": "1'b0",
        "s_axi_control_RDATA": "", "s_axi_control_RRESP": "",
        "s_axi_control_BVALID": "ctl_bvalid", "s_axi_control_BREADY": "ctl_bready",
        "s_axi_control_BRESP": "ctl_bresp",
    }
    connections: list[tuple[str, str]] = []
    observed_bundles: set[str] = set()
    for port in ports:
        if port in simple:
            target = simple[port]
        elif port.startswith("m_axi_"):
            body = port[len("m_axi_"):]
            bundle = next((name for name in (*READ_BUNDLES, *WRITE_BUNDLES)
                           if body.startswith(name + "_")), None)
            if bundle is None:
                raise ValueError(f"unknown AXI bundle in {port}")
            observed_bundles.add(bundle)
            suffix = body[len(bundle)+1:]
            target = (read_mapping(READ_BUNDLES[bundle], suffix) if bundle in READ_BUNDLES
                      else write_mapping(WRITE_BUNDLES[bundle], suffix))
        else:
            raise ValueError(f"unmapped top port {port}")
        connections.append((port, target))
    expected_bundles = set(READ_BUNDLES) | set(WRITE_BUNDLES)
    if observed_bundles != expected_bundles:
        raise ValueError(f"expected exactly six AXI bundles, got {sorted(observed_bundles)}")
    lines = [
        f"// Generated from {top.name} SHA256 {sha256(top)}",
        f"// Control source {control.name} SHA256 {sha256(control)}",
        "// Regenerate for every frozen HLS RTL snapshot; do not hand-edit port mappings.",
    ]
    for name, value in addresses.items():
        lines.append(f"localparam logic [31:0] {name}=32'h{value:02x};")
    for index in range(4):
        lines.append(f"assign rd_arid[{index}][TB_ID_W-1:1]='0;")
    for index in range(2):
        lines.append(f"assign wr_awid[{index}][TB_ID_W-1:1]='0;")
    lines.append("cnn_pipeline_v10 u_dut (")
    for number, (port, target) in enumerate(connections):
        comma = "," if number + 1 < len(connections) else ""
        lines.append(f"    .{port}({target}){comma}")
    lines.append(");")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rendered = generate(args.top, args.control)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"CNN_V10_BINDING_GENERATED ports={rendered.count('    .')} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
