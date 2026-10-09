"""Behavior tests for the bounded v6 cross-frame DAG scheduler."""

import threading
import time
import unittest

from desktop_vlm.board.cnn_pipeline_v6 import (
    CpuThreadBudget,
    FrameActivationLease,
    PipelineStageError,
    V6DagPipeline,
    V6ExecutionPlan,
    V6StageCallbacks,
)


class FakeBackend(object):
    """In-memory boundary double for the external PL/driver service."""

    def __init__(self, hooks=None, fused=False):
        self.generation = 17
        self.hooks = hooks or {}
        self.fused = fused
        self.lock = threading.Lock()
        self.active_pl = 0
        self.max_active_pl = 0
        self.active_leases = set()
        self.peak_leases = 0
        self.released = []
        self.executed = []
        self.prepared_profiles = []
        self.finished_profiles = []
        self.shared_params = {
            name: "param-" + name for name in
            ("n0", "n1_dw", "n1_pw", "n2", "n3_dw", "n3_pw", "n4")
        }

    def current_generation(self):
        return self.generation

    def acquire_frame(self, tag):
        handles = {name: "%s-%s" % (name, tag.frame_id)
                   for name in ("n0", "n1_dw", "n1_pw", "n2",
                                "n3_dw", "n3_pw", "n4")}
        handles["n1_pw"] = handles["n1_dw"]
        handles["n3_pw"] = handles["n3_dw"]
        if self.fused:
            shared = handles["n0"]
            handles = {name: shared for name in handles}
        lease = FrameActivationLease(tag, handles, self.shared_params)
        with self.lock:
            self.active_leases.add(id(lease))
            self.peak_leases = max(self.peak_leases, len(self.active_leases))
        return lease

    def prepare(self, profile, lease, value):
        self.prepared_profiles.append(profile)
        hook = self.hooks.get("prepare:" + profile)
        if hook is not None:
            hook(lease.tag, value)
        return {"profile": profile, "value": value}

    def execute(self, profile, lease, prepared):
        with self.lock:
            self.active_pl += 1
            self.max_active_pl = max(self.max_active_pl, self.active_pl)
            self.executed.append((lease.tag.frame_id, profile))
        try:
            hook = self.hooks.get("execute:" + profile)
            if hook is not None:
                hook(lease.tag, prepared["value"])
            return {"profile": profile, "value": prepared["value"] + 10,
                    "generation": self.generation}
        finally:
            with self.lock:
                self.active_pl -= 1

    def execute_chained(self, profile, lease, previous):
        executed = self.execute(profile, lease, {"value": previous["value"],
                                                 "profile": profile})
        prior = list(previous.get("completions", []))
        prior.append({"profile": previous["profile"],
                      "reset_generation": previous["generation"]})
        executed["completions"] = prior
        return executed

    def finish(self, profile, lease, executed):
        self.finished_profiles.append(profile)
        hook = self.hooks.get("finish:" + profile)
        if hook is not None:
            hook(lease.tag, executed["value"])
        result = {
            "activation": executed["value"],
            "completion": {"profile": profile,
                           "reset_generation": executed["generation"]},
            "timing_ms": {"fake_transfer": 0.0},
        }
        if "completions" in executed:
            result["completions"] = (list(executed["completions"]) +
                                     [result["completion"]])
        return result

    def release_frame(self, lease):
        with self.lock:
            if id(lease) not in self.active_leases:
                raise AssertionError("lease released twice")
            self.active_leases.remove(id(lease))
            self.released.append(lease.tag.frame_id)


def callbacks(**overrides):
    stages = {
        "capture": lambda value: value,
        "decode": lambda value: value,
        "preprocess": lambda value: value,
        "stem_prefix": lambda value: value + 1,
        "network1_bridge": lambda value: value + 2,
        "network3_bridge": lambda value: value + 3,
        "suffix": lambda value: value + 4,
        "rank": lambda value: ("ranked", value),
        "output": lambda value: ("output", value),
    }
    stages.update(overrides)
    return V6StageCallbacks(**stages)


def pipeline(backend, stage_callbacks=None, max_in_flight=3, plan=None, budget=None):
    return V6DagPipeline(
        backend=backend,
        callbacks=stage_callbacks or callbacks(),
        execution_plan=plan,
        queue_capacity=max_in_flight,
        max_in_flight=max_in_flight,
        ps_workers=4,
        cpu_budget=budget or CpuThreadBudget(
            4, {"stem_prefix": 1, "network1_bridge": 1,
                "network3_bridge": 1, "suffix": 1}),
        run_timeout_s=3.0,
        cleanup_timeout_s=1.0)


class V6DagPipelineTests(unittest.TestCase):
    def test_all_ps_steps_and_three_pl_profiles_form_one_frame_dag(self):
        backend = FakeBackend()
        runtime = pipeline(backend)
        result = runtime.run([(9, 0, {"source": "camera-0"})], [9])[0]

        # 0 + stem1 + PL30 + N1 2 + N3 3 + suffix4 = 40.
        self.assertEqual(result.features, 40)
        self.assertEqual(result.value, ("output", ("ranked", 40)))
        self.assertEqual(result.metadata, {"source": "camera-0"})
        self.assertEqual(backend.executed, [(9, "n0"), (9, "n2"), (9, "n4")])
        self.assertEqual([item["profile"] for item in result.completions],
                         ["n0", "n2", "n4"])
        self.assertEqual(set(result.components_ms), {
            "capture", "decode", "preprocess", "stem_prefix",
            "prepare_n0", "pl_n0", "finish_n0", "network1_bridge",
            "prepare_n2", "pl_n2", "finish_n2", "network3_bridge",
            "prepare_n4", "pl_n4", "finish_n4", "suffix", "rank", "output",
            "n0_fake_transfer", "n2_fake_transfer", "n4_fake_transfer"})
        self.assertLessEqual(result.compute_ready_ms, result.output_start_ms)
        self.assertLessEqual(result.output_start_ms, result.output_done_ms)
        self.assertEqual(result.complete_ms, result.output_done_ms)
        self.assertGreaterEqual(result.stage_events["capture"]["start_ms"],
                                result.admitted_ms)
        self.assertLessEqual(result.stage_events["capture"]["queued_ms"],
                             result.stage_events["capture"]["start_ms"])
        self.assertGreater(runtime.last_batch_end, runtime.last_batch_start)

    def test_network1_of_one_frame_runs_while_pl_executes_another_frame(self):
        n1_finished = threading.Event()

        def wait_for_n1(tag, unused_value):
            if tag.frame_id == 1 and not n1_finished.wait(2.0):
                raise AssertionError("frame 0 N1 did not overlap frame 1 PL work")

        backend = FakeBackend({"execute:n0": wait_for_n1})

        def n1(value):
            n1_finished.set()
            return value + 2

        results = pipeline(backend, callbacks(network1_bridge=n1), 2).run(
            [(0, 0), (1, 100)], [0, 1])
        self.assertEqual([result.tag.frame_id for result in results], [0, 1])
        self.assertTrue(n1_finished.is_set())

    def test_one_pl_owner_serializes_every_profile_across_frames(self):
        backend = FakeBackend()
        results = pipeline(backend, max_in_flight=3).run(
            [(0, 0), (1, 10), (2, 20)], [0, 1, 2])
        self.assertEqual(len(results), 3)
        self.assertEqual(backend.max_active_pl, 1)
        self.assertEqual(len(backend.executed), 9)

    def test_each_persistent_ort_stage_has_one_request_owner(self):
        first_entered = threading.Event()
        concurrent_entry = threading.Event()
        call_lock = threading.Lock()
        calls = [0]
        active = [False]

        def stem(value):
            with call_lock:
                calls[0] += 1
                call_index = calls[0]
                if active[0]:
                    concurrent_entry.set()
                active[0] = True
            if call_index == 1:
                first_entered.set()
                concurrent_entry.wait(0.05)
            with call_lock:
                active[0] = False
            return value + 1

        backend = FakeBackend()
        results = pipeline(backend, callbacks(stem_prefix=stem), 2).run(
            [(0, 0), (1, 100)], [0, 1])
        self.assertEqual(len(results), 2)
        self.assertTrue(first_entered.is_set())
        self.assertFalse(concurrent_entry.is_set())

    def test_admission_bound_and_frame_leases_are_unique_but_params_are_shared(self):
        backend = FakeBackend()
        runtime = pipeline(backend, max_in_flight=2)
        results = runtime.run([(frame_id, frame_id) for frame_id in range(6)], range(6))
        self.assertEqual([result.tag.frame_id for result in results], list(range(6)))
        self.assertLessEqual(backend.peak_leases, 2)
        self.assertEqual(sorted(backend.released), list(range(6)))
        self.assertEqual(runtime.stats["in_flight_peak"], 2)

    def test_one_lookahead_frame_reports_wait_before_bounded_admission(self):
        def slow_first(tag, unused_value):
            if tag.frame_id == 0:
                time.sleep(0.03)

        backend = FakeBackend({"execute:n0": slow_first})
        results = pipeline(backend, max_in_flight=1).run(
            [(0, 0), (1, 10)], [0, 1])
        self.assertLess(results[1].arrival_ms, results[1].admitted_ms)
        self.assertGreaterEqual(results[1].admission_wait_ms, 20.0)
        self.assertAlmostEqual(
            results[1].admission_wait_ms,
            results[1].admitted_ms - results[1].arrival_ms,
            places=6)

    def test_results_remain_in_admission_order_when_suffixes_finish_out_of_order(self):
        frame_one_rank = threading.Event()
        emitted = []

        def rank(value):
            feature_value = value
            if feature_value < 100:
                if not frame_one_rank.wait(2.0):
                    raise AssertionError("frame 1 never reached rank")
                time.sleep(0.02)
            else:
                frame_one_rank.set()
            return ("ranked", value)

        def output(value):
            emitted.append(value[1])
            return ("output", value)

        backend = FakeBackend()
        results = pipeline(backend, callbacks(rank=rank, output=output), 2).run(
            [(20, 0), (10, 100)], [20, 10])
        self.assertEqual([result.tag.frame_id for result in results], [20, 10])
        self.assertEqual([result.features for result in results], [40, 140])
        self.assertEqual(emitted, [40, 140])
        self.assertGreater(results[0].ready_to_emit_wait_ms, 0.0)

    def test_stage_failure_stops_admission_drains_pl_and_releases_every_lease(self):
        entered_pl = threading.Event()
        release_pl = threading.Event()

        def pl_hook(tag, unused_value):
            if tag.frame_id == 1:
                entered_pl.set()
                if not release_pl.wait(2.0):
                    raise AssertionError("test did not release in-flight PL")

        backend = FakeBackend({"execute:n0": pl_hook})

        def fail_n1(value):
            self.assertTrue(entered_pl.wait(2.0))
            release_pl.set()
            raise ValueError("bridge failed")

        runtime = pipeline(backend, callbacks(network1_bridge=fail_n1), 2)
        with self.assertRaises(PipelineStageError) as caught:
            runtime.run([(0, 0), (1, 100), (2, 200)], [0, 1, 2])
        self.assertEqual(caught.exception.stage, "network1_bridge")
        self.assertEqual(caught.exception.tag.frame_id, 0)
        self.assertEqual(str(caught.exception.cause), "bridge failed")
        self.assertEqual(backend.active_leases, set())
        self.assertEqual(sorted(backend.released), [0, 1])
        self.assertEqual(runtime.threads_alive, ())

    def test_generation_change_rejects_stale_completion_and_reclaims_lease(self):
        backend = FakeBackend()

        def change_generation(unused_tag, unused_value):
            backend.generation += 1

        backend.hooks["execute:n0"] = change_generation
        runtime = pipeline(backend, max_in_flight=1)
        with self.assertRaises(PipelineStageError) as caught:
            runtime.run([(7, 0)], [7])
        self.assertEqual(caught.exception.stage, "pl_n0")
        self.assertIn("generation changed", str(caught.exception.cause))
        self.assertEqual(backend.released, [7])

    def test_cleanup_timeout_retains_live_lease_until_explicit_safe_recovery(self):
        release_pl = threading.Event()

        def blocked_pl(unused_tag, unused_value):
            release_pl.wait(2.0)

        backend = FakeBackend({"execute:n0": blocked_pl})
        runtime = V6DagPipeline(
            backend, callbacks(), queue_capacity=1, max_in_flight=1,
            ps_workers=4,
            cpu_budget=CpuThreadBudget(
                4, {"stem_prefix": 1, "network1_bridge": 1,
                    "network3_bridge": 1, "suffix": 1}),
            run_timeout_s=0.05, cleanup_timeout_s=0.05)
        with self.assertRaises(PipelineStageError) as caught:
            runtime.run([(4, 0)], [4])
        self.assertEqual(caught.exception.stage, "run")
        self.assertEqual(backend.released, [])
        self.assertNotEqual(runtime.threads_alive, ())
        self.assertTrue(runtime.requires_recovery)

        release_pl.set()
        receipt = runtime.recover(1.0)
        self.assertEqual(receipt, {"frames_released": 1, "workers_alive": ()})
        self.assertEqual(backend.released, [4])
        self.assertEqual(runtime.threads_alive, ())
        self.assertFalse(runtime.requires_recovery)

    def test_split_bridge_plan_chains_n1_and_keeps_n3_se_on_ps(self):
        backend = FakeBackend()

        def forbidden(unused_value):
            raise AssertionError("PS fallback should not run in the offloaded plan")

        plan = V6ExecutionPlan({"n1": "pl_split", "n3": "hybrid_split"})
        result = pipeline(
            backend,
            callbacks(network1_bridge=forbidden, network3_bridge=forbidden,
                      network3_se_gelu=lambda value: value + 3),
            max_in_flight=1,
            plan=plan).run([(3, 0)], [3])[0]
        self.assertEqual([profile for unused_frame, profile in backend.executed],
                         ["n0", "n1_dw", "n1_pw", "n2",
                          "n3_dw", "n3_pw", "n4"])
        self.assertEqual(backend.prepared_profiles,
                         ["n0", "n1_dw", "n2", "n3_dw", "n3_pw", "n4"])
        self.assertNotIn("n1_dw", backend.finished_profiles)
        self.assertEqual(backend.finished_profiles,
                         ["n0", "n1_pw", "n2", "n3_dw", "n3_pw", "n4"])
        self.assertEqual(len(result.completions), 7)
        self.assertEqual(result.features, 78)

    def test_full_fusion_has_only_one_ps_round_trip_between_p5_and_p6(self):
        backend = FakeBackend(fused=True)
        plan = V6ExecutionPlan({"n1": "pl_fused", "n3": "hybrid_fused"})
        result = pipeline(
            backend,
            callbacks(network1_bridge=lambda unused: self.fail("N1 fallback ran"),
                      network3_bridge=lambda unused: self.fail("N3 fallback ran"),
                      network3_se_gelu=lambda value: value + 3),
            max_in_flight=1, plan=plan).run([(6, 0)], [6])[0]
        self.assertEqual([profile for unused_frame, profile in backend.executed],
                         ["n0", "n1_dw", "n1_pw", "n2",
                          "n3_dw", "n3_pw", "n4"])
        self.assertEqual(backend.prepared_profiles, ["n0", "n3_pw"])
        self.assertEqual(backend.finished_profiles, ["n3_dw", "n4"])
        self.assertEqual(len(result.completions), 7)
        self.assertEqual(result.features, 78)

    def test_cpu_budget_rejects_oversubscription_and_excess_ps_workers(self):
        with self.assertRaisesRegex(ValueError, "ORT thread budget"):
            CpuThreadBudget(
                4, {"stem_prefix": 2, "network1_bridge": 1,
                    "network3_bridge": 1, "suffix": 1})
        with self.assertRaisesRegex(ValueError, "ps_workers"):
            V6DagPipeline(
                FakeBackend(), callbacks(), queue_capacity=2, max_in_flight=2,
                ps_workers=5,
                cpu_budget=CpuThreadBudget(
                    4, {"stem_prefix": 1, "network1_bridge": 1,
                        "network3_bridge": 1, "suffix": 1}))

    def test_cpu_budget_exclusive_ort_uses_max_active_stage_threads(self):
        budget = CpuThreadBudget(
            4, {"stem_prefix": 4, "network1_bridge": 4,
                "network3_bridge": 4, "suffix": 4},
            exclusive_ort=True)
        self.assertTrue(budget.exclusive_ort)
        self.assertEqual(budget.active_stage_keys,
                         ("stem_prefix", "network1_bridge",
                          "network3_bridge", "suffix"))
        self.assertEqual(budget.total_ort_threads, 16)
        self.assertEqual(budget.budgeted_ort_threads, 4)

    def test_active_stage_keys_exclude_inactive_full_fusion_bridges(self):
        budget = CpuThreadBudget(
            4, {"stem_prefix": 1, "network1_bridge": 4,
                "network3_bridge": 4, "network3_se_gelu": 1,
                "suffix": 2},
            active_stage_keys=("stem_prefix", "network3_se_gelu", "suffix"))
        self.assertEqual(budget.active_stage_keys,
                         ("stem_prefix", "network3_se_gelu", "suffix"))
        self.assertEqual(budget.budgeted_ort_threads, 4)
        self.assertEqual(budget.active_ort_threads, 4)

    def test_exclusive_ort_requires_one_frame_and_one_ps_worker(self):
        budget = CpuThreadBudget(
            4, {"stem_prefix": 4, "network1_bridge": 4,
                "network3_bridge": 4, "suffix": 4},
            exclusive_ort=True)
        with self.assertRaisesRegex(ValueError, "exclusive_ort"):
            V6DagPipeline(FakeBackend(), callbacks(), queue_capacity=2,
                          max_in_flight=2, ps_workers=1, cpu_budget=budget)
        with self.assertRaisesRegex(ValueError, "exclusive_ort"):
            V6DagPipeline(FakeBackend(), callbacks(), queue_capacity=1,
                          max_in_flight=1, ps_workers=2, cpu_budget=budget)
        runtime = V6DagPipeline(FakeBackend(), callbacks(), queue_capacity=1,
                                 max_in_flight=1, ps_workers=1,
                                 cpu_budget=budget)
        self.assertEqual(runtime.stats["budgeted_ort_threads"], 4)

    def test_full_fusion_budget_configuration_is_stem_se_suffix(self):
        backend = FakeBackend(fused=True)
        plan = V6ExecutionPlan({"n1": "pl_fused", "n3": "hybrid_fused"})
        budget = CpuThreadBudget(
            4, {"stem_prefix": 1, "network3_se_gelu": 1, "suffix": 2},
            active_stage_keys=("stem_prefix", "network3_se_gelu", "suffix"))
        result = pipeline(
            backend,
            callbacks(network1_bridge=lambda unused: self.fail("N1 fallback ran"),
                      network3_bridge=lambda unused: self.fail("N3 fallback ran"),
                      network3_se_gelu=lambda value: value + 3),
            max_in_flight=1, plan=plan, budget=budget).run([(6, 0)], [6])[0]
        self.assertEqual(result.features, 78)
        self.assertEqual(backend.executed[-1][1], "n4")


if __name__ == "__main__":
    unittest.main()
