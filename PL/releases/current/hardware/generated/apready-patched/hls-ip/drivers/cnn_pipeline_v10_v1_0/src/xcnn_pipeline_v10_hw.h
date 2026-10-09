// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
// control
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

#define XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW1_DATA      0x10
#define XCNN_PIPELINE_V10_CONTROL_BITS_PARAMS_PW1_DATA      64
#define XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW2_DATA      0x1c
#define XCNN_PIPELINE_V10_CONTROL_BITS_PARAMS_PW2_DATA      64
#define XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_RD_DATA 0x28
#define XCNN_PIPELINE_V10_CONTROL_BITS_ACTIVATION_A_RD_DATA 64
#define XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_WR_DATA 0x34
#define XCNN_PIPELINE_V10_CONTROL_BITS_ACTIVATION_A_WR_DATA 64
#define XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_RD_DATA 0x40
#define XCNN_PIPELINE_V10_CONTROL_BITS_ACTIVATION_B_RD_DATA 64
#define XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_WR_DATA 0x4c
#define XCNN_PIPELINE_V10_CONTROL_BITS_ACTIVATION_B_WR_DATA 64
#define XCNN_PIPELINE_V10_CONTROL_ADDR_PROFILE_DATA         0x58
#define XCNN_PIPELINE_V10_CONTROL_BITS_PROFILE_DATA         32
#define XCNN_PIPELINE_V10_CONTROL_ADDR_BLOCK_COUNT_DATA     0x60
#define XCNN_PIPELINE_V10_CONTROL_BITS_BLOCK_COUNT_DATA     32
#define XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_WORDS_DATA    0x68
#define XCNN_PIPELINE_V10_CONTROL_BITS_PARAMS_WORDS_DATA    32
#define XCNN_PIPELINE_V10_CONTROL_ADDR_SLOT_WORDS_DATA      0x70
#define XCNN_PIPELINE_V10_CONTROL_BITS_SLOT_WORDS_DATA      32
#define XCNN_PIPELINE_V10_CONTROL_ADDR_ARENA_WORDS_DATA     0x78
#define XCNN_PIPELINE_V10_CONTROL_BITS_ARENA_WORDS_DATA     32
#define XCNN_PIPELINE_V10_CONTROL_ADDR_FLAGS_DATA           0x80
#define XCNN_PIPELINE_V10_CONTROL_BITS_FLAGS_DATA           32

