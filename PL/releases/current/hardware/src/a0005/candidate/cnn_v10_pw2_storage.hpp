#pragma once

#ifndef AP_INT_MAX_W
#define AP_INT_MAX_W 2048
#endif
#include <ap_int.h>
#ifndef __SYNTHESIS__
#include <cassert>
#endif

#include "cnn_v10_storage_helpers.hpp"

namespace cnn_v10_candidate {

typedef ap_uint<160> Pw2StoredColumn;

static inline ap_int<40> pw2_narrow_exact(ap_int<48> value) {
#pragma HLS INLINE
    const ap_int<40> narrowed=value;
#ifndef __SYNTHESIS__
    assert(pw2_signed40_fits(static_cast<long long>(value)));
    assert(value==ap_int<48>(narrowed));
#endif
    return narrowed;
}

static inline ap_int<48> pw2_expand_lane(const Pw2StoredColumn& packed,
                                         unsigned lane) {
#pragma HLS INLINE
    const ap_int<40> stored=packed.range(lane*40+39,lane*40);
    return ap_int<48>(stored);
}

static inline Pw2StoredColumn pw2_pack_column(const ap_int<48> values[4]) {
#pragma HLS INLINE
    Pw2StoredColumn packed=0;
    for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
        packed.range(lane*40+39,lane*40)=
            ap_uint<40>(pw2_narrow_exact(values[lane]));
    }
    return packed;
}

}  // namespace cnn_v10_candidate
