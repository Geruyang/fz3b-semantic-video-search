"""Offline tests for the production FZV6 parameter-contract loader."""

import hashlib
import json
import os
import tempfile
import unittest

from desktop_vlm.board.cnn_pipeline_v6_bundle import (
    load_fzv6_parameter_contract,
)
from desktop_vlm.board.cnn_pipeline_v6_fzv6_backend import PROFILE_SPECS


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _sha_file(path):
    with open(path, "rb") as stream:
        return _sha(stream.read())


def _canonical_sha(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return _sha(encoded)


class Fzv6BundleLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.stage_dir = os.path.join(self.root, "stage6")
        self.v5_dir = os.path.join(self.root, "v5")
        os.makedirs(self.stage_dir)
        os.makedirs(self.v5_dir)
        self.stage_path = os.path.join(self.stage_dir, "manifest.json")
        self.bundle_path = os.path.join(self.v5_dir, "manifest.json")
        self.scales_path = os.path.join(self.v5_dir, "scale-manifest.json")
        self.bundle, self.scales, self.stage = self._make_fixture()

    def tearDown(self):
        self.temp.cleanup()

    def _make_fixture(self):
        abi = {"magic": "FZV5", "version": 327680, "flags": 0}
        bundle = {
            "schema_version": 1,
            "abi": abi,
            "checks": {"profiles": ["0", "1", "2"],
                       "parameter_files_have_no_headers": True,
                       "board_or_pl_execution": False},
            "profiles": {},
            "files": {},
        }
        scales = {"schema_version": 1, "abi": abi, "profiles": {}}
        canonical_records = {}
        for profile in (0, 1, 2):
            spec = PROFILE_SPECS[profile]
            key = str(profile)
            network = {0: "network2", 1: "network4", 2: "network0"}[profile]
            path = "params-profile%d.bin" % profile
            payload = bytes(spec.parameter_bytes)
            with open(os.path.join(self.v5_dir, path), "wb") as stream:
                stream.write(payload)
            sources = []
            per_block = []
            stride = spec.block_stride_words * 16
            previous_add = None
            for index in range(spec.max_blocks):
                chunk = payload[index * stride:(index + 1) * stride]
                block_sha = _sha(chunk)
                sources.append({"index": index, "bytes": stride,
                                "sha256": block_sha})
                input_scale = (0.001 * (profile + 1) if index == 0
                               else previous_add)
                add_scale = input_scale * 1.125
                per_block.append({"block_index": index,
                                  "parameter_block_sha256": block_sha,
                                  "scales": {"input": input_scale,
                                             "add": add_scale}})
                previous_add = add_scale
            file_record = {"bytes": len(payload), "sha256": _sha(payload)}
            bundle["files"][path] = file_record
            bundle["profiles"][key] = {
                "profile": profile,
                "network": network,
                "channels": spec.channels,
                "width": spec.width,
                "block_count": spec.max_blocks,
                "parameter_words_per_block": spec.block_stride_words,
                "block_stride_bytes": spec.block_stride_words * 16,
                "slot_bytes": spec.activation_bytes,
                "parameter_file": {"path": path, **file_record},
                "block_parameter_sources": sources,
            }
            scales["profiles"][key] = {"profile": profile,
                                       "per_block": per_block}
            canonical_records[key] = {
                "parameter_blob": {
                    0: "profile-0-network2-params-w16.bin",
                    1: "profile-1-network4-params-w16.bin",
                    2: "profile-2-network0-params-w16.bin",
                }[profile],
                "canonical_path": path,
                "bytes": len(payload),
                "sha256": _sha(payload),
                "included_in_this_pack": False,
            }

        scale_bytes = json.dumps(scales, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True).encode("utf-8")
        with open(self.scales_path, "wb") as stream:
            stream.write(scale_bytes)
        bundle["files"]["scale-manifest.json"] = {
            "bytes": len(scale_bytes), "sha256": _sha(scale_bytes)}
        bundle_bytes = json.dumps(bundle, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=True).encode("utf-8")
        with open(self.bundle_path, "wb") as stream:
            stream.write(bundle_bytes)
        bundle_sha = _sha(bundle_bytes)
        for alias in canonical_records.values():
            alias["source_bundle_manifest_sha256"] = bundle_sha

        calibration_scales = {
            "p3_input": scales["profiles"]["2"]["per_block"][-1]["scales"]["add"],
            "p3_gelu_output": 0.3,
            "p4_output": scales["profiles"]["0"]["per_block"][0]["scales"]["input"],
            "p5_input": scales["profiles"]["0"]["per_block"][-1]["scales"]["add"],
            "p5_output": 0.6,
            "ps_se_gelu_output": 0.7,
            "p6_output": scales["profiles"]["1"]["per_block"][0]["scales"]["input"],
        }
        profile_records = {}
        for profile in (3, 4, 5, 6):
            spec = PROFILE_SPECS[profile]
            output_channels, output_width = {
                3: (128, 32), 4: (128, 32), 5: (256, 16), 6: (256, 16),
            }[profile]
            payload = bytes(spec.parameter_bytes)
            blob = "profile-%d-params.bin" % profile
            with open(os.path.join(self.stage_dir, blob), "wb") as stream:
                stream.write(payload)
            stage_scale = {
                3: ("p3_input", "p3_gelu_output"),
                4: ("p3_gelu_output", "p4_output"),
                5: ("p5_input", "p5_output"),
                6: ("ps_se_gelu_output", "p6_output"),
            }[profile]
            profile_records["p%d" % profile] = {
                "profile": "p%d" % profile,
                "block_count": 1,
                "channels": output_channels,
                "width": output_width,
                "block_stride_words": spec.block_stride_words,
                "parameter_blob": blob,
                "parameter_bytes": len(payload),
                "parameter_sha256": _sha(payload),
                "scale_input": calibration_scales[stage_scale[0]],
                "scale_output": calibration_scales[stage_scale[1]],
            }
        stage = {
            "schema_version": 1,
            "status": "candidate_not_accuracy_claim",
            "v5_bundle_manifest_sha256": bundle_sha,
            "scale_manifest_sha256": _sha(scale_bytes),
            "calibration": {"scales": calibration_scales},
            "profiles": profile_records,
            "canonical_profile_aliases": canonical_records,
        }
        self._write_stage(stage)
        return bundle, scales, stage

    def _write_stage(self, value):
        with open(self.stage_path, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)

    def _load(self):
        return load_fzv6_parameter_contract(
            self.stage_path, self.bundle_path, self.scales_path,
            expected_manifest_sha256=_canonical_sha(self.stage),
            expected_v5_bundle_sha256=_sha_file(self.bundle_path),
            expected_v5_scale_sha256=_sha_file(self.scales_path))

    def test_loads_all_seven_blobs_and_semantic_scales_exactly(self):
        contract = self._load()
        self.assertEqual(contract["manifest_sha256"], _canonical_sha(self.stage))
        self.assertEqual(set(contract["profiles"]), set(range(7)))
        for profile in range(7):
            record = contract["profiles"][profile]
            self.assertEqual(len(record["params"]),
                             PROFILE_SPECS[profile].parameter_bytes)
            self.assertEqual(_sha(record["params"]), record["params_sha256"])
        expected_normal = {
            0: (self.scales["profiles"]["0"]["per_block"][0]["scales"]["input"],
                self.scales["profiles"]["0"]["per_block"][-1]["scales"]["add"]),
            1: (self.scales["profiles"]["1"]["per_block"][0]["scales"]["input"],
                self.scales["profiles"]["1"]["per_block"][-1]["scales"]["add"]),
            2: (self.scales["profiles"]["2"]["per_block"][0]["scales"]["input"],
                self.scales["profiles"]["2"]["per_block"][-1]["scales"]["add"]),
        }
        for profile, values in expected_normal.items():
            self.assertEqual((contract["profiles"][profile]["input_scale"],
                              contract["profiles"][profile]["output_scale"]), values)
        self.assertEqual(contract["profiles"][3]["input_scale"],
                         self.stage["calibration"]["scales"]["p3_input"])
        self.assertEqual(contract["profiles"][3]["output_scale"], 0.3)
        self.assertEqual(contract["profiles"][4]["input_scale"], 0.3)
        self.assertEqual(contract["profiles"][4]["output_scale"],
                         self.stage["calibration"]["scales"]["p4_output"])
        self.assertEqual(contract["profiles"][5]["input_scale"],
                         self.stage["calibration"]["scales"]["p5_input"])
        self.assertEqual(contract["profiles"][5]["output_scale"], 0.6)
        self.assertEqual(contract["profiles"][6]["input_scale"], 0.7)
        self.assertEqual(contract["profiles"][6]["output_scale"],
                         self.stage["calibration"]["scales"]["p6_output"])

    def test_requires_expected_canonical_manifest_sha(self):
        with self.assertRaises(ValueError):
            load_fzv6_parameter_contract(
                self.stage_path, self.bundle_path, self.scales_path,
                expected_manifest_sha256="0" * 64)

    def test_rejects_transition_blob_hash_mismatch(self):
        path = os.path.join(self.stage_dir, "profile-4-params.bin")
        with open(path, "ab") as stream:
            stream.write(b"tamper")
        with self.assertRaises(ValueError):
            self._load()

    def test_rejects_stage6_blob_path_traversal(self):
        self.stage["profiles"]["p4"]["parameter_blob"] = "../profile-4-params.bin"
        self._write_stage(self.stage)
        with self.assertRaises(ValueError):
            self._load()

    def test_rejects_symlink_parameter_blob_when_supported(self):
        target = os.path.join(self.root, "outside.bin")
        with open(target, "wb") as stream:
            stream.write(bytes(PROFILE_SPECS[3].parameter_bytes))
        link = os.path.join(self.stage_dir, "linked-profile-3.bin")
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("host does not permit symlink creation")
        self.stage["profiles"]["p3"]["parameter_blob"] = "linked-profile-3.bin"
        self._write_stage(self.stage)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self._load()

    def test_rejects_mismatched_canonical_alias_path(self):
        self.stage["canonical_profile_aliases"]["0"]["canonical_path"] = "../escape.bin"
        self._write_stage(self.stage)
        with self.assertRaises(ValueError):
            self._load()

    def test_rejects_stage6_manifest_scale_semantic_mismatch(self):
        self.stage["profiles"]["p4"]["scale_input"] = 9.0
        self._write_stage(self.stage)
        with self.assertRaises(ValueError):
            self._load()


if __name__ == "__main__":
    unittest.main()
