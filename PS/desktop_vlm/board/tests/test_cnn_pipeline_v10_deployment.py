import hashlib
import json
import pathlib
import tempfile
import unittest

from desktop_vlm.board.cnn_pipeline_v10_deployment import (
    CLOCK_IDENTITY_BASIS, IDENTITY, KERNEL_RELEASE, REQUIRED_FILES,
    load_v10_platform_deployment,
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class V10PlatformDeploymentTests(unittest.TestCase):
    def _package(self, root):
        suffixes = {
            "bitstream": ".bit", "ltx": ".ltx", "dtbo": ".dtbo",
            "driver_module": ".ko", "module_symvers": ".symvers",
            "factory_bitstream": ".bin", "factory_driver": ".ko",
        }
        files = {}
        for name in sorted(REQUIRED_FILES):
            path = root / (name + suffixes.get(name, ".json"))
            raw = (name + "\n").encode("ascii")
            path.write_bytes(raw)
            files[name] = {"path": path.name, "bytes": len(raw), "sha256": sha(raw)}
        release = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
        manifest = {
            "schema": "cnn-pipeline-v10.1-platform-deployment-v2",
            "status": "READY_FOR_BOARD_VALIDATION",
            "release_manifest_sha256": release,
            "identity": IDENTITY,
            "target": {"kernel_release": KERNEL_RELEASE,
                       "device": "/dev/network10_v10",
                       "module": "cnn_ddr_v10_candidate"},
            "clock": {
                "kernel_hz": 196415985,
                "domain": "single-domain kernel/AXI",
                "identity": {
                    "basis": CLOCK_IDENTITY_BASIS,
                    "board_input_hz": 101375992,
                    "board_input_rechecked": True,
                    "implemented_mmcm_m": "96.875",
                    "implemented_mmcm_d": 8,
                    "implemented_mmcm_o0": "6.250",
                    "master_clock": "clk_pl_0",
                    "generated_clock":
                        "clk_out1_cnn_pipeline_v10_shell_clock_wiz_0",
                    "full_platform_receipt_sha256":
                        files["full_platform_receipt"]["sha256"],
                    "timing_receipt_sha256":
                        files["timing_receipt"]["sha256"],
                },
            },
            "gates": {
                "all_rtl_profiles_pass": True,
                "rtl_stress_pass": True,
                "full_platform_route_pass": True,
                "internal_setup_met": True,
                "internal_hold_met": True,
                "guard_six_master_pass": True,
                "target_module_compile_pass": True,
                "restore_assets_verified": True,
            },
            "files": files,
        }
        raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        path = root / "manifest.json"
        path.write_bytes(raw)
        return path, sha(raw), release

    def test_complete_platform_manifest_accepts_and_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            path, manifest_sha, release = self._package(root)
            loaded = load_v10_platform_deployment(path, manifest_sha, release)
            self.assertEqual(loaded["clock_hz"], 196415985)
            (root / "guard_validation_receipt.json").write_bytes(b"tampered\n")
            with self.assertRaisesRegex(ValueError, "extent or SHA mismatch"):
                load_v10_platform_deployment(path, manifest_sha, release)

    def test_incomplete_gate_rejects_before_device_use(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            path, unused_sha, release = self._package(root)
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["gates"]["rtl_stress_pass"] = False
            raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "gates are incomplete"):
                load_v10_platform_deployment(path, sha(raw), release)

    def test_clock_identity_or_receipt_mismatch_rejects(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            path, unused_sha, release = self._package(root)
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["clock"]["identity"]["board_input_rechecked"] = False
            raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "clock identity is invalid"):
                load_v10_platform_deployment(path, sha(raw), release)

            path, unused_sha, release = self._package(root)
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["clock"]["identity"]["timing_receipt_sha256"] = "0" * 64
            raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "clock receipt binding mismatch"):
                load_v10_platform_deployment(path, sha(raw), release)


if __name__ == "__main__":
    unittest.main()
