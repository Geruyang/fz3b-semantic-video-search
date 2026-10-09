import hashlib
import os
import pathlib
import tempfile
import unittest

from desktop_vlm.board.cnn_pipeline_v10_bundle import load_v10_release_bundle
from desktop_vlm.board.run_cnn_pipeline_v10_full import preflight_bundle
from desktop_vlm.scripts.acceleration.build_cnn_v10_release_bundle import build


ROOT = pathlib.Path(__file__).resolve().parents[3]
LEGACY_BUNDLE = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10-release-bundle-002"
LEGACY_MANIFEST_SHA = "141af7fb8e552643a670045da5982c352fa4b39ee9665a8db6d3e8606baf91d4"
BUNDLE = ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-release-bundle-001"
MANIFEST_SHA = "679dc768f3525f55c05134e4d66869ea8dacb5d9fee9b1bef4d88f83b5daa268"


class V10ReleaseBundleTests(unittest.TestCase):
    def test_real_abi10_1_bundle_scales_params_models_and_component(self):
        loaded = load_v10_release_bundle(BUNDLE, MANIFEST_SHA)
        contract = loaded["parameter_contract"]
        self.assertEqual(contract["manifest_sha256"], MANIFEST_SHA)
        expected = {
            0: (9.687628574169352e-05, 8.010273432023655e-06,
                4047552, "1be71ba96c31cfb1a1734c0c3a4eb32bd2fd9f519d74f7827ae2385b604bd772"),
            1: (7.726196825520674e-05, 2.462270113096634e-05,
                19105600, "2b217316c31ab2c2e5dbb7bd897a308ff07c67941607315af90fd46b7f824814"),
            2: (0.00016495765799892816, 8.370727368858105e-05,
                703040, "8a9718b15e68d6857667d24c4d3c3c67201baaf2d3a560b657f27c358f9cd082"),
        }
        for profile, (scale_in, scale_out, size, sha) in expected.items():
            item = contract["profiles"][profile]
            self.assertEqual(item["input_scale"], scale_in)
            self.assertEqual(item["output_scale"], scale_out)
            self.assertEqual(len(item["params"]), size)
            self.assertEqual(hashlib.sha256(item["params"]).hexdigest(), sha)
        self.assertEqual(loaded["component_xml_sha256"],
                         "8f0a1241c7b63dc24276ca27b6d29fc181184097ed1395712013fc72f49ed3f1")
        self.assertIsNone(loaded["platform_identity"])

    def test_deployment_rejects_v1_and_tampered_v2_guard(self):
        with self.assertRaisesRegex(ValueError, "requires V10.1 release bundle schema v2"):
            preflight_bundle(BUNDLE, MANIFEST_SHA)
        host_root = ROOT / "artifacts/board-debug-20261006/acceleration/host"
        with tempfile.TemporaryDirectory(prefix="v10-v2-test-", dir=host_root) as temp:
            output = pathlib.Path(temp) / "bundle"
            built = build(
                ROOT / "artifacts/board-debug-20261006/acceleration/host/network10-v10.1-paired-fixtures-001",
                ROOT / "artifacts/board-debug-20261005/acceleration/host/network-w16-runtime-bundles-001",
                ROOT / "artifacts/board-debug-20261005/acceleration/host/v5-runtime-models-001",
                ROOT / "b/v10h0122/hls/impl/ip/component.xml",
                ROOT / "desktop_vlm/board/cnn_ddr_v10_driver/network10_v10_uapi.h",
                ROOT / "desktop_vlm/board/cnn_ddr_v10_driver/network10_v10_regs.h",
                ROOT / "desktop_vlm/board/cnn_ddr_v10_driver/network10_v10_driver.c",
                ROOT / "desktop_vlm/hardware/acceleration/fzv10_ddr_guard.sv",
                ROOT / "desktop_vlm/hardware/acceleration/fzv10_ddr_guard_bd.sv",
                output,
            )
            loaded = preflight_bundle(output, built["manifest_sha256"])
            self.assertEqual(loaded["platform_identity"]["core_abi"], 0x000A0001)
            guard = output / "platform-contract/fzv10_ddr_guard.sv"
            self.assertFalse(os.path.samefile(
                guard, ROOT / "desktop_vlm/hardware/acceleration/fzv10_ddr_guard.sv"))
            self.assertFalse(os.path.samefile(
                output / "hardware/component.xml",
                ROOT / "b/v10h0122/hls/impl/ip/component.xml"))
            guard.write_bytes(guard.read_bytes() + b"\n// tampered\n")
            with self.assertRaisesRegex(ValueError, "extent or SHA mismatch"):
                load_v10_release_bundle(output, built["manifest_sha256"])

    def test_legacy_abi10_layout_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "identity or provenance"):
            load_v10_release_bundle(LEGACY_BUNDLE, LEGACY_MANIFEST_SHA)

    def test_wrong_release_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "manifest SHA"):
            load_v10_release_bundle(LEGACY_BUNDLE, "0" * 64)


if __name__ == "__main__":
    unittest.main()
