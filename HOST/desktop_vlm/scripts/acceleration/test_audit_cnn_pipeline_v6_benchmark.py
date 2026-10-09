"""Synthetic auditor regressions; these are not board performance evidence."""
import copy
import unittest

from audit_cnn_pipeline_v6_benchmark import audit_job_order, check_completion, peak_active, union_ms
from audit_cnn_ddr_v5_benchmark import COUNTERS, STATUS_FIELDS


def interleaved_case():
    base = {key: 0 for key in STATUS_FIELDS}
    base.update(completed_frames=0xfffffff8, reset_generation=7,
                guard_status=(1 << 4) | (1 << 10) | (1 << 11), job_cycles=1000)
    previous = base
    jobs = []
    for profile in (2, 0, 1):
        for frame in range(4):
            after = dict(previous)
            for key in COUNTERS:
                after[key] = (after[key] + (1 if key == "completed_frames" else 8)) & 0xffffffff
            after["profile"] = profile
            jobs.append((len(jobs) + 1, dict(previous), after, frame))
            previous = after
    # This is the result-file ordering: all three jobs for frame0, then frame1.
    return sorted(jobs, key=lambda row: row[3]), base, previous


class CounterOrderTests(unittest.TestCase):
    def test_logical_and_hardware_generations_remain_separately_bound(self):
        unused, unused2, after = self.reset_case()
        completion = dict(after, hardware_reset_generation=after["reset_generation"],
                          generation_token=7, reset_generation=7)
        check_completion(completion, after, 7, True)
        for key in ("hardware_reset_generation", "generation_token", "reset_generation"):
            wrong = dict(completion)
            wrong[key] += 1
            with self.assertRaises(ValueError):
                check_completion(wrong, after, 7, True)

    def reset_case(self):
        jobs, before, unused = copy.deepcopy(interleaved_case())
        previous = before
        for distance, status_before, after, frame in sorted(jobs):
            status_before["reset_generation"] = previous["reset_generation"]
            after["reset_generation"] = (previous["reset_generation"] +
                                         int(status_before["profile"] != after["profile"])) & 0xffffffff
            previous = after
        return jobs, before, previous

    def test_profile_switch_resets_with_interleaved_same_profile_jobs(self):
        jobs, before, final = self.reset_case()
        self.assertEqual(len(audit_job_order(jobs, before, final, 7, 1000000, True)), 3)
        with self.assertRaises(ValueError):
            audit_job_order(jobs, before, final, 7, 1000000)

    def test_missing_extra_and_between_job_resets_rejected(self):
        for which in ("missing", "extra", "between"):
            jobs, before, final = self.reset_case()
            ordered = sorted(jobs)
            if which == "missing":
                ordered[0][2]["reset_generation"] -= 1
            elif which == "extra":
                ordered[1][2]["reset_generation"] += 1
            else:
                ordered[1][1]["reset_generation"] += 1
            with self.assertRaises(ValueError):
                audit_job_order(jobs, before, final, 7, 1000000, True)

    def test_interleaved_frames_and_counter_wrap_are_accepted(self):
        jobs, before, final = interleaved_case()
        result = audit_job_order(jobs, before, final, 7, 1000000)
        self.assertEqual(result, {"2": [1.0] * 4, "0": [1.0] * 4, "1": [1.0] * 4})

    def test_missing_and_duplicate_real_jobs_are_rejected(self):
        jobs, before, final = interleaved_case()
        for malformed in (jobs[:-1], jobs + [jobs[0]]):
            with self.assertRaises(ValueError):
                audit_job_order(malformed, before, final, 7, 1000000)

    def test_balanced_but_discontinuous_axi_counter_is_rejected(self):
        jobs, before, final = copy.deepcopy(interleaved_case())
        jobs[1][1]["ar_total"] += 1
        jobs[1][1]["rlast_total"] += 1
        with self.assertRaises(ValueError):
            audit_job_order(jobs, before, final, 7, 1000000)

    def test_completion_with_uncommitted_write_is_rejected(self):
        jobs, before, final = copy.deepcopy(interleaved_case())
        jobs[1][2]["b_total"] -= 1
        with self.assertRaises(ValueError):
            audit_job_order(jobs, before, final, 7, 1000000)

    def test_overlap_union_is_not_double_counted(self):
        self.assertEqual(union_ms([(0, 4), (2, 5), (3, 4), (7, 8)]), 6)
        self.assertEqual(peak_active([(0, 4), (2, 5), (3, 4), (7, 8)]), 3)
        self.assertEqual(peak_active([(0, 1), (1, 2)]), 1)


if __name__ == "__main__":
    unittest.main()
