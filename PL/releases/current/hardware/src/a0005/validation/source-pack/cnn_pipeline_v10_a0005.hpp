#pragma once
#ifndef AP_INT_MAX_W
#define AP_INT_MAX_W 2048
#endif
#include <ap_int.h>
#include <hls_stream.h>
#include <hls_burst_maxi.h>
#include "cnn_v10_n1.hpp"
#ifndef __SYNTHESIS__
#include <cassert>
#endif

namespace cnn_v10 {

// A completion token carries exactly the legal block/row ranges used by all
// four profiles: block < 32 and row < 64.  Keeping packing in one helper makes
// the producer/consumer contract identical for normal and P3 transition rows.
typedef ap_uint<11> RowReadyToken;

static inline RowReadyToken pack_row_ready(unsigned block,unsigned row) {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
    assert(block<32 && row<64);
#endif
    RowReadyToken token=0;
    token.range(10,6)=ap_uint<5>(block);
    token.range(5,0)=ap_uint<6>(row);
    return token;
}

static inline unsigned row_ready_block(RowReadyToken token) {
#pragma HLS INLINE
    return unsigned(token.range(10,6));
}

static inline unsigned row_ready_row(RowReadyToken token) {
#pragma HLS INLINE
    return unsigned(token.range(5,0));
}

} // namespace cnn_v10

// ABI10.x uses compact GELU storage and 4-output x 16-reduction PW tiles.
// Addresses/counts below are 128-bit words; image rows are HCW signed16.
static inline unsigned cnn_v10_pw_words(unsigned outputs, unsigned inputs) {
    return (outputs/4)*(inputs/16)*8;
}
static inline unsigned cnn_v10_pw1_offset(unsigned c) {
    return c==128?8793:c==256?10553:7913;
}
static inline unsigned cnn_v10_pw2_offset(unsigned c) {
    return c==128?14937:c==256?35129:9449;
}
static inline unsigned cnn_v10_stride(unsigned c) {
    return c==128?21081:c==256?59705:10985;
}
static inline unsigned cnn_v10_weight_tiles(unsigned c,bool final) {
    return final ? (c/4)*((3*c)/16) : ((3*c)/4)*(c/16);
}
static inline unsigned cnn_v10_bias_offset(unsigned c) {return c==128?928:c==256?1856:464;}
static inline unsigned cnn_v10_gelu_offset(unsigned c) {return c==128?1761:c==256?3521:881;}
static inline unsigned cnn_v10_row_shift(unsigned w) {return w==64?6:w==32?5:4;}
static inline unsigned cnn_v10_oc_groups(unsigned oc) { return oc/4; }
// Profiles 0..2 run the paired normal stages. Profile 3 runs the two-stage
// N1 transition while preserving the same paired-image AXI/control envelope.
static inline unsigned cnn_v10_channels(unsigned p) {return p==0?128:p==1?256:p==2?64:cnn_v10::kN1InputChannels;}
static inline unsigned cnn_v10_width(unsigned p) {return p==0?32:p==1?16:p==2?64:cnn_v10::kN1InputWidth;}
static inline unsigned cnn_v10_max_blocks(unsigned p) {return p==0?12:p==1?20:p==2?4:p==3?1:0;}
static inline unsigned cnn_v10_slot_words(unsigned p) {
    return p==0?16384:p==1?8192:p==2?32768:cnn_v10::kN1SlotWords;
}
static const unsigned CNN_V10_SCRATCH_CHUNK_WORDS = 1024;
static const unsigned CNN_V10_SCRATCH_CHUNKS = 4;
static const unsigned CNN_V10_SCRATCH_WORDS =
    CNN_V10_SCRATCH_CHUNK_WORDS*CNN_V10_SCRATCH_CHUNKS;
static inline unsigned cnn_v10_arena_words(unsigned p) {
    return 2*cnn_v10_slot_words(p)+CNN_V10_SCRATCH_WORDS;
}

// Trace: bit31 active, bits23:16 block, bits15:8 row, bits7:0 phase.
// These are explicit live debug ports, not new control-register fields.
void cnn_pipeline_v10(const ap_uint<128>* params_pw1,
                     const ap_uint<128>* params_pw2,
                     const ap_uint<128>* activation_a_rd,
                     hls::burst_maxi<ap_uint<128> > activation_a_wr,
                     const ap_uint<128>* activation_b_rd,
                     hls::burst_maxi<ap_uint<128> > activation_b_wr,
                     unsigned profile, unsigned block_count,
                     unsigned params_words, unsigned slot_words,
                     unsigned arena_words, unsigned flags,
                     unsigned& protocol_error,
                     volatile ap_uint<32>& trace_a_feed, volatile ap_uint<32>& trace_a_dw3,
                     volatile ap_uint<32>& trace_a_dw7, volatile ap_uint<32>& trace_a_pw1,
                     volatile ap_uint<32>& trace_a_pw2, volatile ap_uint<32>& trace_a_write,
                     volatile ap_uint<32>& trace_b_feed, volatile ap_uint<32>& trace_b_dw3,
                     volatile ap_uint<32>& trace_b_dw7, volatile ap_uint<32>& trace_b_pw1,
                     volatile ap_uint<32>& trace_b_pw2, volatile ap_uint<32>& trace_b_write);

