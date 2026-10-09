#pragma once
#include <ap_int.h>

namespace cnn_v10 {

// Floor division plus guard/sticky is exact for signed two's complement,
// including negative ties. Each selected constant shift retains the highest
// discarded bit and OR-reduces everything below it. There is no absolute-value,
// shifted-back remainder, 80-bit half comparator, or final sign restoration.
// Unrolling exposes six registered-schedulable barrel stages to HLS; the caller
// retains II=1. Shift zero naturally has no guard and no rounding increment.
inline ap_int<80> round_even(ap_int<80> product, ap_uint<6> shift) {
#pragma HLS INLINE
    ap_int<80> q=product;
    bool guard=false,sticky=false;
    for(unsigned stage=0;stage<6;++stage) {
#pragma HLS UNROLL
        const unsigned distance=1u<<stage;
        if(shift[stage]) {
            bool low=false;
            // Constant-width reduction after unrolling; no variable mask.
            for(unsigned bit=0;bit<distance-1;++bit) {
#pragma HLS UNROLL
                low=low||q[bit];
            }
            sticky=sticky||guard||low;
            guard=q[distance-1];
            q=q>>distance;
        }
    }
    if(guard&&(sticky||q[0])) ++q;
    return q;
}

inline ap_int<80> scale(ap_int<48> value,ap_int<32> multiplier,ap_uint<6> shift) {
#pragma HLS INLINE
    ap_int<80> product=value*multiplier;
#pragma HLS BIND_OP variable=product op=mul impl=dsp latency=3
    return round_even(product,shift);
}

inline ap_int<80> scale_narrow(ap_int<16> value,ap_int<32> multiplier,
                               ap_uint<6> shift) {
#pragma HLS INLINE
    ap_int<48> product=value*multiplier;
#pragma HLS BIND_OP variable=product op=mul impl=dsp latency=3
    return round_even(ap_int<80>(product),shift);
}
} // namespace cnn_v10

