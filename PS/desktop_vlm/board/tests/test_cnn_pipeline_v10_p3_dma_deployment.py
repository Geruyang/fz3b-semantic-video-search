import hashlib
import importlib.util
import json
import copy
import pathlib
import shutil
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
BOARD = ROOT / "desktop_vlm" / "board"
import sys
sys.path.insert(0, str(BOARD))

import cnn_pipeline_v10_p3_dma_deployment as deployment

BUILDER_PATH = ROOT / "desktop_vlm/scripts/acceleration/build_cnn_v10_p3_dma_deployment.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("a0004_builder", str(BUILDER_PATH))
builder = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(builder)
OVERLAY_PATH = ROOT / "desktop_vlm/scripts/acceleration/render_cnn_v10_p3_dma_overlay.py"
OVERLAY_SPEC = importlib.util.spec_from_file_location("a0004_overlay", str(OVERLAY_PATH))
overlay_builder = importlib.util.module_from_spec(OVERLAY_SPEC)
OVERLAY_SPEC.loader.exec_module(overlay_builder)


RELEASE = "3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d"
CHAIN = (ROOT / "artifacts/board-debug-20261007/acceleration/host/"
         "cnn-v10.4-p3-dma-chain-parameters-001/manifest.json")
PROVIDER = (ROOT / "artifacts/board-debug-20261008/acceleration/network/"
            "network10-v10.4-dma-provider-compatibility-001/receipt.json")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class A0004DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(ROOT))
        self.root = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _file(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": name, "bytes": len(raw), "sha256": sha(raw)}

    def _manifest(self, debug_profile=None, include_ltx=None):
        if debug_profile is None:
            debug_profile = deployment.DEBUG_PROFILE_GUARD_ILA
        if include_ltx is None:
            include_ltx = debug_profile["ltx_required"]
        files = {}
        file_names = {
                "bitstream", "dtbo", "full_platform_receipt",
                "address_map_receipt", "timing_receipt",
                "guard_validation_receipt", "driver_module",
                "driver_compile_receipt", "module_symvers",
                "factory_bitstream", "factory_driver"}
        if include_ltx:
            file_names.add("ltx")
        for name in sorted(file_names):
            extension = {"bitstream": ".bit", "ltx": ".ltx",
                         "dtbo": ".dtbo", "driver_module": ".ko"}.get(name, ".json")
            files[name] = self._file(name + extension, (name + "\n").encode())
        chain_raw = CHAIN.read_bytes()
        files["chain_parameter_manifest"] = self._file("chain.json", chain_raw)
        provider_raw = PROVIDER.read_bytes()
        files["dma_provider_compatibility_receipt"] = self._file(
            "provider.json", provider_raw)
        gates = {name: True for name in {
            "all_rtl_profiles_pass", "rtl_stress_pass",
            "full_platform_route_pass", "internal_setup_met",
            "internal_hold_met", "guard_six_master_pass",
            "target_module_compile_pass", "restore_assets_verified"} |
            deployment.EXTRA_GATES}
        files["full_platform_receipt"]["sha256"] = sha(
            (self.root / files["full_platform_receipt"]["path"]).read_bytes())
        files["timing_receipt"]["sha256"] = sha(
            (self.root / files["timing_receipt"]["path"]).read_bytes())
        return {
            "schema": deployment.SCHEMA,
            "status": "READY_FOR_BOARD_VALIDATION",
            "identity": deployment.IDENTITY,
            "release_manifest_sha256": RELEASE,
            "target": deployment.TARGET,
            "clock": {
                "domain": "single-domain kernel/AXI", "kernel_hz": 101375992,
                "identity": {
                    "basis": "current-board-pl0-hz-x-implemented-mmcm-ratio",
                    "board_input_hz": 101375992, "board_input_rechecked": True,
                    "implemented_mmcm_m": 1, "implemented_mmcm_d": 1,
                    "implemented_mmcm_o0": 1, "master_clock": "pl0",
                    "generated_clock": "kernel",
                    "full_platform_receipt_sha256":
                        files["full_platform_receipt"]["sha256"],
                    "timing_receipt_sha256": files["timing_receipt"]["sha256"],
                }},
            "gates": gates, "files": files,
            "chain_contract": deployment.CHAIN_CONTRACT,
            "chain_parameter_manifest_sha256": deployment.CHAIN_MANIFEST_SHA256,
            "debug_profile": debug_profile,
        }

    def test_exact_a0004_package_loads_and_reports_cached_dma_disabled(self):
        manifest = self._manifest()
        path = self.root / "manifest.json"
        raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        loaded = deployment.load_v10_p3_dma_deployment(
            path, sha(raw), RELEASE, deployment.CHAIN_MANIFEST_SHA256)
        self.assertFalse(loaded["cached_dma_cap_expected"])
        self.assertEqual(loaded["chain_contract"]["core_abi"], 0x000A0004)
        self.assertTrue(loaded["native_ila_capture_applicable"])

    def test_no_ila_package_loads_without_ltx_and_marks_capture_not_applicable(self):
        manifest = self._manifest(deployment.DEBUG_PROFILE_NO_ILA)
        self.assertEqual(
            manifest["debug_profile"]["hls_ap_none_trace_port_count"], 12)
        self.assertEqual(
            manifest["debug_profile"]["platform_trace_mmio_register_count"], 0)
        self.assertEqual(manifest["debug_profile"]["mmio_trace_count"], 0)
        self.assertIs(manifest["debug_profile"]["trace_outputs_connected"],
                      False)
        self.assertEqual(manifest["debug_profile"]["trace_output_transport"],
                         "ap_none")
        self.assertNotIn("ltx", manifest["files"])
        path = self.root / "no-ila-manifest.json"
        raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        loaded = deployment.load_v10_p3_dma_deployment(
            path, sha(raw), RELEASE, deployment.CHAIN_MANIFEST_SHA256)
        self.assertFalse(loaded["native_ila_capture_applicable"])
        self.assertNotIn("ltx", loaded["files"])

    def test_no_ila_rejects_dummy_ltx_and_false_inventory(self):
        manifest = self._manifest(deployment.DEBUG_PROFILE_NO_ILA,
                                  include_ltx=True)
        path = self.root / "no-ila-with-ltx.json"
        raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "artifact set"):
            deployment.load_v10_p3_dma_deployment(
                path, sha(raw), RELEASE, deployment.CHAIN_MANIFEST_SHA256)
        manifest = self._manifest(deployment.DEBUG_PROFILE_NO_ILA)
        manifest["debug_profile"] = dict(manifest["debug_profile"],
                                         debug_hub_count=1)
        path = self.root / "false-no-ila-inventory.json"
        raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "debug profile"):
            deployment.load_v10_p3_dma_deployment(
                path, sha(raw), RELEASE, deployment.CHAIN_MANIFEST_SHA256)

    def test_no_ila_rejects_historical_false_mmio_trace_claim(self):
        manifest = self._manifest(deployment.DEBUG_PROFILE_NO_ILA)
        manifest["debug_profile"] = dict(manifest["debug_profile"],
                                          mmio_trace_count=12)
        path = self.root / "historical-false-mmio.json"
        raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "debug profile"):
            deployment.load_v10_p3_dma_deployment(
                path, sha(raw), RELEASE, deployment.CHAIN_MANIFEST_SHA256)

        manifest = self._manifest(deployment.DEBUG_PROFILE_NO_ILA)
        manifest["debug_profile"] = dict(
            manifest["debug_profile"], trace_outputs_connected=True)
        path = self.root / "false-trace-connection.json"
        raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "debug profile"):
            deployment.load_v10_p3_dma_deployment(
                path, sha(raw), RELEASE, deployment.CHAIN_MANIFEST_SHA256)

    def test_ila_profile_rejects_missing_ltx(self):
        manifest = self._manifest(deployment.DEBUG_PROFILE_GUARD_ILA,
                                  include_ltx=False)
        path = self.root / "ila-without-ltx.json"
        raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "artifact set"):
            deployment.load_v10_p3_dma_deployment(
                path, sha(raw), RELEASE, deployment.CHAIN_MANIFEST_SHA256)

    def test_old_abi_and_false_provider_claim_are_rejected(self):
        manifest = self._manifest()
        manifest["identity"] = dict(deployment.IDENTITY, core_abi="0x000A0003")
        path = self.root / "manifest.json"
        raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "identity"):
            deployment.load_v10_p3_dma_deployment(
                path, sha(raw), RELEASE, deployment.CHAIN_MANIFEST_SHA256)

    def _source_record(self, name, value):
        path = self.root / name
        raw = (json.dumps(value, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        return {"source_path": path.relative_to(ROOT).as_posix(),
                "package_path": name, "sha256": sha(raw)}

    def _full_platform(self, debug_profile=None, include_ltx=None):
        if debug_profile is None:
            debug_profile = deployment.DEBUG_PROFILE_GUARD_ILA
        if include_ltx is None:
            include_ltx = debug_profile["ltx_required"]
        artifact = lambda name: {
            "path": "route/" + name, "bytes": 1,
            "sha256": sha(name.encode())}
        artifact_names = {"bitstream", "bin", "final_dcp"}
        if include_ltx:
            artifact_names.add("ltx")
        return {
            "schema": builder.FULL_PLATFORM_SCHEMA, "pass": True,
            "status": "PASS", "identity": builder.EXPECTED_PLATFORM_IDENTITY,
            "address_map": dict(copy.deepcopy(builder.EXPECTED_ADDRESS_MAP),
                report_sha256=sha(b"address"),
                interface_widths_sha256=sha(b"widths"),
                abi_wiring_sha256=sha(b"abi"),
                exact_bd_tcl_sha256=sha(b"bd")),
            "clock": {"kernel_hz": 196415984.5,
                      "implemented_exact_hz": "196415984.5",
                      "master_clock": "pl0", "generated_clock": "kernel",
                      "mmcm": {"divclk_divide": 8,
                               "clkfbout_mult_f": "96.875",
                               "clkout0_divide_f": "6.25"}},
            "timing": {"setup_wns_ns": 0.01, "hold_whs_ns": 0.01,
                       "pulse_width_min_slack_ns": 0.01,
                       "route_errors": 0, "drc_violations": 0,
                       "check_timing_violations": 0},
            "artifacts": {name: artifact(name) for name in artifact_names},
            "debug_profile": debug_profile}

    def test_final_platform_and_derived_receipts_are_semantically_bound(self):
        full = self._full_platform()
        full_record = self._source_record("full.json", full)
        parsed = builder._validate_final_platform_receipt(full_record)
        self.assertEqual(parsed["clock"]["kernel_hz"], 196415984.5)
        address_record = self._source_record("address.json", {
            "schema": builder.ADDRESS_RECEIPT_SCHEMA, "pass": True,
            "full_platform_receipt_sha256": full_record["sha256"],
            "address_map": full["address_map"]})
        timing_record = self._source_record("timing.json", {
            "schema": builder.TIMING_RECEIPT_SCHEMA, "pass": True,
            "full_platform_receipt_sha256": full_record["sha256"],
            "timing": full["timing"], "clock": full["clock"]})
        builder._validate_derived_receipts(
            {"address_map_receipt": address_record,
             "timing_receipt": timing_record}, full_record, full)

    def test_final_platform_rejects_wrong_window_and_nonzero_route_errors(self):
        full = self._full_platform()
        full["address_map"]["guard_identity"]["base"] = "0xa4020000"
        record = self._source_record("wrong-address.json", full)
        with self.assertRaisesRegex(ValueError, "guard_identity window"):
            builder._validate_final_platform_receipt(record)
        full = self._full_platform()
        full["timing"]["route_errors"] = 1
        record = self._source_record("bad-route.json", full)
        with self.assertRaisesRegex(ValueError, "route_errors"):
            builder._validate_final_platform_receipt(record)

    def test_final_platform_no_ila_accepts_absent_ltx_and_rejects_contradictions(self):
        full = self._full_platform(deployment.DEBUG_PROFILE_NO_ILA)
        record = self._source_record("no-ila-full.json", full)
        parsed = builder._validate_final_platform_receipt(record)
        self.assertNotIn("ltx", parsed["artifacts"])
        full = self._full_platform(deployment.DEBUG_PROFILE_NO_ILA,
                                   include_ltx=True)
        record = self._source_record("no-ila-dummy-ltx.json", full)
        with self.assertRaisesRegex(ValueError, "artifact inventory"):
            builder._validate_final_platform_receipt(record)

    def test_ila_ltx_must_match_final_platform_artifact(self):
        full = self._full_platform(deployment.DEBUG_PROFILE_GUARD_ILA)
        sources = {
            "bitstream": {"sha256": full["artifacts"]["bitstream"]["sha256"]},
            "ltx": {"sha256": sha(b"different-ltx")},
        }
        with self.assertRaisesRegex(ValueError, "LTX is not from final build"):
            builder._validate_final_artifact_binding(
                sources, full, deployment.DEBUG_PROFILE_GUARD_ILA)
        full = self._full_platform(deployment.DEBUG_PROFILE_GUARD_ILA,
                                   include_ltx=False)
        record = self._source_record("ila-missing-ltx.json", full)
        with self.assertRaisesRegex(ValueError, "artifact inventory"):
            builder._validate_final_platform_receipt(record)

    def test_overlay_source_requires_final_receipt_and_has_no_dma_binding(self):
        full = self._full_platform()
        full_record = self._source_record("overlay-full.json", full)
        dts = self.root / "network10_v10_p3_dma.dts"
        receipt = self.root / "overlay-receipt.json"
        result = overlay_builder.render(
            ROOT / full_record["source_path"], full_record["sha256"],
            dts, receipt)
        text = dts.read_text(encoding="utf-8")
        self.assertIn('status = "okay";', text)
        self.assertIn("0xa4000000", text)
        self.assertIn("0xa4010000", text)
        self.assertNotIn("dmas =", text)
        self.assertNotIn("dma-names", text)
        self.assertFalse(result["checks"]["dtbo_compiled"])


if __name__ == "__main__":
    unittest.main()
