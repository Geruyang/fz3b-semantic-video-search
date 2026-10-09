
    wire dl_reset;
    wire dl_clock;
    assign dl_reset = ap_rst_n;
    assign dl_clock = ap_clk;
    wire [10:0] proc_0_data_FIFO_blk;
    wire [10:0] proc_0_data_PIPO_blk;
    wire [10:0] proc_0_start_FIFO_blk;
    wire [10:0] proc_0_TLF_FIFO_blk;
    wire [10:0] proc_0_input_sync_blk;
    wire [10:0] proc_0_output_sync_blk;
    wire [10:0] proc_dep_vld_vec_0;
    reg [10:0] proc_dep_vld_vec_0_reg;
    wire [10:0] in_chan_dep_vld_vec_0;
    wire [428:0] in_chan_dep_data_vec_0;
    wire [10:0] token_in_vec_0;
    wire [10:0] out_chan_dep_vld_vec_0;
    wire [38:0] out_chan_dep_data_0;
    wire [10:0] token_out_vec_0;
    wire dl_detect_out_0;
    wire dep_chan_vld_1_0;
    wire [38:0] dep_chan_data_1_0;
    wire token_1_0;
    wire dep_chan_vld_2_0;
    wire [38:0] dep_chan_data_2_0;
    wire token_2_0;
    wire dep_chan_vld_3_0;
    wire [38:0] dep_chan_data_3_0;
    wire token_3_0;
    wire dep_chan_vld_4_0;
    wire [38:0] dep_chan_data_4_0;
    wire token_4_0;
    wire dep_chan_vld_5_0;
    wire [38:0] dep_chan_data_5_0;
    wire token_5_0;
    wire dep_chan_vld_6_0;
    wire [38:0] dep_chan_data_6_0;
    wire token_6_0;
    wire dep_chan_vld_7_0;
    wire [38:0] dep_chan_data_7_0;
    wire token_7_0;
    wire dep_chan_vld_10_0;
    wire [38:0] dep_chan_data_10_0;
    wire token_10_0;
    wire dep_chan_vld_15_0;
    wire [38:0] dep_chan_data_15_0;
    wire token_15_0;
    wire dep_chan_vld_22_0;
    wire [38:0] dep_chan_data_22_0;
    wire token_22_0;
    wire dep_chan_vld_23_0;
    wire [38:0] dep_chan_data_23_0;
    wire token_23_0;
    wire [8:0] proc_1_data_FIFO_blk;
    wire [8:0] proc_1_data_PIPO_blk;
    wire [8:0] proc_1_start_FIFO_blk;
    wire [8:0] proc_1_TLF_FIFO_blk;
    wire [8:0] proc_1_input_sync_blk;
    wire [8:0] proc_1_output_sync_blk;
    wire [8:0] proc_dep_vld_vec_1;
    reg [8:0] proc_dep_vld_vec_1_reg;
    wire [8:0] in_chan_dep_vld_vec_1;
    wire [350:0] in_chan_dep_data_vec_1;
    wire [8:0] token_in_vec_1;
    wire [8:0] out_chan_dep_vld_vec_1;
    wire [38:0] out_chan_dep_data_1;
    wire [8:0] token_out_vec_1;
    wire dl_detect_out_1;
    wire dep_chan_vld_0_1;
    wire [38:0] dep_chan_data_0_1;
    wire token_0_1;
    wire dep_chan_vld_2_1;
    wire [38:0] dep_chan_data_2_1;
    wire token_2_1;
    wire dep_chan_vld_3_1;
    wire [38:0] dep_chan_data_3_1;
    wire token_3_1;
    wire dep_chan_vld_4_1;
    wire [38:0] dep_chan_data_4_1;
    wire token_4_1;
    wire dep_chan_vld_5_1;
    wire [38:0] dep_chan_data_5_1;
    wire token_5_1;
    wire dep_chan_vld_6_1;
    wire [38:0] dep_chan_data_6_1;
    wire token_6_1;
    wire dep_chan_vld_7_1;
    wire [38:0] dep_chan_data_7_1;
    wire token_7_1;
    wire dep_chan_vld_30_1;
    wire [38:0] dep_chan_data_30_1;
    wire token_30_1;
    wire dep_chan_vld_31_1;
    wire [38:0] dep_chan_data_31_1;
    wire token_31_1;
    wire [8:0] proc_2_data_FIFO_blk;
    wire [8:0] proc_2_data_PIPO_blk;
    wire [8:0] proc_2_start_FIFO_blk;
    wire [8:0] proc_2_TLF_FIFO_blk;
    wire [8:0] proc_2_input_sync_blk;
    wire [8:0] proc_2_output_sync_blk;
    wire [8:0] proc_dep_vld_vec_2;
    reg [8:0] proc_dep_vld_vec_2_reg;
    wire [8:0] in_chan_dep_vld_vec_2;
    wire [350:0] in_chan_dep_data_vec_2;
    wire [8:0] token_in_vec_2;
    wire [8:0] out_chan_dep_vld_vec_2;
    wire [38:0] out_chan_dep_data_2;
    wire [8:0] token_out_vec_2;
    wire dl_detect_out_2;
    wire dep_chan_vld_0_2;
    wire [38:0] dep_chan_data_0_2;
    wire token_0_2;
    wire dep_chan_vld_1_2;
    wire [38:0] dep_chan_data_1_2;
    wire token_1_2;
    wire dep_chan_vld_3_2;
    wire [38:0] dep_chan_data_3_2;
    wire token_3_2;
    wire dep_chan_vld_4_2;
    wire [38:0] dep_chan_data_4_2;
    wire token_4_2;
    wire dep_chan_vld_5_2;
    wire [38:0] dep_chan_data_5_2;
    wire token_5_2;
    wire dep_chan_vld_6_2;
    wire [38:0] dep_chan_data_6_2;
    wire token_6_2;
    wire dep_chan_vld_7_2;
    wire [38:0] dep_chan_data_7_2;
    wire token_7_2;
    wire dep_chan_vld_8_2;
    wire [38:0] dep_chan_data_8_2;
    wire token_8_2;
    wire dep_chan_vld_31_2;
    wire [38:0] dep_chan_data_31_2;
    wire token_31_2;
    wire [8:0] proc_3_data_FIFO_blk;
    wire [8:0] proc_3_data_PIPO_blk;
    wire [8:0] proc_3_start_FIFO_blk;
    wire [8:0] proc_3_TLF_FIFO_blk;
    wire [8:0] proc_3_input_sync_blk;
    wire [8:0] proc_3_output_sync_blk;
    wire [8:0] proc_dep_vld_vec_3;
    reg [8:0] proc_dep_vld_vec_3_reg;
    wire [8:0] in_chan_dep_vld_vec_3;
    wire [350:0] in_chan_dep_data_vec_3;
    wire [8:0] token_in_vec_3;
    wire [8:0] out_chan_dep_vld_vec_3;
    wire [38:0] out_chan_dep_data_3;
    wire [8:0] token_out_vec_3;
    wire dl_detect_out_3;
    wire dep_chan_vld_0_3;
    wire [38:0] dep_chan_data_0_3;
    wire token_0_3;
    wire dep_chan_vld_1_3;
    wire [38:0] dep_chan_data_1_3;
    wire token_1_3;
    wire dep_chan_vld_2_3;
    wire [38:0] dep_chan_data_2_3;
    wire token_2_3;
    wire dep_chan_vld_4_3;
    wire [38:0] dep_chan_data_4_3;
    wire token_4_3;
    wire dep_chan_vld_5_3;
    wire [38:0] dep_chan_data_5_3;
    wire token_5_3;
    wire dep_chan_vld_6_3;
    wire [38:0] dep_chan_data_6_3;
    wire token_6_3;
    wire dep_chan_vld_7_3;
    wire [38:0] dep_chan_data_7_3;
    wire token_7_3;
    wire dep_chan_vld_9_3;
    wire [38:0] dep_chan_data_9_3;
    wire token_9_3;
    wire dep_chan_vld_31_3;
    wire [38:0] dep_chan_data_31_3;
    wire token_31_3;
    wire [15:0] proc_4_data_FIFO_blk;
    wire [15:0] proc_4_data_PIPO_blk;
    wire [15:0] proc_4_start_FIFO_blk;
    wire [15:0] proc_4_TLF_FIFO_blk;
    wire [15:0] proc_4_input_sync_blk;
    wire [15:0] proc_4_output_sync_blk;
    wire [15:0] proc_dep_vld_vec_4;
    reg [15:0] proc_dep_vld_vec_4_reg;
    wire [15:0] in_chan_dep_vld_vec_4;
    wire [623:0] in_chan_dep_data_vec_4;
    wire [15:0] token_in_vec_4;
    wire [15:0] out_chan_dep_vld_vec_4;
    wire [38:0] out_chan_dep_data_4;
    wire [15:0] token_out_vec_4;
    wire dl_detect_out_4;
    wire dep_chan_vld_0_4;
    wire [38:0] dep_chan_data_0_4;
    wire token_0_4;
    wire dep_chan_vld_1_4;
    wire [38:0] dep_chan_data_1_4;
    wire token_1_4;
    wire dep_chan_vld_2_4;
    wire [38:0] dep_chan_data_2_4;
    wire token_2_4;
    wire dep_chan_vld_3_4;
    wire [38:0] dep_chan_data_3_4;
    wire token_3_4;
    wire dep_chan_vld_5_4;
    wire [38:0] dep_chan_data_5_4;
    wire token_5_4;
    wire dep_chan_vld_6_4;
    wire [38:0] dep_chan_data_6_4;
    wire token_6_4;
    wire dep_chan_vld_7_4;
    wire [38:0] dep_chan_data_7_4;
    wire token_7_4;
    wire dep_chan_vld_8_4;
    wire [38:0] dep_chan_data_8_4;
    wire token_8_4;
    wire dep_chan_vld_9_4;
    wire [38:0] dep_chan_data_9_4;
    wire token_9_4;
    wire dep_chan_vld_10_4;
    wire [38:0] dep_chan_data_10_4;
    wire token_10_4;
    wire dep_chan_vld_15_4;
    wire [38:0] dep_chan_data_15_4;
    wire token_15_4;
    wire dep_chan_vld_20_4;
    wire [38:0] dep_chan_data_20_4;
    wire token_20_4;
    wire dep_chan_vld_21_4;
    wire [38:0] dep_chan_data_21_4;
    wire token_21_4;
    wire dep_chan_vld_23_4;
    wire [38:0] dep_chan_data_23_4;
    wire token_23_4;
    wire dep_chan_vld_31_4;
    wire [38:0] dep_chan_data_31_4;
    wire token_31_4;
    wire dep_chan_vld_38_4;
    wire [38:0] dep_chan_data_38_4;
    wire token_38_4;
    wire [15:0] proc_5_data_FIFO_blk;
    wire [15:0] proc_5_data_PIPO_blk;
    wire [15:0] proc_5_start_FIFO_blk;
    wire [15:0] proc_5_TLF_FIFO_blk;
    wire [15:0] proc_5_input_sync_blk;
    wire [15:0] proc_5_output_sync_blk;
    wire [15:0] proc_dep_vld_vec_5;
    reg [15:0] proc_dep_vld_vec_5_reg;
    wire [15:0] in_chan_dep_vld_vec_5;
    wire [623:0] in_chan_dep_data_vec_5;
    wire [15:0] token_in_vec_5;
    wire [15:0] out_chan_dep_vld_vec_5;
    wire [38:0] out_chan_dep_data_5;
    wire [15:0] token_out_vec_5;
    wire dl_detect_out_5;
    wire dep_chan_vld_0_5;
    wire [38:0] dep_chan_data_0_5;
    wire token_0_5;
    wire dep_chan_vld_1_5;
    wire [38:0] dep_chan_data_1_5;
    wire token_1_5;
    wire dep_chan_vld_2_5;
    wire [38:0] dep_chan_data_2_5;
    wire token_2_5;
    wire dep_chan_vld_3_5;
    wire [38:0] dep_chan_data_3_5;
    wire token_3_5;
    wire dep_chan_vld_4_5;
    wire [38:0] dep_chan_data_4_5;
    wire token_4_5;
    wire dep_chan_vld_6_5;
    wire [38:0] dep_chan_data_6_5;
    wire token_6_5;
    wire dep_chan_vld_7_5;
    wire [38:0] dep_chan_data_7_5;
    wire token_7_5;
    wire dep_chan_vld_8_5;
    wire [38:0] dep_chan_data_8_5;
    wire token_8_5;
    wire dep_chan_vld_9_5;
    wire [38:0] dep_chan_data_9_5;
    wire token_9_5;
    wire dep_chan_vld_10_5;
    wire [38:0] dep_chan_data_10_5;
    wire token_10_5;
    wire dep_chan_vld_15_5;
    wire [38:0] dep_chan_data_15_5;
    wire token_15_5;
    wire dep_chan_vld_20_5;
    wire [38:0] dep_chan_data_20_5;
    wire token_20_5;
    wire dep_chan_vld_21_5;
    wire [38:0] dep_chan_data_21_5;
    wire token_21_5;
    wire dep_chan_vld_23_5;
    wire [38:0] dep_chan_data_23_5;
    wire token_23_5;
    wire dep_chan_vld_31_5;
    wire [38:0] dep_chan_data_31_5;
    wire token_31_5;
    wire dep_chan_vld_38_5;
    wire [38:0] dep_chan_data_38_5;
    wire token_38_5;
    wire [9:0] proc_6_data_FIFO_blk;
    wire [9:0] proc_6_data_PIPO_blk;
    wire [9:0] proc_6_start_FIFO_blk;
    wire [9:0] proc_6_TLF_FIFO_blk;
    wire [9:0] proc_6_input_sync_blk;
    wire [9:0] proc_6_output_sync_blk;
    wire [9:0] proc_dep_vld_vec_6;
    reg [9:0] proc_dep_vld_vec_6_reg;
    wire [9:0] in_chan_dep_vld_vec_6;
    wire [389:0] in_chan_dep_data_vec_6;
    wire [9:0] token_in_vec_6;
    wire [9:0] out_chan_dep_vld_vec_6;
    wire [38:0] out_chan_dep_data_6;
    wire [9:0] token_out_vec_6;
    wire dl_detect_out_6;
    wire dep_chan_vld_0_6;
    wire [38:0] dep_chan_data_0_6;
    wire token_0_6;
    wire dep_chan_vld_1_6;
    wire [38:0] dep_chan_data_1_6;
    wire token_1_6;
    wire dep_chan_vld_2_6;
    wire [38:0] dep_chan_data_2_6;
    wire token_2_6;
    wire dep_chan_vld_3_6;
    wire [38:0] dep_chan_data_3_6;
    wire token_3_6;
    wire dep_chan_vld_4_6;
    wire [38:0] dep_chan_data_4_6;
    wire token_4_6;
    wire dep_chan_vld_5_6;
    wire [38:0] dep_chan_data_5_6;
    wire token_5_6;
    wire dep_chan_vld_7_6;
    wire [38:0] dep_chan_data_7_6;
    wire token_7_6;
    wire dep_chan_vld_10_6;
    wire [38:0] dep_chan_data_10_6;
    wire token_10_6;
    wire dep_chan_vld_15_6;
    wire [38:0] dep_chan_data_15_6;
    wire token_15_6;
    wire dep_chan_vld_31_6;
    wire [38:0] dep_chan_data_31_6;
    wire token_31_6;
    wire [9:0] proc_7_data_FIFO_blk;
    wire [9:0] proc_7_data_PIPO_blk;
    wire [9:0] proc_7_start_FIFO_blk;
    wire [9:0] proc_7_TLF_FIFO_blk;
    wire [9:0] proc_7_input_sync_blk;
    wire [9:0] proc_7_output_sync_blk;
    wire [9:0] proc_dep_vld_vec_7;
    reg [9:0] proc_dep_vld_vec_7_reg;
    wire [9:0] in_chan_dep_vld_vec_7;
    wire [389:0] in_chan_dep_data_vec_7;
    wire [9:0] token_in_vec_7;
    wire [9:0] out_chan_dep_vld_vec_7;
    wire [38:0] out_chan_dep_data_7;
    wire [9:0] token_out_vec_7;
    wire dl_detect_out_7;
    wire dep_chan_vld_0_7;
    wire [38:0] dep_chan_data_0_7;
    wire token_0_7;
    wire dep_chan_vld_1_7;
    wire [38:0] dep_chan_data_1_7;
    wire token_1_7;
    wire dep_chan_vld_2_7;
    wire [38:0] dep_chan_data_2_7;
    wire token_2_7;
    wire dep_chan_vld_3_7;
    wire [38:0] dep_chan_data_3_7;
    wire token_3_7;
    wire dep_chan_vld_4_7;
    wire [38:0] dep_chan_data_4_7;
    wire token_4_7;
    wire dep_chan_vld_5_7;
    wire [38:0] dep_chan_data_5_7;
    wire token_5_7;
    wire dep_chan_vld_6_7;
    wire [38:0] dep_chan_data_6_7;
    wire token_6_7;
    wire dep_chan_vld_10_7;
    wire [38:0] dep_chan_data_10_7;
    wire token_10_7;
    wire dep_chan_vld_15_7;
    wire [38:0] dep_chan_data_15_7;
    wire token_15_7;
    wire dep_chan_vld_31_7;
    wire [38:0] dep_chan_data_31_7;
    wire token_31_7;
    wire [10:0] proc_8_data_FIFO_blk;
    wire [10:0] proc_8_data_PIPO_blk;
    wire [10:0] proc_8_start_FIFO_blk;
    wire [10:0] proc_8_TLF_FIFO_blk;
    wire [10:0] proc_8_input_sync_blk;
    wire [10:0] proc_8_output_sync_blk;
    wire [10:0] proc_dep_vld_vec_8;
    reg [10:0] proc_dep_vld_vec_8_reg;
    wire [10:0] in_chan_dep_vld_vec_8;
    wire [428:0] in_chan_dep_data_vec_8;
    wire [10:0] token_in_vec_8;
    wire [10:0] out_chan_dep_vld_vec_8;
    wire [38:0] out_chan_dep_data_8;
    wire [10:0] token_out_vec_8;
    wire dl_detect_out_8;
    wire dep_chan_vld_2_8;
    wire [38:0] dep_chan_data_2_8;
    wire token_2_8;
    wire dep_chan_vld_4_8;
    wire [38:0] dep_chan_data_4_8;
    wire token_4_8;
    wire dep_chan_vld_5_8;
    wire [38:0] dep_chan_data_5_8;
    wire token_5_8;
    wire dep_chan_vld_9_8;
    wire [38:0] dep_chan_data_9_8;
    wire token_9_8;
    wire dep_chan_vld_10_8;
    wire [38:0] dep_chan_data_10_8;
    wire token_10_8;
    wire dep_chan_vld_15_8;
    wire [38:0] dep_chan_data_15_8;
    wire token_15_8;
    wire dep_chan_vld_20_8;
    wire [38:0] dep_chan_data_20_8;
    wire token_20_8;
    wire dep_chan_vld_21_8;
    wire [38:0] dep_chan_data_21_8;
    wire token_21_8;
    wire dep_chan_vld_23_8;
    wire [38:0] dep_chan_data_23_8;
    wire token_23_8;
    wire dep_chan_vld_31_8;
    wire [38:0] dep_chan_data_31_8;
    wire token_31_8;
    wire dep_chan_vld_38_8;
    wire [38:0] dep_chan_data_38_8;
    wire token_38_8;
    wire [10:0] proc_9_data_FIFO_blk;
    wire [10:0] proc_9_data_PIPO_blk;
    wire [10:0] proc_9_start_FIFO_blk;
    wire [10:0] proc_9_TLF_FIFO_blk;
    wire [10:0] proc_9_input_sync_blk;
    wire [10:0] proc_9_output_sync_blk;
    wire [10:0] proc_dep_vld_vec_9;
    reg [10:0] proc_dep_vld_vec_9_reg;
    wire [10:0] in_chan_dep_vld_vec_9;
    wire [428:0] in_chan_dep_data_vec_9;
    wire [10:0] token_in_vec_9;
    wire [10:0] out_chan_dep_vld_vec_9;
    wire [38:0] out_chan_dep_data_9;
    wire [10:0] token_out_vec_9;
    wire dl_detect_out_9;
    wire dep_chan_vld_3_9;
    wire [38:0] dep_chan_data_3_9;
    wire token_3_9;
    wire dep_chan_vld_4_9;
    wire [38:0] dep_chan_data_4_9;
    wire token_4_9;
    wire dep_chan_vld_5_9;
    wire [38:0] dep_chan_data_5_9;
    wire token_5_9;
    wire dep_chan_vld_8_9;
    wire [38:0] dep_chan_data_8_9;
    wire token_8_9;
    wire dep_chan_vld_10_9;
    wire [38:0] dep_chan_data_10_9;
    wire token_10_9;
    wire dep_chan_vld_15_9;
    wire [38:0] dep_chan_data_15_9;
    wire token_15_9;
    wire dep_chan_vld_20_9;
    wire [38:0] dep_chan_data_20_9;
    wire token_20_9;
    wire dep_chan_vld_21_9;
    wire [38:0] dep_chan_data_21_9;
    wire token_21_9;
    wire dep_chan_vld_23_9;
    wire [38:0] dep_chan_data_23_9;
    wire token_23_9;
    wire dep_chan_vld_31_9;
    wire [38:0] dep_chan_data_31_9;
    wire token_31_9;
    wire dep_chan_vld_38_9;
    wire [38:0] dep_chan_data_38_9;
    wire token_38_9;
    wire [12:0] proc_10_data_FIFO_blk;
    wire [12:0] proc_10_data_PIPO_blk;
    wire [12:0] proc_10_start_FIFO_blk;
    wire [12:0] proc_10_TLF_FIFO_blk;
    wire [12:0] proc_10_input_sync_blk;
    wire [12:0] proc_10_output_sync_blk;
    wire [12:0] proc_dep_vld_vec_10;
    reg [12:0] proc_dep_vld_vec_10_reg;
    wire [12:0] in_chan_dep_vld_vec_10;
    wire [506:0] in_chan_dep_data_vec_10;
    wire [12:0] token_in_vec_10;
    wire [12:0] out_chan_dep_vld_vec_10;
    wire [38:0] out_chan_dep_data_10;
    wire [12:0] token_out_vec_10;
    wire dl_detect_out_10;
    wire dep_chan_vld_0_10;
    wire [38:0] dep_chan_data_0_10;
    wire token_0_10;
    wire dep_chan_vld_4_10;
    wire [38:0] dep_chan_data_4_10;
    wire token_4_10;
    wire dep_chan_vld_5_10;
    wire [38:0] dep_chan_data_5_10;
    wire token_5_10;
    wire dep_chan_vld_6_10;
    wire [38:0] dep_chan_data_6_10;
    wire token_6_10;
    wire dep_chan_vld_7_10;
    wire [38:0] dep_chan_data_7_10;
    wire token_7_10;
    wire dep_chan_vld_8_10;
    wire [38:0] dep_chan_data_8_10;
    wire token_8_10;
    wire dep_chan_vld_9_10;
    wire [38:0] dep_chan_data_9_10;
    wire token_9_10;
    wire dep_chan_vld_15_10;
    wire [38:0] dep_chan_data_15_10;
    wire token_15_10;
    wire dep_chan_vld_20_10;
    wire [38:0] dep_chan_data_20_10;
    wire token_20_10;
    wire dep_chan_vld_21_10;
    wire [38:0] dep_chan_data_21_10;
    wire token_21_10;
    wire dep_chan_vld_23_10;
    wire [38:0] dep_chan_data_23_10;
    wire token_23_10;
    wire dep_chan_vld_31_10;
    wire [38:0] dep_chan_data_31_10;
    wire token_31_10;
    wire dep_chan_vld_38_10;
    wire [38:0] dep_chan_data_38_10;
    wire token_38_10;
    wire [2:0] proc_11_data_FIFO_blk;
    wire [2:0] proc_11_data_PIPO_blk;
    wire [2:0] proc_11_start_FIFO_blk;
    wire [2:0] proc_11_TLF_FIFO_blk;
    wire [2:0] proc_11_input_sync_blk;
    wire [2:0] proc_11_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_11;
    reg [2:0] proc_dep_vld_vec_11_reg;
    wire [2:0] in_chan_dep_vld_vec_11;
    wire [116:0] in_chan_dep_data_vec_11;
    wire [2:0] token_in_vec_11;
    wire [2:0] out_chan_dep_vld_vec_11;
    wire [38:0] out_chan_dep_data_11;
    wire [2:0] token_out_vec_11;
    wire dl_detect_out_11;
    wire dep_chan_vld_12_11;
    wire [38:0] dep_chan_data_12_11;
    wire token_12_11;
    wire dep_chan_vld_13_11;
    wire [38:0] dep_chan_data_13_11;
    wire token_13_11;
    wire dep_chan_vld_14_11;
    wire [38:0] dep_chan_data_14_11;
    wire token_14_11;
    wire [2:0] proc_12_data_FIFO_blk;
    wire [2:0] proc_12_data_PIPO_blk;
    wire [2:0] proc_12_start_FIFO_blk;
    wire [2:0] proc_12_TLF_FIFO_blk;
    wire [2:0] proc_12_input_sync_blk;
    wire [2:0] proc_12_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_12;
    reg [2:0] proc_dep_vld_vec_12_reg;
    wire [2:0] in_chan_dep_vld_vec_12;
    wire [116:0] in_chan_dep_data_vec_12;
    wire [2:0] token_in_vec_12;
    wire [2:0] out_chan_dep_vld_vec_12;
    wire [38:0] out_chan_dep_data_12;
    wire [2:0] token_out_vec_12;
    wire dl_detect_out_12;
    wire dep_chan_vld_11_12;
    wire [38:0] dep_chan_data_11_12;
    wire token_11_12;
    wire dep_chan_vld_13_12;
    wire [38:0] dep_chan_data_13_12;
    wire token_13_12;
    wire dep_chan_vld_14_12;
    wire [38:0] dep_chan_data_14_12;
    wire token_14_12;
    wire [2:0] proc_13_data_FIFO_blk;
    wire [2:0] proc_13_data_PIPO_blk;
    wire [2:0] proc_13_start_FIFO_blk;
    wire [2:0] proc_13_TLF_FIFO_blk;
    wire [2:0] proc_13_input_sync_blk;
    wire [2:0] proc_13_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_13;
    reg [2:0] proc_dep_vld_vec_13_reg;
    wire [2:0] in_chan_dep_vld_vec_13;
    wire [116:0] in_chan_dep_data_vec_13;
    wire [2:0] token_in_vec_13;
    wire [2:0] out_chan_dep_vld_vec_13;
    wire [38:0] out_chan_dep_data_13;
    wire [2:0] token_out_vec_13;
    wire dl_detect_out_13;
    wire dep_chan_vld_11_13;
    wire [38:0] dep_chan_data_11_13;
    wire token_11_13;
    wire dep_chan_vld_12_13;
    wire [38:0] dep_chan_data_12_13;
    wire token_12_13;
    wire dep_chan_vld_14_13;
    wire [38:0] dep_chan_data_14_13;
    wire token_14_13;
    wire [2:0] proc_14_data_FIFO_blk;
    wire [2:0] proc_14_data_PIPO_blk;
    wire [2:0] proc_14_start_FIFO_blk;
    wire [2:0] proc_14_TLF_FIFO_blk;
    wire [2:0] proc_14_input_sync_blk;
    wire [2:0] proc_14_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_14;
    reg [2:0] proc_dep_vld_vec_14_reg;
    wire [2:0] in_chan_dep_vld_vec_14;
    wire [116:0] in_chan_dep_data_vec_14;
    wire [2:0] token_in_vec_14;
    wire [2:0] out_chan_dep_vld_vec_14;
    wire [38:0] out_chan_dep_data_14;
    wire [2:0] token_out_vec_14;
    wire dl_detect_out_14;
    wire dep_chan_vld_11_14;
    wire [38:0] dep_chan_data_11_14;
    wire token_11_14;
    wire dep_chan_vld_12_14;
    wire [38:0] dep_chan_data_12_14;
    wire token_12_14;
    wire dep_chan_vld_13_14;
    wire [38:0] dep_chan_data_13_14;
    wire token_13_14;
    wire [12:0] proc_15_data_FIFO_blk;
    wire [12:0] proc_15_data_PIPO_blk;
    wire [12:0] proc_15_start_FIFO_blk;
    wire [12:0] proc_15_TLF_FIFO_blk;
    wire [12:0] proc_15_input_sync_blk;
    wire [12:0] proc_15_output_sync_blk;
    wire [12:0] proc_dep_vld_vec_15;
    reg [12:0] proc_dep_vld_vec_15_reg;
    wire [12:0] in_chan_dep_vld_vec_15;
    wire [506:0] in_chan_dep_data_vec_15;
    wire [12:0] token_in_vec_15;
    wire [12:0] out_chan_dep_vld_vec_15;
    wire [38:0] out_chan_dep_data_15;
    wire [12:0] token_out_vec_15;
    wire dl_detect_out_15;
    wire dep_chan_vld_0_15;
    wire [38:0] dep_chan_data_0_15;
    wire token_0_15;
    wire dep_chan_vld_4_15;
    wire [38:0] dep_chan_data_4_15;
    wire token_4_15;
    wire dep_chan_vld_5_15;
    wire [38:0] dep_chan_data_5_15;
    wire token_5_15;
    wire dep_chan_vld_6_15;
    wire [38:0] dep_chan_data_6_15;
    wire token_6_15;
    wire dep_chan_vld_7_15;
    wire [38:0] dep_chan_data_7_15;
    wire token_7_15;
    wire dep_chan_vld_8_15;
    wire [38:0] dep_chan_data_8_15;
    wire token_8_15;
    wire dep_chan_vld_9_15;
    wire [38:0] dep_chan_data_9_15;
    wire token_9_15;
    wire dep_chan_vld_10_15;
    wire [38:0] dep_chan_data_10_15;
    wire token_10_15;
    wire dep_chan_vld_20_15;
    wire [38:0] dep_chan_data_20_15;
    wire token_20_15;
    wire dep_chan_vld_21_15;
    wire [38:0] dep_chan_data_21_15;
    wire token_21_15;
    wire dep_chan_vld_23_15;
    wire [38:0] dep_chan_data_23_15;
    wire token_23_15;
    wire dep_chan_vld_31_15;
    wire [38:0] dep_chan_data_31_15;
    wire token_31_15;
    wire dep_chan_vld_38_15;
    wire [38:0] dep_chan_data_38_15;
    wire token_38_15;
    wire [2:0] proc_16_data_FIFO_blk;
    wire [2:0] proc_16_data_PIPO_blk;
    wire [2:0] proc_16_start_FIFO_blk;
    wire [2:0] proc_16_TLF_FIFO_blk;
    wire [2:0] proc_16_input_sync_blk;
    wire [2:0] proc_16_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_16;
    reg [2:0] proc_dep_vld_vec_16_reg;
    wire [2:0] in_chan_dep_vld_vec_16;
    wire [116:0] in_chan_dep_data_vec_16;
    wire [2:0] token_in_vec_16;
    wire [2:0] out_chan_dep_vld_vec_16;
    wire [38:0] out_chan_dep_data_16;
    wire [2:0] token_out_vec_16;
    wire dl_detect_out_16;
    wire dep_chan_vld_17_16;
    wire [38:0] dep_chan_data_17_16;
    wire token_17_16;
    wire dep_chan_vld_18_16;
    wire [38:0] dep_chan_data_18_16;
    wire token_18_16;
    wire dep_chan_vld_19_16;
    wire [38:0] dep_chan_data_19_16;
    wire token_19_16;
    wire [2:0] proc_17_data_FIFO_blk;
    wire [2:0] proc_17_data_PIPO_blk;
    wire [2:0] proc_17_start_FIFO_blk;
    wire [2:0] proc_17_TLF_FIFO_blk;
    wire [2:0] proc_17_input_sync_blk;
    wire [2:0] proc_17_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_17;
    reg [2:0] proc_dep_vld_vec_17_reg;
    wire [2:0] in_chan_dep_vld_vec_17;
    wire [116:0] in_chan_dep_data_vec_17;
    wire [2:0] token_in_vec_17;
    wire [2:0] out_chan_dep_vld_vec_17;
    wire [38:0] out_chan_dep_data_17;
    wire [2:0] token_out_vec_17;
    wire dl_detect_out_17;
    wire dep_chan_vld_16_17;
    wire [38:0] dep_chan_data_16_17;
    wire token_16_17;
    wire dep_chan_vld_18_17;
    wire [38:0] dep_chan_data_18_17;
    wire token_18_17;
    wire dep_chan_vld_19_17;
    wire [38:0] dep_chan_data_19_17;
    wire token_19_17;
    wire [2:0] proc_18_data_FIFO_blk;
    wire [2:0] proc_18_data_PIPO_blk;
    wire [2:0] proc_18_start_FIFO_blk;
    wire [2:0] proc_18_TLF_FIFO_blk;
    wire [2:0] proc_18_input_sync_blk;
    wire [2:0] proc_18_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_18;
    reg [2:0] proc_dep_vld_vec_18_reg;
    wire [2:0] in_chan_dep_vld_vec_18;
    wire [116:0] in_chan_dep_data_vec_18;
    wire [2:0] token_in_vec_18;
    wire [2:0] out_chan_dep_vld_vec_18;
    wire [38:0] out_chan_dep_data_18;
    wire [2:0] token_out_vec_18;
    wire dl_detect_out_18;
    wire dep_chan_vld_16_18;
    wire [38:0] dep_chan_data_16_18;
    wire token_16_18;
    wire dep_chan_vld_17_18;
    wire [38:0] dep_chan_data_17_18;
    wire token_17_18;
    wire dep_chan_vld_19_18;
    wire [38:0] dep_chan_data_19_18;
    wire token_19_18;
    wire [2:0] proc_19_data_FIFO_blk;
    wire [2:0] proc_19_data_PIPO_blk;
    wire [2:0] proc_19_start_FIFO_blk;
    wire [2:0] proc_19_TLF_FIFO_blk;
    wire [2:0] proc_19_input_sync_blk;
    wire [2:0] proc_19_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_19;
    reg [2:0] proc_dep_vld_vec_19_reg;
    wire [2:0] in_chan_dep_vld_vec_19;
    wire [116:0] in_chan_dep_data_vec_19;
    wire [2:0] token_in_vec_19;
    wire [2:0] out_chan_dep_vld_vec_19;
    wire [38:0] out_chan_dep_data_19;
    wire [2:0] token_out_vec_19;
    wire dl_detect_out_19;
    wire dep_chan_vld_16_19;
    wire [38:0] dep_chan_data_16_19;
    wire token_16_19;
    wire dep_chan_vld_17_19;
    wire [38:0] dep_chan_data_17_19;
    wire token_17_19;
    wire dep_chan_vld_18_19;
    wire [38:0] dep_chan_data_18_19;
    wire token_18_19;
    wire [9:0] proc_20_data_FIFO_blk;
    wire [9:0] proc_20_data_PIPO_blk;
    wire [9:0] proc_20_start_FIFO_blk;
    wire [9:0] proc_20_TLF_FIFO_blk;
    wire [9:0] proc_20_input_sync_blk;
    wire [9:0] proc_20_output_sync_blk;
    wire [9:0] proc_dep_vld_vec_20;
    reg [9:0] proc_dep_vld_vec_20_reg;
    wire [9:0] in_chan_dep_vld_vec_20;
    wire [389:0] in_chan_dep_data_vec_20;
    wire [9:0] token_in_vec_20;
    wire [9:0] out_chan_dep_vld_vec_20;
    wire [38:0] out_chan_dep_data_20;
    wire [9:0] token_out_vec_20;
    wire dl_detect_out_20;
    wire dep_chan_vld_4_20;
    wire [38:0] dep_chan_data_4_20;
    wire token_4_20;
    wire dep_chan_vld_5_20;
    wire [38:0] dep_chan_data_5_20;
    wire token_5_20;
    wire dep_chan_vld_8_20;
    wire [38:0] dep_chan_data_8_20;
    wire token_8_20;
    wire dep_chan_vld_9_20;
    wire [38:0] dep_chan_data_9_20;
    wire token_9_20;
    wire dep_chan_vld_10_20;
    wire [38:0] dep_chan_data_10_20;
    wire token_10_20;
    wire dep_chan_vld_15_20;
    wire [38:0] dep_chan_data_15_20;
    wire token_15_20;
    wire dep_chan_vld_21_20;
    wire [38:0] dep_chan_data_21_20;
    wire token_21_20;
    wire dep_chan_vld_23_20;
    wire [38:0] dep_chan_data_23_20;
    wire token_23_20;
    wire dep_chan_vld_31_20;
    wire [38:0] dep_chan_data_31_20;
    wire token_31_20;
    wire dep_chan_vld_38_20;
    wire [38:0] dep_chan_data_38_20;
    wire token_38_20;
    wire [9:0] proc_21_data_FIFO_blk;
    wire [9:0] proc_21_data_PIPO_blk;
    wire [9:0] proc_21_start_FIFO_blk;
    wire [9:0] proc_21_TLF_FIFO_blk;
    wire [9:0] proc_21_input_sync_blk;
    wire [9:0] proc_21_output_sync_blk;
    wire [9:0] proc_dep_vld_vec_21;
    reg [9:0] proc_dep_vld_vec_21_reg;
    wire [9:0] in_chan_dep_vld_vec_21;
    wire [389:0] in_chan_dep_data_vec_21;
    wire [9:0] token_in_vec_21;
    wire [9:0] out_chan_dep_vld_vec_21;
    wire [38:0] out_chan_dep_data_21;
    wire [9:0] token_out_vec_21;
    wire dl_detect_out_21;
    wire dep_chan_vld_4_21;
    wire [38:0] dep_chan_data_4_21;
    wire token_4_21;
    wire dep_chan_vld_5_21;
    wire [38:0] dep_chan_data_5_21;
    wire token_5_21;
    wire dep_chan_vld_8_21;
    wire [38:0] dep_chan_data_8_21;
    wire token_8_21;
    wire dep_chan_vld_9_21;
    wire [38:0] dep_chan_data_9_21;
    wire token_9_21;
    wire dep_chan_vld_10_21;
    wire [38:0] dep_chan_data_10_21;
    wire token_10_21;
    wire dep_chan_vld_15_21;
    wire [38:0] dep_chan_data_15_21;
    wire token_15_21;
    wire dep_chan_vld_20_21;
    wire [38:0] dep_chan_data_20_21;
    wire token_20_21;
    wire dep_chan_vld_23_21;
    wire [38:0] dep_chan_data_23_21;
    wire token_23_21;
    wire dep_chan_vld_31_21;
    wire [38:0] dep_chan_data_31_21;
    wire token_31_21;
    wire dep_chan_vld_38_21;
    wire [38:0] dep_chan_data_38_21;
    wire token_38_21;
    wire [1:0] proc_22_data_FIFO_blk;
    wire [1:0] proc_22_data_PIPO_blk;
    wire [1:0] proc_22_start_FIFO_blk;
    wire [1:0] proc_22_TLF_FIFO_blk;
    wire [1:0] proc_22_input_sync_blk;
    wire [1:0] proc_22_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_22;
    reg [1:0] proc_dep_vld_vec_22_reg;
    wire [1:0] in_chan_dep_vld_vec_22;
    wire [77:0] in_chan_dep_data_vec_22;
    wire [1:0] token_in_vec_22;
    wire [1:0] out_chan_dep_vld_vec_22;
    wire [38:0] out_chan_dep_data_22;
    wire [1:0] token_out_vec_22;
    wire dl_detect_out_22;
    wire dep_chan_vld_0_22;
    wire [38:0] dep_chan_data_0_22;
    wire token_0_22;
    wire dep_chan_vld_23_22;
    wire [38:0] dep_chan_data_23_22;
    wire token_23_22;
    wire [11:0] proc_23_data_FIFO_blk;
    wire [11:0] proc_23_data_PIPO_blk;
    wire [11:0] proc_23_start_FIFO_blk;
    wire [11:0] proc_23_TLF_FIFO_blk;
    wire [11:0] proc_23_input_sync_blk;
    wire [11:0] proc_23_output_sync_blk;
    wire [11:0] proc_dep_vld_vec_23;
    reg [11:0] proc_dep_vld_vec_23_reg;
    wire [11:0] in_chan_dep_vld_vec_23;
    wire [467:0] in_chan_dep_data_vec_23;
    wire [11:0] token_in_vec_23;
    wire [11:0] out_chan_dep_vld_vec_23;
    wire [38:0] out_chan_dep_data_23;
    wire [11:0] token_out_vec_23;
    wire dl_detect_out_23;
    wire dep_chan_vld_0_23;
    wire [38:0] dep_chan_data_0_23;
    wire token_0_23;
    wire dep_chan_vld_4_23;
    wire [38:0] dep_chan_data_4_23;
    wire token_4_23;
    wire dep_chan_vld_5_23;
    wire [38:0] dep_chan_data_5_23;
    wire token_5_23;
    wire dep_chan_vld_8_23;
    wire [38:0] dep_chan_data_8_23;
    wire token_8_23;
    wire dep_chan_vld_9_23;
    wire [38:0] dep_chan_data_9_23;
    wire token_9_23;
    wire dep_chan_vld_10_23;
    wire [38:0] dep_chan_data_10_23;
    wire token_10_23;
    wire dep_chan_vld_15_23;
    wire [38:0] dep_chan_data_15_23;
    wire token_15_23;
    wire dep_chan_vld_20_23;
    wire [38:0] dep_chan_data_20_23;
    wire token_20_23;
    wire dep_chan_vld_21_23;
    wire [38:0] dep_chan_data_21_23;
    wire token_21_23;
    wire dep_chan_vld_22_23;
    wire [38:0] dep_chan_data_22_23;
    wire token_22_23;
    wire dep_chan_vld_31_23;
    wire [38:0] dep_chan_data_31_23;
    wire token_31_23;
    wire dep_chan_vld_38_23;
    wire [38:0] dep_chan_data_38_23;
    wire token_38_23;
    wire [0:0] proc_24_data_FIFO_blk;
    wire [0:0] proc_24_data_PIPO_blk;
    wire [0:0] proc_24_start_FIFO_blk;
    wire [0:0] proc_24_TLF_FIFO_blk;
    wire [0:0] proc_24_input_sync_blk;
    wire [0:0] proc_24_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_24;
    reg [0:0] proc_dep_vld_vec_24_reg;
    wire [0:0] in_chan_dep_vld_vec_24;
    wire [38:0] in_chan_dep_data_vec_24;
    wire [0:0] token_in_vec_24;
    wire [0:0] out_chan_dep_vld_vec_24;
    wire [38:0] out_chan_dep_data_24;
    wire [0:0] token_out_vec_24;
    wire dl_detect_out_24;
    wire dep_chan_vld_27_24;
    wire [38:0] dep_chan_data_27_24;
    wire token_27_24;
    wire [0:0] proc_25_data_FIFO_blk;
    wire [0:0] proc_25_data_PIPO_blk;
    wire [0:0] proc_25_start_FIFO_blk;
    wire [0:0] proc_25_TLF_FIFO_blk;
    wire [0:0] proc_25_input_sync_blk;
    wire [0:0] proc_25_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_25;
    reg [0:0] proc_dep_vld_vec_25_reg;
    wire [0:0] in_chan_dep_vld_vec_25;
    wire [38:0] in_chan_dep_data_vec_25;
    wire [0:0] token_in_vec_25;
    wire [0:0] out_chan_dep_vld_vec_25;
    wire [38:0] out_chan_dep_data_25;
    wire [0:0] token_out_vec_25;
    wire dl_detect_out_25;
    wire dep_chan_vld_26_25;
    wire [38:0] dep_chan_data_26_25;
    wire token_26_25;
    wire [0:0] proc_26_data_FIFO_blk;
    wire [0:0] proc_26_data_PIPO_blk;
    wire [0:0] proc_26_start_FIFO_blk;
    wire [0:0] proc_26_TLF_FIFO_blk;
    wire [0:0] proc_26_input_sync_blk;
    wire [0:0] proc_26_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_26;
    reg [0:0] proc_dep_vld_vec_26_reg;
    wire [0:0] in_chan_dep_vld_vec_26;
    wire [38:0] in_chan_dep_data_vec_26;
    wire [0:0] token_in_vec_26;
    wire [0:0] out_chan_dep_vld_vec_26;
    wire [38:0] out_chan_dep_data_26;
    wire [0:0] token_out_vec_26;
    wire dl_detect_out_26;
    wire dep_chan_vld_25_26;
    wire [38:0] dep_chan_data_25_26;
    wire token_25_26;
    wire [0:0] proc_27_data_FIFO_blk;
    wire [0:0] proc_27_data_PIPO_blk;
    wire [0:0] proc_27_start_FIFO_blk;
    wire [0:0] proc_27_TLF_FIFO_blk;
    wire [0:0] proc_27_input_sync_blk;
    wire [0:0] proc_27_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_27;
    reg [0:0] proc_dep_vld_vec_27_reg;
    wire [0:0] in_chan_dep_vld_vec_27;
    wire [38:0] in_chan_dep_data_vec_27;
    wire [0:0] token_in_vec_27;
    wire [0:0] out_chan_dep_vld_vec_27;
    wire [38:0] out_chan_dep_data_27;
    wire [0:0] token_out_vec_27;
    wire dl_detect_out_27;
    wire dep_chan_vld_24_27;
    wire [38:0] dep_chan_data_24_27;
    wire token_24_27;
    wire [0:0] proc_28_data_FIFO_blk;
    wire [0:0] proc_28_data_PIPO_blk;
    wire [0:0] proc_28_start_FIFO_blk;
    wire [0:0] proc_28_TLF_FIFO_blk;
    wire [0:0] proc_28_input_sync_blk;
    wire [0:0] proc_28_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_28;
    reg [0:0] proc_dep_vld_vec_28_reg;
    wire [0:0] in_chan_dep_vld_vec_28;
    wire [38:0] in_chan_dep_data_vec_28;
    wire [0:0] token_in_vec_28;
    wire [0:0] out_chan_dep_vld_vec_28;
    wire [38:0] out_chan_dep_data_28;
    wire [0:0] token_out_vec_28;
    wire dl_detect_out_28;
    wire dep_chan_vld_29_28;
    wire [38:0] dep_chan_data_29_28;
    wire token_29_28;
    wire [0:0] proc_29_data_FIFO_blk;
    wire [0:0] proc_29_data_PIPO_blk;
    wire [0:0] proc_29_start_FIFO_blk;
    wire [0:0] proc_29_TLF_FIFO_blk;
    wire [0:0] proc_29_input_sync_blk;
    wire [0:0] proc_29_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_29;
    reg [0:0] proc_dep_vld_vec_29_reg;
    wire [0:0] in_chan_dep_vld_vec_29;
    wire [38:0] in_chan_dep_data_vec_29;
    wire [0:0] token_in_vec_29;
    wire [0:0] out_chan_dep_vld_vec_29;
    wire [38:0] out_chan_dep_data_29;
    wire [0:0] token_out_vec_29;
    wire dl_detect_out_29;
    wire dep_chan_vld_28_29;
    wire [38:0] dep_chan_data_28_29;
    wire token_28_29;
    wire [1:0] proc_30_data_FIFO_blk;
    wire [1:0] proc_30_data_PIPO_blk;
    wire [1:0] proc_30_start_FIFO_blk;
    wire [1:0] proc_30_TLF_FIFO_blk;
    wire [1:0] proc_30_input_sync_blk;
    wire [1:0] proc_30_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_30;
    reg [1:0] proc_dep_vld_vec_30_reg;
    wire [1:0] in_chan_dep_vld_vec_30;
    wire [77:0] in_chan_dep_data_vec_30;
    wire [1:0] token_in_vec_30;
    wire [1:0] out_chan_dep_vld_vec_30;
    wire [38:0] out_chan_dep_data_30;
    wire [1:0] token_out_vec_30;
    wire dl_detect_out_30;
    wire dep_chan_vld_1_30;
    wire [38:0] dep_chan_data_1_30;
    wire token_1_30;
    wire dep_chan_vld_31_30;
    wire [38:0] dep_chan_data_31_30;
    wire token_31_30;
    wire [15:0] proc_31_data_FIFO_blk;
    wire [15:0] proc_31_data_PIPO_blk;
    wire [15:0] proc_31_start_FIFO_blk;
    wire [15:0] proc_31_TLF_FIFO_blk;
    wire [15:0] proc_31_input_sync_blk;
    wire [15:0] proc_31_output_sync_blk;
    wire [15:0] proc_dep_vld_vec_31;
    reg [15:0] proc_dep_vld_vec_31_reg;
    wire [15:0] in_chan_dep_vld_vec_31;
    wire [623:0] in_chan_dep_data_vec_31;
    wire [15:0] token_in_vec_31;
    wire [15:0] out_chan_dep_vld_vec_31;
    wire [38:0] out_chan_dep_data_31;
    wire [15:0] token_out_vec_31;
    wire dl_detect_out_31;
    wire dep_chan_vld_1_31;
    wire [38:0] dep_chan_data_1_31;
    wire token_1_31;
    wire dep_chan_vld_2_31;
    wire [38:0] dep_chan_data_2_31;
    wire token_2_31;
    wire dep_chan_vld_3_31;
    wire [38:0] dep_chan_data_3_31;
    wire token_3_31;
    wire dep_chan_vld_4_31;
    wire [38:0] dep_chan_data_4_31;
    wire token_4_31;
    wire dep_chan_vld_5_31;
    wire [38:0] dep_chan_data_5_31;
    wire token_5_31;
    wire dep_chan_vld_6_31;
    wire [38:0] dep_chan_data_6_31;
    wire token_6_31;
    wire dep_chan_vld_7_31;
    wire [38:0] dep_chan_data_7_31;
    wire token_7_31;
    wire dep_chan_vld_8_31;
    wire [38:0] dep_chan_data_8_31;
    wire token_8_31;
    wire dep_chan_vld_9_31;
    wire [38:0] dep_chan_data_9_31;
    wire token_9_31;
    wire dep_chan_vld_10_31;
    wire [38:0] dep_chan_data_10_31;
    wire token_10_31;
    wire dep_chan_vld_15_31;
    wire [38:0] dep_chan_data_15_31;
    wire token_15_31;
    wire dep_chan_vld_20_31;
    wire [38:0] dep_chan_data_20_31;
    wire token_20_31;
    wire dep_chan_vld_21_31;
    wire [38:0] dep_chan_data_21_31;
    wire token_21_31;
    wire dep_chan_vld_23_31;
    wire [38:0] dep_chan_data_23_31;
    wire token_23_31;
    wire dep_chan_vld_30_31;
    wire [38:0] dep_chan_data_30_31;
    wire token_30_31;
    wire dep_chan_vld_38_31;
    wire [38:0] dep_chan_data_38_31;
    wire token_38_31;
    wire [0:0] proc_32_data_FIFO_blk;
    wire [0:0] proc_32_data_PIPO_blk;
    wire [0:0] proc_32_start_FIFO_blk;
    wire [0:0] proc_32_TLF_FIFO_blk;
    wire [0:0] proc_32_input_sync_blk;
    wire [0:0] proc_32_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_32;
    reg [0:0] proc_dep_vld_vec_32_reg;
    wire [0:0] in_chan_dep_vld_vec_32;
    wire [38:0] in_chan_dep_data_vec_32;
    wire [0:0] token_in_vec_32;
    wire [0:0] out_chan_dep_vld_vec_32;
    wire [38:0] out_chan_dep_data_32;
    wire [0:0] token_out_vec_32;
    wire dl_detect_out_32;
    wire dep_chan_vld_35_32;
    wire [38:0] dep_chan_data_35_32;
    wire token_35_32;
    wire [0:0] proc_33_data_FIFO_blk;
    wire [0:0] proc_33_data_PIPO_blk;
    wire [0:0] proc_33_start_FIFO_blk;
    wire [0:0] proc_33_TLF_FIFO_blk;
    wire [0:0] proc_33_input_sync_blk;
    wire [0:0] proc_33_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_33;
    reg [0:0] proc_dep_vld_vec_33_reg;
    wire [0:0] in_chan_dep_vld_vec_33;
    wire [38:0] in_chan_dep_data_vec_33;
    wire [0:0] token_in_vec_33;
    wire [0:0] out_chan_dep_vld_vec_33;
    wire [38:0] out_chan_dep_data_33;
    wire [0:0] token_out_vec_33;
    wire dl_detect_out_33;
    wire dep_chan_vld_34_33;
    wire [38:0] dep_chan_data_34_33;
    wire token_34_33;
    wire [0:0] proc_34_data_FIFO_blk;
    wire [0:0] proc_34_data_PIPO_blk;
    wire [0:0] proc_34_start_FIFO_blk;
    wire [0:0] proc_34_TLF_FIFO_blk;
    wire [0:0] proc_34_input_sync_blk;
    wire [0:0] proc_34_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_34;
    reg [0:0] proc_dep_vld_vec_34_reg;
    wire [0:0] in_chan_dep_vld_vec_34;
    wire [38:0] in_chan_dep_data_vec_34;
    wire [0:0] token_in_vec_34;
    wire [0:0] out_chan_dep_vld_vec_34;
    wire [38:0] out_chan_dep_data_34;
    wire [0:0] token_out_vec_34;
    wire dl_detect_out_34;
    wire dep_chan_vld_33_34;
    wire [38:0] dep_chan_data_33_34;
    wire token_33_34;
    wire [0:0] proc_35_data_FIFO_blk;
    wire [0:0] proc_35_data_PIPO_blk;
    wire [0:0] proc_35_start_FIFO_blk;
    wire [0:0] proc_35_TLF_FIFO_blk;
    wire [0:0] proc_35_input_sync_blk;
    wire [0:0] proc_35_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_35;
    reg [0:0] proc_dep_vld_vec_35_reg;
    wire [0:0] in_chan_dep_vld_vec_35;
    wire [38:0] in_chan_dep_data_vec_35;
    wire [0:0] token_in_vec_35;
    wire [0:0] out_chan_dep_vld_vec_35;
    wire [38:0] out_chan_dep_data_35;
    wire [0:0] token_out_vec_35;
    wire dl_detect_out_35;
    wire dep_chan_vld_32_35;
    wire [38:0] dep_chan_data_32_35;
    wire token_32_35;
    wire [0:0] proc_36_data_FIFO_blk;
    wire [0:0] proc_36_data_PIPO_blk;
    wire [0:0] proc_36_start_FIFO_blk;
    wire [0:0] proc_36_TLF_FIFO_blk;
    wire [0:0] proc_36_input_sync_blk;
    wire [0:0] proc_36_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_36;
    reg [0:0] proc_dep_vld_vec_36_reg;
    wire [0:0] in_chan_dep_vld_vec_36;
    wire [38:0] in_chan_dep_data_vec_36;
    wire [0:0] token_in_vec_36;
    wire [0:0] out_chan_dep_vld_vec_36;
    wire [38:0] out_chan_dep_data_36;
    wire [0:0] token_out_vec_36;
    wire dl_detect_out_36;
    wire dep_chan_vld_37_36;
    wire [38:0] dep_chan_data_37_36;
    wire token_37_36;
    wire [0:0] proc_37_data_FIFO_blk;
    wire [0:0] proc_37_data_PIPO_blk;
    wire [0:0] proc_37_start_FIFO_blk;
    wire [0:0] proc_37_TLF_FIFO_blk;
    wire [0:0] proc_37_input_sync_blk;
    wire [0:0] proc_37_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_37;
    reg [0:0] proc_dep_vld_vec_37_reg;
    wire [0:0] in_chan_dep_vld_vec_37;
    wire [38:0] in_chan_dep_data_vec_37;
    wire [0:0] token_in_vec_37;
    wire [0:0] out_chan_dep_vld_vec_37;
    wire [38:0] out_chan_dep_data_37;
    wire [0:0] token_out_vec_37;
    wire dl_detect_out_37;
    wire dep_chan_vld_36_37;
    wire [38:0] dep_chan_data_36_37;
    wire token_36_37;
    wire [9:0] proc_38_data_FIFO_blk;
    wire [9:0] proc_38_data_PIPO_blk;
    wire [9:0] proc_38_start_FIFO_blk;
    wire [9:0] proc_38_TLF_FIFO_blk;
    wire [9:0] proc_38_input_sync_blk;
    wire [9:0] proc_38_output_sync_blk;
    wire [9:0] proc_dep_vld_vec_38;
    reg [9:0] proc_dep_vld_vec_38_reg;
    wire [9:0] in_chan_dep_vld_vec_38;
    wire [389:0] in_chan_dep_data_vec_38;
    wire [9:0] token_in_vec_38;
    wire [9:0] out_chan_dep_vld_vec_38;
    wire [38:0] out_chan_dep_data_38;
    wire [9:0] token_out_vec_38;
    wire dl_detect_out_38;
    wire dep_chan_vld_4_38;
    wire [38:0] dep_chan_data_4_38;
    wire token_4_38;
    wire dep_chan_vld_5_38;
    wire [38:0] dep_chan_data_5_38;
    wire token_5_38;
    wire dep_chan_vld_8_38;
    wire [38:0] dep_chan_data_8_38;
    wire token_8_38;
    wire dep_chan_vld_9_38;
    wire [38:0] dep_chan_data_9_38;
    wire token_9_38;
    wire dep_chan_vld_10_38;
    wire [38:0] dep_chan_data_10_38;
    wire token_10_38;
    wire dep_chan_vld_15_38;
    wire [38:0] dep_chan_data_15_38;
    wire token_15_38;
    wire dep_chan_vld_20_38;
    wire [38:0] dep_chan_data_20_38;
    wire token_20_38;
    wire dep_chan_vld_21_38;
    wire [38:0] dep_chan_data_21_38;
    wire token_21_38;
    wire dep_chan_vld_23_38;
    wire [38:0] dep_chan_data_23_38;
    wire token_23_38;
    wire dep_chan_vld_31_38;
    wire [38:0] dep_chan_data_31_38;
    wire token_31_38;
    wire [38:0] dl_in_vec;
    wire dl_detect_out;
    wire token_clear;
    reg [38:0] origin;

    reg ap_done_reg_0;// for module grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_0 <= 'b0;
        end
        else begin
            ap_done_reg_0 <= grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_continue;
        end
    end

    reg ap_done_reg_1;// for module grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_1 <= 'b0;
        end
        else begin
            ap_done_reg_1 <= grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_continue;
        end
    end

    reg ap_done_reg_2;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_2 <= 'b0;
        end
        else begin
            ap_done_reg_2 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_continue;
        end
    end

    reg ap_done_reg_3;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_3 <= 'b0;
        end
        else begin
            ap_done_reg_3 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_continue;
        end
    end

    reg ap_done_reg_4;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_4 <= 'b0;
        end
        else begin
            ap_done_reg_4 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_continue;
        end
    end

    reg ap_done_reg_5;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_5 <= 'b0;
        end
        else begin
            ap_done_reg_5 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_continue;
        end
    end

    reg ap_done_reg_6;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_6 <= 'b0;
        end
        else begin
            ap_done_reg_6 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_continue;
        end
    end

    reg ap_done_reg_7;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_7 <= 'b0;
        end
        else begin
            ap_done_reg_7 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_continue;
        end
    end

    reg ap_done_reg_8;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_8 <= 'b0;
        end
        else begin
            ap_done_reg_8 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_continue;
        end
    end

    reg ap_done_reg_9;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_9 <= 'b0;
        end
        else begin
            ap_done_reg_9 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_continue;
        end
    end

    reg ap_done_reg_10;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_10 <= 'b0;
        end
        else begin
            ap_done_reg_10 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_continue;
        end
    end

    reg ap_done_reg_11;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_11 <= 'b0;
        end
        else begin
            ap_done_reg_11 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_continue;
        end
    end

    reg ap_done_reg_12;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_12 <= 'b0;
        end
        else begin
            ap_done_reg_12 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_continue;
        end
    end

    reg ap_done_reg_13;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_13 <= 'b0;
        end
        else begin
            ap_done_reg_13 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_continue;
        end
    end

    reg ap_done_reg_14;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_14 <= 'b0;
        end
        else begin
            ap_done_reg_14 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_continue;
        end
    end

    reg ap_done_reg_15;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_15 <= 'b0;
        end
        else begin
            ap_done_reg_15 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_continue;
        end
    end

    reg ap_done_reg_16;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_16 <= 'b0;
        end
        else begin
            ap_done_reg_16 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_continue;
        end
    end

    reg ap_done_reg_17;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_17 <= 'b0;
        end
        else begin
            ap_done_reg_17 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_continue;
        end
    end

    reg ap_done_reg_18;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_18 <= 'b0;
        end
        else begin
            ap_done_reg_18 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_continue;
        end
    end

    reg ap_done_reg_19;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_19 <= 'b0;
        end
        else begin
            ap_done_reg_19 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.ap_continue;
        end
    end

    reg ap_done_reg_20;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_20 <= 'b0;
        end
        else begin
            ap_done_reg_20 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.ap_continue;
        end
    end

    reg ap_done_reg_21;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_21 <= 'b0;
        end
        else begin
            ap_done_reg_21 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.ap_continue;
        end
    end

    reg ap_done_reg_22;// for module grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_22 <= 'b0;
        end
        else begin
            ap_done_reg_22 <= grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.ap_continue;
        end
    end

reg [15:0] trans_in_cnt_0;// for process grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_0 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.start_write == 1'b1) begin
        trans_in_cnt_0 <= trans_in_cnt_0 + 16'h1;
    end
    else begin
        trans_in_cnt_0 <= trans_in_cnt_0;
    end
end

reg [15:0] trans_out_cnt_0;// for process grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_0 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_continue == 1'b1) begin
        trans_out_cnt_0 <= trans_out_cnt_0 + 16'h1;
    end
    else begin
        trans_out_cnt_0 <= trans_out_cnt_0;
    end
end

reg [15:0] trans_in_cnt_1;// for process grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_1 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.start_write == 1'b1) begin
        trans_in_cnt_1 <= trans_in_cnt_1 + 16'h1;
    end
    else begin
        trans_in_cnt_1 <= trans_in_cnt_1;
    end
end

reg [15:0] trans_out_cnt_1;// for process grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_1 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_continue == 1'b1) begin
        trans_out_cnt_1 <= trans_out_cnt_1 + 16'h1;
    end
    else begin
        trans_out_cnt_1 <= trans_out_cnt_1;
    end
end

reg [15:0] trans_in_cnt_2;// for process grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_2 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.start_write == 1'b1) begin
        trans_in_cnt_2 <= trans_in_cnt_2 + 16'h1;
    end
    else begin
        trans_in_cnt_2 <= trans_in_cnt_2;
    end
end

reg [15:0] trans_out_cnt_2;// for process grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_2 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_continue == 1'b1) begin
        trans_out_cnt_2 <= trans_out_cnt_2 + 16'h1;
    end
    else begin
        trans_out_cnt_2 <= trans_out_cnt_2;
    end
end

reg [15:0] trans_in_cnt_3;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_3 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.start_write == 1'b1) begin
        trans_in_cnt_3 <= trans_in_cnt_3 + 16'h1;
    end
    else begin
        trans_in_cnt_3 <= trans_in_cnt_3;
    end
end

reg [15:0] trans_out_cnt_3;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_3 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_continue == 1'b1) begin
        trans_out_cnt_3 <= trans_out_cnt_3 + 16'h1;
    end
    else begin
        trans_out_cnt_3 <= trans_out_cnt_3;
    end
end

reg [15:0] trans_in_cnt_4;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_4 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.start_write == 1'b1) begin
        trans_in_cnt_4 <= trans_in_cnt_4 + 16'h1;
    end
    else begin
        trans_in_cnt_4 <= trans_in_cnt_4;
    end
end

reg [15:0] trans_out_cnt_4;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_4 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_continue == 1'b1) begin
        trans_out_cnt_4 <= trans_out_cnt_4 + 16'h1;
    end
    else begin
        trans_out_cnt_4 <= trans_out_cnt_4;
    end
end

reg [15:0] trans_in_cnt_5;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_5 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.start_write == 1'b1) begin
        trans_in_cnt_5 <= trans_in_cnt_5 + 16'h1;
    end
    else begin
        trans_in_cnt_5 <= trans_in_cnt_5;
    end
end

reg [15:0] trans_out_cnt_5;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_5 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_continue == 1'b1) begin
        trans_out_cnt_5 <= trans_out_cnt_5 + 16'h1;
    end
    else begin
        trans_out_cnt_5 <= trans_out_cnt_5;
    end
end

reg [15:0] trans_in_cnt_6;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_6 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.start_write == 1'b1) begin
        trans_in_cnt_6 <= trans_in_cnt_6 + 16'h1;
    end
    else begin
        trans_in_cnt_6 <= trans_in_cnt_6;
    end
end

reg [15:0] trans_out_cnt_6;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_6 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_continue == 1'b1) begin
        trans_out_cnt_6 <= trans_out_cnt_6 + 16'h1;
    end
    else begin
        trans_out_cnt_6 <= trans_out_cnt_6;
    end
end

reg [15:0] trans_in_cnt_7;// for process grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_7 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.start_write == 1'b1) begin
        trans_in_cnt_7 <= trans_in_cnt_7 + 16'h1;
    end
    else begin
        trans_in_cnt_7 <= trans_in_cnt_7;
    end
end

reg [15:0] trans_out_cnt_7;// for process grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_7 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_continue == 1'b1) begin
        trans_out_cnt_7 <= trans_out_cnt_7 + 16'h1;
    end
    else begin
        trans_out_cnt_7 <= trans_out_cnt_7;
    end
end

reg [15:0] trans_in_cnt_8;// for process grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_8 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.start_write == 1'b1) begin
        trans_in_cnt_8 <= trans_in_cnt_8 + 16'h1;
    end
    else begin
        trans_in_cnt_8 <= trans_in_cnt_8;
    end
end

reg [15:0] trans_out_cnt_8;// for process grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_8 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_continue == 1'b1) begin
        trans_out_cnt_8 <= trans_out_cnt_8 + 16'h1;
    end
    else begin
        trans_out_cnt_8 <= trans_out_cnt_8;
    end
end

reg [15:0] trans_in_cnt_9;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_9 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0.start_write == 1'b1) begin
        trans_in_cnt_9 <= trans_in_cnt_9 + 16'h1;
    end
    else begin
        trans_in_cnt_9 <= trans_in_cnt_9;
    end
end

reg [15:0] trans_out_cnt_9;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_9 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0.ap_continue == 1'b1) begin
        trans_out_cnt_9 <= trans_out_cnt_9 + 16'h1;
    end
    else begin
        trans_out_cnt_9 <= trans_out_cnt_9;
    end
end

reg [15:0] trans_in_cnt_10;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_10 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0.start_write == 1'b1) begin
        trans_in_cnt_10 <= trans_in_cnt_10 + 16'h1;
    end
    else begin
        trans_in_cnt_10 <= trans_in_cnt_10;
    end
end

reg [15:0] trans_out_cnt_10;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_10 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0.ap_continue == 1'b1) begin
        trans_out_cnt_10 <= trans_out_cnt_10 + 16'h1;
    end
    else begin
        trans_out_cnt_10 <= trans_out_cnt_10;
    end
end

reg [15:0] trans_in_cnt_11;// for process grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_11 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.start_write == 1'b1) begin
        trans_in_cnt_11 <= trans_in_cnt_11 + 16'h1;
    end
    else begin
        trans_in_cnt_11 <= trans_in_cnt_11;
    end
end

reg [15:0] trans_out_cnt_11;// for process grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_11 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_continue == 1'b1) begin
        trans_out_cnt_11 <= trans_out_cnt_11 + 16'h1;
    end
    else begin
        trans_out_cnt_11 <= trans_out_cnt_11;
    end
end

reg [15:0] trans_in_cnt_12;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_12 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.start_write == 1'b1) begin
        trans_in_cnt_12 <= trans_in_cnt_12 + 16'h1;
    end
    else begin
        trans_in_cnt_12 <= trans_in_cnt_12;
    end
end

reg [15:0] trans_out_cnt_12;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_12 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.ap_continue == 1'b1) begin
        trans_out_cnt_12 <= trans_out_cnt_12 + 16'h1;
    end
    else begin
        trans_out_cnt_12 <= trans_out_cnt_12;
    end
end

reg [15:0] trans_in_cnt_13;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_13 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.start_write == 1'b1) begin
        trans_in_cnt_13 <= trans_in_cnt_13 + 16'h1;
    end
    else begin
        trans_in_cnt_13 <= trans_in_cnt_13;
    end
end

reg [15:0] trans_out_cnt_13;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_13 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_13 <= trans_out_cnt_13 + 16'h1;
    end
    else begin
        trans_out_cnt_13 <= trans_out_cnt_13;
    end
end

reg [15:0] trans_in_cnt_14;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_14 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.start_write == 1'b1) begin
        trans_in_cnt_14 <= trans_in_cnt_14 + 16'h1;
    end
    else begin
        trans_in_cnt_14 <= trans_in_cnt_14;
    end
end

reg [15:0] trans_out_cnt_14;// for process grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_14 <= 16'h0;
    end
    else if (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done == 1'b1 && grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_14 <= trans_out_cnt_14 + 16'h1;
    end
    else begin
        trans_out_cnt_14 <= trans_out_cnt_14;
    end
end

    // Process: grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 0, 11, 11) cnn_pipeline_v10_hls_deadlock_detect_unit_0 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_0),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_0),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_0),
        .token_in_vec(token_in_vec_0),
        .dl_detect_in(dl_detect_out),
        .origin(origin[0]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_0),
        .out_chan_dep_data(out_chan_dep_data_0),
        .token_out_vec(token_out_vec_0),
        .dl_detect_out(dl_in_vec[0]));

    assign proc_0_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.grp_param_broker_4_Pipeline_read_parameter_burst_fu_447.p1_data_0_blk_n);
    assign proc_0_data_PIPO_blk[0] = 1'b0;
    assign proc_0_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_depthwise_chain_3_4_false_0_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.real_start & (trans_in_cnt_2 == trans_out_cnt_2) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_depthwise_chain_3_4_false_0_U0_U.if_read);
    assign proc_0_TLF_FIFO_blk[0] = 1'b0;
    assign proc_0_input_sync_blk[0] = 1'b0;
    assign proc_0_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_0[0] = dl_detect_out ? proc_dep_vld_vec_0_reg[0] : (proc_0_data_FIFO_blk[0] | proc_0_data_PIPO_blk[0] | proc_0_start_FIFO_blk[0] | proc_0_TLF_FIFO_blk[0] | proc_0_input_sync_blk[0] | proc_0_output_sync_blk[0]);
    assign proc_0_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.grp_param_broker_4_Pipeline_read_parameter_burst_fu_447.p1_data_1_blk_n);
    assign proc_0_data_PIPO_blk[1] = 1'b0;
    assign proc_0_start_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_depthwise_chain_7_16_true_1_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.real_start & (trans_in_cnt_2 == trans_out_cnt_2) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_depthwise_chain_7_16_true_1_U0_U.if_read);
    assign proc_0_TLF_FIFO_blk[1] = 1'b0;
    assign proc_0_input_sync_blk[1] = 1'b0;
    assign proc_0_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_0[1] = dl_detect_out ? proc_dep_vld_vec_0_reg[1] : (proc_0_data_FIFO_blk[1] | proc_0_data_PIPO_blk[1] | proc_0_start_FIFO_blk[1] | proc_0_TLF_FIFO_blk[1] | proc_0_input_sync_blk[1] | proc_0_output_sync_blk[1]);
    assign proc_0_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.grp_param_broker_4_Pipeline_read_parameter_burst_fu_447.p1_data_2_blk_n);
    assign proc_0_data_PIPO_blk[2] = 1'b0;
    assign proc_0_start_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_pointwise1_chain_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.real_start & (trans_in_cnt_2 == trans_out_cnt_2) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_pointwise1_chain_U0_U.if_read);
    assign proc_0_TLF_FIFO_blk[2] = 1'b0;
    assign proc_0_input_sync_blk[2] = 1'b0;
    assign proc_0_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_0[2] = dl_detect_out ? proc_dep_vld_vec_0_reg[2] : (proc_0_data_FIFO_blk[2] | proc_0_data_PIPO_blk[2] | proc_0_start_FIFO_blk[2] | proc_0_TLF_FIFO_blk[2] | proc_0_input_sync_blk[2] | proc_0_output_sync_blk[2]);
    assign proc_0_data_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.grp_param_broker_4_Pipeline_read_parameter_burst_fu_447.p1_data_3_blk_n);
    assign proc_0_data_PIPO_blk[3] = 1'b0;
    assign proc_0_start_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_weight_broadcast_3_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.real_start & (trans_in_cnt_2 == trans_out_cnt_2) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_weight_broadcast_3_U0_U.if_read);
    assign proc_0_TLF_FIFO_blk[3] = 1'b0;
    assign proc_0_input_sync_blk[3] = 1'b0;
    assign proc_0_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_0[3] = dl_detect_out ? proc_dep_vld_vec_0_reg[3] : (proc_0_data_FIFO_blk[3] | proc_0_data_PIPO_blk[3] | proc_0_start_FIFO_blk[3] | proc_0_TLF_FIFO_blk[3] | proc_0_input_sync_blk[3] | proc_0_output_sync_blk[3]);
    assign proc_0_data_FIFO_blk[4] = 1'b0;
    assign proc_0_data_PIPO_blk[4] = 1'b0;
    assign proc_0_start_FIFO_blk[4] = 1'b0;
    assign proc_0_TLF_FIFO_blk[4] = 1'b0;
    assign proc_0_input_sync_blk[4] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready);
    assign proc_0_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_0[4] = dl_detect_out ? proc_dep_vld_vec_0_reg[4] : (proc_0_data_FIFO_blk[4] | proc_0_data_PIPO_blk[4] | proc_0_start_FIFO_blk[4] | proc_0_TLF_FIFO_blk[4] | proc_0_input_sync_blk[4] | proc_0_output_sync_blk[4]);
    assign proc_0_data_FIFO_blk[5] = 1'b0;
    assign proc_0_data_PIPO_blk[5] = 1'b0;
    assign proc_0_start_FIFO_blk[5] = 1'b0;
    assign proc_0_TLF_FIFO_blk[5] = 1'b0;
    assign proc_0_input_sync_blk[5] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready);
    assign proc_0_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_0[5] = dl_detect_out ? proc_dep_vld_vec_0_reg[5] : (proc_0_data_FIFO_blk[5] | proc_0_data_PIPO_blk[5] | proc_0_start_FIFO_blk[5] | proc_0_TLF_FIFO_blk[5] | proc_0_input_sync_blk[5] | proc_0_output_sync_blk[5]);
    assign proc_0_data_FIFO_blk[6] = 1'b0;
    assign proc_0_data_PIPO_blk[6] = 1'b0;
    assign proc_0_start_FIFO_blk[6] = 1'b0;
    assign proc_0_TLF_FIFO_blk[6] = 1'b0;
    assign proc_0_input_sync_blk[6] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready);
    assign proc_0_output_sync_blk[6] = 1'b0;
    assign proc_dep_vld_vec_0[6] = dl_detect_out ? proc_dep_vld_vec_0_reg[6] : (proc_0_data_FIFO_blk[6] | proc_0_data_PIPO_blk[6] | proc_0_start_FIFO_blk[6] | proc_0_TLF_FIFO_blk[6] | proc_0_input_sync_blk[6] | proc_0_output_sync_blk[6]);
    assign proc_0_data_FIFO_blk[7] = 1'b0;
    assign proc_0_data_PIPO_blk[7] = 1'b0;
    assign proc_0_start_FIFO_blk[7] = 1'b0;
    assign proc_0_TLF_FIFO_blk[7] = 1'b0;
    assign proc_0_input_sync_blk[7] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready);
    assign proc_0_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_0[7] = dl_detect_out ? proc_dep_vld_vec_0_reg[7] : (proc_0_data_FIFO_blk[7] | proc_0_data_PIPO_blk[7] | proc_0_start_FIFO_blk[7] | proc_0_TLF_FIFO_blk[7] | proc_0_input_sync_blk[7] | proc_0_output_sync_blk[7]);
    assign proc_0_data_FIFO_blk[8] = 1'b0;
    assign proc_0_data_PIPO_blk[8] = 1'b0;
    assign proc_0_start_FIFO_blk[8] = 1'b0;
    assign proc_0_TLF_FIFO_blk[8] = 1'b0;
    assign proc_0_input_sync_blk[8] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready);
    assign proc_0_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_0[8] = dl_detect_out ? proc_dep_vld_vec_0_reg[8] : (proc_0_data_FIFO_blk[8] | proc_0_data_PIPO_blk[8] | proc_0_start_FIFO_blk[8] | proc_0_TLF_FIFO_blk[8] | proc_0_input_sync_blk[8] | proc_0_output_sync_blk[8]);
    assign proc_0_data_FIFO_blk[9] = 1'b0;
    assign proc_0_data_PIPO_blk[9] = 1'b0;
    assign proc_0_start_FIFO_blk[9] = 1'b0;
    assign proc_0_TLF_FIFO_blk[9] = 1'b0;
    assign proc_0_input_sync_blk[9] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready);
    assign proc_0_output_sync_blk[9] = 1'b0;
    assign proc_dep_vld_vec_0[9] = dl_detect_out ? proc_dep_vld_vec_0_reg[9] : (proc_0_data_FIFO_blk[9] | proc_0_data_PIPO_blk[9] | proc_0_start_FIFO_blk[9] | proc_0_TLF_FIFO_blk[9] | proc_0_input_sync_blk[9] | proc_0_output_sync_blk[9]);
    assign proc_0_data_FIFO_blk[10] = 1'b0;
    assign proc_0_data_PIPO_blk[10] = 1'b0;
    assign proc_0_start_FIFO_blk[10] = 1'b0;
    assign proc_0_TLF_FIFO_blk[10] = 1'b0;
    assign proc_0_input_sync_blk[10] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_4_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready);
    assign proc_0_output_sync_blk[10] = 1'b0;
    assign proc_dep_vld_vec_0[10] = dl_detect_out ? proc_dep_vld_vec_0_reg[10] : (proc_0_data_FIFO_blk[10] | proc_0_data_PIPO_blk[10] | proc_0_start_FIFO_blk[10] | proc_0_TLF_FIFO_blk[10] | proc_0_input_sync_blk[10] | proc_0_output_sync_blk[10]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_0_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_0_reg <= proc_dep_vld_vec_0;
        end
    end
    assign in_chan_dep_vld_vec_0[0] = dep_chan_vld_1_0;
    assign in_chan_dep_data_vec_0[38 : 0] = dep_chan_data_1_0;
    assign token_in_vec_0[0] = token_1_0;
    assign in_chan_dep_vld_vec_0[1] = dep_chan_vld_2_0;
    assign in_chan_dep_data_vec_0[77 : 39] = dep_chan_data_2_0;
    assign token_in_vec_0[1] = token_2_0;
    assign in_chan_dep_vld_vec_0[2] = dep_chan_vld_3_0;
    assign in_chan_dep_data_vec_0[116 : 78] = dep_chan_data_3_0;
    assign token_in_vec_0[2] = token_3_0;
    assign in_chan_dep_vld_vec_0[3] = dep_chan_vld_4_0;
    assign in_chan_dep_data_vec_0[155 : 117] = dep_chan_data_4_0;
    assign token_in_vec_0[3] = token_4_0;
    assign in_chan_dep_vld_vec_0[4] = dep_chan_vld_5_0;
    assign in_chan_dep_data_vec_0[194 : 156] = dep_chan_data_5_0;
    assign token_in_vec_0[4] = token_5_0;
    assign in_chan_dep_vld_vec_0[5] = dep_chan_vld_6_0;
    assign in_chan_dep_data_vec_0[233 : 195] = dep_chan_data_6_0;
    assign token_in_vec_0[5] = token_6_0;
    assign in_chan_dep_vld_vec_0[6] = dep_chan_vld_7_0;
    assign in_chan_dep_data_vec_0[272 : 234] = dep_chan_data_7_0;
    assign token_in_vec_0[6] = token_7_0;
    assign in_chan_dep_vld_vec_0[7] = dep_chan_vld_10_0;
    assign in_chan_dep_data_vec_0[311 : 273] = dep_chan_data_10_0;
    assign token_in_vec_0[7] = token_10_0;
    assign in_chan_dep_vld_vec_0[8] = dep_chan_vld_15_0;
    assign in_chan_dep_data_vec_0[350 : 312] = dep_chan_data_15_0;
    assign token_in_vec_0[8] = token_15_0;
    assign in_chan_dep_vld_vec_0[9] = dep_chan_vld_22_0;
    assign in_chan_dep_data_vec_0[389 : 351] = dep_chan_data_22_0;
    assign token_in_vec_0[9] = token_22_0;
    assign in_chan_dep_vld_vec_0[10] = dep_chan_vld_23_0;
    assign in_chan_dep_data_vec_0[428 : 390] = dep_chan_data_23_0;
    assign token_in_vec_0[10] = token_23_0;
    assign dep_chan_vld_0_10 = out_chan_dep_vld_vec_0[0];
    assign dep_chan_data_0_10 = out_chan_dep_data_0;
    assign token_0_10 = token_out_vec_0[0];
    assign dep_chan_vld_0_15 = out_chan_dep_vld_vec_0[1];
    assign dep_chan_data_0_15 = out_chan_dep_data_0;
    assign token_0_15 = token_out_vec_0[1];
    assign dep_chan_vld_0_23 = out_chan_dep_vld_vec_0[2];
    assign dep_chan_data_0_23 = out_chan_dep_data_0;
    assign token_0_23 = token_out_vec_0[2];
    assign dep_chan_vld_0_22 = out_chan_dep_vld_vec_0[3];
    assign dep_chan_data_0_22 = out_chan_dep_data_0;
    assign token_0_22 = token_out_vec_0[3];
    assign dep_chan_vld_0_1 = out_chan_dep_vld_vec_0[4];
    assign dep_chan_data_0_1 = out_chan_dep_data_0;
    assign token_0_1 = token_out_vec_0[4];
    assign dep_chan_vld_0_2 = out_chan_dep_vld_vec_0[5];
    assign dep_chan_data_0_2 = out_chan_dep_data_0;
    assign token_0_2 = token_out_vec_0[5];
    assign dep_chan_vld_0_3 = out_chan_dep_vld_vec_0[6];
    assign dep_chan_data_0_3 = out_chan_dep_data_0;
    assign token_0_3 = token_out_vec_0[6];
    assign dep_chan_vld_0_4 = out_chan_dep_vld_vec_0[7];
    assign dep_chan_data_0_4 = out_chan_dep_data_0;
    assign token_0_4 = token_out_vec_0[7];
    assign dep_chan_vld_0_5 = out_chan_dep_vld_vec_0[8];
    assign dep_chan_data_0_5 = out_chan_dep_data_0;
    assign token_0_5 = token_out_vec_0[8];
    assign dep_chan_vld_0_6 = out_chan_dep_vld_vec_0[9];
    assign dep_chan_data_0_6 = out_chan_dep_data_0;
    assign token_0_6 = token_out_vec_0[9];
    assign dep_chan_vld_0_7 = out_chan_dep_vld_vec_0[10];
    assign dep_chan_data_0_7 = out_chan_dep_data_0;
    assign token_0_7 = token_out_vec_0[10];

    // Process: grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 1, 9, 9) cnn_pipeline_v10_hls_deadlock_detect_unit_1 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_1),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_1),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_1),
        .token_in_vec(token_in_vec_1),
        .dl_detect_in(dl_detect_out),
        .origin(origin[1]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_1),
        .out_chan_dep_data(out_chan_dep_data_1),
        .token_out_vec(token_out_vec_1),
        .dl_detect_out(dl_in_vec[1]));

    assign proc_1_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.grp_param_broker_2_Pipeline_read_parameter_burst_fu_297.p2_data_0_blk_n);
    assign proc_1_data_PIPO_blk[0] = 1'b0;
    assign proc_1_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_pointwise2_chain_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.real_start & (trans_in_cnt_11 == trans_out_cnt_11) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_pointwise2_chain_U0_U.if_read);
    assign proc_1_TLF_FIFO_blk[0] = 1'b0;
    assign proc_1_input_sync_blk[0] = 1'b0;
    assign proc_1_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_1[0] = dl_detect_out ? proc_dep_vld_vec_1_reg[0] : (proc_1_data_FIFO_blk[0] | proc_1_data_PIPO_blk[0] | proc_1_start_FIFO_blk[0] | proc_1_TLF_FIFO_blk[0] | proc_1_input_sync_blk[0] | proc_1_output_sync_blk[0]);
    assign proc_1_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.grp_param_broker_2_Pipeline_read_parameter_burst_fu_297.p2_data_1_blk_n);
    assign proc_1_data_PIPO_blk[1] = 1'b0;
    assign proc_1_start_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_weight_broadcast_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.real_start & (trans_in_cnt_11 == trans_out_cnt_11) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_weight_broadcast_U0_U.if_read);
    assign proc_1_TLF_FIFO_blk[1] = 1'b0;
    assign proc_1_input_sync_blk[1] = 1'b0;
    assign proc_1_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_1[1] = dl_detect_out ? proc_dep_vld_vec_1_reg[1] : (proc_1_data_FIFO_blk[1] | proc_1_data_PIPO_blk[1] | proc_1_start_FIFO_blk[1] | proc_1_TLF_FIFO_blk[1] | proc_1_input_sync_blk[1] | proc_1_output_sync_blk[1]);
    assign proc_1_data_FIFO_blk[2] = 1'b0;
    assign proc_1_data_PIPO_blk[2] = 1'b0;
    assign proc_1_start_FIFO_blk[2] = 1'b0;
    assign proc_1_TLF_FIFO_blk[2] = 1'b0;
    assign proc_1_input_sync_blk[2] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready);
    assign proc_1_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_1[2] = dl_detect_out ? proc_dep_vld_vec_1_reg[2] : (proc_1_data_FIFO_blk[2] | proc_1_data_PIPO_blk[2] | proc_1_start_FIFO_blk[2] | proc_1_TLF_FIFO_blk[2] | proc_1_input_sync_blk[2] | proc_1_output_sync_blk[2]);
    assign proc_1_data_FIFO_blk[3] = 1'b0;
    assign proc_1_data_PIPO_blk[3] = 1'b0;
    assign proc_1_start_FIFO_blk[3] = 1'b0;
    assign proc_1_TLF_FIFO_blk[3] = 1'b0;
    assign proc_1_input_sync_blk[3] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready);
    assign proc_1_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_1[3] = dl_detect_out ? proc_dep_vld_vec_1_reg[3] : (proc_1_data_FIFO_blk[3] | proc_1_data_PIPO_blk[3] | proc_1_start_FIFO_blk[3] | proc_1_TLF_FIFO_blk[3] | proc_1_input_sync_blk[3] | proc_1_output_sync_blk[3]);
    assign proc_1_data_FIFO_blk[4] = 1'b0;
    assign proc_1_data_PIPO_blk[4] = 1'b0;
    assign proc_1_start_FIFO_blk[4] = 1'b0;
    assign proc_1_TLF_FIFO_blk[4] = 1'b0;
    assign proc_1_input_sync_blk[4] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready);
    assign proc_1_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_1[4] = dl_detect_out ? proc_dep_vld_vec_1_reg[4] : (proc_1_data_FIFO_blk[4] | proc_1_data_PIPO_blk[4] | proc_1_start_FIFO_blk[4] | proc_1_TLF_FIFO_blk[4] | proc_1_input_sync_blk[4] | proc_1_output_sync_blk[4]);
    assign proc_1_data_FIFO_blk[5] = 1'b0;
    assign proc_1_data_PIPO_blk[5] = 1'b0;
    assign proc_1_start_FIFO_blk[5] = 1'b0;
    assign proc_1_TLF_FIFO_blk[5] = 1'b0;
    assign proc_1_input_sync_blk[5] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready);
    assign proc_1_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_1[5] = dl_detect_out ? proc_dep_vld_vec_1_reg[5] : (proc_1_data_FIFO_blk[5] | proc_1_data_PIPO_blk[5] | proc_1_start_FIFO_blk[5] | proc_1_TLF_FIFO_blk[5] | proc_1_input_sync_blk[5] | proc_1_output_sync_blk[5]);
    assign proc_1_data_FIFO_blk[6] = 1'b0;
    assign proc_1_data_PIPO_blk[6] = 1'b0;
    assign proc_1_start_FIFO_blk[6] = 1'b0;
    assign proc_1_TLF_FIFO_blk[6] = 1'b0;
    assign proc_1_input_sync_blk[6] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready);
    assign proc_1_output_sync_blk[6] = 1'b0;
    assign proc_dep_vld_vec_1[6] = dl_detect_out ? proc_dep_vld_vec_1_reg[6] : (proc_1_data_FIFO_blk[6] | proc_1_data_PIPO_blk[6] | proc_1_start_FIFO_blk[6] | proc_1_TLF_FIFO_blk[6] | proc_1_input_sync_blk[6] | proc_1_output_sync_blk[6]);
    assign proc_1_data_FIFO_blk[7] = 1'b0;
    assign proc_1_data_PIPO_blk[7] = 1'b0;
    assign proc_1_start_FIFO_blk[7] = 1'b0;
    assign proc_1_TLF_FIFO_blk[7] = 1'b0;
    assign proc_1_input_sync_blk[7] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready);
    assign proc_1_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_1[7] = dl_detect_out ? proc_dep_vld_vec_1_reg[7] : (proc_1_data_FIFO_blk[7] | proc_1_data_PIPO_blk[7] | proc_1_start_FIFO_blk[7] | proc_1_TLF_FIFO_blk[7] | proc_1_input_sync_blk[7] | proc_1_output_sync_blk[7]);
    assign proc_1_data_FIFO_blk[8] = 1'b0;
    assign proc_1_data_PIPO_blk[8] = 1'b0;
    assign proc_1_start_FIFO_blk[8] = 1'b0;
    assign proc_1_TLF_FIFO_blk[8] = 1'b0;
    assign proc_1_input_sync_blk[8] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready);
    assign proc_1_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_1[8] = dl_detect_out ? proc_dep_vld_vec_1_reg[8] : (proc_1_data_FIFO_blk[8] | proc_1_data_PIPO_blk[8] | proc_1_start_FIFO_blk[8] | proc_1_TLF_FIFO_blk[8] | proc_1_input_sync_blk[8] | proc_1_output_sync_blk[8]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_1_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_1_reg <= proc_dep_vld_vec_1;
        end
    end
    assign in_chan_dep_vld_vec_1[0] = dep_chan_vld_0_1;
    assign in_chan_dep_data_vec_1[38 : 0] = dep_chan_data_0_1;
    assign token_in_vec_1[0] = token_0_1;
    assign in_chan_dep_vld_vec_1[1] = dep_chan_vld_2_1;
    assign in_chan_dep_data_vec_1[77 : 39] = dep_chan_data_2_1;
    assign token_in_vec_1[1] = token_2_1;
    assign in_chan_dep_vld_vec_1[2] = dep_chan_vld_3_1;
    assign in_chan_dep_data_vec_1[116 : 78] = dep_chan_data_3_1;
    assign token_in_vec_1[2] = token_3_1;
    assign in_chan_dep_vld_vec_1[3] = dep_chan_vld_4_1;
    assign in_chan_dep_data_vec_1[155 : 117] = dep_chan_data_4_1;
    assign token_in_vec_1[3] = token_4_1;
    assign in_chan_dep_vld_vec_1[4] = dep_chan_vld_5_1;
    assign in_chan_dep_data_vec_1[194 : 156] = dep_chan_data_5_1;
    assign token_in_vec_1[4] = token_5_1;
    assign in_chan_dep_vld_vec_1[5] = dep_chan_vld_6_1;
    assign in_chan_dep_data_vec_1[233 : 195] = dep_chan_data_6_1;
    assign token_in_vec_1[5] = token_6_1;
    assign in_chan_dep_vld_vec_1[6] = dep_chan_vld_7_1;
    assign in_chan_dep_data_vec_1[272 : 234] = dep_chan_data_7_1;
    assign token_in_vec_1[6] = token_7_1;
    assign in_chan_dep_vld_vec_1[7] = dep_chan_vld_30_1;
    assign in_chan_dep_data_vec_1[311 : 273] = dep_chan_data_30_1;
    assign token_in_vec_1[7] = token_30_1;
    assign in_chan_dep_vld_vec_1[8] = dep_chan_vld_31_1;
    assign in_chan_dep_data_vec_1[350 : 312] = dep_chan_data_31_1;
    assign token_in_vec_1[8] = token_31_1;
    assign dep_chan_vld_1_31 = out_chan_dep_vld_vec_1[0];
    assign dep_chan_data_1_31 = out_chan_dep_data_1;
    assign token_1_31 = token_out_vec_1[0];
    assign dep_chan_vld_1_30 = out_chan_dep_vld_vec_1[1];
    assign dep_chan_data_1_30 = out_chan_dep_data_1;
    assign token_1_30 = token_out_vec_1[1];
    assign dep_chan_vld_1_0 = out_chan_dep_vld_vec_1[2];
    assign dep_chan_data_1_0 = out_chan_dep_data_1;
    assign token_1_0 = token_out_vec_1[2];
    assign dep_chan_vld_1_2 = out_chan_dep_vld_vec_1[3];
    assign dep_chan_data_1_2 = out_chan_dep_data_1;
    assign token_1_2 = token_out_vec_1[3];
    assign dep_chan_vld_1_3 = out_chan_dep_vld_vec_1[4];
    assign dep_chan_data_1_3 = out_chan_dep_data_1;
    assign token_1_3 = token_out_vec_1[4];
    assign dep_chan_vld_1_4 = out_chan_dep_vld_vec_1[5];
    assign dep_chan_data_1_4 = out_chan_dep_data_1;
    assign token_1_4 = token_out_vec_1[5];
    assign dep_chan_vld_1_5 = out_chan_dep_vld_vec_1[6];
    assign dep_chan_data_1_5 = out_chan_dep_data_1;
    assign token_1_5 = token_out_vec_1[6];
    assign dep_chan_vld_1_6 = out_chan_dep_vld_vec_1[7];
    assign dep_chan_data_1_6 = out_chan_dep_data_1;
    assign token_1_6 = token_out_vec_1[7];
    assign dep_chan_vld_1_7 = out_chan_dep_vld_vec_1[8];
    assign dep_chan_data_1_7 = out_chan_dep_data_1;
    assign token_1_7 = token_out_vec_1[8];

    // Process: grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 2, 9, 9) cnn_pipeline_v10_hls_deadlock_detect_unit_2 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_2),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_2),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_2),
        .token_in_vec(token_in_vec_2),
        .dl_detect_in(dl_detect_out),
        .origin(origin[2]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_2),
        .out_chan_dep_data(out_chan_dep_data_2),
        .token_out_vec(token_out_vec_2),
        .dl_detect_out(dl_in_vec[2]));

    assign proc_2_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.grp_param_broker_2_6_Pipeline_read_parameter_burst_fu_297.a_read_data_0_blk_n);
    assign proc_2_data_PIPO_blk[0] = 1'b0;
    assign proc_2_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_feed_chain_1_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.real_start & (trans_in_cnt_0 == trans_out_cnt_0) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_feed_chain_1_U0_U.if_read);
    assign proc_2_TLF_FIFO_blk[0] = 1'b0;
    assign proc_2_input_sync_blk[0] = 1'b0;
    assign proc_2_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_2[0] = dl_detect_out ? proc_dep_vld_vec_2_reg[0] : (proc_2_data_FIFO_blk[0] | proc_2_data_PIPO_blk[0] | proc_2_start_FIFO_blk[0] | proc_2_TLF_FIFO_blk[0] | proc_2_input_sync_blk[0] | proc_2_output_sync_blk[0]);
    assign proc_2_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.grp_param_broker_2_6_Pipeline_read_parameter_burst_fu_297.a_read_data_1_blk_n);
    assign proc_2_data_PIPO_blk[1] = 1'b0;
    assign proc_2_start_FIFO_blk[1] = 1'b0;
    assign proc_2_TLF_FIFO_blk[1] = 1'b0;
    assign proc_2_input_sync_blk[1] = 1'b0;
    assign proc_2_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_2[1] = dl_detect_out ? proc_dep_vld_vec_2_reg[1] : (proc_2_data_FIFO_blk[1] | proc_2_data_PIPO_blk[1] | proc_2_start_FIFO_blk[1] | proc_2_TLF_FIFO_blk[1] | proc_2_input_sync_blk[1] | proc_2_output_sync_blk[1]);
    assign proc_2_data_FIFO_blk[2] = 1'b0;
    assign proc_2_data_PIPO_blk[2] = 1'b0;
    assign proc_2_start_FIFO_blk[2] = 1'b0;
    assign proc_2_TLF_FIFO_blk[2] = 1'b0;
    assign proc_2_input_sync_blk[2] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready);
    assign proc_2_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_2[2] = dl_detect_out ? proc_dep_vld_vec_2_reg[2] : (proc_2_data_FIFO_blk[2] | proc_2_data_PIPO_blk[2] | proc_2_start_FIFO_blk[2] | proc_2_TLF_FIFO_blk[2] | proc_2_input_sync_blk[2] | proc_2_output_sync_blk[2]);
    assign proc_2_data_FIFO_blk[3] = 1'b0;
    assign proc_2_data_PIPO_blk[3] = 1'b0;
    assign proc_2_start_FIFO_blk[3] = 1'b0;
    assign proc_2_TLF_FIFO_blk[3] = 1'b0;
    assign proc_2_input_sync_blk[3] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready);
    assign proc_2_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_2[3] = dl_detect_out ? proc_dep_vld_vec_2_reg[3] : (proc_2_data_FIFO_blk[3] | proc_2_data_PIPO_blk[3] | proc_2_start_FIFO_blk[3] | proc_2_TLF_FIFO_blk[3] | proc_2_input_sync_blk[3] | proc_2_output_sync_blk[3]);
    assign proc_2_data_FIFO_blk[4] = 1'b0;
    assign proc_2_data_PIPO_blk[4] = 1'b0;
    assign proc_2_start_FIFO_blk[4] = 1'b0;
    assign proc_2_TLF_FIFO_blk[4] = 1'b0;
    assign proc_2_input_sync_blk[4] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready);
    assign proc_2_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_2[4] = dl_detect_out ? proc_dep_vld_vec_2_reg[4] : (proc_2_data_FIFO_blk[4] | proc_2_data_PIPO_blk[4] | proc_2_start_FIFO_blk[4] | proc_2_TLF_FIFO_blk[4] | proc_2_input_sync_blk[4] | proc_2_output_sync_blk[4]);
    assign proc_2_data_FIFO_blk[5] = 1'b0;
    assign proc_2_data_PIPO_blk[5] = 1'b0;
    assign proc_2_start_FIFO_blk[5] = 1'b0;
    assign proc_2_TLF_FIFO_blk[5] = 1'b0;
    assign proc_2_input_sync_blk[5] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready);
    assign proc_2_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_2[5] = dl_detect_out ? proc_dep_vld_vec_2_reg[5] : (proc_2_data_FIFO_blk[5] | proc_2_data_PIPO_blk[5] | proc_2_start_FIFO_blk[5] | proc_2_TLF_FIFO_blk[5] | proc_2_input_sync_blk[5] | proc_2_output_sync_blk[5]);
    assign proc_2_data_FIFO_blk[6] = 1'b0;
    assign proc_2_data_PIPO_blk[6] = 1'b0;
    assign proc_2_start_FIFO_blk[6] = 1'b0;
    assign proc_2_TLF_FIFO_blk[6] = 1'b0;
    assign proc_2_input_sync_blk[6] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready);
    assign proc_2_output_sync_blk[6] = 1'b0;
    assign proc_dep_vld_vec_2[6] = dl_detect_out ? proc_dep_vld_vec_2_reg[6] : (proc_2_data_FIFO_blk[6] | proc_2_data_PIPO_blk[6] | proc_2_start_FIFO_blk[6] | proc_2_TLF_FIFO_blk[6] | proc_2_input_sync_blk[6] | proc_2_output_sync_blk[6]);
    assign proc_2_data_FIFO_blk[7] = 1'b0;
    assign proc_2_data_PIPO_blk[7] = 1'b0;
    assign proc_2_start_FIFO_blk[7] = 1'b0;
    assign proc_2_TLF_FIFO_blk[7] = 1'b0;
    assign proc_2_input_sync_blk[7] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready);
    assign proc_2_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_2[7] = dl_detect_out ? proc_dep_vld_vec_2_reg[7] : (proc_2_data_FIFO_blk[7] | proc_2_data_PIPO_blk[7] | proc_2_start_FIFO_blk[7] | proc_2_TLF_FIFO_blk[7] | proc_2_input_sync_blk[7] | proc_2_output_sync_blk[7]);
    assign proc_2_data_FIFO_blk[8] = 1'b0;
    assign proc_2_data_PIPO_blk[8] = 1'b0;
    assign proc_2_start_FIFO_blk[8] = 1'b0;
    assign proc_2_TLF_FIFO_blk[8] = 1'b0;
    assign proc_2_input_sync_blk[8] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_6_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready);
    assign proc_2_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_2[8] = dl_detect_out ? proc_dep_vld_vec_2_reg[8] : (proc_2_data_FIFO_blk[8] | proc_2_data_PIPO_blk[8] | proc_2_start_FIFO_blk[8] | proc_2_TLF_FIFO_blk[8] | proc_2_input_sync_blk[8] | proc_2_output_sync_blk[8]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_2_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_2_reg <= proc_dep_vld_vec_2;
        end
    end
    assign in_chan_dep_vld_vec_2[0] = dep_chan_vld_0_2;
    assign in_chan_dep_data_vec_2[38 : 0] = dep_chan_data_0_2;
    assign token_in_vec_2[0] = token_0_2;
    assign in_chan_dep_vld_vec_2[1] = dep_chan_vld_1_2;
    assign in_chan_dep_data_vec_2[77 : 39] = dep_chan_data_1_2;
    assign token_in_vec_2[1] = token_1_2;
    assign in_chan_dep_vld_vec_2[2] = dep_chan_vld_3_2;
    assign in_chan_dep_data_vec_2[116 : 78] = dep_chan_data_3_2;
    assign token_in_vec_2[2] = token_3_2;
    assign in_chan_dep_vld_vec_2[3] = dep_chan_vld_4_2;
    assign in_chan_dep_data_vec_2[155 : 117] = dep_chan_data_4_2;
    assign token_in_vec_2[3] = token_4_2;
    assign in_chan_dep_vld_vec_2[4] = dep_chan_vld_5_2;
    assign in_chan_dep_data_vec_2[194 : 156] = dep_chan_data_5_2;
    assign token_in_vec_2[4] = token_5_2;
    assign in_chan_dep_vld_vec_2[5] = dep_chan_vld_6_2;
    assign in_chan_dep_data_vec_2[233 : 195] = dep_chan_data_6_2;
    assign token_in_vec_2[5] = token_6_2;
    assign in_chan_dep_vld_vec_2[6] = dep_chan_vld_7_2;
    assign in_chan_dep_data_vec_2[272 : 234] = dep_chan_data_7_2;
    assign token_in_vec_2[6] = token_7_2;
    assign in_chan_dep_vld_vec_2[7] = dep_chan_vld_8_2;
    assign in_chan_dep_data_vec_2[311 : 273] = dep_chan_data_8_2;
    assign token_in_vec_2[7] = token_8_2;
    assign in_chan_dep_vld_vec_2[8] = dep_chan_vld_31_2;
    assign in_chan_dep_data_vec_2[350 : 312] = dep_chan_data_31_2;
    assign token_in_vec_2[8] = token_31_2;
    assign dep_chan_vld_2_8 = out_chan_dep_vld_vec_2[0];
    assign dep_chan_data_2_8 = out_chan_dep_data_2;
    assign token_2_8 = token_out_vec_2[0];
    assign dep_chan_vld_2_31 = out_chan_dep_vld_vec_2[1];
    assign dep_chan_data_2_31 = out_chan_dep_data_2;
    assign token_2_31 = token_out_vec_2[1];
    assign dep_chan_vld_2_0 = out_chan_dep_vld_vec_2[2];
    assign dep_chan_data_2_0 = out_chan_dep_data_2;
    assign token_2_0 = token_out_vec_2[2];
    assign dep_chan_vld_2_1 = out_chan_dep_vld_vec_2[3];
    assign dep_chan_data_2_1 = out_chan_dep_data_2;
    assign token_2_1 = token_out_vec_2[3];
    assign dep_chan_vld_2_3 = out_chan_dep_vld_vec_2[4];
    assign dep_chan_data_2_3 = out_chan_dep_data_2;
    assign token_2_3 = token_out_vec_2[4];
    assign dep_chan_vld_2_4 = out_chan_dep_vld_vec_2[5];
    assign dep_chan_data_2_4 = out_chan_dep_data_2;
    assign token_2_4 = token_out_vec_2[5];
    assign dep_chan_vld_2_5 = out_chan_dep_vld_vec_2[6];
    assign dep_chan_data_2_5 = out_chan_dep_data_2;
    assign token_2_5 = token_out_vec_2[6];
    assign dep_chan_vld_2_6 = out_chan_dep_vld_vec_2[7];
    assign dep_chan_data_2_6 = out_chan_dep_data_2;
    assign token_2_6 = token_out_vec_2[7];
    assign dep_chan_vld_2_7 = out_chan_dep_vld_vec_2[8];
    assign dep_chan_data_2_7 = out_chan_dep_data_2;
    assign token_2_7 = token_out_vec_2[8];

    // Process: grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 3, 9, 9) cnn_pipeline_v10_hls_deadlock_detect_unit_3 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_3),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_3),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_3),
        .token_in_vec(token_in_vec_3),
        .dl_detect_in(dl_detect_out),
        .origin(origin[3]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_3),
        .out_chan_dep_data(out_chan_dep_data_3),
        .token_out_vec(token_out_vec_3),
        .dl_detect_out(dl_in_vec[3]));

    assign proc_3_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.grp_param_broker_2_7_Pipeline_read_parameter_burst_fu_297.b_read_data_0_blk_n);
    assign proc_3_data_PIPO_blk[0] = 1'b0;
    assign proc_3_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_feed_chain_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.real_start & (trans_in_cnt_1 == trans_out_cnt_1) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_feed_chain_U0_U.if_read);
    assign proc_3_TLF_FIFO_blk[0] = 1'b0;
    assign proc_3_input_sync_blk[0] = 1'b0;
    assign proc_3_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_3[0] = dl_detect_out ? proc_dep_vld_vec_3_reg[0] : (proc_3_data_FIFO_blk[0] | proc_3_data_PIPO_blk[0] | proc_3_start_FIFO_blk[0] | proc_3_TLF_FIFO_blk[0] | proc_3_input_sync_blk[0] | proc_3_output_sync_blk[0]);
    assign proc_3_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.grp_param_broker_2_7_Pipeline_read_parameter_burst_fu_297.b_read_data_1_blk_n);
    assign proc_3_data_PIPO_blk[1] = 1'b0;
    assign proc_3_start_FIFO_blk[1] = 1'b0;
    assign proc_3_TLF_FIFO_blk[1] = 1'b0;
    assign proc_3_input_sync_blk[1] = 1'b0;
    assign proc_3_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_3[1] = dl_detect_out ? proc_dep_vld_vec_3_reg[1] : (proc_3_data_FIFO_blk[1] | proc_3_data_PIPO_blk[1] | proc_3_start_FIFO_blk[1] | proc_3_TLF_FIFO_blk[1] | proc_3_input_sync_blk[1] | proc_3_output_sync_blk[1]);
    assign proc_3_data_FIFO_blk[2] = 1'b0;
    assign proc_3_data_PIPO_blk[2] = 1'b0;
    assign proc_3_start_FIFO_blk[2] = 1'b0;
    assign proc_3_TLF_FIFO_blk[2] = 1'b0;
    assign proc_3_input_sync_blk[2] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready);
    assign proc_3_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_3[2] = dl_detect_out ? proc_dep_vld_vec_3_reg[2] : (proc_3_data_FIFO_blk[2] | proc_3_data_PIPO_blk[2] | proc_3_start_FIFO_blk[2] | proc_3_TLF_FIFO_blk[2] | proc_3_input_sync_blk[2] | proc_3_output_sync_blk[2]);
    assign proc_3_data_FIFO_blk[3] = 1'b0;
    assign proc_3_data_PIPO_blk[3] = 1'b0;
    assign proc_3_start_FIFO_blk[3] = 1'b0;
    assign proc_3_TLF_FIFO_blk[3] = 1'b0;
    assign proc_3_input_sync_blk[3] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready);
    assign proc_3_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_3[3] = dl_detect_out ? proc_dep_vld_vec_3_reg[3] : (proc_3_data_FIFO_blk[3] | proc_3_data_PIPO_blk[3] | proc_3_start_FIFO_blk[3] | proc_3_TLF_FIFO_blk[3] | proc_3_input_sync_blk[3] | proc_3_output_sync_blk[3]);
    assign proc_3_data_FIFO_blk[4] = 1'b0;
    assign proc_3_data_PIPO_blk[4] = 1'b0;
    assign proc_3_start_FIFO_blk[4] = 1'b0;
    assign proc_3_TLF_FIFO_blk[4] = 1'b0;
    assign proc_3_input_sync_blk[4] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready);
    assign proc_3_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_3[4] = dl_detect_out ? proc_dep_vld_vec_3_reg[4] : (proc_3_data_FIFO_blk[4] | proc_3_data_PIPO_blk[4] | proc_3_start_FIFO_blk[4] | proc_3_TLF_FIFO_blk[4] | proc_3_input_sync_blk[4] | proc_3_output_sync_blk[4]);
    assign proc_3_data_FIFO_blk[5] = 1'b0;
    assign proc_3_data_PIPO_blk[5] = 1'b0;
    assign proc_3_start_FIFO_blk[5] = 1'b0;
    assign proc_3_TLF_FIFO_blk[5] = 1'b0;
    assign proc_3_input_sync_blk[5] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready);
    assign proc_3_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_3[5] = dl_detect_out ? proc_dep_vld_vec_3_reg[5] : (proc_3_data_FIFO_blk[5] | proc_3_data_PIPO_blk[5] | proc_3_start_FIFO_blk[5] | proc_3_TLF_FIFO_blk[5] | proc_3_input_sync_blk[5] | proc_3_output_sync_blk[5]);
    assign proc_3_data_FIFO_blk[6] = 1'b0;
    assign proc_3_data_PIPO_blk[6] = 1'b0;
    assign proc_3_start_FIFO_blk[6] = 1'b0;
    assign proc_3_TLF_FIFO_blk[6] = 1'b0;
    assign proc_3_input_sync_blk[6] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready);
    assign proc_3_output_sync_blk[6] = 1'b0;
    assign proc_dep_vld_vec_3[6] = dl_detect_out ? proc_dep_vld_vec_3_reg[6] : (proc_3_data_FIFO_blk[6] | proc_3_data_PIPO_blk[6] | proc_3_start_FIFO_blk[6] | proc_3_TLF_FIFO_blk[6] | proc_3_input_sync_blk[6] | proc_3_output_sync_blk[6]);
    assign proc_3_data_FIFO_blk[7] = 1'b0;
    assign proc_3_data_PIPO_blk[7] = 1'b0;
    assign proc_3_start_FIFO_blk[7] = 1'b0;
    assign proc_3_TLF_FIFO_blk[7] = 1'b0;
    assign proc_3_input_sync_blk[7] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready);
    assign proc_3_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_3[7] = dl_detect_out ? proc_dep_vld_vec_3_reg[7] : (proc_3_data_FIFO_blk[7] | proc_3_data_PIPO_blk[7] | proc_3_start_FIFO_blk[7] | proc_3_TLF_FIFO_blk[7] | proc_3_input_sync_blk[7] | proc_3_output_sync_blk[7]);
    assign proc_3_data_FIFO_blk[8] = 1'b0;
    assign proc_3_data_PIPO_blk[8] = 1'b0;
    assign proc_3_start_FIFO_blk[8] = 1'b0;
    assign proc_3_TLF_FIFO_blk[8] = 1'b0;
    assign proc_3_input_sync_blk[8] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.param_broker_2_7_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready);
    assign proc_3_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_3[8] = dl_detect_out ? proc_dep_vld_vec_3_reg[8] : (proc_3_data_FIFO_blk[8] | proc_3_data_PIPO_blk[8] | proc_3_start_FIFO_blk[8] | proc_3_TLF_FIFO_blk[8] | proc_3_input_sync_blk[8] | proc_3_output_sync_blk[8]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_3_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_3_reg <= proc_dep_vld_vec_3;
        end
    end
    assign in_chan_dep_vld_vec_3[0] = dep_chan_vld_0_3;
    assign in_chan_dep_data_vec_3[38 : 0] = dep_chan_data_0_3;
    assign token_in_vec_3[0] = token_0_3;
    assign in_chan_dep_vld_vec_3[1] = dep_chan_vld_1_3;
    assign in_chan_dep_data_vec_3[77 : 39] = dep_chan_data_1_3;
    assign token_in_vec_3[1] = token_1_3;
    assign in_chan_dep_vld_vec_3[2] = dep_chan_vld_2_3;
    assign in_chan_dep_data_vec_3[116 : 78] = dep_chan_data_2_3;
    assign token_in_vec_3[2] = token_2_3;
    assign in_chan_dep_vld_vec_3[3] = dep_chan_vld_4_3;
    assign in_chan_dep_data_vec_3[155 : 117] = dep_chan_data_4_3;
    assign token_in_vec_3[3] = token_4_3;
    assign in_chan_dep_vld_vec_3[4] = dep_chan_vld_5_3;
    assign in_chan_dep_data_vec_3[194 : 156] = dep_chan_data_5_3;
    assign token_in_vec_3[4] = token_5_3;
    assign in_chan_dep_vld_vec_3[5] = dep_chan_vld_6_3;
    assign in_chan_dep_data_vec_3[233 : 195] = dep_chan_data_6_3;
    assign token_in_vec_3[5] = token_6_3;
    assign in_chan_dep_vld_vec_3[6] = dep_chan_vld_7_3;
    assign in_chan_dep_data_vec_3[272 : 234] = dep_chan_data_7_3;
    assign token_in_vec_3[6] = token_7_3;
    assign in_chan_dep_vld_vec_3[7] = dep_chan_vld_9_3;
    assign in_chan_dep_data_vec_3[311 : 273] = dep_chan_data_9_3;
    assign token_in_vec_3[7] = token_9_3;
    assign in_chan_dep_vld_vec_3[8] = dep_chan_vld_31_3;
    assign in_chan_dep_data_vec_3[350 : 312] = dep_chan_data_31_3;
    assign token_in_vec_3[8] = token_31_3;
    assign dep_chan_vld_3_9 = out_chan_dep_vld_vec_3[0];
    assign dep_chan_data_3_9 = out_chan_dep_data_3;
    assign token_3_9 = token_out_vec_3[0];
    assign dep_chan_vld_3_31 = out_chan_dep_vld_vec_3[1];
    assign dep_chan_data_3_31 = out_chan_dep_data_3;
    assign token_3_31 = token_out_vec_3[1];
    assign dep_chan_vld_3_0 = out_chan_dep_vld_vec_3[2];
    assign dep_chan_data_3_0 = out_chan_dep_data_3;
    assign token_3_0 = token_out_vec_3[2];
    assign dep_chan_vld_3_1 = out_chan_dep_vld_vec_3[3];
    assign dep_chan_data_3_1 = out_chan_dep_data_3;
    assign token_3_1 = token_out_vec_3[3];
    assign dep_chan_vld_3_2 = out_chan_dep_vld_vec_3[4];
    assign dep_chan_data_3_2 = out_chan_dep_data_3;
    assign token_3_2 = token_out_vec_3[4];
    assign dep_chan_vld_3_4 = out_chan_dep_vld_vec_3[5];
    assign dep_chan_data_3_4 = out_chan_dep_data_3;
    assign token_3_4 = token_out_vec_3[5];
    assign dep_chan_vld_3_5 = out_chan_dep_vld_vec_3[6];
    assign dep_chan_data_3_5 = out_chan_dep_data_3;
    assign token_3_5 = token_out_vec_3[6];
    assign dep_chan_vld_3_6 = out_chan_dep_vld_vec_3[7];
    assign dep_chan_data_3_6 = out_chan_dep_data_3;
    assign token_3_6 = token_out_vec_3[7];
    assign dep_chan_vld_3_7 = out_chan_dep_vld_vec_3[8];
    assign dep_chan_data_3_7 = out_chan_dep_data_3;
    assign token_3_7 = token_out_vec_3[8];

    // Process: grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 4, 16, 16) cnn_pipeline_v10_hls_deadlock_detect_unit_4 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_4),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_4),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_4),
        .token_in_vec(token_in_vec_4),
        .dl_detect_in(dl_detect_out),
        .origin(origin[4]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_4),
        .out_chan_dep_data(out_chan_dep_data_4),
        .token_out_vec(token_out_vec_4),
        .dl_detect_out(dl_in_vec[4]));

    assign proc_4_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.grp_write_broker_2_Pipeline_VITIS_LOOP_148_5_fu_273.a_write_data_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.a_committed_0_blk_n);
    assign proc_4_data_PIPO_blk[0] = 1'b0;
    assign proc_4_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_residual_writer_2_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.real_start & (trans_in_cnt_7 == trans_out_cnt_7) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_residual_writer_2_U0_U.if_read);
    assign proc_4_TLF_FIFO_blk[0] = 1'b0;
    assign proc_4_input_sync_blk[0] = 1'b0;
    assign proc_4_output_sync_blk[0] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_4[0] = dl_detect_out ? proc_dep_vld_vec_4_reg[0] : (proc_4_data_FIFO_blk[0] | proc_4_data_PIPO_blk[0] | proc_4_start_FIFO_blk[0] | proc_4_TLF_FIFO_blk[0] | proc_4_input_sync_blk[0] | proc_4_output_sync_blk[0]);
    assign proc_4_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.grp_write_broker_2_Pipeline_VITIS_LOOP_148_5_fu_273.a_write_data_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.a_committed_1_blk_n);
    assign proc_4_data_PIPO_blk[1] = 1'b0;
    assign proc_4_start_FIFO_blk[1] = 1'b0;
    assign proc_4_TLF_FIFO_blk[1] = 1'b0;
    assign proc_4_input_sync_blk[1] = 1'b0;
    assign proc_4_output_sync_blk[1] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_4[1] = dl_detect_out ? proc_dep_vld_vec_4_reg[1] : (proc_4_data_FIFO_blk[1] | proc_4_data_PIPO_blk[1] | proc_4_start_FIFO_blk[1] | proc_4_TLF_FIFO_blk[1] | proc_4_input_sync_blk[1] | proc_4_output_sync_blk[1]);
    assign proc_4_data_FIFO_blk[2] = 1'b0;
    assign proc_4_data_PIPO_blk[2] = 1'b0;
    assign proc_4_start_FIFO_blk[2] = 1'b0;
    assign proc_4_TLF_FIFO_blk[2] = 1'b0;
    assign proc_4_input_sync_blk[2] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready);
    assign proc_4_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_4[2] = dl_detect_out ? proc_dep_vld_vec_4_reg[2] : (proc_4_data_FIFO_blk[2] | proc_4_data_PIPO_blk[2] | proc_4_start_FIFO_blk[2] | proc_4_TLF_FIFO_blk[2] | proc_4_input_sync_blk[2] | proc_4_output_sync_blk[2]);
    assign proc_4_data_FIFO_blk[3] = 1'b0;
    assign proc_4_data_PIPO_blk[3] = 1'b0;
    assign proc_4_start_FIFO_blk[3] = 1'b0;
    assign proc_4_TLF_FIFO_blk[3] = 1'b0;
    assign proc_4_input_sync_blk[3] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready);
    assign proc_4_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_4[3] = dl_detect_out ? proc_dep_vld_vec_4_reg[3] : (proc_4_data_FIFO_blk[3] | proc_4_data_PIPO_blk[3] | proc_4_start_FIFO_blk[3] | proc_4_TLF_FIFO_blk[3] | proc_4_input_sync_blk[3] | proc_4_output_sync_blk[3]);
    assign proc_4_data_FIFO_blk[4] = 1'b0;
    assign proc_4_data_PIPO_blk[4] = 1'b0;
    assign proc_4_start_FIFO_blk[4] = 1'b0;
    assign proc_4_TLF_FIFO_blk[4] = 1'b0;
    assign proc_4_input_sync_blk[4] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready);
    assign proc_4_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_4[4] = dl_detect_out ? proc_dep_vld_vec_4_reg[4] : (proc_4_data_FIFO_blk[4] | proc_4_data_PIPO_blk[4] | proc_4_start_FIFO_blk[4] | proc_4_TLF_FIFO_blk[4] | proc_4_input_sync_blk[4] | proc_4_output_sync_blk[4]);
    assign proc_4_data_FIFO_blk[5] = 1'b0;
    assign proc_4_data_PIPO_blk[5] = 1'b0;
    assign proc_4_start_FIFO_blk[5] = 1'b0;
    assign proc_4_TLF_FIFO_blk[5] = 1'b0;
    assign proc_4_input_sync_blk[5] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready);
    assign proc_4_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_4[5] = dl_detect_out ? proc_dep_vld_vec_4_reg[5] : (proc_4_data_FIFO_blk[5] | proc_4_data_PIPO_blk[5] | proc_4_start_FIFO_blk[5] | proc_4_TLF_FIFO_blk[5] | proc_4_input_sync_blk[5] | proc_4_output_sync_blk[5]);
    assign proc_4_data_FIFO_blk[6] = 1'b0;
    assign proc_4_data_PIPO_blk[6] = 1'b0;
    assign proc_4_start_FIFO_blk[6] = 1'b0;
    assign proc_4_TLF_FIFO_blk[6] = 1'b0;
    assign proc_4_input_sync_blk[6] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready);
    assign proc_4_output_sync_blk[6] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_4[6] = dl_detect_out ? proc_dep_vld_vec_4_reg[6] : (proc_4_data_FIFO_blk[6] | proc_4_data_PIPO_blk[6] | proc_4_start_FIFO_blk[6] | proc_4_TLF_FIFO_blk[6] | proc_4_input_sync_blk[6] | proc_4_output_sync_blk[6]);
    assign proc_4_data_FIFO_blk[7] = 1'b0;
    assign proc_4_data_PIPO_blk[7] = 1'b0;
    assign proc_4_start_FIFO_blk[7] = 1'b0;
    assign proc_4_TLF_FIFO_blk[7] = 1'b0;
    assign proc_4_input_sync_blk[7] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready);
    assign proc_4_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_4[7] = dl_detect_out ? proc_dep_vld_vec_4_reg[7] : (proc_4_data_FIFO_blk[7] | proc_4_data_PIPO_blk[7] | proc_4_start_FIFO_blk[7] | proc_4_TLF_FIFO_blk[7] | proc_4_input_sync_blk[7] | proc_4_output_sync_blk[7]);
    assign proc_4_data_FIFO_blk[8] = 1'b0;
    assign proc_4_data_PIPO_blk[8] = 1'b0;
    assign proc_4_start_FIFO_blk[8] = 1'b0;
    assign proc_4_TLF_FIFO_blk[8] = 1'b0;
    assign proc_4_input_sync_blk[8] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready);
    assign proc_4_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_4[8] = dl_detect_out ? proc_dep_vld_vec_4_reg[8] : (proc_4_data_FIFO_blk[8] | proc_4_data_PIPO_blk[8] | proc_4_start_FIFO_blk[8] | proc_4_TLF_FIFO_blk[8] | proc_4_input_sync_blk[8] | proc_4_output_sync_blk[8]);
    assign proc_4_data_FIFO_blk[9] = 1'b0;
    assign proc_4_data_PIPO_blk[9] = 1'b0;
    assign proc_4_start_FIFO_blk[9] = 1'b0;
    assign proc_4_TLF_FIFO_blk[9] = 1'b0;
    assign proc_4_input_sync_blk[9] = 1'b0;
    assign proc_4_output_sync_blk[9] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_4[9] = dl_detect_out ? proc_dep_vld_vec_4_reg[9] : (proc_4_data_FIFO_blk[9] | proc_4_data_PIPO_blk[9] | proc_4_start_FIFO_blk[9] | proc_4_TLF_FIFO_blk[9] | proc_4_input_sync_blk[9] | proc_4_output_sync_blk[9]);
    assign proc_4_data_FIFO_blk[10] = 1'b0;
    assign proc_4_data_PIPO_blk[10] = 1'b0;
    assign proc_4_start_FIFO_blk[10] = 1'b0;
    assign proc_4_TLF_FIFO_blk[10] = 1'b0;
    assign proc_4_input_sync_blk[10] = 1'b0;
    assign proc_4_output_sync_blk[10] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_4[10] = dl_detect_out ? proc_dep_vld_vec_4_reg[10] : (proc_4_data_FIFO_blk[10] | proc_4_data_PIPO_blk[10] | proc_4_start_FIFO_blk[10] | proc_4_TLF_FIFO_blk[10] | proc_4_input_sync_blk[10] | proc_4_output_sync_blk[10]);
    assign proc_4_data_FIFO_blk[11] = 1'b0;
    assign proc_4_data_PIPO_blk[11] = 1'b0;
    assign proc_4_start_FIFO_blk[11] = 1'b0;
    assign proc_4_TLF_FIFO_blk[11] = 1'b0;
    assign proc_4_input_sync_blk[11] = 1'b0;
    assign proc_4_output_sync_blk[11] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_4[11] = dl_detect_out ? proc_dep_vld_vec_4_reg[11] : (proc_4_data_FIFO_blk[11] | proc_4_data_PIPO_blk[11] | proc_4_start_FIFO_blk[11] | proc_4_TLF_FIFO_blk[11] | proc_4_input_sync_blk[11] | proc_4_output_sync_blk[11]);
    assign proc_4_data_FIFO_blk[12] = 1'b0;
    assign proc_4_data_PIPO_blk[12] = 1'b0;
    assign proc_4_start_FIFO_blk[12] = 1'b0;
    assign proc_4_TLF_FIFO_blk[12] = 1'b0;
    assign proc_4_input_sync_blk[12] = 1'b0;
    assign proc_4_output_sync_blk[12] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_4[12] = dl_detect_out ? proc_dep_vld_vec_4_reg[12] : (proc_4_data_FIFO_blk[12] | proc_4_data_PIPO_blk[12] | proc_4_start_FIFO_blk[12] | proc_4_TLF_FIFO_blk[12] | proc_4_input_sync_blk[12] | proc_4_output_sync_blk[12]);
    assign proc_4_data_FIFO_blk[13] = 1'b0;
    assign proc_4_data_PIPO_blk[13] = 1'b0;
    assign proc_4_start_FIFO_blk[13] = 1'b0;
    assign proc_4_TLF_FIFO_blk[13] = 1'b0;
    assign proc_4_input_sync_blk[13] = 1'b0;
    assign proc_4_output_sync_blk[13] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_4[13] = dl_detect_out ? proc_dep_vld_vec_4_reg[13] : (proc_4_data_FIFO_blk[13] | proc_4_data_PIPO_blk[13] | proc_4_start_FIFO_blk[13] | proc_4_TLF_FIFO_blk[13] | proc_4_input_sync_blk[13] | proc_4_output_sync_blk[13]);
    assign proc_4_data_FIFO_blk[14] = 1'b0;
    assign proc_4_data_PIPO_blk[14] = 1'b0;
    assign proc_4_start_FIFO_blk[14] = 1'b0;
    assign proc_4_TLF_FIFO_blk[14] = 1'b0;
    assign proc_4_input_sync_blk[14] = 1'b0;
    assign proc_4_output_sync_blk[14] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_4[14] = dl_detect_out ? proc_dep_vld_vec_4_reg[14] : (proc_4_data_FIFO_blk[14] | proc_4_data_PIPO_blk[14] | proc_4_start_FIFO_blk[14] | proc_4_TLF_FIFO_blk[14] | proc_4_input_sync_blk[14] | proc_4_output_sync_blk[14]);
    assign proc_4_data_FIFO_blk[15] = 1'b0;
    assign proc_4_data_PIPO_blk[15] = 1'b0;
    assign proc_4_start_FIFO_blk[15] = 1'b0;
    assign proc_4_TLF_FIFO_blk[15] = 1'b0;
    assign proc_4_input_sync_blk[15] = 1'b0;
    assign proc_4_output_sync_blk[15] = 1'b0 | (ap_done_reg_0 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_4[15] = dl_detect_out ? proc_dep_vld_vec_4_reg[15] : (proc_4_data_FIFO_blk[15] | proc_4_data_PIPO_blk[15] | proc_4_start_FIFO_blk[15] | proc_4_TLF_FIFO_blk[15] | proc_4_input_sync_blk[15] | proc_4_output_sync_blk[15]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_4_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_4_reg <= proc_dep_vld_vec_4;
        end
    end
    assign in_chan_dep_vld_vec_4[0] = dep_chan_vld_0_4;
    assign in_chan_dep_data_vec_4[38 : 0] = dep_chan_data_0_4;
    assign token_in_vec_4[0] = token_0_4;
    assign in_chan_dep_vld_vec_4[1] = dep_chan_vld_1_4;
    assign in_chan_dep_data_vec_4[77 : 39] = dep_chan_data_1_4;
    assign token_in_vec_4[1] = token_1_4;
    assign in_chan_dep_vld_vec_4[2] = dep_chan_vld_2_4;
    assign in_chan_dep_data_vec_4[116 : 78] = dep_chan_data_2_4;
    assign token_in_vec_4[2] = token_2_4;
    assign in_chan_dep_vld_vec_4[3] = dep_chan_vld_3_4;
    assign in_chan_dep_data_vec_4[155 : 117] = dep_chan_data_3_4;
    assign token_in_vec_4[3] = token_3_4;
    assign in_chan_dep_vld_vec_4[4] = dep_chan_vld_5_4;
    assign in_chan_dep_data_vec_4[194 : 156] = dep_chan_data_5_4;
    assign token_in_vec_4[4] = token_5_4;
    assign in_chan_dep_vld_vec_4[5] = dep_chan_vld_6_4;
    assign in_chan_dep_data_vec_4[233 : 195] = dep_chan_data_6_4;
    assign token_in_vec_4[5] = token_6_4;
    assign in_chan_dep_vld_vec_4[6] = dep_chan_vld_7_4;
    assign in_chan_dep_data_vec_4[272 : 234] = dep_chan_data_7_4;
    assign token_in_vec_4[6] = token_7_4;
    assign in_chan_dep_vld_vec_4[7] = dep_chan_vld_8_4;
    assign in_chan_dep_data_vec_4[311 : 273] = dep_chan_data_8_4;
    assign token_in_vec_4[7] = token_8_4;
    assign in_chan_dep_vld_vec_4[8] = dep_chan_vld_9_4;
    assign in_chan_dep_data_vec_4[350 : 312] = dep_chan_data_9_4;
    assign token_in_vec_4[8] = token_9_4;
    assign in_chan_dep_vld_vec_4[9] = dep_chan_vld_10_4;
    assign in_chan_dep_data_vec_4[389 : 351] = dep_chan_data_10_4;
    assign token_in_vec_4[9] = token_10_4;
    assign in_chan_dep_vld_vec_4[10] = dep_chan_vld_15_4;
    assign in_chan_dep_data_vec_4[428 : 390] = dep_chan_data_15_4;
    assign token_in_vec_4[10] = token_15_4;
    assign in_chan_dep_vld_vec_4[11] = dep_chan_vld_20_4;
    assign in_chan_dep_data_vec_4[467 : 429] = dep_chan_data_20_4;
    assign token_in_vec_4[11] = token_20_4;
    assign in_chan_dep_vld_vec_4[12] = dep_chan_vld_21_4;
    assign in_chan_dep_data_vec_4[506 : 468] = dep_chan_data_21_4;
    assign token_in_vec_4[12] = token_21_4;
    assign in_chan_dep_vld_vec_4[13] = dep_chan_vld_23_4;
    assign in_chan_dep_data_vec_4[545 : 507] = dep_chan_data_23_4;
    assign token_in_vec_4[13] = token_23_4;
    assign in_chan_dep_vld_vec_4[14] = dep_chan_vld_31_4;
    assign in_chan_dep_data_vec_4[584 : 546] = dep_chan_data_31_4;
    assign token_in_vec_4[14] = token_31_4;
    assign in_chan_dep_vld_vec_4[15] = dep_chan_vld_38_4;
    assign in_chan_dep_data_vec_4[623 : 585] = dep_chan_data_38_4;
    assign token_in_vec_4[15] = token_38_4;
    assign dep_chan_vld_4_20 = out_chan_dep_vld_vec_4[0];
    assign dep_chan_data_4_20 = out_chan_dep_data_4;
    assign token_4_20 = token_out_vec_4[0];
    assign dep_chan_vld_4_31 = out_chan_dep_vld_vec_4[1];
    assign dep_chan_data_4_31 = out_chan_dep_data_4;
    assign token_4_31 = token_out_vec_4[1];
    assign dep_chan_vld_4_0 = out_chan_dep_vld_vec_4[2];
    assign dep_chan_data_4_0 = out_chan_dep_data_4;
    assign token_4_0 = token_out_vec_4[2];
    assign dep_chan_vld_4_1 = out_chan_dep_vld_vec_4[3];
    assign dep_chan_data_4_1 = out_chan_dep_data_4;
    assign token_4_1 = token_out_vec_4[3];
    assign dep_chan_vld_4_2 = out_chan_dep_vld_vec_4[4];
    assign dep_chan_data_4_2 = out_chan_dep_data_4;
    assign token_4_2 = token_out_vec_4[4];
    assign dep_chan_vld_4_3 = out_chan_dep_vld_vec_4[5];
    assign dep_chan_data_4_3 = out_chan_dep_data_4;
    assign token_4_3 = token_out_vec_4[5];
    assign dep_chan_vld_4_5 = out_chan_dep_vld_vec_4[6];
    assign dep_chan_data_4_5 = out_chan_dep_data_4;
    assign token_4_5 = token_out_vec_4[6];
    assign dep_chan_vld_4_6 = out_chan_dep_vld_vec_4[7];
    assign dep_chan_data_4_6 = out_chan_dep_data_4;
    assign token_4_6 = token_out_vec_4[7];
    assign dep_chan_vld_4_7 = out_chan_dep_vld_vec_4[8];
    assign dep_chan_data_4_7 = out_chan_dep_data_4;
    assign token_4_7 = token_out_vec_4[8];
    assign dep_chan_vld_4_8 = out_chan_dep_vld_vec_4[9];
    assign dep_chan_data_4_8 = out_chan_dep_data_4;
    assign token_4_8 = token_out_vec_4[9];
    assign dep_chan_vld_4_9 = out_chan_dep_vld_vec_4[10];
    assign dep_chan_data_4_9 = out_chan_dep_data_4;
    assign token_4_9 = token_out_vec_4[10];
    assign dep_chan_vld_4_10 = out_chan_dep_vld_vec_4[11];
    assign dep_chan_data_4_10 = out_chan_dep_data_4;
    assign token_4_10 = token_out_vec_4[11];
    assign dep_chan_vld_4_15 = out_chan_dep_vld_vec_4[12];
    assign dep_chan_data_4_15 = out_chan_dep_data_4;
    assign token_4_15 = token_out_vec_4[12];
    assign dep_chan_vld_4_21 = out_chan_dep_vld_vec_4[13];
    assign dep_chan_data_4_21 = out_chan_dep_data_4;
    assign token_4_21 = token_out_vec_4[13];
    assign dep_chan_vld_4_23 = out_chan_dep_vld_vec_4[14];
    assign dep_chan_data_4_23 = out_chan_dep_data_4;
    assign token_4_23 = token_out_vec_4[14];
    assign dep_chan_vld_4_38 = out_chan_dep_vld_vec_4[15];
    assign dep_chan_data_4_38 = out_chan_dep_data_4;
    assign token_4_38 = token_out_vec_4[15];

    // Process: grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 5, 16, 16) cnn_pipeline_v10_hls_deadlock_detect_unit_5 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_5),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_5),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_5),
        .token_in_vec(token_in_vec_5),
        .dl_detect_in(dl_detect_out),
        .origin(origin[5]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_5),
        .out_chan_dep_data(out_chan_dep_data_5),
        .token_out_vec(token_out_vec_5),
        .dl_detect_out(dl_in_vec[5]));

    assign proc_5_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.grp_write_broker_2_8_Pipeline_VITIS_LOOP_148_5_fu_273.b_write_data_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.b_committed_0_blk_n);
    assign proc_5_data_PIPO_blk[0] = 1'b0;
    assign proc_5_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_residual_writer_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.real_start & (trans_in_cnt_8 == trans_out_cnt_8) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_residual_writer_U0_U.if_read);
    assign proc_5_TLF_FIFO_blk[0] = 1'b0;
    assign proc_5_input_sync_blk[0] = 1'b0;
    assign proc_5_output_sync_blk[0] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_5[0] = dl_detect_out ? proc_dep_vld_vec_5_reg[0] : (proc_5_data_FIFO_blk[0] | proc_5_data_PIPO_blk[0] | proc_5_start_FIFO_blk[0] | proc_5_TLF_FIFO_blk[0] | proc_5_input_sync_blk[0] | proc_5_output_sync_blk[0]);
    assign proc_5_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.grp_write_broker_2_8_Pipeline_VITIS_LOOP_148_5_fu_273.b_write_data_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.b_committed_1_blk_n);
    assign proc_5_data_PIPO_blk[1] = 1'b0;
    assign proc_5_start_FIFO_blk[1] = 1'b0;
    assign proc_5_TLF_FIFO_blk[1] = 1'b0;
    assign proc_5_input_sync_blk[1] = 1'b0;
    assign proc_5_output_sync_blk[1] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_5[1] = dl_detect_out ? proc_dep_vld_vec_5_reg[1] : (proc_5_data_FIFO_blk[1] | proc_5_data_PIPO_blk[1] | proc_5_start_FIFO_blk[1] | proc_5_TLF_FIFO_blk[1] | proc_5_input_sync_blk[1] | proc_5_output_sync_blk[1]);
    assign proc_5_data_FIFO_blk[2] = 1'b0;
    assign proc_5_data_PIPO_blk[2] = 1'b0;
    assign proc_5_start_FIFO_blk[2] = 1'b0;
    assign proc_5_TLF_FIFO_blk[2] = 1'b0;
    assign proc_5_input_sync_blk[2] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready);
    assign proc_5_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_5[2] = dl_detect_out ? proc_dep_vld_vec_5_reg[2] : (proc_5_data_FIFO_blk[2] | proc_5_data_PIPO_blk[2] | proc_5_start_FIFO_blk[2] | proc_5_TLF_FIFO_blk[2] | proc_5_input_sync_blk[2] | proc_5_output_sync_blk[2]);
    assign proc_5_data_FIFO_blk[3] = 1'b0;
    assign proc_5_data_PIPO_blk[3] = 1'b0;
    assign proc_5_start_FIFO_blk[3] = 1'b0;
    assign proc_5_TLF_FIFO_blk[3] = 1'b0;
    assign proc_5_input_sync_blk[3] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready);
    assign proc_5_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_5[3] = dl_detect_out ? proc_dep_vld_vec_5_reg[3] : (proc_5_data_FIFO_blk[3] | proc_5_data_PIPO_blk[3] | proc_5_start_FIFO_blk[3] | proc_5_TLF_FIFO_blk[3] | proc_5_input_sync_blk[3] | proc_5_output_sync_blk[3]);
    assign proc_5_data_FIFO_blk[4] = 1'b0;
    assign proc_5_data_PIPO_blk[4] = 1'b0;
    assign proc_5_start_FIFO_blk[4] = 1'b0;
    assign proc_5_TLF_FIFO_blk[4] = 1'b0;
    assign proc_5_input_sync_blk[4] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready);
    assign proc_5_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_5[4] = dl_detect_out ? proc_dep_vld_vec_5_reg[4] : (proc_5_data_FIFO_blk[4] | proc_5_data_PIPO_blk[4] | proc_5_start_FIFO_blk[4] | proc_5_TLF_FIFO_blk[4] | proc_5_input_sync_blk[4] | proc_5_output_sync_blk[4]);
    assign proc_5_data_FIFO_blk[5] = 1'b0;
    assign proc_5_data_PIPO_blk[5] = 1'b0;
    assign proc_5_start_FIFO_blk[5] = 1'b0;
    assign proc_5_TLF_FIFO_blk[5] = 1'b0;
    assign proc_5_input_sync_blk[5] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready);
    assign proc_5_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_5[5] = dl_detect_out ? proc_dep_vld_vec_5_reg[5] : (proc_5_data_FIFO_blk[5] | proc_5_data_PIPO_blk[5] | proc_5_start_FIFO_blk[5] | proc_5_TLF_FIFO_blk[5] | proc_5_input_sync_blk[5] | proc_5_output_sync_blk[5]);
    assign proc_5_data_FIFO_blk[6] = 1'b0;
    assign proc_5_data_PIPO_blk[6] = 1'b0;
    assign proc_5_start_FIFO_blk[6] = 1'b0;
    assign proc_5_TLF_FIFO_blk[6] = 1'b0;
    assign proc_5_input_sync_blk[6] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready);
    assign proc_5_output_sync_blk[6] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_5[6] = dl_detect_out ? proc_dep_vld_vec_5_reg[6] : (proc_5_data_FIFO_blk[6] | proc_5_data_PIPO_blk[6] | proc_5_start_FIFO_blk[6] | proc_5_TLF_FIFO_blk[6] | proc_5_input_sync_blk[6] | proc_5_output_sync_blk[6]);
    assign proc_5_data_FIFO_blk[7] = 1'b0;
    assign proc_5_data_PIPO_blk[7] = 1'b0;
    assign proc_5_start_FIFO_blk[7] = 1'b0;
    assign proc_5_TLF_FIFO_blk[7] = 1'b0;
    assign proc_5_input_sync_blk[7] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready);
    assign proc_5_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_5[7] = dl_detect_out ? proc_dep_vld_vec_5_reg[7] : (proc_5_data_FIFO_blk[7] | proc_5_data_PIPO_blk[7] | proc_5_start_FIFO_blk[7] | proc_5_TLF_FIFO_blk[7] | proc_5_input_sync_blk[7] | proc_5_output_sync_blk[7]);
    assign proc_5_data_FIFO_blk[8] = 1'b0;
    assign proc_5_data_PIPO_blk[8] = 1'b0;
    assign proc_5_start_FIFO_blk[8] = 1'b0;
    assign proc_5_TLF_FIFO_blk[8] = 1'b0;
    assign proc_5_input_sync_blk[8] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready);
    assign proc_5_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_5[8] = dl_detect_out ? proc_dep_vld_vec_5_reg[8] : (proc_5_data_FIFO_blk[8] | proc_5_data_PIPO_blk[8] | proc_5_start_FIFO_blk[8] | proc_5_TLF_FIFO_blk[8] | proc_5_input_sync_blk[8] | proc_5_output_sync_blk[8]);
    assign proc_5_data_FIFO_blk[9] = 1'b0;
    assign proc_5_data_PIPO_blk[9] = 1'b0;
    assign proc_5_start_FIFO_blk[9] = 1'b0;
    assign proc_5_TLF_FIFO_blk[9] = 1'b0;
    assign proc_5_input_sync_blk[9] = 1'b0;
    assign proc_5_output_sync_blk[9] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_5[9] = dl_detect_out ? proc_dep_vld_vec_5_reg[9] : (proc_5_data_FIFO_blk[9] | proc_5_data_PIPO_blk[9] | proc_5_start_FIFO_blk[9] | proc_5_TLF_FIFO_blk[9] | proc_5_input_sync_blk[9] | proc_5_output_sync_blk[9]);
    assign proc_5_data_FIFO_blk[10] = 1'b0;
    assign proc_5_data_PIPO_blk[10] = 1'b0;
    assign proc_5_start_FIFO_blk[10] = 1'b0;
    assign proc_5_TLF_FIFO_blk[10] = 1'b0;
    assign proc_5_input_sync_blk[10] = 1'b0;
    assign proc_5_output_sync_blk[10] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_5[10] = dl_detect_out ? proc_dep_vld_vec_5_reg[10] : (proc_5_data_FIFO_blk[10] | proc_5_data_PIPO_blk[10] | proc_5_start_FIFO_blk[10] | proc_5_TLF_FIFO_blk[10] | proc_5_input_sync_blk[10] | proc_5_output_sync_blk[10]);
    assign proc_5_data_FIFO_blk[11] = 1'b0;
    assign proc_5_data_PIPO_blk[11] = 1'b0;
    assign proc_5_start_FIFO_blk[11] = 1'b0;
    assign proc_5_TLF_FIFO_blk[11] = 1'b0;
    assign proc_5_input_sync_blk[11] = 1'b0;
    assign proc_5_output_sync_blk[11] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_5[11] = dl_detect_out ? proc_dep_vld_vec_5_reg[11] : (proc_5_data_FIFO_blk[11] | proc_5_data_PIPO_blk[11] | proc_5_start_FIFO_blk[11] | proc_5_TLF_FIFO_blk[11] | proc_5_input_sync_blk[11] | proc_5_output_sync_blk[11]);
    assign proc_5_data_FIFO_blk[12] = 1'b0;
    assign proc_5_data_PIPO_blk[12] = 1'b0;
    assign proc_5_start_FIFO_blk[12] = 1'b0;
    assign proc_5_TLF_FIFO_blk[12] = 1'b0;
    assign proc_5_input_sync_blk[12] = 1'b0;
    assign proc_5_output_sync_blk[12] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_5[12] = dl_detect_out ? proc_dep_vld_vec_5_reg[12] : (proc_5_data_FIFO_blk[12] | proc_5_data_PIPO_blk[12] | proc_5_start_FIFO_blk[12] | proc_5_TLF_FIFO_blk[12] | proc_5_input_sync_blk[12] | proc_5_output_sync_blk[12]);
    assign proc_5_data_FIFO_blk[13] = 1'b0;
    assign proc_5_data_PIPO_blk[13] = 1'b0;
    assign proc_5_start_FIFO_blk[13] = 1'b0;
    assign proc_5_TLF_FIFO_blk[13] = 1'b0;
    assign proc_5_input_sync_blk[13] = 1'b0;
    assign proc_5_output_sync_blk[13] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_5[13] = dl_detect_out ? proc_dep_vld_vec_5_reg[13] : (proc_5_data_FIFO_blk[13] | proc_5_data_PIPO_blk[13] | proc_5_start_FIFO_blk[13] | proc_5_TLF_FIFO_blk[13] | proc_5_input_sync_blk[13] | proc_5_output_sync_blk[13]);
    assign proc_5_data_FIFO_blk[14] = 1'b0;
    assign proc_5_data_PIPO_blk[14] = 1'b0;
    assign proc_5_start_FIFO_blk[14] = 1'b0;
    assign proc_5_TLF_FIFO_blk[14] = 1'b0;
    assign proc_5_input_sync_blk[14] = 1'b0;
    assign proc_5_output_sync_blk[14] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_5[14] = dl_detect_out ? proc_dep_vld_vec_5_reg[14] : (proc_5_data_FIFO_blk[14] | proc_5_data_PIPO_blk[14] | proc_5_start_FIFO_blk[14] | proc_5_TLF_FIFO_blk[14] | proc_5_input_sync_blk[14] | proc_5_output_sync_blk[14]);
    assign proc_5_data_FIFO_blk[15] = 1'b0;
    assign proc_5_data_PIPO_blk[15] = 1'b0;
    assign proc_5_start_FIFO_blk[15] = 1'b0;
    assign proc_5_TLF_FIFO_blk[15] = 1'b0;
    assign proc_5_input_sync_blk[15] = 1'b0;
    assign proc_5_output_sync_blk[15] = 1'b0 | (ap_done_reg_1 & grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_5[15] = dl_detect_out ? proc_dep_vld_vec_5_reg[15] : (proc_5_data_FIFO_blk[15] | proc_5_data_PIPO_blk[15] | proc_5_start_FIFO_blk[15] | proc_5_TLF_FIFO_blk[15] | proc_5_input_sync_blk[15] | proc_5_output_sync_blk[15]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_5_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_5_reg <= proc_dep_vld_vec_5;
        end
    end
    assign in_chan_dep_vld_vec_5[0] = dep_chan_vld_0_5;
    assign in_chan_dep_data_vec_5[38 : 0] = dep_chan_data_0_5;
    assign token_in_vec_5[0] = token_0_5;
    assign in_chan_dep_vld_vec_5[1] = dep_chan_vld_1_5;
    assign in_chan_dep_data_vec_5[77 : 39] = dep_chan_data_1_5;
    assign token_in_vec_5[1] = token_1_5;
    assign in_chan_dep_vld_vec_5[2] = dep_chan_vld_2_5;
    assign in_chan_dep_data_vec_5[116 : 78] = dep_chan_data_2_5;
    assign token_in_vec_5[2] = token_2_5;
    assign in_chan_dep_vld_vec_5[3] = dep_chan_vld_3_5;
    assign in_chan_dep_data_vec_5[155 : 117] = dep_chan_data_3_5;
    assign token_in_vec_5[3] = token_3_5;
    assign in_chan_dep_vld_vec_5[4] = dep_chan_vld_4_5;
    assign in_chan_dep_data_vec_5[194 : 156] = dep_chan_data_4_5;
    assign token_in_vec_5[4] = token_4_5;
    assign in_chan_dep_vld_vec_5[5] = dep_chan_vld_6_5;
    assign in_chan_dep_data_vec_5[233 : 195] = dep_chan_data_6_5;
    assign token_in_vec_5[5] = token_6_5;
    assign in_chan_dep_vld_vec_5[6] = dep_chan_vld_7_5;
    assign in_chan_dep_data_vec_5[272 : 234] = dep_chan_data_7_5;
    assign token_in_vec_5[6] = token_7_5;
    assign in_chan_dep_vld_vec_5[7] = dep_chan_vld_8_5;
    assign in_chan_dep_data_vec_5[311 : 273] = dep_chan_data_8_5;
    assign token_in_vec_5[7] = token_8_5;
    assign in_chan_dep_vld_vec_5[8] = dep_chan_vld_9_5;
    assign in_chan_dep_data_vec_5[350 : 312] = dep_chan_data_9_5;
    assign token_in_vec_5[8] = token_9_5;
    assign in_chan_dep_vld_vec_5[9] = dep_chan_vld_10_5;
    assign in_chan_dep_data_vec_5[389 : 351] = dep_chan_data_10_5;
    assign token_in_vec_5[9] = token_10_5;
    assign in_chan_dep_vld_vec_5[10] = dep_chan_vld_15_5;
    assign in_chan_dep_data_vec_5[428 : 390] = dep_chan_data_15_5;
    assign token_in_vec_5[10] = token_15_5;
    assign in_chan_dep_vld_vec_5[11] = dep_chan_vld_20_5;
    assign in_chan_dep_data_vec_5[467 : 429] = dep_chan_data_20_5;
    assign token_in_vec_5[11] = token_20_5;
    assign in_chan_dep_vld_vec_5[12] = dep_chan_vld_21_5;
    assign in_chan_dep_data_vec_5[506 : 468] = dep_chan_data_21_5;
    assign token_in_vec_5[12] = token_21_5;
    assign in_chan_dep_vld_vec_5[13] = dep_chan_vld_23_5;
    assign in_chan_dep_data_vec_5[545 : 507] = dep_chan_data_23_5;
    assign token_in_vec_5[13] = token_23_5;
    assign in_chan_dep_vld_vec_5[14] = dep_chan_vld_31_5;
    assign in_chan_dep_data_vec_5[584 : 546] = dep_chan_data_31_5;
    assign token_in_vec_5[14] = token_31_5;
    assign in_chan_dep_vld_vec_5[15] = dep_chan_vld_38_5;
    assign in_chan_dep_data_vec_5[623 : 585] = dep_chan_data_38_5;
    assign token_in_vec_5[15] = token_38_5;
    assign dep_chan_vld_5_21 = out_chan_dep_vld_vec_5[0];
    assign dep_chan_data_5_21 = out_chan_dep_data_5;
    assign token_5_21 = token_out_vec_5[0];
    assign dep_chan_vld_5_31 = out_chan_dep_vld_vec_5[1];
    assign dep_chan_data_5_31 = out_chan_dep_data_5;
    assign token_5_31 = token_out_vec_5[1];
    assign dep_chan_vld_5_0 = out_chan_dep_vld_vec_5[2];
    assign dep_chan_data_5_0 = out_chan_dep_data_5;
    assign token_5_0 = token_out_vec_5[2];
    assign dep_chan_vld_5_1 = out_chan_dep_vld_vec_5[3];
    assign dep_chan_data_5_1 = out_chan_dep_data_5;
    assign token_5_1 = token_out_vec_5[3];
    assign dep_chan_vld_5_2 = out_chan_dep_vld_vec_5[4];
    assign dep_chan_data_5_2 = out_chan_dep_data_5;
    assign token_5_2 = token_out_vec_5[4];
    assign dep_chan_vld_5_3 = out_chan_dep_vld_vec_5[5];
    assign dep_chan_data_5_3 = out_chan_dep_data_5;
    assign token_5_3 = token_out_vec_5[5];
    assign dep_chan_vld_5_4 = out_chan_dep_vld_vec_5[6];
    assign dep_chan_data_5_4 = out_chan_dep_data_5;
    assign token_5_4 = token_out_vec_5[6];
    assign dep_chan_vld_5_6 = out_chan_dep_vld_vec_5[7];
    assign dep_chan_data_5_6 = out_chan_dep_data_5;
    assign token_5_6 = token_out_vec_5[7];
    assign dep_chan_vld_5_7 = out_chan_dep_vld_vec_5[8];
    assign dep_chan_data_5_7 = out_chan_dep_data_5;
    assign token_5_7 = token_out_vec_5[8];
    assign dep_chan_vld_5_8 = out_chan_dep_vld_vec_5[9];
    assign dep_chan_data_5_8 = out_chan_dep_data_5;
    assign token_5_8 = token_out_vec_5[9];
    assign dep_chan_vld_5_9 = out_chan_dep_vld_vec_5[10];
    assign dep_chan_data_5_9 = out_chan_dep_data_5;
    assign token_5_9 = token_out_vec_5[10];
    assign dep_chan_vld_5_10 = out_chan_dep_vld_vec_5[11];
    assign dep_chan_data_5_10 = out_chan_dep_data_5;
    assign token_5_10 = token_out_vec_5[11];
    assign dep_chan_vld_5_15 = out_chan_dep_vld_vec_5[12];
    assign dep_chan_data_5_15 = out_chan_dep_data_5;
    assign token_5_15 = token_out_vec_5[12];
    assign dep_chan_vld_5_20 = out_chan_dep_vld_vec_5[13];
    assign dep_chan_data_5_20 = out_chan_dep_data_5;
    assign token_5_20 = token_out_vec_5[13];
    assign dep_chan_vld_5_23 = out_chan_dep_vld_vec_5[14];
    assign dep_chan_data_5_23 = out_chan_dep_data_5;
    assign token_5_23 = token_out_vec_5[14];
    assign dep_chan_vld_5_38 = out_chan_dep_vld_vec_5[15];
    assign dep_chan_data_5_38 = out_chan_dep_data_5;
    assign token_5_38 = token_out_vec_5[15];

    // Process: grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 6, 10, 10) cnn_pipeline_v10_hls_deadlock_detect_unit_6 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_6),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_6),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_6),
        .token_in_vec(token_in_vec_6),
        .dl_detect_in(dl_detect_out),
        .origin(origin[6]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_6),
        .out_chan_dep_data(out_chan_dep_data_6),
        .token_out_vec(token_out_vec_6),
        .dl_detect_out(dl_in_vec[6]));

    assign proc_6_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.scale_rsp_a_0_blk_n);
    assign proc_6_data_PIPO_blk[0] = 1'b0;
    assign proc_6_start_FIFO_blk[0] = 1'b0;
    assign proc_6_TLF_FIFO_blk[0] = 1'b0;
    assign proc_6_input_sync_blk[0] = 1'b0;
    assign proc_6_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_6[0] = dl_detect_out ? proc_dep_vld_vec_6_reg[0] : (proc_6_data_FIFO_blk[0] | proc_6_data_PIPO_blk[0] | proc_6_start_FIFO_blk[0] | proc_6_TLF_FIFO_blk[0] | proc_6_input_sync_blk[0] | proc_6_output_sync_blk[0]);
    assign proc_6_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.scale_rsp_a_1_blk_n);
    assign proc_6_data_PIPO_blk[1] = 1'b0;
    assign proc_6_start_FIFO_blk[1] = 1'b0;
    assign proc_6_TLF_FIFO_blk[1] = 1'b0;
    assign proc_6_input_sync_blk[1] = 1'b0;
    assign proc_6_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_6[1] = dl_detect_out ? proc_dep_vld_vec_6_reg[1] : (proc_6_data_FIFO_blk[1] | proc_6_data_PIPO_blk[1] | proc_6_start_FIFO_blk[1] | proc_6_TLF_FIFO_blk[1] | proc_6_input_sync_blk[1] | proc_6_output_sync_blk[1]);
    assign proc_6_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.scale_rsp_a_2_blk_n);
    assign proc_6_data_PIPO_blk[2] = 1'b0;
    assign proc_6_start_FIFO_blk[2] = 1'b0;
    assign proc_6_TLF_FIFO_blk[2] = 1'b0;
    assign proc_6_input_sync_blk[2] = 1'b0;
    assign proc_6_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_6[2] = dl_detect_out ? proc_dep_vld_vec_6_reg[2] : (proc_6_data_FIFO_blk[2] | proc_6_data_PIPO_blk[2] | proc_6_start_FIFO_blk[2] | proc_6_TLF_FIFO_blk[2] | proc_6_input_sync_blk[2] | proc_6_output_sync_blk[2]);
    assign proc_6_data_FIFO_blk[3] = 1'b0;
    assign proc_6_data_PIPO_blk[3] = 1'b0;
    assign proc_6_start_FIFO_blk[3] = 1'b0;
    assign proc_6_TLF_FIFO_blk[3] = 1'b0;
    assign proc_6_input_sync_blk[3] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready);
    assign proc_6_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_6[3] = dl_detect_out ? proc_dep_vld_vec_6_reg[3] : (proc_6_data_FIFO_blk[3] | proc_6_data_PIPO_blk[3] | proc_6_start_FIFO_blk[3] | proc_6_TLF_FIFO_blk[3] | proc_6_input_sync_blk[3] | proc_6_output_sync_blk[3]);
    assign proc_6_data_FIFO_blk[4] = 1'b0;
    assign proc_6_data_PIPO_blk[4] = 1'b0;
    assign proc_6_start_FIFO_blk[4] = 1'b0;
    assign proc_6_TLF_FIFO_blk[4] = 1'b0;
    assign proc_6_input_sync_blk[4] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready);
    assign proc_6_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_6[4] = dl_detect_out ? proc_dep_vld_vec_6_reg[4] : (proc_6_data_FIFO_blk[4] | proc_6_data_PIPO_blk[4] | proc_6_start_FIFO_blk[4] | proc_6_TLF_FIFO_blk[4] | proc_6_input_sync_blk[4] | proc_6_output_sync_blk[4]);
    assign proc_6_data_FIFO_blk[5] = 1'b0;
    assign proc_6_data_PIPO_blk[5] = 1'b0;
    assign proc_6_start_FIFO_blk[5] = 1'b0;
    assign proc_6_TLF_FIFO_blk[5] = 1'b0;
    assign proc_6_input_sync_blk[5] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready);
    assign proc_6_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_6[5] = dl_detect_out ? proc_dep_vld_vec_6_reg[5] : (proc_6_data_FIFO_blk[5] | proc_6_data_PIPO_blk[5] | proc_6_start_FIFO_blk[5] | proc_6_TLF_FIFO_blk[5] | proc_6_input_sync_blk[5] | proc_6_output_sync_blk[5]);
    assign proc_6_data_FIFO_blk[6] = 1'b0;
    assign proc_6_data_PIPO_blk[6] = 1'b0;
    assign proc_6_start_FIFO_blk[6] = 1'b0;
    assign proc_6_TLF_FIFO_blk[6] = 1'b0;
    assign proc_6_input_sync_blk[6] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready);
    assign proc_6_output_sync_blk[6] = 1'b0;
    assign proc_dep_vld_vec_6[6] = dl_detect_out ? proc_dep_vld_vec_6_reg[6] : (proc_6_data_FIFO_blk[6] | proc_6_data_PIPO_blk[6] | proc_6_start_FIFO_blk[6] | proc_6_TLF_FIFO_blk[6] | proc_6_input_sync_blk[6] | proc_6_output_sync_blk[6]);
    assign proc_6_data_FIFO_blk[7] = 1'b0;
    assign proc_6_data_PIPO_blk[7] = 1'b0;
    assign proc_6_start_FIFO_blk[7] = 1'b0;
    assign proc_6_TLF_FIFO_blk[7] = 1'b0;
    assign proc_6_input_sync_blk[7] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready);
    assign proc_6_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_6[7] = dl_detect_out ? proc_dep_vld_vec_6_reg[7] : (proc_6_data_FIFO_blk[7] | proc_6_data_PIPO_blk[7] | proc_6_start_FIFO_blk[7] | proc_6_TLF_FIFO_blk[7] | proc_6_input_sync_blk[7] | proc_6_output_sync_blk[7]);
    assign proc_6_data_FIFO_blk[8] = 1'b0;
    assign proc_6_data_PIPO_blk[8] = 1'b0;
    assign proc_6_start_FIFO_blk[8] = 1'b0;
    assign proc_6_TLF_FIFO_blk[8] = 1'b0;
    assign proc_6_input_sync_blk[8] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready);
    assign proc_6_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_6[8] = dl_detect_out ? proc_dep_vld_vec_6_reg[8] : (proc_6_data_FIFO_blk[8] | proc_6_data_PIPO_blk[8] | proc_6_start_FIFO_blk[8] | proc_6_TLF_FIFO_blk[8] | proc_6_input_sync_blk[8] | proc_6_output_sync_blk[8]);
    assign proc_6_data_FIFO_blk[9] = 1'b0;
    assign proc_6_data_PIPO_blk[9] = 1'b0;
    assign proc_6_start_FIFO_blk[9] = 1'b0;
    assign proc_6_TLF_FIFO_blk[9] = 1'b0;
    assign proc_6_input_sync_blk[9] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_0_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready);
    assign proc_6_output_sync_blk[9] = 1'b0;
    assign proc_dep_vld_vec_6[9] = dl_detect_out ? proc_dep_vld_vec_6_reg[9] : (proc_6_data_FIFO_blk[9] | proc_6_data_PIPO_blk[9] | proc_6_start_FIFO_blk[9] | proc_6_TLF_FIFO_blk[9] | proc_6_input_sync_blk[9] | proc_6_output_sync_blk[9]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_6_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_6_reg <= proc_dep_vld_vec_6;
        end
    end
    assign in_chan_dep_vld_vec_6[0] = dep_chan_vld_0_6;
    assign in_chan_dep_data_vec_6[38 : 0] = dep_chan_data_0_6;
    assign token_in_vec_6[0] = token_0_6;
    assign in_chan_dep_vld_vec_6[1] = dep_chan_vld_1_6;
    assign in_chan_dep_data_vec_6[77 : 39] = dep_chan_data_1_6;
    assign token_in_vec_6[1] = token_1_6;
    assign in_chan_dep_vld_vec_6[2] = dep_chan_vld_2_6;
    assign in_chan_dep_data_vec_6[116 : 78] = dep_chan_data_2_6;
    assign token_in_vec_6[2] = token_2_6;
    assign in_chan_dep_vld_vec_6[3] = dep_chan_vld_3_6;
    assign in_chan_dep_data_vec_6[155 : 117] = dep_chan_data_3_6;
    assign token_in_vec_6[3] = token_3_6;
    assign in_chan_dep_vld_vec_6[4] = dep_chan_vld_4_6;
    assign in_chan_dep_data_vec_6[194 : 156] = dep_chan_data_4_6;
    assign token_in_vec_6[4] = token_4_6;
    assign in_chan_dep_vld_vec_6[5] = dep_chan_vld_5_6;
    assign in_chan_dep_data_vec_6[233 : 195] = dep_chan_data_5_6;
    assign token_in_vec_6[5] = token_5_6;
    assign in_chan_dep_vld_vec_6[6] = dep_chan_vld_7_6;
    assign in_chan_dep_data_vec_6[272 : 234] = dep_chan_data_7_6;
    assign token_in_vec_6[6] = token_7_6;
    assign in_chan_dep_vld_vec_6[7] = dep_chan_vld_10_6;
    assign in_chan_dep_data_vec_6[311 : 273] = dep_chan_data_10_6;
    assign token_in_vec_6[7] = token_10_6;
    assign in_chan_dep_vld_vec_6[8] = dep_chan_vld_15_6;
    assign in_chan_dep_data_vec_6[350 : 312] = dep_chan_data_15_6;
    assign token_in_vec_6[8] = token_15_6;
    assign in_chan_dep_vld_vec_6[9] = dep_chan_vld_31_6;
    assign in_chan_dep_data_vec_6[389 : 351] = dep_chan_data_31_6;
    assign token_in_vec_6[9] = token_31_6;
    assign dep_chan_vld_6_10 = out_chan_dep_vld_vec_6[0];
    assign dep_chan_data_6_10 = out_chan_dep_data_6;
    assign token_6_10 = token_out_vec_6[0];
    assign dep_chan_vld_6_15 = out_chan_dep_vld_vec_6[1];
    assign dep_chan_data_6_15 = out_chan_dep_data_6;
    assign token_6_15 = token_out_vec_6[1];
    assign dep_chan_vld_6_31 = out_chan_dep_vld_vec_6[2];
    assign dep_chan_data_6_31 = out_chan_dep_data_6;
    assign token_6_31 = token_out_vec_6[2];
    assign dep_chan_vld_6_0 = out_chan_dep_vld_vec_6[3];
    assign dep_chan_data_6_0 = out_chan_dep_data_6;
    assign token_6_0 = token_out_vec_6[3];
    assign dep_chan_vld_6_1 = out_chan_dep_vld_vec_6[4];
    assign dep_chan_data_6_1 = out_chan_dep_data_6;
    assign token_6_1 = token_out_vec_6[4];
    assign dep_chan_vld_6_2 = out_chan_dep_vld_vec_6[5];
    assign dep_chan_data_6_2 = out_chan_dep_data_6;
    assign token_6_2 = token_out_vec_6[5];
    assign dep_chan_vld_6_3 = out_chan_dep_vld_vec_6[6];
    assign dep_chan_data_6_3 = out_chan_dep_data_6;
    assign token_6_3 = token_out_vec_6[6];
    assign dep_chan_vld_6_4 = out_chan_dep_vld_vec_6[7];
    assign dep_chan_data_6_4 = out_chan_dep_data_6;
    assign token_6_4 = token_out_vec_6[7];
    assign dep_chan_vld_6_5 = out_chan_dep_vld_vec_6[8];
    assign dep_chan_data_6_5 = out_chan_dep_data_6;
    assign token_6_5 = token_out_vec_6[8];
    assign dep_chan_vld_6_7 = out_chan_dep_vld_vec_6[9];
    assign dep_chan_data_6_7 = out_chan_dep_data_6;
    assign token_6_7 = token_out_vec_6[9];

    // Process: grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 7, 10, 10) cnn_pipeline_v10_hls_deadlock_detect_unit_7 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_7),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_7),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_7),
        .token_in_vec(token_in_vec_7),
        .dl_detect_in(dl_detect_out),
        .origin(origin[7]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_7),
        .out_chan_dep_data(out_chan_dep_data_7),
        .token_out_vec(token_out_vec_7),
        .dl_detect_out(dl_in_vec[7]));

    assign proc_7_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.scale_rsp_b_0_blk_n);
    assign proc_7_data_PIPO_blk[0] = 1'b0;
    assign proc_7_start_FIFO_blk[0] = 1'b0;
    assign proc_7_TLF_FIFO_blk[0] = 1'b0;
    assign proc_7_input_sync_blk[0] = 1'b0;
    assign proc_7_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_7[0] = dl_detect_out ? proc_dep_vld_vec_7_reg[0] : (proc_7_data_FIFO_blk[0] | proc_7_data_PIPO_blk[0] | proc_7_start_FIFO_blk[0] | proc_7_TLF_FIFO_blk[0] | proc_7_input_sync_blk[0] | proc_7_output_sync_blk[0]);
    assign proc_7_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.scale_rsp_b_1_blk_n);
    assign proc_7_data_PIPO_blk[1] = 1'b0;
    assign proc_7_start_FIFO_blk[1] = 1'b0;
    assign proc_7_TLF_FIFO_blk[1] = 1'b0;
    assign proc_7_input_sync_blk[1] = 1'b0;
    assign proc_7_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_7[1] = dl_detect_out ? proc_dep_vld_vec_7_reg[1] : (proc_7_data_FIFO_blk[1] | proc_7_data_PIPO_blk[1] | proc_7_start_FIFO_blk[1] | proc_7_TLF_FIFO_blk[1] | proc_7_input_sync_blk[1] | proc_7_output_sync_blk[1]);
    assign proc_7_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.scale_rsp_b_2_blk_n);
    assign proc_7_data_PIPO_blk[2] = 1'b0;
    assign proc_7_start_FIFO_blk[2] = 1'b0;
    assign proc_7_TLF_FIFO_blk[2] = 1'b0;
    assign proc_7_input_sync_blk[2] = 1'b0;
    assign proc_7_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_7[2] = dl_detect_out ? proc_dep_vld_vec_7_reg[2] : (proc_7_data_FIFO_blk[2] | proc_7_data_PIPO_blk[2] | proc_7_start_FIFO_blk[2] | proc_7_TLF_FIFO_blk[2] | proc_7_input_sync_blk[2] | proc_7_output_sync_blk[2]);
    assign proc_7_data_FIFO_blk[3] = 1'b0;
    assign proc_7_data_PIPO_blk[3] = 1'b0;
    assign proc_7_start_FIFO_blk[3] = 1'b0;
    assign proc_7_TLF_FIFO_blk[3] = 1'b0;
    assign proc_7_input_sync_blk[3] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_4_U0_ap_ready);
    assign proc_7_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_7[3] = dl_detect_out ? proc_dep_vld_vec_7_reg[3] : (proc_7_data_FIFO_blk[3] | proc_7_data_PIPO_blk[3] | proc_7_start_FIFO_blk[3] | proc_7_TLF_FIFO_blk[3] | proc_7_input_sync_blk[3] | proc_7_output_sync_blk[3]);
    assign proc_7_data_FIFO_blk[4] = 1'b0;
    assign proc_7_data_PIPO_blk[4] = 1'b0;
    assign proc_7_start_FIFO_blk[4] = 1'b0;
    assign proc_7_TLF_FIFO_blk[4] = 1'b0;
    assign proc_7_input_sync_blk[4] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_U0_ap_ready);
    assign proc_7_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_7[4] = dl_detect_out ? proc_dep_vld_vec_7_reg[4] : (proc_7_data_FIFO_blk[4] | proc_7_data_PIPO_blk[4] | proc_7_start_FIFO_blk[4] | proc_7_TLF_FIFO_blk[4] | proc_7_input_sync_blk[4] | proc_7_output_sync_blk[4]);
    assign proc_7_data_FIFO_blk[5] = 1'b0;
    assign proc_7_data_PIPO_blk[5] = 1'b0;
    assign proc_7_start_FIFO_blk[5] = 1'b0;
    assign proc_7_TLF_FIFO_blk[5] = 1'b0;
    assign proc_7_input_sync_blk[5] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_6_U0_ap_ready);
    assign proc_7_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_7[5] = dl_detect_out ? proc_dep_vld_vec_7_reg[5] : (proc_7_data_FIFO_blk[5] | proc_7_data_PIPO_blk[5] | proc_7_start_FIFO_blk[5] | proc_7_TLF_FIFO_blk[5] | proc_7_input_sync_blk[5] | proc_7_output_sync_blk[5]);
    assign proc_7_data_FIFO_blk[6] = 1'b0;
    assign proc_7_data_PIPO_blk[6] = 1'b0;
    assign proc_7_start_FIFO_blk[6] = 1'b0;
    assign proc_7_TLF_FIFO_blk[6] = 1'b0;
    assign proc_7_input_sync_blk[6] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_param_broker_2_7_U0_ap_ready);
    assign proc_7_output_sync_blk[6] = 1'b0;
    assign proc_dep_vld_vec_7[6] = dl_detect_out ? proc_dep_vld_vec_7_reg[6] : (proc_7_data_FIFO_blk[6] | proc_7_data_PIPO_blk[6] | proc_7_start_FIFO_blk[6] | proc_7_TLF_FIFO_blk[6] | proc_7_input_sync_blk[6] | proc_7_output_sync_blk[6]);
    assign proc_7_data_FIFO_blk[7] = 1'b0;
    assign proc_7_data_PIPO_blk[7] = 1'b0;
    assign proc_7_start_FIFO_blk[7] = 1'b0;
    assign proc_7_TLF_FIFO_blk[7] = 1'b0;
    assign proc_7_input_sync_blk[7] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_U0_ap_ready);
    assign proc_7_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_7[7] = dl_detect_out ? proc_dep_vld_vec_7_reg[7] : (proc_7_data_FIFO_blk[7] | proc_7_data_PIPO_blk[7] | proc_7_start_FIFO_blk[7] | proc_7_TLF_FIFO_blk[7] | proc_7_input_sync_blk[7] | proc_7_output_sync_blk[7]);
    assign proc_7_data_FIFO_blk[8] = 1'b0;
    assign proc_7_data_PIPO_blk[8] = 1'b0;
    assign proc_7_start_FIFO_blk[8] = 1'b0;
    assign proc_7_TLF_FIFO_blk[8] = 1'b0;
    assign proc_7_input_sync_blk[8] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_write_broker_2_8_U0_ap_ready);
    assign proc_7_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_7[8] = dl_detect_out ? proc_dep_vld_vec_7_reg[8] : (proc_7_data_FIFO_blk[8] | proc_7_data_PIPO_blk[8] | proc_7_start_FIFO_blk[8] | proc_7_TLF_FIFO_blk[8] | proc_7_input_sync_blk[8] | proc_7_output_sync_blk[8]);
    assign proc_7_data_FIFO_blk[9] = 1'b0;
    assign proc_7_data_PIPO_blk[9] = 1'b0;
    assign proc_7_start_FIFO_blk[9] = 1'b0;
    assign proc_7_TLF_FIFO_blk[9] = 1'b0;
    assign proc_7_input_sync_blk[9] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_1_3_16_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.scale_service_1_3_16_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.ap_sync_scale_service_0_3_16_U0_ap_ready);
    assign proc_7_output_sync_blk[9] = 1'b0;
    assign proc_dep_vld_vec_7[9] = dl_detect_out ? proc_dep_vld_vec_7_reg[9] : (proc_7_data_FIFO_blk[9] | proc_7_data_PIPO_blk[9] | proc_7_start_FIFO_blk[9] | proc_7_TLF_FIFO_blk[9] | proc_7_input_sync_blk[9] | proc_7_output_sync_blk[9]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_7_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_7_reg <= proc_dep_vld_vec_7;
        end
    end
    assign in_chan_dep_vld_vec_7[0] = dep_chan_vld_0_7;
    assign in_chan_dep_data_vec_7[38 : 0] = dep_chan_data_0_7;
    assign token_in_vec_7[0] = token_0_7;
    assign in_chan_dep_vld_vec_7[1] = dep_chan_vld_1_7;
    assign in_chan_dep_data_vec_7[77 : 39] = dep_chan_data_1_7;
    assign token_in_vec_7[1] = token_1_7;
    assign in_chan_dep_vld_vec_7[2] = dep_chan_vld_2_7;
    assign in_chan_dep_data_vec_7[116 : 78] = dep_chan_data_2_7;
    assign token_in_vec_7[2] = token_2_7;
    assign in_chan_dep_vld_vec_7[3] = dep_chan_vld_3_7;
    assign in_chan_dep_data_vec_7[155 : 117] = dep_chan_data_3_7;
    assign token_in_vec_7[3] = token_3_7;
    assign in_chan_dep_vld_vec_7[4] = dep_chan_vld_4_7;
    assign in_chan_dep_data_vec_7[194 : 156] = dep_chan_data_4_7;
    assign token_in_vec_7[4] = token_4_7;
    assign in_chan_dep_vld_vec_7[5] = dep_chan_vld_5_7;
    assign in_chan_dep_data_vec_7[233 : 195] = dep_chan_data_5_7;
    assign token_in_vec_7[5] = token_5_7;
    assign in_chan_dep_vld_vec_7[6] = dep_chan_vld_6_7;
    assign in_chan_dep_data_vec_7[272 : 234] = dep_chan_data_6_7;
    assign token_in_vec_7[6] = token_6_7;
    assign in_chan_dep_vld_vec_7[7] = dep_chan_vld_10_7;
    assign in_chan_dep_data_vec_7[311 : 273] = dep_chan_data_10_7;
    assign token_in_vec_7[7] = token_10_7;
    assign in_chan_dep_vld_vec_7[8] = dep_chan_vld_15_7;
    assign in_chan_dep_data_vec_7[350 : 312] = dep_chan_data_15_7;
    assign token_in_vec_7[8] = token_15_7;
    assign in_chan_dep_vld_vec_7[9] = dep_chan_vld_31_7;
    assign in_chan_dep_data_vec_7[389 : 351] = dep_chan_data_31_7;
    assign token_in_vec_7[9] = token_31_7;
    assign dep_chan_vld_7_10 = out_chan_dep_vld_vec_7[0];
    assign dep_chan_data_7_10 = out_chan_dep_data_7;
    assign token_7_10 = token_out_vec_7[0];
    assign dep_chan_vld_7_15 = out_chan_dep_vld_vec_7[1];
    assign dep_chan_data_7_15 = out_chan_dep_data_7;
    assign token_7_15 = token_out_vec_7[1];
    assign dep_chan_vld_7_31 = out_chan_dep_vld_vec_7[2];
    assign dep_chan_data_7_31 = out_chan_dep_data_7;
    assign token_7_31 = token_out_vec_7[2];
    assign dep_chan_vld_7_0 = out_chan_dep_vld_vec_7[3];
    assign dep_chan_data_7_0 = out_chan_dep_data_7;
    assign token_7_0 = token_out_vec_7[3];
    assign dep_chan_vld_7_1 = out_chan_dep_vld_vec_7[4];
    assign dep_chan_data_7_1 = out_chan_dep_data_7;
    assign token_7_1 = token_out_vec_7[4];
    assign dep_chan_vld_7_2 = out_chan_dep_vld_vec_7[5];
    assign dep_chan_data_7_2 = out_chan_dep_data_7;
    assign token_7_2 = token_out_vec_7[5];
    assign dep_chan_vld_7_3 = out_chan_dep_vld_vec_7[6];
    assign dep_chan_data_7_3 = out_chan_dep_data_7;
    assign token_7_3 = token_out_vec_7[6];
    assign dep_chan_vld_7_4 = out_chan_dep_vld_vec_7[7];
    assign dep_chan_data_7_4 = out_chan_dep_data_7;
    assign token_7_4 = token_out_vec_7[7];
    assign dep_chan_vld_7_5 = out_chan_dep_vld_vec_7[8];
    assign dep_chan_data_7_5 = out_chan_dep_data_7;
    assign token_7_5 = token_out_vec_7[8];
    assign dep_chan_vld_7_6 = out_chan_dep_vld_vec_7[9];
    assign dep_chan_data_7_6 = out_chan_dep_data_7;
    assign token_7_6 = token_out_vec_7[9];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 8, 11, 11) cnn_pipeline_v10_hls_deadlock_detect_unit_8 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_8),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_8),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_8),
        .token_in_vec(token_in_vec_8),
        .dl_detect_in(dl_detect_out),
        .origin(origin[8]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_8),
        .out_chan_dep_data(out_chan_dep_data_8),
        .token_out_vec(token_out_vec_8),
        .dl_detect_out(dl_in_vec[8]));

    assign proc_8_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.a_read_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.grp_p_anonymous_namespace_feed_chain_1_Pipeline_VITIS_LOOP_325_3_VITIS_LOOP_327_4_VIT_fu_217.a_read_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.grp_p_anonymous_namespace_feed_chain_1_Pipeline_VITIS_LOOP_325_3_VITIS_LOOP_327_4_VIT_fu_217.a_read_data_0_blk_n);
    assign proc_8_data_PIPO_blk[0] = 1'b0;
    assign proc_8_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_feed_chain_1_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_feed_chain_1_U0_U.if_write);
    assign proc_8_TLF_FIFO_blk[0] = 1'b0;
    assign proc_8_input_sync_blk[0] = 1'b0;
    assign proc_8_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_8[0] = dl_detect_out ? proc_dep_vld_vec_8_reg[0] : (proc_8_data_FIFO_blk[0] | proc_8_data_PIPO_blk[0] | proc_8_start_FIFO_blk[0] | proc_8_TLF_FIFO_blk[0] | proc_8_input_sync_blk[0] | proc_8_output_sync_blk[0]);
    assign proc_8_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.row_ready_a_blk_n);
    assign proc_8_data_PIPO_blk[1] = 1'b0;
    assign proc_8_start_FIFO_blk[1] = 1'b0;
    assign proc_8_TLF_FIFO_blk[1] = 1'b0;
    assign proc_8_input_sync_blk[1] = 1'b0;
    assign proc_8_output_sync_blk[1] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_8[1] = dl_detect_out ? proc_dep_vld_vec_8_reg[1] : (proc_8_data_FIFO_blk[1] | proc_8_data_PIPO_blk[1] | proc_8_start_FIFO_blk[1] | proc_8_TLF_FIFO_blk[1] | proc_8_input_sync_blk[1] | proc_8_output_sync_blk[1]);
    assign proc_8_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.grp_p_anonymous_namespace_feed_chain_1_Pipeline_VITIS_LOOP_325_3_VITIS_LOOP_327_4_VIT_fu_217.input_a_blk_n);
    assign proc_8_data_PIPO_blk[2] = 1'b0;
    assign proc_8_start_FIFO_blk[2] = 1'b0;
    assign proc_8_TLF_FIFO_blk[2] = 1'b0;
    assign proc_8_input_sync_blk[2] = 1'b0;
    assign proc_8_output_sync_blk[2] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_8[2] = dl_detect_out ? proc_dep_vld_vec_8_reg[2] : (proc_8_data_FIFO_blk[2] | proc_8_data_PIPO_blk[2] | proc_8_start_FIFO_blk[2] | proc_8_TLF_FIFO_blk[2] | proc_8_input_sync_blk[2] | proc_8_output_sync_blk[2]);
    assign proc_8_data_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.errors_a_blk_n);
    assign proc_8_data_PIPO_blk[3] = 1'b0;
    assign proc_8_start_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_collect_errors_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.real_start & (trans_in_cnt_14 == trans_out_cnt_14) & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_collect_errors_U0_U.if_read);
    assign proc_8_TLF_FIFO_blk[3] = 1'b0;
    assign proc_8_input_sync_blk[3] = 1'b0;
    assign proc_8_output_sync_blk[3] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_8[3] = dl_detect_out ? proc_dep_vld_vec_8_reg[3] : (proc_8_data_FIFO_blk[3] | proc_8_data_PIPO_blk[3] | proc_8_start_FIFO_blk[3] | proc_8_TLF_FIFO_blk[3] | proc_8_input_sync_blk[3] | proc_8_output_sync_blk[3]);
    assign proc_8_data_FIFO_blk[4] = 1'b0;
    assign proc_8_data_PIPO_blk[4] = 1'b0;
    assign proc_8_start_FIFO_blk[4] = 1'b0;
    assign proc_8_TLF_FIFO_blk[4] = 1'b0;
    assign proc_8_input_sync_blk[4] = 1'b0;
    assign proc_8_output_sync_blk[4] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_8[4] = dl_detect_out ? proc_dep_vld_vec_8_reg[4] : (proc_8_data_FIFO_blk[4] | proc_8_data_PIPO_blk[4] | proc_8_start_FIFO_blk[4] | proc_8_TLF_FIFO_blk[4] | proc_8_input_sync_blk[4] | proc_8_output_sync_blk[4]);
    assign proc_8_data_FIFO_blk[5] = 1'b0;
    assign proc_8_data_PIPO_blk[5] = 1'b0;
    assign proc_8_start_FIFO_blk[5] = 1'b0;
    assign proc_8_TLF_FIFO_blk[5] = 1'b0;
    assign proc_8_input_sync_blk[5] = 1'b0;
    assign proc_8_output_sync_blk[5] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_8[5] = dl_detect_out ? proc_dep_vld_vec_8_reg[5] : (proc_8_data_FIFO_blk[5] | proc_8_data_PIPO_blk[5] | proc_8_start_FIFO_blk[5] | proc_8_TLF_FIFO_blk[5] | proc_8_input_sync_blk[5] | proc_8_output_sync_blk[5]);
    assign proc_8_data_FIFO_blk[6] = 1'b0;
    assign proc_8_data_PIPO_blk[6] = 1'b0;
    assign proc_8_start_FIFO_blk[6] = 1'b0;
    assign proc_8_TLF_FIFO_blk[6] = 1'b0;
    assign proc_8_input_sync_blk[6] = 1'b0;
    assign proc_8_output_sync_blk[6] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_8[6] = dl_detect_out ? proc_dep_vld_vec_8_reg[6] : (proc_8_data_FIFO_blk[6] | proc_8_data_PIPO_blk[6] | proc_8_start_FIFO_blk[6] | proc_8_TLF_FIFO_blk[6] | proc_8_input_sync_blk[6] | proc_8_output_sync_blk[6]);
    assign proc_8_data_FIFO_blk[7] = 1'b0;
    assign proc_8_data_PIPO_blk[7] = 1'b0;
    assign proc_8_start_FIFO_blk[7] = 1'b0;
    assign proc_8_TLF_FIFO_blk[7] = 1'b0;
    assign proc_8_input_sync_blk[7] = 1'b0;
    assign proc_8_output_sync_blk[7] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_8[7] = dl_detect_out ? proc_dep_vld_vec_8_reg[7] : (proc_8_data_FIFO_blk[7] | proc_8_data_PIPO_blk[7] | proc_8_start_FIFO_blk[7] | proc_8_TLF_FIFO_blk[7] | proc_8_input_sync_blk[7] | proc_8_output_sync_blk[7]);
    assign proc_8_data_FIFO_blk[8] = 1'b0;
    assign proc_8_data_PIPO_blk[8] = 1'b0;
    assign proc_8_start_FIFO_blk[8] = 1'b0;
    assign proc_8_TLF_FIFO_blk[8] = 1'b0;
    assign proc_8_input_sync_blk[8] = 1'b0;
    assign proc_8_output_sync_blk[8] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_8[8] = dl_detect_out ? proc_dep_vld_vec_8_reg[8] : (proc_8_data_FIFO_blk[8] | proc_8_data_PIPO_blk[8] | proc_8_start_FIFO_blk[8] | proc_8_TLF_FIFO_blk[8] | proc_8_input_sync_blk[8] | proc_8_output_sync_blk[8]);
    assign proc_8_data_FIFO_blk[9] = 1'b0;
    assign proc_8_data_PIPO_blk[9] = 1'b0;
    assign proc_8_start_FIFO_blk[9] = 1'b0;
    assign proc_8_TLF_FIFO_blk[9] = 1'b0;
    assign proc_8_input_sync_blk[9] = 1'b0;
    assign proc_8_output_sync_blk[9] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_8[9] = dl_detect_out ? proc_dep_vld_vec_8_reg[9] : (proc_8_data_FIFO_blk[9] | proc_8_data_PIPO_blk[9] | proc_8_start_FIFO_blk[9] | proc_8_TLF_FIFO_blk[9] | proc_8_input_sync_blk[9] | proc_8_output_sync_blk[9]);
    assign proc_8_data_FIFO_blk[10] = 1'b0;
    assign proc_8_data_PIPO_blk[10] = 1'b0;
    assign proc_8_start_FIFO_blk[10] = 1'b0;
    assign proc_8_TLF_FIFO_blk[10] = 1'b0;
    assign proc_8_input_sync_blk[10] = 1'b0;
    assign proc_8_output_sync_blk[10] = 1'b0 | (ap_done_reg_2 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_8[10] = dl_detect_out ? proc_dep_vld_vec_8_reg[10] : (proc_8_data_FIFO_blk[10] | proc_8_data_PIPO_blk[10] | proc_8_start_FIFO_blk[10] | proc_8_TLF_FIFO_blk[10] | proc_8_input_sync_blk[10] | proc_8_output_sync_blk[10]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_8_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_8_reg <= proc_dep_vld_vec_8;
        end
    end
    assign in_chan_dep_vld_vec_8[0] = dep_chan_vld_2_8;
    assign in_chan_dep_data_vec_8[38 : 0] = dep_chan_data_2_8;
    assign token_in_vec_8[0] = token_2_8;
    assign in_chan_dep_vld_vec_8[1] = dep_chan_vld_4_8;
    assign in_chan_dep_data_vec_8[77 : 39] = dep_chan_data_4_8;
    assign token_in_vec_8[1] = token_4_8;
    assign in_chan_dep_vld_vec_8[2] = dep_chan_vld_5_8;
    assign in_chan_dep_data_vec_8[116 : 78] = dep_chan_data_5_8;
    assign token_in_vec_8[2] = token_5_8;
    assign in_chan_dep_vld_vec_8[3] = dep_chan_vld_9_8;
    assign in_chan_dep_data_vec_8[155 : 117] = dep_chan_data_9_8;
    assign token_in_vec_8[3] = token_9_8;
    assign in_chan_dep_vld_vec_8[4] = dep_chan_vld_10_8;
    assign in_chan_dep_data_vec_8[194 : 156] = dep_chan_data_10_8;
    assign token_in_vec_8[4] = token_10_8;
    assign in_chan_dep_vld_vec_8[5] = dep_chan_vld_15_8;
    assign in_chan_dep_data_vec_8[233 : 195] = dep_chan_data_15_8;
    assign token_in_vec_8[5] = token_15_8;
    assign in_chan_dep_vld_vec_8[6] = dep_chan_vld_20_8;
    assign in_chan_dep_data_vec_8[272 : 234] = dep_chan_data_20_8;
    assign token_in_vec_8[6] = token_20_8;
    assign in_chan_dep_vld_vec_8[7] = dep_chan_vld_21_8;
    assign in_chan_dep_data_vec_8[311 : 273] = dep_chan_data_21_8;
    assign token_in_vec_8[7] = token_21_8;
    assign in_chan_dep_vld_vec_8[8] = dep_chan_vld_23_8;
    assign in_chan_dep_data_vec_8[350 : 312] = dep_chan_data_23_8;
    assign token_in_vec_8[8] = token_23_8;
    assign in_chan_dep_vld_vec_8[9] = dep_chan_vld_31_8;
    assign in_chan_dep_data_vec_8[389 : 351] = dep_chan_data_31_8;
    assign token_in_vec_8[9] = token_31_8;
    assign in_chan_dep_vld_vec_8[10] = dep_chan_vld_38_8;
    assign in_chan_dep_data_vec_8[428 : 390] = dep_chan_data_38_8;
    assign token_in_vec_8[10] = token_38_8;
    assign dep_chan_vld_8_2 = out_chan_dep_vld_vec_8[0];
    assign dep_chan_data_8_2 = out_chan_dep_data_8;
    assign token_8_2 = token_out_vec_8[0];
    assign dep_chan_vld_8_31 = out_chan_dep_vld_vec_8[1];
    assign dep_chan_data_8_31 = out_chan_dep_data_8;
    assign token_8_31 = token_out_vec_8[1];
    assign dep_chan_vld_8_10 = out_chan_dep_vld_vec_8[2];
    assign dep_chan_data_8_10 = out_chan_dep_data_8;
    assign token_8_10 = token_out_vec_8[2];
    assign dep_chan_vld_8_38 = out_chan_dep_vld_vec_8[3];
    assign dep_chan_data_8_38 = out_chan_dep_data_8;
    assign token_8_38 = token_out_vec_8[3];
    assign dep_chan_vld_8_4 = out_chan_dep_vld_vec_8[4];
    assign dep_chan_data_8_4 = out_chan_dep_data_8;
    assign token_8_4 = token_out_vec_8[4];
    assign dep_chan_vld_8_5 = out_chan_dep_vld_vec_8[5];
    assign dep_chan_data_8_5 = out_chan_dep_data_8;
    assign token_8_5 = token_out_vec_8[5];
    assign dep_chan_vld_8_9 = out_chan_dep_vld_vec_8[6];
    assign dep_chan_data_8_9 = out_chan_dep_data_8;
    assign token_8_9 = token_out_vec_8[6];
    assign dep_chan_vld_8_15 = out_chan_dep_vld_vec_8[7];
    assign dep_chan_data_8_15 = out_chan_dep_data_8;
    assign token_8_15 = token_out_vec_8[7];
    assign dep_chan_vld_8_20 = out_chan_dep_vld_vec_8[8];
    assign dep_chan_data_8_20 = out_chan_dep_data_8;
    assign token_8_20 = token_out_vec_8[8];
    assign dep_chan_vld_8_21 = out_chan_dep_vld_vec_8[9];
    assign dep_chan_data_8_21 = out_chan_dep_data_8;
    assign token_8_21 = token_out_vec_8[9];
    assign dep_chan_vld_8_23 = out_chan_dep_vld_vec_8[10];
    assign dep_chan_data_8_23 = out_chan_dep_data_8;
    assign token_8_23 = token_out_vec_8[10];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 9, 11, 11) cnn_pipeline_v10_hls_deadlock_detect_unit_9 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_9),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_9),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_9),
        .token_in_vec(token_in_vec_9),
        .dl_detect_in(dl_detect_out),
        .origin(origin[9]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_9),
        .out_chan_dep_data(out_chan_dep_data_9),
        .token_out_vec(token_out_vec_9),
        .dl_detect_out(dl_in_vec[9]));

    assign proc_9_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.b_read_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.grp_p_anonymous_namespace_feed_chain_Pipeline_VITIS_LOOP_325_3_VITIS_LOOP_327_4_VITIS_fu_217.b_read_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.grp_p_anonymous_namespace_feed_chain_Pipeline_VITIS_LOOP_325_3_VITIS_LOOP_327_4_VITIS_fu_217.b_read_data_0_blk_n);
    assign proc_9_data_PIPO_blk[0] = 1'b0;
    assign proc_9_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_feed_chain_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_feed_chain_U0_U.if_write);
    assign proc_9_TLF_FIFO_blk[0] = 1'b0;
    assign proc_9_input_sync_blk[0] = 1'b0;
    assign proc_9_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_9[0] = dl_detect_out ? proc_dep_vld_vec_9_reg[0] : (proc_9_data_FIFO_blk[0] | proc_9_data_PIPO_blk[0] | proc_9_start_FIFO_blk[0] | proc_9_TLF_FIFO_blk[0] | proc_9_input_sync_blk[0] | proc_9_output_sync_blk[0]);
    assign proc_9_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.row_ready_b_blk_n);
    assign proc_9_data_PIPO_blk[1] = 1'b0;
    assign proc_9_start_FIFO_blk[1] = 1'b0;
    assign proc_9_TLF_FIFO_blk[1] = 1'b0;
    assign proc_9_input_sync_blk[1] = 1'b0;
    assign proc_9_output_sync_blk[1] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_9[1] = dl_detect_out ? proc_dep_vld_vec_9_reg[1] : (proc_9_data_FIFO_blk[1] | proc_9_data_PIPO_blk[1] | proc_9_start_FIFO_blk[1] | proc_9_TLF_FIFO_blk[1] | proc_9_input_sync_blk[1] | proc_9_output_sync_blk[1]);
    assign proc_9_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.grp_p_anonymous_namespace_feed_chain_Pipeline_VITIS_LOOP_325_3_VITIS_LOOP_327_4_VITIS_fu_217.input_b_blk_n);
    assign proc_9_data_PIPO_blk[2] = 1'b0;
    assign proc_9_start_FIFO_blk[2] = 1'b0;
    assign proc_9_TLF_FIFO_blk[2] = 1'b0;
    assign proc_9_input_sync_blk[2] = 1'b0;
    assign proc_9_output_sync_blk[2] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_9[2] = dl_detect_out ? proc_dep_vld_vec_9_reg[2] : (proc_9_data_FIFO_blk[2] | proc_9_data_PIPO_blk[2] | proc_9_start_FIFO_blk[2] | proc_9_TLF_FIFO_blk[2] | proc_9_input_sync_blk[2] | proc_9_output_sync_blk[2]);
    assign proc_9_data_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.errors_b_blk_n);
    assign proc_9_data_PIPO_blk[3] = 1'b0;
    assign proc_9_start_FIFO_blk[3] = 1'b0;
    assign proc_9_TLF_FIFO_blk[3] = 1'b0;
    assign proc_9_input_sync_blk[3] = 1'b0;
    assign proc_9_output_sync_blk[3] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_9[3] = dl_detect_out ? proc_dep_vld_vec_9_reg[3] : (proc_9_data_FIFO_blk[3] | proc_9_data_PIPO_blk[3] | proc_9_start_FIFO_blk[3] | proc_9_TLF_FIFO_blk[3] | proc_9_input_sync_blk[3] | proc_9_output_sync_blk[3]);
    assign proc_9_data_FIFO_blk[4] = 1'b0;
    assign proc_9_data_PIPO_blk[4] = 1'b0;
    assign proc_9_start_FIFO_blk[4] = 1'b0;
    assign proc_9_TLF_FIFO_blk[4] = 1'b0;
    assign proc_9_input_sync_blk[4] = 1'b0;
    assign proc_9_output_sync_blk[4] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_9[4] = dl_detect_out ? proc_dep_vld_vec_9_reg[4] : (proc_9_data_FIFO_blk[4] | proc_9_data_PIPO_blk[4] | proc_9_start_FIFO_blk[4] | proc_9_TLF_FIFO_blk[4] | proc_9_input_sync_blk[4] | proc_9_output_sync_blk[4]);
    assign proc_9_data_FIFO_blk[5] = 1'b0;
    assign proc_9_data_PIPO_blk[5] = 1'b0;
    assign proc_9_start_FIFO_blk[5] = 1'b0;
    assign proc_9_TLF_FIFO_blk[5] = 1'b0;
    assign proc_9_input_sync_blk[5] = 1'b0;
    assign proc_9_output_sync_blk[5] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_9[5] = dl_detect_out ? proc_dep_vld_vec_9_reg[5] : (proc_9_data_FIFO_blk[5] | proc_9_data_PIPO_blk[5] | proc_9_start_FIFO_blk[5] | proc_9_TLF_FIFO_blk[5] | proc_9_input_sync_blk[5] | proc_9_output_sync_blk[5]);
    assign proc_9_data_FIFO_blk[6] = 1'b0;
    assign proc_9_data_PIPO_blk[6] = 1'b0;
    assign proc_9_start_FIFO_blk[6] = 1'b0;
    assign proc_9_TLF_FIFO_blk[6] = 1'b0;
    assign proc_9_input_sync_blk[6] = 1'b0;
    assign proc_9_output_sync_blk[6] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_9[6] = dl_detect_out ? proc_dep_vld_vec_9_reg[6] : (proc_9_data_FIFO_blk[6] | proc_9_data_PIPO_blk[6] | proc_9_start_FIFO_blk[6] | proc_9_TLF_FIFO_blk[6] | proc_9_input_sync_blk[6] | proc_9_output_sync_blk[6]);
    assign proc_9_data_FIFO_blk[7] = 1'b0;
    assign proc_9_data_PIPO_blk[7] = 1'b0;
    assign proc_9_start_FIFO_blk[7] = 1'b0;
    assign proc_9_TLF_FIFO_blk[7] = 1'b0;
    assign proc_9_input_sync_blk[7] = 1'b0;
    assign proc_9_output_sync_blk[7] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_9[7] = dl_detect_out ? proc_dep_vld_vec_9_reg[7] : (proc_9_data_FIFO_blk[7] | proc_9_data_PIPO_blk[7] | proc_9_start_FIFO_blk[7] | proc_9_TLF_FIFO_blk[7] | proc_9_input_sync_blk[7] | proc_9_output_sync_blk[7]);
    assign proc_9_data_FIFO_blk[8] = 1'b0;
    assign proc_9_data_PIPO_blk[8] = 1'b0;
    assign proc_9_start_FIFO_blk[8] = 1'b0;
    assign proc_9_TLF_FIFO_blk[8] = 1'b0;
    assign proc_9_input_sync_blk[8] = 1'b0;
    assign proc_9_output_sync_blk[8] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_9[8] = dl_detect_out ? proc_dep_vld_vec_9_reg[8] : (proc_9_data_FIFO_blk[8] | proc_9_data_PIPO_blk[8] | proc_9_start_FIFO_blk[8] | proc_9_TLF_FIFO_blk[8] | proc_9_input_sync_blk[8] | proc_9_output_sync_blk[8]);
    assign proc_9_data_FIFO_blk[9] = 1'b0;
    assign proc_9_data_PIPO_blk[9] = 1'b0;
    assign proc_9_start_FIFO_blk[9] = 1'b0;
    assign proc_9_TLF_FIFO_blk[9] = 1'b0;
    assign proc_9_input_sync_blk[9] = 1'b0;
    assign proc_9_output_sync_blk[9] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_9[9] = dl_detect_out ? proc_dep_vld_vec_9_reg[9] : (proc_9_data_FIFO_blk[9] | proc_9_data_PIPO_blk[9] | proc_9_start_FIFO_blk[9] | proc_9_TLF_FIFO_blk[9] | proc_9_input_sync_blk[9] | proc_9_output_sync_blk[9]);
    assign proc_9_data_FIFO_blk[10] = 1'b0;
    assign proc_9_data_PIPO_blk[10] = 1'b0;
    assign proc_9_start_FIFO_blk[10] = 1'b0;
    assign proc_9_TLF_FIFO_blk[10] = 1'b0;
    assign proc_9_input_sync_blk[10] = 1'b0;
    assign proc_9_output_sync_blk[10] = 1'b0 | (ap_done_reg_3 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_9[10] = dl_detect_out ? proc_dep_vld_vec_9_reg[10] : (proc_9_data_FIFO_blk[10] | proc_9_data_PIPO_blk[10] | proc_9_start_FIFO_blk[10] | proc_9_TLF_FIFO_blk[10] | proc_9_input_sync_blk[10] | proc_9_output_sync_blk[10]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_9_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_9_reg <= proc_dep_vld_vec_9;
        end
    end
    assign in_chan_dep_vld_vec_9[0] = dep_chan_vld_3_9;
    assign in_chan_dep_data_vec_9[38 : 0] = dep_chan_data_3_9;
    assign token_in_vec_9[0] = token_3_9;
    assign in_chan_dep_vld_vec_9[1] = dep_chan_vld_4_9;
    assign in_chan_dep_data_vec_9[77 : 39] = dep_chan_data_4_9;
    assign token_in_vec_9[1] = token_4_9;
    assign in_chan_dep_vld_vec_9[2] = dep_chan_vld_5_9;
    assign in_chan_dep_data_vec_9[116 : 78] = dep_chan_data_5_9;
    assign token_in_vec_9[2] = token_5_9;
    assign in_chan_dep_vld_vec_9[3] = dep_chan_vld_8_9;
    assign in_chan_dep_data_vec_9[155 : 117] = dep_chan_data_8_9;
    assign token_in_vec_9[3] = token_8_9;
    assign in_chan_dep_vld_vec_9[4] = dep_chan_vld_10_9;
    assign in_chan_dep_data_vec_9[194 : 156] = dep_chan_data_10_9;
    assign token_in_vec_9[4] = token_10_9;
    assign in_chan_dep_vld_vec_9[5] = dep_chan_vld_15_9;
    assign in_chan_dep_data_vec_9[233 : 195] = dep_chan_data_15_9;
    assign token_in_vec_9[5] = token_15_9;
    assign in_chan_dep_vld_vec_9[6] = dep_chan_vld_20_9;
    assign in_chan_dep_data_vec_9[272 : 234] = dep_chan_data_20_9;
    assign token_in_vec_9[6] = token_20_9;
    assign in_chan_dep_vld_vec_9[7] = dep_chan_vld_21_9;
    assign in_chan_dep_data_vec_9[311 : 273] = dep_chan_data_21_9;
    assign token_in_vec_9[7] = token_21_9;
    assign in_chan_dep_vld_vec_9[8] = dep_chan_vld_23_9;
    assign in_chan_dep_data_vec_9[350 : 312] = dep_chan_data_23_9;
    assign token_in_vec_9[8] = token_23_9;
    assign in_chan_dep_vld_vec_9[9] = dep_chan_vld_31_9;
    assign in_chan_dep_data_vec_9[389 : 351] = dep_chan_data_31_9;
    assign token_in_vec_9[9] = token_31_9;
    assign in_chan_dep_vld_vec_9[10] = dep_chan_vld_38_9;
    assign in_chan_dep_data_vec_9[428 : 390] = dep_chan_data_38_9;
    assign token_in_vec_9[10] = token_38_9;
    assign dep_chan_vld_9_3 = out_chan_dep_vld_vec_9[0];
    assign dep_chan_data_9_3 = out_chan_dep_data_9;
    assign token_9_3 = token_out_vec_9[0];
    assign dep_chan_vld_9_31 = out_chan_dep_vld_vec_9[1];
    assign dep_chan_data_9_31 = out_chan_dep_data_9;
    assign token_9_31 = token_out_vec_9[1];
    assign dep_chan_vld_9_10 = out_chan_dep_vld_vec_9[2];
    assign dep_chan_data_9_10 = out_chan_dep_data_9;
    assign token_9_10 = token_out_vec_9[2];
    assign dep_chan_vld_9_38 = out_chan_dep_vld_vec_9[3];
    assign dep_chan_data_9_38 = out_chan_dep_data_9;
    assign token_9_38 = token_out_vec_9[3];
    assign dep_chan_vld_9_4 = out_chan_dep_vld_vec_9[4];
    assign dep_chan_data_9_4 = out_chan_dep_data_9;
    assign token_9_4 = token_out_vec_9[4];
    assign dep_chan_vld_9_5 = out_chan_dep_vld_vec_9[5];
    assign dep_chan_data_9_5 = out_chan_dep_data_9;
    assign token_9_5 = token_out_vec_9[5];
    assign dep_chan_vld_9_8 = out_chan_dep_vld_vec_9[6];
    assign dep_chan_data_9_8 = out_chan_dep_data_9;
    assign token_9_8 = token_out_vec_9[6];
    assign dep_chan_vld_9_15 = out_chan_dep_vld_vec_9[7];
    assign dep_chan_data_9_15 = out_chan_dep_data_9;
    assign token_9_15 = token_out_vec_9[7];
    assign dep_chan_vld_9_20 = out_chan_dep_vld_vec_9[8];
    assign dep_chan_data_9_20 = out_chan_dep_data_9;
    assign token_9_20 = token_out_vec_9[8];
    assign dep_chan_vld_9_21 = out_chan_dep_vld_vec_9[9];
    assign dep_chan_data_9_21 = out_chan_dep_data_9;
    assign token_9_21 = token_out_vec_9[9];
    assign dep_chan_vld_9_23 = out_chan_dep_vld_vec_9[10];
    assign dep_chan_data_9_23 = out_chan_dep_data_9;
    assign token_9_23 = token_out_vec_9[10];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 10, 13, 13) cnn_pipeline_v10_hls_deadlock_detect_unit_10 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_10),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_10),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_10),
        .token_in_vec(token_in_vec_10),
        .dl_detect_in(dl_detect_out),
        .origin(origin[10]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_10),
        .out_chan_dep_data(out_chan_dep_data_10),
        .token_out_vec(token_out_vec_10),
        .dl_detect_out(dl_in_vec[10]));

    assign proc_10_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.p1_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_load_coeff_5123_fu_293.p2_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_load_coeff_5123_fu_293.p2_data_0_blk_n);
    assign proc_10_data_PIPO_blk[0] = 1'b0;
    assign proc_10_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_depthwise_chain_3_4_false_0_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_depthwise_chain_3_4_false_0_U0_U.if_write);
    assign proc_10_TLF_FIFO_blk[0] = 1'b0;
    assign proc_10_input_sync_blk[0] = 1'b0;
    assign proc_10_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_10[0] = dl_detect_out ? proc_dep_vld_vec_10_reg[0] : (proc_10_data_FIFO_blk[0] | proc_10_data_PIPO_blk[0] | proc_10_start_FIFO_blk[0] | proc_10_TLF_FIFO_blk[0] | proc_10_input_sync_blk[0] | proc_10_output_sync_blk[0]);
    assign proc_10_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_chain_3_4_false_0_Pipeline_VITIS_LOOP_772_1_fu_280.input_a_blk_n);
    assign proc_10_data_PIPO_blk[1] = 1'b0;
    assign proc_10_start_FIFO_blk[1] = 1'b0;
    assign proc_10_TLF_FIFO_blk[1] = 1'b0;
    assign proc_10_input_sync_blk[1] = 1'b0;
    assign proc_10_output_sync_blk[1] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_10[1] = dl_detect_out ? proc_dep_vld_vec_10_reg[1] : (proc_10_data_FIFO_blk[1] | proc_10_data_PIPO_blk[1] | proc_10_start_FIFO_blk[1] | proc_10_TLF_FIFO_blk[1] | proc_10_input_sync_blk[1] | proc_10_output_sync_blk[1]);
    assign proc_10_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_chain_3_4_false_0_Pipeline_VITIS_LOOP_772_1_fu_280.q3_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_chain_3_4_false_0_Pipeline_VITIS_LOOP_772_1_fu_280.q3_b_blk_n);
    assign proc_10_data_PIPO_blk[2] = 1'b0;
    assign proc_10_start_FIFO_blk[2] = 1'b0;
    assign proc_10_TLF_FIFO_blk[2] = 1'b0;
    assign proc_10_input_sync_blk[2] = 1'b0;
    assign proc_10_output_sync_blk[2] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_10[2] = dl_detect_out ? proc_dep_vld_vec_10_reg[2] : (proc_10_data_FIFO_blk[2] | proc_10_data_PIPO_blk[2] | proc_10_start_FIFO_blk[2] | proc_10_TLF_FIFO_blk[2] | proc_10_input_sync_blk[2] | proc_10_output_sync_blk[2]);
    assign proc_10_data_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_chain_3_4_false_0_Pipeline_VITIS_LOOP_772_1_fu_280.input_b_blk_n);
    assign proc_10_data_PIPO_blk[3] = 1'b0;
    assign proc_10_start_FIFO_blk[3] = 1'b0;
    assign proc_10_TLF_FIFO_blk[3] = 1'b0;
    assign proc_10_input_sync_blk[3] = 1'b0;
    assign proc_10_output_sync_blk[3] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_10[3] = dl_detect_out ? proc_dep_vld_vec_10_reg[3] : (proc_10_data_FIFO_blk[3] | proc_10_data_PIPO_blk[3] | proc_10_start_FIFO_blk[3] | proc_10_TLF_FIFO_blk[3] | proc_10_input_sync_blk[3] | proc_10_output_sync_blk[3]);
    assign proc_10_data_FIFO_blk[4] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.scale_req_a_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.scale_ret_a_0_blk_n);
    assign proc_10_data_PIPO_blk[4] = 1'b0;
    assign proc_10_start_FIFO_blk[4] = 1'b0;
    assign proc_10_TLF_FIFO_blk[4] = 1'b0;
    assign proc_10_input_sync_blk[4] = 1'b0;
    assign proc_10_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_10[4] = dl_detect_out ? proc_dep_vld_vec_10_reg[4] : (proc_10_data_FIFO_blk[4] | proc_10_data_PIPO_blk[4] | proc_10_start_FIFO_blk[4] | proc_10_TLF_FIFO_blk[4] | proc_10_input_sync_blk[4] | proc_10_output_sync_blk[4]);
    assign proc_10_data_FIFO_blk[5] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.scale_req_b_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.scale_ret_b_0_blk_n);
    assign proc_10_data_PIPO_blk[5] = 1'b0;
    assign proc_10_start_FIFO_blk[5] = 1'b0;
    assign proc_10_TLF_FIFO_blk[5] = 1'b0;
    assign proc_10_input_sync_blk[5] = 1'b0;
    assign proc_10_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_10[5] = dl_detect_out ? proc_dep_vld_vec_10_reg[5] : (proc_10_data_FIFO_blk[5] | proc_10_data_PIPO_blk[5] | proc_10_start_FIFO_blk[5] | proc_10_TLF_FIFO_blk[5] | proc_10_input_sync_blk[5] | proc_10_output_sync_blk[5]);
    assign proc_10_data_FIFO_blk[6] = 1'b0;
    assign proc_10_data_PIPO_blk[6] = 1'b0;
    assign proc_10_start_FIFO_blk[6] = 1'b0;
    assign proc_10_TLF_FIFO_blk[6] = 1'b0;
    assign proc_10_input_sync_blk[6] = 1'b0;
    assign proc_10_output_sync_blk[6] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_10[6] = dl_detect_out ? proc_dep_vld_vec_10_reg[6] : (proc_10_data_FIFO_blk[6] | proc_10_data_PIPO_blk[6] | proc_10_start_FIFO_blk[6] | proc_10_TLF_FIFO_blk[6] | proc_10_input_sync_blk[6] | proc_10_output_sync_blk[6]);
    assign proc_10_data_FIFO_blk[7] = 1'b0;
    assign proc_10_data_PIPO_blk[7] = 1'b0;
    assign proc_10_start_FIFO_blk[7] = 1'b0;
    assign proc_10_TLF_FIFO_blk[7] = 1'b0;
    assign proc_10_input_sync_blk[7] = 1'b0;
    assign proc_10_output_sync_blk[7] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_10[7] = dl_detect_out ? proc_dep_vld_vec_10_reg[7] : (proc_10_data_FIFO_blk[7] | proc_10_data_PIPO_blk[7] | proc_10_start_FIFO_blk[7] | proc_10_TLF_FIFO_blk[7] | proc_10_input_sync_blk[7] | proc_10_output_sync_blk[7]);
    assign proc_10_data_FIFO_blk[8] = 1'b0;
    assign proc_10_data_PIPO_blk[8] = 1'b0;
    assign proc_10_start_FIFO_blk[8] = 1'b0;
    assign proc_10_TLF_FIFO_blk[8] = 1'b0;
    assign proc_10_input_sync_blk[8] = 1'b0;
    assign proc_10_output_sync_blk[8] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_10[8] = dl_detect_out ? proc_dep_vld_vec_10_reg[8] : (proc_10_data_FIFO_blk[8] | proc_10_data_PIPO_blk[8] | proc_10_start_FIFO_blk[8] | proc_10_TLF_FIFO_blk[8] | proc_10_input_sync_blk[8] | proc_10_output_sync_blk[8]);
    assign proc_10_data_FIFO_blk[9] = 1'b0;
    assign proc_10_data_PIPO_blk[9] = 1'b0;
    assign proc_10_start_FIFO_blk[9] = 1'b0;
    assign proc_10_TLF_FIFO_blk[9] = 1'b0;
    assign proc_10_input_sync_blk[9] = 1'b0;
    assign proc_10_output_sync_blk[9] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_10[9] = dl_detect_out ? proc_dep_vld_vec_10_reg[9] : (proc_10_data_FIFO_blk[9] | proc_10_data_PIPO_blk[9] | proc_10_start_FIFO_blk[9] | proc_10_TLF_FIFO_blk[9] | proc_10_input_sync_blk[9] | proc_10_output_sync_blk[9]);
    assign proc_10_data_FIFO_blk[10] = 1'b0;
    assign proc_10_data_PIPO_blk[10] = 1'b0;
    assign proc_10_start_FIFO_blk[10] = 1'b0;
    assign proc_10_TLF_FIFO_blk[10] = 1'b0;
    assign proc_10_input_sync_blk[10] = 1'b0;
    assign proc_10_output_sync_blk[10] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_10[10] = dl_detect_out ? proc_dep_vld_vec_10_reg[10] : (proc_10_data_FIFO_blk[10] | proc_10_data_PIPO_blk[10] | proc_10_start_FIFO_blk[10] | proc_10_TLF_FIFO_blk[10] | proc_10_input_sync_blk[10] | proc_10_output_sync_blk[10]);
    assign proc_10_data_FIFO_blk[11] = 1'b0;
    assign proc_10_data_PIPO_blk[11] = 1'b0;
    assign proc_10_start_FIFO_blk[11] = 1'b0;
    assign proc_10_TLF_FIFO_blk[11] = 1'b0;
    assign proc_10_input_sync_blk[11] = 1'b0;
    assign proc_10_output_sync_blk[11] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_10[11] = dl_detect_out ? proc_dep_vld_vec_10_reg[11] : (proc_10_data_FIFO_blk[11] | proc_10_data_PIPO_blk[11] | proc_10_start_FIFO_blk[11] | proc_10_TLF_FIFO_blk[11] | proc_10_input_sync_blk[11] | proc_10_output_sync_blk[11]);
    assign proc_10_data_FIFO_blk[12] = 1'b0;
    assign proc_10_data_PIPO_blk[12] = 1'b0;
    assign proc_10_start_FIFO_blk[12] = 1'b0;
    assign proc_10_TLF_FIFO_blk[12] = 1'b0;
    assign proc_10_input_sync_blk[12] = 1'b0;
    assign proc_10_output_sync_blk[12] = 1'b0 | (ap_done_reg_4 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_10[12] = dl_detect_out ? proc_dep_vld_vec_10_reg[12] : (proc_10_data_FIFO_blk[12] | proc_10_data_PIPO_blk[12] | proc_10_start_FIFO_blk[12] | proc_10_TLF_FIFO_blk[12] | proc_10_input_sync_blk[12] | proc_10_output_sync_blk[12]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_10_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_10_reg <= proc_dep_vld_vec_10;
        end
    end
    assign in_chan_dep_vld_vec_10[0] = dep_chan_vld_0_10;
    assign in_chan_dep_data_vec_10[38 : 0] = dep_chan_data_0_10;
    assign token_in_vec_10[0] = token_0_10;
    assign in_chan_dep_vld_vec_10[1] = dep_chan_vld_4_10;
    assign in_chan_dep_data_vec_10[77 : 39] = dep_chan_data_4_10;
    assign token_in_vec_10[1] = token_4_10;
    assign in_chan_dep_vld_vec_10[2] = dep_chan_vld_5_10;
    assign in_chan_dep_data_vec_10[116 : 78] = dep_chan_data_5_10;
    assign token_in_vec_10[2] = token_5_10;
    assign in_chan_dep_vld_vec_10[3] = dep_chan_vld_6_10;
    assign in_chan_dep_data_vec_10[155 : 117] = dep_chan_data_6_10;
    assign token_in_vec_10[3] = token_6_10;
    assign in_chan_dep_vld_vec_10[4] = dep_chan_vld_7_10;
    assign in_chan_dep_data_vec_10[194 : 156] = dep_chan_data_7_10;
    assign token_in_vec_10[4] = token_7_10;
    assign in_chan_dep_vld_vec_10[5] = dep_chan_vld_8_10;
    assign in_chan_dep_data_vec_10[233 : 195] = dep_chan_data_8_10;
    assign token_in_vec_10[5] = token_8_10;
    assign in_chan_dep_vld_vec_10[6] = dep_chan_vld_9_10;
    assign in_chan_dep_data_vec_10[272 : 234] = dep_chan_data_9_10;
    assign token_in_vec_10[6] = token_9_10;
    assign in_chan_dep_vld_vec_10[7] = dep_chan_vld_15_10;
    assign in_chan_dep_data_vec_10[311 : 273] = dep_chan_data_15_10;
    assign token_in_vec_10[7] = token_15_10;
    assign in_chan_dep_vld_vec_10[8] = dep_chan_vld_20_10;
    assign in_chan_dep_data_vec_10[350 : 312] = dep_chan_data_20_10;
    assign token_in_vec_10[8] = token_20_10;
    assign in_chan_dep_vld_vec_10[9] = dep_chan_vld_21_10;
    assign in_chan_dep_data_vec_10[389 : 351] = dep_chan_data_21_10;
    assign token_in_vec_10[9] = token_21_10;
    assign in_chan_dep_vld_vec_10[10] = dep_chan_vld_23_10;
    assign in_chan_dep_data_vec_10[428 : 390] = dep_chan_data_23_10;
    assign token_in_vec_10[10] = token_23_10;
    assign in_chan_dep_vld_vec_10[11] = dep_chan_vld_31_10;
    assign in_chan_dep_data_vec_10[467 : 429] = dep_chan_data_31_10;
    assign token_in_vec_10[11] = token_31_10;
    assign in_chan_dep_vld_vec_10[12] = dep_chan_vld_38_10;
    assign in_chan_dep_data_vec_10[506 : 468] = dep_chan_data_38_10;
    assign token_in_vec_10[12] = token_38_10;
    assign dep_chan_vld_10_0 = out_chan_dep_vld_vec_10[0];
    assign dep_chan_data_10_0 = out_chan_dep_data_10;
    assign token_10_0 = token_out_vec_10[0];
    assign dep_chan_vld_10_8 = out_chan_dep_vld_vec_10[1];
    assign dep_chan_data_10_8 = out_chan_dep_data_10;
    assign token_10_8 = token_out_vec_10[1];
    assign dep_chan_vld_10_15 = out_chan_dep_vld_vec_10[2];
    assign dep_chan_data_10_15 = out_chan_dep_data_10;
    assign token_10_15 = token_out_vec_10[2];
    assign dep_chan_vld_10_9 = out_chan_dep_vld_vec_10[3];
    assign dep_chan_data_10_9 = out_chan_dep_data_10;
    assign token_10_9 = token_out_vec_10[3];
    assign dep_chan_vld_10_6 = out_chan_dep_vld_vec_10[4];
    assign dep_chan_data_10_6 = out_chan_dep_data_10;
    assign token_10_6 = token_out_vec_10[4];
    assign dep_chan_vld_10_7 = out_chan_dep_vld_vec_10[5];
    assign dep_chan_data_10_7 = out_chan_dep_data_10;
    assign token_10_7 = token_out_vec_10[5];
    assign dep_chan_vld_10_4 = out_chan_dep_vld_vec_10[6];
    assign dep_chan_data_10_4 = out_chan_dep_data_10;
    assign token_10_4 = token_out_vec_10[6];
    assign dep_chan_vld_10_5 = out_chan_dep_vld_vec_10[7];
    assign dep_chan_data_10_5 = out_chan_dep_data_10;
    assign token_10_5 = token_out_vec_10[7];
    assign dep_chan_vld_10_20 = out_chan_dep_vld_vec_10[8];
    assign dep_chan_data_10_20 = out_chan_dep_data_10;
    assign token_10_20 = token_out_vec_10[8];
    assign dep_chan_vld_10_21 = out_chan_dep_vld_vec_10[9];
    assign dep_chan_data_10_21 = out_chan_dep_data_10;
    assign token_10_21 = token_out_vec_10[9];
    assign dep_chan_vld_10_23 = out_chan_dep_vld_vec_10[10];
    assign dep_chan_data_10_23 = out_chan_dep_data_10;
    assign token_10_23 = token_out_vec_10[10];
    assign dep_chan_vld_10_31 = out_chan_dep_vld_vec_10[11];
    assign dep_chan_data_10_31 = out_chan_dep_data_10;
    assign token_10_31 = token_out_vec_10[11];
    assign dep_chan_vld_10_38 = out_chan_dep_vld_vec_10[12];
    assign dep_chan_data_10_38 = out_chan_dep_data_10;
    assign token_10_38 = token_out_vec_10[12];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 11, 3, 3) cnn_pipeline_v10_hls_deadlock_detect_unit_11 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_11),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_11),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_11),
        .token_in_vec(token_in_vec_11),
        .dl_detect_in(dl_detect_out),
        .origin(origin[11]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_11),
        .out_chan_dep_data(out_chan_dep_data_11),
        .token_out_vec(token_out_vec_11),
        .dl_detect_out(dl_in_vec[11]));

    assign proc_11_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.grp_p_anonymous_namespace_depthwise_compute_Pipeline_VITIS_LOOP_600_27_1_fu_449.raw_a_blk_n);
    assign proc_11_data_PIPO_blk[0] = 1'b0;
    assign proc_11_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.start_for_p_anonymous_namespace_depthwise_emit_0_false_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.real_start & (trans_in_cnt_3 == trans_out_cnt_3) & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.start_for_p_anonymous_namespace_depthwise_emit_0_false_U0_U.if_read);
    assign proc_11_TLF_FIFO_blk[0] = 1'b0;
    assign proc_11_input_sync_blk[0] = 1'b0;
    assign proc_11_output_sync_blk[0] = 1'b0 | (ap_done_reg_11 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_done);
    assign proc_dep_vld_vec_11[0] = dl_detect_out ? proc_dep_vld_vec_11_reg[0] : (proc_11_data_FIFO_blk[0] | proc_11_data_PIPO_blk[0] | proc_11_start_FIFO_blk[0] | proc_11_TLF_FIFO_blk[0] | proc_11_input_sync_blk[0] | proc_11_output_sync_blk[0]);
    assign proc_11_data_FIFO_blk[1] = 1'b0;
    assign proc_11_data_PIPO_blk[1] = 1'b0;
    assign proc_11_start_FIFO_blk[1] = 1'b0;
    assign proc_11_TLF_FIFO_blk[1] = 1'b0;
    assign proc_11_input_sync_blk[1] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.ap_sync_p_anonymous_namespace_depthwise_compute_0_3_4_false_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.ap_sync_p_anonymous_namespace_depthwise_compute_1_3_4_false_U0_ap_ready);
    assign proc_11_output_sync_blk[1] = 1'b0 | (ap_done_reg_11 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_done);
    assign proc_dep_vld_vec_11[1] = dl_detect_out ? proc_dep_vld_vec_11_reg[1] : (proc_11_data_FIFO_blk[1] | proc_11_data_PIPO_blk[1] | proc_11_start_FIFO_blk[1] | proc_11_TLF_FIFO_blk[1] | proc_11_input_sync_blk[1] | proc_11_output_sync_blk[1]);
    assign proc_11_data_FIFO_blk[2] = 1'b0;
    assign proc_11_data_PIPO_blk[2] = 1'b0;
    assign proc_11_start_FIFO_blk[2] = 1'b0;
    assign proc_11_TLF_FIFO_blk[2] = 1'b0;
    assign proc_11_input_sync_blk[2] = 1'b0;
    assign proc_11_output_sync_blk[2] = 1'b0 | (ap_done_reg_11 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_done);
    assign proc_dep_vld_vec_11[2] = dl_detect_out ? proc_dep_vld_vec_11_reg[2] : (proc_11_data_FIFO_blk[2] | proc_11_data_PIPO_blk[2] | proc_11_start_FIFO_blk[2] | proc_11_TLF_FIFO_blk[2] | proc_11_input_sync_blk[2] | proc_11_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_11_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_11_reg <= proc_dep_vld_vec_11;
        end
    end
    assign in_chan_dep_vld_vec_11[0] = dep_chan_vld_12_11;
    assign in_chan_dep_data_vec_11[38 : 0] = dep_chan_data_12_11;
    assign token_in_vec_11[0] = token_12_11;
    assign in_chan_dep_vld_vec_11[1] = dep_chan_vld_13_11;
    assign in_chan_dep_data_vec_11[77 : 39] = dep_chan_data_13_11;
    assign token_in_vec_11[1] = token_13_11;
    assign in_chan_dep_vld_vec_11[2] = dep_chan_vld_14_11;
    assign in_chan_dep_data_vec_11[116 : 78] = dep_chan_data_14_11;
    assign token_in_vec_11[2] = token_14_11;
    assign dep_chan_vld_11_12 = out_chan_dep_vld_vec_11[0];
    assign dep_chan_data_11_12 = out_chan_dep_data_11;
    assign token_11_12 = token_out_vec_11[0];
    assign dep_chan_vld_11_13 = out_chan_dep_vld_vec_11[1];
    assign dep_chan_data_11_13 = out_chan_dep_data_11;
    assign token_11_13 = token_out_vec_11[1];
    assign dep_chan_vld_11_14 = out_chan_dep_vld_vec_11[2];
    assign dep_chan_data_11_14 = out_chan_dep_data_11;
    assign token_11_14 = token_out_vec_11[2];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 12, 3, 3) cnn_pipeline_v10_hls_deadlock_detect_unit_12 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_12),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_12),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_12),
        .token_in_vec(token_in_vec_12),
        .dl_detect_in(dl_detect_out),
        .origin(origin[12]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_12),
        .out_chan_dep_data(out_chan_dep_data_12),
        .token_out_vec(token_out_vec_12),
        .dl_detect_out(dl_in_vec[12]));

    assign proc_12_data_FIFO_blk[0] = 1'b0;
    assign proc_12_data_PIPO_blk[0] = 1'b0;
    assign proc_12_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.start_for_p_anonymous_namespace_depthwise_emit_0_false_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.start_for_p_anonymous_namespace_depthwise_emit_0_false_U0_U.if_write);
    assign proc_12_TLF_FIFO_blk[0] = 1'b0;
    assign proc_12_input_sync_blk[0] = 1'b0;
    assign proc_12_output_sync_blk[0] = 1'b0 | (ap_done_reg_12 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_done);
    assign proc_dep_vld_vec_12[0] = dl_detect_out ? proc_dep_vld_vec_12_reg[0] : (proc_12_data_FIFO_blk[0] | proc_12_data_PIPO_blk[0] | proc_12_start_FIFO_blk[0] | proc_12_TLF_FIFO_blk[0] | proc_12_input_sync_blk[0] | proc_12_output_sync_blk[0]);
    assign proc_12_data_FIFO_blk[1] = 1'b0;
    assign proc_12_data_PIPO_blk[1] = 1'b0;
    assign proc_12_start_FIFO_blk[1] = 1'b0;
    assign proc_12_TLF_FIFO_blk[1] = 1'b0;
    assign proc_12_input_sync_blk[1] = 1'b0;
    assign proc_12_output_sync_blk[1] = 1'b0 | (ap_done_reg_12 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_done);
    assign proc_dep_vld_vec_12[1] = dl_detect_out ? proc_dep_vld_vec_12_reg[1] : (proc_12_data_FIFO_blk[1] | proc_12_data_PIPO_blk[1] | proc_12_start_FIFO_blk[1] | proc_12_TLF_FIFO_blk[1] | proc_12_input_sync_blk[1] | proc_12_output_sync_blk[1]);
    assign proc_12_data_FIFO_blk[2] = 1'b0;
    assign proc_12_data_PIPO_blk[2] = 1'b0;
    assign proc_12_start_FIFO_blk[2] = 1'b0;
    assign proc_12_TLF_FIFO_blk[2] = 1'b0;
    assign proc_12_input_sync_blk[2] = 1'b0;
    assign proc_12_output_sync_blk[2] = 1'b0 | (ap_done_reg_12 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_done);
    assign proc_dep_vld_vec_12[2] = dl_detect_out ? proc_dep_vld_vec_12_reg[2] : (proc_12_data_FIFO_blk[2] | proc_12_data_PIPO_blk[2] | proc_12_start_FIFO_blk[2] | proc_12_TLF_FIFO_blk[2] | proc_12_input_sync_blk[2] | proc_12_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_12_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_12_reg <= proc_dep_vld_vec_12;
        end
    end
    assign in_chan_dep_vld_vec_12[0] = dep_chan_vld_11_12;
    assign in_chan_dep_data_vec_12[38 : 0] = dep_chan_data_11_12;
    assign token_in_vec_12[0] = token_11_12;
    assign in_chan_dep_vld_vec_12[1] = dep_chan_vld_13_12;
    assign in_chan_dep_data_vec_12[77 : 39] = dep_chan_data_13_12;
    assign token_in_vec_12[1] = token_13_12;
    assign in_chan_dep_vld_vec_12[2] = dep_chan_vld_14_12;
    assign in_chan_dep_data_vec_12[116 : 78] = dep_chan_data_14_12;
    assign token_in_vec_12[2] = token_14_12;
    assign dep_chan_vld_12_11 = out_chan_dep_vld_vec_12[0];
    assign dep_chan_data_12_11 = out_chan_dep_data_12;
    assign token_12_11 = token_out_vec_12[0];
    assign dep_chan_vld_12_13 = out_chan_dep_vld_vec_12[1];
    assign dep_chan_data_12_13 = out_chan_dep_data_12;
    assign token_12_13 = token_out_vec_12[1];
    assign dep_chan_vld_12_14 = out_chan_dep_vld_vec_12[2];
    assign dep_chan_data_12_14 = out_chan_dep_data_12;
    assign token_12_14 = token_out_vec_12[2];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 13, 3, 3) cnn_pipeline_v10_hls_deadlock_detect_unit_13 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_13),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_13),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_13),
        .token_in_vec(token_in_vec_13),
        .dl_detect_in(dl_detect_out),
        .origin(origin[13]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_13),
        .out_chan_dep_data(out_chan_dep_data_13),
        .token_out_vec(token_out_vec_13),
        .dl_detect_out(dl_in_vec[13]));

    assign proc_13_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.grp_p_anonymous_namespace_depthwise_compute_Pipeline_VITIS_LOOP_600_27_fu_455.raw_b_blk_n);
    assign proc_13_data_PIPO_blk[0] = 1'b0;
    assign proc_13_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.start_for_p_anonymous_namespace_depthwise_emit_1_false_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.real_start & (trans_in_cnt_4 == trans_out_cnt_4) & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.start_for_p_anonymous_namespace_depthwise_emit_1_false_U0_U.if_read);
    assign proc_13_TLF_FIFO_blk[0] = 1'b0;
    assign proc_13_input_sync_blk[0] = 1'b0;
    assign proc_13_output_sync_blk[0] = 1'b0 | (ap_done_reg_13 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_done);
    assign proc_dep_vld_vec_13[0] = dl_detect_out ? proc_dep_vld_vec_13_reg[0] : (proc_13_data_FIFO_blk[0] | proc_13_data_PIPO_blk[0] | proc_13_start_FIFO_blk[0] | proc_13_TLF_FIFO_blk[0] | proc_13_input_sync_blk[0] | proc_13_output_sync_blk[0]);
    assign proc_13_data_FIFO_blk[1] = 1'b0;
    assign proc_13_data_PIPO_blk[1] = 1'b0;
    assign proc_13_start_FIFO_blk[1] = 1'b0;
    assign proc_13_TLF_FIFO_blk[1] = 1'b0;
    assign proc_13_input_sync_blk[1] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.ap_sync_p_anonymous_namespace_depthwise_compute_1_3_4_false_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.ap_sync_p_anonymous_namespace_depthwise_compute_0_3_4_false_U0_ap_ready);
    assign proc_13_output_sync_blk[1] = 1'b0 | (ap_done_reg_13 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_done);
    assign proc_dep_vld_vec_13[1] = dl_detect_out ? proc_dep_vld_vec_13_reg[1] : (proc_13_data_FIFO_blk[1] | proc_13_data_PIPO_blk[1] | proc_13_start_FIFO_blk[1] | proc_13_TLF_FIFO_blk[1] | proc_13_input_sync_blk[1] | proc_13_output_sync_blk[1]);
    assign proc_13_data_FIFO_blk[2] = 1'b0;
    assign proc_13_data_PIPO_blk[2] = 1'b0;
    assign proc_13_start_FIFO_blk[2] = 1'b0;
    assign proc_13_TLF_FIFO_blk[2] = 1'b0;
    assign proc_13_input_sync_blk[2] = 1'b0;
    assign proc_13_output_sync_blk[2] = 1'b0 | (ap_done_reg_13 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_done);
    assign proc_dep_vld_vec_13[2] = dl_detect_out ? proc_dep_vld_vec_13_reg[2] : (proc_13_data_FIFO_blk[2] | proc_13_data_PIPO_blk[2] | proc_13_start_FIFO_blk[2] | proc_13_TLF_FIFO_blk[2] | proc_13_input_sync_blk[2] | proc_13_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_13_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_13_reg <= proc_dep_vld_vec_13;
        end
    end
    assign in_chan_dep_vld_vec_13[0] = dep_chan_vld_11_13;
    assign in_chan_dep_data_vec_13[38 : 0] = dep_chan_data_11_13;
    assign token_in_vec_13[0] = token_11_13;
    assign in_chan_dep_vld_vec_13[1] = dep_chan_vld_12_13;
    assign in_chan_dep_data_vec_13[77 : 39] = dep_chan_data_12_13;
    assign token_in_vec_13[1] = token_12_13;
    assign in_chan_dep_vld_vec_13[2] = dep_chan_vld_14_13;
    assign in_chan_dep_data_vec_13[116 : 78] = dep_chan_data_14_13;
    assign token_in_vec_13[2] = token_14_13;
    assign dep_chan_vld_13_14 = out_chan_dep_vld_vec_13[0];
    assign dep_chan_data_13_14 = out_chan_dep_data_13;
    assign token_13_14 = token_out_vec_13[0];
    assign dep_chan_vld_13_11 = out_chan_dep_vld_vec_13[1];
    assign dep_chan_data_13_11 = out_chan_dep_data_13;
    assign token_13_11 = token_out_vec_13[1];
    assign dep_chan_vld_13_12 = out_chan_dep_vld_vec_13[2];
    assign dep_chan_data_13_12 = out_chan_dep_data_13;
    assign token_13_12 = token_out_vec_13[2];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 14, 3, 3) cnn_pipeline_v10_hls_deadlock_detect_unit_14 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_14),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_14),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_14),
        .token_in_vec(token_in_vec_14),
        .dl_detect_in(dl_detect_out),
        .origin(origin[14]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_14),
        .out_chan_dep_data(out_chan_dep_data_14),
        .token_out_vec(token_out_vec_14),
        .dl_detect_out(dl_in_vec[14]));

    assign proc_14_data_FIFO_blk[0] = 1'b0;
    assign proc_14_data_PIPO_blk[0] = 1'b0;
    assign proc_14_start_FIFO_blk[0] = 1'b0;
    assign proc_14_TLF_FIFO_blk[0] = 1'b0;
    assign proc_14_input_sync_blk[0] = 1'b0;
    assign proc_14_output_sync_blk[0] = 1'b0 | (ap_done_reg_14 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_0_3_4_false_U0.ap_done);
    assign proc_dep_vld_vec_14[0] = dl_detect_out ? proc_dep_vld_vec_14_reg[0] : (proc_14_data_FIFO_blk[0] | proc_14_data_PIPO_blk[0] | proc_14_start_FIFO_blk[0] | proc_14_TLF_FIFO_blk[0] | proc_14_input_sync_blk[0] | proc_14_output_sync_blk[0]);
    assign proc_14_data_FIFO_blk[1] = 1'b0;
    assign proc_14_data_PIPO_blk[1] = 1'b0;
    assign proc_14_start_FIFO_blk[1] = 1'b0;
    assign proc_14_TLF_FIFO_blk[1] = 1'b0;
    assign proc_14_input_sync_blk[1] = 1'b0;
    assign proc_14_output_sync_blk[1] = 1'b0 | (ap_done_reg_14 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_0_false_U0.ap_done);
    assign proc_dep_vld_vec_14[1] = dl_detect_out ? proc_dep_vld_vec_14_reg[1] : (proc_14_data_FIFO_blk[1] | proc_14_data_PIPO_blk[1] | proc_14_start_FIFO_blk[1] | proc_14_TLF_FIFO_blk[1] | proc_14_input_sync_blk[1] | proc_14_output_sync_blk[1]);
    assign proc_14_data_FIFO_blk[2] = 1'b0;
    assign proc_14_data_PIPO_blk[2] = 1'b0;
    assign proc_14_start_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.start_for_p_anonymous_namespace_depthwise_emit_1_false_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.start_for_p_anonymous_namespace_depthwise_emit_1_false_U0_U.if_write);
    assign proc_14_TLF_FIFO_blk[2] = 1'b0;
    assign proc_14_input_sync_blk[2] = 1'b0;
    assign proc_14_output_sync_blk[2] = 1'b0 | (ap_done_reg_14 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_emit_1_false_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.grp_p_anonymous_namespace_depthwise_dual_3_4_false_s_fu_321.p_anonymous_namespace_depthwise_compute_1_3_4_false_U0.ap_done);
    assign proc_dep_vld_vec_14[2] = dl_detect_out ? proc_dep_vld_vec_14_reg[2] : (proc_14_data_FIFO_blk[2] | proc_14_data_PIPO_blk[2] | proc_14_start_FIFO_blk[2] | proc_14_TLF_FIFO_blk[2] | proc_14_input_sync_blk[2] | proc_14_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_14_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_14_reg <= proc_dep_vld_vec_14;
        end
    end
    assign in_chan_dep_vld_vec_14[0] = dep_chan_vld_11_14;
    assign in_chan_dep_data_vec_14[38 : 0] = dep_chan_data_11_14;
    assign token_in_vec_14[0] = token_11_14;
    assign in_chan_dep_vld_vec_14[1] = dep_chan_vld_12_14;
    assign in_chan_dep_data_vec_14[77 : 39] = dep_chan_data_12_14;
    assign token_in_vec_14[1] = token_12_14;
    assign in_chan_dep_vld_vec_14[2] = dep_chan_vld_13_14;
    assign in_chan_dep_data_vec_14[116 : 78] = dep_chan_data_13_14;
    assign token_in_vec_14[2] = token_13_14;
    assign dep_chan_vld_14_11 = out_chan_dep_vld_vec_14[0];
    assign dep_chan_data_14_11 = out_chan_dep_data_14;
    assign token_14_11 = token_out_vec_14[0];
    assign dep_chan_vld_14_12 = out_chan_dep_vld_vec_14[1];
    assign dep_chan_data_14_12 = out_chan_dep_data_14;
    assign token_14_12 = token_out_vec_14[1];
    assign dep_chan_vld_14_13 = out_chan_dep_vld_vec_14[2];
    assign dep_chan_data_14_13 = out_chan_dep_data_14;
    assign token_14_13 = token_out_vec_14[2];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 15, 13, 13) cnn_pipeline_v10_hls_deadlock_detect_unit_15 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_15),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_15),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_15),
        .token_in_vec(token_in_vec_15),
        .dl_detect_in(dl_detect_out),
        .origin(origin[15]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_15),
        .out_chan_dep_data(out_chan_dep_data_15),
        .token_out_vec(token_out_vec_15),
        .dl_detect_out(dl_in_vec[15]));

    assign proc_15_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.p1_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_load_dw7_i16_parity_fu_288.p1_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_load_dw7_i16_parity_fu_288.grp_p_anonymous_namespace_load_dw7_i16_parity_Pipeline_VITIS_LOOP_197_2_VITIS_LOOP_19_fu_129.p1_data_1_blk_n);
    assign proc_15_data_PIPO_blk[0] = 1'b0;
    assign proc_15_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_depthwise_chain_7_16_true_1_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_depthwise_chain_7_16_true_1_U0_U.if_write);
    assign proc_15_TLF_FIFO_blk[0] = 1'b0;
    assign proc_15_input_sync_blk[0] = 1'b0;
    assign proc_15_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_15[0] = dl_detect_out ? proc_dep_vld_vec_15_reg[0] : (proc_15_data_FIFO_blk[0] | proc_15_data_PIPO_blk[0] | proc_15_start_FIFO_blk[0] | proc_15_TLF_FIFO_blk[0] | proc_15_input_sync_blk[0] | proc_15_output_sync_blk[0]);
    assign proc_15_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_chain_7_16_true_1_Pipeline_VITIS_LOOP_772_1_fu_276.q3_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_chain_7_16_true_1_Pipeline_VITIS_LOOP_772_1_fu_276.q3_b_blk_n);
    assign proc_15_data_PIPO_blk[1] = 1'b0;
    assign proc_15_start_FIFO_blk[1] = 1'b0;
    assign proc_15_TLF_FIFO_blk[1] = 1'b0;
    assign proc_15_input_sync_blk[1] = 1'b0;
    assign proc_15_output_sync_blk[1] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_15[1] = dl_detect_out ? proc_dep_vld_vec_15_reg[1] : (proc_15_data_FIFO_blk[1] | proc_15_data_PIPO_blk[1] | proc_15_start_FIFO_blk[1] | proc_15_TLF_FIFO_blk[1] | proc_15_input_sync_blk[1] | proc_15_output_sync_blk[1]);
    assign proc_15_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_chain_7_16_true_1_Pipeline_VITIS_LOOP_772_1_fu_276.q7_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_chain_7_16_true_1_Pipeline_VITIS_LOOP_772_1_fu_276.q7_b_blk_n);
    assign proc_15_data_PIPO_blk[2] = 1'b0;
    assign proc_15_start_FIFO_blk[2] = 1'b0;
    assign proc_15_TLF_FIFO_blk[2] = 1'b0;
    assign proc_15_input_sync_blk[2] = 1'b0;
    assign proc_15_output_sync_blk[2] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_15[2] = dl_detect_out ? proc_dep_vld_vec_15_reg[2] : (proc_15_data_FIFO_blk[2] | proc_15_data_PIPO_blk[2] | proc_15_start_FIFO_blk[2] | proc_15_TLF_FIFO_blk[2] | proc_15_input_sync_blk[2] | proc_15_output_sync_blk[2]);
    assign proc_15_data_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.res_a_blk_n);
    assign proc_15_data_PIPO_blk[3] = 1'b0;
    assign proc_15_start_FIFO_blk[3] = 1'b0;
    assign proc_15_TLF_FIFO_blk[3] = 1'b0;
    assign proc_15_input_sync_blk[3] = 1'b0;
    assign proc_15_output_sync_blk[3] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_15[3] = dl_detect_out ? proc_dep_vld_vec_15_reg[3] : (proc_15_data_FIFO_blk[3] | proc_15_data_PIPO_blk[3] | proc_15_start_FIFO_blk[3] | proc_15_TLF_FIFO_blk[3] | proc_15_input_sync_blk[3] | proc_15_output_sync_blk[3]);
    assign proc_15_data_FIFO_blk[4] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.res_b_blk_n);
    assign proc_15_data_PIPO_blk[4] = 1'b0;
    assign proc_15_start_FIFO_blk[4] = 1'b0;
    assign proc_15_TLF_FIFO_blk[4] = 1'b0;
    assign proc_15_input_sync_blk[4] = 1'b0;
    assign proc_15_output_sync_blk[4] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_15[4] = dl_detect_out ? proc_dep_vld_vec_15_reg[4] : (proc_15_data_FIFO_blk[4] | proc_15_data_PIPO_blk[4] | proc_15_start_FIFO_blk[4] | proc_15_TLF_FIFO_blk[4] | proc_15_input_sync_blk[4] | proc_15_output_sync_blk[4]);
    assign proc_15_data_FIFO_blk[5] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.scale_req_a_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.scale_ret_a_1_blk_n);
    assign proc_15_data_PIPO_blk[5] = 1'b0;
    assign proc_15_start_FIFO_blk[5] = 1'b0;
    assign proc_15_TLF_FIFO_blk[5] = 1'b0;
    assign proc_15_input_sync_blk[5] = 1'b0;
    assign proc_15_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_15[5] = dl_detect_out ? proc_dep_vld_vec_15_reg[5] : (proc_15_data_FIFO_blk[5] | proc_15_data_PIPO_blk[5] | proc_15_start_FIFO_blk[5] | proc_15_TLF_FIFO_blk[5] | proc_15_input_sync_blk[5] | proc_15_output_sync_blk[5]);
    assign proc_15_data_FIFO_blk[6] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.scale_req_b_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.scale_ret_b_1_blk_n);
    assign proc_15_data_PIPO_blk[6] = 1'b0;
    assign proc_15_start_FIFO_blk[6] = 1'b0;
    assign proc_15_TLF_FIFO_blk[6] = 1'b0;
    assign proc_15_input_sync_blk[6] = 1'b0;
    assign proc_15_output_sync_blk[6] = 1'b0;
    assign proc_dep_vld_vec_15[6] = dl_detect_out ? proc_dep_vld_vec_15_reg[6] : (proc_15_data_FIFO_blk[6] | proc_15_data_PIPO_blk[6] | proc_15_start_FIFO_blk[6] | proc_15_TLF_FIFO_blk[6] | proc_15_input_sync_blk[6] | proc_15_output_sync_blk[6]);
    assign proc_15_data_FIFO_blk[7] = 1'b0;
    assign proc_15_data_PIPO_blk[7] = 1'b0;
    assign proc_15_start_FIFO_blk[7] = 1'b0;
    assign proc_15_TLF_FIFO_blk[7] = 1'b0;
    assign proc_15_input_sync_blk[7] = 1'b0;
    assign proc_15_output_sync_blk[7] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_15[7] = dl_detect_out ? proc_dep_vld_vec_15_reg[7] : (proc_15_data_FIFO_blk[7] | proc_15_data_PIPO_blk[7] | proc_15_start_FIFO_blk[7] | proc_15_TLF_FIFO_blk[7] | proc_15_input_sync_blk[7] | proc_15_output_sync_blk[7]);
    assign proc_15_data_FIFO_blk[8] = 1'b0;
    assign proc_15_data_PIPO_blk[8] = 1'b0;
    assign proc_15_start_FIFO_blk[8] = 1'b0;
    assign proc_15_TLF_FIFO_blk[8] = 1'b0;
    assign proc_15_input_sync_blk[8] = 1'b0;
    assign proc_15_output_sync_blk[8] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_15[8] = dl_detect_out ? proc_dep_vld_vec_15_reg[8] : (proc_15_data_FIFO_blk[8] | proc_15_data_PIPO_blk[8] | proc_15_start_FIFO_blk[8] | proc_15_TLF_FIFO_blk[8] | proc_15_input_sync_blk[8] | proc_15_output_sync_blk[8]);
    assign proc_15_data_FIFO_blk[9] = 1'b0;
    assign proc_15_data_PIPO_blk[9] = 1'b0;
    assign proc_15_start_FIFO_blk[9] = 1'b0;
    assign proc_15_TLF_FIFO_blk[9] = 1'b0;
    assign proc_15_input_sync_blk[9] = 1'b0;
    assign proc_15_output_sync_blk[9] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_15[9] = dl_detect_out ? proc_dep_vld_vec_15_reg[9] : (proc_15_data_FIFO_blk[9] | proc_15_data_PIPO_blk[9] | proc_15_start_FIFO_blk[9] | proc_15_TLF_FIFO_blk[9] | proc_15_input_sync_blk[9] | proc_15_output_sync_blk[9]);
    assign proc_15_data_FIFO_blk[10] = 1'b0;
    assign proc_15_data_PIPO_blk[10] = 1'b0;
    assign proc_15_start_FIFO_blk[10] = 1'b0;
    assign proc_15_TLF_FIFO_blk[10] = 1'b0;
    assign proc_15_input_sync_blk[10] = 1'b0;
    assign proc_15_output_sync_blk[10] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_15[10] = dl_detect_out ? proc_dep_vld_vec_15_reg[10] : (proc_15_data_FIFO_blk[10] | proc_15_data_PIPO_blk[10] | proc_15_start_FIFO_blk[10] | proc_15_TLF_FIFO_blk[10] | proc_15_input_sync_blk[10] | proc_15_output_sync_blk[10]);
    assign proc_15_data_FIFO_blk[11] = 1'b0;
    assign proc_15_data_PIPO_blk[11] = 1'b0;
    assign proc_15_start_FIFO_blk[11] = 1'b0;
    assign proc_15_TLF_FIFO_blk[11] = 1'b0;
    assign proc_15_input_sync_blk[11] = 1'b0;
    assign proc_15_output_sync_blk[11] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_15[11] = dl_detect_out ? proc_dep_vld_vec_15_reg[11] : (proc_15_data_FIFO_blk[11] | proc_15_data_PIPO_blk[11] | proc_15_start_FIFO_blk[11] | proc_15_TLF_FIFO_blk[11] | proc_15_input_sync_blk[11] | proc_15_output_sync_blk[11]);
    assign proc_15_data_FIFO_blk[12] = 1'b0;
    assign proc_15_data_PIPO_blk[12] = 1'b0;
    assign proc_15_start_FIFO_blk[12] = 1'b0;
    assign proc_15_TLF_FIFO_blk[12] = 1'b0;
    assign proc_15_input_sync_blk[12] = 1'b0;
    assign proc_15_output_sync_blk[12] = 1'b0 | (ap_done_reg_5 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_15[12] = dl_detect_out ? proc_dep_vld_vec_15_reg[12] : (proc_15_data_FIFO_blk[12] | proc_15_data_PIPO_blk[12] | proc_15_start_FIFO_blk[12] | proc_15_TLF_FIFO_blk[12] | proc_15_input_sync_blk[12] | proc_15_output_sync_blk[12]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_15_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_15_reg <= proc_dep_vld_vec_15;
        end
    end
    assign in_chan_dep_vld_vec_15[0] = dep_chan_vld_0_15;
    assign in_chan_dep_data_vec_15[38 : 0] = dep_chan_data_0_15;
    assign token_in_vec_15[0] = token_0_15;
    assign in_chan_dep_vld_vec_15[1] = dep_chan_vld_4_15;
    assign in_chan_dep_data_vec_15[77 : 39] = dep_chan_data_4_15;
    assign token_in_vec_15[1] = token_4_15;
    assign in_chan_dep_vld_vec_15[2] = dep_chan_vld_5_15;
    assign in_chan_dep_data_vec_15[116 : 78] = dep_chan_data_5_15;
    assign token_in_vec_15[2] = token_5_15;
    assign in_chan_dep_vld_vec_15[3] = dep_chan_vld_6_15;
    assign in_chan_dep_data_vec_15[155 : 117] = dep_chan_data_6_15;
    assign token_in_vec_15[3] = token_6_15;
    assign in_chan_dep_vld_vec_15[4] = dep_chan_vld_7_15;
    assign in_chan_dep_data_vec_15[194 : 156] = dep_chan_data_7_15;
    assign token_in_vec_15[4] = token_7_15;
    assign in_chan_dep_vld_vec_15[5] = dep_chan_vld_8_15;
    assign in_chan_dep_data_vec_15[233 : 195] = dep_chan_data_8_15;
    assign token_in_vec_15[5] = token_8_15;
    assign in_chan_dep_vld_vec_15[6] = dep_chan_vld_9_15;
    assign in_chan_dep_data_vec_15[272 : 234] = dep_chan_data_9_15;
    assign token_in_vec_15[6] = token_9_15;
    assign in_chan_dep_vld_vec_15[7] = dep_chan_vld_10_15;
    assign in_chan_dep_data_vec_15[311 : 273] = dep_chan_data_10_15;
    assign token_in_vec_15[7] = token_10_15;
    assign in_chan_dep_vld_vec_15[8] = dep_chan_vld_20_15;
    assign in_chan_dep_data_vec_15[350 : 312] = dep_chan_data_20_15;
    assign token_in_vec_15[8] = token_20_15;
    assign in_chan_dep_vld_vec_15[9] = dep_chan_vld_21_15;
    assign in_chan_dep_data_vec_15[389 : 351] = dep_chan_data_21_15;
    assign token_in_vec_15[9] = token_21_15;
    assign in_chan_dep_vld_vec_15[10] = dep_chan_vld_23_15;
    assign in_chan_dep_data_vec_15[428 : 390] = dep_chan_data_23_15;
    assign token_in_vec_15[10] = token_23_15;
    assign in_chan_dep_vld_vec_15[11] = dep_chan_vld_31_15;
    assign in_chan_dep_data_vec_15[467 : 429] = dep_chan_data_31_15;
    assign token_in_vec_15[11] = token_31_15;
    assign in_chan_dep_vld_vec_15[12] = dep_chan_vld_38_15;
    assign in_chan_dep_data_vec_15[506 : 468] = dep_chan_data_38_15;
    assign token_in_vec_15[12] = token_38_15;
    assign dep_chan_vld_15_0 = out_chan_dep_vld_vec_15[0];
    assign dep_chan_data_15_0 = out_chan_dep_data_15;
    assign token_15_0 = token_out_vec_15[0];
    assign dep_chan_vld_15_10 = out_chan_dep_vld_vec_15[1];
    assign dep_chan_data_15_10 = out_chan_dep_data_15;
    assign token_15_10 = token_out_vec_15[1];
    assign dep_chan_vld_15_23 = out_chan_dep_vld_vec_15[2];
    assign dep_chan_data_15_23 = out_chan_dep_data_15;
    assign token_15_23 = token_out_vec_15[2];
    assign dep_chan_vld_15_20 = out_chan_dep_vld_vec_15[3];
    assign dep_chan_data_15_20 = out_chan_dep_data_15;
    assign token_15_20 = token_out_vec_15[3];
    assign dep_chan_vld_15_21 = out_chan_dep_vld_vec_15[4];
    assign dep_chan_data_15_21 = out_chan_dep_data_15;
    assign token_15_21 = token_out_vec_15[4];
    assign dep_chan_vld_15_6 = out_chan_dep_vld_vec_15[5];
    assign dep_chan_data_15_6 = out_chan_dep_data_15;
    assign token_15_6 = token_out_vec_15[5];
    assign dep_chan_vld_15_7 = out_chan_dep_vld_vec_15[6];
    assign dep_chan_data_15_7 = out_chan_dep_data_15;
    assign token_15_7 = token_out_vec_15[6];
    assign dep_chan_vld_15_4 = out_chan_dep_vld_vec_15[7];
    assign dep_chan_data_15_4 = out_chan_dep_data_15;
    assign token_15_4 = token_out_vec_15[7];
    assign dep_chan_vld_15_5 = out_chan_dep_vld_vec_15[8];
    assign dep_chan_data_15_5 = out_chan_dep_data_15;
    assign token_15_5 = token_out_vec_15[8];
    assign dep_chan_vld_15_8 = out_chan_dep_vld_vec_15[9];
    assign dep_chan_data_15_8 = out_chan_dep_data_15;
    assign token_15_8 = token_out_vec_15[9];
    assign dep_chan_vld_15_9 = out_chan_dep_vld_vec_15[10];
    assign dep_chan_data_15_9 = out_chan_dep_data_15;
    assign token_15_9 = token_out_vec_15[10];
    assign dep_chan_vld_15_31 = out_chan_dep_vld_vec_15[11];
    assign dep_chan_data_15_31 = out_chan_dep_data_15;
    assign token_15_31 = token_out_vec_15[11];
    assign dep_chan_vld_15_38 = out_chan_dep_vld_vec_15[12];
    assign dep_chan_data_15_38 = out_chan_dep_data_15;
    assign token_15_38 = token_out_vec_15[12];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 16, 3, 3) cnn_pipeline_v10_hls_deadlock_detect_unit_16 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_16),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_16),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_16),
        .token_in_vec(token_in_vec_16),
        .dl_detect_in(dl_detect_out),
        .origin(origin[16]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_16),
        .out_chan_dep_data(out_chan_dep_data_16),
        .token_out_vec(token_out_vec_16),
        .dl_detect_out(dl_in_vec[16]));

    assign proc_16_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.grp_p_anonymous_namespace_depthwise_compute_Pipeline_VITIS_LOOP_529_15_VITIS_LOOP_530_1_fu_855.raw_a_blk_n);
    assign proc_16_data_PIPO_blk[0] = 1'b0;
    assign proc_16_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.start_for_p_anonymous_namespace_depthwise_emit_0_true_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.real_start & (trans_in_cnt_5 == trans_out_cnt_5) & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.start_for_p_anonymous_namespace_depthwise_emit_0_true_U0_U.if_read);
    assign proc_16_TLF_FIFO_blk[0] = 1'b0;
    assign proc_16_input_sync_blk[0] = 1'b0;
    assign proc_16_output_sync_blk[0] = 1'b0 | (ap_done_reg_15 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_done);
    assign proc_dep_vld_vec_16[0] = dl_detect_out ? proc_dep_vld_vec_16_reg[0] : (proc_16_data_FIFO_blk[0] | proc_16_data_PIPO_blk[0] | proc_16_start_FIFO_blk[0] | proc_16_TLF_FIFO_blk[0] | proc_16_input_sync_blk[0] | proc_16_output_sync_blk[0]);
    assign proc_16_data_FIFO_blk[1] = 1'b0;
    assign proc_16_data_PIPO_blk[1] = 1'b0;
    assign proc_16_start_FIFO_blk[1] = 1'b0;
    assign proc_16_TLF_FIFO_blk[1] = 1'b0;
    assign proc_16_input_sync_blk[1] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.ap_sync_p_anonymous_namespace_depthwise_compute_0_7_16_true_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.ap_sync_p_anonymous_namespace_depthwise_compute_1_7_16_true_U0_ap_ready);
    assign proc_16_output_sync_blk[1] = 1'b0 | (ap_done_reg_15 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_done);
    assign proc_dep_vld_vec_16[1] = dl_detect_out ? proc_dep_vld_vec_16_reg[1] : (proc_16_data_FIFO_blk[1] | proc_16_data_PIPO_blk[1] | proc_16_start_FIFO_blk[1] | proc_16_TLF_FIFO_blk[1] | proc_16_input_sync_blk[1] | proc_16_output_sync_blk[1]);
    assign proc_16_data_FIFO_blk[2] = 1'b0;
    assign proc_16_data_PIPO_blk[2] = 1'b0;
    assign proc_16_start_FIFO_blk[2] = 1'b0;
    assign proc_16_TLF_FIFO_blk[2] = 1'b0;
    assign proc_16_input_sync_blk[2] = 1'b0;
    assign proc_16_output_sync_blk[2] = 1'b0 | (ap_done_reg_15 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_done);
    assign proc_dep_vld_vec_16[2] = dl_detect_out ? proc_dep_vld_vec_16_reg[2] : (proc_16_data_FIFO_blk[2] | proc_16_data_PIPO_blk[2] | proc_16_start_FIFO_blk[2] | proc_16_TLF_FIFO_blk[2] | proc_16_input_sync_blk[2] | proc_16_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_16_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_16_reg <= proc_dep_vld_vec_16;
        end
    end
    assign in_chan_dep_vld_vec_16[0] = dep_chan_vld_17_16;
    assign in_chan_dep_data_vec_16[38 : 0] = dep_chan_data_17_16;
    assign token_in_vec_16[0] = token_17_16;
    assign in_chan_dep_vld_vec_16[1] = dep_chan_vld_18_16;
    assign in_chan_dep_data_vec_16[77 : 39] = dep_chan_data_18_16;
    assign token_in_vec_16[1] = token_18_16;
    assign in_chan_dep_vld_vec_16[2] = dep_chan_vld_19_16;
    assign in_chan_dep_data_vec_16[116 : 78] = dep_chan_data_19_16;
    assign token_in_vec_16[2] = token_19_16;
    assign dep_chan_vld_16_17 = out_chan_dep_vld_vec_16[0];
    assign dep_chan_data_16_17 = out_chan_dep_data_16;
    assign token_16_17 = token_out_vec_16[0];
    assign dep_chan_vld_16_18 = out_chan_dep_vld_vec_16[1];
    assign dep_chan_data_16_18 = out_chan_dep_data_16;
    assign token_16_18 = token_out_vec_16[1];
    assign dep_chan_vld_16_19 = out_chan_dep_vld_vec_16[2];
    assign dep_chan_data_16_19 = out_chan_dep_data_16;
    assign token_16_19 = token_out_vec_16[2];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 17, 3, 3) cnn_pipeline_v10_hls_deadlock_detect_unit_17 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_17),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_17),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_17),
        .token_in_vec(token_in_vec_17),
        .dl_detect_in(dl_detect_out),
        .origin(origin[17]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_17),
        .out_chan_dep_data(out_chan_dep_data_17),
        .token_out_vec(token_out_vec_17),
        .dl_detect_out(dl_in_vec[17]));

    assign proc_17_data_FIFO_blk[0] = 1'b0;
    assign proc_17_data_PIPO_blk[0] = 1'b0;
    assign proc_17_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.start_for_p_anonymous_namespace_depthwise_emit_0_true_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.start_for_p_anonymous_namespace_depthwise_emit_0_true_U0_U.if_write);
    assign proc_17_TLF_FIFO_blk[0] = 1'b0;
    assign proc_17_input_sync_blk[0] = 1'b0;
    assign proc_17_output_sync_blk[0] = 1'b0 | (ap_done_reg_16 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_done);
    assign proc_dep_vld_vec_17[0] = dl_detect_out ? proc_dep_vld_vec_17_reg[0] : (proc_17_data_FIFO_blk[0] | proc_17_data_PIPO_blk[0] | proc_17_start_FIFO_blk[0] | proc_17_TLF_FIFO_blk[0] | proc_17_input_sync_blk[0] | proc_17_output_sync_blk[0]);
    assign proc_17_data_FIFO_blk[1] = 1'b0;
    assign proc_17_data_PIPO_blk[1] = 1'b0;
    assign proc_17_start_FIFO_blk[1] = 1'b0;
    assign proc_17_TLF_FIFO_blk[1] = 1'b0;
    assign proc_17_input_sync_blk[1] = 1'b0;
    assign proc_17_output_sync_blk[1] = 1'b0 | (ap_done_reg_16 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_done);
    assign proc_dep_vld_vec_17[1] = dl_detect_out ? proc_dep_vld_vec_17_reg[1] : (proc_17_data_FIFO_blk[1] | proc_17_data_PIPO_blk[1] | proc_17_start_FIFO_blk[1] | proc_17_TLF_FIFO_blk[1] | proc_17_input_sync_blk[1] | proc_17_output_sync_blk[1]);
    assign proc_17_data_FIFO_blk[2] = 1'b0;
    assign proc_17_data_PIPO_blk[2] = 1'b0;
    assign proc_17_start_FIFO_blk[2] = 1'b0;
    assign proc_17_TLF_FIFO_blk[2] = 1'b0;
    assign proc_17_input_sync_blk[2] = 1'b0;
    assign proc_17_output_sync_blk[2] = 1'b0 | (ap_done_reg_16 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_done);
    assign proc_dep_vld_vec_17[2] = dl_detect_out ? proc_dep_vld_vec_17_reg[2] : (proc_17_data_FIFO_blk[2] | proc_17_data_PIPO_blk[2] | proc_17_start_FIFO_blk[2] | proc_17_TLF_FIFO_blk[2] | proc_17_input_sync_blk[2] | proc_17_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_17_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_17_reg <= proc_dep_vld_vec_17;
        end
    end
    assign in_chan_dep_vld_vec_17[0] = dep_chan_vld_16_17;
    assign in_chan_dep_data_vec_17[38 : 0] = dep_chan_data_16_17;
    assign token_in_vec_17[0] = token_16_17;
    assign in_chan_dep_vld_vec_17[1] = dep_chan_vld_18_17;
    assign in_chan_dep_data_vec_17[77 : 39] = dep_chan_data_18_17;
    assign token_in_vec_17[1] = token_18_17;
    assign in_chan_dep_vld_vec_17[2] = dep_chan_vld_19_17;
    assign in_chan_dep_data_vec_17[116 : 78] = dep_chan_data_19_17;
    assign token_in_vec_17[2] = token_19_17;
    assign dep_chan_vld_17_16 = out_chan_dep_vld_vec_17[0];
    assign dep_chan_data_17_16 = out_chan_dep_data_17;
    assign token_17_16 = token_out_vec_17[0];
    assign dep_chan_vld_17_18 = out_chan_dep_vld_vec_17[1];
    assign dep_chan_data_17_18 = out_chan_dep_data_17;
    assign token_17_18 = token_out_vec_17[1];
    assign dep_chan_vld_17_19 = out_chan_dep_vld_vec_17[2];
    assign dep_chan_data_17_19 = out_chan_dep_data_17;
    assign token_17_19 = token_out_vec_17[2];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 18, 3, 3) cnn_pipeline_v10_hls_deadlock_detect_unit_18 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_18),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_18),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_18),
        .token_in_vec(token_in_vec_18),
        .dl_detect_in(dl_detect_out),
        .origin(origin[18]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_18),
        .out_chan_dep_data(out_chan_dep_data_18),
        .token_out_vec(token_out_vec_18),
        .dl_detect_out(dl_in_vec[18]));

    assign proc_18_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.grp_p_anonymous_namespace_depthwise_compute_Pipeline_VITIS_LOOP_529_15_VITIS_LOOP_530_fu_867.raw_b_blk_n);
    assign proc_18_data_PIPO_blk[0] = 1'b0;
    assign proc_18_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.start_for_p_anonymous_namespace_depthwise_emit_1_true_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.start_for_p_anonymous_namespace_depthwise_emit_1_true_U0_U.if_read);
    assign proc_18_TLF_FIFO_blk[0] = 1'b0;
    assign proc_18_input_sync_blk[0] = 1'b0;
    assign proc_18_output_sync_blk[0] = 1'b0 | (ap_done_reg_17 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_done);
    assign proc_dep_vld_vec_18[0] = dl_detect_out ? proc_dep_vld_vec_18_reg[0] : (proc_18_data_FIFO_blk[0] | proc_18_data_PIPO_blk[0] | proc_18_start_FIFO_blk[0] | proc_18_TLF_FIFO_blk[0] | proc_18_input_sync_blk[0] | proc_18_output_sync_blk[0]);
    assign proc_18_data_FIFO_blk[1] = 1'b0;
    assign proc_18_data_PIPO_blk[1] = 1'b0;
    assign proc_18_start_FIFO_blk[1] = 1'b0;
    assign proc_18_TLF_FIFO_blk[1] = 1'b0;
    assign proc_18_input_sync_blk[1] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.ap_sync_p_anonymous_namespace_depthwise_compute_1_7_16_true_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.ap_sync_p_anonymous_namespace_depthwise_compute_0_7_16_true_U0_ap_ready);
    assign proc_18_output_sync_blk[1] = 1'b0 | (ap_done_reg_17 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_done);
    assign proc_dep_vld_vec_18[1] = dl_detect_out ? proc_dep_vld_vec_18_reg[1] : (proc_18_data_FIFO_blk[1] | proc_18_data_PIPO_blk[1] | proc_18_start_FIFO_blk[1] | proc_18_TLF_FIFO_blk[1] | proc_18_input_sync_blk[1] | proc_18_output_sync_blk[1]);
    assign proc_18_data_FIFO_blk[2] = 1'b0;
    assign proc_18_data_PIPO_blk[2] = 1'b0;
    assign proc_18_start_FIFO_blk[2] = 1'b0;
    assign proc_18_TLF_FIFO_blk[2] = 1'b0;
    assign proc_18_input_sync_blk[2] = 1'b0;
    assign proc_18_output_sync_blk[2] = 1'b0 | (ap_done_reg_17 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_done);
    assign proc_dep_vld_vec_18[2] = dl_detect_out ? proc_dep_vld_vec_18_reg[2] : (proc_18_data_FIFO_blk[2] | proc_18_data_PIPO_blk[2] | proc_18_start_FIFO_blk[2] | proc_18_TLF_FIFO_blk[2] | proc_18_input_sync_blk[2] | proc_18_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_18_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_18_reg <= proc_dep_vld_vec_18;
        end
    end
    assign in_chan_dep_vld_vec_18[0] = dep_chan_vld_16_18;
    assign in_chan_dep_data_vec_18[38 : 0] = dep_chan_data_16_18;
    assign token_in_vec_18[0] = token_16_18;
    assign in_chan_dep_vld_vec_18[1] = dep_chan_vld_17_18;
    assign in_chan_dep_data_vec_18[77 : 39] = dep_chan_data_17_18;
    assign token_in_vec_18[1] = token_17_18;
    assign in_chan_dep_vld_vec_18[2] = dep_chan_vld_19_18;
    assign in_chan_dep_data_vec_18[116 : 78] = dep_chan_data_19_18;
    assign token_in_vec_18[2] = token_19_18;
    assign dep_chan_vld_18_19 = out_chan_dep_vld_vec_18[0];
    assign dep_chan_data_18_19 = out_chan_dep_data_18;
    assign token_18_19 = token_out_vec_18[0];
    assign dep_chan_vld_18_16 = out_chan_dep_vld_vec_18[1];
    assign dep_chan_data_18_16 = out_chan_dep_data_18;
    assign token_18_16 = token_out_vec_18[1];
    assign dep_chan_vld_18_17 = out_chan_dep_vld_vec_18[2];
    assign dep_chan_data_18_17 = out_chan_dep_data_18;
    assign token_18_17 = token_out_vec_18[2];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 19, 3, 3) cnn_pipeline_v10_hls_deadlock_detect_unit_19 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_19),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_19),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_19),
        .token_in_vec(token_in_vec_19),
        .dl_detect_in(dl_detect_out),
        .origin(origin[19]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_19),
        .out_chan_dep_data(out_chan_dep_data_19),
        .token_out_vec(token_out_vec_19),
        .dl_detect_out(dl_in_vec[19]));

    assign proc_19_data_FIFO_blk[0] = 1'b0;
    assign proc_19_data_PIPO_blk[0] = 1'b0;
    assign proc_19_start_FIFO_blk[0] = 1'b0;
    assign proc_19_TLF_FIFO_blk[0] = 1'b0;
    assign proc_19_input_sync_blk[0] = 1'b0;
    assign proc_19_output_sync_blk[0] = 1'b0 | (ap_done_reg_18 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_0_7_16_true_U0.ap_done);
    assign proc_dep_vld_vec_19[0] = dl_detect_out ? proc_dep_vld_vec_19_reg[0] : (proc_19_data_FIFO_blk[0] | proc_19_data_PIPO_blk[0] | proc_19_start_FIFO_blk[0] | proc_19_TLF_FIFO_blk[0] | proc_19_input_sync_blk[0] | proc_19_output_sync_blk[0]);
    assign proc_19_data_FIFO_blk[1] = 1'b0;
    assign proc_19_data_PIPO_blk[1] = 1'b0;
    assign proc_19_start_FIFO_blk[1] = 1'b0;
    assign proc_19_TLF_FIFO_blk[1] = 1'b0;
    assign proc_19_input_sync_blk[1] = 1'b0;
    assign proc_19_output_sync_blk[1] = 1'b0 | (ap_done_reg_18 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_0_true_U0.ap_done);
    assign proc_dep_vld_vec_19[1] = dl_detect_out ? proc_dep_vld_vec_19_reg[1] : (proc_19_data_FIFO_blk[1] | proc_19_data_PIPO_blk[1] | proc_19_start_FIFO_blk[1] | proc_19_TLF_FIFO_blk[1] | proc_19_input_sync_blk[1] | proc_19_output_sync_blk[1]);
    assign proc_19_data_FIFO_blk[2] = 1'b0;
    assign proc_19_data_PIPO_blk[2] = 1'b0;
    assign proc_19_start_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.start_for_p_anonymous_namespace_depthwise_emit_1_true_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.start_for_p_anonymous_namespace_depthwise_emit_1_true_U0_U.if_write);
    assign proc_19_TLF_FIFO_blk[2] = 1'b0;
    assign proc_19_input_sync_blk[2] = 1'b0;
    assign proc_19_output_sync_blk[2] = 1'b0 | (ap_done_reg_18 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_emit_1_true_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.grp_p_anonymous_namespace_depthwise_dual_7_16_true_s_fu_330.p_anonymous_namespace_depthwise_compute_1_7_16_true_U0.ap_done);
    assign proc_dep_vld_vec_19[2] = dl_detect_out ? proc_dep_vld_vec_19_reg[2] : (proc_19_data_FIFO_blk[2] | proc_19_data_PIPO_blk[2] | proc_19_start_FIFO_blk[2] | proc_19_TLF_FIFO_blk[2] | proc_19_input_sync_blk[2] | proc_19_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_19_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_19_reg <= proc_dep_vld_vec_19;
        end
    end
    assign in_chan_dep_vld_vec_19[0] = dep_chan_vld_16_19;
    assign in_chan_dep_data_vec_19[38 : 0] = dep_chan_data_16_19;
    assign token_in_vec_19[0] = token_16_19;
    assign in_chan_dep_vld_vec_19[1] = dep_chan_vld_17_19;
    assign in_chan_dep_data_vec_19[77 : 39] = dep_chan_data_17_19;
    assign token_in_vec_19[1] = token_17_19;
    assign in_chan_dep_vld_vec_19[2] = dep_chan_vld_18_19;
    assign in_chan_dep_data_vec_19[116 : 78] = dep_chan_data_18_19;
    assign token_in_vec_19[2] = token_18_19;
    assign dep_chan_vld_19_16 = out_chan_dep_vld_vec_19[0];
    assign dep_chan_data_19_16 = out_chan_dep_data_19;
    assign token_19_16 = token_out_vec_19[0];
    assign dep_chan_vld_19_17 = out_chan_dep_vld_vec_19[1];
    assign dep_chan_data_19_17 = out_chan_dep_data_19;
    assign token_19_17 = token_out_vec_19[1];
    assign dep_chan_vld_19_18 = out_chan_dep_vld_vec_19[2];
    assign dep_chan_data_19_18 = out_chan_dep_data_19;
    assign token_19_18 = token_out_vec_19[2];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 20, 10, 10) cnn_pipeline_v10_hls_deadlock_detect_unit_20 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_20),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_20),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_20),
        .token_in_vec(token_in_vec_20),
        .dl_detect_in(dl_detect_out),
        .origin(origin[20]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_20),
        .out_chan_dep_data(out_chan_dep_data_20),
        .token_out_vec(token_out_vec_20),
        .dl_detect_out(dl_in_vec[20]));

    assign proc_20_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.grp_p_anonymous_namespace_residual_writer_2_Pipeline_VITIS_LOOP_831_5_VITIS_LOOP_833_s_fu_283.res_a_blk_n);
    assign proc_20_data_PIPO_blk[0] = 1'b0;
    assign proc_20_start_FIFO_blk[0] = 1'b0;
    assign proc_20_TLF_FIFO_blk[0] = 1'b0;
    assign proc_20_input_sync_blk[0] = 1'b0;
    assign proc_20_output_sync_blk[0] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_20[0] = dl_detect_out ? proc_dep_vld_vec_20_reg[0] : (proc_20_data_FIFO_blk[0] | proc_20_data_PIPO_blk[0] | proc_20_start_FIFO_blk[0] | proc_20_TLF_FIFO_blk[0] | proc_20_input_sync_blk[0] | proc_20_output_sync_blk[0]);
    assign proc_20_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.a_write_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.grp_p_anonymous_namespace_residual_writer_2_Pipeline_VITIS_LOOP_831_5_VITIS_LOOP_833_s_fu_283.a_write_data_0_blk_n);
    assign proc_20_data_PIPO_blk[1] = 1'b0;
    assign proc_20_start_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_residual_writer_2_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_residual_writer_2_U0_U.if_write);
    assign proc_20_TLF_FIFO_blk[1] = 1'b0;
    assign proc_20_input_sync_blk[1] = 1'b0;
    assign proc_20_output_sync_blk[1] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_20[1] = dl_detect_out ? proc_dep_vld_vec_20_reg[1] : (proc_20_data_FIFO_blk[1] | proc_20_data_PIPO_blk[1] | proc_20_start_FIFO_blk[1] | proc_20_TLF_FIFO_blk[1] | proc_20_input_sync_blk[1] | proc_20_output_sync_blk[1]);
    assign proc_20_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.residual_ready_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.residual_release_a_blk_n);
    assign proc_20_data_PIPO_blk[2] = 1'b0;
    assign proc_20_start_FIFO_blk[2] = 1'b0;
    assign proc_20_TLF_FIFO_blk[2] = 1'b0;
    assign proc_20_input_sync_blk[2] = 1'b0;
    assign proc_20_output_sync_blk[2] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_20[2] = dl_detect_out ? proc_dep_vld_vec_20_reg[2] : (proc_20_data_FIFO_blk[2] | proc_20_data_PIPO_blk[2] | proc_20_start_FIFO_blk[2] | proc_20_TLF_FIFO_blk[2] | proc_20_input_sync_blk[2] | proc_20_output_sync_blk[2]);
    assign proc_20_data_FIFO_blk[3] = 1'b0;
    assign proc_20_data_PIPO_blk[3] = 1'b0;
    assign proc_20_start_FIFO_blk[3] = 1'b0;
    assign proc_20_TLF_FIFO_blk[3] = 1'b0;
    assign proc_20_input_sync_blk[3] = 1'b0;
    assign proc_20_output_sync_blk[3] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_20[3] = dl_detect_out ? proc_dep_vld_vec_20_reg[3] : (proc_20_data_FIFO_blk[3] | proc_20_data_PIPO_blk[3] | proc_20_start_FIFO_blk[3] | proc_20_TLF_FIFO_blk[3] | proc_20_input_sync_blk[3] | proc_20_output_sync_blk[3]);
    assign proc_20_data_FIFO_blk[4] = 1'b0;
    assign proc_20_data_PIPO_blk[4] = 1'b0;
    assign proc_20_start_FIFO_blk[4] = 1'b0;
    assign proc_20_TLF_FIFO_blk[4] = 1'b0;
    assign proc_20_input_sync_blk[4] = 1'b0;
    assign proc_20_output_sync_blk[4] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_20[4] = dl_detect_out ? proc_dep_vld_vec_20_reg[4] : (proc_20_data_FIFO_blk[4] | proc_20_data_PIPO_blk[4] | proc_20_start_FIFO_blk[4] | proc_20_TLF_FIFO_blk[4] | proc_20_input_sync_blk[4] | proc_20_output_sync_blk[4]);
    assign proc_20_data_FIFO_blk[5] = 1'b0;
    assign proc_20_data_PIPO_blk[5] = 1'b0;
    assign proc_20_start_FIFO_blk[5] = 1'b0;
    assign proc_20_TLF_FIFO_blk[5] = 1'b0;
    assign proc_20_input_sync_blk[5] = 1'b0;
    assign proc_20_output_sync_blk[5] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_20[5] = dl_detect_out ? proc_dep_vld_vec_20_reg[5] : (proc_20_data_FIFO_blk[5] | proc_20_data_PIPO_blk[5] | proc_20_start_FIFO_blk[5] | proc_20_TLF_FIFO_blk[5] | proc_20_input_sync_blk[5] | proc_20_output_sync_blk[5]);
    assign proc_20_data_FIFO_blk[6] = 1'b0;
    assign proc_20_data_PIPO_blk[6] = 1'b0;
    assign proc_20_start_FIFO_blk[6] = 1'b0;
    assign proc_20_TLF_FIFO_blk[6] = 1'b0;
    assign proc_20_input_sync_blk[6] = 1'b0;
    assign proc_20_output_sync_blk[6] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_20[6] = dl_detect_out ? proc_dep_vld_vec_20_reg[6] : (proc_20_data_FIFO_blk[6] | proc_20_data_PIPO_blk[6] | proc_20_start_FIFO_blk[6] | proc_20_TLF_FIFO_blk[6] | proc_20_input_sync_blk[6] | proc_20_output_sync_blk[6]);
    assign proc_20_data_FIFO_blk[7] = 1'b0;
    assign proc_20_data_PIPO_blk[7] = 1'b0;
    assign proc_20_start_FIFO_blk[7] = 1'b0;
    assign proc_20_TLF_FIFO_blk[7] = 1'b0;
    assign proc_20_input_sync_blk[7] = 1'b0;
    assign proc_20_output_sync_blk[7] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_20[7] = dl_detect_out ? proc_dep_vld_vec_20_reg[7] : (proc_20_data_FIFO_blk[7] | proc_20_data_PIPO_blk[7] | proc_20_start_FIFO_blk[7] | proc_20_TLF_FIFO_blk[7] | proc_20_input_sync_blk[7] | proc_20_output_sync_blk[7]);
    assign proc_20_data_FIFO_blk[8] = 1'b0;
    assign proc_20_data_PIPO_blk[8] = 1'b0;
    assign proc_20_start_FIFO_blk[8] = 1'b0;
    assign proc_20_TLF_FIFO_blk[8] = 1'b0;
    assign proc_20_input_sync_blk[8] = 1'b0;
    assign proc_20_output_sync_blk[8] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_20[8] = dl_detect_out ? proc_dep_vld_vec_20_reg[8] : (proc_20_data_FIFO_blk[8] | proc_20_data_PIPO_blk[8] | proc_20_start_FIFO_blk[8] | proc_20_TLF_FIFO_blk[8] | proc_20_input_sync_blk[8] | proc_20_output_sync_blk[8]);
    assign proc_20_data_FIFO_blk[9] = 1'b0;
    assign proc_20_data_PIPO_blk[9] = 1'b0;
    assign proc_20_start_FIFO_blk[9] = 1'b0;
    assign proc_20_TLF_FIFO_blk[9] = 1'b0;
    assign proc_20_input_sync_blk[9] = 1'b0;
    assign proc_20_output_sync_blk[9] = 1'b0 | (ap_done_reg_6 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_20[9] = dl_detect_out ? proc_dep_vld_vec_20_reg[9] : (proc_20_data_FIFO_blk[9] | proc_20_data_PIPO_blk[9] | proc_20_start_FIFO_blk[9] | proc_20_TLF_FIFO_blk[9] | proc_20_input_sync_blk[9] | proc_20_output_sync_blk[9]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_20_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_20_reg <= proc_dep_vld_vec_20;
        end
    end
    assign in_chan_dep_vld_vec_20[0] = dep_chan_vld_4_20;
    assign in_chan_dep_data_vec_20[38 : 0] = dep_chan_data_4_20;
    assign token_in_vec_20[0] = token_4_20;
    assign in_chan_dep_vld_vec_20[1] = dep_chan_vld_5_20;
    assign in_chan_dep_data_vec_20[77 : 39] = dep_chan_data_5_20;
    assign token_in_vec_20[1] = token_5_20;
    assign in_chan_dep_vld_vec_20[2] = dep_chan_vld_8_20;
    assign in_chan_dep_data_vec_20[116 : 78] = dep_chan_data_8_20;
    assign token_in_vec_20[2] = token_8_20;
    assign in_chan_dep_vld_vec_20[3] = dep_chan_vld_9_20;
    assign in_chan_dep_data_vec_20[155 : 117] = dep_chan_data_9_20;
    assign token_in_vec_20[3] = token_9_20;
    assign in_chan_dep_vld_vec_20[4] = dep_chan_vld_10_20;
    assign in_chan_dep_data_vec_20[194 : 156] = dep_chan_data_10_20;
    assign token_in_vec_20[4] = token_10_20;
    assign in_chan_dep_vld_vec_20[5] = dep_chan_vld_15_20;
    assign in_chan_dep_data_vec_20[233 : 195] = dep_chan_data_15_20;
    assign token_in_vec_20[5] = token_15_20;
    assign in_chan_dep_vld_vec_20[6] = dep_chan_vld_21_20;
    assign in_chan_dep_data_vec_20[272 : 234] = dep_chan_data_21_20;
    assign token_in_vec_20[6] = token_21_20;
    assign in_chan_dep_vld_vec_20[7] = dep_chan_vld_23_20;
    assign in_chan_dep_data_vec_20[311 : 273] = dep_chan_data_23_20;
    assign token_in_vec_20[7] = token_23_20;
    assign in_chan_dep_vld_vec_20[8] = dep_chan_vld_31_20;
    assign in_chan_dep_data_vec_20[350 : 312] = dep_chan_data_31_20;
    assign token_in_vec_20[8] = token_31_20;
    assign in_chan_dep_vld_vec_20[9] = dep_chan_vld_38_20;
    assign in_chan_dep_data_vec_20[389 : 351] = dep_chan_data_38_20;
    assign token_in_vec_20[9] = token_38_20;
    assign dep_chan_vld_20_15 = out_chan_dep_vld_vec_20[0];
    assign dep_chan_data_20_15 = out_chan_dep_data_20;
    assign token_20_15 = token_out_vec_20[0];
    assign dep_chan_vld_20_4 = out_chan_dep_vld_vec_20[1];
    assign dep_chan_data_20_4 = out_chan_dep_data_20;
    assign token_20_4 = token_out_vec_20[1];
    assign dep_chan_vld_20_31 = out_chan_dep_vld_vec_20[2];
    assign dep_chan_data_20_31 = out_chan_dep_data_20;
    assign token_20_31 = token_out_vec_20[2];
    assign dep_chan_vld_20_5 = out_chan_dep_vld_vec_20[3];
    assign dep_chan_data_20_5 = out_chan_dep_data_20;
    assign token_20_5 = token_out_vec_20[3];
    assign dep_chan_vld_20_8 = out_chan_dep_vld_vec_20[4];
    assign dep_chan_data_20_8 = out_chan_dep_data_20;
    assign token_20_8 = token_out_vec_20[4];
    assign dep_chan_vld_20_9 = out_chan_dep_vld_vec_20[5];
    assign dep_chan_data_20_9 = out_chan_dep_data_20;
    assign token_20_9 = token_out_vec_20[5];
    assign dep_chan_vld_20_10 = out_chan_dep_vld_vec_20[6];
    assign dep_chan_data_20_10 = out_chan_dep_data_20;
    assign token_20_10 = token_out_vec_20[6];
    assign dep_chan_vld_20_21 = out_chan_dep_vld_vec_20[7];
    assign dep_chan_data_20_21 = out_chan_dep_data_20;
    assign token_20_21 = token_out_vec_20[7];
    assign dep_chan_vld_20_23 = out_chan_dep_vld_vec_20[8];
    assign dep_chan_data_20_23 = out_chan_dep_data_20;
    assign token_20_23 = token_out_vec_20[8];
    assign dep_chan_vld_20_38 = out_chan_dep_vld_vec_20[9];
    assign dep_chan_data_20_38 = out_chan_dep_data_20;
    assign token_20_38 = token_out_vec_20[9];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 21, 10, 10) cnn_pipeline_v10_hls_deadlock_detect_unit_21 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_21),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_21),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_21),
        .token_in_vec(token_in_vec_21),
        .dl_detect_in(dl_detect_out),
        .origin(origin[21]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_21),
        .out_chan_dep_data(out_chan_dep_data_21),
        .token_out_vec(token_out_vec_21),
        .dl_detect_out(dl_in_vec[21]));

    assign proc_21_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.grp_p_anonymous_namespace_residual_writer_Pipeline_VITIS_LOOP_831_5_VITIS_LOOP_833_6_fu_283.res_b_blk_n);
    assign proc_21_data_PIPO_blk[0] = 1'b0;
    assign proc_21_start_FIFO_blk[0] = 1'b0;
    assign proc_21_TLF_FIFO_blk[0] = 1'b0;
    assign proc_21_input_sync_blk[0] = 1'b0;
    assign proc_21_output_sync_blk[0] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_21[0] = dl_detect_out ? proc_dep_vld_vec_21_reg[0] : (proc_21_data_FIFO_blk[0] | proc_21_data_PIPO_blk[0] | proc_21_start_FIFO_blk[0] | proc_21_TLF_FIFO_blk[0] | proc_21_input_sync_blk[0] | proc_21_output_sync_blk[0]);
    assign proc_21_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.b_write_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.grp_p_anonymous_namespace_residual_writer_Pipeline_VITIS_LOOP_831_5_VITIS_LOOP_833_6_fu_283.b_write_data_0_blk_n);
    assign proc_21_data_PIPO_blk[1] = 1'b0;
    assign proc_21_start_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_residual_writer_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_residual_writer_U0_U.if_write);
    assign proc_21_TLF_FIFO_blk[1] = 1'b0;
    assign proc_21_input_sync_blk[1] = 1'b0;
    assign proc_21_output_sync_blk[1] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_21[1] = dl_detect_out ? proc_dep_vld_vec_21_reg[1] : (proc_21_data_FIFO_blk[1] | proc_21_data_PIPO_blk[1] | proc_21_start_FIFO_blk[1] | proc_21_TLF_FIFO_blk[1] | proc_21_input_sync_blk[1] | proc_21_output_sync_blk[1]);
    assign proc_21_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.residual_ready_b_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.residual_release_b_blk_n);
    assign proc_21_data_PIPO_blk[2] = 1'b0;
    assign proc_21_start_FIFO_blk[2] = 1'b0;
    assign proc_21_TLF_FIFO_blk[2] = 1'b0;
    assign proc_21_input_sync_blk[2] = 1'b0;
    assign proc_21_output_sync_blk[2] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_21[2] = dl_detect_out ? proc_dep_vld_vec_21_reg[2] : (proc_21_data_FIFO_blk[2] | proc_21_data_PIPO_blk[2] | proc_21_start_FIFO_blk[2] | proc_21_TLF_FIFO_blk[2] | proc_21_input_sync_blk[2] | proc_21_output_sync_blk[2]);
    assign proc_21_data_FIFO_blk[3] = 1'b0;
    assign proc_21_data_PIPO_blk[3] = 1'b0;
    assign proc_21_start_FIFO_blk[3] = 1'b0;
    assign proc_21_TLF_FIFO_blk[3] = 1'b0;
    assign proc_21_input_sync_blk[3] = 1'b0;
    assign proc_21_output_sync_blk[3] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_21[3] = dl_detect_out ? proc_dep_vld_vec_21_reg[3] : (proc_21_data_FIFO_blk[3] | proc_21_data_PIPO_blk[3] | proc_21_start_FIFO_blk[3] | proc_21_TLF_FIFO_blk[3] | proc_21_input_sync_blk[3] | proc_21_output_sync_blk[3]);
    assign proc_21_data_FIFO_blk[4] = 1'b0;
    assign proc_21_data_PIPO_blk[4] = 1'b0;
    assign proc_21_start_FIFO_blk[4] = 1'b0;
    assign proc_21_TLF_FIFO_blk[4] = 1'b0;
    assign proc_21_input_sync_blk[4] = 1'b0;
    assign proc_21_output_sync_blk[4] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_21[4] = dl_detect_out ? proc_dep_vld_vec_21_reg[4] : (proc_21_data_FIFO_blk[4] | proc_21_data_PIPO_blk[4] | proc_21_start_FIFO_blk[4] | proc_21_TLF_FIFO_blk[4] | proc_21_input_sync_blk[4] | proc_21_output_sync_blk[4]);
    assign proc_21_data_FIFO_blk[5] = 1'b0;
    assign proc_21_data_PIPO_blk[5] = 1'b0;
    assign proc_21_start_FIFO_blk[5] = 1'b0;
    assign proc_21_TLF_FIFO_blk[5] = 1'b0;
    assign proc_21_input_sync_blk[5] = 1'b0;
    assign proc_21_output_sync_blk[5] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_21[5] = dl_detect_out ? proc_dep_vld_vec_21_reg[5] : (proc_21_data_FIFO_blk[5] | proc_21_data_PIPO_blk[5] | proc_21_start_FIFO_blk[5] | proc_21_TLF_FIFO_blk[5] | proc_21_input_sync_blk[5] | proc_21_output_sync_blk[5]);
    assign proc_21_data_FIFO_blk[6] = 1'b0;
    assign proc_21_data_PIPO_blk[6] = 1'b0;
    assign proc_21_start_FIFO_blk[6] = 1'b0;
    assign proc_21_TLF_FIFO_blk[6] = 1'b0;
    assign proc_21_input_sync_blk[6] = 1'b0;
    assign proc_21_output_sync_blk[6] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_21[6] = dl_detect_out ? proc_dep_vld_vec_21_reg[6] : (proc_21_data_FIFO_blk[6] | proc_21_data_PIPO_blk[6] | proc_21_start_FIFO_blk[6] | proc_21_TLF_FIFO_blk[6] | proc_21_input_sync_blk[6] | proc_21_output_sync_blk[6]);
    assign proc_21_data_FIFO_blk[7] = 1'b0;
    assign proc_21_data_PIPO_blk[7] = 1'b0;
    assign proc_21_start_FIFO_blk[7] = 1'b0;
    assign proc_21_TLF_FIFO_blk[7] = 1'b0;
    assign proc_21_input_sync_blk[7] = 1'b0;
    assign proc_21_output_sync_blk[7] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_21[7] = dl_detect_out ? proc_dep_vld_vec_21_reg[7] : (proc_21_data_FIFO_blk[7] | proc_21_data_PIPO_blk[7] | proc_21_start_FIFO_blk[7] | proc_21_TLF_FIFO_blk[7] | proc_21_input_sync_blk[7] | proc_21_output_sync_blk[7]);
    assign proc_21_data_FIFO_blk[8] = 1'b0;
    assign proc_21_data_PIPO_blk[8] = 1'b0;
    assign proc_21_start_FIFO_blk[8] = 1'b0;
    assign proc_21_TLF_FIFO_blk[8] = 1'b0;
    assign proc_21_input_sync_blk[8] = 1'b0;
    assign proc_21_output_sync_blk[8] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_21[8] = dl_detect_out ? proc_dep_vld_vec_21_reg[8] : (proc_21_data_FIFO_blk[8] | proc_21_data_PIPO_blk[8] | proc_21_start_FIFO_blk[8] | proc_21_TLF_FIFO_blk[8] | proc_21_input_sync_blk[8] | proc_21_output_sync_blk[8]);
    assign proc_21_data_FIFO_blk[9] = 1'b0;
    assign proc_21_data_PIPO_blk[9] = 1'b0;
    assign proc_21_start_FIFO_blk[9] = 1'b0;
    assign proc_21_TLF_FIFO_blk[9] = 1'b0;
    assign proc_21_input_sync_blk[9] = 1'b0;
    assign proc_21_output_sync_blk[9] = 1'b0 | (ap_done_reg_7 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_21[9] = dl_detect_out ? proc_dep_vld_vec_21_reg[9] : (proc_21_data_FIFO_blk[9] | proc_21_data_PIPO_blk[9] | proc_21_start_FIFO_blk[9] | proc_21_TLF_FIFO_blk[9] | proc_21_input_sync_blk[9] | proc_21_output_sync_blk[9]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_21_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_21_reg <= proc_dep_vld_vec_21;
        end
    end
    assign in_chan_dep_vld_vec_21[0] = dep_chan_vld_4_21;
    assign in_chan_dep_data_vec_21[38 : 0] = dep_chan_data_4_21;
    assign token_in_vec_21[0] = token_4_21;
    assign in_chan_dep_vld_vec_21[1] = dep_chan_vld_5_21;
    assign in_chan_dep_data_vec_21[77 : 39] = dep_chan_data_5_21;
    assign token_in_vec_21[1] = token_5_21;
    assign in_chan_dep_vld_vec_21[2] = dep_chan_vld_8_21;
    assign in_chan_dep_data_vec_21[116 : 78] = dep_chan_data_8_21;
    assign token_in_vec_21[2] = token_8_21;
    assign in_chan_dep_vld_vec_21[3] = dep_chan_vld_9_21;
    assign in_chan_dep_data_vec_21[155 : 117] = dep_chan_data_9_21;
    assign token_in_vec_21[3] = token_9_21;
    assign in_chan_dep_vld_vec_21[4] = dep_chan_vld_10_21;
    assign in_chan_dep_data_vec_21[194 : 156] = dep_chan_data_10_21;
    assign token_in_vec_21[4] = token_10_21;
    assign in_chan_dep_vld_vec_21[5] = dep_chan_vld_15_21;
    assign in_chan_dep_data_vec_21[233 : 195] = dep_chan_data_15_21;
    assign token_in_vec_21[5] = token_15_21;
    assign in_chan_dep_vld_vec_21[6] = dep_chan_vld_20_21;
    assign in_chan_dep_data_vec_21[272 : 234] = dep_chan_data_20_21;
    assign token_in_vec_21[6] = token_20_21;
    assign in_chan_dep_vld_vec_21[7] = dep_chan_vld_23_21;
    assign in_chan_dep_data_vec_21[311 : 273] = dep_chan_data_23_21;
    assign token_in_vec_21[7] = token_23_21;
    assign in_chan_dep_vld_vec_21[8] = dep_chan_vld_31_21;
    assign in_chan_dep_data_vec_21[350 : 312] = dep_chan_data_31_21;
    assign token_in_vec_21[8] = token_31_21;
    assign in_chan_dep_vld_vec_21[9] = dep_chan_vld_38_21;
    assign in_chan_dep_data_vec_21[389 : 351] = dep_chan_data_38_21;
    assign token_in_vec_21[9] = token_38_21;
    assign dep_chan_vld_21_15 = out_chan_dep_vld_vec_21[0];
    assign dep_chan_data_21_15 = out_chan_dep_data_21;
    assign token_21_15 = token_out_vec_21[0];
    assign dep_chan_vld_21_5 = out_chan_dep_vld_vec_21[1];
    assign dep_chan_data_21_5 = out_chan_dep_data_21;
    assign token_21_5 = token_out_vec_21[1];
    assign dep_chan_vld_21_31 = out_chan_dep_vld_vec_21[2];
    assign dep_chan_data_21_31 = out_chan_dep_data_21;
    assign token_21_31 = token_out_vec_21[2];
    assign dep_chan_vld_21_4 = out_chan_dep_vld_vec_21[3];
    assign dep_chan_data_21_4 = out_chan_dep_data_21;
    assign token_21_4 = token_out_vec_21[3];
    assign dep_chan_vld_21_8 = out_chan_dep_vld_vec_21[4];
    assign dep_chan_data_21_8 = out_chan_dep_data_21;
    assign token_21_8 = token_out_vec_21[4];
    assign dep_chan_vld_21_9 = out_chan_dep_vld_vec_21[5];
    assign dep_chan_data_21_9 = out_chan_dep_data_21;
    assign token_21_9 = token_out_vec_21[5];
    assign dep_chan_vld_21_10 = out_chan_dep_vld_vec_21[6];
    assign dep_chan_data_21_10 = out_chan_dep_data_21;
    assign token_21_10 = token_out_vec_21[6];
    assign dep_chan_vld_21_20 = out_chan_dep_vld_vec_21[7];
    assign dep_chan_data_21_20 = out_chan_dep_data_21;
    assign token_21_20 = token_out_vec_21[7];
    assign dep_chan_vld_21_23 = out_chan_dep_vld_vec_21[8];
    assign dep_chan_data_21_23 = out_chan_dep_data_21;
    assign token_21_23 = token_out_vec_21[8];
    assign dep_chan_vld_21_38 = out_chan_dep_vld_vec_21[9];
    assign dep_chan_data_21_38 = out_chan_dep_data_21;
    assign token_21_38 = token_out_vec_21[9];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_3_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 22, 2, 2) cnn_pipeline_v10_hls_deadlock_detect_unit_22 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_22),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_22),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_22),
        .token_in_vec(token_in_vec_22),
        .dl_detect_in(dl_detect_out),
        .origin(origin[22]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_22),
        .out_chan_dep_data(out_chan_dep_data_22),
        .token_out_vec(token_out_vec_22),
        .dl_detect_out(dl_in_vec[22]));

    assign proc_22_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_3_U0.p1_cmd_3_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_3_U0.grp_p_anonymous_namespace_weight_broadcast_3_Pipeline_VITIS_LOOP_876_4_VITIS_LOOP_878_fu_249.p1_data_3_blk_n);
    assign proc_22_data_PIPO_blk[0] = 1'b0;
    assign proc_22_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_weight_broadcast_3_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_3_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_weight_broadcast_3_U0_U.if_write);
    assign proc_22_TLF_FIFO_blk[0] = 1'b0;
    assign proc_22_input_sync_blk[0] = 1'b0;
    assign proc_22_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_22[0] = dl_detect_out ? proc_dep_vld_vec_22_reg[0] : (proc_22_data_FIFO_blk[0] | proc_22_data_PIPO_blk[0] | proc_22_start_FIFO_blk[0] | proc_22_TLF_FIFO_blk[0] | proc_22_input_sync_blk[0] | proc_22_output_sync_blk[0]);
    assign proc_22_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_3_U0.grp_p_anonymous_namespace_weight_broadcast_3_Pipeline_VITIS_LOOP_876_4_VITIS_LOOP_878_fu_249.wt1_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_3_U0.grp_p_anonymous_namespace_weight_broadcast_3_Pipeline_VITIS_LOOP_876_4_VITIS_LOOP_878_fu_249.wt1_b_blk_n);
    assign proc_22_data_PIPO_blk[1] = 1'b0;
    assign proc_22_start_FIFO_blk[1] = 1'b0;
    assign proc_22_TLF_FIFO_blk[1] = 1'b0;
    assign proc_22_input_sync_blk[1] = 1'b0;
    assign proc_22_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_22[1] = dl_detect_out ? proc_dep_vld_vec_22_reg[1] : (proc_22_data_FIFO_blk[1] | proc_22_data_PIPO_blk[1] | proc_22_start_FIFO_blk[1] | proc_22_TLF_FIFO_blk[1] | proc_22_input_sync_blk[1] | proc_22_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_22_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_22_reg <= proc_dep_vld_vec_22;
        end
    end
    assign in_chan_dep_vld_vec_22[0] = dep_chan_vld_0_22;
    assign in_chan_dep_data_vec_22[38 : 0] = dep_chan_data_0_22;
    assign token_in_vec_22[0] = token_0_22;
    assign in_chan_dep_vld_vec_22[1] = dep_chan_vld_23_22;
    assign in_chan_dep_data_vec_22[77 : 39] = dep_chan_data_23_22;
    assign token_in_vec_22[1] = token_23_22;
    assign dep_chan_vld_22_0 = out_chan_dep_vld_vec_22[0];
    assign dep_chan_data_22_0 = out_chan_dep_data_22;
    assign token_22_0 = token_out_vec_22[0];
    assign dep_chan_vld_22_23 = out_chan_dep_vld_vec_22[1];
    assign dep_chan_data_22_23 = out_chan_dep_data_22;
    assign token_22_23 = token_out_vec_22[1];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 23, 12, 12) cnn_pipeline_v10_hls_deadlock_detect_unit_23 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_23),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_23),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_23),
        .token_in_vec(token_in_vec_23),
        .dl_detect_in(dl_detect_out),
        .origin(origin[23]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_23),
        .out_chan_dep_data(out_chan_dep_data_23),
        .token_out_vec(token_out_vec_23),
        .dl_detect_out(dl_in_vec[23]));

    assign proc_23_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.p1_cmd_2_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_load_segmented_gelu_ParamReader_s_fu_506.p1_cmd_2_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_load_segmented_gelu_ParamReader_s_fu_506.grp_load_segmented_gelu_ParamReader_Pipeline_VITIS_LOOP_81_2_VITIS_LOOP_83_3_fu_135.p1_data_2_blk_n);
    assign proc_23_data_PIPO_blk[0] = 1'b0;
    assign proc_23_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_pointwise1_chain_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_pointwise1_chain_U0_U.if_write);
    assign proc_23_TLF_FIFO_blk[0] = 1'b0;
    assign proc_23_input_sync_blk[0] = 1'b0;
    assign proc_23_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_23[0] = dl_detect_out ? proc_dep_vld_vec_23_reg[0] : (proc_23_data_FIFO_blk[0] | proc_23_data_PIPO_blk[0] | proc_23_start_FIFO_blk[0] | proc_23_TLF_FIFO_blk[0] | proc_23_input_sync_blk[0] | proc_23_output_sync_blk[0]);
    assign proc_23_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_n1_folded_gelu_dual_fu_523.grp_p_anonymous_namespace_n1_folded_gelu_dual_Pipeline_VITIS_LOOP_928_2_fu_100.q7_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_n1_folded_gelu_dual_fu_523.grp_p_anonymous_namespace_n1_folded_gelu_dual_Pipeline_VITIS_LOOP_928_2_fu_100.q7_b_blk_n);
    assign proc_23_data_PIPO_blk[1] = 1'b0;
    assign proc_23_start_FIFO_blk[1] = 1'b0;
    assign proc_23_TLF_FIFO_blk[1] = 1'b0;
    assign proc_23_input_sync_blk[1] = 1'b0;
    assign proc_23_output_sync_blk[1] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_23[1] = dl_detect_out ? proc_dep_vld_vec_23_reg[1] : (proc_23_data_FIFO_blk[1] | proc_23_data_PIPO_blk[1] | proc_23_start_FIFO_blk[1] | proc_23_TLF_FIFO_blk[1] | proc_23_input_sync_blk[1] | proc_23_output_sync_blk[1]);
    assign proc_23_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0.wt1_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0.wt1_b_blk_n);
    assign proc_23_data_PIPO_blk[2] = 1'b0;
    assign proc_23_start_FIFO_blk[2] = 1'b0;
    assign proc_23_TLF_FIFO_blk[2] = 1'b0;
    assign proc_23_input_sync_blk[2] = 1'b0;
    assign proc_23_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_23[2] = dl_detect_out ? proc_dep_vld_vec_23_reg[2] : (proc_23_data_FIFO_blk[2] | proc_23_data_PIPO_blk[2] | proc_23_start_FIFO_blk[2] | proc_23_TLF_FIFO_blk[2] | proc_23_input_sync_blk[2] | proc_23_output_sync_blk[2]);
    assign proc_23_data_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_n1_folded_gelu_dual_fu_523.grp_p_anonymous_namespace_n1_folded_gelu_dual_Pipeline_VITIS_LOOP_928_2_fu_100.expanded_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_n1_folded_gelu_dual_fu_523.grp_p_anonymous_namespace_n1_folded_gelu_dual_Pipeline_VITIS_LOOP_928_2_fu_100.expanded_b_blk_n);
    assign proc_23_data_PIPO_blk[3] = 1'b0;
    assign proc_23_start_FIFO_blk[3] = 1'b0;
    assign proc_23_TLF_FIFO_blk[3] = 1'b0;
    assign proc_23_input_sync_blk[3] = 1'b0;
    assign proc_23_output_sync_blk[3] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_23[3] = dl_detect_out ? proc_dep_vld_vec_23_reg[3] : (proc_23_data_FIFO_blk[3] | proc_23_data_PIPO_blk[3] | proc_23_start_FIFO_blk[3] | proc_23_TLF_FIFO_blk[3] | proc_23_input_sync_blk[3] | proc_23_output_sync_blk[3]);
    assign proc_23_data_FIFO_blk[4] = 1'b0;
    assign proc_23_data_PIPO_blk[4] = 1'b0;
    assign proc_23_start_FIFO_blk[4] = 1'b0;
    assign proc_23_TLF_FIFO_blk[4] = 1'b0;
    assign proc_23_input_sync_blk[4] = 1'b0;
    assign proc_23_output_sync_blk[4] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_23[4] = dl_detect_out ? proc_dep_vld_vec_23_reg[4] : (proc_23_data_FIFO_blk[4] | proc_23_data_PIPO_blk[4] | proc_23_start_FIFO_blk[4] | proc_23_TLF_FIFO_blk[4] | proc_23_input_sync_blk[4] | proc_23_output_sync_blk[4]);
    assign proc_23_data_FIFO_blk[5] = 1'b0;
    assign proc_23_data_PIPO_blk[5] = 1'b0;
    assign proc_23_start_FIFO_blk[5] = 1'b0;
    assign proc_23_TLF_FIFO_blk[5] = 1'b0;
    assign proc_23_input_sync_blk[5] = 1'b0;
    assign proc_23_output_sync_blk[5] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_23[5] = dl_detect_out ? proc_dep_vld_vec_23_reg[5] : (proc_23_data_FIFO_blk[5] | proc_23_data_PIPO_blk[5] | proc_23_start_FIFO_blk[5] | proc_23_TLF_FIFO_blk[5] | proc_23_input_sync_blk[5] | proc_23_output_sync_blk[5]);
    assign proc_23_data_FIFO_blk[6] = 1'b0;
    assign proc_23_data_PIPO_blk[6] = 1'b0;
    assign proc_23_start_FIFO_blk[6] = 1'b0;
    assign proc_23_TLF_FIFO_blk[6] = 1'b0;
    assign proc_23_input_sync_blk[6] = 1'b0;
    assign proc_23_output_sync_blk[6] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_23[6] = dl_detect_out ? proc_dep_vld_vec_23_reg[6] : (proc_23_data_FIFO_blk[6] | proc_23_data_PIPO_blk[6] | proc_23_start_FIFO_blk[6] | proc_23_TLF_FIFO_blk[6] | proc_23_input_sync_blk[6] | proc_23_output_sync_blk[6]);
    assign proc_23_data_FIFO_blk[7] = 1'b0;
    assign proc_23_data_PIPO_blk[7] = 1'b0;
    assign proc_23_start_FIFO_blk[7] = 1'b0;
    assign proc_23_TLF_FIFO_blk[7] = 1'b0;
    assign proc_23_input_sync_blk[7] = 1'b0;
    assign proc_23_output_sync_blk[7] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_23[7] = dl_detect_out ? proc_dep_vld_vec_23_reg[7] : (proc_23_data_FIFO_blk[7] | proc_23_data_PIPO_blk[7] | proc_23_start_FIFO_blk[7] | proc_23_TLF_FIFO_blk[7] | proc_23_input_sync_blk[7] | proc_23_output_sync_blk[7]);
    assign proc_23_data_FIFO_blk[8] = 1'b0;
    assign proc_23_data_PIPO_blk[8] = 1'b0;
    assign proc_23_start_FIFO_blk[8] = 1'b0;
    assign proc_23_TLF_FIFO_blk[8] = 1'b0;
    assign proc_23_input_sync_blk[8] = 1'b0;
    assign proc_23_output_sync_blk[8] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_23[8] = dl_detect_out ? proc_dep_vld_vec_23_reg[8] : (proc_23_data_FIFO_blk[8] | proc_23_data_PIPO_blk[8] | proc_23_start_FIFO_blk[8] | proc_23_TLF_FIFO_blk[8] | proc_23_input_sync_blk[8] | proc_23_output_sync_blk[8]);
    assign proc_23_data_FIFO_blk[9] = 1'b0;
    assign proc_23_data_PIPO_blk[9] = 1'b0;
    assign proc_23_start_FIFO_blk[9] = 1'b0;
    assign proc_23_TLF_FIFO_blk[9] = 1'b0;
    assign proc_23_input_sync_blk[9] = 1'b0;
    assign proc_23_output_sync_blk[9] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_23[9] = dl_detect_out ? proc_dep_vld_vec_23_reg[9] : (proc_23_data_FIFO_blk[9] | proc_23_data_PIPO_blk[9] | proc_23_start_FIFO_blk[9] | proc_23_TLF_FIFO_blk[9] | proc_23_input_sync_blk[9] | proc_23_output_sync_blk[9]);
    assign proc_23_data_FIFO_blk[10] = 1'b0;
    assign proc_23_data_PIPO_blk[10] = 1'b0;
    assign proc_23_start_FIFO_blk[10] = 1'b0;
    assign proc_23_TLF_FIFO_blk[10] = 1'b0;
    assign proc_23_input_sync_blk[10] = 1'b0;
    assign proc_23_output_sync_blk[10] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_23[10] = dl_detect_out ? proc_dep_vld_vec_23_reg[10] : (proc_23_data_FIFO_blk[10] | proc_23_data_PIPO_blk[10] | proc_23_start_FIFO_blk[10] | proc_23_TLF_FIFO_blk[10] | proc_23_input_sync_blk[10] | proc_23_output_sync_blk[10]);
    assign proc_23_data_FIFO_blk[11] = 1'b0;
    assign proc_23_data_PIPO_blk[11] = 1'b0;
    assign proc_23_start_FIFO_blk[11] = 1'b0;
    assign proc_23_TLF_FIFO_blk[11] = 1'b0;
    assign proc_23_input_sync_blk[11] = 1'b0;
    assign proc_23_output_sync_blk[11] = 1'b0 | (ap_done_reg_8 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_23[11] = dl_detect_out ? proc_dep_vld_vec_23_reg[11] : (proc_23_data_FIFO_blk[11] | proc_23_data_PIPO_blk[11] | proc_23_start_FIFO_blk[11] | proc_23_TLF_FIFO_blk[11] | proc_23_input_sync_blk[11] | proc_23_output_sync_blk[11]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_23_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_23_reg <= proc_dep_vld_vec_23;
        end
    end
    assign in_chan_dep_vld_vec_23[0] = dep_chan_vld_0_23;
    assign in_chan_dep_data_vec_23[38 : 0] = dep_chan_data_0_23;
    assign token_in_vec_23[0] = token_0_23;
    assign in_chan_dep_vld_vec_23[1] = dep_chan_vld_4_23;
    assign in_chan_dep_data_vec_23[77 : 39] = dep_chan_data_4_23;
    assign token_in_vec_23[1] = token_4_23;
    assign in_chan_dep_vld_vec_23[2] = dep_chan_vld_5_23;
    assign in_chan_dep_data_vec_23[116 : 78] = dep_chan_data_5_23;
    assign token_in_vec_23[2] = token_5_23;
    assign in_chan_dep_vld_vec_23[3] = dep_chan_vld_8_23;
    assign in_chan_dep_data_vec_23[155 : 117] = dep_chan_data_8_23;
    assign token_in_vec_23[3] = token_8_23;
    assign in_chan_dep_vld_vec_23[4] = dep_chan_vld_9_23;
    assign in_chan_dep_data_vec_23[194 : 156] = dep_chan_data_9_23;
    assign token_in_vec_23[4] = token_9_23;
    assign in_chan_dep_vld_vec_23[5] = dep_chan_vld_10_23;
    assign in_chan_dep_data_vec_23[233 : 195] = dep_chan_data_10_23;
    assign token_in_vec_23[5] = token_10_23;
    assign in_chan_dep_vld_vec_23[6] = dep_chan_vld_15_23;
    assign in_chan_dep_data_vec_23[272 : 234] = dep_chan_data_15_23;
    assign token_in_vec_23[6] = token_15_23;
    assign in_chan_dep_vld_vec_23[7] = dep_chan_vld_20_23;
    assign in_chan_dep_data_vec_23[311 : 273] = dep_chan_data_20_23;
    assign token_in_vec_23[7] = token_20_23;
    assign in_chan_dep_vld_vec_23[8] = dep_chan_vld_21_23;
    assign in_chan_dep_data_vec_23[350 : 312] = dep_chan_data_21_23;
    assign token_in_vec_23[8] = token_21_23;
    assign in_chan_dep_vld_vec_23[9] = dep_chan_vld_22_23;
    assign in_chan_dep_data_vec_23[389 : 351] = dep_chan_data_22_23;
    assign token_in_vec_23[9] = token_22_23;
    assign in_chan_dep_vld_vec_23[10] = dep_chan_vld_31_23;
    assign in_chan_dep_data_vec_23[428 : 390] = dep_chan_data_31_23;
    assign token_in_vec_23[10] = token_31_23;
    assign in_chan_dep_vld_vec_23[11] = dep_chan_vld_38_23;
    assign in_chan_dep_data_vec_23[467 : 429] = dep_chan_data_38_23;
    assign token_in_vec_23[11] = token_38_23;
    assign dep_chan_vld_23_0 = out_chan_dep_vld_vec_23[0];
    assign dep_chan_data_23_0 = out_chan_dep_data_23;
    assign token_23_0 = token_out_vec_23[0];
    assign dep_chan_vld_23_15 = out_chan_dep_vld_vec_23[1];
    assign dep_chan_data_23_15 = out_chan_dep_data_23;
    assign token_23_15 = token_out_vec_23[1];
    assign dep_chan_vld_23_22 = out_chan_dep_vld_vec_23[2];
    assign dep_chan_data_23_22 = out_chan_dep_data_23;
    assign token_23_22 = token_out_vec_23[2];
    assign dep_chan_vld_23_31 = out_chan_dep_vld_vec_23[3];
    assign dep_chan_data_23_31 = out_chan_dep_data_23;
    assign token_23_31 = token_out_vec_23[3];
    assign dep_chan_vld_23_4 = out_chan_dep_vld_vec_23[4];
    assign dep_chan_data_23_4 = out_chan_dep_data_23;
    assign token_23_4 = token_out_vec_23[4];
    assign dep_chan_vld_23_5 = out_chan_dep_vld_vec_23[5];
    assign dep_chan_data_23_5 = out_chan_dep_data_23;
    assign token_23_5 = token_out_vec_23[5];
    assign dep_chan_vld_23_8 = out_chan_dep_vld_vec_23[6];
    assign dep_chan_data_23_8 = out_chan_dep_data_23;
    assign token_23_8 = token_out_vec_23[6];
    assign dep_chan_vld_23_9 = out_chan_dep_vld_vec_23[7];
    assign dep_chan_data_23_9 = out_chan_dep_data_23;
    assign token_23_9 = token_out_vec_23[7];
    assign dep_chan_vld_23_10 = out_chan_dep_vld_vec_23[8];
    assign dep_chan_data_23_10 = out_chan_dep_data_23;
    assign token_23_10 = token_out_vec_23[8];
    assign dep_chan_vld_23_20 = out_chan_dep_vld_vec_23[9];
    assign dep_chan_data_23_20 = out_chan_dep_data_23;
    assign token_23_20 = token_out_vec_23[9];
    assign dep_chan_vld_23_21 = out_chan_dep_vld_vec_23[10];
    assign dep_chan_data_23_21 = out_chan_dep_data_23;
    assign token_23_21 = token_out_vec_23[10];
    assign dep_chan_vld_23_38 = out_chan_dep_vld_vec_23[11];
    assign dep_chan_data_23_38 = out_chan_dep_data_23;
    assign token_23_38 = token_out_vec_23[11];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 24, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_24 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_24),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_24),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_24),
        .token_in_vec(token_in_vec_24),
        .dl_detect_in(dl_detect_out),
        .origin(origin[24]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_24),
        .out_chan_dep_data(out_chan_dep_data_24),
        .token_out_vec(token_out_vec_24),
        .dl_detect_out(dl_in_vec[24]));

    assign proc_24_data_FIFO_blk[0] = 1'b0;
    assign proc_24_data_PIPO_blk[0] = 1'b0;
    assign proc_24_start_FIFO_blk[0] = 1'b0;
    assign proc_24_TLF_FIFO_blk[0] = 1'b0;
    assign proc_24_input_sync_blk[0] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.ap_sync_p_anonymous_namespace_pointwise_pair_expand_0_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.ap_sync_p_anonymous_namespace_pointwise_pair_expand_1_U0_ap_ready);
    assign proc_24_output_sync_blk[0] = 1'b0 | (ap_done_reg_19 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.ap_done);
    assign proc_dep_vld_vec_24[0] = dl_detect_out ? proc_dep_vld_vec_24_reg[0] : (proc_24_data_FIFO_blk[0] | proc_24_data_PIPO_blk[0] | proc_24_start_FIFO_blk[0] | proc_24_TLF_FIFO_blk[0] | proc_24_input_sync_blk[0] | proc_24_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_24_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_24_reg <= proc_dep_vld_vec_24;
        end
    end
    assign in_chan_dep_vld_vec_24[0] = dep_chan_vld_27_24;
    assign in_chan_dep_data_vec_24[38 : 0] = dep_chan_data_27_24;
    assign token_in_vec_24[0] = token_27_24;
    assign dep_chan_vld_24_27 = out_chan_dep_vld_vec_24[0];
    assign dep_chan_data_24_27 = out_chan_dep_data_24;
    assign token_24_27 = token_out_vec_24[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 25, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_25 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_25),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_25),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_25),
        .token_in_vec(token_in_vec_25),
        .dl_detect_in(dl_detect_out),
        .origin(origin[25]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_25),
        .out_chan_dep_data(out_chan_dep_data_25),
        .token_out_vec(token_out_vec_25),
        .dl_detect_out(dl_in_vec[25]));

    assign proc_25_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0.grp_p_anonymous_namespace_pointwise_compute_0_false_256_Pipeline_VITIS_LOOP_101_9_fu_463.columns_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0.scales_blk_n);
    assign proc_25_data_PIPO_blk[0] = 1'b0;
    assign proc_25_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.start_for_p_anonymous_namespace_pointwise_post_expand_0_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_compute_0_false_256_U0.real_start & (trans_in_cnt_9 == trans_out_cnt_9) & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.start_for_p_anonymous_namespace_pointwise_post_expand_0_U0_U.if_read);
    assign proc_25_TLF_FIFO_blk[0] = 1'b0;
    assign proc_25_input_sync_blk[0] = 1'b0;
    assign proc_25_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_25[0] = dl_detect_out ? proc_dep_vld_vec_25_reg[0] : (proc_25_data_FIFO_blk[0] | proc_25_data_PIPO_blk[0] | proc_25_start_FIFO_blk[0] | proc_25_TLF_FIFO_blk[0] | proc_25_input_sync_blk[0] | proc_25_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_25_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_25_reg <= proc_dep_vld_vec_25;
        end
    end
    assign in_chan_dep_vld_vec_25[0] = dep_chan_vld_26_25;
    assign in_chan_dep_data_vec_25[38 : 0] = dep_chan_data_26_25;
    assign token_in_vec_25[0] = token_26_25;
    assign dep_chan_vld_25_26 = out_chan_dep_vld_vec_25[0];
    assign dep_chan_data_25_26 = out_chan_dep_data_25;
    assign token_25_26 = token_out_vec_25[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_post_expand_0_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 26, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_26 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_26),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_26),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_26),
        .token_in_vec(token_in_vec_26),
        .dl_detect_in(dl_detect_out),
        .origin(origin[26]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_26),
        .out_chan_dep_data(out_chan_dep_data_26),
        .token_out_vec(token_out_vec_26),
        .dl_detect_out(dl_in_vec[26]));

    assign proc_26_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_post_expand_0_U0.grp_p_anonymous_namespace_pointwise_post_expand_0_Pipeline_VITIS_LOOP_233_3_fu_228.columns_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_post_expand_0_U0.scales_blk_n);
    assign proc_26_data_PIPO_blk[0] = 1'b0;
    assign proc_26_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.start_for_p_anonymous_namespace_pointwise_post_expand_0_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.p_anonymous_namespace_pointwise_post_expand_0_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.start_for_p_anonymous_namespace_pointwise_post_expand_0_U0_U.if_write);
    assign proc_26_TLF_FIFO_blk[0] = 1'b0;
    assign proc_26_input_sync_blk[0] = 1'b0;
    assign proc_26_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_26[0] = dl_detect_out ? proc_dep_vld_vec_26_reg[0] : (proc_26_data_FIFO_blk[0] | proc_26_data_PIPO_blk[0] | proc_26_start_FIFO_blk[0] | proc_26_TLF_FIFO_blk[0] | proc_26_input_sync_blk[0] | proc_26_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_26_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_26_reg <= proc_dep_vld_vec_26;
        end
    end
    assign in_chan_dep_vld_vec_26[0] = dep_chan_vld_25_26;
    assign in_chan_dep_data_vec_26[38 : 0] = dep_chan_data_25_26;
    assign token_in_vec_26[0] = token_25_26;
    assign dep_chan_vld_26_25 = out_chan_dep_vld_vec_26[0];
    assign dep_chan_data_26_25 = out_chan_dep_data_26;
    assign token_26_25 = token_out_vec_26[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 27, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_27 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_27),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_27),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_27),
        .token_in_vec(token_in_vec_27),
        .dl_detect_in(dl_detect_out),
        .origin(origin[27]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_27),
        .out_chan_dep_data(out_chan_dep_data_27),
        .token_out_vec(token_out_vec_27),
        .dl_detect_out(dl_in_vec[27]));

    assign proc_27_data_FIFO_blk[0] = 1'b0;
    assign proc_27_data_PIPO_blk[0] = 1'b0;
    assign proc_27_start_FIFO_blk[0] = 1'b0;
    assign proc_27_TLF_FIFO_blk[0] = 1'b0;
    assign proc_27_input_sync_blk[0] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.ap_sync_p_anonymous_namespace_pointwise_pair_expand_1_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.ap_sync_p_anonymous_namespace_pointwise_pair_expand_0_U0_ap_ready);
    assign proc_27_output_sync_blk[0] = 1'b0 | (ap_done_reg_20 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_0_U0.ap_done);
    assign proc_dep_vld_vec_27[0] = dl_detect_out ? proc_dep_vld_vec_27_reg[0] : (proc_27_data_FIFO_blk[0] | proc_27_data_PIPO_blk[0] | proc_27_start_FIFO_blk[0] | proc_27_TLF_FIFO_blk[0] | proc_27_input_sync_blk[0] | proc_27_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_27_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_27_reg <= proc_dep_vld_vec_27;
        end
    end
    assign in_chan_dep_vld_vec_27[0] = dep_chan_vld_24_27;
    assign in_chan_dep_data_vec_27[38 : 0] = dep_chan_data_24_27;
    assign token_in_vec_27[0] = token_24_27;
    assign dep_chan_vld_27_24 = out_chan_dep_vld_vec_27[0];
    assign dep_chan_data_27_24 = out_chan_dep_data_27;
    assign token_27_24 = token_out_vec_27[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 28, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_28 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_28),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_28),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_28),
        .token_in_vec(token_in_vec_28),
        .dl_detect_in(dl_detect_out),
        .origin(origin[28]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_28),
        .out_chan_dep_data(out_chan_dep_data_28),
        .token_out_vec(token_out_vec_28),
        .dl_detect_out(dl_in_vec[28]));

    assign proc_28_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0.grp_p_anonymous_namespace_pointwise_compute_1_false_256_Pipeline_VITIS_LOOP_101_9_fu_463.columns_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0.scales_blk_n);
    assign proc_28_data_PIPO_blk[0] = 1'b0;
    assign proc_28_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.start_for_p_anonymous_namespace_pointwise_post_expand_1_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_compute_1_false_256_U0.real_start & (trans_in_cnt_10 == trans_out_cnt_10) & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.start_for_p_anonymous_namespace_pointwise_post_expand_1_U0_U.if_read);
    assign proc_28_TLF_FIFO_blk[0] = 1'b0;
    assign proc_28_input_sync_blk[0] = 1'b0;
    assign proc_28_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_28[0] = dl_detect_out ? proc_dep_vld_vec_28_reg[0] : (proc_28_data_FIFO_blk[0] | proc_28_data_PIPO_blk[0] | proc_28_start_FIFO_blk[0] | proc_28_TLF_FIFO_blk[0] | proc_28_input_sync_blk[0] | proc_28_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_28_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_28_reg <= proc_dep_vld_vec_28;
        end
    end
    assign in_chan_dep_vld_vec_28[0] = dep_chan_vld_29_28;
    assign in_chan_dep_data_vec_28[38 : 0] = dep_chan_data_29_28;
    assign token_in_vec_28[0] = token_29_28;
    assign dep_chan_vld_28_29 = out_chan_dep_vld_vec_28[0];
    assign dep_chan_data_28_29 = out_chan_dep_data_28;
    assign token_28_29 = token_out_vec_28[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_post_expand_1_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 29, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_29 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_29),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_29),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_29),
        .token_in_vec(token_in_vec_29),
        .dl_detect_in(dl_detect_out),
        .origin(origin[29]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_29),
        .out_chan_dep_data(out_chan_dep_data_29),
        .token_out_vec(token_out_vec_29),
        .dl_detect_out(dl_in_vec[29]));

    assign proc_29_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_post_expand_1_U0.grp_p_anonymous_namespace_pointwise_post_expand_1_Pipeline_VITIS_LOOP_233_3_fu_228.columns_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_post_expand_1_U0.scales_blk_n);
    assign proc_29_data_PIPO_blk[0] = 1'b0;
    assign proc_29_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.start_for_p_anonymous_namespace_pointwise_post_expand_1_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.p_anonymous_namespace_pointwise_post_expand_1_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.grp_p_anonymous_namespace_pointwise_expand_dual_fu_581.p_anonymous_namespace_pointwise_pair_expand_1_U0.start_for_p_anonymous_namespace_pointwise_post_expand_1_U0_U.if_write);
    assign proc_29_TLF_FIFO_blk[0] = 1'b0;
    assign proc_29_input_sync_blk[0] = 1'b0;
    assign proc_29_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_29[0] = dl_detect_out ? proc_dep_vld_vec_29_reg[0] : (proc_29_data_FIFO_blk[0] | proc_29_data_PIPO_blk[0] | proc_29_start_FIFO_blk[0] | proc_29_TLF_FIFO_blk[0] | proc_29_input_sync_blk[0] | proc_29_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_29_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_29_reg <= proc_dep_vld_vec_29;
        end
    end
    assign in_chan_dep_vld_vec_29[0] = dep_chan_vld_28_29;
    assign in_chan_dep_data_vec_29[38 : 0] = dep_chan_data_28_29;
    assign token_in_vec_29[0] = token_28_29;
    assign dep_chan_vld_29_28 = out_chan_dep_vld_vec_29[0];
    assign dep_chan_data_29_28 = out_chan_dep_data_29;
    assign token_29_28 = token_out_vec_29[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 30, 2, 2) cnn_pipeline_v10_hls_deadlock_detect_unit_30 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_30),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_30),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_30),
        .token_in_vec(token_in_vec_30),
        .dl_detect_in(dl_detect_out),
        .origin(origin[30]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_30),
        .out_chan_dep_data(out_chan_dep_data_30),
        .token_out_vec(token_out_vec_30),
        .dl_detect_out(dl_in_vec[30]));

    assign proc_30_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_U0.p2_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_U0.grp_p_anonymous_namespace_weight_broadcast_Pipeline_VITIS_LOOP_876_4_VITIS_LOOP_878_5_fu_243.p2_data_1_blk_n);
    assign proc_30_data_PIPO_blk[0] = 1'b0;
    assign proc_30_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_weight_broadcast_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_weight_broadcast_U0_U.if_write);
    assign proc_30_TLF_FIFO_blk[0] = 1'b0;
    assign proc_30_input_sync_blk[0] = 1'b0;
    assign proc_30_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_30[0] = dl_detect_out ? proc_dep_vld_vec_30_reg[0] : (proc_30_data_FIFO_blk[0] | proc_30_data_PIPO_blk[0] | proc_30_start_FIFO_blk[0] | proc_30_TLF_FIFO_blk[0] | proc_30_input_sync_blk[0] | proc_30_output_sync_blk[0]);
    assign proc_30_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_U0.grp_p_anonymous_namespace_weight_broadcast_Pipeline_VITIS_LOOP_876_4_VITIS_LOOP_878_5_fu_243.wt2_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_weight_broadcast_U0.grp_p_anonymous_namespace_weight_broadcast_Pipeline_VITIS_LOOP_876_4_VITIS_LOOP_878_5_fu_243.wt2_b_blk_n);
    assign proc_30_data_PIPO_blk[1] = 1'b0;
    assign proc_30_start_FIFO_blk[1] = 1'b0;
    assign proc_30_TLF_FIFO_blk[1] = 1'b0;
    assign proc_30_input_sync_blk[1] = 1'b0;
    assign proc_30_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_30[1] = dl_detect_out ? proc_dep_vld_vec_30_reg[1] : (proc_30_data_FIFO_blk[1] | proc_30_data_PIPO_blk[1] | proc_30_start_FIFO_blk[1] | proc_30_TLF_FIFO_blk[1] | proc_30_input_sync_blk[1] | proc_30_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_30_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_30_reg <= proc_dep_vld_vec_30;
        end
    end
    assign in_chan_dep_vld_vec_30[0] = dep_chan_vld_1_30;
    assign in_chan_dep_data_vec_30[38 : 0] = dep_chan_data_1_30;
    assign token_in_vec_30[0] = token_1_30;
    assign in_chan_dep_vld_vec_30[1] = dep_chan_vld_31_30;
    assign in_chan_dep_data_vec_30[77 : 39] = dep_chan_data_31_30;
    assign token_in_vec_30[1] = token_31_30;
    assign dep_chan_vld_30_1 = out_chan_dep_vld_vec_30[0];
    assign dep_chan_data_30_1 = out_chan_dep_data_30;
    assign token_30_1 = token_out_vec_30[0];
    assign dep_chan_vld_30_31 = out_chan_dep_vld_vec_30[1];
    assign dep_chan_data_30_31 = out_chan_dep_data_30;
    assign token_30_31 = token_out_vec_30[1];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 31, 16, 16) cnn_pipeline_v10_hls_deadlock_detect_unit_31 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_31),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_31),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_31),
        .token_in_vec(token_in_vec_31),
        .dl_detect_in(dl_detect_out),
        .origin(origin[31]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_31),
        .out_chan_dep_data(out_chan_dep_data_31),
        .token_out_vec(token_out_vec_31),
        .dl_detect_out(dl_in_vec[31]));

    assign proc_31_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.p2_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_load_coeff_5_fu_370.p2_cmd_0_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_load_coeff_5_fu_370.p2_data_0_blk_n);
    assign proc_31_data_PIPO_blk[0] = 1'b0;
    assign proc_31_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_pointwise2_chain_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_pointwise2_chain_U0_U.if_write);
    assign proc_31_TLF_FIFO_blk[0] = 1'b0;
    assign proc_31_input_sync_blk[0] = 1'b0;
    assign proc_31_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_31[0] = dl_detect_out ? proc_dep_vld_vec_31_reg[0] : (proc_31_data_FIFO_blk[0] | proc_31_data_PIPO_blk[0] | proc_31_start_FIFO_blk[0] | proc_31_TLF_FIFO_blk[0] | proc_31_input_sync_blk[0] | proc_31_output_sync_blk[0]);
    assign proc_31_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.grp_p_anonymous_namespace_pointwise_compute_final_streaming_Pipeline_VITIS_LOOP_155_3_1_fu_588.expanded_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.grp_p_anonymous_namespace_pointwise_compute_final_streaming_Pipeline_VITIS_LOOP_155_3_fu_588.expanded_b_blk_n);
    assign proc_31_data_PIPO_blk[1] = 1'b0;
    assign proc_31_start_FIFO_blk[1] = 1'b0;
    assign proc_31_TLF_FIFO_blk[1] = 1'b0;
    assign proc_31_input_sync_blk[1] = 1'b0;
    assign proc_31_output_sync_blk[1] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_31[1] = dl_detect_out ? proc_dep_vld_vec_31_reg[1] : (proc_31_data_FIFO_blk[1] | proc_31_data_PIPO_blk[1] | proc_31_start_FIFO_blk[1] | proc_31_TLF_FIFO_blk[1] | proc_31_input_sync_blk[1] | proc_31_output_sync_blk[1]);
    assign proc_31_data_FIFO_blk[2] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.wt2_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.wt2_b_blk_n);
    assign proc_31_data_PIPO_blk[2] = 1'b0;
    assign proc_31_start_FIFO_blk[2] = 1'b0;
    assign proc_31_TLF_FIFO_blk[2] = 1'b0;
    assign proc_31_input_sync_blk[2] = 1'b0;
    assign proc_31_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_31[2] = dl_detect_out ? proc_dep_vld_vec_31_reg[2] : (proc_31_data_FIFO_blk[2] | proc_31_data_PIPO_blk[2] | proc_31_start_FIFO_blk[2] | proc_31_TLF_FIFO_blk[2] | proc_31_input_sync_blk[2] | proc_31_output_sync_blk[2]);
    assign proc_31_data_FIFO_blk[3] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.a_read_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.a_read_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.grp_p_anonymous_namespace_pointwise_post_final_Pipeline_VITIS_LOOP_299_5_1_fu_404.a_read_data_1_blk_n);
    assign proc_31_data_PIPO_blk[3] = 1'b0;
    assign proc_31_start_FIFO_blk[3] = 1'b0;
    assign proc_31_TLF_FIFO_blk[3] = 1'b0;
    assign proc_31_input_sync_blk[3] = 1'b0;
    assign proc_31_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_31[3] = dl_detect_out ? proc_dep_vld_vec_31_reg[3] : (proc_31_data_FIFO_blk[3] | proc_31_data_PIPO_blk[3] | proc_31_start_FIFO_blk[3] | proc_31_TLF_FIFO_blk[3] | proc_31_input_sync_blk[3] | proc_31_output_sync_blk[3]);
    assign proc_31_data_FIFO_blk[4] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.residual_ready_a_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.residual_release_a_blk_n);
    assign proc_31_data_PIPO_blk[4] = 1'b0;
    assign proc_31_start_FIFO_blk[4] = 1'b0;
    assign proc_31_TLF_FIFO_blk[4] = 1'b0;
    assign proc_31_input_sync_blk[4] = 1'b0;
    assign proc_31_output_sync_blk[4] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_31[4] = dl_detect_out ? proc_dep_vld_vec_31_reg[4] : (proc_31_data_FIFO_blk[4] | proc_31_data_PIPO_blk[4] | proc_31_start_FIFO_blk[4] | proc_31_TLF_FIFO_blk[4] | proc_31_input_sync_blk[4] | proc_31_output_sync_blk[4]);
    assign proc_31_data_FIFO_blk[5] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.a_write_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.grp_p_anonymous_namespace_pointwise_post_final_Outline_VITIS_LOOP_307_6_1_fu_412.grp_p_anonymous_namespace_pointwise_post_final_Pipeline_VITIS_LOOP_315_7_1_fu_202.a_write_data_1_blk_n);
    assign proc_31_data_PIPO_blk[5] = 1'b0;
    assign proc_31_start_FIFO_blk[5] = 1'b0;
    assign proc_31_TLF_FIFO_blk[5] = 1'b0;
    assign proc_31_input_sync_blk[5] = 1'b0;
    assign proc_31_output_sync_blk[5] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_31[5] = dl_detect_out ? proc_dep_vld_vec_31_reg[5] : (proc_31_data_FIFO_blk[5] | proc_31_data_PIPO_blk[5] | proc_31_start_FIFO_blk[5] | proc_31_TLF_FIFO_blk[5] | proc_31_input_sync_blk[5] | proc_31_output_sync_blk[5]);
    assign proc_31_data_FIFO_blk[6] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.row_ready_a_blk_n);
    assign proc_31_data_PIPO_blk[6] = 1'b0;
    assign proc_31_start_FIFO_blk[6] = 1'b0;
    assign proc_31_TLF_FIFO_blk[6] = 1'b0;
    assign proc_31_input_sync_blk[6] = 1'b0;
    assign proc_31_output_sync_blk[6] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_31[6] = dl_detect_out ? proc_dep_vld_vec_31_reg[6] : (proc_31_data_FIFO_blk[6] | proc_31_data_PIPO_blk[6] | proc_31_start_FIFO_blk[6] | proc_31_TLF_FIFO_blk[6] | proc_31_input_sync_blk[6] | proc_31_output_sync_blk[6]);
    assign proc_31_data_FIFO_blk[7] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.scale_req_a_2_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.grp_p_anonymous_namespace_pointwise_post_final_Outline_VITIS_LOOP_307_6_1_fu_412.grp_p_anonymous_namespace_pointwise_post_final_Pipeline_VITIS_LOOP_315_7_1_fu_202.scale_ret_a_2_blk_n);
    assign proc_31_data_PIPO_blk[7] = 1'b0;
    assign proc_31_start_FIFO_blk[7] = 1'b0;
    assign proc_31_TLF_FIFO_blk[7] = 1'b0;
    assign proc_31_input_sync_blk[7] = 1'b0;
    assign proc_31_output_sync_blk[7] = 1'b0;
    assign proc_dep_vld_vec_31[7] = dl_detect_out ? proc_dep_vld_vec_31_reg[7] : (proc_31_data_FIFO_blk[7] | proc_31_data_PIPO_blk[7] | proc_31_start_FIFO_blk[7] | proc_31_TLF_FIFO_blk[7] | proc_31_input_sync_blk[7] | proc_31_output_sync_blk[7]);
    assign proc_31_data_FIFO_blk[8] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.b_read_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.b_read_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.grp_p_anonymous_namespace_pointwise_post_final_Pipeline_VITIS_LOOP_299_5_fu_404.b_read_data_1_blk_n);
    assign proc_31_data_PIPO_blk[8] = 1'b0;
    assign proc_31_start_FIFO_blk[8] = 1'b0;
    assign proc_31_TLF_FIFO_blk[8] = 1'b0;
    assign proc_31_input_sync_blk[8] = 1'b0;
    assign proc_31_output_sync_blk[8] = 1'b0;
    assign proc_dep_vld_vec_31[8] = dl_detect_out ? proc_dep_vld_vec_31_reg[8] : (proc_31_data_FIFO_blk[8] | proc_31_data_PIPO_blk[8] | proc_31_start_FIFO_blk[8] | proc_31_TLF_FIFO_blk[8] | proc_31_input_sync_blk[8] | proc_31_output_sync_blk[8]);
    assign proc_31_data_FIFO_blk[9] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.residual_ready_b_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.residual_release_b_blk_n);
    assign proc_31_data_PIPO_blk[9] = 1'b0;
    assign proc_31_start_FIFO_blk[9] = 1'b0;
    assign proc_31_TLF_FIFO_blk[9] = 1'b0;
    assign proc_31_input_sync_blk[9] = 1'b0;
    assign proc_31_output_sync_blk[9] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_31[9] = dl_detect_out ? proc_dep_vld_vec_31_reg[9] : (proc_31_data_FIFO_blk[9] | proc_31_data_PIPO_blk[9] | proc_31_start_FIFO_blk[9] | proc_31_TLF_FIFO_blk[9] | proc_31_input_sync_blk[9] | proc_31_output_sync_blk[9]);
    assign proc_31_data_FIFO_blk[10] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.b_write_cmd_1_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.grp_p_anonymous_namespace_pointwise_post_final_Outline_VITIS_LOOP_307_6_fu_412.grp_p_anonymous_namespace_pointwise_post_final_Pipeline_VITIS_LOOP_315_7_fu_210.b_write_data_1_blk_n);
    assign proc_31_data_PIPO_blk[10] = 1'b0;
    assign proc_31_start_FIFO_blk[10] = 1'b0;
    assign proc_31_TLF_FIFO_blk[10] = 1'b0;
    assign proc_31_input_sync_blk[10] = 1'b0;
    assign proc_31_output_sync_blk[10] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_31[10] = dl_detect_out ? proc_dep_vld_vec_31_reg[10] : (proc_31_data_FIFO_blk[10] | proc_31_data_PIPO_blk[10] | proc_31_start_FIFO_blk[10] | proc_31_TLF_FIFO_blk[10] | proc_31_input_sync_blk[10] | proc_31_output_sync_blk[10]);
    assign proc_31_data_FIFO_blk[11] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.row_ready_b_blk_n);
    assign proc_31_data_PIPO_blk[11] = 1'b0;
    assign proc_31_start_FIFO_blk[11] = 1'b0;
    assign proc_31_TLF_FIFO_blk[11] = 1'b0;
    assign proc_31_input_sync_blk[11] = 1'b0;
    assign proc_31_output_sync_blk[11] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_31[11] = dl_detect_out ? proc_dep_vld_vec_31_reg[11] : (proc_31_data_FIFO_blk[11] | proc_31_data_PIPO_blk[11] | proc_31_start_FIFO_blk[11] | proc_31_TLF_FIFO_blk[11] | proc_31_input_sync_blk[11] | proc_31_output_sync_blk[11]);
    assign proc_31_data_FIFO_blk[12] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.scale_req_b_2_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.grp_p_anonymous_namespace_pointwise_post_final_Outline_VITIS_LOOP_307_6_fu_412.grp_p_anonymous_namespace_pointwise_post_final_Pipeline_VITIS_LOOP_315_7_fu_210.scale_ret_b_2_blk_n);
    assign proc_31_data_PIPO_blk[12] = 1'b0;
    assign proc_31_start_FIFO_blk[12] = 1'b0;
    assign proc_31_TLF_FIFO_blk[12] = 1'b0;
    assign proc_31_input_sync_blk[12] = 1'b0;
    assign proc_31_output_sync_blk[12] = 1'b0;
    assign proc_dep_vld_vec_31[12] = dl_detect_out ? proc_dep_vld_vec_31_reg[12] : (proc_31_data_FIFO_blk[12] | proc_31_data_PIPO_blk[12] | proc_31_start_FIFO_blk[12] | proc_31_TLF_FIFO_blk[12] | proc_31_input_sync_blk[12] | proc_31_output_sync_blk[12]);
    assign proc_31_data_FIFO_blk[13] = 1'b0;
    assign proc_31_data_PIPO_blk[13] = 1'b0;
    assign proc_31_start_FIFO_blk[13] = 1'b0;
    assign proc_31_TLF_FIFO_blk[13] = 1'b0;
    assign proc_31_input_sync_blk[13] = 1'b0;
    assign proc_31_output_sync_blk[13] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_31[13] = dl_detect_out ? proc_dep_vld_vec_31_reg[13] : (proc_31_data_FIFO_blk[13] | proc_31_data_PIPO_blk[13] | proc_31_start_FIFO_blk[13] | proc_31_TLF_FIFO_blk[13] | proc_31_input_sync_blk[13] | proc_31_output_sync_blk[13]);
    assign proc_31_data_FIFO_blk[14] = 1'b0;
    assign proc_31_data_PIPO_blk[14] = 1'b0;
    assign proc_31_start_FIFO_blk[14] = 1'b0;
    assign proc_31_TLF_FIFO_blk[14] = 1'b0;
    assign proc_31_input_sync_blk[14] = 1'b0;
    assign proc_31_output_sync_blk[14] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_31[14] = dl_detect_out ? proc_dep_vld_vec_31_reg[14] : (proc_31_data_FIFO_blk[14] | proc_31_data_PIPO_blk[14] | proc_31_start_FIFO_blk[14] | proc_31_TLF_FIFO_blk[14] | proc_31_input_sync_blk[14] | proc_31_output_sync_blk[14]);
    assign proc_31_data_FIFO_blk[15] = 1'b0;
    assign proc_31_data_PIPO_blk[15] = 1'b0;
    assign proc_31_start_FIFO_blk[15] = 1'b0;
    assign proc_31_TLF_FIFO_blk[15] = 1'b0;
    assign proc_31_input_sync_blk[15] = 1'b0;
    assign proc_31_output_sync_blk[15] = 1'b0 | (ap_done_reg_9 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done);
    assign proc_dep_vld_vec_31[15] = dl_detect_out ? proc_dep_vld_vec_31_reg[15] : (proc_31_data_FIFO_blk[15] | proc_31_data_PIPO_blk[15] | proc_31_start_FIFO_blk[15] | proc_31_TLF_FIFO_blk[15] | proc_31_input_sync_blk[15] | proc_31_output_sync_blk[15]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_31_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_31_reg <= proc_dep_vld_vec_31;
        end
    end
    assign in_chan_dep_vld_vec_31[0] = dep_chan_vld_1_31;
    assign in_chan_dep_data_vec_31[38 : 0] = dep_chan_data_1_31;
    assign token_in_vec_31[0] = token_1_31;
    assign in_chan_dep_vld_vec_31[1] = dep_chan_vld_2_31;
    assign in_chan_dep_data_vec_31[77 : 39] = dep_chan_data_2_31;
    assign token_in_vec_31[1] = token_2_31;
    assign in_chan_dep_vld_vec_31[2] = dep_chan_vld_3_31;
    assign in_chan_dep_data_vec_31[116 : 78] = dep_chan_data_3_31;
    assign token_in_vec_31[2] = token_3_31;
    assign in_chan_dep_vld_vec_31[3] = dep_chan_vld_4_31;
    assign in_chan_dep_data_vec_31[155 : 117] = dep_chan_data_4_31;
    assign token_in_vec_31[3] = token_4_31;
    assign in_chan_dep_vld_vec_31[4] = dep_chan_vld_5_31;
    assign in_chan_dep_data_vec_31[194 : 156] = dep_chan_data_5_31;
    assign token_in_vec_31[4] = token_5_31;
    assign in_chan_dep_vld_vec_31[5] = dep_chan_vld_6_31;
    assign in_chan_dep_data_vec_31[233 : 195] = dep_chan_data_6_31;
    assign token_in_vec_31[5] = token_6_31;
    assign in_chan_dep_vld_vec_31[6] = dep_chan_vld_7_31;
    assign in_chan_dep_data_vec_31[272 : 234] = dep_chan_data_7_31;
    assign token_in_vec_31[6] = token_7_31;
    assign in_chan_dep_vld_vec_31[7] = dep_chan_vld_8_31;
    assign in_chan_dep_data_vec_31[311 : 273] = dep_chan_data_8_31;
    assign token_in_vec_31[7] = token_8_31;
    assign in_chan_dep_vld_vec_31[8] = dep_chan_vld_9_31;
    assign in_chan_dep_data_vec_31[350 : 312] = dep_chan_data_9_31;
    assign token_in_vec_31[8] = token_9_31;
    assign in_chan_dep_vld_vec_31[9] = dep_chan_vld_10_31;
    assign in_chan_dep_data_vec_31[389 : 351] = dep_chan_data_10_31;
    assign token_in_vec_31[9] = token_10_31;
    assign in_chan_dep_vld_vec_31[10] = dep_chan_vld_15_31;
    assign in_chan_dep_data_vec_31[428 : 390] = dep_chan_data_15_31;
    assign token_in_vec_31[10] = token_15_31;
    assign in_chan_dep_vld_vec_31[11] = dep_chan_vld_20_31;
    assign in_chan_dep_data_vec_31[467 : 429] = dep_chan_data_20_31;
    assign token_in_vec_31[11] = token_20_31;
    assign in_chan_dep_vld_vec_31[12] = dep_chan_vld_21_31;
    assign in_chan_dep_data_vec_31[506 : 468] = dep_chan_data_21_31;
    assign token_in_vec_31[12] = token_21_31;
    assign in_chan_dep_vld_vec_31[13] = dep_chan_vld_23_31;
    assign in_chan_dep_data_vec_31[545 : 507] = dep_chan_data_23_31;
    assign token_in_vec_31[13] = token_23_31;
    assign in_chan_dep_vld_vec_31[14] = dep_chan_vld_30_31;
    assign in_chan_dep_data_vec_31[584 : 546] = dep_chan_data_30_31;
    assign token_in_vec_31[14] = token_30_31;
    assign in_chan_dep_vld_vec_31[15] = dep_chan_vld_38_31;
    assign in_chan_dep_data_vec_31[623 : 585] = dep_chan_data_38_31;
    assign token_in_vec_31[15] = token_38_31;
    assign dep_chan_vld_31_1 = out_chan_dep_vld_vec_31[0];
    assign dep_chan_data_31_1 = out_chan_dep_data_31;
    assign token_31_1 = token_out_vec_31[0];
    assign dep_chan_vld_31_23 = out_chan_dep_vld_vec_31[1];
    assign dep_chan_data_31_23 = out_chan_dep_data_31;
    assign token_31_23 = token_out_vec_31[1];
    assign dep_chan_vld_31_30 = out_chan_dep_vld_vec_31[2];
    assign dep_chan_data_31_30 = out_chan_dep_data_31;
    assign token_31_30 = token_out_vec_31[2];
    assign dep_chan_vld_31_2 = out_chan_dep_vld_vec_31[3];
    assign dep_chan_data_31_2 = out_chan_dep_data_31;
    assign token_31_2 = token_out_vec_31[3];
    assign dep_chan_vld_31_20 = out_chan_dep_vld_vec_31[4];
    assign dep_chan_data_31_20 = out_chan_dep_data_31;
    assign token_31_20 = token_out_vec_31[4];
    assign dep_chan_vld_31_4 = out_chan_dep_vld_vec_31[5];
    assign dep_chan_data_31_4 = out_chan_dep_data_31;
    assign token_31_4 = token_out_vec_31[5];
    assign dep_chan_vld_31_8 = out_chan_dep_vld_vec_31[6];
    assign dep_chan_data_31_8 = out_chan_dep_data_31;
    assign token_31_8 = token_out_vec_31[6];
    assign dep_chan_vld_31_6 = out_chan_dep_vld_vec_31[7];
    assign dep_chan_data_31_6 = out_chan_dep_data_31;
    assign token_31_6 = token_out_vec_31[7];
    assign dep_chan_vld_31_3 = out_chan_dep_vld_vec_31[8];
    assign dep_chan_data_31_3 = out_chan_dep_data_31;
    assign token_31_3 = token_out_vec_31[8];
    assign dep_chan_vld_31_21 = out_chan_dep_vld_vec_31[9];
    assign dep_chan_data_31_21 = out_chan_dep_data_31;
    assign token_31_21 = token_out_vec_31[9];
    assign dep_chan_vld_31_5 = out_chan_dep_vld_vec_31[10];
    assign dep_chan_data_31_5 = out_chan_dep_data_31;
    assign token_31_5 = token_out_vec_31[10];
    assign dep_chan_vld_31_9 = out_chan_dep_vld_vec_31[11];
    assign dep_chan_data_31_9 = out_chan_dep_data_31;
    assign token_31_9 = token_out_vec_31[11];
    assign dep_chan_vld_31_7 = out_chan_dep_vld_vec_31[12];
    assign dep_chan_data_31_7 = out_chan_dep_data_31;
    assign token_31_7 = token_out_vec_31[12];
    assign dep_chan_vld_31_10 = out_chan_dep_vld_vec_31[13];
    assign dep_chan_data_31_10 = out_chan_dep_data_31;
    assign token_31_10 = token_out_vec_31[13];
    assign dep_chan_vld_31_15 = out_chan_dep_vld_vec_31[14];
    assign dep_chan_data_31_15 = out_chan_dep_data_31;
    assign token_31_15 = token_out_vec_31[14];
    assign dep_chan_vld_31_38 = out_chan_dep_vld_vec_31[15];
    assign dep_chan_data_31_38 = out_chan_dep_data_31;
    assign token_31_38 = token_out_vec_31[15];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 32, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_32 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_32),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_32),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_32),
        .token_in_vec(token_in_vec_32),
        .dl_detect_in(dl_detect_out),
        .origin(origin[32]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_32),
        .out_chan_dep_data(out_chan_dep_data_32),
        .token_out_vec(token_out_vec_32),
        .dl_detect_out(dl_in_vec[32]));

    assign proc_32_data_FIFO_blk[0] = 1'b0;
    assign proc_32_data_PIPO_blk[0] = 1'b0;
    assign proc_32_start_FIFO_blk[0] = 1'b0;
    assign proc_32_TLF_FIFO_blk[0] = 1'b0;
    assign proc_32_input_sync_blk[0] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.ap_sync_p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.ap_sync_p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0_ap_ready);
    assign proc_32_output_sync_blk[0] = 1'b0 | (ap_done_reg_21 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.ap_done);
    assign proc_dep_vld_vec_32[0] = dl_detect_out ? proc_dep_vld_vec_32_reg[0] : (proc_32_data_FIFO_blk[0] | proc_32_data_PIPO_blk[0] | proc_32_start_FIFO_blk[0] | proc_32_TLF_FIFO_blk[0] | proc_32_input_sync_blk[0] | proc_32_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_32_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_32_reg <= proc_dep_vld_vec_32;
        end
    end
    assign in_chan_dep_vld_vec_32[0] = dep_chan_vld_35_32;
    assign in_chan_dep_data_vec_32[38 : 0] = dep_chan_data_35_32;
    assign token_in_vec_32[0] = token_35_32;
    assign dep_chan_vld_32_35 = out_chan_dep_vld_vec_32[0];
    assign dep_chan_data_32_35 = out_chan_dep_data_32;
    assign token_32_35 = token_out_vec_32[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 33, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_33 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_33),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_33),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_33),
        .token_in_vec(token_in_vec_33),
        .dl_detect_in(dl_detect_out),
        .origin(origin[33]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_33),
        .out_chan_dep_data(out_chan_dep_data_33),
        .token_out_vec(token_out_vec_33),
        .dl_detect_out(dl_in_vec[33]));

    assign proc_33_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.grp_p_anonymous_namespace_pointwise_compute_final_streaming_Pipeline_VITIS_LOOP_183_1_1_fu_638.columns_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.scales_blk_n);
    assign proc_33_data_PIPO_blk[0] = 1'b0;
    assign proc_33_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.start_for_p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_0_U0.real_start & (trans_in_cnt_12 == trans_out_cnt_12) & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.start_for_p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0_U.if_read);
    assign proc_33_TLF_FIFO_blk[0] = 1'b0;
    assign proc_33_input_sync_blk[0] = 1'b0;
    assign proc_33_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_33[0] = dl_detect_out ? proc_dep_vld_vec_33_reg[0] : (proc_33_data_FIFO_blk[0] | proc_33_data_PIPO_blk[0] | proc_33_start_FIFO_blk[0] | proc_33_TLF_FIFO_blk[0] | proc_33_input_sync_blk[0] | proc_33_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_33_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_33_reg <= proc_dep_vld_vec_33;
        end
    end
    assign in_chan_dep_vld_vec_33[0] = dep_chan_vld_34_33;
    assign in_chan_dep_data_vec_33[38 : 0] = dep_chan_data_34_33;
    assign token_in_vec_33[0] = token_34_33;
    assign dep_chan_vld_33_34 = out_chan_dep_vld_vec_33[0];
    assign dep_chan_data_33_34 = out_chan_dep_data_33;
    assign token_33_34 = token_out_vec_33[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 34, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_34 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_34),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_34),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_34),
        .token_in_vec(token_in_vec_34),
        .dl_detect_in(dl_detect_out),
        .origin(origin[34]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_34),
        .out_chan_dep_data(out_chan_dep_data_34),
        .token_out_vec(token_out_vec_34),
        .dl_detect_out(dl_in_vec[34]));

    assign proc_34_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.grp_p_anonymous_namespace_pointwise_post_final_Pipeline_VITIS_LOOP_287_3_1_fu_396.columns_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.scales_blk_n);
    assign proc_34_data_PIPO_blk[0] = 1'b0;
    assign proc_34_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.start_for_p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.start_for_p_anonymous_namespace_pointwise_post_final_0_ScaleClient_U0_U.if_write);
    assign proc_34_TLF_FIFO_blk[0] = 1'b0;
    assign proc_34_input_sync_blk[0] = 1'b0;
    assign proc_34_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_34[0] = dl_detect_out ? proc_dep_vld_vec_34_reg[0] : (proc_34_data_FIFO_blk[0] | proc_34_data_PIPO_blk[0] | proc_34_start_FIFO_blk[0] | proc_34_TLF_FIFO_blk[0] | proc_34_input_sync_blk[0] | proc_34_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_34_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_34_reg <= proc_dep_vld_vec_34;
        end
    end
    assign in_chan_dep_vld_vec_34[0] = dep_chan_vld_33_34;
    assign in_chan_dep_data_vec_34[38 : 0] = dep_chan_data_33_34;
    assign token_in_vec_34[0] = token_33_34;
    assign dep_chan_vld_34_33 = out_chan_dep_vld_vec_34[0];
    assign dep_chan_data_34_33 = out_chan_dep_data_34;
    assign token_34_33 = token_out_vec_34[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 35, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_35 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_35),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_35),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_35),
        .token_in_vec(token_in_vec_35),
        .dl_detect_in(dl_detect_out),
        .origin(origin[35]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_35),
        .out_chan_dep_data(out_chan_dep_data_35),
        .token_out_vec(token_out_vec_35),
        .dl_detect_out(dl_in_vec[35]));

    assign proc_35_data_FIFO_blk[0] = 1'b0;
    assign proc_35_data_PIPO_blk[0] = 1'b0;
    assign proc_35_start_FIFO_blk[0] = 1'b0;
    assign proc_35_TLF_FIFO_blk[0] = 1'b0;
    assign proc_35_input_sync_blk[0] = 1'b0 | (grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.ap_sync_p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0_ap_ready & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.ap_sync_p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0_ap_ready);
    assign proc_35_output_sync_blk[0] = 1'b0 | (ap_done_reg_22 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_0_ScaleClient_U0.ap_done);
    assign proc_dep_vld_vec_35[0] = dl_detect_out ? proc_dep_vld_vec_35_reg[0] : (proc_35_data_FIFO_blk[0] | proc_35_data_PIPO_blk[0] | proc_35_start_FIFO_blk[0] | proc_35_TLF_FIFO_blk[0] | proc_35_input_sync_blk[0] | proc_35_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_35_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_35_reg <= proc_dep_vld_vec_35;
        end
    end
    assign in_chan_dep_vld_vec_35[0] = dep_chan_vld_32_35;
    assign in_chan_dep_data_vec_35[38 : 0] = dep_chan_data_32_35;
    assign token_in_vec_35[0] = token_32_35;
    assign dep_chan_vld_35_32 = out_chan_dep_vld_vec_35[0];
    assign dep_chan_data_35_32 = out_chan_dep_data_35;
    assign token_35_32 = token_out_vec_35[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 36, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_36 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_36),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_36),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_36),
        .token_in_vec(token_in_vec_36),
        .dl_detect_in(dl_detect_out),
        .origin(origin[36]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_36),
        .out_chan_dep_data(out_chan_dep_data_36),
        .token_out_vec(token_out_vec_36),
        .dl_detect_out(dl_in_vec[36]));

    assign proc_36_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.grp_p_anonymous_namespace_pointwise_compute_final_streaming_Pipeline_VITIS_LOOP_183_1_fu_638.columns_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.scales_blk_n);
    assign proc_36_data_PIPO_blk[0] = 1'b0;
    assign proc_36_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.start_for_p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0_U.if_full_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.ap_start & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_compute_final_streaming_1_U0.real_start & (trans_in_cnt_13 == trans_out_cnt_13) & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.start_for_p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0_U.if_read);
    assign proc_36_TLF_FIFO_blk[0] = 1'b0;
    assign proc_36_input_sync_blk[0] = 1'b0;
    assign proc_36_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_36[0] = dl_detect_out ? proc_dep_vld_vec_36_reg[0] : (proc_36_data_FIFO_blk[0] | proc_36_data_PIPO_blk[0] | proc_36_start_FIFO_blk[0] | proc_36_TLF_FIFO_blk[0] | proc_36_input_sync_blk[0] | proc_36_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_36_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_36_reg <= proc_dep_vld_vec_36;
        end
    end
    assign in_chan_dep_vld_vec_36[0] = dep_chan_vld_37_36;
    assign in_chan_dep_data_vec_36[38 : 0] = dep_chan_data_37_36;
    assign token_in_vec_36[0] = token_37_36;
    assign dep_chan_vld_36_37 = out_chan_dep_vld_vec_36[0];
    assign dep_chan_data_36_37 = out_chan_dep_data_36;
    assign token_36_37 = token_out_vec_36[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 37, 1, 1) cnn_pipeline_v10_hls_deadlock_detect_unit_37 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_37),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_37),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_37),
        .token_in_vec(token_in_vec_37),
        .dl_detect_in(dl_detect_out),
        .origin(origin[37]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_37),
        .out_chan_dep_data(out_chan_dep_data_37),
        .token_out_vec(token_out_vec_37),
        .dl_detect_out(dl_in_vec[37]));

    assign proc_37_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.grp_p_anonymous_namespace_pointwise_post_final_Pipeline_VITIS_LOOP_287_3_fu_396.columns_blk_n) | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.scales_blk_n);
    assign proc_37_data_PIPO_blk[0] = 1'b0;
    assign proc_37_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.start_for_p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.grp_p_anonymous_namespace_pointwise_final_dual_fu_422.p_anonymous_namespace_pointwise_pair_final_1_ScaleClient_U0.start_for_p_anonymous_namespace_pointwise_post_final_1_ScaleClient_U0_U.if_write);
    assign proc_37_TLF_FIFO_blk[0] = 1'b0;
    assign proc_37_input_sync_blk[0] = 1'b0;
    assign proc_37_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_37[0] = dl_detect_out ? proc_dep_vld_vec_37_reg[0] : (proc_37_data_FIFO_blk[0] | proc_37_data_PIPO_blk[0] | proc_37_start_FIFO_blk[0] | proc_37_TLF_FIFO_blk[0] | proc_37_input_sync_blk[0] | proc_37_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_37_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_37_reg <= proc_dep_vld_vec_37;
        end
    end
    assign in_chan_dep_vld_vec_37[0] = dep_chan_vld_36_37;
    assign in_chan_dep_data_vec_37[38 : 0] = dep_chan_data_36_37;
    assign token_in_vec_37[0] = token_36_37;
    assign dep_chan_vld_37_36 = out_chan_dep_vld_vec_37[0];
    assign dep_chan_data_37_36 = out_chan_dep_data_37;
    assign token_37_36 = token_out_vec_37[0];

    // Process: grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0
    cnn_pipeline_v10_hls_deadlock_detect_unit #(39, 38, 10, 10) cnn_pipeline_v10_hls_deadlock_detect_unit_38 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_38),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_38),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_38),
        .token_in_vec(token_in_vec_38),
        .dl_detect_in(dl_detect_out),
        .origin(origin[38]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_38),
        .out_chan_dep_data(out_chan_dep_data_38),
        .token_out_vec(token_out_vec_38),
        .dl_detect_out(dl_in_vec[38]));

    assign proc_38_data_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.errors_a_blk_n);
    assign proc_38_data_PIPO_blk[0] = 1'b0;
    assign proc_38_start_FIFO_blk[0] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_collect_errors_U0_U.if_empty_n & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_idle & ~grp_p_anonymous_namespace_chain_fu_635.start_for_p_anonymous_namespace_collect_errors_U0_U.if_write);
    assign proc_38_TLF_FIFO_blk[0] = 1'b0;
    assign proc_38_input_sync_blk[0] = 1'b0;
    assign proc_38_output_sync_blk[0] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_1_U0.ap_done);
    assign proc_dep_vld_vec_38[0] = dl_detect_out ? proc_dep_vld_vec_38_reg[0] : (proc_38_data_FIFO_blk[0] | proc_38_data_PIPO_blk[0] | proc_38_start_FIFO_blk[0] | proc_38_TLF_FIFO_blk[0] | proc_38_input_sync_blk[0] | proc_38_output_sync_blk[0]);
    assign proc_38_data_FIFO_blk[1] = 1'b0 | (~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.errors_b_blk_n);
    assign proc_38_data_PIPO_blk[1] = 1'b0;
    assign proc_38_start_FIFO_blk[1] = 1'b0;
    assign proc_38_TLF_FIFO_blk[1] = 1'b0;
    assign proc_38_input_sync_blk[1] = 1'b0;
    assign proc_38_output_sync_blk[1] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_feed_chain_U0.ap_done);
    assign proc_dep_vld_vec_38[1] = dl_detect_out ? proc_dep_vld_vec_38_reg[1] : (proc_38_data_FIFO_blk[1] | proc_38_data_PIPO_blk[1] | proc_38_start_FIFO_blk[1] | proc_38_TLF_FIFO_blk[1] | proc_38_input_sync_blk[1] | proc_38_output_sync_blk[1]);
    assign proc_38_data_FIFO_blk[2] = 1'b0;
    assign proc_38_data_PIPO_blk[2] = 1'b0;
    assign proc_38_start_FIFO_blk[2] = 1'b0;
    assign proc_38_TLF_FIFO_blk[2] = 1'b0;
    assign proc_38_input_sync_blk[2] = 1'b0;
    assign proc_38_output_sync_blk[2] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_U0.ap_done);
    assign proc_dep_vld_vec_38[2] = dl_detect_out ? proc_dep_vld_vec_38_reg[2] : (proc_38_data_FIFO_blk[2] | proc_38_data_PIPO_blk[2] | proc_38_start_FIFO_blk[2] | proc_38_TLF_FIFO_blk[2] | proc_38_input_sync_blk[2] | proc_38_output_sync_blk[2]);
    assign proc_38_data_FIFO_blk[3] = 1'b0;
    assign proc_38_data_PIPO_blk[3] = 1'b0;
    assign proc_38_start_FIFO_blk[3] = 1'b0;
    assign proc_38_TLF_FIFO_blk[3] = 1'b0;
    assign proc_38_input_sync_blk[3] = 1'b0;
    assign proc_38_output_sync_blk[3] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.write_broker_2_8_U0.ap_done);
    assign proc_dep_vld_vec_38[3] = dl_detect_out ? proc_dep_vld_vec_38_reg[3] : (proc_38_data_FIFO_blk[3] | proc_38_data_PIPO_blk[3] | proc_38_start_FIFO_blk[3] | proc_38_TLF_FIFO_blk[3] | proc_38_input_sync_blk[3] | proc_38_output_sync_blk[3]);
    assign proc_38_data_FIFO_blk[4] = 1'b0;
    assign proc_38_data_PIPO_blk[4] = 1'b0;
    assign proc_38_start_FIFO_blk[4] = 1'b0;
    assign proc_38_TLF_FIFO_blk[4] = 1'b0;
    assign proc_38_input_sync_blk[4] = 1'b0;
    assign proc_38_output_sync_blk[4] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_3_4_false_0_U0.ap_done);
    assign proc_dep_vld_vec_38[4] = dl_detect_out ? proc_dep_vld_vec_38_reg[4] : (proc_38_data_FIFO_blk[4] | proc_38_data_PIPO_blk[4] | proc_38_start_FIFO_blk[4] | proc_38_TLF_FIFO_blk[4] | proc_38_input_sync_blk[4] | proc_38_output_sync_blk[4]);
    assign proc_38_data_FIFO_blk[5] = 1'b0;
    assign proc_38_data_PIPO_blk[5] = 1'b0;
    assign proc_38_start_FIFO_blk[5] = 1'b0;
    assign proc_38_TLF_FIFO_blk[5] = 1'b0;
    assign proc_38_input_sync_blk[5] = 1'b0;
    assign proc_38_output_sync_blk[5] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_depthwise_chain_7_16_true_1_U0.ap_done);
    assign proc_dep_vld_vec_38[5] = dl_detect_out ? proc_dep_vld_vec_38_reg[5] : (proc_38_data_FIFO_blk[5] | proc_38_data_PIPO_blk[5] | proc_38_start_FIFO_blk[5] | proc_38_TLF_FIFO_blk[5] | proc_38_input_sync_blk[5] | proc_38_output_sync_blk[5]);
    assign proc_38_data_FIFO_blk[6] = 1'b0;
    assign proc_38_data_PIPO_blk[6] = 1'b0;
    assign proc_38_start_FIFO_blk[6] = 1'b0;
    assign proc_38_TLF_FIFO_blk[6] = 1'b0;
    assign proc_38_input_sync_blk[6] = 1'b0;
    assign proc_38_output_sync_blk[6] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_2_U0.ap_done);
    assign proc_dep_vld_vec_38[6] = dl_detect_out ? proc_dep_vld_vec_38_reg[6] : (proc_38_data_FIFO_blk[6] | proc_38_data_PIPO_blk[6] | proc_38_start_FIFO_blk[6] | proc_38_TLF_FIFO_blk[6] | proc_38_input_sync_blk[6] | proc_38_output_sync_blk[6]);
    assign proc_38_data_FIFO_blk[7] = 1'b0;
    assign proc_38_data_PIPO_blk[7] = 1'b0;
    assign proc_38_start_FIFO_blk[7] = 1'b0;
    assign proc_38_TLF_FIFO_blk[7] = 1'b0;
    assign proc_38_input_sync_blk[7] = 1'b0;
    assign proc_38_output_sync_blk[7] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_residual_writer_U0.ap_done);
    assign proc_dep_vld_vec_38[7] = dl_detect_out ? proc_dep_vld_vec_38_reg[7] : (proc_38_data_FIFO_blk[7] | proc_38_data_PIPO_blk[7] | proc_38_start_FIFO_blk[7] | proc_38_TLF_FIFO_blk[7] | proc_38_input_sync_blk[7] | proc_38_output_sync_blk[7]);
    assign proc_38_data_FIFO_blk[8] = 1'b0;
    assign proc_38_data_PIPO_blk[8] = 1'b0;
    assign proc_38_start_FIFO_blk[8] = 1'b0;
    assign proc_38_TLF_FIFO_blk[8] = 1'b0;
    assign proc_38_input_sync_blk[8] = 1'b0;
    assign proc_38_output_sync_blk[8] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise1_chain_U0.ap_done);
    assign proc_dep_vld_vec_38[8] = dl_detect_out ? proc_dep_vld_vec_38_reg[8] : (proc_38_data_FIFO_blk[8] | proc_38_data_PIPO_blk[8] | proc_38_start_FIFO_blk[8] | proc_38_TLF_FIFO_blk[8] | proc_38_input_sync_blk[8] | proc_38_output_sync_blk[8]);
    assign proc_38_data_FIFO_blk[9] = 1'b0;
    assign proc_38_data_PIPO_blk[9] = 1'b0;
    assign proc_38_start_FIFO_blk[9] = 1'b0;
    assign proc_38_TLF_FIFO_blk[9] = 1'b0;
    assign proc_38_input_sync_blk[9] = 1'b0;
    assign proc_38_output_sync_blk[9] = 1'b0 | (ap_done_reg_10 & grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_collect_errors_U0.ap_done & ~grp_p_anonymous_namespace_chain_fu_635.p_anonymous_namespace_pointwise2_chain_U0.ap_done);
    assign proc_dep_vld_vec_38[9] = dl_detect_out ? proc_dep_vld_vec_38_reg[9] : (proc_38_data_FIFO_blk[9] | proc_38_data_PIPO_blk[9] | proc_38_start_FIFO_blk[9] | proc_38_TLF_FIFO_blk[9] | proc_38_input_sync_blk[9] | proc_38_output_sync_blk[9]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_38_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_38_reg <= proc_dep_vld_vec_38;
        end
    end
    assign in_chan_dep_vld_vec_38[0] = dep_chan_vld_4_38;
    assign in_chan_dep_data_vec_38[38 : 0] = dep_chan_data_4_38;
    assign token_in_vec_38[0] = token_4_38;
    assign in_chan_dep_vld_vec_38[1] = dep_chan_vld_5_38;
    assign in_chan_dep_data_vec_38[77 : 39] = dep_chan_data_5_38;
    assign token_in_vec_38[1] = token_5_38;
    assign in_chan_dep_vld_vec_38[2] = dep_chan_vld_8_38;
    assign in_chan_dep_data_vec_38[116 : 78] = dep_chan_data_8_38;
    assign token_in_vec_38[2] = token_8_38;
    assign in_chan_dep_vld_vec_38[3] = dep_chan_vld_9_38;
    assign in_chan_dep_data_vec_38[155 : 117] = dep_chan_data_9_38;
    assign token_in_vec_38[3] = token_9_38;
    assign in_chan_dep_vld_vec_38[4] = dep_chan_vld_10_38;
    assign in_chan_dep_data_vec_38[194 : 156] = dep_chan_data_10_38;
    assign token_in_vec_38[4] = token_10_38;
    assign in_chan_dep_vld_vec_38[5] = dep_chan_vld_15_38;
    assign in_chan_dep_data_vec_38[233 : 195] = dep_chan_data_15_38;
    assign token_in_vec_38[5] = token_15_38;
    assign in_chan_dep_vld_vec_38[6] = dep_chan_vld_20_38;
    assign in_chan_dep_data_vec_38[272 : 234] = dep_chan_data_20_38;
    assign token_in_vec_38[6] = token_20_38;
    assign in_chan_dep_vld_vec_38[7] = dep_chan_vld_21_38;
    assign in_chan_dep_data_vec_38[311 : 273] = dep_chan_data_21_38;
    assign token_in_vec_38[7] = token_21_38;
    assign in_chan_dep_vld_vec_38[8] = dep_chan_vld_23_38;
    assign in_chan_dep_data_vec_38[350 : 312] = dep_chan_data_23_38;
    assign token_in_vec_38[8] = token_23_38;
    assign in_chan_dep_vld_vec_38[9] = dep_chan_vld_31_38;
    assign in_chan_dep_data_vec_38[389 : 351] = dep_chan_data_31_38;
    assign token_in_vec_38[9] = token_31_38;
    assign dep_chan_vld_38_8 = out_chan_dep_vld_vec_38[0];
    assign dep_chan_data_38_8 = out_chan_dep_data_38;
    assign token_38_8 = token_out_vec_38[0];
    assign dep_chan_vld_38_9 = out_chan_dep_vld_vec_38[1];
    assign dep_chan_data_38_9 = out_chan_dep_data_38;
    assign token_38_9 = token_out_vec_38[1];
    assign dep_chan_vld_38_4 = out_chan_dep_vld_vec_38[2];
    assign dep_chan_data_38_4 = out_chan_dep_data_38;
    assign token_38_4 = token_out_vec_38[2];
    assign dep_chan_vld_38_5 = out_chan_dep_vld_vec_38[3];
    assign dep_chan_data_38_5 = out_chan_dep_data_38;
    assign token_38_5 = token_out_vec_38[3];
    assign dep_chan_vld_38_10 = out_chan_dep_vld_vec_38[4];
    assign dep_chan_data_38_10 = out_chan_dep_data_38;
    assign token_38_10 = token_out_vec_38[4];
    assign dep_chan_vld_38_15 = out_chan_dep_vld_vec_38[5];
    assign dep_chan_data_38_15 = out_chan_dep_data_38;
    assign token_38_15 = token_out_vec_38[5];
    assign dep_chan_vld_38_20 = out_chan_dep_vld_vec_38[6];
    assign dep_chan_data_38_20 = out_chan_dep_data_38;
    assign token_38_20 = token_out_vec_38[6];
    assign dep_chan_vld_38_21 = out_chan_dep_vld_vec_38[7];
    assign dep_chan_data_38_21 = out_chan_dep_data_38;
    assign token_38_21 = token_out_vec_38[7];
    assign dep_chan_vld_38_23 = out_chan_dep_vld_vec_38[8];
    assign dep_chan_data_38_23 = out_chan_dep_data_38;
    assign token_38_23 = token_out_vec_38[8];
    assign dep_chan_vld_38_31 = out_chan_dep_vld_vec_38[9];
    assign dep_chan_data_38_31 = out_chan_dep_data_38;
    assign token_38_31 = token_out_vec_38[9];


`include "cnn_pipeline_v10_hls_deadlock_report_unit.vh"
