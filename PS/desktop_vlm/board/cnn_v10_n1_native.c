#define _POSIX_C_SOURCE 200809L
/*
 * N1 W8A16Acc32 bridge kernel for AArch64/Linux, with a portable scalar
 * host-oracle implementation and an AArch64 NEON PW spatial-lane candidate.
 *
 * Build: aarch64-linux-gnu-gcc -std=c99 -O3 -fPIC -shared -fno-fast-math \
 *        -ffp-contract=off -pthread \
 *        cnn_v10_n1_native.c -o libcnn_v10_n1_native.so -lm
 * Do not use fast-math: GELU and FP32 post-op order are part of the frozen
 * FP32 contract. All tensors passed to/from this ABI use contiguous HCW order.
 */
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#if defined(_WIN32)
#include <windows.h>
#else
#include <time.h>
#endif
#if defined(__aarch64__)
#include <arm_neon.h>
#endif

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

#define C 128
#define IN_C 64
#define IN_W 64
#define OUT_W 32
#define HEADER_BYTES 40
#define DW_W8_OFF HEADER_BYTES
#define DW_SCALE_OFF (DW_W8_OFF + C * 49)
#define DW_BIAS_OFF (DW_SCALE_OFF + C * 4)
#define DW_FP32_OFF (DW_BIAS_OFF + C * 4)
#define DW_MASK_OFF (DW_FP32_OFF + C * 49 * 4)
#define PW_W8_OFF (DW_MASK_OFF + C)
#define PW_SCALE_OFF (PW_W8_OFF + C * C)
#define PW_BIAS_OFF (PW_SCALE_OFF + C * 4)
#define PW_FP32_OFF (PW_BIAS_OFF + C * 4)
#define PW_MASK_OFF (PW_FP32_OFF + C * C * 4)
#define PARAM_BYTES (PW_MASK_OFF + C)

static double round_even(double x)
{
    double lo, frac;
    if (!isfinite(x)) return x;
    lo = floor(x); frac = x - lo;
    if (frac < 0.5) return lo;
    if (frac > 0.5) return lo + 1.0;
    return fmod(fabs(lo), 2.0) == 0.0 ? lo : lo + 1.0;
}

static float read_f32(const unsigned char *p)
{
    float v;
    memcpy(&v, p, sizeof(v));
    return v;
}

static int16_t quant_a16(float x, float scale)
{
    double q = round_even((double)x / (double)scale);
    if (q > 32767.0) q = 32767.0;
    if (q < -32767.0) q = -32767.0;
    return (int16_t)q;
}

static float gelu_exact(float x)
{
    /* Matches cnn_v10_mixed_int._gelu_fp32's FP32 operation ordering. */
    float erf_value = (float)erf((double)x / 1.4142135623730950488);
    float half_x = 0.5f * x;
    return half_x * (1.0f + erf_value);
}

static size_t hcw(size_t h, size_t c, size_t w, size_t channels, size_t width)
{
    return (h * channels + c) * width + w;
}

static int validate(const unsigned char *p, size_t bytes)
{
    static const unsigned char magic[8] = {'N','1','W','8','A','1','6',0};
    uint32_t version, dwc, pwc, outc, reserved;
    if (!p || bytes != PARAM_BYTES || memcmp(p, magic, 8) != 0) return -1;
    memcpy(&version, p + 8, 4); memcpy(&dwc, p + 12, 4);
    memcpy(&pwc, p + 16, 4); memcpy(&outc, p + 20, 4);
    memcpy(&reserved, p + 24, 4);
    if (version != 1 || dwc != C || pwc != C || outc != C || reserved != 0) return -1;
    if (!isfinite(read_f32(p + 28)) || read_f32(p + 28) <= 0.0f ||
        !isfinite(read_f32(p + 32)) || read_f32(p + 32) <= 0.0f ||
        !isfinite(read_f32(p + 36)) || read_f32(p + 36) <= 0.0f) return -1;
    return 0;
}

/* Input/output buffers are caller-owned and remain independent after return. */
typedef struct {
    const unsigned char *p;
    const int16_t *input;
    const int16_t *padded_input;
    int16_t *mid;
    int16_t *output;
    int oc_begin;
    int oc_end;
    int use_neon;
    float input_scale;
    float pw_scale;
    float output_scale;
    int status;
} worker_args;

#if defined(__aarch64__)
static void *dw_worker_neon(void *opaque)
{
    worker_args *args = (worker_args *)opaque;
    const unsigned char *p = args->p;
    size_t oc, h, w, ky, kx;
    for (oc = (size_t)args->oc_begin; oc < (size_t)args->oc_end; oc += 2) {
        const int ic = (int)(oc / 2);
        const int fp32_0 = p[DW_MASK_OFF + oc] != 0;
        const int fp32_1 = p[DW_MASK_OFF + oc + 1] != 0;
        const float ws0 = read_f32(p + DW_SCALE_OFF + oc * 4);
        const float ws1 = read_f32(p + DW_SCALE_OFF + (oc + 1) * 4);
        const float bias0 = read_f32(p + DW_BIAS_OFF + oc * 4);
        const float bias1 = read_f32(p + DW_BIAS_OFF + (oc + 1) * 4);
        const float scale0 = args->input_scale * ws0;
        const float scale1 = args->input_scale * ws1;
        for (h = 0; h < OUT_W; ++h) for (w = 0; w < OUT_W; w += 8) {
            int32x4_t acc0_lo = vdupq_n_s32(0), acc0_hi = vdupq_n_s32(0);
            int32x4_t acc1_lo = vdupq_n_s32(0), acc1_hi = vdupq_n_s32(0);
            float32x4_t f0_lo = vdupq_n_f32(0.0f), f0_hi = vdupq_n_f32(0.0f);
            float32x4_t f1_lo = vdupq_n_f32(0.0f), f1_hi = vdupq_n_f32(0.0f);
            float values0[8], values1[8];
            for (ky = 0; ky < 7; ++ky) for (kx = 0; kx < 7; ++kx) {
                const size_t base = ((size_t)ic * 70 + (2 * h + ky)) * 70 + (2 * w + kx);
                /* Even lanes are the stride-2 samples; padding removed all edge branches. */
                int16x8x2_t interleaved = vld2q_s16(args->padded_input + base);
                int16x8_t x = interleaved.val[0];
                size_t wi0 = oc * 49 + ky * 7 + kx;
                size_t wi1 = (oc + 1) * 49 + ky * 7 + kx;
                int8_t qw0 = (int8_t)p[DW_W8_OFF + wi0];
                int8_t qw1 = (int8_t)p[DW_W8_OFF + wi1];
                if (fp32_0) {
                    float32x4_t xlo = vmulq_n_f32(
                        vcvtq_f32_s32(vmovl_s16(vget_low_s16(x))), args->input_scale);
                    float32x4_t xhi = vmulq_n_f32(
                        vcvtq_f32_s32(vmovl_s16(vget_high_s16(x))), args->input_scale);
                    float w0 = read_f32(p + DW_FP32_OFF + wi0 * 4);
                    f0_lo = vaddq_f32(f0_lo, vmulq_n_f32(xlo, w0));
                    f0_hi = vaddq_f32(f0_hi, vmulq_n_f32(xhi, w0));
                } else {
                    acc0_lo = vmlal_n_s16(acc0_lo, vget_low_s16(x), qw0);
                    acc0_hi = vmlal_n_s16(acc0_hi, vget_high_s16(x), qw0);
                }
                if (fp32_1) {
                    float32x4_t xlo = vmulq_n_f32(
                        vcvtq_f32_s32(vmovl_s16(vget_low_s16(x))), args->input_scale);
                    float32x4_t xhi = vmulq_n_f32(
                        vcvtq_f32_s32(vmovl_s16(vget_high_s16(x))), args->input_scale);
                    float w1 = read_f32(p + DW_FP32_OFF + wi1 * 4);
                    f1_lo = vaddq_f32(f1_lo, vmulq_n_f32(xlo, w1));
                    f1_hi = vaddq_f32(f1_hi, vmulq_n_f32(xhi, w1));
                } else {
                    acc1_lo = vmlal_n_s16(acc1_lo, vget_low_s16(x), qw1);
                    acc1_hi = vmlal_n_s16(acc1_hi, vget_high_s16(x), qw1);
                }
            }
            if (fp32_0) {
                vst1q_f32(values0, vaddq_f32(f0_lo, vdupq_n_f32(bias0)));
                vst1q_f32(values0 + 4, vaddq_f32(f0_hi, vdupq_n_f32(bias0)));
            } else {
                vst1q_f32(values0, vaddq_f32(
                    vmulq_n_f32(vcvtq_f32_s32(acc0_lo), scale0), vdupq_n_f32(bias0)));
                vst1q_f32(values0 + 4, vaddq_f32(
                    vmulq_n_f32(vcvtq_f32_s32(acc0_hi), scale0), vdupq_n_f32(bias0)));
            }
            if (fp32_1) {
                vst1q_f32(values1, vaddq_f32(f1_lo, vdupq_n_f32(bias1)));
                vst1q_f32(values1 + 4, vaddq_f32(f1_hi, vdupq_n_f32(bias1)));
            } else {
                vst1q_f32(values1, vaddq_f32(
                    vmulq_n_f32(vcvtq_f32_s32(acc1_lo), scale1), vdupq_n_f32(bias1)));
                vst1q_f32(values1 + 4, vaddq_f32(
                    vmulq_n_f32(vcvtq_f32_s32(acc1_hi), scale1), vdupq_n_f32(bias1)));
            }
            for (size_t lane = 0; lane < 8; ++lane) {
                args->mid[hcw(h, oc, w + lane, C, OUT_W)] = quant_a16(
                    gelu_exact(values0[lane]), args->pw_scale);
                args->mid[hcw(h, oc + 1, w + lane, C, OUT_W)] = quant_a16(
                    gelu_exact(values1[lane]), args->pw_scale);
            }
        }
    }
    return NULL;
}
#endif

static void *dw_worker(void *opaque)
{
    worker_args *args = (worker_args *)opaque;
#if defined(__aarch64__)
    if (args->use_neon) return dw_worker_neon(opaque);
#endif
    const unsigned char *p = args->p;
    size_t oc, h, w, ky, kx;
    for (oc = (size_t)args->oc_begin; oc < (size_t)args->oc_end; ++oc) {
        int in_channel = (int)(oc / 2);
        int fp32 = p[DW_MASK_OFF + oc] != 0;
        float ws = read_f32(p + DW_SCALE_OFF + oc * 4);
        float bias = read_f32(p + DW_BIAS_OFF + oc * 4);
        for (h = 0; h < OUT_W; ++h) for (w = 0; w < OUT_W; ++w) {
            int64_t acc = 0;
            float facc = 0.0f;
            for (ky = 0; ky < 7; ++ky) for (kx = 0; kx < 7; ++kx) {
                int iy = (int)(2 * h + ky) - 3;
                int ix = (int)(2 * w + kx) - 3;
                int16_t aq = 0;
                if (iy >= 0 && iy < IN_W && ix >= 0 && ix < IN_W)
                    aq = args->input[hcw((size_t)iy, (size_t)in_channel, (size_t)ix, IN_C, IN_W)];
                size_t wi = (oc * 49) + ky * 7 + kx;
                if (fp32) {
                    float a = (float)aq * args->input_scale;
                    facc += a * read_f32(p + DW_FP32_OFF + wi * 4);
                } else {
                    int8_t qw = (int8_t)p[DW_W8_OFF + wi];
                    acc += (int64_t)aq * (int64_t)qw;
                }
            }
            if (!fp32 && (acc < INT32_MIN || acc > INT32_MAX)) {
                args->status = -3;
                return NULL;
            }
            float y = fp32 ? (facc + bias) : ((float)(int32_t)acc * (args->input_scale * ws) + bias);
            size_t oi = hcw(h, oc, w, C, OUT_W);
            args->mid[oi] = quant_a16(gelu_exact(y), args->pw_scale);
        }
    }
    return NULL;
}

static void *pw_worker(void *opaque)
{
    worker_args *args = (worker_args *)opaque;
    const unsigned char *p = args->p;
    size_t oc, h, w, ic;
    for (oc = (size_t)args->oc_begin; oc < (size_t)args->oc_end; ++oc) {
        int fp32 = p[PW_MASK_OFF + oc] != 0;
        float ws = read_f32(p + PW_SCALE_OFF + oc * 4);
        float bias = read_f32(p + PW_BIAS_OFF + oc * 4);
#if defined(__aarch64__)
        if (args->use_neon) {
            const float requant_scale = args->pw_scale * ws;
            for (h = 0; h < OUT_W; ++h) {
                for (w = 0; w < OUT_W; w += 8) {
                    float values[8];
                    if (!fp32) {
                        int32x4_t acc_lo = vdupq_n_s32(0);
                        int32x4_t acc_hi = vdupq_n_s32(0);
                        for (ic = 0; ic < C; ++ic) {
                            size_t ai = hcw(h, ic, w, C, OUT_W);
                            size_t wi = oc * C + ic;
                            int16x8_t a = vld1q_s16(args->mid + ai);
                            int16_t qw = (int8_t)p[PW_W8_OFF + wi];
                            acc_lo = vmlal_n_s16(acc_lo, vget_low_s16(a), qw);
                            acc_hi = vmlal_n_s16(acc_hi, vget_high_s16(a), qw);
                        }
                        vst1q_f32(values, vaddq_f32(
                            vmulq_n_f32(vcvtq_f32_s32(acc_lo), requant_scale),
                            vdupq_n_f32(bias)));
                        vst1q_f32(values + 4, vaddq_f32(
                            vmulq_n_f32(vcvtq_f32_s32(acc_hi), requant_scale),
                            vdupq_n_f32(bias)));
                    } else {
                        float32x4_t acc_lo = vdupq_n_f32(0.0f);
                        float32x4_t acc_hi = vdupq_n_f32(0.0f);
                        for (ic = 0; ic < C; ++ic) {
                            size_t ai = hcw(h, ic, w, C, OUT_W);
                            size_t wi = oc * C + ic;
                            int16x8_t a16 = vld1q_s16(args->mid + ai);
                            float32x4_t alo = vmulq_n_f32(
                                vcvtq_f32_s32(vmovl_s16(vget_low_s16(a16))), args->pw_scale);
                            float32x4_t ahi = vmulq_n_f32(
                                vcvtq_f32_s32(vmovl_s16(vget_high_s16(a16))), args->pw_scale);
                            float weight = read_f32(p + PW_FP32_OFF + wi * 4);
                            acc_lo = vaddq_f32(acc_lo, vmulq_n_f32(alo, weight));
                            acc_hi = vaddq_f32(acc_hi, vmulq_n_f32(ahi, weight));
                        }
                        vst1q_f32(values, vaddq_f32(acc_lo, vdupq_n_f32(bias)));
                        vst1q_f32(values + 4, vaddq_f32(acc_hi, vdupq_n_f32(bias)));
                    }
                    for (size_t lane = 0; lane < 8; ++lane) {
                        size_t oi = hcw(h, oc, w + lane, C, OUT_W);
                        args->output[oi] = quant_a16(gelu_exact(values[lane]), args->output_scale);
                    }
                }
            }
            continue;
        }
#endif
        for (h = 0; h < OUT_W; ++h) for (w = 0; w < OUT_W; ++w) {
            int64_t acc = 0;
            float facc = 0.0f;
            for (ic = 0; ic < C; ++ic) {
                size_t ai = hcw(h, ic, w, C, OUT_W);
                size_t wi = oc * C + ic;
                if (fp32) {
                    facc += ((float)args->mid[ai] * args->pw_scale) * read_f32(p + PW_FP32_OFF + wi * 4);
                } else {
                    int8_t qw = (int8_t)p[PW_W8_OFF + wi];
                    acc += (int64_t)args->mid[ai] * (int64_t)qw;
                }
            }
            if (!fp32 && (acc < INT32_MIN || acc > INT32_MAX)) {
                args->status = -3;
                return NULL;
            }
            float y = fp32 ? (facc + bias) : ((float)(int32_t)acc * (args->pw_scale * ws) + bias);
            size_t oi = hcw(h, oc, w, C, OUT_W);
            args->output[oi] = quant_a16(gelu_exact(y), args->output_scale);
        }
    }
    return NULL;
}

static int run_stage(worker_args args[3], void *(*worker)(void *))
{
    pthread_t threads[3];
    int created = 0;
    int i;
    int join_error = 0;
    for (i = 0; i < 3; ++i) {
        if (pthread_create(&threads[i], NULL, worker, &args[i]) != 0) break;
        ++created;
    }
    for (i = 0; i < created; ++i)
        if (pthread_join(threads[i], NULL) != 0) join_error = 1;
    if (created != 3 || join_error) return -4;
    for (i = 0; i < 3; ++i) if (args[i].status != 0) return args[i].status;
    return 0;
}

static double wall_time_ms(void)
{
#if defined(_WIN32)
    LARGE_INTEGER counter, frequency;
    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&counter);
    return 1000.0 * (double)counter.QuadPart / (double)frequency.QuadPart;
#else
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0.0;
    return 1000.0 * (double)ts.tv_sec + (double)ts.tv_nsec / 1000000.0;
#endif
}

#if defined(__aarch64__)
static void pad_reorder_hcw(const int16_t *input, int16_t *padded)
{
    size_t c, h;
    memset(padded, 0, 64u * 70u * 70u * sizeof(int16_t));
    for (c = 0; c < IN_C; ++c) for (h = 0; h < IN_W; ++h) {
        const int16_t *src = input + hcw(h, c, 0, IN_C, IN_W);
        int16_t *dst = padded + (c * 70u + (h + 3u)) * 70u + 3u;
        memcpy(dst, src, IN_W * sizeof(int16_t));
    }
}
#endif

static int infer_impl(const unsigned char *p, size_t bytes,
                      const int16_t *input, int16_t *output, int use_neon,
                      double *dw_ms, double *pw_ms)
{
    worker_args args[3];
    int16_t *mid, *padded = NULL;
    float input_scale, pw_scale, output_scale;
    int i, status;
    double started;
    if (dw_ms) *dw_ms = 0.0;
    if (pw_ms) *pw_ms = 0.0;
    if (validate(p, bytes) != 0 || !input || !output) return -1;
    input_scale = read_f32(p + 28);
    pw_scale = read_f32(p + 32);
    output_scale = read_f32(p + 36);
    mid = (int16_t *)malloc(C * OUT_W * OUT_W * sizeof(int16_t));
    if (!mid) return -2;
#if defined(__aarch64__)
    if (use_neon) {
        padded = (int16_t *)malloc(64u * 70u * 70u * sizeof(int16_t));
        if (!padded) { free(mid); return -2; }
    }
#endif
    started = wall_time_ms();
#if defined(__aarch64__)
    if (padded) pad_reorder_hcw(input, padded);
#endif
    for (i = 0; i < 3; ++i) {
        args[i].p = p; args[i].input = input; args[i].padded_input = padded;
        args[i].mid = mid; args[i].output = output;
        /* Split the 64 input-channel pairs, then double the pair index.
         * Doubling before integer division yields odd boundaries (42,85),
         * which violates dw_worker_neon's oc/oc+1 invariant and lets the last
         * worker write channel 128. */
        args[i].oc_begin = 2 * ((64 * i) / 3);
        args[i].oc_end = 2 * ((64 * (i + 1)) / 3);
        args[i].use_neon = use_neon; args[i].input_scale = input_scale;
        args[i].pw_scale = pw_scale; args[i].output_scale = output_scale;
        args[i].status = 0;
    }
    status = run_stage(args, dw_worker);
    if (dw_ms) *dw_ms = wall_time_ms() - started;
    if (status == 0) {
        started = wall_time_ms();
        status = run_stage(args, pw_worker);
        if (pw_ms) *pw_ms = wall_time_ms() - started;
    }
    free(mid);
    free(padded);
    return status;
}

EXPORT int cnn_v10_n1_infer_int16_hcw(const unsigned char *p, size_t bytes,
                                      const int16_t *input, int16_t *output)
{
    return infer_impl(p, bytes, input, output, 1, NULL, NULL);
}

EXPORT int cnn_v10_n1_infer_int16_hcw_scalar(const unsigned char *p, size_t bytes,
                                             const int16_t *input, int16_t *output)
{
    return infer_impl(p, bytes, input, output, 0, NULL, NULL);
}

EXPORT int cnn_v10_n1_infer_int16_hcw_profile(const unsigned char *p, size_t bytes,
                                              const int16_t *input, int16_t *output,
                                              double *dw_ms, double *pw_ms)
{
    if (!dw_ms || !pw_ms) return -1;
    return infer_impl(p, bytes, input, output, 1, dw_ms, pw_ms);
}

EXPORT int cnn_v10_n1_native_abi_version(void) { return 1; }
