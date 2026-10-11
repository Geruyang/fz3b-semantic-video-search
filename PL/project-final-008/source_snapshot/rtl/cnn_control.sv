// Register ABI independently implemented from driver map; start/done are external.
module cnn_control (
 input logic clk,rst,
 input logic [11:0] s_axi_control_awaddr,input logic s_axi_control_awvalid,output logic s_axi_control_awready,
 input logic [31:0] s_axi_control_wdata,input logic [3:0] s_axi_control_wstrb,
 input logic s_axi_control_wvalid,output logic s_axi_control_wready,
 output logic [1:0] s_axi_control_bresp,output logic s_axi_control_bvalid,input logic s_axi_control_bready,
 input logic [11:0] s_axi_control_araddr,input logic s_axi_control_arvalid,output logic s_axi_control_arready,
 output logic [31:0] s_axi_control_rdata,output logic [1:0] s_axi_control_rresp,
 output logic s_axi_control_rvalid,input logic s_axi_control_rready,
 output logic [63:0] params_pw1,
 output logic [63:0] params_pw2,
 output logic [63:0] activation_a_rd,
 output logic [63:0] activation_a_wr,
 output logic [63:0] activation_b_rd,
 output logic [63:0] activation_b_wr,
 output logic [31:0] profile,
 output logic [31:0] block_count,
 output logic [31:0] params_words,
 output logic [31:0] slot_words,
 output logic [31:0] arena_words,
 output logic [31:0] flags);
 logic aw_hold,w_hold;
 logic [11:0] awaddr;
 logic [31:0] wdata,wmask;
 logic [3:0] wstrb;
 assign s_axi_control_awready=!aw_hold && !s_axi_control_bvalid;
 assign s_axi_control_wready=!w_hold && !s_axi_control_bvalid;
 assign s_axi_control_arready=!s_axi_control_rvalid;
 assign s_axi_control_bresp=0;assign s_axi_control_rresp=0;
 assign wmask={{8{wstrb[3]}},{8{wstrb[2]}},{8{wstrb[1]}},{8{wstrb[0]}}};
 always_ff @(posedge clk) begin
  if(rst) begin
   aw_hold<=0;w_hold<=0;awaddr<=0;wdata<=0;wstrb<=0;
   s_axi_control_bvalid<=0;s_axi_control_rvalid<=0;s_axi_control_rdata<=0;
   params_pw1<=0;
   params_pw2<=0;
   activation_a_rd<=0;
   activation_a_wr<=0;
   activation_b_rd<=0;
   activation_b_wr<=0;
   profile<=0;
   block_count<=0;
   params_words<=0;
   slot_words<=0;
   arena_words<=0;
   flags<=0;
  end else begin
   if(s_axi_control_awvalid && s_axi_control_awready) begin awaddr<={s_axi_control_awaddr[11:2],2'b0};aw_hold<=1;end
   if(s_axi_control_wvalid && s_axi_control_wready) begin wdata<=s_axi_control_wdata;wstrb<=s_axi_control_wstrb;w_hold<=1;end
   if(s_axi_control_bvalid && s_axi_control_bready) s_axi_control_bvalid<=0;
   if(aw_hold && w_hold && !s_axi_control_bvalid) begin
    aw_hold<=0;w_hold<=0;s_axi_control_bvalid<=1;
    unique case(awaddr)
     12'h010: params_pw1[31:0]<=(params_pw1[31:0] & ~wmask)|(wdata & wmask);
     12'h014: params_pw1[63:32]<=(params_pw1[63:32] & ~wmask)|(wdata & wmask);
     12'h01c: params_pw2[31:0]<=(params_pw2[31:0] & ~wmask)|(wdata & wmask);
     12'h020: params_pw2[63:32]<=(params_pw2[63:32] & ~wmask)|(wdata & wmask);
     12'h028: activation_a_rd[31:0]<=(activation_a_rd[31:0] & ~wmask)|(wdata & wmask);
     12'h02c: activation_a_rd[63:32]<=(activation_a_rd[63:32] & ~wmask)|(wdata & wmask);
     12'h034: activation_a_wr[31:0]<=(activation_a_wr[31:0] & ~wmask)|(wdata & wmask);
     12'h038: activation_a_wr[63:32]<=(activation_a_wr[63:32] & ~wmask)|(wdata & wmask);
     12'h040: activation_b_rd[31:0]<=(activation_b_rd[31:0] & ~wmask)|(wdata & wmask);
     12'h044: activation_b_rd[63:32]<=(activation_b_rd[63:32] & ~wmask)|(wdata & wmask);
     12'h04c: activation_b_wr[31:0]<=(activation_b_wr[31:0] & ~wmask)|(wdata & wmask);
     12'h050: activation_b_wr[63:32]<=(activation_b_wr[63:32] & ~wmask)|(wdata & wmask);
     12'h058: profile<=(profile & ~wmask)|(wdata & wmask);
     12'h060: block_count<=(block_count & ~wmask)|(wdata & wmask);
     12'h068: params_words<=(params_words & ~wmask)|(wdata & wmask);
     12'h070: slot_words<=(slot_words & ~wmask)|(wdata & wmask);
     12'h078: arena_words<=(arena_words & ~wmask)|(wdata & wmask);
     12'h080: flags<=(flags & ~wmask)|(wdata & wmask);
     default:begin end
    endcase
   end
   if(s_axi_control_rvalid && s_axi_control_rready) s_axi_control_rvalid<=0;
   if(s_axi_control_arvalid && s_axi_control_arready) begin
    s_axi_control_rvalid<=1;
    unique case({s_axi_control_araddr[11:2],2'b0})
     12'h010:s_axi_control_rdata<=params_pw1[31:0];
     12'h014:s_axi_control_rdata<=params_pw1[63:32];
     12'h01c:s_axi_control_rdata<=params_pw2[31:0];
     12'h020:s_axi_control_rdata<=params_pw2[63:32];
     12'h028:s_axi_control_rdata<=activation_a_rd[31:0];
     12'h02c:s_axi_control_rdata<=activation_a_rd[63:32];
     12'h034:s_axi_control_rdata<=activation_a_wr[31:0];
     12'h038:s_axi_control_rdata<=activation_a_wr[63:32];
     12'h040:s_axi_control_rdata<=activation_b_rd[31:0];
     12'h044:s_axi_control_rdata<=activation_b_rd[63:32];
     12'h04c:s_axi_control_rdata<=activation_b_wr[31:0];
     12'h050:s_axi_control_rdata<=activation_b_wr[63:32];
     12'h058:s_axi_control_rdata<=profile;
     12'h060:s_axi_control_rdata<=block_count;
     12'h068:s_axi_control_rdata<=params_words;
     12'h070:s_axi_control_rdata<=slot_words;
     12'h078:s_axi_control_rdata<=arena_words;
     12'h080:s_axi_control_rdata<=flags;
     default:s_axi_control_rdata<=0;
    endcase
   end
  end
 end
endmodule
