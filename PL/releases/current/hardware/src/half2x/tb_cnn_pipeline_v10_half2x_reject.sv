`timescale 1ns/1ps
module tb_cnn_pipeline_v10_half2x_reject;
    tb_cnn_pipeline_v10_half2x_common #(.REJECT_ONLY(1'b1)) u_test();
endmodule
