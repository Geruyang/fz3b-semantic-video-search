#include <ap_int.h>
#include "cnn_v10_pw_dsp_half2x.hpp"

void pw_half2x_blackbox_smoke(
    ap_uint<1> pw_fast_clk,
    ap_uint<1> pw_fast_rst,
    const ap_int<16> values[64],
    const ap_int<16> weights[64],
    const ap_int<48> priors[4],
    ap_int<48> results[4]) {
#pragma HLS INTERFACE mode=ap_stable port=pw_fast_clk
#pragma HLS INTERFACE mode=ap_stable port=pw_fast_rst
#pragma HLS INTERFACE mode=ap_memory port=values
#pragma HLS INTERFACE mode=ap_memory port=weights
#pragma HLS INTERFACE mode=ap_memory port=priors
#pragma HLS INTERFACE mode=ap_memory port=results
#pragma HLS INTERFACE mode=ap_ctrl_hs port=return
#pragma HLS ARRAY_PARTITION variable=values complete dim=1
#pragma HLS ARRAY_PARTITION variable=weights complete dim=1
#pragma HLS ARRAY_PARTITION variable=priors complete dim=1
#pragma HLS ARRAY_PARTITION variable=results complete dim=1
    for (unsigned n=0;n<4;++n) {
#pragma HLS PIPELINE II=1
        results[n]=cnn_v10_pw_dsp16_half2x_hls(
            pw_fast_clk,pw_fast_rst,priors[n],
            values[n*16+0],weights[n*16+0], values[n*16+1],weights[n*16+1],
            values[n*16+2],weights[n*16+2], values[n*16+3],weights[n*16+3],
            values[n*16+4],weights[n*16+4], values[n*16+5],weights[n*16+5],
            values[n*16+6],weights[n*16+6], values[n*16+7],weights[n*16+7],
            values[n*16+8],weights[n*16+8], values[n*16+9],weights[n*16+9],
            values[n*16+10],weights[n*16+10], values[n*16+11],weights[n*16+11],
            values[n*16+12],weights[n*16+12], values[n*16+13],weights[n*16+13],
            values[n*16+14],weights[n*16+14], values[n*16+15],weights[n*16+15]);
    }
}
