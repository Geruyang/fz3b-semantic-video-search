"""Reusable exact V10 CHW-to-HCW quantization workspace.

This implementation keeps NumPy's established FP64 divide, ties-to-even
``rint`` and signed INT16 saturation semantics while writing the division
result in destination HCW order.  Returned storage belongs to the workspace
and is overwritten by its next call.
"""

import contextlib
import math
import threading

import numpy as np


INT16_CLAMP = (-32768, 32767)
# Unknown DMA outcomes intentionally retain their Python owners until process
# exit.  The kernel simultaneously retains its GUP pages in quarantine.
_QUARANTINED_QUANT_BUFFERS = []


def _checked_clamp(clamp):
    if (not isinstance(clamp, (tuple, list)) or len(clamp) != 2 or
            any(isinstance(value, bool) or not isinstance(value, (int, np.integer))
                for value in clamp)):
        raise ValueError("clamp must be an integer (minimum, maximum) pair")
    low, high = int(clamp[0]), int(clamp[1])
    if low > high or low < -32768 or high > 32767:
        raise ValueError("clamp must be an ordered range within signed INT16")
    return low, high


def _checked_scale(scale):
    if isinstance(scale, (bool, np.bool_)):
        raise ValueError("scale must be finite and positive")
    try:
        result = float(scale)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("scale must be finite and positive")
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError("scale must be finite and positive")
    return result


class V10NativeQuantWorkspace(object):
    """Preallocated workspace for one NCHW batch-one activation shape."""

    def __init__(self, profile, channels, width, clamp=INT16_CLAMP,
                 native_lib=None):
        for name, value in (("profile", profile), ("channels", channels),
                            ("width", width)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("%s must be a non-negative integer" % name)
        if channels <= 0 or width <= 0:
            raise ValueError("channels and width must be positive")
        self.profile = profile
        self.channels = channels
        self.width = width
        self.clamp = _checked_clamp(clamp)
        self.chw_shape = (1, channels, width, width)
        self.hcw_shape = (width, channels, width)
        self._scratch_f64 = np.empty(self.hcw_shape, dtype=np.float64)
        self._output_i16 = np.empty(self.hcw_shape, dtype="<i2")
        self._lock = threading.RLock()
        self._poisoned = False
        if native_lib is None:
            self._native_quantizer = None
        else:
            try:
                from cnn_v10_native_quant_ctypes import CtypesV10Quantizer
            except ImportError:
                from .cnn_v10_native_quant_ctypes import CtypesV10Quantizer
            self._native_quantizer = (
                native_lib if callable(getattr(native_lib, "quantize", None))
                else CtypesV10Quantizer(native_lib))

    def quantize_chw_to_hcw(self, value, scale, label="V10 activation"):
        """Quantize finite FP32 NCHW to little-endian INT16 HCW, reusing output.

        The FP32 source is read through a CHW-to-HCW transpose view.  NumPy's
        FP64 ufunc loop writes directly to contiguous HCW scratch, then applies
        ``rint`` (nearest, ties-to-even), clamp, and INT16 conversion in place.
        """
        with self._lock:
            self._require_usable()
            return self.quantize_chw_to_hcw_into(
                value, scale, self._output_i16, label)

    def _require_usable(self):
        if self._poisoned:
            raise RuntimeError("quantization workspace is poisoned by an unknown DMA outcome")

    @contextlib.contextmanager
    def locked_quantized_hcw(self, value, scale, label="V10 activation"):
        """Hold workspace ownership until a synchronous consumer returns.

        The yielded cacheable NumPy buffer is read-only.  This is intended for
        the cached-DMA ioctl, whose GUP/SG lifetime ends before the context is
        released.  It prevents another caller from reusing the same scratch or
        output storage while DMA still reads it.
        """
        with self._lock:
            self._require_usable()
            result = self.quantize_chw_to_hcw(value, scale, label)
            result.flags.writeable = False
            try:
                yield result
            except BaseException:
                # The exception may follow DMA submission or even a completed
                # transfer whose returned evidence could not be validated.
                # Keep the exact malloc-backed ndarray alive and immutable;
                # never let this workspace overwrite it or offer another
                # upload after an outcome the caller cannot prove safe.
                self._poisoned = True
                if not any(item is result for item in _QUARANTINED_QUANT_BUFFERS):
                    _QUARANTINED_QUANT_BUFFERS.append(result)
                raise
            else:
                result.flags.writeable = True

    def quantize_chw_to_hcw_into(self, value, scale, output,
                                 label="V10 activation"):
        """Quantize directly into caller-owned contiguous INT16 HCW storage.

        This is the direct-target form used by the A0003 mapped-arena
        candidate.  It retains the established FP64 division and ties-to-even
        semantics while avoiding the intermediate INT16 activation copy.
        """
        with self._lock:
            self._require_usable()
            scale = _checked_scale(scale)
            source = np.asarray(value, dtype=np.float32)
            if source.shape != self.chw_shape or not np.isfinite(source).all():
                raise ValueError("%s must be finite FP32 %s" %
                                 (label, self.chw_shape))
            target = np.asarray(output)
            if (target.shape != self.hcw_shape or
                    target.dtype != np.dtype("<i2") or
                    not target.flags.c_contiguous or
                    not target.flags.writeable):
                raise ValueError("output must be writable contiguous INT16 HCW %s" %
                                 (self.hcw_shape,))
            if self._native_quantizer is not None:
                return self._native_quantizer.quantize(
                    source, scale, target, self.clamp)
            # Explicit dtype forces FP64 division even on NumPy versions whose
            # scalar-promotion rules would otherwise use a narrower loop.
            np.divide(source[0].transpose(1, 0, 2), np.float64(scale),
                      out=self._scratch_f64, dtype=np.float64)
            np.rint(self._scratch_f64, out=self._scratch_f64)
            np.clip(self._scratch_f64, self.clamp[0], self.clamp[1],
                    out=self._scratch_f64)
            np.copyto(target, self._scratch_f64, casting="unsafe")
            return target


__all__ = ["INT16_CLAMP", "V10NativeQuantWorkspace"]
