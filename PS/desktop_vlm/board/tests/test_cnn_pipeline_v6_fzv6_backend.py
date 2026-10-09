"""Offline contracts for the FZV6 full-fused DAG backend."""

import hashlib
import unittest

import numpy as np

from desktop_vlm.board.cnn_pipeline_v6_fzv6_backend import (
    DAG_ORDER, LOGICAL_TO_PHYSICAL, PROFILE_SPECS, Fzv6FullFusedBackend,
    Fzv6NormalFallbackBackend,
)
from desktop_vlm.board.cnn_pipeline_v6 import (
    FrameActivationLease as SchedulerFrameActivationLease, FrameTag,
    V6DagPipeline, V6ExecutionPlan, V6StageCallbacks,
)


MANIFEST_SHA256 = "a" * 64


def parameter_contract():
    profiles = {}
    for profile, spec in PROFILE_SPECS.items():
        payload = bytes(spec.parameter_bytes)
        profiles[profile] = {
            "params": payload,
            "params_sha256": hashlib.sha256(payload).hexdigest(),
            "input_scale": 0.125 + profile * 0.03125,
            "output_scale": 0.25 + profile * 0.03125,
        }
    return {"manifest_sha256": MANIFEST_SHA256, "profiles": profiles}


class FakeTransport(object):
    def __init__(self, identity=None, array_transfers=True):
        self.identity = identity or {
            "core_id": 0x465A5636,
            "core_abi": 0x00060000,
            "guard_caps": 0x1ff,
            "abi_version": 6,
            "profile_count": 7,
        }
        self.array_transfers = array_transfers
        self.next_handle = 1
        self.allocations = {}
        self.uploads = []
        self.downloads = []
        self.submits = []
        self.completions = []
        self.events = []
        self.quiesced = False
        self.generation = 17
        if not array_transfers:
            self.upload_array = None
            self.download_into = None

    def alloc(self, size_bytes, alignment=16, flags=0):
        handle = self.next_handle
        self.next_handle += 1
        self.allocations[handle] = size_bytes
        self.events.append(("alloc", handle, size_bytes))
        return handle

    def upload_array(self, handle, offset, value):
        if not self.array_transfers:
            raise AssertionError("array upload should not be called in fallback mode")
        self.uploads.append((handle, offset, value.shape, value.dtype,
                             hashlib.sha256(value.tobytes()).hexdigest()))
        self.events.append(("upload_array", handle, offset))

    def upload(self, handle, offset, payload):
        self.uploads.append((handle, offset, len(payload),
                             hashlib.sha256(payload).hexdigest()))
        self.events.append(("upload", handle, offset))

    def submit(self, profile, block_count, params_handle, activation_handle,
               activation_base_offset_bytes, input_offset_bytes):
        record = (profile, block_count, params_handle, activation_handle,
                  activation_base_offset_bytes, input_offset_bytes)
        self.submits.append(record)
        self.events.append(("submit",) + record)

    def wait_complete(self, profile, timeout_s):
        completion = {"profile": profile, "completion_index": len(self.completions),
                      "reset_generation": self.generation}
        self.completions.append(completion)
        self.events.append(("complete", profile))
        return completion

    def get_status(self):
        return {"reset_generation": self.generation}

    def download_into(self, handle, offset, output):
        if not self.array_transfers:
            raise AssertionError("download_into should not be called in fallback mode")
        profile = 5 if offset == 524288 else 1
        self.downloads.append((handle, offset, output.shape, output.dtype))
        output.fill(profile + 1)
        self.events.append(("download_into", handle, offset))

    def download(self, handle, offset, size_bytes):
        self.downloads.append((handle, offset, size_bytes))
        self.events.append(("download", handle, offset))
        return np.full(size_bytes // 2, 6 if offset == 524288 else 2,
                       dtype="<i2").tobytes()

    def quiesce(self):
        self.events.append(("quiesce",))
        self.quiesced = True

    def free(self, handle):
        if not self.quiesced:
            raise AssertionError("FREE must follow QUIESCE")
        self.events.append(("free", handle))
        del self.allocations[handle]


class Fzv6FullFusedBackendTests(unittest.TestCase):
    def _backend(self, transport=None, contract=None, expected_sha=MANIFEST_SHA256):
        transport = transport or FakeTransport()
        backend = Fzv6FullFusedBackend(
            transport, parameter_contract() if contract is None else contract,
            expected_manifest_sha256=expected_sha)
        return backend, transport

    def test_identity_and_logical_profile_mapping_match_frozen_fzv6_contract(self):
        self.assertEqual(LOGICAL_TO_PHYSICAL, {
            "n0": 2, "n1_dw": 3, "n1_pw": 4, "n2": 0,
            "n3_dw": 5, "n3_pw": 6, "n4": 1,
        })
        self.assertEqual(DAG_ORDER, ("n0", "n1_dw", "n1_pw", "n2",
                                     "n3_dw", "n3_pw", "n4"))
        backend, _ = self._backend()
        backend.close()

    def test_rejects_incompatible_fzv6_identity_before_allocating(self):
        for field, value in (("core_id", 0x465A5635),
                             ("core_abi", 0x00050000),
                             ("guard_caps", 0x1fe),
                             ("abi_version", 5),
                             ("profile_count", 3)):
            transport = FakeTransport()
            transport.identity[field] = value
            with self.assertRaises(ValueError):
                Fzv6FullFusedBackend(transport, parameter_contract(),
                                     expected_manifest_sha256=MANIFEST_SHA256)
            self.assertEqual(transport.allocations, {})

    def test_requires_sha_pinned_complete_params_and_explicit_scales_before_alloc(self):
        broken = parameter_contract()
        broken["profiles"][4]["input_scale"] = None
        transport = FakeTransport()
        with self.assertRaises(ValueError):
            Fzv6FullFusedBackend(transport, broken,
                                 expected_manifest_sha256=MANIFEST_SHA256)
        self.assertEqual(transport.allocations, {})

        broken = parameter_contract()
        broken["profiles"][3]["params"] = b"bad"
        transport = FakeTransport()
        with self.assertRaises(ValueError):
            Fzv6FullFusedBackend(transport, broken,
                                 expected_manifest_sha256=MANIFEST_SHA256)
        self.assertEqual(transport.allocations, {})

    def test_uploads_seven_pinned_parameter_blobs_once_and_shares_handles(self):
        backend, transport = self._backend()
        self.assertEqual(len(backend.parameter_handles), 7)
        self.assertEqual(len(transport.uploads), 7)
        for profile, handle in backend.parameter_handles.items():
            self.assertEqual(transport.allocations[handle],
                             PROFILE_SPECS[profile].parameter_bytes)
        lease = backend.create_frame_lease(11)
        self.assertEqual(transport.allocations[lease.activation_handle], 1 << 20)
        self.assertEqual(len(transport.uploads), 7)
        lease.close()
        backend.close()

    def test_released_frame_activation_handle_is_reused_by_the_next_lease(self):
        backend, transport = self._backend()
        first = backend.create_frame_lease(13)
        first_handle = first.activation_handle
        first.close()
        second = backend.create_frame_lease(14)
        self.assertEqual(second.activation_handle, first_handle)
        self.assertEqual(len([event for event in transport.events
                              if event[0] == "alloc"]), 8)
        second.close()
        backend.close()

    def test_prepare_only_uploads_n0_and_n3_pw_to_base_zero(self):
        backend, transport = self._backend()
        lease = backend.create_frame_lease(23)
        for stage in ("n0", "n3_pw"):
            profile = LOGICAL_TO_PHYSICAL[stage]
            spec = PROFILE_SPECS[profile]
            values = np.full((1, spec.channels, spec.width, spec.width),
                             profile + 1.0, dtype=np.float32)
            lease.prepare(stage, values)
        uploads = [item for item in transport.uploads if item[0] == lease.activation_handle]
        self.assertEqual([item[1] for item in uploads], [0, 0])
        self.assertEqual([item[2] for item in uploads], [
            (64, 64, 64), (16, 256, 16)])
        with self.assertRaises(ValueError):
            lease.prepare("n1_dw", np.zeros((1, 64, 64, 64), dtype=np.float32))
        lease.close()
        backend.close()

    def test_execute_chained_uses_frozen_offsets_and_retains_all_completions(self):
        backend, transport = self._backend()
        lease = backend.create_frame_lease(31)
        lease.prepare("n0", np.zeros((1, 64, 64, 64), dtype=np.float32))
        lease.prepare("n3_pw", np.zeros((1, 256, 16, 16), dtype=np.float32))
        completions = lease.execute_chained()
        expected_profiles = [2, 3, 4, 0, 5, 6, 1]
        self.assertEqual([call[0] for call in transport.submits], expected_profiles)
        self.assertEqual([call[1] for call in transport.submits], [4, 1, 1, 12, 1, 1, 20])
        self.assertEqual([(call[4], call[5]) for call in transport.submits], [
            (0, 0), (0, 0), (0, 32768 * 16), (16384 * 16, 0),
            (16384 * 16, 0), (0, 0), (8192 * 16, 0)])
        self.assertEqual(len(completions), 7)
        self.assertEqual([entry["profile"] for entry in completions], expected_profiles)
        self.assertEqual(len(lease.completions), 7)
        lease.close()
        backend.close()

    def test_expected_profile_switch_resets_keep_one_scheduler_generation(self):
        class ModeSwitchTransport(FakeTransport):
            def __init__(self):
                FakeTransport.__init__(self)
                self.token = self.generation
                self.last_profile = None

            def current_generation_token(self):
                return self.token

            def wait_complete(self, profile, timeout_s):
                switched = self.last_profile is not None and self.last_profile != profile
                if switched:
                    self.generation = (self.generation + 1) & 0xffffffff
                self.last_profile = profile
                completion = FakeTransport.wait_complete(self, profile, timeout_s)
                completion["mode_switch_reset"] = switched
                completion["reset_generation_before"] = (
                    self.generation - (1 if switched else 0)) & 0xffffffff
                completion["generation_token"] = self.token
                return completion

        transport = ModeSwitchTransport()
        contract = parameter_contract()
        backend = Fzv6FullFusedBackend(
            transport, contract, expected_manifest_sha256=MANIFEST_SHA256)
        lease = backend.acquire_frame(FrameTag(17, 32, 0))
        prepared = backend.prepare(
            "n0", lease, np.zeros((1, 64, 64, 64), dtype=np.float32))
        executed = backend.execute("n0", lease, prepared)
        for stage in ("n1_dw", "n1_pw", "n2", "n3_dw"):
            executed = backend.execute_chained(stage, lease, executed)
        prepared = backend.prepare(
            "n3_pw", lease, np.zeros((1, 256, 16, 16), dtype=np.float32))
        executed = backend.execute("n3_pw", lease, prepared)
        executed = backend.execute_chained("n4", lease, executed)
        completions = executed["completions"]
        self.assertEqual([item["reset_generation"] for item in completions],
                         [17] * 7)
        self.assertEqual([item["hardware_reset_generation"] for item in completions],
                         [17, 18, 19, 20, 21, 22, 23])
        self.assertFalse(completions[0]["mode_switch_reset"])
        self.assertTrue(all(item["mode_switch_reset"] for item in completions[1:]))
        self.assertEqual(backend.current_generation(), 17)
        backend.release_frame(lease)
        backend.close()

    def test_chain_can_pause_for_n3_pw_prepare_after_finishing_n3_dw(self):
        backend, transport = self._backend()
        lease = backend.create_frame_lease(33)
        lease.prepare("n0", np.zeros((1, 64, 64, 64), dtype=np.float32))
        first = lease.execute_chained()
        self.assertEqual([entry["profile"] for entry in first], [2, 3, 4, 0, 5])
        lease.finish("n3_dw")
        lease.prepare("n3_pw", np.zeros((1, 256, 16, 16), dtype=np.float32))
        second = lease.execute_chained()
        self.assertEqual([entry["profile"] for entry in second], [2, 3, 4, 0, 5, 6, 1])
        self.assertEqual([call[0] for call in transport.submits], [2, 3, 4, 0, 5, 6, 1])
        lease.finish("n4")
        lease.close()
        backend.close()

    def test_finish_only_downloads_p5_and_p1_absolute_spans_and_dequantizes(self):
        backend, transport = self._backend()
        lease = backend.create_frame_lease(37)
        lease.prepare("n0", np.zeros((1, 64, 64, 64), dtype=np.float32))
        lease.prepare("n3_pw", np.zeros((1, 256, 16, 16), dtype=np.float32))
        lease.execute_chained()
        n3_output = lease.finish("n3_dw")
        n4_output = lease.finish("n4")
        self.assertEqual([(item[1], item[2]) for item in transport.downloads], [
            (524288, (16, 256, 16)), (131072, (16, 256, 16))])
        self.assertEqual(n3_output.shape, (1, 256, 16, 16))
        self.assertEqual(n4_output.shape, (1, 256, 16, 16))
        self.assertTrue(np.all(n3_output == np.float32(6 *
            backend.contract["profiles"][5]["output_scale"])))
        self.assertTrue(np.all(n4_output == np.float32(2 *
            backend.contract["profiles"][1]["output_scale"])))
        with self.assertRaises(ValueError):
            lease.finish("n2")
        lease.close()
        backend.close()

    def test_fallback_transport_copies_only_when_array_methods_are_absent(self):
        backend, transport = self._backend(FakeTransport(array_transfers=False))
        lease = backend.create_frame_lease(41)
        lease.prepare("n0", np.zeros((1, 64, 64, 64), dtype=np.float32))
        lease.prepare("n3_pw", np.zeros((1, 256, 16, 16), dtype=np.float32))
        lease.execute_chained()
        lease.finish("n3_dw")
        lease.finish("n4")
        activation_uploads = [record for record in transport.uploads
                              if record[0] == lease.activation_handle]
        self.assertEqual([record[1] for record in activation_uploads], [0, 0])
        self.assertEqual([record[1] for record in transport.downloads], [524288, 131072])
        lease.close()
        backend.close()

    def test_close_rejects_active_leases_then_quiesces_before_free(self):
        backend, transport = self._backend()
        lease = backend.create_frame_lease(47)
        before = list(transport.events)
        with self.assertRaises(RuntimeError):
            backend.close()
        self.assertEqual(transport.events, before)
        lease.close()
        backend.close()
        names = [event[0] for event in transport.events]
        self.assertLess(names.index("quiesce"), names.index("free"))
        self.assertEqual(len([event for event in transport.events if event[0] == "free"]), 8)

    def test_real_v6_dag_pipeline_accepts_backend_and_collects_seven_completions(self):
        backend, transport = self._backend()
        spec = PROFILE_SPECS[2]
        callbacks = V6StageCallbacks(
            stem_prefix=lambda unused: np.zeros(
                (1, spec.channels, spec.width, spec.width), dtype=np.float32),
            network1_bridge=lambda value: value,
            network3_bridge=lambda value: value,
            network3_se_gelu=lambda unused: np.zeros(
                (1, 256, 16, 16), dtype=np.float32),
            suffix=lambda unused: np.zeros((1, 512), dtype=np.float32))
        pipeline = V6DagPipeline(
            backend, callbacks,
            execution_plan=V6ExecutionPlan(
                {"n1": "pl_fused", "n3": "hybrid_fused"}),
            queue_capacity=2, max_in_flight=1, ps_workers=1)
        results = pipeline.run([(1, object())], [1])
        self.assertEqual(len(results), 1)
        self.assertEqual([item["profile"] for item in results[0].completions],
                         [2, 3, 4, 0, 5, 6, 1])
        self.assertTrue(all(item["reset_generation"] == 17
                            for item in results[0].completions))
        self.assertEqual(len(transport.submits), 7)
        self.assertEqual(len(set(call[3] for call in transport.submits)), 1)
        self.assertEqual(len(set(call[2] for call in transport.submits)), 7)
        self.assertEqual(backend.current_generation(), 17)
        backend.close()

    def test_scheduler_acquire_returns_scheduler_lease_with_full_activation_alias(self):
        from desktop_vlm.board.cnn_pipeline_v6 import FrameTag

        backend, _ = self._backend()
        tag = FrameTag(17, 5, 0)
        lease = backend.acquire_frame(tag)
        self.assertIsInstance(lease, SchedulerFrameActivationLease)
        self.assertIs(lease.tag, tag)
        self.assertEqual(set(lease.activation_handles), set(DAG_ORDER))
        self.assertEqual(len(set(lease.activation_handles.values())), 1)
        self.assertEqual(set(lease.parameter_handles), set(DAG_ORDER))
        self.assertEqual(lease.native_lease.activation_handle,
                         lease.activation_handles["n0"])
        backend.release_frame(lease)
        backend.close()

    def test_real_v6_dag_default_plan_uses_abi6_ps_transition_fallback(self):
        backend, transport = self._backend_class(Fzv6NormalFallbackBackend)
        callbacks = V6StageCallbacks(
            stem_prefix=lambda unused: np.zeros(
                (1, 64, 64, 64), dtype=np.float32),
            network1_bridge=lambda unused: np.zeros(
                (1, 128, 32, 32), dtype=np.float32),
            network3_bridge=lambda unused: np.zeros(
                (1, 256, 16, 16), dtype=np.float32),
            suffix=lambda unused: np.zeros((1, 512), dtype=np.float32))
        pipeline = V6DagPipeline(
            backend, callbacks, queue_capacity=2, max_in_flight=1, ps_workers=1)
        results = pipeline.run([(2, object())], [2])
        self.assertEqual([item["profile"] for item in results[0].completions],
                         [2, 0, 1])
        self.assertTrue(all(item["reset_generation"] == 17
                            for item in results[0].completions))
        self.assertEqual([call[0] for call in transport.submits], [2, 0, 1])
        self.assertEqual([(call[4], call[5]) for call in transport.submits],
                         [(0, 0), (0, 0), (0, 0)])
        self.assertEqual(len(set(call[3] for call in transport.submits)), 3)
        self.assertEqual(len(set(call[2] for call in transport.submits)), 3)
        self.assertEqual(len(backend.parameter_handles), 3)
        self.assertEqual(backend.identity["core_id"], 0x465A5636)
        self.assertEqual(backend.identity["core_abi"], 0x00060000)
        self.assertEqual(backend.identity["abi_version"], 6)
        self.assertEqual(backend.identity["profile_count"], 7)
        self.assertEqual(backend.identity["guard_caps"], 0x1ff)
        self.assertEqual(backend.current_generation(), 17)
        activation_sizes = sorted(event[2] for event in transport.events
                                  if event[0] == "alloc" and
                                  event[2] in (1 << 20, 1 << 19, 1 << 18))
        self.assertEqual(activation_sizes, [1 << 18, 1 << 19, 1 << 20])
        # FakeTransport.submit has the frozen six-argument ABI6 signature;
        # successful calls above prove the fallback never routes via ABI5.
        parameter_uploads = [event for event in transport.events
                             if event[0] == "upload_array" and
                             event[1] in backend.parameter_handles.values()]
        self.assertEqual(len(parameter_uploads), 3)
        backend.close()

    def test_normal_fallback_lease_pool_keeps_three_handles_distinct_and_quiesces(self):
        from desktop_vlm.board.cnn_pipeline_v6 import FrameTag

        backend, transport = self._backend_class(Fzv6NormalFallbackBackend)
        first = backend.acquire_frame(FrameTag(17, 11, 0))
        first_handles = dict(first.activation_handles)
        self.assertEqual(set(first_handles), {"n0", "n2", "n4"})
        self.assertEqual(len(set(first_handles.values())), 3)
        events_before_close = list(transport.events)
        with self.assertRaises(RuntimeError):
            backend.close()
        self.assertEqual(transport.events, events_before_close)
        backend.release_frame(first)

        second = backend.acquire_frame(FrameTag(17, 12, 1))
        self.assertEqual(second.activation_handles, first_handles)
        self.assertEqual(len(set(second.activation_handles.values())), 3)
        backend.release_frame(second)
        backend.close()
        event_names = [event[0] for event in transport.events]
        self.assertLess(event_names.index("quiesce"), event_names.index("free"))
        self.assertEqual(transport.allocations, {})

    def _backend_class(self, backend_type):
        transport = FakeTransport()
        backend = backend_type(
            transport, parameter_contract(),
            expected_manifest_sha256=MANIFEST_SHA256)
        return backend, transport


if __name__ == "__main__":
    unittest.main()
