"""Offline dependency model for adjacent-block v7 stripe scheduling.

The class models proofs the future runtime must preserve.  It does not issue
ioctls and is intentionally separate from every v5/v6 runtime.
"""

from collections import namedtuple

import cnn_shared_v7_contract as contract


StripeJob = namedtuple("StripeJob", [
    "frame_id", "block_index", "profile", "start_row", "row_count",
    "core_id", "scratch_id", "arena_id", "src_words", "dst_words",
])


class StripeScheduler(object):
    def __init__(self):
        self._next_token = 1
        self._active = {}
        self._committed = {}

    @staticmethod
    def _target_span(job):
        geometry = contract.stripe_geometry(job.profile, job.start_row, job.row_count)
        start = int(job.dst_words) + geometry["start_row"] * geometry["row_words"]
        end = start + geometry["row_count"] * geometry["row_words"]
        return start, end

    @staticmethod
    def _source_span(job):
        geometry = contract.stripe_geometry(job.profile, job.start_row, job.row_count)
        start = (int(job.src_words) +
                 geometry["source_start_row"] * geometry["row_words"])
        end = start + geometry["source_row_count"] * geometry["row_words"]
        return start, end

    @staticmethod
    def _logical_key(job):
        return (job.frame_id, int(job.profile), int(job.block_index))

    @staticmethod
    def _ranges_overlap(left, right):
        return left[0] < right[1] and right[0] < left[1]

    def _ready(self, job, geometry):
        block = int(job.block_index)
        if block < 0:
            raise ValueError("block_index must be nonnegative")
        if block == 0:
            return True
        previous = self._committed.get(
            (job.frame_id, int(job.profile), block - 1), set())
        begin = geometry["source_start_row"]
        end = begin + geometry["source_row_count"]
        return all(row in previous for row in range(begin, end))

    def dispatch(self, job):
        geometry = contract.stripe_geometry(job.profile, job.start_row, job.row_count)
        if not self._ready(job, geometry):
            raise RuntimeError("predecessor rows including halo4 are not committed")
        logical_key = self._logical_key(job)
        target_rows = set(range(int(job.start_row),
                                int(job.start_row) + int(job.row_count)))
        if target_rows.intersection(self._committed.get(logical_key, set())):
            raise RuntimeError("logical output rows are already committed")
        for active in self._active.values():
            other = active["job"]
            if self._logical_key(other) == logical_key:
                other_rows = set(range(int(other.start_row),
                                       int(other.start_row) + int(other.row_count)))
                if target_rows.intersection(other_rows):
                    raise RuntimeError("logical output rows already have an active owner")
            if other.core_id == job.core_id:
                raise RuntimeError("core already owns an active stripe")
            if other.scratch_id == job.scratch_id:
                raise RuntimeError("scratch lease is not private")
            if other.arena_id == job.arena_id:
                new_destination = self._target_span(job)
                new_source = self._source_span(job)
                if self._ranges_overlap(active["destination_span"],
                                        new_destination):
                    raise RuntimeError("destination write spans overlap")
                if self._ranges_overlap(active["source_span"], new_destination):
                    raise RuntimeError(
                        "destination write overlaps active source read span")
                if self._ranges_overlap(active["destination_span"], new_source):
                    raise RuntimeError(
                        "source read overlaps active destination write span")
        token = self._next_token
        self._next_token += 1
        self._active[token] = {
            "job": job,
            "geometry": geometry,
            "destination_span": self._target_span(job),
            "source_span": self._source_span(job),
        }
        return token

    def complete(self, token, success):
        if token not in self._active:
            raise RuntimeError("completion token is not active")
        active = self._active.pop(token)
        if success:
            job = active["job"]
            key = self._logical_key(job)
            rows = self._committed.setdefault(key, set())
            begin = int(job.start_row)
            rows.update(range(begin, begin + int(job.row_count)))
        return active["job"]

    def committed_intervals(self, frame_id, profile, block_index):
        rows = sorted(self._committed.get(
            (frame_id, int(profile), int(block_index)), set()))
        if not rows:
            return []
        result = []
        begin = previous = rows[0]
        for row in rows[1:]:
            if row != previous + 1:
                result.append((begin, previous + 1))
                begin = row
            previous = row
        result.append((begin, previous + 1))
        return result

    def active_jobs(self):
        return {token: value["job"] for token, value in self._active.items()}

