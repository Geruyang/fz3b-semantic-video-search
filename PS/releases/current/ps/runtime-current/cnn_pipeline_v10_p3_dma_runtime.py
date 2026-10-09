"""Isolated A0004 P3-chain runtime adapter with fused mapped uploads.

This candidate is opt-in through an A0004 parameter object and transport.  It
does not change the A0002 default runtime or claim deployment readiness.
"""
from __future__ import print_function

import time

import numpy as np

try:
    from cnn_ddr_v10_p3_dma_runtime import PROFILE_ARENA_WORDS, profile_contract
    from cnn_pipeline_v10_p3_dma_parameters import (
        CHAIN_CONTRACT, load_v10_p3_dma_parameters)
    from cnn_pipeline_v10_p3_runtime import V10P3ChainMixin
    from cnn_v10_native_quant import V10NativeQuantWorkspace
except ImportError:
    from .cnn_ddr_v10_p3_dma_runtime import PROFILE_ARENA_WORDS, profile_contract
    from .cnn_pipeline_v10_p3_dma_parameters import (
        CHAIN_CONTRACT, load_v10_p3_dma_parameters)
    from .cnn_pipeline_v10_p3_runtime import V10P3ChainMixin
    from .cnn_v10_native_quant import V10NativeQuantWorkspace


class V10P3DmaChainMixin(V10P3ChainMixin):
    """Run A0004 with an explicit direct-WC or cached-DMA PS boundary."""

    PARAMETER_CONTRACT = CHAIN_CONTRACT
    PARAMETER_LABEL = "A0004"

    def __init__(self, *args, **kwargs):
        parameters = kwargs.pop("p3_dma_parameters", None)
        upload_backend = kwargs.pop("activation_upload_backend", "direct_wc")
        if upload_backend not in ("direct_wc", "cached_dma"):
            raise ValueError("activation_upload_backend must be direct_wc or cached_dma")
        if (not isinstance(parameters, dict) or
                parameters.get("manifest_sha256") !=
                parameters.get("chain_manifest_sha256") or
                parameters.get("contract") != self.PARAMETER_CONTRACT or
                not isinstance(parameters.get("params"), (bytes, bytearray)) or
                len(parameters["params"]) != 11280 * 16 or
                not isinstance(parameters.get("parameter_manifest_words"), tuple) or
                len(parameters["parameter_manifest_words"]) != 8):
            raise ValueError("validated %s combined parameters are required" %
                             self.PARAMETER_LABEL)
        expected_words = tuple(
            int(parameters["manifest_sha256"][index:index + 8], 16)
            for index in range(0, 64, 8))
        if parameters["parameter_manifest_words"] != expected_words:
            raise ValueError("%s combined parameter words mismatch" %
                             self.PARAMETER_LABEL)
        active = kwargs.get("active_quantized_partitions", ()) or ()
        if "n1" in active:
            raise ValueError("%s P3 chain uses n1_pl; PS-native n1 is forbidden" %
                             self.PARAMETER_LABEL)

        # Deliberately skip V10P3ChainMixin.__init__, whose strict identity is
        # A0002. Continue with the next runtime in the MRO, then install the
        # isolated A0004 resources below.
        super(V10P3ChainMixin, self).__init__(*args, **kwargs)
        self.p3_parameters = parameters
        self.activation_upload_backend = upload_backend
        self._unused_pre_a0004_arenas = {
            0: tuple(self.arena_handles[0]),
        }
        try:
            # After external stage rings were removed, A0004 normal arenas are
            # exactly the base two-slot plus residual-scratch extents. Reuse the
            # already allocated P2/P1 pairs instead of allocating and retaining
            # four duplicate arenas for the lifetime of the transport. Only the
            # smaller original P0 pair becomes unused because P0 must share P2's
            # larger pair across the atomic 2->3->0 chain.
            p2_arenas = self.arena_handles[2]
            self.arena_handles[0] = p2_arenas
            p3_handle = self.transport.alloc(11280 * 16, alignment=16)
            self.parameter_handles[3] = p3_handle
            self.transport.upload(p3_handle, 0, parameters["params"])

            native_lib = getattr(self, "mixed_native_lib", None)
            self.workspaces[2] = (
                V10NativeQuantWorkspace(2, 64, 64, native_lib=native_lib),
                V10NativeQuantWorkspace(2, 64, 64, native_lib=native_lib),
            )
            self._p1_input_workspaces = (
                V10NativeQuantWorkspace(1, 256, 16, native_lib=native_lib),
                V10NativeQuantWorkspace(1, 256, 16, native_lib=native_lib),
            )
            self._p1_output_codes = (
                np.empty((16, 256, 16), dtype="<i2"),
                np.empty((16, 256, 16), dtype="<i2"),
            )
            self._p3_output_codes = (
                np.empty((32, 128, 32), dtype="<i2"),
                np.empty((32, 128, 32), dtype="<i2"),
            )
        except BaseException:
            self._close_owned_resources()
            raise

    def _quantize_upload_lane(self, handle, value, scale, workspace, label):
        if self.activation_upload_backend == "cached_dma":
            upload = getattr(self.transport, "quantize_upload_cached_dma", None)
            if not callable(upload):
                raise RuntimeError("A0004 transport lacks cached-DMA quantization")
            evidence = upload(handle, 0, value, scale, workspace, label)
            if (not isinstance(evidence, dict) or
                    evidence.get("backend") != "cached_dma" or
                    evidence.get("direct_target") is not False or
                    not isinstance(evidence.get("driver_dma_ns"), int) or
                    evidence.get("driver_dma_ns") < 0):
                raise RuntimeError("A0004 cached-DMA evidence is invalid")
            return evidence
        upload = getattr(self.transport, "quantize_upload_into", None)
        if not callable(upload):
            raise RuntimeError("A0004 transport lacks fused mapped quantization")
        evidence = upload(handle, 0, value, scale, workspace, label)
        if (not isinstance(evidence, dict) or
                evidence.get("direct_target") is not True or
                evidence.get("backend") != "wc_mmap_direct_quantize"):
            raise RuntimeError("A0004 direct-WC evidence is invalid")
        return evidence

    def _upload_pair(self, handle_a, handle_b, left, right, scale,
                     work_a, work_b, label, expected_bytes):
        started = time.perf_counter()
        lane_a = self._quantize_upload_lane(
            handle_a, left, scale, work_a, label + " A")
        lane_b = self._quantize_upload_lane(
            handle_b, right, scale, work_b, label + " B")
        total_ms = (time.perf_counter() - started) * 1000.0
        for lane, evidence in (("A", lane_a), ("B", lane_b)):
            if evidence.get("bytes") != expected_bytes:
                raise RuntimeError("A0004 lane %s byte count mismatch" % lane)
        conversion_ms = sum(float(item.get("conversion_ms", 0.0))
                            for item in (lane_a, lane_b))
        dma_ioctl_wall_ms = sum(float(item.get("dma_ioctl_wall_ms", 0.0))
                                for item in (lane_a, lane_b))
        transfer_ms = sum(float(item.get(
            "transfer_ms", item.get("dma_ioctl_wall_ms", 0.0)))
            for item in (lane_a, lane_b))
        return {
            "backend": ("cached_dma" if self.activation_upload_backend ==
                        "cached_dma" else "wc_mmap_direct_quantize"),
            "direct_target": self.activation_upload_backend == "direct_wc",
            "conversion_ms": conversion_ms,
            "transfer_ms": transfer_ms,
            "dma_ioctl_wall_ms": dma_ioctl_wall_ms,
            "driver_dma_ns": sum(int(item.get("driver_dma_ns", 0))
                                 for item in (lane_a, lane_b)),
            "combined_quantize_upload_ms": total_ms,
            "lanes": {"A": lane_a, "B": lane_b},
        }

    def _upload_p2_chain_inputs(self, handles_a, handles_b, left, right,
                                scale, work_a, work_b):
        evidence = self._upload_pair(
            handles_a, handles_b, left, right, scale, work_a, work_b,
            "profile 2", 64 * 64 * 64 * 2)
        return (evidence["conversion_ms"], evidence["dma_ioctl_wall_ms"]
                if evidence["backend"] == "cached_dma"
                else evidence["transfer_ms"], evidence)

    def _run_profile(self, profile, left, right):
        """Use the same direct-target boundary for N3 -> profile1."""
        if profile != 1:
            return super(V10P3DmaChainMixin, self)._run_profile(
                profile, left, right)
        blocks = 20
        cfg = profile_contract(profile, blocks)
        scale = self.contract["profiles"][profile]["input_scale"]
        arena_left, arena_right = self.arena_handles[profile]
        work_left, work_right = self._p1_input_workspaces
        total_started = time.perf_counter()
        upload_evidence = self._upload_pair(
            arena_left, arena_right, left, right, scale, work_left, work_right,
            "profile 1", 256 * 16 * 16 * 2)
        started = time.perf_counter()
        descriptor = self.transport.submit(
            profile, blocks, self.parameter_handles[profile],
            arena_left, arena_right)
        submit_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        completion = self.transport.wait_complete(profile, self.timeout_s)
        wait_ms = (time.perf_counter() - started) * 1000.0
        q_left, q_right = self._p1_output_codes
        started = time.perf_counter()
        self._download_array(arena_left, cfg["output_offset_bytes"], q_left)
        self._download_array(arena_right, cfg["output_offset_bytes"], q_right)
        download_ms = (time.perf_counter() - started) * 1000.0
        output_scale = self.contract["profiles"][profile]["output_scale"]
        dequant_left, dequant_right = self.workspaces[profile]
        started = time.perf_counter()
        out_left = dequant_left.dequantize_hcw_to_chw(
            q_left, output_scale, "profile 1 A").copy()
        out_right = dequant_right.dequantize_hcw_to_chw(
            q_right, output_scale, "profile 1 B").copy()
        dequantize_ms = (time.perf_counter() - started) * 1000.0
        return out_left, out_right, {
            "profile": profile, "block_count": blocks,
            "descriptor": descriptor, "completion": completion,
            "timing": {
                "quantize_ms": upload_evidence["conversion_ms"],
                "upload_ms": (upload_evidence["dma_ioctl_wall_ms"]
                              if upload_evidence["backend"] == "cached_dma"
                              else upload_evidence["transfer_ms"]),
                "quantize_upload": upload_evidence,
                "submit_ms": submit_ms, "wait_ms": wait_ms,
                "download_ms": download_ms,
                "dequantize_ms": dequantize_ms,
                "pl_window_wall_ms": (
                    time.perf_counter() - total_started) * 1000.0,
            },
        }


__all__ = ["V10P3DmaChainMixin", "load_v10_p3_dma_parameters"]
