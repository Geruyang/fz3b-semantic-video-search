/*
 * Exact V10 activation quantization with fused CHW -> HCW output.
 *
 * Build for the board with, for example:
 *   aarch64-linux-gnu-gcc -O3 -fPIC -shared -fno-fast-math \
 *       -o libcnn_v10_native_quant.so cnn_v10_native_quant_neon.c -lm
 *
 * No NumPy or Python headers are required.  Division is performed as IEEE
 * double per element; ties are resolved explicitly to even.  Do not compile
 * this file with fast-math flags.
 */

#include <math.h>
#include <stddef.h>
#include <stdint.h>

#if defined(__aarch64__)
#include <arm_neon.h>
#endif

#if defined(_WIN32)
#define CNNV10_EXPORT __declspec(dllexport)
#else
#define CNNV10_EXPORT __attribute__((visibility("default")))
#endif

static double round_ties_even(double value)
{
    double lower;
    double fraction;

    if (!isfinite(value)) {
        return value;
    }

    lower = floor(value);
    fraction = value - lower;
    if (fraction < 0.5) {
        return lower;
    }
    if (fraction > 0.5) {
        return lower + 1.0;
    }

    /* floor(value) is exactly integral in this tie region. */
    return fmod(fabs(lower), 2.0) == 0.0 ? lower : lower + 1.0;
}

/* Input is contiguous batch-one NCHW FP32; output is contiguous HCW i16. */
static int quantize_chw_to_hcw_impl(
    const float *source,
    int32_t channels,
    int32_t width,
    double scale,
    int16_t *destination,
    int32_t clamp_min,
    int32_t clamp_max,
    int use_neon)
{
    size_t elements;
    size_t plane;
    size_t i;
    int32_t h;
    int32_t c;
    int32_t w;

    if (source == NULL || destination == NULL || channels <= 0 || width <= 0 ||
        !isfinite(scale) || scale <= 0.0 || clamp_min < -32768 ||
        clamp_max > 32767 || clamp_min > clamp_max) {
        return -1;
    }

    if ((size_t)width > SIZE_MAX / (size_t)width) {
        return -1;
    }
    plane = (size_t)width * (size_t)width;
    if ((size_t)channels > SIZE_MAX / plane) {
        return -1;
    }
    elements = (size_t)channels * plane;
    for (i = 0; i < elements; ++i) {
        if (!isfinite(source[i])) {
            return -2;
        }
    }

    /* HCW traversal makes destination writes contiguous; CHW reads remain
       well-defined strided accesses.  Quantization itself is never vectorized
       through approximate reciprocal arithmetic. */
    for (h = 0; h < width; ++h) {
        for (c = 0; c < channels; ++c) {
            const float *src = source + (size_t)c * (size_t)width * (size_t)width +
                               (size_t)h * (size_t)width;
            int16_t *dst = destination +
                           ((size_t)h * (size_t)channels + (size_t)c) *
                               (size_t)width;
            w = 0;
#if defined(__aarch64__)
            if (use_neon) {
            /* ARMv8 executes two exact FP64 divisions and nearest-even rounds
               per vector.  This uses neither reciprocal approximation nor
               fast-math contraction; scalar conversion after clamp remains
               exact.  The scalar export below remains available on AArch64
               for differential checking against this path. */
            {
                const float64x2_t scale_v = vdupq_n_f64(scale);
                const float64x2_t low_v = vdupq_n_f64((double)clamp_min);
                const float64x2_t high_v = vdupq_n_f64((double)clamp_max);
                for (; w + 1 < width; w += 2) {
                    double input_pair[2];
                    double rounded_pair[2];
                    float64x2_t quotient;
                    float64x2_t rounded;
                    input_pair[0] = (double)src[w];
                    input_pair[1] = (double)src[w + 1];
                    quotient = vdivq_f64(vld1q_f64(input_pair), scale_v);
                    rounded = vrndnq_f64(quotient);
                    rounded = vmaxq_f64(low_v, vminq_f64(high_v, rounded));
                    vst1q_f64(rounded_pair, rounded);
                    dst[w] = (int16_t)rounded_pair[0];
                    dst[w + 1] = (int16_t)rounded_pair[1];
                }
            }
            }
#else
            (void)use_neon;
#endif
            for (; w < width; ++w) {
                const double quotient = (double)src[w] / scale;
                double rounded;

                /* Saturating early avoids large-value rounding edge cases;
                   these thresholds are strictly outside the unclamped range. */
                if (quotient <= (double)clamp_min - 1.0) {
                    dst[w] = (int16_t)clamp_min;
                    continue;
                }
                if (quotient >= (double)clamp_max + 1.0) {
                    dst[w] = (int16_t)clamp_max;
                    continue;
                }
                rounded = round_ties_even(quotient);
                if (rounded < (double)clamp_min) {
                    rounded = (double)clamp_min;
                } else if (rounded > (double)clamp_max) {
                    rounded = (double)clamp_max;
                }
                dst[w] = (int16_t)rounded;
            }
        }
    }
    return 0;
}

/*
 * Return: 0 success; -1 invalid arguments; -2 non-finite source element.
 * A non-finite source is rejected before any output is written.
 */
CNNV10_EXPORT int cnn_v10_quantize_chw_to_hcw_scalar(
    const float *source, int32_t channels, int32_t width, double scale,
    int16_t *destination, int32_t clamp_min, int32_t clamp_max)
{
    return quantize_chw_to_hcw_impl(source, channels, width, scale, destination,
                                    clamp_min, clamp_max, 0);
}

CNNV10_EXPORT int cnn_v10_quantize_chw_to_hcw(
    const float *source, int32_t channels, int32_t width, double scale,
    int16_t *destination, int32_t clamp_min, int32_t clamp_max)
{
    return quantize_chw_to_hcw_impl(source, channels, width, scale, destination,
                                    clamp_min, clamp_max, 1);
}
