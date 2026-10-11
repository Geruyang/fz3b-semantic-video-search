// Two independent exact signed16x32 narrow scales. Retain signed80 results
// until after their addition: clipping each term would change cancellation.
module cnn_narrow_post(
 input logic clk,rst,s_valid,output logic s_ready,
 input logic signed [15:0] s_q,s_skip,
 input logic signed [31:0] s_output_multiplier,s_residual_multiplier,
 input logic [5:0] s_output_shift,s_residual_shift,
 output logic m_valid,input logic m_ready,output logic signed [15:0] m_data
);
 import cnn_math_pkg::*;
 logic [10:0] valid;
 logic enable;
 logic signed [15:0] operand[2];
 logic signed [31:0] multiplier[2];
 logic [5:0] input_shift[2];
 logic signed [33:0] lower_product[2],upper_product[2];
 logic signed [79:0] q[2][8],rounded[2],sum;
 logic [5:0] shifts[2][8];
 logic [7:0] guard_bits[2],sticky_bits[2];
 assign operand[0]=s_q;
 assign operand[1]=s_skip;
 assign multiplier[0]=s_output_multiplier;
 assign multiplier[1]=s_residual_multiplier;
 assign input_shift[0]=s_output_shift;
 assign input_shift[1]=s_residual_shift;
 assign enable=!valid[10]||m_ready;
 assign s_ready=enable;
 assign m_valid=valid[10];
 always_ff @(posedge clk) begin
   if(rst)valid<='0;
   else if(enable)begin
     valid<={valid[9:0],s_valid};
     for(int p=0;p<2;p++)begin
       lower_product[p]<=operand[p]*$signed({1'b0,multiplier[p][15:0]});
       upper_product[p]<=operand[p]*$signed(multiplier[p][31:16]);
       shifts[p][0]<=input_shift[p];
       q[p][1]<=$signed(lower_product[p])+($signed({{46{upper_product[p][33]}},upper_product[p]})<<<16);
       shifts[p][1]<=shifts[p][0];guard_bits[p][1]<=0;sticky_bits[p][1]<=0;
       for(int k=0;k<6;k++)begin
         shifts[p][k+2]<=shifts[p][k+1];
         if(shifts[p][k+1][k])begin
           q[p][k+2]<=q[p][k+1]>>>(1<<k);
           guard_bits[p][k+2]<=q[p][k+1][(1<<k)-1];
           if(k==0)sticky_bits[p][k+2]<=sticky_bits[p][k+1]||guard_bits[p][k+1];
           else sticky_bits[p][k+2]<=sticky_bits[p][k+1]||guard_bits[p][k+1]||(|(q[p][k+1]&((80'd1<<((1<<k)-1))-1)));
         end else begin
           q[p][k+2]<=q[p][k+1];
           guard_bits[p][k+2]<=guard_bits[p][k+1];
           sticky_bits[p][k+2]<=sticky_bits[p][k+1];
         end
       end
       rounded[p]<=q[p][7]+{{79{1'b0}},(guard_bits[p][7]&&(sticky_bits[p][7]||q[p][7][0]))};
     end
     sum<=rounded[0]+rounded[1];
     m_data<=clip(sum);
   end
 end
endmodule
