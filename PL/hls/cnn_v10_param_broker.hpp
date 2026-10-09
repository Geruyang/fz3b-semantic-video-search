#pragma once

#ifndef AP_INT_MAX_W
#define AP_INT_MAX_W 2048
#endif

#include <ap_int.h>
#include <hls_stream.h>

#ifndef __SYNTHESIS__
#include <cassert>
#endif

namespace cnn_v10 {

typedef ap_uint<128> ParamWord;

// All offsets and counts are expressed in 128-bit words.  An end command has
// count == 0 and carries no response data.
struct ReadCmd {
    ap_uint<32> offset;
    ap_uint<6> count;
    ap_uint<1> end;

    ReadCmd() : offset(0), count(0), end(0) {}
    ReadCmd(ap_uint<32> request_offset, ap_uint<6> request_count,
            ap_uint<1> request_end = 0)
        : offset(request_offset), count(request_count), end(request_end) {}
};

// A consumer may have only one request in flight.  Explicit request sizes keep
// the final short window inside the caller's parameter extent; there is no
// implicit cache-line fill beyond the requested words.
class ParamReader {
public:
    ParamReader(hls::stream<ReadCmd>& commands,
                hls::stream<ParamWord>& responses)
        : commands_(commands), responses_(responses), remaining_(0), finished_(0) {}

    void request(ap_uint<32> offset, unsigned count) {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!finished_);
        assert(remaining_ == 0);
        assert(count >= 1 && count <= 32);
#endif
        commands_.write(ReadCmd(offset, ap_uint<6>(count), 0));
        remaining_ = ap_uint<6>(count);
    }

    ParamWord read() {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!finished_);
        assert(remaining_ != 0);
#endif
        ParamWord value = responses_.read();
        --remaining_;
        return value;
    }

    void finish() {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!finished_);
        assert(remaining_ == 0);
#endif
        commands_.write(ReadCmd(0, 0, 1));
        finished_ = 1;
    }

private:
    hls::stream<ReadCmd>& commands_;
    hls::stream<ParamWord>& responses_;
    ap_uint<6> remaining_;
    ap_uint<1> finished_;
};

namespace detail {

template<int N>
void write_selected(hls::stream<ParamWord> (&responses)[N], int selected,
                    const ParamWord& value) {
#pragma HLS INLINE
    // The unrolled loop gives every stream a constant hardware index.  Only
    // the selected stream observes a write transaction.
    for (int i = 0; i < N; ++i) {
#pragma HLS UNROLL
        if (selected == i) responses[i].write(value);
    }
}

} // namespace detail

// One broker is the sole AXI reader for a parameter bundle.  Each input gets a
// one-command holding register.  Arbitration is round-robin at command
// granularity, so a continuously requesting input cannot starve another input;
// the maximum service quantum is 32 words.
//
// ParamReader permits exactly one request in flight and every response FIFO at
// the top level has depth 32.  Therefore the selected response FIFO is empty
// when a request starts and can hold the entire 1..32-word response even if its
// consumer is temporarily descheduled.  The response FIFO itself is the
// bounded prefetch buffer; no second bank or spill path is needed.  Any future
// overlapping-request client or response FIFO shallower than 32 must replace
// this broker contract rather than silently reusing it.
template<int N>
void param_broker(const ParamWord* params,
                  hls::stream<ReadCmd> (&commands)[N],
                  hls::stream<ParamWord> (&responses)[N]) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=commands complete dim=1
#pragma HLS ARRAY_PARTITION variable=responses complete dim=1
    static_assert(N > 0, "param_broker requires at least one consumer");

    ReadCmd pending[N];
    ap_uint<1> pending_valid[N];
    ap_uint<1> ended[N];
#pragma HLS ARRAY_PARTITION variable=pending complete dim=1
#pragma HLS ARRAY_PARTITION variable=pending_valid complete dim=1
#pragma HLS ARRAY_PARTITION variable=ended complete dim=1

    for (int i = 0; i < N; ++i) {
#pragma HLS UNROLL
        pending_valid[i] = 0;
        ended[i] = 0;
    }

    unsigned round_robin = 0;
    unsigned ended_count = 0;
    while (ended_count != unsigned(N)) {
        // read_nb is applied only at constant stream indices after unrolling;
        // dynamic selection is confined to ordinary partitioned registers.
        for (int i = 0; i < N; ++i) {
#pragma HLS UNROLL
            if (!ended[i] && !pending_valid[i]) {
                ReadCmd candidate;
                if (commands[i].read_nb(candidate)) {
                    pending[i] = candidate;
                    pending_valid[i] = 1;
                }
            }
        }

        int selected = -1;
        for (int distance = 0; distance < N; ++distance) {
            unsigned index = round_robin + unsigned(distance);
            if (index >= unsigned(N)) index -= unsigned(N);
            if (selected < 0 && pending_valid[index]) selected = int(index);
        }

        if (selected < 0) continue;

        ReadCmd command = pending[selected];
        pending_valid[selected] = 0;
        round_robin = unsigned(selected + 1);
        if (round_robin == unsigned(N)) round_robin = 0;

        if (command.end) {
#ifndef __SYNTHESIS__
            assert(command.count == 0);
#endif
            ended[selected] = 1;
            ++ended_count;
            continue;
        }

#ifndef __SYNTHESIS__
        assert(command.count >= 1 && command.count <= 32);
#endif
        const unsigned count = unsigned(command.count);
        const unsigned offset = unsigned(command.offset);
    read_parameter_burst:
        for (unsigned word = 0; word < count; ++word) {
#pragma HLS PIPELINE II=1
            const ParamWord incoming = params[offset + word];
            detail::write_selected<N>(responses,selected,incoming);
        }
    }
}

enum Param1Consumer {
    PARAM1_DW3_METADATA = 0,
    PARAM1_DW7_METADATA = 1,
    PARAM1_PW1_METADATA = 2,
    PARAM1_PW1_WEIGHTS = 3,
    PARAM1_CONSUMERS = 4
};

enum Param2Consumer {
    PARAM2_PW2_METADATA = 0,
    PARAM2_PW2_WEIGHTS = 1,
    PARAM2_CONSUMERS = 2
};

} // namespace cnn_v10

