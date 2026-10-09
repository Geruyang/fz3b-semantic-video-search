#pragma once

#include <ap_int.h>
#include <hls_stream.h>
#include "cnn_v10_arithmetic.hpp"
#ifndef __SYNTHESIS__
#include <cassert>
#endif

namespace cnn_v10 {

struct ScaleRequest {
    ap_int<48> value;
    ap_int<32> multiplier;
    ap_uint<6> shift;
    ap_uint<1> end;
    ScaleRequest() : value(0), multiplier(0), shift(0), end(0) {}
    ScaleRequest(ap_int<48> v, ap_int<32> m, ap_uint<6> s)
        : value(v), multiplier(m), shift(s), end(0) {}
};

typedef ap_int<16> ScaleResponse;
typedef ap_uint<1> ScaleCredit;

// Preserve the historical post-rounding saturation exactly.  The service
// performs the complete 48x32 multiply and round-even operation first; only
// that final rounded value is narrowed for the response transport.
inline ScaleResponse scale_response(ap_int<48> value,ap_int<32> multiplier,
                                    ap_uint<6> shift) {
#pragma HLS INLINE
    const ap_int<80> rounded=scale(value,multiplier,shift);
    return rounded>32767 ? ScaleResponse(32767) :
           rounded< -32767 ? ScaleResponse(-32767) : ScaleResponse(rounded);
}

// A fixed client port is the routing tag. FIFO ordering preserves pixel order;
// finishing every client drains the block epoch before the next invocation.
// A request reserves a response slot until the client actually consumes it,
// including the multiplier/rounding pipeline's in-flight transactions.
class ScaleClient {
public:
    ScaleClient(hls::stream<ScaleRequest>& requests,
                hls::stream<ScaleResponse>& responses,
                hls::stream<ScaleCredit>& returns)
        : requests_(requests), responses_(responses), returns_(returns)
#ifndef __SYNTHESIS__
        , outstanding_(0), ended_(false)
#endif
        {}

    void request(ap_int<48> value, ap_int<32> multiplier, ap_uint<6> shift) {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!ended_);
        assert(shift <= 62);
#endif
        requests_.write(ScaleRequest(value, multiplier, shift));
#ifndef __SYNTHESIS__
        ++outstanding_;
#endif
    }

    ScaleResponse response() {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!ended_ && outstanding_ != 0);
#endif
        ScaleResponse value = responses_.read();
        returns_.write(ScaleCredit(1));
#ifndef __SYNTHESIS__
        --outstanding_;
#endif
        return value;
    }

    bool try_request(ap_int<48> value, ap_int<32> multiplier, ap_uint<6> shift) {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!ended_ && shift <= 62);
#endif
        const bool sent = requests_.write_nb(ScaleRequest(value, multiplier, shift));
#ifndef __SYNTHESIS__
        if (sent) ++outstanding_;
#endif
        return sent;
    }

    bool try_response(ScaleResponse& value) {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!ended_);
#endif
        // Never consume a response unless its credit can also be returned.
        // Only this client writes returns_, so a successful full check cannot
        // race another producer. This keeps an empty response FIFO from
        // blocking request issue when both are in one HLS pipeline iteration.
        if (returns_.full()) return false;
        ScaleResponse candidate;
        if (!responses_.read_nb(candidate)) return false;
#ifndef __SYNTHESIS__
        assert(outstanding_ != 0);
#endif
        returns_.write(ScaleCredit(1));
        value = candidate;
#ifndef __SYNTHESIS__
        --outstanding_;
#endif
        return true;
    }

    void finish() {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!ended_ && outstanding_ == 0);
#endif
        ScaleRequest end;
        end.end = 1;
        requests_.write(end);
#ifndef __SYNTHESIS__
        ended_ = true;
#endif
    }

private:
    hls::stream<ScaleRequest>& requests_;
    hls::stream<ScaleResponse>& responses_;
    hls::stream<ScaleCredit>& returns_;
#ifndef __SYNTHESIS__
    // Native contract assertions only: synthesizing these otherwise-unused
    // counters creates a false 32-bit feedback path across HLS subfunctions.
    // Hardware safety is provided by the service's real response credits and
    // the caller's bounded sent/received counters.
    unsigned outstanding_;
    bool ended_;
#endif
};

// Instantiate once for each core (distinct CORE_ID), never once for both cores.
// Integration contract: each response FIFO has at least CREDITS entries and
// returns is written exactly once for each consumed response, never on issue.
// Producers must overlap issue/consume or limit their issue batches; an entire
// image cannot be queued before reading any responses from a bounded service.
template<int CORE_ID, int N = 3, int CREDITS = 16>
void scale_service(hls::stream<ScaleRequest> (&requests)[N],
                   hls::stream<ScaleResponse> (&responses)[N],
                   hls::stream<ScaleCredit> (&returns)[N]) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=requests complete dim=1
#pragma HLS ARRAY_PARTITION variable=responses complete dim=1
#pragma HLS ARRAY_PARTITION variable=returns complete dim=1
    static_assert(N > 0 && N <= 3, "one scale service supports up to three clients");
    static_assert(CREDITS > 0 && CREDITS <= 31, "five-bit credit counter capacity");
    ScaleRequest pending[N];
    ap_uint<1> valid[N], ended[N], credit_ok[N];
    ap_uint<5> available[N];
#pragma HLS ARRAY_PARTITION variable=pending complete dim=1
#pragma HLS ARRAY_PARTITION variable=valid complete dim=1
#pragma HLS ARRAY_PARTITION variable=ended complete dim=1
#pragma HLS ARRAY_PARTITION variable=credit_ok complete dim=1
#pragma HLS ARRAY_PARTITION variable=available complete dim=1
    for (int i = 0; i < N; ++i) {
#pragma HLS UNROLL
        valid[i] = 0;
        ended[i] = 0;
        available[i] = CREDITS;
        credit_ok[i] = 1;
    }
    // One-hot priority avoids a 32-bit add/modulo and dynamic array mux in
    // the loop-carried arbiter path. All array indices below are constants
    // after unrolling (N is at most three).
    ap_uint<N> priority = 1;
    bool done = false;
scale_service_loop:
    while (!done) {
#pragma HLS PIPELINE II=1
        ap_uint<N> eligible = 0, grant = 0;
        done = true;
        for (int i = 0; i < N; ++i) {
#pragma HLS UNROLL
            // Use only state from the preceding iteration. A returned credit
            // or newly prefetched request becomes eligible next cycle; neither
            // FIFO's combinational output feeds the arbitration feedback path.
#ifndef __SYNTHESIS__
            assert(bool(credit_ok[i]) == (available[i] != 0));
#endif
            eligible[i] = valid[i] && (pending[i].end || credit_ok[i]);
            done = done && ended[i] && !valid[i] && available[i] == CREDITS;
        }
        if (N == 3) {
            // Explicit three-way equations avoid chained bit-slice updates
            // becoming priority muxes in the feedback path.
            const bool e0 = eligible[0], e1 = eligible[1], e2 = eligible[2];
            grant[0] = e0 && (priority[0] || (priority[1] && !e1 && !e2) ||
                             (priority[2] && !e2));
            grant[1] = e1 && (priority[1] || (priority[2] && !e2 && !e0) ||
                             (priority[0] && !e0));
            grant[2] = e2 && (priority[2] || (priority[0] && !e0 && !e1) ||
                             (priority[1] && !e1));
        } else {
          for (int start = 0; start < N; ++start) {
#pragma HLS UNROLL
            bool earlier = false;
            for (int distance = 0; distance < N; ++distance) {
#pragma HLS UNROLL
                const int index = (start + distance) % N;
                grant[index] = bool(grant[index]) ||
                    (priority[start] && eligible[index] && !earlier);
                earlier = earlier || eligible[index];
            }
          }
        }
        if (grant != 0) priority = (grant << 1) | (grant >> (N - 1));

        ScaleRequest request;
        ap_uint<N> issue = 0;
        for (int i = 0; i < N; ++i) {
#pragma HLS UNROLL
            const bool selected = grant[i];
            const bool stop = selected && pending[i].end;
            const bool send = selected && !pending[i].end;
            issue[i] = send;
            if (send) {
                request.value |= pending[i].value;
                request.multiplier |= pending[i].multiplier;
                request.shift |= pending[i].shift;
            }
            ScaleCredit credit;
            const bool returned = returns[i].read_nb(credit);
#ifndef __SYNTHESIS__
            if (returned) assert(credit == 1 && available[i] < CREDITS);
#endif
            if (returned != send) {
                // The eligibility flip-flop changes only at zero/one. Its
                // feedback avoids an adder followed by a nonzero comparator.
                if (returned) {
                    if (available[i] == 0) credit_ok[i] = 1;
                    ++available[i];
                } else {
                    if (available[i] == 1) credit_ok[i] = 0;
                    --available[i];
                }
            }
            // Refill a consumed prefetch register without adding a bubble for
            // a busy client. An end marker is never followed by another read.
            if (stop) ended[i] = 1;
            if (selected) valid[i] = 0;
            if (!ended[i] && !valid[i]) {
                ScaleRequest candidate;
                if (requests[i].read_nb(candidate)) {
                    pending[i] = candidate;
                    valid[i] = 1;
                }
            }
        }
        if (issue != 0) {
            // Single syntactic arithmetic call; one shared multiplier chain.
            ScaleResponse result = scale_response(request.value,
                                                  request.multiplier,
                                                  request.shift);
            for (int i = 0; i < N; ++i) {
#pragma HLS UNROLL
                if (issue[i]) responses[i].write(result);
            }
        }
    }
}

} // namespace cnn_v10
