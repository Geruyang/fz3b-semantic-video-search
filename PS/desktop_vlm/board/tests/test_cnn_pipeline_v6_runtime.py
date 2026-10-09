"""Integration tests for v6 ORT callbacks and external pipeline adapters."""

import unittest

import numpy as np

from desktop_vlm.board.cnn_pipeline_v6 import (
    CpuThreadBudget,
    FrameActivationLease,
    V6ExecutionPlan,
)
from desktop_vlm.board.cnn_pipeline_v6_runtime import CnnPipelineV6Runtime


class FakeClient(object):
    def __init__(self, output_name, output_shape, threads):
        self.output_name = output_name
        self.output_shape = output_shape
        self.header = {"threads": threads}
        self.inputs = []
        self.closed = False

    def infer(self, tensors):
        self.inputs.append(tuple(np.asarray(tensors[0]).shape))
        return ({self.output_name: np.zeros(self.output_shape, dtype=np.float32)}, 0.25)

    def close(self):
        self.closed = True


class TensorBackend(object):
    def __init__(self):
        self.generation = 5
        self.next_handle = 0
        self.active = {}
        self.closed = False

    def current_generation(self):
        return self.generation

    def acquire_frame(self, tag):
        self.next_handle += 1
        lease = FrameActivationLease(
            tag,
            {name: "%s-%d" % (name, self.next_handle)
             for name in ("n0", "n2", "n4")},
            {name: "shared-" + name for name in ("n0", "n2", "n4")})
        self.active[id(lease)] = lease
        return lease

    def prepare(self, profile, lease, value):
        return value

    def execute(self, profile, lease, value):
        return {"value": value, "generation": self.generation,
                "profile": profile}

    def finish(self, profile, lease, executed):
        return {"activation": executed["value"],
                "completion": {"profile": profile,
                               "reset_generation": self.generation},
                "timing_ms": {}}

    def release_frame(self, lease):
        del self.active[id(lease)]

    def close(self):
        self.closed = True
        return {"quiesce_confirmed": True, "all_handles_freed": True,
                "transport_closed": True}


def clients(threads=None):
    threads = threads or {"stem_prefix": 1, "network1_bridge": 1,
                          "network3_bridge": 1, "suffix": 1}
    return {
        "stem-prefix": FakeClient("n0_input", (1, 64, 64, 64),
                                  threads["stem_prefix"]),
        "network1-bridge": FakeClient("n2_input", (1, 128, 32, 32),
                                      threads["network1_bridge"]),
        "network3-bridge": FakeClient("n4_input", (1, 256, 16, 16),
                                      threads["network3_bridge"]),
        "suffix": FakeClient("features", (1, 512), threads["suffix"]),
    }


class CnnPipelineV6RuntimeTests(unittest.TestCase):
    def test_runtime_connects_capture_decode_preprocess_ort_rank_and_output(self):
        events = []

        def adapter(name, function):
            def call(value):
                events.append(name)
                return function(value)
            return call

        backend = TensorBackend()
        stage_clients = clients()
        runtime = CnnPipelineV6Runtime(
            backend,
            stage_clients,
            cpu_budget=CpuThreadBudget(
                4, {"stem_prefix": 1, "network1_bridge": 1,
                    "network3_bridge": 1, "suffix": 1}),
            capture=adapter("capture", lambda value: value + b"-captured"),
            decode=adapter("decode", lambda unused: np.zeros((256, 256, 3), dtype=np.uint8)),
            preprocess=adapter(
                "preprocess",
                lambda unused: np.zeros((1, 3, 256, 256), dtype=np.float32)),
            rank=adapter("rank", lambda features: [int(features.size), 7]),
            output=adapter("output", lambda ranking: {"ranking": ranking}),
            queue_capacity=2, max_in_flight=2, ps_workers=4)

        result = runtime.run([(12, b"frame", {"captured_ns": 99})], [12])[0]
        self.assertEqual(result.features.shape, (512,))
        self.assertEqual(result.features.dtype, np.dtype(np.float32))
        self.assertEqual(result.value, {"ranking": [512, 7]})
        self.assertEqual(result.metadata, {"captured_ns": 99})
        self.assertEqual(events, ["capture", "decode", "preprocess", "rank", "output"])
        self.assertEqual(stage_clients["stem-prefix"].inputs, [(1, 3, 256, 256)])
        self.assertEqual(stage_clients["network1-bridge"].inputs, [(1, 64, 64, 64)])
        self.assertEqual(stage_clients["network3-bridge"].inputs, [(1, 128, 32, 32)])
        self.assertEqual(stage_clients["suffix"].inputs, [(1, 256, 16, 16)])

        receipt = runtime.close()
        self.assertTrue(receipt["quiesce_confirmed"])
        self.assertTrue(receipt["all_handles_freed"])
        self.assertTrue(receipt["transport_closed"])
        self.assertTrue(receipt["clients_closed"])
        self.assertTrue(all(client.closed for client in stage_clients.values()))

    def test_runtime_rejects_client_thread_count_outside_four_core_budget(self):
        stage_clients = clients({"stem_prefix": 2, "network1_bridge": 1,
                                 "network3_bridge": 1, "suffix": 1})
        with self.assertRaisesRegex(ValueError, "thread count"):
            CnnPipelineV6Runtime(
                TensorBackend(), stage_clients,
                cpu_budget=CpuThreadBudget(
                    4, {"stem_prefix": 1, "network1_bridge": 1,
                        "network3_bridge": 1, "suffix": 1}))

    def test_hybrid_n3_plan_accepts_shape_checked_ps_se_gelu_callback(self):
        calls = []

        def se_gelu(value):
            calls.append(tuple(value.shape))
            return value

        runtime = CnnPipelineV6Runtime(
            TensorBackend(), clients({"stem_prefix": 1, "network1_bridge": 1,
                                      "network3_bridge": 1, "suffix": 2}),
            cpu_budget=CpuThreadBudget(
                4, {"stem_prefix": 1, "network3_se_gelu": 1,
                    "suffix": 2},
                active_stage_keys=("stem_prefix", "network3_se_gelu",
                                   "suffix")),
            execution_plan=V6ExecutionPlan(
                {"n1": "pl_fused", "n3": "hybrid_fused"}),
            network3_se_gelu=se_gelu, network3_se_gelu_threads=1)
        value = np.zeros((1, 256, 16, 16), dtype=np.float32)
        result = runtime.pipeline.callbacks.call("network3_se_gelu", value)
        self.assertEqual(result.shape, (1, 256, 16, 16))
        self.assertEqual(calls, [(1, 256, 16, 16)])

    def test_full_fused_budget_counts_only_stem_se_and_suffix_clients(self):
        stage_clients = clients({"stem_prefix": 1, "network1_bridge": 4,
                                 "network3_bridge": 4, "suffix": 2})
        budget = CpuThreadBudget(
            4, {"stem_prefix": 1, "network3_se_gelu": 1, "suffix": 2},
            active_stage_keys=("stem_prefix", "network3_se_gelu", "suffix"))
        runtime = CnnPipelineV6Runtime(
            TensorBackend(), stage_clients, cpu_budget=budget,
            execution_plan=V6ExecutionPlan(
                {"n1": "pl_fused", "n3": "hybrid_fused"}),
            network3_se_gelu=lambda value: value,
            network3_se_gelu_threads=1)
        self.assertEqual(runtime.cpu_budget.budgeted_ort_threads, 4)

    def test_runtime_rejects_budget_active_keys_that_do_not_match_plan(self):
        budget = CpuThreadBudget(
            4, {"stem_prefix": 1, "network3_se_gelu": 1, "suffix": 2},
            active_stage_keys=("stem_prefix", "network3_se_gelu", "suffix"))
        with self.assertRaisesRegex(ValueError, "active ORT stages"):
            CnnPipelineV6Runtime(
                TensorBackend(), clients(), cpu_budget=budget,
                execution_plan=V6ExecutionPlan(),
                network3_se_gelu=lambda value: value,
                network3_se_gelu_threads=1)

    def test_exclusive_serial4_validates_active_se_client_threads(self):
        stage_clients = clients({"stem_prefix": 4, "network1_bridge": 4,
                                 "network3_bridge": 4, "suffix": 4})
        budget = CpuThreadBudget(
            4, {"stem_prefix": 4, "network3_se_gelu": 4, "suffix": 4},
            active_stage_keys=("stem_prefix", "network3_se_gelu", "suffix"),
            exclusive_ort=True)
        with self.assertRaisesRegex(ValueError, "SE/GELU.*thread count"):
            CnnPipelineV6Runtime(
                TensorBackend(), stage_clients, cpu_budget=budget,
                execution_plan=V6ExecutionPlan(
                    {"n1": "pl_fused", "n3": "hybrid_fused"}),
                network3_se_gelu=lambda value: value,
                network3_se_gelu_threads=1,
                max_in_flight=1, ps_workers=1)

    def test_close_refuses_to_free_backend_before_pipeline_recovery(self):
        backend = TensorBackend()
        runtime = CnnPipelineV6Runtime(
            backend, clients(),
            cpu_budget=CpuThreadBudget(
                4, {"stem_prefix": 1, "network1_bridge": 1,
                    "network3_bridge": 1, "suffix": 1}))
        runtime.pipeline._orphaned_contexts.append(object())
        with self.assertRaisesRegex(RuntimeError, "recover"):
            runtime.close()
        self.assertFalse(backend.closed)


if __name__ == "__main__":
    unittest.main()
