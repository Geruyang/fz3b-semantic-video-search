#!/usr/bin/env python3
"""Build the strict dual-clock full-platform receipt from preserved reports."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("missing artifact: %s" % path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def key_values(path: Path) -> dict:
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def number(value, label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("invalid numeric %s: %r" % (label, value))


def integer(value, label):
    parsed = number(value, label)
    if not parsed.is_integer():
        raise ValueError("non-integral %s: %r" % (label, value))
    return int(parsed)


def parse_resource(report: str, label: str) -> int:
    match = re.search(r"^\|\s*" + re.escape(label) + r"\s*\|\s*([0-9]+)\s*\|", report, re.M)
    if not match:
        raise ValueError("resource row missing: %s" % label)
    return int(match.group(1))


def pulse_min_slack(path: Path) -> float:
    values = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not re.match(r"^(Min Period|Max Period|Low Pulse Width|High Pulse Width)\s{2,}", line):
            continue
        fields = re.split(r"\s{2,}", line.strip())
        if len(fields) < 7:
            raise ValueError("malformed pulse row: %s" % line)
        values.append(float(fields[6]))
    if not values:
        raise ValueError("pulse report contains no checks")
    return min(values)


def check_timing_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8-sig")
    values = [int(value) for value in re.findall(r"^\d+\.\s+checking\s+\S+\s+\(([0-9]+)\)\s*$", text, re.M)]
    if len(values) != 12:
        raise ValueError("expected 12 check_timing categories, found %d" % len(values))
    return sum(values)


def cdc_violation_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8-sig")
    # A related 1x/2x MMCM design has no asynchronous CDC endpoint table.  Any
    # explicit CDC rule identifier is kept fail-closed for the deployment gate.
    return len(re.findall(r"\bCDC-[0-9]+\b", text))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-dir", type=Path, required=True)
    parser.add_argument("--route-dir", type=Path, required=True)
    parser.add_argument("--synth-dir", type=Path, required=True)
    parser.add_argument("--rtl-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    final_dir = args.final_dir.resolve()
    route_dir = args.route_dir.resolve()
    synth_dir = args.synth_dir.resolve()
    status = key_values(final_dir / "final-stage-status.rpt")
    if status.get("status") != "PASS":
        raise ValueError("final stage did not pass")

    utilization_path = final_dir / "utilization.rpt"
    utilization = utilization_path.read_text(encoding="utf-8-sig")
    resources = {
        "lut": parse_resource(utilization, "CLB LUTs"),
        "ff": parse_resource(utilization, "CLB Registers"),
        "bram_tiles": parse_resource(utilization, "Block RAM Tile"),
        "dsp": parse_resource(utilization, "DSPs"),
    }

    path_classes = {}
    for name in ("slow_to_slow", "fast_to_fast", "slow_to_fast", "fast_to_slow"):
        path_classes[name] = {
            "setup_wns_ns": number(status[name + "_setup_ns"], name + " setup"),
            "hold_whs_ns": number(status[name + "_hold_ns"], name + " hold"),
        }

    timing = {
        "setup_wns_ns": number(status["setup_wns_ns"], "setup WNS"),
        "hold_whs_ns": number(status["hold_whs_ns"], "hold WHS"),
        "pulse_width_min_slack_ns": pulse_min_slack(final_dir / "pulse-width.rpt"),
        "route_errors": integer(status["routing_error_count"], "routing errors"),
        "unrouted_nets": integer(status["unrouted_net_count"], "unrouted nets"),
        "drc_violations": integer(status["severe_drc_count"], "severe DRC"),
        "check_timing_violations": check_timing_count(final_dir / "check-timing.rpt"),
        "cdc_violations": cdc_violation_count(final_dir / "cdc.rpt"),
        "path_classes": path_classes,
    }
    if any(value < 0 for value in (timing["setup_wns_ns"], timing["hold_whs_ns"], timing["pulse_width_min_slack_ns"])):
        raise ValueError("global timing did not close")
    if any(value != 0 for key, value in timing.items() if key in {
        "route_errors", "unrouted_nets", "drc_violations", "check_timing_violations", "cdc_violations"
    }):
        raise ValueError("route/DRC/check_timing/CDC gate failed")
    for value in path_classes.values():
        if value["setup_wns_ns"] < 0 or value["hold_whs_ns"] < 0:
            raise ValueError("dual-clock path class did not close")

    address_paths = {
        "report_sha256": synth_dir / "address-map.rpt",
        "interface_widths_sha256": synth_dir / "interface-widths.rpt",
        "abi_wiring_sha256": synth_dir / "v10-abi-wiring.rpt",
        "exact_bd_tcl_sha256": synth_dir / "exact-bd.tcl",
    }
    address_map = {
        "hls_control": {"base": "0xa4000000", "size": "0x00010000"},
        "guard_identity": {"base": "0xa4010000", "size": "0x00010000"},
    }
    for key, path in address_paths.items():
        address_map[key] = sha256(path)

    clock = {
        "master": {"name": "clk_pl_1", "runtime_hz": 99999999, "nominal_hz": 100000000},
        "domains": {
            "driver_job": {
                "generated_clock": "clk_out1_cnn_pipeline_v10_shell_clock_wiz_0",
                "nominal_hz": 200000000,
                "implemented_exact_hz": "199999998",
                "runtime_hz": 199999998,
                "period_ns": "5.0",
            },
            "pw_local": {
                "generated_clock": "clk_out2_cnn_pipeline_v10_shell_clock_wiz_0",
                "nominal_hz": 400000000,
                "implemented_exact_hz": "399999996",
                "runtime_hz": 399999996,
                "period_ns": "2.5",
            },
        },
        "relationship": {"same_mmcm": True, "integer_ratio": 2, "phase_aligned": True},
        "mmcm": {
            "divclk_divide": number(status["mmcm_d"], "MMCM D"),
            "clkfbout_mult_f": number(status["mmcm_m"], "MMCM M"),
            "clkout_slow_divide_f": number(status["mmcm_slow_divide"], "MMCM slow divide"),
            "clkout_fast_divide_f": number(status["mmcm_fast_divide"], "MMCM fast divide"),
        },
    }
    if clock["mmcm"] != {
        "divclk_divide": 1.0, "clkfbout_mult_f": 12.0,
        "clkout_slow_divide_f": 6.0, "clkout_fast_divide_f": 3.0,
    }:
        raise ValueError("MMCM contract mismatch")

    receipt = {
        "schema": "cnn-v10.4-half2x-full-platform-v1",
        "status": "PASS",
        "pass": True,
        "identity": {
            "core_id": "0x465A5641",
            "core_abi": "0x000A0004",
            "guard_caps": "0x000007FF",
            "combined_parameter_manifest_sha256": "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9",
        },
        "address_map": address_map,
        "clock": clock,
        "timing": timing,
        "resources": resources,
        "artifacts": {
            "bitstream": artifact(final_dir / "cnn-pipeline-v10-half2x-pl1.bit"),
            "bin": artifact(final_dir / "cnn-pipeline-v10-half2x-pl1.bin"),
            "final_dcp": artifact(final_dir / "half2x-final.dcp"),
        },
        "debug_profile": {
            "mode": "release-no-ila",
            "guard_ila_count": 0,
            "pipeline_ila_count": 0,
            "debug_hub_count": 0,
            "trace_pack_present": False,
            "mmio_trace_count": 0,
            "platform_trace_mmio_register_count": 0,
            "hls_ap_none_trace_port_count": 12,
            "trace_outputs_connected": False,
            "trace_output_transport": "ap_none",
            "ltx_required": False,
        },
        "verification": {
            "full_rtl_receipt": artifact(args.rtl_receipt.resolve()),
            "hardware_programmed": False,
        },
        "provenance": {
            "route_stage_status": artifact(route_dir / "route-stage-status.rpt"),
            "route_routed_dcp": artifact(route_dir / "half2x-post-route.dcp"),
            "final_stage_status": artifact(final_dir / "final-stage-status.rpt"),
            "timing_report": artifact(final_dir / "timing-summary.rpt"),
            "pulse_width_report": artifact(final_dir / "pulse-width.rpt"),
            "route_status_report": artifact(final_dir / "route-status.rpt"),
            "drc_report": artifact(final_dir / "drc.rpt"),
            "check_timing_report": artifact(final_dir / "check-timing.rpt"),
            "cdc_report": artifact(final_dir / "cdc.rpt"),
            "utilization_report": artifact(utilization_path),
        },
    }
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"path": str(args.output), "sha256": sha256(args.output), "pass": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
