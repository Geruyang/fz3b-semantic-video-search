#include "cnn_v10_pw_dsp_half2x.hpp"

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
    ap_int<16> value15, ap_int<16> weight15) {
    (void)pw_fast_clk;
    (void)pw_fast_rst;
    ap_int<80> sum = prior;
#define CNN_V10_PW_HALF2X_TERM(I) \
    sum += ap_int<32>(value##I) * ap_int<32>(weight##I)
    CNN_V10_PW_HALF2X_TERM(0);  CNN_V10_PW_HALF2X_TERM(1);
    CNN_V10_PW_HALF2X_TERM(2);  CNN_V10_PW_HALF2X_TERM(3);
    CNN_V10_PW_HALF2X_TERM(4);  CNN_V10_PW_HALF2X_TERM(5);
    CNN_V10_PW_HALF2X_TERM(6);  CNN_V10_PW_HALF2X_TERM(7);
    CNN_V10_PW_HALF2X_TERM(8);  CNN_V10_PW_HALF2X_TERM(9);
    CNN_V10_PW_HALF2X_TERM(10); CNN_V10_PW_HALF2X_TERM(11);
    CNN_V10_PW_HALF2X_TERM(12); CNN_V10_PW_HALF2X_TERM(13);
    CNN_V10_PW_HALF2X_TERM(14); CNN_V10_PW_HALF2X_TERM(15);
#undef CNN_V10_PW_HALF2X_TERM
    return ap_int<48>(sum);
}
