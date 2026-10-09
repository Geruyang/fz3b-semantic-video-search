"""P3 combined-parameter gate and whole-region PL-chain runtime mixin.

The mixin owns the profile-2/3/0 submit/wait sequence within one PL scheduler
call and reuses the profile-2 activation arenas. Host tests exercise the same
transport API with an in-memory mock; this module does not claim target runs.
"""
from __future__ import print_function

import time

import numpy as np

try:
    from cnn_pipeline_v10_p3_chain_parameters import load_v10_p3_parameters
except ImportError:
    from .cnn_pipeline_v10_p3_chain_parameters import load_v10_p3_parameters


P3_PIPELINE_STAGES = (
    ("PS", "stem-prefix"), ("PL", "n0-n1-n2"),
    ("PS", "network3-bridge"), ("PL", 1), ("PS", "suffix"),
)


class V10P3ChainMixin(object):
    """Replace N0/PS-N1/N2 with a single profile-2/3/0 PL owner call."""

    PIPELINE_STAGES = P3_PIPELINE_STAGES

    def __init__(self, *args, **kwargs):
        parameters = kwargs.pop("p3_parameters", None)
        if (not isinstance(parameters, dict) or
                parameters.get("manifest_sha256") != parameters.get("chain_manifest_sha256") or
                not isinstance(parameters.get("params"), (bytes, bytearray)) or
                len(parameters["params"]) != 11280 * 16 or
                not isinstance(parameters.get("parameter_manifest_words"), tuple) or
                len(parameters["parameter_manifest_words"]) != 8):
            raise ValueError("validated combined P3 parameters are required")
        expected_words = tuple(int(parameters["manifest_sha256"][i:i+8], 16)
                               for i in range(0, 64, 8))
        try:
            from cnn_pipeline_v10_chain_deployment import CHAIN_CONTRACT
        except ImportError:
            from .cnn_pipeline_v10_chain_deployment import CHAIN_CONTRACT
        if (parameters["parameter_manifest_words"] != expected_words or
                parameters.get("contract") != CHAIN_CONTRACT):
            raise ValueError("P3 manifest words or deployment chain contract mismatch")
        active_requested = kwargs.get("active_quantized_partitions", ())
        if active_requested is None:
            active_requested = ()
        if "n1" in active_requested:
            raise ValueError("P3 chain uses n1_pl; PS-native n1 must remain inactive")
        super(V10P3ChainMixin, self).__init__(*args, **kwargs)
        self.p3_parameters = parameters
        self._unused_original_profile0_arenas = tuple(self.arena_handles[0])
        try:
            # FREE requires global QUIESCE and would make this live transport
            # unusable. Retain the original P0 pair until terminal transport
            # close; the profile2 pair becomes the shared [2,3,0] arena pair.
            self.arena_handles[0] = self.arena_handles[2]
            p3_handle = self.transport.alloc(11280 * 16, alignment=16)
            self.parameter_handles[3] = p3_handle
            self.transport.upload(p3_handle, 0, parameters["params"])
            self._p3_output_codes = (
                np.empty((32, 128, 32), dtype="<i2"),
                np.empty((32, 128, 32), dtype="<i2"))
        except BaseException:
            self._close_owned_resources()
            raise

    @staticmethod
    def _validate_chain_evidence(evidence):
        if not isinstance(evidence, dict) or evidence.get("profiles") != [2, 3, 0]:
            raise ValueError("P3 transport must report profiles [2, 3, 0]")
        jobs = evidence.get("jobs")
        if not isinstance(jobs, list) or len(jobs) != 3:
            raise ValueError("P3 transport must report three job completions")
        for expected_profile, job in zip((2, 3, 0), jobs):
            if (not isinstance(job, dict) or isinstance(job.get("profile"), bool) or
                    not isinstance(job.get("profile"), int) or
                    job.get("profile") != expected_profile):
                raise ValueError("P3 chain job order/profile mismatch")
            completion = job.get("completion")
            if not isinstance(completion, dict):
                raise ValueError("P3 chain completion evidence is missing")
            protocol_error = completion.get("protocol_error")
            guard_errors = completion.get("guard_error_flags")
            if (isinstance(protocol_error, bool) or not isinstance(protocol_error, int) or
                    protocol_error != 0 or isinstance(guard_errors, bool) or
                    not isinstance(guard_errors, int) or guard_errors != 0):
                raise ValueError("P3 chain completion has protocol or guard errors")
            if expected_profile == 3:
                if (isinstance(completion.get("valid_slot"), bool) or
                        completion.get("valid_slot") != 0 or
                        isinstance(completion.get("output_valid_words"), bool) or
                        completion.get("output_valid_words") != 16384 or
                        isinstance(completion.get("output_valid_bytes"), bool) or
                        completion.get("output_valid_bytes") != 262144 or
                        completion.get("only_valid_region") is not True):
                    raise ValueError("P3 completion must validate only slot0 first 16384 words")
        return jobs

    def _upload_p2_chain_inputs(self, handles_a, handles_b, left, right,
                                scale, work_a, work_b):
        """Prepare profile-2 inputs; isolated transports may fuse this step."""
        stage_started = time.perf_counter()
        q_a = work_a.quantize_chw_to_hcw(left, scale, "profile 2 A")
        q_b = work_b.quantize_chw_to_hcw(right, scale, "profile 2 B")
        quantize_ms = (time.perf_counter() - stage_started) * 1000.0
        stage_started = time.perf_counter()
        self._upload_array(handles_a, q_a)
        self._upload_array(handles_b, q_b)
        upload_ms = (time.perf_counter() - stage_started) * 1000.0
        return quantize_ms, upload_ms, {
            "backend": "workspace_then_transport_upload",
            "direct_target": False,
        }

    def _run_pl_stage(self, key, left, right):
        if key != "n0-n1-n2":
            return super(V10P3ChainMixin, self)._run_pl_stage(key, left, right)
        for name, value in (("A", left), ("B", right)):
            if (not isinstance(value, np.ndarray) or
                    value.shape != (1, 64, 64, 64) or
                    value.dtype != np.dtype("<f4") or
                    not value.flags.c_contiguous):
                raise ValueError("P3 chain %s input must be contiguous N0 FP32" % name)
        # `_upload_p2_chain_inputs` always reaches the exact quantization
        # workspace, which owns the finite-value validation immediately before
        # reading each lane. Avoid scanning both full tensors a second time here.
        total_started = time.perf_counter()
        profiles = []
        jobs = []
        handles_a, handles_b = self.arena_handles[2]
        if self.arena_handles[0] != (handles_a, handles_b):
            raise RuntimeError("P3 chain profile0 arenas are not shared with profile2")

        # Profile 2 quantizes the stem output once. The resulting HCW INT16
        # stays in slot0 across the P3 job and directly feeds profile 0.
        p2_blocks = 4
        p2_scale = self.contract["profiles"][2]["input_scale"]
        work_a, work_b = self.workspaces[2]
        quantize_ms, upload_ms, upload_evidence = self._upload_p2_chain_inputs(
            handles_a, handles_b, left, right, p2_scale, work_a, work_b)

        for profile, blocks, parameter_handle in (
                (2, p2_blocks, self.parameter_handles[2]),
                (3, 1, self.parameter_handles[3]),
                (0, 12, self.parameter_handles[0])):
            started = time.perf_counter()
            descriptor = self.transport.submit(profile, blocks, parameter_handle,
                                               handles_a, handles_b)
            submit_ms = (time.perf_counter() - started) * 1000.0
            started = time.perf_counter()
            raw_completion = self.transport.wait_complete(profile, self.timeout_s)
            wait_ms = (time.perf_counter() - started) * 1000.0
            completion = self._normalize_completion(profile, raw_completion)
            profiles.append(profile)
            jobs.append({"profile": profile, "block_count": blocks,
                         "descriptor": descriptor,
                         "driver_completion_raw": dict(raw_completion),
                         "completion": completion,
                         "timing": {"submit_ms": submit_ms, "wait_ms": wait_ms}})

        # P3 profile 3 marks exactly the first 16384 words in slot0 valid; P0
        # consumes that prefix. P0 has an even block count, so its own output
        # also lands at offset zero.
        p0_cfg = self._profile_cfg(0, 12)
        out_a, out_b = self._p3_output_codes
        stage_started = time.perf_counter()
        self._download_array(handles_a, p0_cfg["output_offset_bytes"], out_a)
        self._download_array(handles_b, p0_cfg["output_offset_bytes"], out_b)
        download_ms = (time.perf_counter() - stage_started) * 1000.0
        output_scale = self.contract["profiles"][0]["output_scale"]
        out_work_a, out_work_b = self.workspaces[0]
        stage_started = time.perf_counter()
        out_left = out_work_a.dequantize_hcw_to_chw(
            out_a, output_scale, "profile 0 A").copy()
        out_right = out_work_b.dequantize_hcw_to_chw(
            out_b, output_scale, "profile 0 B").copy()
        dequantize_ms = (time.perf_counter() - stage_started) * 1000.0
        evidence = {"profiles": profiles, "jobs": jobs,
            "timing": {"quantize_ms": quantize_ms, "upload_ms": upload_ms,
                "profile2_input_upload": upload_evidence,
                "profile_submit_wait_ms": [job["timing"] for job in jobs],
                "p3_intermediate_and_gelu_reload": {
                    "intermediate_word_range": "slot1[32768,49152)",
                    "intermediate_byte_range": "slot1[524288,786432)",
                    "gelu_ram_reloaded_between_dw_and_pw": True},
                "download_ms": download_ms, "dequantize_ms": dequantize_ms,
                "pl_window_wall_ms": (time.perf_counter() - total_started) * 1000.0},
            "active_partition": "n1_pl",
            "p3_manifest_sha256": self.p3_parameters["p3_manifest_sha256"],
            "chain_manifest_sha256": self.p3_parameters["chain_manifest_sha256"],
            "p3_output_valid_region": {"slot": 0, "word_range": "slot0[0,16384)",
                                        "byte_range": "slot0[0,262144)"}}
        self._validate_chain_evidence(evidence)
        return out_left, out_right, evidence

    @staticmethod
    def _profile_cfg(profile, blocks):
        try:
            from cnn_ddr_v10_runtime import profile_contract
        except ImportError:
            from .cnn_ddr_v10_runtime import profile_contract
        return profile_contract(profile, blocks)

    @staticmethod
    def _normalize_completion(profile, completion):
        if not isinstance(completion, dict):
            raise ValueError("profile %d completion is malformed" % profile)
        result = {}
        completed_profile = completion.get("profile")
        if (isinstance(completed_profile, bool) or
                not isinstance(completed_profile, int) or completed_profile != profile):
            raise ValueError("profile %d completion identity mismatch" % profile)
        # wait_complete() is the transport's acceptance gate and raises on
        # protocol/guard errors. Normalize omitted legacy status fields while
        # preserving every raw status value for the receipt.
        protocol_error = completion.get("protocol_error", 0)
        guard_errors = completion.get("guard_error_flags", 0)
        if (isinstance(protocol_error, bool) or not isinstance(protocol_error, int) or
                protocol_error != 0 or isinstance(guard_errors, bool) or
                not isinstance(guard_errors, int) or guard_errors != 0):
            raise ValueError("profile %d completion is not protocol/guard clean" % profile)
        result.update(protocol_error=0, guard_error_flags=0,
                      wait_complete_accepted=True,
                      validity_source="validated transport wait_complete")
        if profile == 3:
            result.update(valid_slot=0, output_valid_words=16384,
                          output_valid_bytes=262144, only_valid_region=True,
                          validity_source="ABI10.2 P3 completion contract")
        return result


__all__ = ["P3_PIPELINE_STAGES", "V10P3ChainMixin", "load_v10_p3_parameters"]
