#pragma once

#ifndef AP_INT_MAX_W
#define AP_INT_MAX_W 2048
#endif

#include <ap_int.h>

namespace cnn_v10 {

// Candidate ABI10.4 profile 3 (N1 transition).  Offsets and lengths are in
// 128-bit words.  The external packer owns byte serialization; hardware keeps
// the existing signed INT16 containers and signed48/signed80 arithmetic.
static const unsigned kN1Profile = 3;
static const unsigned kN1Blocks = 1;
static const unsigned kN1InputChannels = 64;
static const unsigned kN1InputWidth = 64;
static const unsigned kN1OutputChannels = 128;
static const unsigned kN1OutputWidth = 32;
static const unsigned kN1SlotWords = 32768;
static const unsigned kN1OutputWords = 16384;
// A0004 restores q3/q7/expanded to bounded on-chip FIFOs.  The external arena
// therefore contains only the two reusable 32768-word slots and the 4096-word
// residual scratch region.
static const unsigned kN1ArenaWords = 69632;
static const unsigned kN1ParamWords = 11280;

static const unsigned kN1DwWeightOffset = 0;
static const unsigned kN1DwWeightWords = 784;
static const unsigned kN1DwBiasOffset = 784;
static const unsigned kN1DwBiasWords = 64;
static const unsigned kN1DwMultiplierOffset = 848;
static const unsigned kN1DwMultiplierWords = 32;
static const unsigned kN1DwShiftOffset = 880;
static const unsigned kN1DwShiftWords = 32;
static const unsigned kN1DwGeluOffset = 912;
static const unsigned kN1FoldedGeluWords = 4096;

static const unsigned kN1PwWeightOffset = 5008;
static const unsigned kN1PwWeightWords = 2048;
static const unsigned kN1PwBiasOffset = 7056;
static const unsigned kN1PwBiasWords = 64;
static const unsigned kN1PwMultiplierOffset = 7120;
static const unsigned kN1PwMultiplierWords = 32;
static const unsigned kN1PwShiftOffset = 7152;
static const unsigned kN1PwShiftWords = 32;
static const unsigned kN1PwGeluOffset = 7184;

static_assert(kN1PwGeluOffset + kN1FoldedGeluWords == kN1ParamWords,
              "N1 parameter layout must exactly fill params_words");
static_assert(kN1OutputWords <= kN1SlotWords,
              "N1 valid output must fit the reusable slot");

// T is the negative half of a full signed-int16-domain GELU LUT:
// T[0] maps -32768 and T[32767] maps -1.  The independently proven identity
// full(+q) == q + full(-q), q=1..32767, reconstructs the positive half with
// a 17-bit sum.  q==0 is exactly zero.
static inline ap_int<16> n1_folded_gelu(ap_int<16> q,
                                       const ap_int<16>* negative_half) {
#pragma HLS INLINE
    if (q < 0) {
        const ap_uint<16> index = ap_uint<16>(q) + ap_uint<16>(32768);
        return negative_half[unsigned(index)];
    }
    if (q == 0) return 0;
    const ap_uint<16> index = ap_uint<16>(32768) - ap_uint<16>(q);
    const ap_int<17> reconstructed = ap_int<17>(q) +
                                     ap_int<17>(negative_half[unsigned(index)]);
    return ap_int<16>(reconstructed);
}

}  // namespace cnn_v10
