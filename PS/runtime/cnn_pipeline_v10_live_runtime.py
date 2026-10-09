"""Incremental ordered results with bounded PS/PL ownership (Python 3.6+).

Use ``with runtime.iter_results(items) as results`` when the consumer may stop
early. The consumer owns each returned feature and metadata. Slow consumers
apply backpressure; elapsed time includes consumer pauses. Full trace retention
is opt-in, and live IDs must increase monotonically to avoid an unbounded ID set.
The frozen finite-batch stream runtime remains available unchanged.
"""
import concurrent.futures
import copy
import math
import threading
import time

import numpy as np

try:
    from cnn_pipeline_v10_stream_runtime import V10StreamRuntime
    from cnn_pipeline_v10_paired_runtime import _CLIENT_SPECS
except ImportError:
    from .cnn_pipeline_v10_stream_runtime import V10StreamRuntime
    from .cnn_pipeline_v10_paired_runtime import _CLIENT_SPECS


class _LiveResults(object):
    def __init__(self, runtime, generator):
        self._runtime = runtime
        self._generator = generator
        self._operation_lock = threading.Lock()
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    def __iter__(self):
        return self

    def _release(self):
        if not self._closed:
            self._closed = True
            self._runtime._execution_lock.release()

    def __next__(self):
        if not self._operation_lock.acquire(False):
            raise RuntimeError('V10 result iteration is already active')
        try:
            if self._closed:
                raise StopIteration
            try:
                return next(self._generator)
            except BaseException:
                self._release()
                raise
        finally:
            self._operation_lock.release()

    def close(self):
        if not self._operation_lock.acquire(False):
            raise RuntimeError('cannot close while result iteration is active')
        try:
            if not self._closed:
                try:
                    # GeneratorExit executes pool shutdown(wait=True) before
                    # releasing the runtime reservation and driver ownership.
                    self._generator.close()
                finally:
                    self._release()
        finally:
            self._operation_lock.release()


class V10LiveRuntime(V10StreamRuntime):
    # Subclasses may replace a whole PS/PL region with one PL-owner call. A
    # grouped call must keep its intermediate buffers inside that call; the
    # scheduler never hands the PL owner to a different pair midway through it.
    PIPELINE_STAGES = (
        ('PS', 'stem-prefix'), ('PL', 2), ('PS', 'network1-bridge'),
        ('PL', 0), ('PS', 'network3-bridge'), ('PL', 1), ('PS', 'suffix'),
    )

    def __init__(self, *args, **kwargs):
        plan = self.PIPELINE_STAGES
        if (not isinstance(plan, tuple) or len(plan) < 3 or len(plan) % 2 != 1 or
                plan[0] != ('PS', 'stem-prefix') or plan[-1] != ('PS', 'suffix')):
            raise ValueError('pipeline must start at stem, alternate owners and end at suffix')
        for index, entry in enumerate(plan):
            if (not isinstance(entry, tuple) or len(entry) != 2 or
                    entry[0] != ('PS' if index % 2 == 0 else 'PL')):
                raise ValueError('pipeline stages must alternate PS and PL owners')
            key = entry[1]
            if entry[0] == 'PS':
                if not isinstance(key, str) or key not in _CLIENT_SPECS:
                    raise ValueError('pipeline PS partition is unknown')
            elif (isinstance(key, bool) or not isinstance(key, (int, str)) or
                  isinstance(key, str) and not key):
                raise ValueError('pipeline PL stage key is invalid')
        self._pipeline_stages = plan
        super(V10LiveRuntime, self).__init__(*args, **kwargs)

    def _run_pl_stage(self, key, left, right):
        if isinstance(key, bool) or not isinstance(key, int) or key not in (0, 1, 2):
            raise ValueError('PL stage requires an explicitly implemented backend')
        return self._run_profile(key, left, right)

    def _pl_pair(self, context, stage, origin):
        started = time.perf_counter()
        key = self._pipeline_stages[stage][1]
        result = self._run_pl_stage(key, context['left'], context['right'])
        return result + ({
            'owner': 'PL', 'stage': key, 'pair_index': context['index'],
            'start_ms': (started-origin)*1000,
            'end_ms': (time.perf_counter()-origin)*1000,
        },)

    def _client_timed(self, name, value):
        client = self.clients[name]
        if getattr(client, 'validates_tensor_finiteness', False) is not True:
            return super(V10LiveRuntime, self)._client_timed(name, value)
        # This capability belongs to the local client implementation, never to
        # a model/runner response. Its infer() checks each tensor once while it
        # owns the exchange, avoiding a second full scan in this scheduler.
        input_shape, output_name, output_shape = _CLIENT_SPECS[name]
        source = np.asarray(value, dtype='<f4', order='C')
        if source.shape != input_shape:
            raise ValueError('%s input shape mismatch' % name)
        started = time.perf_counter()
        response = client.infer([source])
        call_wall_ms = (time.perf_counter()-started)*1000
        if (not isinstance(response, tuple) or len(response) != 2 or
                not isinstance(response[0], dict)):
            raise ValueError('%s response is malformed' % name)
        outputs, run_ms = response
        if (isinstance(run_ms, bool) or not isinstance(run_ms, (int, float)) or
                not math.isfinite(run_ms) or run_ms < 0 or output_name not in outputs):
            raise ValueError('%s output or runtime is invalid' % name)
        result = outputs[output_name]
        if (not isinstance(result, np.ndarray) or result.shape != output_shape or
                result.dtype != np.dtype('<f4') or not result.flags.c_contiguous):
            raise ValueError('%s validated output shape/dtype/layout mismatch' % name)
        return result, dict(partition=name, ort_run_ms=float(run_ms),
                            call_wall_ms=call_wall_ms, finite_validation_owner='client')

    def _ps_pair(self, context, stage, origin):
        started = time.perf_counter()
        name = self._pipeline_stages[stage][1]
        independent = getattr(self.clients[name],
                              'outputs_have_independent_lifetime', False) is True
        left, event_a = self._client_timed(name, context['left'])
        if not independent:
            left = left.copy()
        event_a['lane'] = 'A'
        events = [event_a]
        if context['second_id'] is None:
            right = left.copy()
        else:
            right, event_b = self._client_timed(name, context['right'])
            if not independent:
                right = right.copy()
            event_b['lane'] = 'B'
            events.append(event_b)
        return left, right, events, {
            'owner': 'PS', 'stage': name, 'pair_index': context['index'],
            'start_ms': (started-origin)*1000,
            'end_ms': (time.perf_counter()-origin)*1000,
        }

    def iter_results(self, items, max_in_flight=3, record_history=False):
        """Reserve this runtime and return an explicitly closeable iterator.

        Input IDs are nonnegative, strictly increasing integers. Inputs are
        snapshotted before pulling another frame. At most max_in_flight pairs,
        including finished pairs waiting for delivery, are retained internally.
        An early close is terminal: drain submitted work, then call runtime.close.
        Closing an iterator before its first next() merely releases reservation.
        """
        if (isinstance(max_in_flight, bool) or not isinstance(max_in_flight, int)
                or max_in_flight not in (1, 2, 3, 4)):
            raise ValueError('max_in_flight must be an integer from 1 to 4')
        if not isinstance(record_history, bool):
            raise ValueError('record_history must be bool')
        if not self._execution_lock.acquire(False):
            raise RuntimeError('V10 stream runtime is already running')
        try:
            if self.closed:
                raise RuntimeError('V10 runtime is closed')
            if self._stream_failed:
                raise RuntimeError('V10 stream failed; close is required before a new runtime')
            return _LiveResults(self, self._iter_live(items, max_in_flight, record_history))
        except BaseException:
            self._execution_lock.release()
            raise

    def run(self, items, max_in_flight=3):
        """Collect a finite live stream, retaining full benchmark evidence."""
        with self.iter_results(items, max_in_flight, record_history=True) as results:
            return list(results)

    def _iter_live(self, items, max_in_flight, record_history):
        origin = time.perf_counter()
        active, ready = {}, {}
        pending, running = {'PS': [], 'PL': []}, {}
        timeline, timings = [], []
        busy_ms = {'PS': 0.0, 'PL': 0.0}
        exhausted, last_id = False, -1
        next_index = next_emit = peak = completed_pairs = completed_frames = emitted = 0
        status = 'FAILED_DRAINED'

        def take():
            nonlocal last_id
            frame_id, value = self._parse_item(next(source))
            if frame_id <= last_id:
                raise ValueError('live frame IDs must be unique and strictly increasing')
            last_id = frame_id
            return frame_id, self._finite(value, (1, 3, 256, 256), 'stream input').copy()

        def admit():
            nonlocal exhausted, next_index, peak
            while not exhausted and len(active)+len(ready) < max_in_flight:
                try:
                    first = take()
                except StopIteration:
                    exhausted = True
                    break
                try:
                    second = take()
                except StopIteration:
                    second, exhausted = (None, first[1]), True
                context = dict(index=next_index, first_id=first[0], second_id=second[0],
                               left=first[1], right=second[1], stage=0,
                               admitted_ms=(time.perf_counter()-origin)*1000,
                               ps_events=[], pl_events=[])
                active[next_index] = context
                pending['PS'].append(context)
                next_index += 1
                peak = max(peak, len(active)+len(ready))

        def finish(context):
            nonlocal completed_pairs, completed_frames
            ended = (time.perf_counter()-origin)*1000
            shadow = context['second_id'] is None
            timing = dict(schedule='incremental_bounded_cross_pair_ps_pl',
                          frame_ids=[context['first_id'], context['second_id']],
                          real_frame_count=1 if shadow else 2,
                          hardware_lane_frame_count=2, shadow_counts_as_real_throughput=False,
                          ps_events=context['ps_events'], pl_events=context['pl_events'],
                          admitted_ms=context['admitted_ms'], completed_ms=ended,
                          pair_wall_ms=ended-context['admitted_ms'])
            frames = []
            for frame_id, partner, value in (
                    (context['first_id'], context['second_id'], context['left']),
                    (context['second_id'], context['first_id'], context['right'])):
                if frame_id is not None:
                    frames.append(dict(frame_id=frame_id, paired_with=partner,
                                       shadow_partner_used=shadow,
                                       features=value.reshape(512).copy()))
            ready[context['index']] = frames, timing
            if record_history:
                timings.append(timing)
            completed_pairs += 1
            completed_frames += len(frames)
            del active[context['index']]
            context['left'] = context['right'] = None

        def dispatch(pools):
            for owner in ('PL', 'PS'):
                if owner in running or not pending[owner]:
                    continue
                pending[owner].sort(key=lambda c: (-c['stage'], c['index']))
                context = pending[owner].pop(0)
                function = self._ps_pair if owner == 'PS' else self._pl_pair
                running[owner] = (pools[owner].submit(
                    function, context, context['stage'], origin), context)

        try:
            source = iter(items)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ps_pool:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pl_pool:
                    pools = {'PS': ps_pool, 'PL': pl_pool}
                    admit()
                    while active or ready:
                        # Keep already-admitted work progressing while a caller
                        # processes its result; never queue a second owner call.
                        dispatch(pools)
                        while next_emit in ready:
                            frames, timing = ready[next_emit]
                            for frame in frames:
                                # Deep-copy small metadata, not activation tensors:
                                # consumer mutation must not alter the partner or
                                # runtime's retained benchmark history.
                                result = dict(frame)
                                result['pair_timing'] = copy.deepcopy(timing)
                                # This frame already owns an independent timing
                                # tree. Expose its PL branch instead of copying
                                # the same nested register snapshots twice.
                                result['pl_completions'] = result['pair_timing']['pl_events']
                                delivered = (time.perf_counter()-origin)*1000
                                result['delivery_ms'] = delivered
                                result['completion_to_delivery_ms'] = delivered-timing['completed_ms']
                                emitted += 1
                                yield result
                            del ready[next_emit]
                            next_emit += 1
                        admit()
                        dispatch(pools)
                        if not running:
                            if active or ready:
                                raise RuntimeError('V10 scheduler has no runnable stage')
                            break
                        done, _ = concurrent.futures.wait(
                            [entry[0] for entry in running.values()],
                            return_when=concurrent.futures.FIRST_COMPLETED)
                        for owner in ('PL', 'PS'):
                            if owner not in running or running[owner][0] not in done:
                                continue
                            future, context = running.pop(owner)
                            left, right, evidence, span = future.result()
                            context['left'], context['right'] = left, right
                            busy_ms[owner] += span['end_ms']-span['start_ms']
                            if record_history:
                                timeline.append(span)
                            if owner == 'PS':
                                context['ps_events'].extend(evidence)
                            else:
                                context['pl_events'].append(evidence)
                            context['stage'] += 1
                            if context['stage'] == len(self._pipeline_stages):
                                finish(context)
                            else:
                                next_owner = self._pipeline_stages[context['stage']][0]
                                pending[next_owner].append(context)
            status = 'COMPLETED'
        except GeneratorExit:
            status = 'CANCELLED_DRAINED'
            self._stream_failed = True
            raise
        except BaseException:
            self._stream_failed = True
            raise
        finally:
            # Reached only after submitted owner calls have drained, including
            # GeneratorExit. No arena is freed or quiesced in this generator.
            cancelled = status == 'CANCELLED_DRAINED'
            drained_errors = []
            for owner, (future, context) in running.items():
                try:
                    unused_left, unused_right, unused_evidence, span = future.result()
                    busy_ms[owner] += span['end_ms']-span['start_ms']
                    if record_history:
                        timeline.append(span)
                except BaseException as error:
                    drained_errors.append(dict(owner=owner, pair_index=context['index'],
                                               error='%s: %s' % (type(error).__name__, error)))
            if drained_errors:
                status = 'FAILED_DRAINED'
                self._stream_failed = True
            wall_ms = (time.perf_counter()-origin)*1000
            self.last_run_summary = dict(
                schedule='incremental_bounded_cross_pair_ps_pl', status=status,
                pipeline_stages=list(self._pipeline_stages),
                pair_count=completed_pairs, completed_pair_count=completed_pairs,
                real_frame_count=completed_frames, emitted_frame_count=emitted,
                pair_timings=timings, timeline=timeline, record_history=record_history,
                peak_in_flight_pairs=peak, max_in_flight_pairs=max_in_flight,
                admitted_pair_count=next_index, ps_workers=1, pl_workers=1,
                ps_worker_busy_ms=busy_ms['PS'], pl_worker_busy_ms=busy_ms['PL'],
                execution_ms=wall_ms, workers_drained=True,
                drained_call_errors=drained_errors,
                fps_including_fill_and_drain=emitted*1000/wall_ms if emitted else 0,
                elapsed_includes_consumer_pauses=True,
                shadow_counts_as_real_throughput=False)
            if cancelled and drained_errors:
                raise RuntimeError('worker failed while draining cancelled stream: %s' %
                                   drained_errors[0]['error'])


__all__ = ['V10LiveRuntime']
