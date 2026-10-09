#pragma once

#include <ap_int.h>
#include "cnn_v10_gelu.hpp"

namespace cnn_v10 {

// Exact fixed-model codec: 32 adjacent int16 values have a span <= 255.
// Store their minimum once and each original low byte. Subtraction modulo
// 256 reconstructs the unsigned distance from that minimum. No interpolation,
// approximate GELU, variable-length search or multiplier is involved.
// The raw DDR parameter ABI is unchanged. Preflight MUST reject a wider span
// before starting any activation traffic; the loader does not silently fall
// back to a truncated representation.
static const unsigned kGeluSegmentShift = 5;
static const unsigned kGeluSegmentEntries = 1u << kGeluSegmentShift;
static const unsigned kGeluSegments =
    (kGeluStorageEntries + kGeluSegmentEntries - 1) / kGeluSegmentEntries;

struct SegmentedGelu {
    ap_int<16> base[kGeluSegments];
    ap_uint<8> low[kGeluStorageEntries];

    ap_int<16> lookup(unsigned index) const {
#pragma HLS INLINE
        const ap_int<16> anchor = base[index >> kGeluSegmentShift];
        const ap_uint<8> delta = low[index] - ap_uint<8>(anchor);
        const ap_int<17> value = ap_int<17>(anchor) + ap_int<17>(delta);
        return ap_int<16>(value);
    }
};

// Validate the exact representation on raw 128-bit DDR words. The retained
// interval can end with 8/16/24 values in its final segment. Parameters are
// immutable from preflight through job completion (driver ownership contract).
static inline bool segmented_gelu_valid(const ap_uint<128>* raw,
                                        unsigned offset, unsigned words) {
#pragma HLS INLINE off
    if (words == 0 || words > kGeluStorageWords) return false;
    ap_int<16> segment_min = 32767, segment_max = -32768;
    bool valid = true;
    for (unsigned word = 0; word < words; ++word) {
#pragma HLS PIPELINE II=1
        const ap_uint<128> packed = raw[offset + word];
        ap_int<16> word_min = 32767, word_max = -32768;
        for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
            const ap_int<16> value = packed.range(lane * 16 + 15, lane * 16);
            if (value < word_min) word_min = value;
            if (value > word_max) word_max = value;
        }
        if ((word & 3u) == 0) {
            segment_min = word_min;
            segment_max = word_max;
        } else {
            if (word_min < segment_min) segment_min = word_min;
            if (word_max > segment_max) segment_max = word_max;
        }
        if ((word & 3u) == 3u || word + 1 == words) {
            const ap_int<17> span = ap_int<17>(segment_max) -
                                    ap_int<17>(segment_min);
            valid = valid && (span <= 255);
        }
    }
    return valid;
}

// Same 32-word requests and one unpacked entry per iteration as load_i16.
// The segment minimum is published only after its final entry. Compute starts
// after this loader returns, so no consumer observes an incomplete directory.
template<typename Reader>
static void load_segmented_gelu(Reader& reader, unsigned offset,
                                unsigned count, SegmentedGelu& table) {
#pragma HLS INLINE off
    const unsigned words = count / 8;
    ap_int<16> minimum = 32767;
    for (unsigned pos = 0; pos < words; pos += 32) {
#pragma HLS LOOP_FLATTEN off
        const unsigned length = words - pos < 32 ? words - pos : 32;
        reader.request(offset + pos, length);
        for (unsigned word = 0; word < length; ++word) {
            const ap_uint<128> packed = reader.read();
            for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS PIPELINE II=1
                const unsigned index = (pos + word) * 8 + lane;
                const ap_int<16> value = packed.range(lane * 16 + 15, lane * 16);
                if ((index & 31u) == 0) minimum = value;
                else if (value < minimum) minimum = value;
                table.low[index] = ap_uint<8>(value);
                if ((index & 31u) == 31u || index + 1 == count)
                    table.base[index >> kGeluSegmentShift] = minimum;
            }
        }
    }
}

static inline ap_int<16> segmented_folded_gelu(ap_int<16> q,
                                              const SegmentedGelu& table) {
#pragma HLS INLINE
    if (q < 0) {
        const ap_uint<16> index = ap_uint<16>(q) + ap_uint<16>(32768);
        return table.lookup(unsigned(index));
    }
    if (q == 0) return 0;
    const ap_uint<16> index = ap_uint<16>(32768) - ap_uint<16>(q);
    const ap_int<17> value = ap_int<17>(q) +
                              ap_int<17>(table.lookup(unsigned(index)));
    return ap_int<16>(value);
}

}  // namespace cnn_v10
