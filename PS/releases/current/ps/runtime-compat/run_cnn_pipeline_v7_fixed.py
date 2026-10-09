"""Run the existing fixed MobileCLIP graph with v7 normal block chains."""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import time

import numpy as np

try:
    from .cnn_pipeline_v7_normal_backend import (
        CnnPipelineV7NormalStageBackend, create_linux_transport)
except (ImportError, ValueError):
    from cnn_pipeline_v7_normal_backend import (
        CnnPipelineV7NormalStageBackend, create_linux_transport)


_LOGICAL_OUTPUT_NAMES = {
    "stem-prefix": "n0_input",
    "network1-bridge": "n2_input",
    "network3-bridge": "n4_input",
    "suffix": "features",
}


class _LogicalOutputClient(object):
    """Normalize original ONNX tensor names to the v6 DAG callback contract."""

    def __init__(self, client, source_name, logical_name):
        self._client = client
        self.source_name = source_name
        self.logical_name = logical_name
        self.header = client.header

    @property
    def closed(self):
        return bool(getattr(self._client, "_closed", False))

    def infer(self, tensors):
        outputs, run_ms = self._client.infer(tensors)
        if self.source_name not in outputs:
            raise ValueError("ORT output %s is missing" % self.source_name)
        return {self.logical_name: outputs[self.source_name]}, run_ms

    def close(self):
        return self._client.close()


def mobileclip_preprocess(value):
    """Use the existing S1 PIL preprocessing for paths, or accept FP32 NCHW."""
    if isinstance(value, str):
        if value.lower().endswith(".f32"):
            value = np.fromfile(value, dtype="<f4")
            if value.size != 3 * 256 * 256:
                raise ValueError("frozen FP32 input must contain 3*256*256 values")
            value = value.reshape(1, 3, 256, 256)
        else:
            try:
                from preprocess_s1 import preprocess
            except ImportError:
                from .preprocess_s1 import preprocess
            chw, unused_metadata = preprocess(value)
            value = chw
    array = np.asarray(value, dtype=np.float32)
    if array.shape == (3, 256, 256):
        array = array[np.newaxis, ...]
    if array.shape != (1, 3, 256, 256) or not np.isfinite(array).all():
        raise ValueError("preprocess must return finite FP32 NCHW [1,3,256,256]")
    return np.ascontiguousarray(array, dtype=np.float32)


def load_existing_split_clients(model_root, runner, model_manifest_path,
                                expected_manifest_sha256, threads=1):
    """Verify the frozen v5 split contract before lazily opening ORT clients."""
    try:
        from .cnn_ddr_v5_runtime import load_v5_split_contracts
    except (ImportError, ValueError):
        from cnn_ddr_v5_runtime import load_v5_split_contracts
    try:
        from .partition_s1 import OrtPartitionClient
    except (ImportError, ValueError):
        from partition_s1 import OrtPartitionClient
    manifest_path = os.path.abspath(model_manifest_path)
    expected_path = os.path.abspath(os.path.join(model_root, "manifest.json"))
    if manifest_path != expected_path:
        raise ValueError("model manifest path must match the selected split bundle")
    bundle = load_v5_split_contracts(model_root, expected_manifest_sha256)
    clients = {}
    try:
        for name, record in bundle["models"].items():
            command = [runner, "--stream", record["path"], str(int(threads))]
            client = OrtPartitionClient(
                command, record["contract"], threads=int(threads))
            source_name = record["contract"]["outputs"][0]["name"]
            clients[name] = _LogicalOutputClient(
                client, source_name, _LOGICAL_OUTPUT_NAMES[name])
    except Exception:
        for client in clients.values():
            try:
                client.close()
            except Exception:
                pass
        raise
    return clients, bundle["manifest_sha256"]


def run_fixed_graph(items, expected_frame_ids, backend, clients,
                    capture=None, decode=None, preprocess=None, rank=None,
                    output=None, logical_cores=4, queue_capacity=4,
                    max_in_flight=4, ps_workers=4, run_timeout_s=300.0,
                    cleanup_timeout_s=5.0):
    """Run the established capture-to-suffix adapter with an injected backend."""
    try:
        from .cnn_pipeline_v7_adapter import CnnPipelineV7Adapter
    except (ImportError, ValueError):
        from cnn_pipeline_v7_adapter import CnnPipelineV7Adapter
    adapter = CnnPipelineV7Adapter(
        backend, clients, capture=capture, decode=decode,
        preprocess=preprocess or mobileclip_preprocess,
        rank=rank or (lambda raw: int(np.argmax(raw))), output=output,
        logical_cores=logical_cores, queue_capacity=queue_capacity,
        max_in_flight=max_in_flight, ps_workers=ps_workers,
        run_timeout_s=run_timeout_s, cleanup_timeout_s=cleanup_timeout_s)
    started = time.perf_counter()
    batch = None
    primary_error = None
    cleanup_receipt = None
    try:
        batch = adapter.run(items, expected_frame_ids)
    except Exception as error:
        primary_error = error
    finally:
        if not adapter.closed:
            if adapter.pipeline.requires_recovery or adapter.pipeline.threads_alive:
                try:
                    adapter.recover(cleanup_timeout_s)
                except Exception as recovery_error:
                    if primary_error is None:
                        primary_error = recovery_error
            try:
                cleanup_receipt = adapter.close()
            except Exception as close_error:
                if primary_error is None:
                    primary_error = close_error
                cleanup_receipt = dict(adapter._close_receipt or {})
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if primary_error is not None:
        raise primary_error
    return {
        "status": "CNN_PIPELINE_V7_FIXED_GRAPH_COMPLETED",
        "board_operation_performed": bool(
            getattr(backend, "board_operation_performed", False)),
        "frame_count": batch["frame_count"],
        "batch_wall_ms": batch["batch_wall_ms"],
        "runner_wall_ms": elapsed_ms,
        "batch": batch,
        "cleanup": cleanup_receipt,
    }


def _json_safe_report(result, output_dir):
    frames = []
    for record in result["batch"]["frames"]:
        raw = np.asarray(record["raw512"], dtype="<f4").reshape(512)
        filename = "features-frame-%s-raw512.f32" % str(record["frame_id"])
        path = os.path.join(output_dir, filename)
        with open(path, "wb") as stream:
            stream.write(raw.tobytes(order="C"))
        frames.append({
            "frame_id": record["frame_id"], "raw512_path": filename,
            "raw512_sha256": hashlib.sha256(raw.tobytes(order="C")).hexdigest(),
            "wall_ms": record["wall_ms"],
            "components_ms": record["components_ms"],
            "stage_events": record["stage_events"],
            "normal_stage_events": record["normal_stage_events"],
            "stage_order": record["stage_order"],
        })
    return {"status": result["status"],
            "board_operation_performed": result["board_operation_performed"],
            "frame_count": result["frame_count"],
            "batch_wall_ms": result["batch_wall_ms"],
            "runner_wall_ms": result["runner_wall_ms"],
            "frames": frames, "cleanup": result["cleanup"],
            "scope": result["batch"]["scope"]}


def main(argv=None):
    process_started = time.perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--runtime-bundle-root", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--expected-model-manifest-sha256", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--transport", choices=("single", "multicore"),
                        default="single")
    parser.add_argument("--device", default="/dev/network7_v7")
    parser.add_argument("--input-image", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if os.path.exists(args.output_dir):
        raise RuntimeError("output directory already exists: %s" % args.output_dir)
    os.makedirs(args.output_dir)
    clients = None
    transport = None
    backend = None
    result = None
    error = None
    cleanup_error = None
    try:
        clients, split_sha = load_existing_split_clients(
            args.models, args.runner, args.model_manifest,
            args.expected_model_manifest_sha256, threads=1)
        transport = create_linux_transport(
            args.device, multicore=(args.transport == "multicore"))
        backend = CnnPipelineV7NormalStageBackend(
            transport, args.bundle_root, args.runtime_bundle_root)
        items = [(index, path) for index, path in enumerate(args.input_image)]
        result = run_fixed_graph(items, [item[0] for item in items],
                                 backend, clients)
        receipt = _json_safe_report(result, args.output_dir)
        receipt["process_wall_ms"] = (
            time.perf_counter() - process_started) * 1000.0
        receipt["timing_scope"] = {
            "process_wall_ms":
                "includes split-client and transport/backend initialization, DAG run, and cleanup",
            "runner_wall_ms":
                "includes bounded DAG run and cleanup after clients/backend are initialized",
            "batch_wall_ms":
                "bounded DAG admission through ordered output; includes short-batch fill and drain",
            "steady_state_claim": False,
        }
        receipt["split_model_manifest_sha256"] = split_sha
        receipt["transport"] = args.transport
        receipt["device"] = args.device
        with open(os.path.join(args.output_dir, "result.json"), "w") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except Exception as exception:
        error = exception
        raise
    finally:
        if backend is not None and not getattr(backend, "_closed", False):
            try:
                backend.close()
            except Exception as exception:
                cleanup_error = "%s: %s" % (type(exception).__name__, exception)
        elif transport is not None and backend is None:
            close = getattr(transport, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exception:
                    cleanup_error = "%s: %s" % (type(exception).__name__, exception)
        if error is not None:
            receipt = {"status": "CNN_PIPELINE_V7_FIXED_GRAPH_INCOMPLETE",
                       "board_operation_performed": bool(
                           backend is not None and
                           getattr(backend, "board_operation_performed", False)),
                       "error": "%s: %s" % (type(error).__name__, error),
                       "cleanup": (dict(backend._close_receipt)
                                   if backend is not None and
                                   isinstance(getattr(backend, "_close_receipt", None), dict)
                                   else None),
                       "cleanup_error": cleanup_error}
            receipt["process_wall_ms"] = (
                time.perf_counter() - process_started) * 1000.0
            with open(os.path.join(args.output_dir, "incomplete.json"), "w") as stream:
                json.dump(receipt, stream, indent=2, sort_keys=True)
                stream.write("\n")


if __name__ == "__main__":
    main()
