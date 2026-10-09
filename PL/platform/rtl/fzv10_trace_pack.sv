module fzv10_trace_pack (
    input  logic [31:0] trace_a_feed,
    input  logic [31:0] trace_a_dw3,
    input  logic [31:0] trace_a_dw7,
    input  logic [31:0] trace_a_pw1,
    input  logic [31:0] trace_a_pw2,
    input  logic [31:0] trace_a_write,
    input  logic [31:0] trace_b_feed,
    input  logic [31:0] trace_b_dw3,
    input  logic [31:0] trace_b_dw7,
    input  logic [31:0] trace_b_pw1,
    input  logic [31:0] trace_b_pw2,
    input  logic [31:0] trace_b_write,
    output logic [17:0] packed_a_feed,
    output logic [17:0] packed_a_dw3,
    output logic [17:0] packed_a_dw7,
    output logic [17:0] packed_a_pw1,
    output logic [17:0] packed_a_pw2,
    output logic [17:0] packed_a_write,
    output logic [17:0] packed_b_feed,
    output logic [17:0] packed_b_dw3,
    output logic [17:0] packed_b_dw7,
    output logic [17:0] packed_b_pw1,
    output logic [17:0] packed_b_pw2,
    output logic [17:0] packed_b_write
);
    function automatic logic [17:0] pack_trace(input logic [31:0] trace_value);
        return {
            trace_value[31],
            trace_value[20:16],
            trace_value[13:8],
            trace_value[5:0]
        };
    endfunction

    assign packed_a_feed  = pack_trace(trace_a_feed);
    assign packed_a_dw3   = pack_trace(trace_a_dw3);
    assign packed_a_dw7   = pack_trace(trace_a_dw7);
    assign packed_a_pw1   = pack_trace(trace_a_pw1);
    assign packed_a_pw2   = pack_trace(trace_a_pw2);
    assign packed_a_write = pack_trace(trace_a_write);
    assign packed_b_feed  = pack_trace(trace_b_feed);
    assign packed_b_dw3   = pack_trace(trace_b_dw3);
    assign packed_b_dw7   = pack_trace(trace_b_dw7);
    assign packed_b_pw1   = pack_trace(trace_b_pw1);
    assign packed_b_pw2   = pack_trace(trace_b_pw2);
    assign packed_b_write = pack_trace(trace_b_write);
endmodule
