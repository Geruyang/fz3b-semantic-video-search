"""Combined P3 identity and shared-PL-chain tests; transport is mocked."""
import copy
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE.parent
ROOT = BOARD.parents[1]
sys.path[:0] = [str(BOARD), str(HERE)]

from cnn_pipeline_v10_bundle import load_v10_release_bundle
from cnn_pipeline_v10_p3_chain_parameters import (
    build_combined_manifest, load_v10_p3_parameters)
from cnn_pipeline_v10_p3_chain_parameters import CHAIN_CONTRACT
from cnn_pipeline_v10_p3_runtime import V10P3ChainMixin
from cnn_pipeline_v10_mixed_runtime import V10MixedBoundaryMixin
from cnn_pipeline_v10_live_runtime import V10LiveRuntime
from test_cnn_pipeline_v10_paired_runtime import (
    FakeTransport, MANIFEST_SHA, clients, contract, image)


BASE_ROOT = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-release-bundle-003"
BASE_SHA = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
CHAIN_ROOT = ROOT / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-p3-chain-parameters-002"
CHAIN_SHA = "c62b9f49b1118916168a2ca7a4a63c56d51bba66a0921523af35d46495bbab99"


class ChainTransport(FakeTransport):
    def __init__(self):
        super(ChainTransport, self).__init__()
        self.upload_calls = []
        self.download_calls = []
        self.wait_calls = []

    def upload(self, handle, offset, payload):
        raw = bytes(payload)
        self.upload_calls.append((handle, offset, len(raw)))
        return super(ChainTransport, self).upload(handle, offset, raw)

    def submit(self, profile, blocks, params, arena_a, arena_b):
        if profile == 3:
            if blocks != 1 or len(self.allocations[params]) != 11280 * 16:
                raise AssertionError("P3 must submit its distinct exact parameter image")
            self.pending = profile
            record = {"profile": profile, "blocks": blocks, "params": params,
                      "arena_a": arena_a, "arena_b": arena_b}
            self.submits.append(record)
            return record.copy()
        return super(ChainTransport, self).submit(profile, blocks, params,
                                                  arena_a, arena_b)

    def wait_complete(self, profile, timeout_s):
        self.wait_calls.append(profile)
        result = super(ChainTransport, self).wait_complete(profile, timeout_s)
        result["guard_error_flags"] = 0
        return result

    def download_into(self, handle, offset, array):
        self.download_calls.append((handle, offset, np.asarray(array).nbytes))
        return super(ChainTransport, self).download_into(handle, offset, array)


def parameters():
    return load_v10_p3_parameters(CHAIN_ROOT / "manifest.json", CHAIN_SHA,
        load_v10_release_bundle(BASE_ROOT, BASE_SHA)["parameter_contract"])


class P3ChainRuntime(V10P3ChainMixin, V10MixedBoundaryMixin, V10LiveRuntime):
    pass


class P3CombinedRuntimeTests(unittest.TestCase):
    def test_loader_binds_combined_sha_words_old_profiles_and_p3_bytes(self):
        base = load_v10_release_bundle(BASE_ROOT, BASE_SHA)
        result = load_v10_p3_parameters(CHAIN_ROOT / "manifest.json", CHAIN_SHA,
                                        base["parameter_contract"])
        self.assertEqual(result["manifest_sha256"], CHAIN_SHA)
        self.assertEqual(result["chain_manifest_sha256"], CHAIN_SHA)
        self.assertEqual(result["parameter_manifest_words"],
            tuple(int(CHAIN_SHA[i:i+8], 16) for i in range(0, 64, 8)))
        self.assertEqual(result["p3_manifest_sha256"],
            "47cb1bc9c4232fb9dee6a0b46fd29f96859bac253ae7bd6ec1fbdd37c1a5533a")
        self.assertEqual(len(result["params"]), 11280 * 16)
        self.assertEqual(result["contract"]["arena_words"], 69632)
        self.assertEqual(result["contract"]["p3"]["output_words"], 16384)
        self.assertEqual(result["contract"], CHAIN_CONTRACT)
        altered = copy.deepcopy(base["parameter_contract"])
        altered["profiles"][0]["output_scale"] *= 2
        with self.assertRaisesRegex(ValueError, "profile 0"):
            load_v10_p3_parameters(CHAIN_ROOT / "manifest.json", CHAIN_SHA,
                                   altered)
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            load_v10_p3_parameters(CHAIN_ROOT / "manifest.json", "0" * 64,
                                   base["parameter_contract"])
        with tempfile.TemporaryDirectory() as folder:
            p3_path = ROOT / "artifacts/board-debug-20261007/acceleration/host/cnn-v10-n1-p3-full-w16-002/manifest.json"
            build_combined_manifest(BASE_ROOT, BASE_SHA, p3_path,
                "47cb1bc9c4232fb9dee6a0b46fd29f96859bac253ae7bd6ec1fbdd37c1a5533a",
                pathlib.Path(folder) / "generated")
            generated = pathlib.Path(folder) / "generated" / "manifest.json"
            self.assertEqual(hashlib.sha256(generated.read_bytes()).hexdigest(), CHAIN_SHA)

    def test_combined_manifest_must_match_deployment_chain_contract(self):
        base = load_v10_release_bundle(BASE_ROOT, BASE_SHA)
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            record = json.loads((CHAIN_ROOT / "manifest.json").read_text())
            record["chain_contract"]["arena_words"] = 69696
            raw = (json.dumps(record, sort_keys=True, indent=2) + "\n").encode()
            (root / "manifest.json").write_bytes(raw)
            shutil.copyfile(str(CHAIN_ROOT / "p3-params.bin"), str(root / "p3-params.bin"))
            expected = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "contract mismatch"):
                load_v10_p3_parameters(root / "manifest.json", expected,
                                       base["parameter_contract"])

    def test_runtime_runs_profiles_2_3_0_on_shared_arenas_without_ps_n1(self):
        owned = clients()
        transport = ChainTransport()
        original_profile0_arenas = None
        original_profile1_arenas = None
        runtime = P3ChainRuntime(transport, contract(), MANIFEST_SHA, owned,
                                 p3_parameters=parameters())
        try:
            original_profile0_arenas = runtime._unused_original_profile0_arenas
            original_profile1_arenas = runtime.arena_handles[1]
            results = runtime.run(((i, image(i + 1)) for i in range(4)),
                                  max_in_flight=1)
            self.assertEqual([r["frame_id"] for r in results], [0, 1, 2, 3])
            self.assertEqual([x["profile"] for x in transport.submits],
                             [2, 3, 0, 1, 2, 3, 0, 1])
            self.assertEqual(transport.wait_calls, [2, 3, 0, 1, 2, 3, 0, 1])
            self.assertEqual(owned["network1-bridge"].calls, 0)
            self.assertEqual(runtime._pipeline_stages, V10P3ChainMixin.PIPELINE_STAGES)
            shared = runtime.arena_handles[2]
            self.assertEqual(runtime.arena_handles[0], shared)
            self.assertEqual(runtime.arena_handles[1], original_profile1_arenas)
            self.assertTrue(set(original_profile0_arenas).isdisjoint(shared))
            self.assertEqual(len([x for x in transport.download_calls if x[2] == 262144]), 4)
            self.assertEqual(len([x for x in transport.upload_calls if x[2] == 524288]), 4)
            p3_param = runtime.parameter_handles[3]
            self.assertEqual(len([x for x in transport.upload_calls
                                  if x[0] == p3_param and x[2] == 11280 * 16]), 1)
            for triplet in (transport.submits[:3], transport.submits[4:7]):
                self.assertEqual(triplet[0]["arena_a"], shared[0])
                self.assertEqual(triplet[0]["arena_b"], shared[1])
                self.assertEqual(triplet[1]["arena_a"], shared[0])
                self.assertEqual(triplet[1]["arena_b"], shared[1])
                self.assertEqual(triplet[2]["arena_a"], shared[0])
                self.assertEqual(triplet[2]["arena_b"], shared[1])
                self.assertEqual(triplet[1]["params"], p3_param)
                self.assertNotEqual(triplet[1]["params"], triplet[0]["params"])
            for timing in runtime.last_run_summary["pair_timings"]:
                evidence = timing["pl_events"][0]
                self.assertEqual(evidence["profiles"], [2, 3, 0])
                self.assertEqual(evidence["active_partition"], "n1_pl")
                self.assertEqual(evidence["p3_output_valid_region"]["word_range"],
                                 "slot0[0,16384)")
                self.assertEqual(len(evidence["jobs"]), 3)
                p3_job = evidence["jobs"][1]
                self.assertNotIn("valid_slot", p3_job["driver_completion_raw"])
                self.assertEqual(p3_job["completion"]["valid_slot"], 0)
                self.assertEqual(p3_job["completion"]["validity_source"],
                                 "ABI10.2 P3 completion contract")
                self.assertEqual(evidence["timing"]["p3_intermediate_and_gelu_reload"]
                                 ["gelu_ram_reloaded_between_dw_and_pw"], True)
                self.assertNotIn("n1", [x.get("partition") for x in timing["ps_events"]])
        finally:
            runtime.close()
        self.assertTrue(transport.closed)
        self.assertFalse(transport.allocations)
        self.assertTrue(all(client.closed for client in owned.values()))

    def test_invalid_p3_completion_fails_closed(self):
        evidence = {"profiles": [2, 3, 0], "jobs": [
            {"profile": p, "completion": {"protocol_error": 0,
             "guard_error_flags": 0, **({"valid_slot": 1,
             "output_valid_words": 16384, "output_valid_bytes": 262144,
             "only_valid_region": True} if p == 3 else {})}}
            for p in (2, 3, 0)]}
        with self.assertRaisesRegex(ValueError, "slot0 first 16384"):
            V10P3ChainMixin._validate_chain_evidence(evidence)

    def test_ps_native_n1_cannot_be_active_in_parallel(self):
        with self.assertRaisesRegex(ValueError, "PS-native n1"):
            P3ChainRuntime(ChainTransport(), contract(), MANIFEST_SHA, clients(),
                p3_parameters=parameters(), active_quantized_partitions=("n1",))


if __name__ == "__main__":
    unittest.main()
