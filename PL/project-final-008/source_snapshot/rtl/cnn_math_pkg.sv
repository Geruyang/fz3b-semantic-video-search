package cnn_math_pkg;
  function automatic logic signed [79:0] round_even(input logic signed [79:0] value, input logic [5:0] shift);
    logic signed [79:0] q;
    logic guard_bit, sticky_bit;
    q = value >>> shift;
    guard_bit = 1'b0;
    sticky_bit = 1'b0;
    for (int b = 0; b < 63; b++) begin
      if (shift != 0 && b == int'(shift)-1) guard_bit = value[b];
      if (b < int'(shift)-1) sticky_bit |= value[b];
    end
    return q + {{79{1'b0}}, (guard_bit && (sticky_bit || q[0]))};
  endfunction
  function automatic logic signed [15:0] clip(input logic signed [79:0] value);
    if (value > 80'sd32767) return 16'sd32767;
    if (value < -80'sd32767) return -16'sd32767;
    return value[15:0];
  endfunction
  function automatic logic signed [79:0] scale_narrow(input logic signed [15:0] value, input logic signed [31:0] multiplier, input logic [5:0] shift);
    logic signed [47:0] product;
    product = value * multiplier;
    return round_even({{32{product[47]}},product},shift);
  endfunction
endpackage
