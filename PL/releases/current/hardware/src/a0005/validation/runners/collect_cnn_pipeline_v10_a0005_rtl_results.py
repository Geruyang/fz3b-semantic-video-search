#!/usr/bin/env python3
"""Build a frozen V10 RTL result receipt from successful xsim PASS logs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


# Generated HLS RTL includes deadlock-monitor headers that are part of the
# frozen simulation dependency set.  Keep this aligned with the PowerShell
# snapshot digest instead of silently omitting .vh files.
RTL_DEPENDENCY_SUFFIXES = {".v", ".sv", ".vh", ".dat", ".mem", ".hex"}
SUPPORTED_FIXTURE_SCHEMAS = {
    "cnn-v10-paired-rtl-fixtures-v1",
    "cnn-v10.1-paired-rtl-fixtures-v1",
    "cnn-v10.3-a0003-rtl-fixtures-v1",
    "cnn-v10.4-a0004-bram-stage-rtl-fixtures-v1",
}

BRAM_STAGE_FIFO_DEPTHS = {
    "q3_a": 4096, "q3_b": 4096,
    "q7_a": 8192, "q7_b": 8192,
    "expanded_a": 2048, "expanded_b": 2048,
}
SIMULATOR_ERROR_LINE = re.compile(r"^(?:Fatal:|ERROR:)", re.MULTILINE)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path, files: list[Path] | None = None) -> list[dict[str, str]]:
    selected = files if files is not None else [
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in RTL_DEPENDENCY_SUFFIXES
    ]
    records = []
    for path in selected:
        resolved = path.resolve()
        relative = resolved.relative_to(root.resolve()).as_posix()
        records.append({"path": relative, "sha256": file_sha256(resolved)})
    records.sort(key=lambda item: item["path"])
    if not records or len({item["path"] for item in records}) != len(records):
        raise ValueError("empty or duplicate source inventory")
    return records


def canonical_digest(records: list[dict[str, str]]) -> str:
    normalized = [{"path": item["path"].replace("\\", "/"),
                   "sha256": item["sha256"].lower()} for item in records]
    normalized.sort(key=lambda item: item["path"])
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fields(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result


def integers(text: str, count: int) -> list[int]:
    values = [int(item, 0) for item in text.split("/")]
    if len(values) != count:
        raise ValueError(f"expected {count} slash-separated integers, got {text!r}")
    return values


def fixture_record(manifest: dict[str, Any], profile: int) -> dict[str, Any]:
    matches = [case for case in manifest["cases"] if case["profile"] == profile]
    if len(matches) != 1:
        raise ValueError(f"fixture manifest has {len(matches)} cases for profile {profile}")
    case = matches[0]
    result: dict[str, Any] = {"name": case["name"]}
    for key in ("params", "input_a", "input_b", "expected_a", "expected_b"):
        result[f"{key}_sha256"] = case["files"][key]["sha256"].lower()
    return result


def validate_product_freeze(path: Path, expected_sha256: str) -> dict[str, Any]:
    actual = file_sha256(path)
    if actual != expected_sha256.lower():
        raise ValueError(f"product source freeze SHA mismatch: {actual}")
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    files = manifest.get("files", [])
    identity = manifest.get("identity") or {}
    candidate_manifest = manifest.get("schema") == "dual-lane-storage-dw7-opt-source-manifest-v1"
    # A0004 removed the retired stage-DDR-ring header from the product source
    # set, so its canonical freeze has 17 members.  Keep the historical
    # 18-member gate for earlier ABIs and fail closed if an A0004 manifest
    # silently reintroduces the retired header.
    expected_file_count = 8 if candidate_manifest else (
        17 if identity.get("core_abi") == "0x000A0004" else 18
    )
    if (len(files) != expected_file_count or
            len({item["path"] for item in files}) != expected_file_count):
        raise ValueError(
            f"product source freeze must contain exactly {expected_file_count} "
            "unique files for this ABI")
    if identity.get("core_abi") == "0x000A0004" and any(
            re.search(r"(?i)cnn_v10_stage_ring[.]hpp$", item["path"])
            for item in files):
        raise ValueError("A0004 product source freeze contains retired stage-ring header")
    for item in files:
        if (not item.get("path") or
                not re.fullmatch(r"[0-9a-fA-F]{64}", item.get("sha256", "")) or
                not item.get("role")):
            raise ValueError("malformed product source freeze member")
    return {"path": str(path.resolve()), "sha256": actual,
            "schema": manifest.get("schema"), "file_count": len(files),
            "identity": identity, "files": files}


def parse_log(path: Path, manifest: dict[str, Any], exit_code: int,
              log_index: int = 0) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    error = SIMULATOR_ERROR_LINE.search(text)
    if error is not None:
        line = text[error.start():].splitlines()[0]
        raise ValueError(f"simulator error marker in {path}: {line}")
    log_record = {"path": str(path.resolve()), "sha256": file_sha256(path)}
    lines = text.splitlines()
    fifo_summaries: dict[str, dict[str, int]] = {}
    for line in lines:
        if not line.startswith("CNN_PIPELINE_V10_FIFO_SUMMARY "):
            continue
        value = fields(line)
        name = value["fifo"]
        if name in fifo_summaries:
            raise ValueError(f"duplicate FIFO summary for {name} in {path}")
        fifo_summaries[name] = {
            "configured_depth": int(value["configured_depth"]),
            "accepted_writes": int(value["accepted_writes"]),
            "accepted_reads": int(value["accepted_reads"]),
            "high_water": int(value["high_water"]),
            "final_occupancy": int(value["final_occupancy"]),
            "write_full_stall_cycles": int(value["write_full_stall_cycles"]),
            "repeat_launch_checks": int(value.get("repeat_launch_checks", "0")),
        }
    bram_stage = manifest.get("schema") == "cnn-v10.4-a0004-bram-stage-rtl-fixtures-v1"
    expected_fifos = (set(BRAM_STAGE_FIFO_DEPTHS) if bram_stage else
                      {"q3_a", "q3_b", "q7_a", "q7_b"})
    if fifo_summaries and set(fifo_summaries) != expected_fifos:
        raise ValueError(f"incomplete FIFO summaries in {path}: {sorted(fifo_summaries)}")
    ring_summaries: dict[int, dict[str, dict[str, int]]] = {}
    for line in lines:
        if not line.startswith("CNN_PIPELINE_V10_RING_SUMMARY "):
            continue
        value = fields(line)
        run = int(value["run"])
        key = f"core{int(value['core'])}-ring{int(value['ring'])}"
        run_summaries = ring_summaries.setdefault(run, {})
        if key in run_summaries:
            raise ValueError(f"duplicate ring summary for run={run} {key} in {path}")
        run_summaries[key] = {name: int(value[name]) for name in
                              ("write_bursts", "read_bursts",
                               "write_wraps", "read_wraps")}
    residual_summaries: dict[int, dict[str, dict[str, int]]] = {}
    for line in lines:
        if not line.startswith("CNN_PIPELINE_V10_RESIDUAL_RING_SUMMARY "):
            continue
        value = fields(line)
        run = int(value["run"])
        key = f"core{int(value['core'])}"
        record = {name: int(value[name]) for name in
                  ("write_bursts", "read_bursts", "write_wraps", "read_wraps",
                   "legacy_stage_writes", "legacy_stage_reads")}
        if key in residual_summaries.setdefault(run, {}):
            raise ValueError(f"duplicate residual summary for run={run} {key} in {path}")
        residual_summaries[run][key] = record
    cases: list[dict[str, Any]] = []
    serial = 0
    for line in lines:
        if line.startswith("CNN_PIPELINE_V10_SHARED_PASS "):
            value = fields(line)
            if value.get("functional_pass") != "1" or value.get("shared_ddr") != "1":
                raise ValueError(f"invalid shared PASS claims in {path}: {line}")
            if value.get("stress_exercised") == "1" and int(value.get("pause_hits", "0")) <= 0:
                raise ValueError(f"stress PASS lacks observed pause in {path}: {line}")
            profile = int(value["profile"])
            run = int(value["run"])
            rings = ring_summaries.get(run, {})
            if manifest.get("schema") == "cnn-v10.3-a0003-rtl-fixtures-v1":
                expected_rings = {f"core{core}-ring{ring}"
                                  for core in range(2) for ring in range(3)}
                if set(rings) != expected_rings:
                    raise ValueError(f"incomplete A0003 ring summaries for run={run} in {path}")
                if any(any(record[name] <= 0 for name in record)
                       for record in rings.values()):
                    raise ValueError(f"A0003 ring summary lacks wrap/traffic for run={run} in {path}")
            residuals = residual_summaries.get(run, {})
            if bram_stage:
                if rings:
                    raise ValueError(f"BRAM-stage run emitted stale stage-ring summaries in {path}")
                if set(fifo_summaries) != set(BRAM_STAGE_FIFO_DEPTHS):
                    raise ValueError(f"incomplete BRAM-stage FIFO summaries in {path}")
                for name, depth in BRAM_STAGE_FIFO_DEPTHS.items():
                    record = fifo_summaries[name]
                    if record["configured_depth"] != depth:
                        raise ValueError(f"wrong FIFO depth for {name} in {path}")
                    if (record["accepted_writes"] <= 0 or record["accepted_reads"] <= 0 or
                            record["high_water"] > depth or record["final_occupancy"] != 0):
                        raise ValueError(f"invalid BRAM-stage FIFO observation for {name} in {path}")
                    if value.get("repeat_without_reset") == "1" and record["repeat_launch_checks"] < 2:
                        raise ValueError(f"repeat launch gate was not exercised for {name} in {path}")
                if set(residuals) != {"core0", "core1"}:
                    raise ValueError(f"incomplete residual DDR summaries for run={run} in {path}")
                for record in residuals.values():
                    if record["legacy_stage_writes"] != 0 or record["legacy_stage_reads"] != 0:
                        raise ValueError(f"legacy stage DDR access observed for run={run} in {path}")
                    residual_fields = ("write_bursts", "read_bursts",
                                       "write_wraps", "read_wraps")
                    if profile == 3:
                        # P3 transition stages do not consume the normal-mode
                        # residual path.  Require the instrumented ring to stay
                        # completely idle rather than weakening this gate.
                        if any(record[name] != 0 for name in residual_fields):
                            raise ValueError(
                                f"P3 residual DDR ring unexpectedly active for "
                                f"run={run} in {path}")
                    elif any(record[name] <= 0 for name in residual_fields):
                        raise ValueError(
                            f"residual DDR ring lacks traffic/wrap for run={run} in {path}")
            pressure_mode = int(value.get("pressure_mode", "1" if value.get("stress_exercised") == "1" else "0"))
            if pressure_mode == 2 and value.get("stress_exercised") != "1":
                raise ValueError(f"strong pressure PASS lacks stress claim in {path}: {line}")
            cases.append({
                "id": f"log{log_index}-{path.stem}-shared-{serial}",
                "region": value["region"], "profile": profile,
                "blocks": int(value["blocks"]), "rejection": False,
                "active_cycles": {
                    "common_start_to_done": int(value["cycles"]),
                    "core_a_last_write_response": int(value["core_a_last_b"]),
                    "core_b_last_write_response": int(value["core_b_last_b"]),
                },
                "functional_pass": value["functional_pass"] == "1",
                "performance_reference": value["performance_reference"] == "1",
                "stress_exercised": value["stress_exercised"] == "1",
                "pressure_mode": pressure_mode,
                "repeat_without_reset": value["repeat_without_reset"] == "1",
                "profile_switch": value.get("profile_switch", "0") == "1",
                "swapped": value["swapped"] == "1",
                "exit_code": exit_code, "pass_token": line,
                "fixture": fixture_record(manifest, profile),
                "traffic": {
                    "read_handshake_beats": integers(value["read_beats"], 4),
                    "write_handshake_beats": integers(value["write_beats"], 2),
                    "aggregate_issued_beats": int(value["aggregate_issued"]),
                    "pause_hit_cycles": int(value["pause_hits"]),
                },
                "ddr_config": {
                    "token_numer": integers(value["token"], 3)[0],
                    "token_denom": integers(value["token"], 3)[1],
                    "token_burst": integers(value["token"], 3)[2],
                    "b_response_delay": int(value["b_delay"]),
                },
                "fifo_observation": {
                    "scope": "whole_simulation_cumulative",
                    "fifos": fifo_summaries,
                } if fifo_summaries else None,
                "stage_ring_observation": rings or None,
                "residual_ddr_observation": residuals or None,
                "log": log_record,
            })
            serial += 1
        elif line.startswith("CNN_PIPELINE_V10_REJECT_PASS "):
            value = fields(line)
            if value.get("functional_pass") != "1" or value.get("shared_ddr") != "1":
                raise ValueError(f"invalid reject PASS claims in {path}: {line}")
            activation = {key: integers(value[f"activation_{key}"], 2)
                          for key in ("ar", "aw", "w")}
            if any(any(count != 0 for count in counts) for counts in activation.values()):
                raise ValueError(f"reject PASS contains activation traffic in {path}: {line}")
            if value.get("error_kind", "").startswith("gelu_span256_"):
                if (int(value["expected_protocol_error"]) != 2 or
                        int(value["observed_protocol_error"]) != 2 or
                        value.get("trace_inert") != "1"):
                    raise ValueError(f"bad-GELU reject lacks error-2/inert evidence in {path}: {line}")
            profile = int(value["profile"])
            cases.append({
                "id": f"log{log_index}-{path.stem}-reject-{serial}",
                "region": value["region"], "profile": profile,
                "blocks": int(value["blocks"]), "rejection": True,
                "active_cycles": {
                    "common_start_to_done": int(value["cycles"]),
                    "core_a_last_write_response": None,
                    "core_b_last_write_response": None,
                },
                "functional_pass": value["functional_pass"] == "1",
                "performance_reference": False, "stress_exercised": False,
                "exit_code": exit_code, "pass_token": line,
                "fixture": fixture_record(manifest, profile),
                "error_kind": value["error_kind"],
                "expected_protocol_error": int(value["expected_protocol_error"]),
                "observed_protocol_error": int(value["observed_protocol_error"]),
                "activation_accesses": activation,
                "trace_inert": value.get("trace_inert") == "1",
                "log": log_record,
            })
            serial += 1
    if not cases:
        raise ValueError(f"no V10 PASS token found in {path}")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, action="append", required=True)
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--dut-rtl-root", type=Path, required=True)
    parser.add_argument("--tb-root", type=Path, required=True)
    parser.add_argument("--tb-source", type=Path, action="append", required=True)
    parser.add_argument("--ddr-model", type=Path, required=True)
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--source-freeze-manifest", type=Path)
    parser.add_argument("--expected-source-freeze-sha256")
    parser.add_argument("--candidate-contract", type=Path)
    parser.add_argument("--expected-candidate-contract-sha256")
    parser.add_argument("--dsp-rtl", type=Path)
    parser.add_argument("--clock-period-ns", type=float, default=5.0)
    parser.add_argument("--post-route-achieved", action="store_true")
    parser.add_argument("--model-limited", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.exit_code != 0:
        raise ValueError("refusing to create PASS receipt for a nonzero simulator exit")
    manifest = json.loads(args.fixture_manifest.read_text(encoding="utf-8-sig"))
    if manifest.get("schema") not in SUPPORTED_FIXTURE_SCHEMAS:
        raise ValueError("unsupported fixture manifest schema")
    source_freeze = None
    if manifest.get("schema") in {"cnn-v10.3-a0003-rtl-fixtures-v1",
                                  "cnn-v10.4-a0004-bram-stage-rtl-fixtures-v1"}:
        if not args.source_freeze_manifest or not args.expected_source_freeze_sha256:
            raise ValueError("A0005 reuse of the A0004 fixture requires source manifest and expected SHA")
        if not args.dsp_rtl:
            raise ValueError("A0005 reuse of the A0004 fixture requires frozen DSP RTL")
    if args.source_freeze_manifest:
        if not args.expected_source_freeze_sha256:
            raise ValueError("source freeze manifest requires expected SHA")
        source_freeze = validate_product_freeze(
            args.source_freeze_manifest, args.expected_source_freeze_sha256)
        if manifest.get("schema") == "cnn-v10.4-a0004-bram-stage-rtl-fixtures-v1":
            if source_freeze["schema"] != "dual-lane-storage-dw7-opt-source-manifest-v1":
                raise ValueError("A0005 runner requires the candidate source manifest")
            if not args.candidate_contract or not args.expected_candidate_contract_sha256:
                raise ValueError("A0005 runner requires the candidate contract")
            contract_sha = file_sha256(args.candidate_contract)
            if contract_sha != args.expected_candidate_contract_sha256.lower():
                raise ValueError("A0005 candidate contract SHA mismatch")
            candidate_contract = json.loads(args.candidate_contract.read_text(encoding="utf-8-sig"))
            identity = candidate_contract.get("identity") or {}
            if (identity.get("core_abi"), identity.get("software"), identity.get("guard_caps")) != (
                    "0x000A0005", "sw10.5", "0x00000fff"):
                raise ValueError("A0005 candidate identity mismatch")
            source_freeze["candidate_contract"] = {
                "path": str(args.candidate_contract.resolve()),
                "sha256": contract_sha,
                "identity": identity,
            }
    dut_files = inventory(args.dut_rtl_root)
    tb_files = inventory(args.tb_root, args.tb_source)
    cases: list[dict[str, Any]] = []
    for log_index, log in enumerate(args.log):
        cases.extend(parse_log(log, manifest, args.exit_code, log_index))
    result = {
        "schema": "cnn-v10-rtl-results-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "dut_rtl_sha256": canonical_digest(dut_files),
            "dut_rtl_files": dut_files,
            "tb_sha256": canonical_digest(tb_files),
            "tb_files": tb_files,
            "ddr_model_sha256": file_sha256(args.ddr_model),
            "fixture_manifest_sha256": file_sha256(args.fixture_manifest),
            "product_source_freeze": source_freeze,
            "dsp_rtl": ({"path": str(args.dsp_rtl.resolve()),
                         "sha256": file_sha256(args.dsp_rtl)}
                        if args.dsp_rtl else None),
        },
        "clock": {"period_ns": args.clock_period_ns,
                  "post_route_achieved": args.post_route_achieved},
        "ddr_model": {
            "shared": True, "aggregate_issue_limit": "one 128-bit data beat per token",
            "model_limited": args.model_limited,
        },
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"cases": len(cases), "dut_rtl_sha256": result["source"]["dut_rtl_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
