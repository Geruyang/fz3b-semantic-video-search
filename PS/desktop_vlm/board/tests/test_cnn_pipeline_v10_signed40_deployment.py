import copy
import hashlib
import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
BOARD = ROOT / "desktop_vlm/board"
sys.path.insert(0, str(BOARD))

import cnn_pipeline_v10_signed40_deployment as deployment  # noqa: E402

RENDERER_PATH = ROOT / "desktop_vlm/scripts/acceleration/render_cnn_v10_signed40_overlay.py"
RENDERER_SPEC = importlib.util.spec_from_file_location("a0005_overlay", str(RENDERER_PATH))
renderer = importlib.util.module_from_spec(RENDERER_SPEC)
RENDERER_SPEC.loader.exec_module(renderer)
BUILDER_PATH = ROOT / "desktop_vlm/scripts/acceleration/build_cnn_v10_signed40_deployment.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("a0005_builder", str(BUILDER_PATH))
builder = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(builder)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class A0005DeploymentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(ROOT))
        self.root = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _record(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": name, "bytes": len(raw), "sha256": sha(raw)}

    def _copy_record(self, name, source):
        return self._record(name, pathlib.Path(source).read_bytes())

    def _manifest(self):
        files = {}
        for name, extension in {
                "bitstream": ".bit", "configuration_bin": ".bin",
                "dtbo": ".dtbo", "full_platform_receipt": ".json",
                "address_map_receipt": ".json", "timing_receipt": ".json",
                "guard_validation_receipt": ".json",
                "module_symvers": ".txt", "factory_bitstream": ".bin",
                "factory_driver": ".ko"}.items():
            if name != "full_platform_receipt":
                files[name] = self._record(name + extension,
                                           (name + "\n").encode())
        files["driver_module"] = self._copy_record(
            "driver.ko", ROOT / "artifacts/board-debug-20261008/acceleration/"
            "network/network10-v10.5-a0005-driver-compile-001/"
            "cnn_ddr_v10_signed40_candidate.ko")
        files["driver_compile_receipt"] = self._copy_record(
            "driver-compile.json", ROOT / "artifacts/board-debug-20261008/"
            "acceleration/network/network10-v10.5-a0005-driver-compile-001/receipt.json")
        files["chain_parameter_manifest"] = self._copy_record(
            "combined.json", ROOT / "artifacts/board-debug-20261008/acceleration/"
            "host/network10-v10.5-pw2-signed40-combined-001/manifest.json")
        files["signed40_admission"] = self._copy_record(
            "admission.json", ROOT / "artifacts/board-debug-20261008/acceleration/"
            "host/network10-v10.5-pw2-signed40-combined-001/admission.json")
        files["signed40_range_proof"] = self._copy_record(
            "proof.json", ROOT / "artifacts/board-debug-20261008/acceleration/"
            "host/network10-v10.5-pw2-signed40-proof-003/proof.json")
        files["candidate_source_manifest"] = self._copy_record(
            "source.json", ROOT / "desktop_vlm/hardware/acceleration/experiments/"
            "dual_lane_storage_dw7_opt/candidate/source-manifest.json")
        files["candidate_contract"] = self._copy_record(
            "contract.json", ROOT / "desktop_vlm/hardware/acceleration/experiments/"
            "dual_lane_storage_dw7_opt/candidate/candidate-contract.json")
        identity = dict(
            deployment.IDENTITY,
            combined_parameter_manifest_sha256=deployment.COMBINED_SHA256,
            candidate_source_manifest_sha256=
                deployment.SOURCE_MANIFEST_SHA256,
            candidate_contract_sha256=
                deployment.CANDIDATE_CONTRACT_SHA256)
        timing = {
            "setup_wns_ns": 0.01, "hold_whs_ns": 0.01,
            "pulse_width_min_slack_ns": 0.01, "route_errors": 0,
            "drc_violations": 0, "check_timing_violations": 0,
            "cdc_violations": 0,
            "path_groups": {name: {"setup_wns_ns": 0.01,
                                    "hold_whs_ns": 0.01}
                            for name in deployment.PATH_GROUPS},
        }
        platform = {
            "schema": deployment.FINAL_PLATFORM_SCHEMA,
            "pass": True, "status": "PASS", "identity": identity,
            "clock": deployment.CLOCK_CONTRACT,
            "debug_profile": deployment.DEBUG_PROFILE,
            "address_map": {
                "hls_control": {"base": "0xa4000000", "size": "0x00010000"},
                "guard_identity": {"base": "0xa4010000", "size": "0x00010000"}},
            "timing": timing,
            "artifacts": {
                "bitstream": files["bitstream"],
                "bin": files["configuration_bin"],
                "final_dcp": {"path": "route/final.dcp", "bytes": 1,
                              "sha256": sha(b"dcp")}},
        }
        platform_raw = (json.dumps(platform, sort_keys=True) + "\n").encode()
        files["full_platform_receipt"] = self._record(
            "full-platform.json", platform_raw)
        return {
            "schema": deployment.SCHEMA,
            "status": "READY_FOR_BOARD_VALIDATION",
            "identity": deployment.IDENTITY, "target": deployment.TARGET,
            "base_release_manifest_sha256": "3" * 64,
            "chain_contract": deployment.CHAIN_CONTRACT,
            "combined_parameter_manifest_sha256": deployment.COMBINED_SHA256,
            "candidate_source_manifest_sha256":
                deployment.SOURCE_MANIFEST_SHA256,
            "candidate_contract_sha256":
                deployment.CANDIDATE_CONTRACT_SHA256,
            "clock": deployment.CLOCK_CONTRACT,
            "debug_profile": deployment.DEBUG_PROFILE,
            "gates": {name: True for name in deployment.REQUIRED_GATES},
            "files": files,
        }

    def _write(self, value, name="manifest.json"):
        path = self.root / name
        raw = (json.dumps(value, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        return path, sha(raw)

    def test_complete_package_loads_and_exposes_both_clocks(self):
        path, digest = self._write(self._manifest())
        loaded = deployment.load_v10_signed40_deployment(
            path, digest, "3" * 64,
            deployment.COMBINED_SHA256)
        self.assertEqual(loaded["clock_hz"], 199999998)
        self.assertEqual(loaded["pw_local_clock_hz"], 399999996)
        self.assertFalse(loaded["native_ila_capture_applicable"])

    def test_rejects_old_abi_ltx_and_missing_cross_domain_timing(self):
        value = self._manifest()
        value["identity"] = dict(value["identity"], core_abi="0x000A0004")
        path, digest = self._write(value, "old.json")
        with self.assertRaisesRegex(ValueError, "identity"):
            deployment.load_v10_signed40_deployment(
                path, digest, "3" * 64,
                deployment.COMBINED_SHA256)

    def test_overlay_renderer_binds_final_receipt_without_clock_or_dma_claims(self):
        value = self._manifest()
        full_record = value["files"]["full_platform_receipt"]
        full_path = self.root / full_record["path"]
        dts = self.root / "a0005.dts"
        receipt = self.root / "a0005-overlay.json"
        result = renderer.render(full_path, full_record["sha256"], dts, receipt)
        text = dts.read_text(encoding="utf-8")
        self.assertIn('compatible = "fz3b,cnn-ddr-v10-signed40-candidate";',
                      text)
        self.assertIn("0x000a0005", text)
        self.assertIn("0x00000fff", text)
        self.assertNotIn("dmas =", text)
        self.assertNotIn("dma-names", text)
        self.assertNotIn("clock-frequency", text)
        self.assertTrue(result["checks"]["clock_properties_absent"])

    def test_builder_copies_frozen_sources_and_self_loads(self):
        value = self._manifest()
        sources = {}
        for name, record in value["files"].items():
            source = self.root / record["path"]
            sources[name] = {
                "source_path": source.relative_to(ROOT).as_posix(),
                "package_path": "files/" + source.name,
                "sha256": record["sha256"]}
        spec = {
            "schema": builder.INPUT_SCHEMA,
            "status": "FINAL_INPUTS_APPROVED",
            "identity": deployment.IDENTITY, "target": deployment.TARGET,
            "base_release_manifest_sha256": "3" * 64,
            "chain_contract": deployment.CHAIN_CONTRACT,
            "combined_parameter_manifest_sha256": deployment.COMBINED_SHA256,
            "candidate_source_manifest_sha256":
                deployment.SOURCE_MANIFEST_SHA256,
            "candidate_contract_sha256":
                deployment.CANDIDATE_CONTRACT_SHA256,
            "clock": deployment.CLOCK_CONTRACT,
            "debug_profile": deployment.DEBUG_PROFILE,
            "gates": {name: True for name in deployment.REQUIRED_GATES},
            "files": sources}
        spec_path = self.root / "builder-spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        output = self.root / "package"
        receipt = builder.build(spec_path, output)
        self.assertTrue(receipt["pass"])
        loaded = deployment.load_v10_signed40_deployment(
            output / "manifest.json", receipt["manifest_sha256"],
            "3" * 64, deployment.COMBINED_SHA256)
        self.assertEqual(loaded["clock_hz"], 199999998)
        value = self._manifest()
        value["files"]["ltx"] = self._record("fake.ltx", b"fake")
        path, digest = self._write(value, "ltx.json")
        with self.assertRaisesRegex(ValueError, "artifact set"):
            deployment.load_v10_signed40_deployment(
                path, digest, "3" * 64,
                deployment.COMBINED_SHA256)
        value = self._manifest()
        platform_path = self.root / value["files"]["full_platform_receipt"]["path"]
        platform = json.loads(platform_path.read_text(encoding="utf-8"))
        del platform["timing"]["path_groups"]["slow_to_fast"]
        raw = (json.dumps(platform, sort_keys=True) + "\n").encode()
        platform_path.write_bytes(raw)
        value["files"]["full_platform_receipt"] = {
            "path": platform_path.name, "bytes": len(raw), "sha256": sha(raw)}
        path, digest = self._write(value, "bad-timing.json")
        with self.assertRaisesRegex(ValueError, "path group"):
            deployment.load_v10_signed40_deployment(
                path, digest, "3" * 64,
                deployment.COMBINED_SHA256)


if __name__ == "__main__":
    unittest.main()
