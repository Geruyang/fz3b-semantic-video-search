import copy
import pathlib
import sys
import unittest


BOARD = pathlib.Path(__file__).resolve().parents[1]
if str(BOARD) not in sys.path:
    sys.path.insert(0, str(BOARD))

from cnn_pipeline_v8_ab import build_contract


def report():
    frames = []
    outputs = []
    for index in range(30):
        frame_id = 100 + index
        frames.append({
            "frame_id": frame_id,
            "input_sha256": ("%064x" % (index % 3 + 1)),
            "driver_completions": [
                {"profile": 2, "job_cycles": 10},
                {"profile": 0, "job_cycles": 20},
                {"profile": 1, "job_cycles": 30},
            ],
        })
        outputs.append({"frame_id": frame_id, "bytes": 2048,
                        "sha256": "%064x" % (index % 3 + 4)})
    return {
        "status": "BOARD_V6_BENCHMARK_COMPLETED",
        "execution": "board_linux_ioctl_fzv6",
        "warmup_policy": {"frames": 3},
        "measurement_policy": {"frames": 30},
        "parameter_binding": {"physical_profiles": [2, 0, 1], "sha": "x"},
        "runtime_config_sha256": "a" * 64,
        "split_manifest_sha256": "b" * 64,
        "kernel_boot_id": "boot",
        "pl_clock": {"hz": 100},
        "measurement": {"frames": frames, "batch_wall_ms": 3000,
                        "throughput_fps": 10},
        "feature_outputs": outputs,
    }


class V8AbTests(unittest.TestCase):
    def test_contract_freezes_identical_inputs_outputs_cycles_and_timing_scope(self):
        value = report()
        contract = build_contract(value, "1" * 64, copy.deepcopy(value), "2" * 64)
        self.assertEqual(contract["status"], "FZV8_AB_CONTRACT_READY")
        self.assertEqual(contract["candidate_requirements"]["physical_profiles"], [2, 0, 1])
        self.assertEqual(contract["v6_baselines"]["pipeline"]["profile_cycles"]["0"]["mean_cycles"], 20)
        self.assertIn("excludes client/transport initialization",
                      contract["candidate_requirements"]["timing"]["batch_wall"])

    def test_contract_rejects_input_or_feature_drift(self):
        serial = report()
        pipeline = copy.deepcopy(serial)
        pipeline["measurement"]["frames"][2]["input_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "input_sha256_sequence"):
            build_contract(serial, "1" * 64, pipeline, "2" * 64)
        pipeline = copy.deepcopy(serial)
        pipeline["feature_outputs"][4]["sha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "raw512_sha256_sequence"):
            build_contract(serial, "1" * 64, pipeline, "2" * 64)


if __name__ == "__main__":
    unittest.main()
