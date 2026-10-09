"""Verify board PS DW3->DW7 capture bytes and report host-ORT differences.

This tool treats the board collector's tensors as the golden and host outputs
only as independent comparison data. It never promotes host recomputation to a
board result.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from split_stage2_dw3_dw7 import OLD_INPUTS, sha256


def _compare(board, host):
    if board.shape != host.shape:
        raise ValueError("host reference shape differs from board capture")
    delta = np.abs(board.astype(np.float64) - host.astype(np.float64))
    return {"exact_bytes_match": board.tobytes(order="C") == host.tobytes(order="C"),
            "max_abs": float(delta.max()) if delta.size else 0.0,
            "rms_abs": float(np.sqrt(np.mean(delta * delta))) if delta.size else 0.0,
            "allclose_rtol_1e-4_atol_1e-5": bool(np.allclose(board, host, rtol=1e-4, atol=1e-5))}


def verify(split_dir, collection_dir, expected_split_sha256,
           expected_collection_sha256, output_path=None):
    split_dir = Path(split_dir)
    collection_dir = Path(collection_dir)
    split_manifest_path = split_dir / "manifest.json"
    collection_manifest_path = collection_dir / "board-ps-collection-manifest.json"
    if sha256(split_manifest_path) != expected_split_sha256:
        raise ValueError("stage2 split manifest SHA256 mismatch")
    if sha256(collection_manifest_path) != expected_collection_sha256:
        raise ValueError("board collection manifest SHA256 mismatch")
    split = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    collection = json.loads(collection_manifest_path.read_text(encoding="utf-8"))
    if collection.get("status") != "BOARD_PS_CPU_DW3_TO_DW7_COLLECTION":
        raise ValueError("collection manifest is not from the stage2 board PS collector")
    provenance = collection.get("provenance", {})
    collector_source = Path(__file__).resolve().parents[2] / "board/collect_stage2_dw3_dw7.py"
    actual_collector_sha256 = sha256(collector_source)
    if split.get("collector", {}).get("source_sha256") != actual_collector_sha256 or \
            provenance.get("source_sha256") != actual_collector_sha256:
        raise ValueError("board collector source SHA differs from split pin or board receipt")
    if provenance.get("pl_used") is not False or provenance.get("camera_used") is not False:
        raise ValueError("collection must be explicitly marked CPU-only without camera")
    if collection.get("source_model_sha256") != split.get("source_model", {}).get("sha256"):
        raise ValueError("board collection model identity differs from split")
    if collection.get("split_manifest_sha256") != expected_split_sha256:
        raise ValueError("board collection does not pin the expected split manifest")
    collector_pin = split.get("collector", {})
    if provenance.get("partition_client_source_sha256") != \
            collector_pin.get("partition_client_source_sha256") or \
            provenance.get("partition_runner_sha256") != \
            collector_pin.get("partition_runner_binary_sha256"):
        raise ValueError("board collection runner/client identities differ from split pins")
    if collection.get("stage_model_sha256") != {
            stage: split["stages"][stage]["sha256"] for stage in ("prefix", "region")}:
        raise ValueError("board collection stage model identities differ")
    cases = collection.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        raise ValueError("board collection must contain exactly three cases")

    reports = []
    for index, ((input_name, expected_input_sha), case) in enumerate(zip(OLD_INPUTS, cases)):
        if case.get("sample_id") != "image-%02d" % index:
            raise ValueError("case order/identity mismatch")
        if case.get("input", {}).get("path") != input_name or \
                case.get("input", {}).get("sha256") != expected_input_sha:
            raise ValueError("case input tensor identity mismatch")
        comparisons = {}
        for label in ("pre-dw3", "dw3-output", "dw7-output"):
            record = case.get("files", {}).get(label)
            host_record = split["host_reference"]["samples"][index]["host_reference_files"][label]
            if not isinstance(record, dict) or record.get("dtype") != "<f4":
                raise ValueError("missing board FP32 capture: %s case %d" % (label, index))
            board_path = collection_dir / record["path"]
            if sha256(board_path) != record.get("sha256") or board_path.stat().st_size != record.get("bytes"):
                raise ValueError("board tensor SHA/size mismatch: %s case %d" % (label, index))
            if record.get("shape") != host_record.get("shape"):
                raise ValueError("board tensor shape differs from frozen host split contract")
            host_path = split_dir / host_record["path"]
            if sha256(host_path) != host_record.get("sha256"):
                raise ValueError("frozen independent host reference SHA mismatch")
            board = np.fromfile(str(board_path), dtype="<f4").reshape(record["shape"])
            host = np.fromfile(str(host_path), dtype="<f4").reshape(record["shape"])
            if not np.isfinite(board).all() or not np.isfinite(host).all():
                raise ValueError("non-finite tensor in board collection or host reference")
            comparisons[label] = {"board_sha256": record["sha256"],
                                  "host_sha256": host_record["sha256"],
                                  "comparison": _compare(board, host),
                                  "board_provenance": "actual_board_ps_cpu_collector",
                                  "host_provenance": "independent_host_ort_reference_only"}
        reports.append({"sample_id": case["sample_id"], "input_sha256": expected_input_sha,
                        "tensors": comparisons})
    result = {
        "schema_version": 1,
        "status": "BOARD_PS_TENSORS_INTEGRITY_VERIFIED_HOST_COMPARISON_REPORTED",
        "board_golden_source": "board-side PS CPU ORT collection; SHA-verified",
        "host_reference_role": "independent numerical comparison only; never the board golden",
        "source_model_sha256": collection["source_model_sha256"],
        "split_manifest_sha256": expected_split_sha256,
        "collection_manifest_sha256": expected_collection_sha256,
        "collector_source_sha256": provenance.get("source_sha256"),
        "board_identity": provenance.get("board_label"),
        "execution": provenance.get("execution"), "pl_used": False,
        "cases": reports,
    }
    encoded = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if output_path:
        Path(output_path).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-dir", required=True)
    parser.add_argument("--collection-dir", required=True)
    parser.add_argument("--expected-split-manifest-sha256", required=True)
    parser.add_argument("--expected-collection-manifest-sha256", required=True)
    parser.add_argument("--output", help="optional verification report path")
    args = parser.parse_args()
    verify(args.split_dir, args.collection_dir, args.expected_split_manifest_sha256,
           args.expected_collection_manifest_sha256, args.output)


if __name__ == "__main__":
    main()
