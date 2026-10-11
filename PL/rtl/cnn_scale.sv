// Elastic, globally stalled pipeline. Four 24x16 partial products are combined
// in a second registered stage; six constant barrel stages retain guard/sticky.
module cnn_scale(
  input logic clk,rst,s_valid, output logic s_ready,
  input logic signed [47:0] s_value,
  input logic signed [31:0] s_multiplier, input logic [5:0] s_shift,
  output logic m_valid, input logic m_ready, output logic signed [15:0] m_data
);
  import cnn_math_pkg::*;
  logic [9:0] valid;
  logic enable;
  logic signed [41:0] p00,p01,p10,p11;
  logic signed [79:0] q[8];
  logic [5:0] shifts[8];
  logic [7:0] guard_bits,sticky_bits;
  logic signed [79:0] rounded;
  assign enable = !valid[9] || m_ready;
  assign s_ready = enable;
  assign m_valid = valid[9];
  always_ff @(posedge clk) begin
    if (rst) valid <= '0;
    else if (enable) begin
      valid <= {valid[8:0],s_valid};
      p00 <= $signed({1'b0,s_value[23:0]}) * $signed({1'b0,s_multiplier[15:0]});
      p01 <= $signed({1'b0,s_value[23:0]}) * $signed(s_multiplier[31:16]);
      p10 <= $signed(s_value[47:24]) * $signed({1'b0,s_multiplier[15:0]});
      p11 <= $signed(s_value[47:24]) * $signed(s_multiplier[31:16]);
      shifts[0] <= s_shift;
      q[1] <= $signed(p00) + ($signed({{38{p01[41]}},p01}) <<< 16)
                + ($signed({{38{p10[41]}},p10}) <<< 24)
                + ($signed({{38{p11[41]}},p11}) <<< 40);
      shifts[1] <= shifts[0];
      guard_bits[1] <= 0;
      sticky_bits[1] <= 0;
      for (int k=0;k<6;k++) begin
        shifts[k+2] <= shifts[k+1];
        if (shifts[k+1][k]) begin
          q[k+2] <= q[k+1] >>> (1<<k);
          guard_bits[k+2] <= q[k+1][(1<<k)-1];
          if (k==0) sticky_bits[k+2] <= sticky_bits[k+1] || guard_bits[k+1];
          else sticky_bits[k+2] <= sticky_bits[k+1] || guard_bits[k+1] || (|(q[k+1] & ((80'd1 << ((1<<k)-1))-1)));
        end else begin
          q[k+2] <= q[k+1];
          guard_bits[k+2] <= guard_bits[k+1];
          sticky_bits[k+2] <= sticky_bits[k+1];
        end
      end
      rounded <= q[7] + {{79{1'b0}},(guard_bits[7] && (sticky_bits[7] || q[7][0]))};
      m_data <= clip(rounded);
    end
  end
endmodule
