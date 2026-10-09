// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
`timescale 1ns/1ps
(* DowngradeIPIdentifiedWarnings="yes" *) module cnn_pipeline_v10_control_s_axi
#(parameter
    C_S_AXI_ADDR_WIDTH = 8,
    C_S_AXI_DATA_WIDTH = 32
)(
    input  wire                          ACLK,
    input  wire                          ARESET,
    input  wire                          ACLK_EN,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] AWADDR,
    input  wire                          AWVALID,
    output wire                          AWREADY,
    input  wire [C_S_AXI_DATA_WIDTH-1:0] WDATA,
    input  wire [C_S_AXI_DATA_WIDTH/8-1:0] WSTRB,
    input  wire                          WVALID,
    output wire                          WREADY,
    output wire [1:0]                    BRESP,
    output wire                          BVALID,
    input  wire                          BREADY,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] ARADDR,
    input  wire                          ARVALID,
    output wire                          ARREADY,
    output wire [C_S_AXI_DATA_WIDTH-1:0] RDATA,
    output wire [1:0]                    RRESP,
    output wire                          RVALID,
    input  wire                          RREADY,
    output wire [63:0]                   params_pw1,
    output wire [63:0]                   params_pw2,
    output wire [63:0]                   activation_a_rd,
    output wire [63:0]                   activation_a_wr,
    output wire [63:0]                   activation_b_rd,
    output wire [63:0]                   activation_b_wr,
    output wire [31:0]                   profile,
    output wire [31:0]                   block_count,
    output wire [31:0]                   params_words,
    output wire [31:0]                   slot_words,
    output wire [31:0]                   arena_words,
    output wire [31:0]                   flags
);
//------------------------Address Info-------------------
// Protocol Used: ap_ctrl_none
//
// 0x00 : reserved
// 0x04 : reserved
// 0x08 : reserved
// 0x0c : reserved
// 0x10 : Data signal of params_pw1
//        bit 31~0 - params_pw1[31:0] (Read/Write)
// 0x14 : Data signal of params_pw1
//        bit 31~0 - params_pw1[63:32] (Read/Write)
// 0x18 : reserved
// 0x1c : Data signal of params_pw2
//        bit 31~0 - params_pw2[31:0] (Read/Write)
// 0x20 : Data signal of params_pw2
//        bit 31~0 - params_pw2[63:32] (Read/Write)
// 0x24 : reserved
// 0x28 : Data signal of activation_a_rd
//        bit 31~0 - activation_a_rd[31:0] (Read/Write)
// 0x2c : Data signal of activation_a_rd
//        bit 31~0 - activation_a_rd[63:32] (Read/Write)
// 0x30 : reserved
// 0x34 : Data signal of activation_a_wr
//        bit 31~0 - activation_a_wr[31:0] (Read/Write)
// 0x38 : Data signal of activation_a_wr
//        bit 31~0 - activation_a_wr[63:32] (Read/Write)
// 0x3c : reserved
// 0x40 : Data signal of activation_b_rd
//        bit 31~0 - activation_b_rd[31:0] (Read/Write)
// 0x44 : Data signal of activation_b_rd
//        bit 31~0 - activation_b_rd[63:32] (Read/Write)
// 0x48 : reserved
// 0x4c : Data signal of activation_b_wr
//        bit 31~0 - activation_b_wr[31:0] (Read/Write)
// 0x50 : Data signal of activation_b_wr
//        bit 31~0 - activation_b_wr[63:32] (Read/Write)
// 0x54 : reserved
// 0x58 : Data signal of profile
//        bit 31~0 - profile[31:0] (Read/Write)
// 0x5c : reserved
// 0x60 : Data signal of block_count
//        bit 31~0 - block_count[31:0] (Read/Write)
// 0x64 : reserved
// 0x68 : Data signal of params_words
//        bit 31~0 - params_words[31:0] (Read/Write)
// 0x6c : reserved
// 0x70 : Data signal of slot_words
//        bit 31~0 - slot_words[31:0] (Read/Write)
// 0x74 : reserved
// 0x78 : Data signal of arena_words
//        bit 31~0 - arena_words[31:0] (Read/Write)
// 0x7c : reserved
// 0x80 : Data signal of flags
//        bit 31~0 - flags[31:0] (Read/Write)
// 0x84 : reserved
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

//------------------------Parameter----------------------
localparam
    ADDR_PARAMS_PW1_DATA_0      = 8'h10,
    ADDR_PARAMS_PW1_DATA_1      = 8'h14,
    ADDR_PARAMS_PW1_CTRL        = 8'h18,
    ADDR_PARAMS_PW2_DATA_0      = 8'h1c,
    ADDR_PARAMS_PW2_DATA_1      = 8'h20,
    ADDR_PARAMS_PW2_CTRL        = 8'h24,
    ADDR_ACTIVATION_A_RD_DATA_0 = 8'h28,
    ADDR_ACTIVATION_A_RD_DATA_1 = 8'h2c,
    ADDR_ACTIVATION_A_RD_CTRL   = 8'h30,
    ADDR_ACTIVATION_A_WR_DATA_0 = 8'h34,
    ADDR_ACTIVATION_A_WR_DATA_1 = 8'h38,
    ADDR_ACTIVATION_A_WR_CTRL   = 8'h3c,
    ADDR_ACTIVATION_B_RD_DATA_0 = 8'h40,
    ADDR_ACTIVATION_B_RD_DATA_1 = 8'h44,
    ADDR_ACTIVATION_B_RD_CTRL   = 8'h48,
    ADDR_ACTIVATION_B_WR_DATA_0 = 8'h4c,
    ADDR_ACTIVATION_B_WR_DATA_1 = 8'h50,
    ADDR_ACTIVATION_B_WR_CTRL   = 8'h54,
    ADDR_PROFILE_DATA_0         = 8'h58,
    ADDR_PROFILE_CTRL           = 8'h5c,
    ADDR_BLOCK_COUNT_DATA_0     = 8'h60,
    ADDR_BLOCK_COUNT_CTRL       = 8'h64,
    ADDR_PARAMS_WORDS_DATA_0    = 8'h68,
    ADDR_PARAMS_WORDS_CTRL      = 8'h6c,
    ADDR_SLOT_WORDS_DATA_0      = 8'h70,
    ADDR_SLOT_WORDS_CTRL        = 8'h74,
    ADDR_ARENA_WORDS_DATA_0     = 8'h78,
    ADDR_ARENA_WORDS_CTRL       = 8'h7c,
    ADDR_FLAGS_DATA_0           = 8'h80,
    ADDR_FLAGS_CTRL             = 8'h84,
    WRIDLE                      = 2'd0,
    WRDATA                      = 2'd1,
    WRRESP                      = 2'd2,
    WRRESET                     = 2'd3,
    RDIDLE                      = 2'd0,
    RDDATA                      = 2'd1,
    RDRESET                     = 2'd2,
    ADDR_BITS                = 8;

//------------------------Local signal-------------------
    reg  [1:0]                    wstate = WRRESET;
    reg  [1:0]                    wnext;
    reg  [ADDR_BITS-1:0]          waddr;
    wire [C_S_AXI_DATA_WIDTH-1:0] wmask;
    wire                          aw_hs;
    wire                          w_hs;
    reg  [1:0]                    rstate = RDRESET;
    reg  [1:0]                    rnext;
    reg  [C_S_AXI_DATA_WIDTH-1:0] rdata;
    wire                          ar_hs;
    wire [ADDR_BITS-1:0]          raddr;
    // internal registers
    reg  [63:0]                   int_params_pw1 = 'b0;
    reg  [63:0]                   int_params_pw2 = 'b0;
    reg  [63:0]                   int_activation_a_rd = 'b0;
    reg  [63:0]                   int_activation_a_wr = 'b0;
    reg  [63:0]                   int_activation_b_rd = 'b0;
    reg  [63:0]                   int_activation_b_wr = 'b0;
    reg  [31:0]                   int_profile = 'b0;
    reg  [31:0]                   int_block_count = 'b0;
    reg  [31:0]                   int_params_words = 'b0;
    reg  [31:0]                   int_slot_words = 'b0;
    reg  [31:0]                   int_arena_words = 'b0;
    reg  [31:0]                   int_flags = 'b0;

//------------------------Instantiation------------------


//------------------------AXI write fsm------------------
assign AWREADY = (wstate == WRIDLE);
assign WREADY  = (wstate == WRDATA);
assign BVALID  = (wstate == WRRESP);
assign BRESP   = 2'b00;  // OKAY
assign wmask   = { {8{WSTRB[3]}}, {8{WSTRB[2]}}, {8{WSTRB[1]}}, {8{WSTRB[0]}} };
assign aw_hs   = AWVALID & AWREADY;
assign w_hs    = WVALID & WREADY;

// wstate
always @(posedge ACLK) begin
    if (ARESET)
        wstate <= WRRESET;
    else if (ACLK_EN)
        wstate <= wnext;
end

// wnext
always @(*) begin
    case (wstate)
        WRIDLE:
            if (AWVALID)
                wnext = WRDATA;
            else
                wnext = WRIDLE;
        WRDATA:
            if (WVALID)
                wnext = WRRESP;
            else
                wnext = WRDATA;
        WRRESP:
            if (BREADY & BVALID)
                wnext = WRIDLE;
            else
                wnext = WRRESP;
        default:
            wnext = WRIDLE;
    endcase
end

// waddr
always @(posedge ACLK) begin
    if (ACLK_EN) begin
        if (aw_hs)
            waddr <= {AWADDR[ADDR_BITS-1:2], {2{1'b0}}};
    end
end

//------------------------AXI read fsm-------------------
assign ARREADY = (rstate == RDIDLE);
assign RDATA   = rdata;
assign RRESP   = 2'b00;  // OKAY
assign RVALID  = (rstate == RDDATA);
assign ar_hs   = ARVALID & ARREADY;
assign raddr   = ARADDR[ADDR_BITS-1:0];

// rstate
always @(posedge ACLK) begin
    if (ARESET)
        rstate <= RDRESET;
    else if (ACLK_EN)
        rstate <= rnext;
end

// rnext
always @(*) begin
    case (rstate)
        RDIDLE:
            if (ARVALID)
                rnext = RDDATA;
            else
                rnext = RDIDLE;
        RDDATA:
            if (RREADY & RVALID)
                rnext = RDIDLE;
            else
                rnext = RDDATA;
        default:
            rnext = RDIDLE;
    endcase
end

// rdata
always @(posedge ACLK) begin
    if (ACLK_EN) begin
        if (ar_hs) begin
            rdata <= 'b0;
            case (raddr)
                ADDR_PARAMS_PW1_DATA_0: begin
                    rdata <= int_params_pw1[31:0];
                end
                ADDR_PARAMS_PW1_DATA_1: begin
                    rdata <= int_params_pw1[63:32];
                end
                ADDR_PARAMS_PW2_DATA_0: begin
                    rdata <= int_params_pw2[31:0];
                end
                ADDR_PARAMS_PW2_DATA_1: begin
                    rdata <= int_params_pw2[63:32];
                end
                ADDR_ACTIVATION_A_RD_DATA_0: begin
                    rdata <= int_activation_a_rd[31:0];
                end
                ADDR_ACTIVATION_A_RD_DATA_1: begin
                    rdata <= int_activation_a_rd[63:32];
                end
                ADDR_ACTIVATION_A_WR_DATA_0: begin
                    rdata <= int_activation_a_wr[31:0];
                end
                ADDR_ACTIVATION_A_WR_DATA_1: begin
                    rdata <= int_activation_a_wr[63:32];
                end
                ADDR_ACTIVATION_B_RD_DATA_0: begin
                    rdata <= int_activation_b_rd[31:0];
                end
                ADDR_ACTIVATION_B_RD_DATA_1: begin
                    rdata <= int_activation_b_rd[63:32];
                end
                ADDR_ACTIVATION_B_WR_DATA_0: begin
                    rdata <= int_activation_b_wr[31:0];
                end
                ADDR_ACTIVATION_B_WR_DATA_1: begin
                    rdata <= int_activation_b_wr[63:32];
                end
                ADDR_PROFILE_DATA_0: begin
                    rdata <= int_profile[31:0];
                end
                ADDR_BLOCK_COUNT_DATA_0: begin
                    rdata <= int_block_count[31:0];
                end
                ADDR_PARAMS_WORDS_DATA_0: begin
                    rdata <= int_params_words[31:0];
                end
                ADDR_SLOT_WORDS_DATA_0: begin
                    rdata <= int_slot_words[31:0];
                end
                ADDR_ARENA_WORDS_DATA_0: begin
                    rdata <= int_arena_words[31:0];
                end
                ADDR_FLAGS_DATA_0: begin
                    rdata <= int_flags[31:0];
                end
            endcase
        end
    end
end


//------------------------Register logic-----------------
assign params_pw1      = int_params_pw1;
assign params_pw2      = int_params_pw2;
assign activation_a_rd = int_activation_a_rd;
assign activation_a_wr = int_activation_a_wr;
assign activation_b_rd = int_activation_b_rd;
assign activation_b_wr = int_activation_b_wr;
assign profile         = int_profile;
assign block_count     = int_block_count;
assign params_words    = int_params_words;
assign slot_words      = int_slot_words;
assign arena_words     = int_arena_words;
assign flags           = int_flags;
// int_params_pw1[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_params_pw1[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_PARAMS_PW1_DATA_0)
            int_params_pw1[31:0] <= (WDATA[31:0] & wmask) | (int_params_pw1[31:0] & ~wmask);
    end
end

// int_params_pw1[63:32]
always @(posedge ACLK) begin
    if (ARESET)
        int_params_pw1[63:32] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_PARAMS_PW1_DATA_1)
            int_params_pw1[63:32] <= (WDATA[31:0] & wmask) | (int_params_pw1[63:32] & ~wmask);
    end
end

// int_params_pw2[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_params_pw2[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_PARAMS_PW2_DATA_0)
            int_params_pw2[31:0] <= (WDATA[31:0] & wmask) | (int_params_pw2[31:0] & ~wmask);
    end
end

// int_params_pw2[63:32]
always @(posedge ACLK) begin
    if (ARESET)
        int_params_pw2[63:32] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_PARAMS_PW2_DATA_1)
            int_params_pw2[63:32] <= (WDATA[31:0] & wmask) | (int_params_pw2[63:32] & ~wmask);
    end
end

// int_activation_a_rd[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_activation_a_rd[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ACTIVATION_A_RD_DATA_0)
            int_activation_a_rd[31:0] <= (WDATA[31:0] & wmask) | (int_activation_a_rd[31:0] & ~wmask);
    end
end

// int_activation_a_rd[63:32]
always @(posedge ACLK) begin
    if (ARESET)
        int_activation_a_rd[63:32] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ACTIVATION_A_RD_DATA_1)
            int_activation_a_rd[63:32] <= (WDATA[31:0] & wmask) | (int_activation_a_rd[63:32] & ~wmask);
    end
end

// int_activation_a_wr[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_activation_a_wr[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ACTIVATION_A_WR_DATA_0)
            int_activation_a_wr[31:0] <= (WDATA[31:0] & wmask) | (int_activation_a_wr[31:0] & ~wmask);
    end
end

// int_activation_a_wr[63:32]
always @(posedge ACLK) begin
    if (ARESET)
        int_activation_a_wr[63:32] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ACTIVATION_A_WR_DATA_1)
            int_activation_a_wr[63:32] <= (WDATA[31:0] & wmask) | (int_activation_a_wr[63:32] & ~wmask);
    end
end

// int_activation_b_rd[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_activation_b_rd[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ACTIVATION_B_RD_DATA_0)
            int_activation_b_rd[31:0] <= (WDATA[31:0] & wmask) | (int_activation_b_rd[31:0] & ~wmask);
    end
end

// int_activation_b_rd[63:32]
always @(posedge ACLK) begin
    if (ARESET)
        int_activation_b_rd[63:32] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ACTIVATION_B_RD_DATA_1)
            int_activation_b_rd[63:32] <= (WDATA[31:0] & wmask) | (int_activation_b_rd[63:32] & ~wmask);
    end
end

// int_activation_b_wr[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_activation_b_wr[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ACTIVATION_B_WR_DATA_0)
            int_activation_b_wr[31:0] <= (WDATA[31:0] & wmask) | (int_activation_b_wr[31:0] & ~wmask);
    end
end

// int_activation_b_wr[63:32]
always @(posedge ACLK) begin
    if (ARESET)
        int_activation_b_wr[63:32] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ACTIVATION_B_WR_DATA_1)
            int_activation_b_wr[63:32] <= (WDATA[31:0] & wmask) | (int_activation_b_wr[63:32] & ~wmask);
    end
end

// int_profile[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_profile[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_PROFILE_DATA_0)
            int_profile[31:0] <= (WDATA[31:0] & wmask) | (int_profile[31:0] & ~wmask);
    end
end

// int_block_count[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_block_count[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_BLOCK_COUNT_DATA_0)
            int_block_count[31:0] <= (WDATA[31:0] & wmask) | (int_block_count[31:0] & ~wmask);
    end
end

// int_params_words[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_params_words[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_PARAMS_WORDS_DATA_0)
            int_params_words[31:0] <= (WDATA[31:0] & wmask) | (int_params_words[31:0] & ~wmask);
    end
end

// int_slot_words[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_slot_words[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_SLOT_WORDS_DATA_0)
            int_slot_words[31:0] <= (WDATA[31:0] & wmask) | (int_slot_words[31:0] & ~wmask);
    end
end

// int_arena_words[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_arena_words[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_ARENA_WORDS_DATA_0)
            int_arena_words[31:0] <= (WDATA[31:0] & wmask) | (int_arena_words[31:0] & ~wmask);
    end
end

// int_flags[31:0]
always @(posedge ACLK) begin
    if (ARESET)
        int_flags[31:0] <= 0;
    else if (ACLK_EN) begin
        if (w_hs && waddr == ADDR_FLAGS_DATA_0)
            int_flags[31:0] <= (WDATA[31:0] & wmask) | (int_flags[31:0] & ~wmask);
    end
end


//------------------------Memory logic-------------------

endmodule
