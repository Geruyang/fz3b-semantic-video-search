"""Bounded cross-pair PS/PL overlap, using the unchanged V10 transport.

One worker owns all PS clients, and one worker owns all PL calls/arenas. The
caller retains exclusive ownership of the runtime until run() returns. Python
3.6 is supported for the board. No driver, arithmetic, or clock changes.
"""
import concurrent.futures
import threading
import time

try:
    from cnn_pipeline_v10_paired_runtime import V10PairedNormalRuntime
except ImportError:
    from .cnn_pipeline_v10_paired_runtime import V10PairedNormalRuntime


_PS_NAMES = {0: 'stem-prefix', 2: 'network1-bridge',
             4: 'network3-bridge', 6: 'suffix'}
_PL_PROFILES = {1: 2, 3: 0, 5: 1}


class V10StreamRuntime(V10PairedNormalRuntime):
    def __init__(self, *args, **kwargs):
        self._execution_lock = threading.Lock()
        self._stream_failed = False
        super(V10StreamRuntime, self).__init__(*args, **kwargs)

    def _ps_pair(self, context, stage, origin):
        started = time.perf_counter()
        name = _PS_NAMES[stage]
        left, event_a = self._client_timed(name, context['left'])
        left = left.copy()
        event_a['lane'] = 'A'
        events = [event_a]
        if context['second_id'] is None:
            # Deterministic inference of the same image need not run twice.
            # PL still receives two valid independent arena addresses.
            right = left
        else:
            right, event_b = self._client_timed(name, context['right'])
            event_b['lane'] = 'B'
            events.append(event_b)
        # A client may reuse its response buffers on its next invocation.
        # Detach before handing outputs to another worker / reusing the client.
        right = right.copy()
        ended = time.perf_counter()
        return left, right, events, {
            'owner': 'PS', 'stage': name, 'pair_index': context['index'],
            'start_ms': (started - origin) * 1000,
            'end_ms': (ended - origin) * 1000,
        }

    def _pl_pair(self, context, stage, origin):
        started = time.perf_counter()
        result = self._run_profile(_PL_PROFILES[stage], context['left'], context['right'])
        ended = time.perf_counter()
        return result + ({
            'owner': 'PL', 'stage': _PL_PROFILES[stage],
            'pair_index': context['index'],
            'start_ms': (started - origin) * 1000,
            'end_ms': (ended - origin) * 1000,
        },)

    def run(self, items, max_in_flight=3):
        """Process a finite iterable, retaining at most max_in_flight pairs.

        Input IDs must be unique. On any error, dispatch stops and active worker
        calls drain before the error escapes; only then may close() quiesce and
        release driver handles. Transport and PS clients provide call timeouts.
        The returned feature list is ordered and retained, unlike activations.
        """
        if isinstance(max_in_flight, bool) or max_in_flight not in (1, 2, 3, 4):
            raise ValueError('max_in_flight must be an integer from 1 to 4')
        if not isinstance(max_in_flight, int):
            raise ValueError('max_in_flight must be an integer')
        if not self._execution_lock.acquire(False):
            raise RuntimeError('V10 stream runtime is already running')
        try:
            if self.closed:
                raise RuntimeError('V10 runtime is closed')
            if self._stream_failed:
                raise RuntimeError('V10 stream failed; close is required before a new runtime')
            return self._run_stream(items, max_in_flight)
        finally:
            self._execution_lock.release()

    def _run_stream(self, items, max_in_flight):
        origin = time.perf_counter()
        source = iter(items)
        exhausted = False
        seen = set()
        active = {}
        completed = {}
        timings = {}
        timeline = []
        next_index = 0
        peak_active = 0
        pending = {'PS': [], 'PL': []}
        running = {}

        def take():
            item = self._parse_item(next(source))
            if item[0] in seen:
                raise ValueError('frame IDs must be unique')
            seen.add(item[0])
            # Snapshot before asking a producer for its next item: capture and
            # decoding generators commonly refill one mutable image buffer.
            return item[0], self._finite(item[1], (1, 3, 256, 256), 'stream input').copy()

        def admit():
            nonlocal exhausted, next_index, peak_active
            while not exhausted and len(active) < max_in_flight:
                try:
                    first = take()
                except StopIteration:
                    exhausted = True
                    break
                try:
                    second = take()
                except StopIteration:
                    second = (None, first[1])
                    exhausted = True
                context = dict(index=next_index, first_id=first[0], second_id=second[0],
                               left=first[1], right=second[1], stage=0,
                               admitted_ms=(time.perf_counter()-origin)*1000,
                               ps_events=[], pl_events=[])
                active[next_index] = context
                pending['PS'].append(context)
                next_index += 1
                peak_active = max(peak_active, len(active))

        def finish(context):
            end_ms = (time.perf_counter() - origin) * 1000
            shadow = context['second_id'] is None
            timing = dict(schedule='bounded_cross_pair_ps_pl',
                          frame_ids=[context['first_id'], context['second_id']],
                          real_frame_count=1 if shadow else 2,
                          hardware_lane_frame_count=2,
                          shadow_counts_as_real_throughput=False,
                          ps_events=context['ps_events'], pl_events=context['pl_events'],
                          admitted_ms=context['admitted_ms'], completed_ms=end_ms,
                          pair_wall_ms=end_ms-context['admitted_ms'])
            pair_results = []
            for frame_id, partner, value in [
                    (context['first_id'], context['second_id'], context['left']),
                    (context['second_id'], context['first_id'], context['right'])]:
                if frame_id is not None:
                    pair_results.append(dict(frame_id=frame_id, paired_with=partner,
                        shadow_partner_used=shadow, features=value.reshape(512).copy(),
                        pl_completions=context['pl_events'], pair_timing=timing))
            completed[context['index']] = pair_results
            timings[context['index']] = timing
            del active[context['index']]
            context['left'] = context['right'] = None

        # Context managers wait for already running calls on error. There is
        # never a queued executor task beyond the single submitted owner call.
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ps_pool:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pl_pool:
                    pools = {'PS': ps_pool, 'PL': pl_pool}
                    admit()
                    while active:
                        for owner in ('PL', 'PS'):
                            if owner in running or not pending[owner]:
                                continue
                            # Drain advanced work first; equal-stage FIFO order.
                            pending[owner].sort(key=lambda c: (-c['stage'], c['index']))
                            context = pending[owner].pop(0)
                            function = self._ps_pair if owner == 'PS' else self._pl_pair
                            future = pools[owner].submit(function, context, context['stage'], origin)
                            running[owner] = (future, context)
                        if not running:
                            raise RuntimeError('V10 scheduler has active work but no runnable stage')
                        done, _ = concurrent.futures.wait(
                            [entry[0] for entry in running.values()],
                            return_when=concurrent.futures.FIRST_COMPLETED)
                        for owner in ('PL', 'PS'):
                            if owner not in running or running[owner][0] not in done:
                                continue
                            future, context = running.pop(owner)
                            left, right, evidence, span = future.result()
                            context['left'], context['right'] = left, right
                            timeline.append(span)
                            if owner == 'PS':
                                context['ps_events'].extend(evidence)
                            else:
                                context['pl_events'].append(evidence)
                            context['stage'] += 1
                            if context['stage'] == 7:
                                finish(context)
                            else:
                                pending['PL' if owner == 'PS' else 'PS'].append(context)
                        admit()
        except Exception:
            self._stream_failed = True
            self.last_run_summary = dict(schedule='bounded_cross_pair_ps_pl', status='FAILED_DRAINED',
                completed_pair_count=len(completed), peak_in_flight_pairs=peak_active,
                timeline=timeline, workers_drained=True)
            raise
        results = [result for index in sorted(completed) for result in completed[index]]
        wall_ms = (time.perf_counter()-origin)*1000
        self.last_run_summary = dict(schedule='bounded_cross_pair_ps_pl', status='COMPLETED',
            pair_count=len(completed), real_frame_count=len(results),
            pair_timings=[timings[index] for index in sorted(timings)],
            peak_in_flight_pairs=peak_active, max_in_flight_pairs=max_in_flight,
            ps_workers=1, pl_workers=1, timeline=timeline, execution_ms=wall_ms,
            fps_including_fill_and_drain=len(results)*1000/wall_ms if results else 0,
            shadow_counts_as_real_throughput=False)
        return results

    def run_one(self, frame_id, value):
        return self.run([(frame_id, value)], max_in_flight=1)[0]

    def close(self):
        if not self._execution_lock.acquire(False):
            raise RuntimeError('cannot close V10 stream runtime while work is active')
        try:
            return super(V10StreamRuntime, self).close()
        finally:
            self._execution_lock.release()
