"""Opt-in three-owner live scheduler for A0004 PS/PL overlap.

The frozen single-PS runtime remains the default.  This candidate gives stem
and network3 to one PS owner, suffix to a second PS owner, and all accelerator
calls to the existing single PL owner.  A client is never used by two owners.
"""
from __future__ import print_function

import concurrent.futures
import copy
import threading
import time

try:
    from cnn_pipeline_v10_live_runtime import V10LiveRuntime
except ImportError:
    from .cnn_pipeline_v10_live_runtime import V10LiveRuntime


class _OwnerActivity(object):
    """Integrate owner unions at state transitions without retaining spans."""

    OWNERS = ("PS_FRONT", "PS_SUFFIX", "PL")

    def __init__(self):
        self._lock = threading.Lock()
        self._active = dict((owner, False) for owner in self.OWNERS)
        self._last = time.perf_counter()
        self._totals = dict(
            ps_front_busy_ms=0.0, ps_suffix_busy_ms=0.0, pl_busy_ms=0.0,
            ps_union_busy_ms=0.0, front_suffix_overlap_ms=0.0,
            cross_pair_ps_pl_overlap_ms=0.0, all_owner_union_ms=0.0)

    def _advance(self, now):
        elapsed = (now - self._last) * 1000.0
        front = self._active["PS_FRONT"]
        suffix = self._active["PS_SUFFIX"]
        pl = self._active["PL"]
        if front:
            self._totals["ps_front_busy_ms"] += elapsed
        if suffix:
            self._totals["ps_suffix_busy_ms"] += elapsed
        if pl:
            self._totals["pl_busy_ms"] += elapsed
        if front or suffix:
            self._totals["ps_union_busy_ms"] += elapsed
        if front and suffix:
            self._totals["front_suffix_overlap_ms"] += elapsed
        if pl and (front or suffix):
            self._totals["cross_pair_ps_pl_overlap_ms"] += elapsed
        if front or suffix or pl:
            self._totals["all_owner_union_ms"] += elapsed
        self._last = now

    def enter(self, owner):
        with self._lock:
            if owner not in self._active or self._active[owner]:
                raise RuntimeError("split owner was entered twice: %s" % owner)
            self._advance(time.perf_counter())
            self._active[owner] = True

    def leave(self, owner):
        with self._lock:
            if owner not in self._active or not self._active[owner]:
                raise RuntimeError("split owner leave without enter: %s" % owner)
            self._advance(time.perf_counter())
            self._active[owner] = False

    def snapshot(self):
        with self._lock:
            self._advance(time.perf_counter())
            return dict(self._totals)


class V10SplitPsLiveRuntime(V10LiveRuntime):
    """Explicit opt-in scheduler with PS_FRONT, PS_SUFFIX and PL owners."""

    @staticmethod
    def _stage_owner(entry):
        owner, key = entry
        if owner == "PL":
            return "PL"
        if owner != "PS":
            raise ValueError("split scheduler only accepts PS/PL pipeline stages")
        return "PS_SUFFIX" if key == "suffix" else "PS_FRONT"

    def _split_ps_pair(self, context, stage, origin):
        result = self._ps_pair(context, stage, origin)
        span = result[-1]
        span["owner"] = self._stage_owner(self._pipeline_stages[stage])
        return result

    def _iter_live(self, items, max_in_flight, record_history):
        origin = time.perf_counter()
        active, ready = {}, {}
        owners = ("PS_SUFFIX", "PL", "PS_FRONT")
        pending = dict((owner, []) for owner in owners)
        running = {}
        timeline, timings = [], []
        busy_ms = dict((owner, 0.0) for owner in owners)
        activity = _OwnerActivity()
        exhausted, last_id = False, -1
        next_index = next_emit = peak = completed_pairs = completed_frames = emitted = 0
        status = "FAILED_DRAINED"

        def take():
            nonlocal last_id
            frame_id, value = self._parse_item(next(source))
            if frame_id <= last_id:
                raise ValueError("live frame IDs must be unique and strictly increasing")
            last_id = frame_id
            return frame_id, self._finite(
                value, (1, 3, 256, 256), "stream input").copy()

        def admit():
            nonlocal exhausted, next_index, peak
            while not exhausted and len(active) + len(ready) < max_in_flight:
                try:
                    first = take()
                except StopIteration:
                    exhausted = True
                    break
                try:
                    second = take()
                except StopIteration:
                    second, exhausted = (None, first[1]), True
                context = dict(
                    index=next_index, first_id=first[0], second_id=second[0],
                    left=first[1], right=second[1], stage=0,
                    admitted_ms=(time.perf_counter() - origin) * 1000.0,
                    ps_events=[], pl_events=[])
                active[next_index] = context
                pending["PS_FRONT"].append(context)
                next_index += 1
                peak = max(peak, len(active) + len(ready))

        def finish(context):
            nonlocal completed_pairs, completed_frames
            ended = (time.perf_counter() - origin) * 1000.0
            shadow = context["second_id"] is None
            timing = dict(
                schedule="incremental_bounded_split_ps_pl",
                frame_ids=[context["first_id"], context["second_id"]],
                real_frame_count=1 if shadow else 2,
                hardware_lane_frame_count=2,
                shadow_counts_as_real_throughput=False,
                ps_events=context["ps_events"], pl_events=context["pl_events"],
                admitted_ms=context["admitted_ms"], completed_ms=ended,
                pair_wall_ms=ended - context["admitted_ms"])
            frames = []
            for frame_id, partner, value in (
                    (context["first_id"], context["second_id"], context["left"]),
                    (context["second_id"], context["first_id"], context["right"])):
                if frame_id is not None:
                    frames.append(dict(
                        frame_id=frame_id, paired_with=partner,
                        shadow_partner_used=shadow,
                        features=value.reshape(512).copy()))
            ready[context["index"]] = frames, timing
            if record_history:
                timings.append(timing)
            completed_pairs += 1
            completed_frames += len(frames)
            del active[context["index"]]
            context["left"] = context["right"] = None

        def dispatch(pools):
            for owner in owners:
                if owner in running or not pending[owner]:
                    continue
                pending[owner].sort(key=lambda context: (
                    -context["stage"], context["index"]))
                context = pending[owner].pop(0)
                function = self._pl_pair if owner == "PL" else self._split_ps_pair
                running[owner] = (
                    pools[owner].submit(
                        invoke, owner, function, context,
                        context["stage"], origin), context)

        def invoke(owner, function, context, stage, started):
            activity.enter(owner)
            try:
                return function(context, stage, started)
            finally:
                activity.leave(owner)

        try:
            source = iter(items)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as suffix_pool:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pl_pool:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as front_pool:
                        pools = {"PS_SUFFIX": suffix_pool, "PL": pl_pool,
                                 "PS_FRONT": front_pool}
                        admit()
                        while active or ready:
                            dispatch(pools)
                            while next_emit in ready:
                                frames, timing = ready[next_emit]
                                for frame in frames:
                                    result = dict(frame)
                                    result["pair_timing"] = copy.deepcopy(timing)
                                    result["pl_completions"] = result[
                                        "pair_timing"]["pl_events"]
                                    delivered = (
                                        time.perf_counter() - origin) * 1000.0
                                    result["delivery_ms"] = delivered
                                    result["completion_to_delivery_ms"] = (
                                        delivered - timing["completed_ms"])
                                    emitted += 1
                                    yield result
                                del ready[next_emit]
                                next_emit += 1
                            admit()
                            dispatch(pools)
                            if not running:
                                if active or ready:
                                    raise RuntimeError(
                                        "V10 split scheduler has no runnable stage")
                                break
                            done, unused = concurrent.futures.wait(
                                [entry[0] for entry in running.values()],
                                return_when=concurrent.futures.FIRST_COMPLETED)
                            for owner in owners:
                                if (owner not in running or
                                        running[owner][0] not in done):
                                    continue
                                future, context = running.pop(owner)
                                left, right, evidence, span = future.result()
                                context["left"], context["right"] = left, right
                                busy_ms[owner] += span["end_ms"] - span["start_ms"]
                                if record_history:
                                    timeline.append(span)
                                if owner == "PL":
                                    context["pl_events"].append(evidence)
                                else:
                                    context["ps_events"].extend(evidence)
                                context["stage"] += 1
                                if context["stage"] == len(self._pipeline_stages):
                                    finish(context)
                                else:
                                    next_owner = self._stage_owner(
                                        self._pipeline_stages[context["stage"]])
                                    pending[next_owner].append(context)
            status = "COMPLETED"
        except GeneratorExit:
            status = "CANCELLED_DRAINED"
            self._stream_failed = True
            raise
        except BaseException:
            self._stream_failed = True
            raise
        finally:
            cancelled = status == "CANCELLED_DRAINED"
            drained_errors = []
            for owner, (future, context) in running.items():
                try:
                    unused_left, unused_right, unused_evidence, span = future.result()
                    busy_ms[owner] += span["end_ms"] - span["start_ms"]
                    if record_history:
                        timeline.append(span)
                except BaseException as error:
                    drained_errors.append(dict(
                        owner=owner, pair_index=context["index"],
                        error="%s: %s" % (type(error).__name__, error)))
            if drained_errors:
                status = "FAILED_DRAINED"
                self._stream_failed = True
            wall_ms = (time.perf_counter() - origin) * 1000.0
            ps_busy = busy_ms["PS_FRONT"] + busy_ms["PS_SUFFIX"]
            overlap = activity.snapshot()
            self.last_run_summary = dict(
                schedule="incremental_bounded_split_ps_pl", status=status,
                pipeline_stages=list(self._pipeline_stages),
                execution_owners=list(owners),
                pair_count=completed_pairs,
                completed_pair_count=completed_pairs,
                real_frame_count=completed_frames,
                emitted_frame_count=emitted,
                pair_timings=timings, timeline=timeline,
                record_history=record_history,
                peak_in_flight_pairs=peak,
                max_in_flight_pairs=max_in_flight,
                admitted_pair_count=next_index,
                ps_workers=2, ps_front_workers=1, ps_suffix_workers=1,
                pl_workers=1, ps_worker_busy_ms=ps_busy,
                ps_front_worker_busy_ms=busy_ms["PS_FRONT"],
                ps_suffix_worker_busy_ms=busy_ms["PS_SUFFIX"],
                pl_worker_busy_ms=busy_ms["PL"],
                overlap=overlap,
                execution_ms=wall_ms, workers_drained=True,
                drained_call_errors=drained_errors,
                fps_including_fill_and_drain=(
                    emitted * 1000.0 / wall_ms if emitted else 0),
                elapsed_includes_consumer_pauses=True,
                shadow_counts_as_real_throughput=False)
            if cancelled and drained_errors:
                raise RuntimeError(
                    "worker failed while draining cancelled stream: %s" %
                    drained_errors[0]["error"])


__all__ = ["V10SplitPsLiveRuntime"]
