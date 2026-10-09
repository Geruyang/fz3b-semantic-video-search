"""Production-facing ORT and source/sink wiring for the v6 DAG scheduler."""

import numpy as np

try:
    from cnn_pipeline_v6 import V6DagPipeline, V6ExecutionPlan, V6StageCallbacks
except ImportError:
    from .cnn_pipeline_v6 import V6DagPipeline, V6ExecutionPlan, V6StageCallbacks


_CLIENT_SPECS = {
    "stem-prefix": {
        "budget": "stem_prefix", "input_shape": (1, 3, 256, 256),
        "output_name": "n0_input", "output_shape": (1, 64, 64, 64)},
    "network1-bridge": {
        "budget": "network1_bridge", "input_shape": (1, 64, 64, 64),
        "output_name": "n2_input", "output_shape": (1, 128, 32, 32)},
    "network3-bridge": {
        "budget": "network3_bridge", "input_shape": (1, 128, 32, 32),
        "output_name": "n4_input", "output_shape": (1, 256, 16, 16)},
    "suffix": {
        "budget": "suffix", "input_shape": (1, 256, 16, 16),
        "output_name": "features", "output_shape": (1, 512)},
}


def _identity(value):
    return value


class CnnPipelineV6Runtime(object):
    """Connect four persistent ORT clients and external adapters to one DAG."""

    def __init__(self, backend, clients, cpu_budget, capture=None, decode=None,
                 preprocess=None, rank=None, output=None, execution_plan=None,
                 queue_capacity=4, max_in_flight=4, ps_workers=4,
                 run_timeout_s=300.0, cleanup_timeout_s=5.0,
                 network3_se_gelu=None, network3_se_gelu_threads=None):
        self.backend = backend
        self.clients = dict(clients)
        self.cpu_budget = cpu_budget
        self.closed = False
        plan = execution_plan or V6ExecutionPlan()
        if set(self.clients) != set(_CLIENT_SPECS):
            raise ValueError("v6 runtime requires all four split ORT clients")
        expected_active = {"stem_prefix", "suffix"}
        if plan.transition_routes["n1"] == "ps":
            expected_active.add("network1_bridge")
        if plan.transition_routes["n3"] == "ps":
            expected_active.add("network3_bridge")
        else:
            expected_active.add("network3_se_gelu")
        if set(cpu_budget.active_stage_keys) != expected_active:
            raise ValueError("CPU budget active ORT stages do not match execution plan")
        for name, spec in _CLIENT_SPECS.items():
            if spec["budget"] not in expected_active:
                continue
            header = getattr(self.clients[name], "header", {})
            if header.get("threads") != cpu_budget.ort_intra_op_threads[spec["budget"]]:
                raise ValueError("%s ORT thread count does not match CPU budget" % name)
        if (plan.transition_routes["n3"] in ("hybrid_split", "hybrid_fused") and
                network3_se_gelu is None):
            raise ValueError("hybrid bridge plan requires network3_se_gelu callback")
        if plan.transition_routes["n3"] in ("hybrid_split", "hybrid_fused"):
            if network3_se_gelu_threads is None:
                network3_se_gelu_threads = getattr(
                    network3_se_gelu, "header", {}).get("threads")
            if (network3_se_gelu_threads !=
                    cpu_budget.ort_intra_op_threads["network3_se_gelu"]):
                raise ValueError(
                    "network3 SE/GELU ORT thread count does not match CPU budget")

        def se_gelu_callback(value):
            source = self._finite_fp32(
                value, (1, 256, 16, 16), "network3 SE/GELU input")
            output_value = network3_se_gelu(source)
            return self._finite_fp32(
                output_value, (1, 256, 16, 16), "network3 SE/GELU output")

        stage_callbacks = V6StageCallbacks(
            capture=capture or _identity,
            decode=decode or _identity,
            preprocess=preprocess or _identity,
            stem_prefix=self._ort_callback("stem-prefix"),
            network1_bridge=self._ort_callback("network1-bridge"),
            network3_bridge=self._ort_callback("network3-bridge"),
            network3_se_gelu=(se_gelu_callback
                              if network3_se_gelu is not None else None),
            suffix=self._suffix_callback,
            rank=rank or _identity,
            output=output or _identity)
        self.pipeline = V6DagPipeline(
            backend=backend, callbacks=stage_callbacks,
            execution_plan=plan,
            queue_capacity=queue_capacity, max_in_flight=max_in_flight,
            ps_workers=ps_workers, cpu_budget=cpu_budget,
            run_timeout_s=run_timeout_s, cleanup_timeout_s=cleanup_timeout_s,
            thread_name="cnn-pipeline-v6-runtime")

    @staticmethod
    def _finite_fp32(value, shape, label):
        array = np.asarray(value, dtype=np.float32)
        if array.shape != shape or not np.isfinite(array).all():
            raise ValueError("%s must be finite FP32 %s" % (label, shape))
        return np.ascontiguousarray(array, dtype=np.float32)

    def _ort_callback(self, name):
        spec = _CLIENT_SPECS[name]
        client = self.clients[name]

        def call(value):
            source = self._finite_fp32(value, spec["input_shape"], name + " input")
            response = client.infer([source])
            if (not isinstance(response, tuple) or len(response) != 2 or
                    not isinstance(response[0], dict)):
                raise ValueError("%s ORT response is malformed" % name)
            outputs, run_ms = response
            if (not isinstance(run_ms, (int, float)) or
                    not np.isfinite(run_ms) or run_ms < 0):
                raise ValueError("%s ORT run time is invalid" % name)
            if spec["output_name"] not in outputs:
                raise ValueError("%s ORT output is missing" % name)
            return self._finite_fp32(
                outputs[spec["output_name"]], spec["output_shape"],
                name + " output")

        return call

    def _suffix_callback(self, value):
        output = self._ort_callback("suffix")(value)
        return output.reshape(512).copy()

    def run(self, items, expected_frame_ids):
        if self.closed:
            raise RuntimeError("v6 runtime is closed")
        return self.pipeline.run(items, expected_frame_ids)

    def recover(self, timeout_s=None):
        return self.pipeline.recover(timeout_s)

    def close(self):
        if self.closed:
            return {"quiesce_confirmed": True, "all_handles_freed": True,
                    "transport_closed": True, "clients_closed": True}
        if self.pipeline.requires_recovery or self.pipeline.threads_alive:
            raise RuntimeError("recover the v6 pipeline before closing runtime resources")
        first_error = None
        backend_receipt = None
        try:
            backend_receipt = self.backend.close()
        except Exception as error:
            first_error = error
        if first_error is None:
            if not isinstance(backend_receipt, dict):
                first_error = RuntimeError("v6 backend returned no cleanup receipt")
            else:
                transport = getattr(self.backend, "transport", None)
                close_device = getattr(transport, "close_device", None)
                if (backend_receipt.get("transport_closed") is not True and
                        callable(close_device)):
                    try:
                        close_device()
                        backend_receipt["transport_closed"] = bool(
                            getattr(transport, "closed", True))
                    except Exception as error:
                        first_error = error
        for client in reversed(list(self.clients.values())):
            try:
                client.close()
            except Exception as error:
                if first_error is None:
                    first_error = error
        self.closed = True
        if first_error is not None:
            raise first_error
        receipt = dict(backend_receipt)
        receipt["clients_closed"] = True
        return receipt


__all__ = ["CnnPipelineV6Runtime"]
