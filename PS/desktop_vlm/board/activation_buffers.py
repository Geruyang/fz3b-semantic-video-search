"""Reusable NumPy workspaces for v5 CHW/HCW activation conversion.

Create one workspace per frame lease. Returned arrays are owned by the
workspace and are overwritten by the next call to the same method; callers
must not retain them across workspace reuse or share a workspace between
concurrent frames.
"""

import math

import numpy as np


class ActivationBufferWorkspace(object):
    """Preallocated buffers for one profile on one frame lease."""

    def __init__(self, profile, channels, width):
        for name, value in (("profile", profile), ("channels", channels),
                            ("width", width)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("%s must be a non-negative integer" % name)
        if channels <= 0 or width <= 0:
            raise ValueError("channels and width must be positive")
        self.profile = profile
        self.channels = channels
        self.width = width
        self._chw_shape = (1, channels, width, width)
        self._hcw_shape = (width, channels, width)
        self._quant_scratch_f64 = np.empty((channels, width, width), dtype=np.float64)
        self._quantized_hcw = np.empty(self._hcw_shape, dtype="<i2")
        self._dequantized_chw = np.empty(self._chw_shape, dtype=np.float32)

    @staticmethod
    def _scale(value, label):
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("%s scale must be finite and positive" % label)
        if not math.isfinite(result) or result <= 0.0:
            raise ValueError("%s scale must be finite and positive" % label)
        return result

    def quantize_chw_to_hcw(self, value, scale, label):
        """Round FP32 NCHW input and write clipped INT16 directly in HCW order.

        Rounding follows NumPy ``rint`` (ties to even), with the same FP64
        division intermediate and saturation as the existing v5 quantizer.
        The returned little-endian INT16 array is reused on the next call.
        """
        scale = self._scale(scale, label)
        source = np.asarray(value, dtype=np.float32)
        if source.shape != self._chw_shape or not np.isfinite(source).all():
            raise ValueError("%s must be finite FP32 CHW %s" %
                             (label, self._chw_shape))
        np.copyto(self._quant_scratch_f64, source[0])
        np.divide(self._quant_scratch_f64, scale,
                  out=self._quant_scratch_f64)
        np.rint(self._quant_scratch_f64, out=self._quant_scratch_f64)
        np.clip(self._quant_scratch_f64, -32768, 32767,
                out=self._quant_scratch_f64)
        np.copyto(self._quantized_hcw,
                  self._quant_scratch_f64.transpose(1, 0, 2),
                  casting="unsafe")
        return self._quantized_hcw

    def dequantize_hcw_to_chw(self, value, scale, label):
        """Transpose INT16 HCW and dequantize directly into reusable FP32 NCHW."""
        scale = self._scale(scale, label)
        source = np.asarray(value)
        if source.shape != self._hcw_shape or source.dtype != np.dtype("<i2"):
            raise ValueError("%s must be INT16 HCW %s" %
                             (label, self._hcw_shape))
        np.multiply(source.transpose(1, 0, 2), np.float32(scale),
                    out=self._dequantized_chw[0])
        return self._dequantized_chw


__all__ = ["ActivationBufferWorkspace"]
