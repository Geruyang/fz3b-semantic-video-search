"""ctypes binding for the optional exact V10 quantization shared library."""

import ctypes
import math
import os

import numpy as np


_FUNCTION = "cnn_v10_quantize_chw_to_hcw"


class CtypesV10Quantizer(object):
    """Call the C quantizer into caller-owned reusable INT16 HCW storage.

    ``library`` may be a path or a loaded CDLL-compatible object.  The library
    is stateless after loading, so independent workspace buffers can call it
    concurrently.  Source conversion to contiguous FP32 is performed only if
    needed; output storage must already be contiguous little-endian INT16.
    """

    def __init__(self, library, symbol=_FUNCTION):
        if isinstance(library, (str, bytes, os.PathLike)):
            self._library = ctypes.CDLL(os.fspath(library))
        else:
            self._library = library
        try:
            function = getattr(self._library, symbol)
        except AttributeError:
            raise ValueError("native quant library is missing %s" % symbol)
        function.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.c_int32, ctypes.c_int32,
            ctypes.c_double, ctypes.POINTER(ctypes.c_int16), ctypes.c_int32,
            ctypes.c_int32,
        ]
        function.restype = ctypes.c_int
        self._function = function

    def quantize(self, value, scale, output, clamp):
        source = np.asarray(value, dtype=np.float32)
        if source.ndim != 4 or source.shape[0] != 1:
            raise ValueError("native quant input must be batch-one NCHW FP32")
        if not np.isfinite(source).all():
            raise ValueError("native quant input must contain only finite values")
        if isinstance(scale, (bool, np.bool_)):
            raise ValueError("scale must be finite and positive")
        try:
            scale = float(scale)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("scale must be finite and positive")
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("scale must be finite and positive")
        if (not isinstance(clamp, (tuple, list)) or len(clamp) != 2 or
                any(isinstance(x, bool) or not isinstance(x, (int, np.integer))
                    for x in clamp)):
            raise ValueError("clamp must be an integer (minimum, maximum) pair")
        low, high = int(clamp[0]), int(clamp[1])
        if low < -32768 or high > 32767 or low > high:
            raise ValueError("clamp must be an ordered range within signed INT16")
        _, channels, height, width = source.shape
        if height != width:
            raise ValueError("native quant input must have square spatial dimensions")
        expected = (width, channels, width)
        target = np.asarray(output)
        if (target.shape != expected or target.dtype != np.dtype("<i2") or
                not target.flags.c_contiguous or not target.flags.writeable):
            raise ValueError("output must be writable contiguous INT16 HCW %s" %
                             (expected,))
        source = np.ascontiguousarray(source, dtype=np.float32)
        source_ptr = source.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        target_ptr = target.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        status = self._function(source_ptr, channels, width, scale, target_ptr,
                                low, high)
        if status != 0:
            if status == -2:
                raise ValueError("native quant input contains non-finite values")
            raise RuntimeError("native quantizer returned status %d" % status)
        return target


__all__ = ["CtypesV10Quantizer"]
