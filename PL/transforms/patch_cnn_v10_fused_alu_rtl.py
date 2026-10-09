#!/usr/bin/env python3
"""Create a reproducible A0004 fused-ALU HLS-IP candidate.

Vitis HLS 2026.1 treats custom black-box clock arguments as ordinary data and
registers them in generated RTL.  That is not a clock-safe integration.  This
tool instead starts from the frozen exported A0004 IP, computes the complete
module-instantiation closure above ``cnn_v10_pw_dsp16``, and adds two physical
ports through every ancestor up to ``cnn_pipeline_v10``.  The original leaf is
retained under a reference-only module name and replaced by the verified
half-width implementation.  IP-XACT receives real clock/reset interfaces.

The input tree is never edited.  Every changed file and every propagated edge
is recorded in a fail-closed receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


LEAF = "cnn_v10_pw_dsp16"
TOP = "cnn_pipeline_v10"
PORTS = ("pw_fast_clk", "pw_fast_rst")
EXPECTED_PRIMITIVE_SHA256 = "278af8d1a70e8812fae70ac2cb1b9c637b9325d9f1276474c722e17771b07248"
EXPECTED_FUSED_LEAF_SHA256 = "514d1b1134f9c84999ed131527c9d3700778b688897bdeccaa3b66811080f482"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def inventory(root: Path) -> list[dict[str, object]]:
    result = []
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        result.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return result


def inventory_sha(items: list[dict[str, object]]) -> str:
    encoded = json.dumps(items, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return sha256_bytes(encoded)


@dataclass(frozen=True)
class ModuleDef:
    name: str
    path: Path
    start: int
    end: int
    text: str


MODULE_START_RE = re.compile(r"(?m)^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b")
ENDMODULE_RE = re.compile(r"(?m)^\s*endmodule\b")


def parse_modules(rtl_dir: Path) -> dict[str, ModuleDef]:
    modules: dict[str, ModuleDef] = {}
    for path in sorted(rtl_dir.glob("*.v"), key=lambda p: p.name):
        # Use byte-decoded text so offsets remain valid for the exported CRLF
        # files.  pathlib.read_text performs universal-newline conversion and
        # would make those offsets unsafe when splicing the original bytes.
        text = path.read_bytes().decode("utf-8", errors="strict")
        starts = list(MODULE_START_RE.finditer(text))
        for idx, match in enumerate(starts):
            limit = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
            end_match = ENDMODULE_RE.search(text, match.end(), limit)
            if not end_match:
                raise RuntimeError(f"module {match.group(1)} has no endmodule in {path}")
            name = match.group(1)
            if name in modules:
                raise RuntimeError(f"duplicate module definition {name}")
            modules[name] = ModuleDef(
                name=name,
                path=path,
                start=match.start(),
                end=end_match.end(),
                text=text[match.start() : end_match.end()],
            )
    return modules


def instance_spans(module_text: str, child: str) -> list[tuple[int, int]]:
    """Return opening/closing parenthesis offsets for named child instances."""
    pattern = re.compile(
        rf"(?m)^\s*{re.escape(child)}\s+(?:#\s*\([^;]*?\)\s*)?"
        rf"[A-Za-z_][A-Za-z0-9_$]*\s*\("
    )
    spans = []
    for match in pattern.finditer(module_text):
        open_pos = module_text.rfind("(", match.start(), match.end())
        depth = 0
        close_pos = -1
        for pos in range(open_pos, len(module_text)):
            char = module_text[pos]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    close_pos = pos
                    break
        if close_pos < 0 or not re.match(r"\s*;", module_text[close_pos + 1 :]):
            raise RuntimeError(f"cannot parse instance of {child}")
        spans.append((open_pos, close_pos))
    return spans


def compute_closure(modules: dict[str, ModuleDef]) -> tuple[set[str], list[dict[str, object]]]:
    if LEAF not in modules or TOP not in modules:
        raise RuntimeError(f"required modules absent: leaf={LEAF in modules}, top={TOP in modules}")
    closure = {LEAF}
    edges: list[dict[str, object]] = []
    changed = True
    while changed:
        changed = False
        for parent, definition in modules.items():
            if parent in closure:
                continue
            matched = []
            for child in sorted(closure):
                count = len(instance_spans(definition.text, child))
                if count:
                    matched.append((child, count))
            if matched:
                closure.add(parent)
                changed = True
    for parent in sorted(closure):
        if parent == LEAF:
            continue
        definition = modules[parent]
        for child in sorted(closure):
            count = len(instance_spans(definition.text, child))
            if count:
                edges.append(
                    {
                        "parent": parent,
                        "child": child,
                        "instances": count,
                        "file": definition.path.name,
                    }
                )
    if TOP not in closure:
        raise RuntimeError("leaf-to-top hierarchy closure did not reach cnn_pipeline_v10")
    return closure, edges


def find_header_close(module_text: str, name: str) -> tuple[int, int]:
    match = re.search(rf"\bmodule\s+{re.escape(name)}\b", module_text)
    if not match:
        raise RuntimeError(f"cannot locate module header {name}")
    open_pos = module_text.find("(", match.end())
    if open_pos < 0:
        raise RuntimeError(f"module {name} has no port-list opening parenthesis")
    depth = 0
    for pos in range(open_pos, len(module_text)):
        if module_text[pos] == "(":
            depth += 1
        elif module_text[pos] == ")":
            depth -= 1
            if depth == 0:
                semi = re.match(r"\s*;", module_text[pos + 1 :])
                if not semi:
                    raise RuntimeError(f"module {name} port list is not followed by semicolon")
                return pos, pos + 1 + semi.end()
    raise RuntimeError(f"module {name} header is unbalanced")


def patch_ancestor(module_text: str, name: str, child_counts: dict[str, int]) -> tuple[str, int]:
    if any(re.search(rf"\b{port}\b", module_text) for port in PORTS):
        raise RuntimeError(f"module {name} already contains a fast-clock port")
    header_close, header_end = find_header_close(module_text, name)
    edits: list[tuple[int, str]] = [
        (header_close, ",\n        pw_fast_clk,\n        pw_fast_rst"),
        (header_end, "\ninput wire pw_fast_clk;\ninput wire pw_fast_rst;"),
    ]
    total = 0
    for child, expected in child_counts.items():
        spans = instance_spans(module_text, child)
        if len(spans) != expected:
            raise RuntimeError(f"{name}->{child}: expected {expected} instances, found {len(spans)}")
        for _, close_pos in spans:
            edits.append(
                (
                    close_pos,
                    ",\n    .pw_fast_clk(pw_fast_clk),\n    .pw_fast_rst(pw_fast_rst)\n",
                )
            )
        total += len(spans)
    result = module_text
    for pos, addition in sorted(edits, key=lambda item: item[0], reverse=True):
        result = result[:pos] + addition + result[pos:]
    return result, total


def wrapper_text() -> str:
    pairs = []
    for index in range(16):
        pairs.append(f"        .value{index}(value{index}), .weight{index}(weight{index})")
    ports = [
        "    input wire ap_clk",
        "    input wire ap_rst",
        "    input wire ap_ce",
        "    input wire pw_fast_clk",
        "    input wire pw_fast_rst",
        "    input wire [47:0] prior",
    ]
    for index in range(16):
        ports += [f"    input wire [15:0] value{index}", f"    input wire [15:0] weight{index}"]
    ports.append("    output wire [47:0] result")
    return (
        "\n// Deterministic post-HLS clock bridge wrapper.\n"
        "module cnn_v10_pw_dsp16 (\n"
        + ",\n".join(ports)
        + "\n);\n"
        "    wire result_valid_unused;\n"
        "    cnn_v10_pw_dsp16_half2x_fused_alu fused_half2x (\n"
        "        .slow_clk(ap_clk), .slow_rst(ap_rst), .slow_ce(ap_ce),\n"
        "        .fast_clk(pw_fast_clk), .fast_rst(pw_fast_rst),\n"
        "        .in_valid(1'b1), .prior(prior),\n"
        + ",\n".join(pairs)
        + ",\n"
        "        .out_valid(result_valid_unused), .result(result));\n"
        "endmodule\n"
    )


def patch_leaf(primitive: str, fused_leaf: str) -> str:
    count = len(re.findall(r"(?m)^\s*module\s+cnn_v10_pw_dsp16\b", primitive))
    if count != 1:
        raise RuntimeError(f"expected one fullwidth module in tested primitive source, found {count}")
    renamed = re.sub(
        r"(?m)^(\s*module\s+)cnn_v10_pw_dsp16\b",
        r"\1cnn_v10_pw_dsp16_fullwidth_reference",
        primitive,
        count=1,
    )
    if re.search(r"(?m)^\s*module\s+cnn_v10_pw_dsp16\b", fused_leaf):
        raise RuntimeError("fused leaf source unexpectedly defines the product wrapper name")
    return renamed.rstrip() + "\n\n" + fused_leaf.rstrip() + "\n" + wrapper_text()


def patch_component_xml(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if any(f"<spirit:name>{port}</spirit:name>" in text for port in PORTS):
        raise RuntimeError("component.xml already contains half2x physical ports")
    bus_anchor = "    <spirit:busInterface>\n      <spirit:name>ap_clk</spirit:name>"
    if text.count(bus_anchor) != 1:
        raise RuntimeError("cannot find unique ap_clk bus-interface anchor")
    bus_xml = """    <spirit:busInterface>
      <spirit:name>pw_fast_clk</spirit:name>
      <spirit:busType spirit:vendor="xilinx.com" spirit:library="signal" spirit:name="clock" spirit:version="1.0"/>
      <spirit:abstractionType spirit:vendor="xilinx.com" spirit:library="signal" spirit:name="clock_rtl" spirit:version="1.0"/>
      <spirit:slave/>
      <spirit:portMaps>
        <spirit:portMap><spirit:logicalPort><spirit:name>CLK</spirit:name></spirit:logicalPort><spirit:physicalPort><spirit:name>pw_fast_clk</spirit:name></spirit:physicalPort></spirit:portMap>
      </spirit:portMaps>
      <spirit:parameters>
        <spirit:parameter><spirit:name>ASSOCIATED_RESET</spirit:name><spirit:value spirit:id="BUSIFPARAM_VALUE.PW_FAST_CLK.ASSOCIATED_RESET">pw_fast_rst</spirit:value></spirit:parameter>
      </spirit:parameters>
    </spirit:busInterface>
    <spirit:busInterface>
      <spirit:name>pw_fast_rst</spirit:name>
      <spirit:busType spirit:vendor="xilinx.com" spirit:library="signal" spirit:name="reset" spirit:version="1.0"/>
      <spirit:abstractionType spirit:vendor="xilinx.com" spirit:library="signal" spirit:name="reset_rtl" spirit:version="1.0"/>
      <spirit:slave/>
      <spirit:portMaps>
        <spirit:portMap><spirit:logicalPort><spirit:name>RST</spirit:name></spirit:logicalPort><spirit:physicalPort><spirit:name>pw_fast_rst</spirit:name></spirit:physicalPort></spirit:portMap>
      </spirit:portMaps>
      <spirit:parameters>
        <spirit:parameter><spirit:name>POLARITY</spirit:name><spirit:value spirit:id="BUSIFPARAM_VALUE.PW_FAST_RST.POLARITY">ACTIVE_HIGH</spirit:value></spirit:parameter>
      </spirit:parameters>
    </spirit:busInterface>
"""
    text = text.replace(bus_anchor, bus_xml + bus_anchor)
    port_anchor = "      <spirit:port>\n        <spirit:name>ap_clk</spirit:name>"
    if text.count(port_anchor) != 1:
        raise RuntimeError("cannot find unique ap_clk model-port anchor")
    port_xml = """      <spirit:port>
        <spirit:name>pw_fast_clk</spirit:name>
        <spirit:wire><spirit:direction>in</spirit:direction><spirit:wireTypeDefs><spirit:wireTypeDef><spirit:typeName>std_logic</spirit:typeName><spirit:viewNameRef>xilinx_verilogsynthesis</spirit:viewNameRef><spirit:viewNameRef>xilinx_verilogbehavioralsimulation</spirit:viewNameRef></spirit:wireTypeDef></spirit:wireTypeDefs></spirit:wire>
      </spirit:port>
      <spirit:port>
        <spirit:name>pw_fast_rst</spirit:name>
        <spirit:wire><spirit:direction>in</spirit:direction><spirit:wireTypeDefs><spirit:wireTypeDef><spirit:typeName>std_logic</spirit:typeName><spirit:viewNameRef>xilinx_verilogsynthesis</spirit:viewNameRef><spirit:viewNameRef>xilinx_verilogbehavioralsimulation</spirit:viewNameRef></spirit:wireTypeDef></spirit:wireTypeDefs></spirit:wire>
      </spirit:port>
"""
    text = text.replace(port_anchor, port_xml + port_anchor)
    path.write_text(text, encoding="utf-8", newline="\n")
    ET.parse(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-ip", required=True, type=Path)
    parser.add_argument("--output-ip", type=Path)
    parser.add_argument("--primitive-source", required=True, type=Path)
    parser.add_argument("--fused-leaf-source", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()

    source = args.source_ip.resolve()
    source_rtl = source / "hdl" / "verilog"
    primitive_path = args.primitive_source.resolve()
    fused_leaf_path = args.fused_leaf_source.resolve()
    if sha256_file(primitive_path) != EXPECTED_PRIMITIVE_SHA256:
        raise RuntimeError("tested fused primitive SHA256 mismatch")
    if sha256_file(fused_leaf_path) != EXPECTED_FUSED_LEAF_SHA256:
        raise RuntimeError("tested fused leaf SHA256 mismatch")
    source_items = inventory(source)
    modules = parse_modules(source_rtl)
    closure, edges = compute_closure(modules)
    direct_leaf_instances = sum(
        int(edge["instances"]) for edge in edges if edge["child"] == LEAF
    )
    analysis = {
        "closure_modules": sorted(closure),
        "closure_module_count": len(closure),
        "closure_files": sorted({modules[name].path.name for name in closure}),
        "edges": edges,
        "direct_leaf_instances": direct_leaf_instances,
    }
    base_receipt: dict[str, object] = {
        "schema": "cnn-v10-pw-half2x-fused-alu-generated-rtl-transform-v1",
        "pass": False,
        "analysis_only": args.analyze_only,
        "source_ip": str(source),
        "source_inventory_sha256": inventory_sha(source_items),
        "source_component_sha256": sha256_file(source / "component.xml"),
        "primitive_source": str(primitive_path),
        "primitive_source_sha256": sha256_file(primitive_path),
        "fused_leaf_source": str(fused_leaf_path),
        "fused_leaf_source_sha256": sha256_file(fused_leaf_path),
        "analysis": analysis,
    }
    if args.analyze_only:
        base_receipt["pass"] = TOP in closure and direct_leaf_instances == 16
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(base_receipt, indent=2) + "\n", encoding="utf-8")
        if not base_receipt["pass"]:
            raise SystemExit("hierarchy analysis gate failed")
        return 0

    if args.output_ip is None:
        raise SystemExit("--output-ip is required unless --analyze-only is used")
    if direct_leaf_instances != 16:
        raise RuntimeError(f"expected 16 PW leaves, found {direct_leaf_instances}")
    output = args.output_ip.resolve()
    if output.exists():
        raise RuntimeError(f"refusing to overwrite output tree {output}")
    shutil.copytree(source, output)

    out_modules = parse_modules(output / "hdl" / "verilog")
    by_file: dict[Path, list[str]] = {}
    for name in closure:
        if name != LEAF:
            by_file.setdefault(out_modules[name].path, []).append(name)
    changed_files: list[dict[str, object]] = []
    propagated_instances = 0
    for path, names in sorted(by_file.items(), key=lambda item: item[0].name):
        if len(names) != 1:
            raise RuntimeError(
                f"expected one propagated module per generated file, got {names} in {path}"
            )
        before_bytes = path.read_bytes()
        before = before_bytes.decode("utf-8")
        name = names[0]
        definition = out_modules[name]
        child_counts = {
            str(edge["child"]): int(edge["instances"])
            for edge in edges
            if edge["parent"] == name
        }
        patched, count = patch_ancestor(definition.text, name, child_counts)
        current = before[: definition.start] + patched + before[definition.end :]
        path.write_text(current, encoding="utf-8", newline="\n")
        propagated_instances += count
        after = path.read_bytes()
        changed_files.append(
            {
                "path": path.relative_to(output).as_posix(),
                "before_sha256": sha256_bytes(before_bytes),
                "after_sha256": sha256_bytes(after),
            }
        )

    leaf_path = output / "hdl" / "verilog" / "cnn_v10_pw_dsp16.v"
    leaf_before = leaf_path.read_bytes()
    leaf_after = patch_leaf(
        primitive_path.read_text(encoding="utf-8"),
        fused_leaf_path.read_text(encoding="utf-8"),
    )
    leaf_path.write_text(leaf_after, encoding="utf-8", newline="\n")
    changed_files.append(
        {
            "path": leaf_path.relative_to(output).as_posix(),
            "before_sha256": sha256_bytes(leaf_before),
            "after_sha256": sha256_file(leaf_path),
        }
    )

    xml_path = output / "component.xml"
    xml_before = xml_path.read_bytes()
    patch_component_xml(xml_path)
    changed_files.append(
        {
            "path": "component.xml",
            "before_sha256": sha256_bytes(xml_before),
            "after_sha256": sha256_file(xml_path),
        }
    )

    final_modules = parse_modules(output / "hdl" / "verilog")
    final_closure, final_edges = compute_closure(final_modules)
    top_text = final_modules[TOP].text
    leaf_text = final_modules[LEAF].text
    leaf_file_text = leaf_path.read_text(encoding="utf-8")
    top_header_close, top_header_end = find_header_close(top_text, TOP)
    top_header = top_text[:top_header_close]
    propagated_connections_ok = True
    for edge in final_edges:
        parent = str(edge["parent"])
        child = str(edge["child"])
        definition = final_modules[parent]
        spans = instance_spans(definition.text, child)
        if len(spans) != int(edge["instances"]):
            propagated_connections_ok = False
            break
        for open_pos, close_pos in spans:
            body = definition.text[open_pos:close_pos]
            if body.count(".pw_fast_clk(pw_fast_clk)") != 1:
                propagated_connections_ok = False
            if body.count(".pw_fast_rst(pw_fast_rst)") != 1:
                propagated_connections_ok = False
    checks = {
        "source_tree_unchanged": inventory_sha(inventory(source)) == inventory_sha(source_items),
        "top_reached": TOP in final_closure,
        "leaf_instances_16": direct_leaf_instances == 16,
        "propagated_instance_edges": propagated_instances,
        "top_fast_clock_port_once": len(re.findall(r"\bpw_fast_clk\b", top_header)) == 1,
        "top_fast_reset_port_once": len(re.findall(r"\bpw_fast_rst\b", top_header)) == 1,
        "top_fast_clock_input_once": top_text[top_header_end:].count("input wire pw_fast_clk;") == 1,
        "top_fast_reset_input_once": top_text[top_header_end:].count("input wire pw_fast_rst;") == 1,
        "all_hierarchy_edges_connected": propagated_connections_ok,
        "leaf_wrapper_once": len(re.findall(r"(?m)^\s*module\s+cnn_v10_pw_dsp16\b", leaf_path.read_text(encoding="utf-8"))) == 1,
        "leaf_reference_once": len(re.findall(r"(?m)^\s*module\s+cnn_v10_pw_dsp16_fullwidth_reference\b", leaf_path.read_text(encoding="utf-8"))) == 1,
        "fused_leaf_once": len(re.findall(r"(?m)^\s*module\s+cnn_v10_pw_dsp16_half2x_fused_alu\b", leaf_file_text)) == 1,
        "fused_fast_once": len(re.findall(r"(?m)^\s*module\s+cnn_v10_pw_dsp8_fast_fused_alu\b", leaf_file_text)) == 1,
        "no_unrenamed_primitive_product_module": len(re.findall(r"(?m)^\s*module\s+cnn_v10_pw_dsp16\b", leaf_file_text)) == 1,
        "wrapper_targets_fused_leaf": "cnn_v10_pw_dsp16_half2x_fused_alu fused_half2x" in leaf_text,
        "leaf_fast_clock_direct": ".fast_clk(pw_fast_clk)" in leaf_text,
        "leaf_fast_reset_direct": ".fast_rst(pw_fast_rst)" in leaf_text,
        "fused_latency8_due_pipe": "reg [6:0] due_valid_pipe;" in leaf_file_text and "wire result_due = due_valid_pipe[6];" in leaf_file_text,
        "fused_ii1_accept": "if (slow_ce && in_valid)" in leaf_file_text,
        "fused_opmode_0x195": "9'h195" in leaf_file_text,
        "fused_areg_breg2": ".AREG(EXTRA_AB_REG ? 2 : 1)" in leaf_file_text and ".BREG(EXTRA_AB_REG ? 2 : 1)" in leaf_file_text,
        "component_xml_parse": True,
        "component_clock_names_once": xml_path.read_text(encoding="utf-8").count("<spirit:name>pw_fast_clk</spirit:name>") == 3,
        "component_reset_names_once": xml_path.read_text(encoding="utf-8").count("<spirit:name>pw_fast_rst</spirit:name>") == 3,
    }
    passed = all(value is True or (key == "propagated_instance_edges" and value > 0) for key, value in checks.items())
    out_items = inventory(output)
    base_receipt.update(
        {
            "pass": passed,
            "output_ip": str(output),
            "output_inventory_sha256": inventory_sha(out_items),
            "output_component_sha256": sha256_file(xml_path),
            "changed_files": sorted(changed_files, key=lambda item: str(item["path"])),
            "checks": checks,
            "final_edges": final_edges,
            "scope": "generated RTL hierarchy clock/reset propagation plus leaf replacement and IP-XACT ports",
            "deployment_ready": False,
        }
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(base_receipt, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit("post-transform validation failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
