"""Reusable exact V10 CHW-to-HCW quantization workspace.

This implementation keeps NumPy's established FP64 divide, ties-to-even
``rint`` and signed INT16 saturation semantics while writing the division
result in destination HCW order.  Returned storage belongs to the workspace
and is overwritten by its next call.
"""

import math

import numpy as np


INT16_CLAMP = (-32768, 32767)


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
        scale = _checked_scale(scale)
        source = np.asarray(value, dtype=np.float32)
        if source.shape != self.chw_shape or not np.isfinite(source).all():
            raise ValueError("%s must be finite FP32 %s" % (label, self.chw_shape))
        if self._native_quantizer is not None:
            return self._native_quantizer.quantize(
                source, scale, self._output_i16, self.clamp)
        # Explicit dtype forces FP64 division even on NumPy versions whose
        # scalar-promotion rules would otherwise use a narrower loop.
        np.divide(source[0].transpose(1, 0, 2), np.float64(scale),
                  out=self._scratch_f64, dtype=np.float64)
        np.rint(self._scratch_f64, out=self._scratch_f64)
        np.clip(self._scratch_f64, self.clamp[0], self.clamp[1],
                out=self._scratch_f64)
        np.copyto(self._output_i16, self._scratch_f64, casting="unsafe")
        return self._output_i16


__all__ = ["INT16_CLAMP", "V10NativeQuantWorkspace"]
