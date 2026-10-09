"""Strict A0004 deployment gate for the internal-FIFO P3 chain.

This module validates immutable local package files only.  It never opens the
device, loads a module, applies an overlay, contacts the board, or programs PL.
The older A0001/A0002 public loaders remain unchanged and reject this target.
"""
from __future__ import print_function

import json
import pathlib

try:
    from cnn_pipeline_v10_deployment import (
        KERNEL_RELEASE, _checked_sha, _load_platform_package, _sha)
    from cnn_pipeline_v10_p3_dma_parameters import CHAIN_CONTRACT
except ImportError:
    from .cnn_pipeline_v10_deployment import (
        KERNEL_RELEASE, _checked_sha, _load_platform_package, _sha)
    from .cnn_pipeline_v10_p3_dma_parameters import CHAIN_CONTRACT


SCHEMA = "cnn-pipeline-v10.4-p3-dma-deployment-v1"
IDENTITY = dict(core_id="0x465A5641", core_abi="0x000A0004",
                guard_caps="0x000007FF", software_uapi=10)
TARGET = dict(kernel_release=KERNEL_RELEASE,
              device="/dev/network10_v10_p3_dma",
              module="cnn_ddr_v10_p3_dma_candidate")
CHAIN_MANIFEST_SHA256 = (
    "e285a08615111752f7c71b9541267a8a1f3b7062c9a8cbb36a7bb2b5a609d5c9")
EXTRA_FILES = {"chain_parameter_manifest",
               "dma_provider_compatibility_receipt"}
EXTRA_GATES = {"p3_native_integer_exact", "p3_rtl_integer_exact",
               "p3_chain_memory_bounds_pass",
               "a0004_internal_fifo_topology_pass",
               "direct_wc_runtime_path_pass"}
DEBUG_PROFILE_GUARD_ILA = {
    "mode": "guard-ila",
    "guard_ila_count": 1,
    "pipeline_ila_count": 0,
    "debug_hub_count": 1,
    "trace_pack_present": False,
    "hls_ap_none_trace_port_count": 12,
    "platform_trace_mmio_register_count": 0,
    "trace_outputs_connected": False,
    "trace_output_transport": "ap_none",
    "mmio_trace_count": 0,
    "ltx_required": True,
}
DEBUG_PROFILE_NO_ILA = {
    "mode": "release-no-ila",
    "guard_ila_count": 0,
    "pipeline_ila_count": 0,
    "debug_hub_count": 0,
    "trace_pack_present": False,
    "hls_ap_none_trace_port_count": 12,
    "platform_trace_mmio_register_count": 0,
    "trace_outputs_connected": False,
    "trace_output_transport": "ap_none",
    "mmio_trace_count": 0,
    "ltx_required": False,
}
SUPPORTED_DEBUG_PROFILES = (DEBUG_PROFILE_GUARD_ILA, DEBUG_PROFILE_NO_ILA)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _validated_debug_profile(value):
    if not isinstance(value, dict):
        raise ValueError("A0004 debug profile is missing")
    canonical = _canonical(value)
    for expected in SUPPORTED_DEBUG_PROFILES:
        if canonical == _canonical(expected):
            return expected
    raise ValueError("A0004 debug profile is unsupported or inconsistent")


def load_v10_p3_dma_deployment(manifest_path, expected_manifest_sha256,
                               expected_release_manifest_sha256,
                               expected_chain_manifest_sha256):
    expected_chain = _checked_sha(expected_chain_manifest_sha256,
                                  "A0004 combined parameter manifest")
    if expected_chain != CHAIN_MANIFEST_SHA256:
        raise ValueError("A0004 combined parameter identity mismatch")
    path = pathlib.Path(manifest_path).resolve()
    raw = path.read_bytes()
    if _sha(raw) != _checked_sha(expected_manifest_sha256,
                                 "deployment manifest"):
        raise ValueError("A0004 deployment manifest SHA mismatch")
    try:
        preliminary = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("A0004 deployment manifest is not valid JSON")
    profile = _validated_debug_profile(preliminary.get("debug_profile"))
    excluded_files = () if profile["ltx_required"] else ("ltx",)
    loaded = _load_platform_package(
        manifest_path, expected_manifest_sha256,
        expected_release_manifest_sha256, SCHEMA, IDENTITY, TARGET,
        EXTRA_FILES, EXTRA_GATES, excluded_files)
    manifest = loaded["manifest"]
    if _canonical(manifest.get("debug_profile")) != _canonical(profile):
        raise ValueError("A0004 debug profile changed during validation")
    if (_canonical(manifest.get("chain_contract")) !=
            _canonical(CHAIN_CONTRACT)):
        raise ValueError("A0004 internal-FIFO chain contract mismatch")
    files = manifest["files"]
    if (manifest.get("chain_parameter_manifest_sha256") != expected_chain or
            files["chain_parameter_manifest"]["sha256"] != expected_chain):
        raise ValueError("A0004 combined parameter manifest binding mismatch")
    provider_path = loaded["files"]["dma_provider_compatibility_receipt"]
    provider = json.loads(provider_path.read_text(encoding="utf-8"))
    facts = provider.get("facts")
    if (provider.get("status") !=
            "CACHED_DMA_CAP_DISABLED_PROVIDER_LACKS_SYNCHRONIZE" or
            not isinstance(facts, dict) or
            facts.get("device_synchronize") is not False or
            facts.get("cached_dma_cap_expected") is not False or
            facts.get("direct_wc_affected") is not False):
        raise ValueError("A0004 DMA provider compatibility binding mismatch")
    loaded["chain_manifest_sha256"] = expected_chain
    loaded["chain_contract"] = CHAIN_CONTRACT
    loaded["cached_dma_cap_expected"] = False
    loaded["debug_profile"] = profile
    loaded["native_ila_capture_applicable"] = profile["ltx_required"]
    return loaded


__all__ = ["SCHEMA", "IDENTITY", "TARGET", "CHAIN_CONTRACT",
           "CHAIN_MANIFEST_SHA256", "EXTRA_FILES", "EXTRA_GATES",
           "DEBUG_PROFILE_GUARD_ILA", "DEBUG_PROFILE_NO_ILA",
           "load_v10_p3_dma_deployment"]
