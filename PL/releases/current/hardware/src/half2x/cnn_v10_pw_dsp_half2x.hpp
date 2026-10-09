#pragma once

#ifndef AP_INT_MAX_W
#define AP_INT_MAX_W 2048
#endif

#include <ap_int.h>

// Experimental replacement for the frozen 16-DSP PW leaf.  pw_fast_clk and
// pw_fast_rst are ordinary one-bit C parameters only so Vitis HLS can carry
// the related 2x clock/reset through the generated hierarchy.  The blackbox
// metadata maps them directly to RTL wires; generated RTL must prove there is
// no intervening register or AXI-Lite transport before this candidate may be
// integrated into the full kernel.
ap_int<48> cnn_v10_pw_dsp16_half2x_hls(
    ap_uint<1> pw_fast_clk,
    ap_uint<1> pw_fast_rst,
    ap_int<48> prior,
    ap_int<16> value0,  ap_int<16> weight0,
    ap_int<16> value1,  ap_int<16> weight1,
    ap_int<16> value2,  ap_int<16> weight2,
    ap_int<16> value3,  ap_int<16> weight3,
    ap_int<16> value4,  ap_int<16> weight4,
    ap_int<16> value5,  ap_int<16> weight5,
    ap_int<16> value6,  ap_int<16> weight6,
    ap_int<16> value7,  ap_int<16> weight7,
    ap_int<16> value8,  ap_int<16> weight8,
    ap_int<16> value9,  ap_int<16> weight9,
    ap_int<16> value10, ap_int<16> weight10,
    ap_int<16> value11, ap_int<16> weight11,
    ap_int<16> value12, ap_int<16> weight12,
    ap_int<16> value13, ap_int<16> weight13,
    ap_int<16> value14, ap_int<16> weight14,
    ap_int<16> value15, ap_int<16> weight15);

template<typename Pixel, typename Tile>
static inline ap_int<48> cnn_v10_pw_dsp16_half2x_call(
    ap_uint<1> pw_fast_clk, ap_uint<1> pw_fast_rst,
    ap_int<48> prior, const Pixel values[16], const Tile& weights,
    unsigned output_lane) {
#pragma HLS INLINE
    const unsigned base = output_lane * 256;
    return cnn_v10_pw_dsp16_half2x_hls(
        pw_fast_clk, pw_fast_rst, prior,
        values[0],  ap_int<16>(weights.range(base + 15,  base)),
        values[1],  ap_int<16>(weights.range(base + 31,  base + 16)),
        values[2],  ap_int<16>(weights.range(base + 47,  base + 32)),
        values[3],  ap_int<16>(weights.range(base + 63,  base + 48)),
        values[4],  ap_int<16>(weights.range(base + 79,  base + 64)),
        values[5],  ap_int<16>(weights.range(base + 95,  base + 80)),
        values[6],  ap_int<16>(weights.range(base + 111, base + 96)),
        values[7],  ap_int<16>(weights.range(base + 127, base + 112)),
        values[8],  ap_int<16>(weights.range(base + 143, base + 128)),
        values[9],  ap_int<16>(weights.range(base + 159, base + 144)),
        values[10], ap_int<16>(weights.range(base + 175, base + 160)),
        values[11], ap_int<16>(weights.range(base + 191, base + 176)),
        values[12], ap_int<16>(weights.range(base + 207, base + 192)),
        values[13], ap_int<16>(weights.range(base + 223, base + 208)),
        values[14], ap_int<16>(weights.range(base + 239, base + 224)),
        values[15], ap_int<16>(weights.range(base + 255, base + 240)));
}
