#!/usr/bin/env python3
"""Run or preflight the portable paired V10 full normal-path bundle.

The command never programs PL, applies an overlay, loads a module, or discovers
devices.  Non-preflight execution requires the caller to provide an already
released ABI10.1 device node and the existing C ORT partition runner.
"""

import argparse
import hashlib
import json
import os
import pathlib
import time

import numpy as np

try:
    from cnn_ddr_v10_runtime import LinuxIoctlV10Transport
    from cnn_pipeline_v10_bundle import load_v10_release_bundle
    from run_cnn_pipeline_v10_board_window import create_full_model_runtime
    from run_cnn_pipeline_v7_fixed import (load_existing_split_clients,
                                           mobileclip_preprocess)
    from cnn_ddr_v5_runtime import load_v5_split_contracts
    from cnn_pipeline_v10_deployment import load_v10_platform_deployment
except ImportError:
    from .cnn_ddr_v10_runtime import LinuxIoctlV10Transport
    from .cnn_pipeline_v10_bundle import load_v10_release_bundle
    from .run_cnn_pipeline_v10_board_window import create_full_model_runtime
    from .run_cnn_pipeline_v7_fixed import (load_existing_split_clients,
                                            mobileclip_preprocess)
    from .cnn_ddr_v5_runtime import load_v5_split_contracts
    from .cnn_pipeline_v10_deployment import load_v10_platform_deployment


def preflight_bundle(bundle_root, expected_bundle_sha256):
    loaded = load_v10_release_bundle(bundle_root, expected_bundle_sha256)
    if loaded["manifest"].get("schema") != "cnn-pipeline-v10.1-release-bundle-v2":
        raise ValueError("deployment preflight requires V10.1 release bundle schema v2")
    split = load_v5_split_contracts(
        loaded["model_root"], loaded["model_manifest_sha256"])
    if split["manifest_sha256"] != loaded["model_manifest_sha256"]:
        raise ValueError("split model loader identity mismatch")
    return loaded


def _write_result(output_dir, loaded, results, timing, runtime_summary, cleanup):
    root = pathlib.Path(output_dir)
    if root.exists():
        raise RuntimeError("output path already exists: %s" % root)
    root.mkdir(parents=True)
    frames = []
    for result in results:
        feature = np.asarray(result["features"], dtype="<f4").reshape(512)
        name = "features-frame-%s.f32" % result["frame_id"]
        raw = feature.tobytes(order="C")
        (root / name).write_bytes(raw)
        frames.append({
            "frame_id": result["frame_id"],
            "feature_file": name,
            "feature_sha256": hashlib.sha256(raw).hexdigest(),
            "shadow_partner_used": result["shadow_partner_used"],
            "paired_with": result["paired_with"],
            "pl_completions": result["pl_completions"],
            "pair_timing": result["pair_timing"],
        })
    real_count = len(frames)
    shadow_count = sum(1 for item in frames if item["shadow_partner_used"])
    receipt = {
        "schema": "cnn-pipeline-v10-full-model-result-v1",
        "status": "CNN_PIPELINE_V10_FULL_MODEL_COMPLETED",
        "release_manifest_sha256": loaded["manifest_sha256"],
        "parameter_identity_words": list(loaded["parameter_manifest_words"]),
        "split_model_manifest_sha256": loaded["model_manifest_sha256"],
        "real_frame_count": real_count,
        "shadow_frame_count": shadow_count,
        "hardware_lane_frame_count": real_count + shadow_count,
        "shadow_counts_as_real_throughput": False,
        "wall_ms": timing["process_wall_ms"],
        "timing": timing,
        "runtime_summary": runtime_summary,
        "scheduling_scope": "synchronous serial PS->PL stages; no cross-pair pipeline",
        "frames": frames,
        "cleanup": cleanup,
    }
    (root / "result.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--deployment-manifest")
    parser.add_argument("--expected-deployment-sha256")
    parser.add_argument("--runner")
    parser.add_argument("--device", default="/dev/network10_v10")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--timeout-s", type=float, default=300.0)
    parser.add_argument("--input-image", action="append")
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)

    loaded = preflight_bundle(args.bundle_root, args.expected_bundle_sha256)
    if args.preflight_only:
        print(json.dumps({
            "status": "CNN_PIPELINE_V10_RELEASE_PREFLIGHT_PASS_NO_DEVICE_OPEN",
            "release_manifest_sha256": loaded["manifest_sha256"],
            "parameter_identity_words": list(loaded["parameter_manifest_words"]),
            "split_model_manifest_sha256": loaded["model_manifest_sha256"],
            "board_operation_performed": False,
        }, indent=2))
        return 0
    if not args.deployment_manifest or not args.expected_deployment_sha256:
        parser.error("execution needs --deployment-manifest and --expected-deployment-sha256")
    load_v10_platform_deployment(
        args.deployment_manifest, args.expected_deployment_sha256,
        loaded["manifest_sha256"])
    if (not args.runner or not args.input_image or not args.output_dir or
            args.threads <= 0 or args.timeout_s <= 0):
        parser.error("execution needs --runner, --input-image, --output-dir, positive threads and timeout")
    if os.path.exists(args.output_dir):
        raise RuntimeError("output path already exists: %s" % args.output_dir)

    clients = None
    transport = None
    runtime = None
    primary = None
    cleanup = None
    process_started = time.perf_counter()
    try:
        started = time.perf_counter()
        clients, unused_split_sha = load_existing_split_clients(
            loaded["model_root"], args.runner, loaded["model_manifest"],
            loaded["model_manifest_sha256"], threads=args.threads)
        transport = LinuxIoctlV10Transport(
            args.device,
            expected_parameter_manifest_words=loaded["parameter_manifest_words"])
        runtime = create_full_model_runtime(
            transport, loaded["parameter_contract"],
            loaded["manifest_sha256"], clients, timeout_s=args.timeout_s)
        setup_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        items = [(index, mobileclip_preprocess(path))
                 for index, path in enumerate(args.input_image)]
        preprocess_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        results = runtime.run(items)
        execution_ms = (time.perf_counter() - started) * 1000.0
        runtime_summary = runtime.last_run_summary
    except Exception as error:
        primary = error
        raise
    finally:
        cleanup_started = time.perf_counter()
        if runtime is not None and not runtime.closed:
            try:
                cleanup = runtime.close()
            except Exception:
                if primary is None:
                    raise
        elif transport is not None:
            try:
                transport.close()
            except Exception:
                if primary is None:
                    raise
        elif clients is not None:
            for client in clients.values():
                try:
                    client.close()
                except Exception:
                    if primary is None:
                        raise
        cleanup_ms = (time.perf_counter() - cleanup_started) * 1000.0
    timing = {
        "setup_ms": setup_ms, "preprocess_ms": preprocess_ms,
        "execution_ms": execution_ms, "cleanup_ms": cleanup_ms,
        "process_wall_ms": (time.perf_counter() - process_started) * 1000.0,
        "steady_state_claim": False,
    }
    _write_result(args.output_dir, loaded, results, timing, runtime_summary, cleanup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["preflight_bundle", "main"]
