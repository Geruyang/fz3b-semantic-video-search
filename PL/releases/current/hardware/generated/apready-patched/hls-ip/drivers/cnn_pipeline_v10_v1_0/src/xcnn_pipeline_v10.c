// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xcnn_pipeline_v10.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XCnn_pipeline_v10_CfgInitialize(XCnn_pipeline_v10 *InstancePtr, XCnn_pipeline_v10_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XCnn_pipeline_v10_Set_params_pw1(XCnn_pipeline_v10 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW1_DATA, (u32)(Data));
    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW1_DATA + 4, (u32)(Data >> 32));
}

u64 XCnn_pipeline_v10_Get_params_pw1(XCnn_pipeline_v10 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW1_DATA);
    Data += (u64)XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW1_DATA + 4) << 32;
    return Data;
}

void XCnn_pipeline_v10_Set_params_pw2(XCnn_pipeline_v10 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW2_DATA, (u32)(Data));
    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW2_DATA + 4, (u32)(Data >> 32));
}

u64 XCnn_pipeline_v10_Get_params_pw2(XCnn_pipeline_v10 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW2_DATA);
    Data += (u64)XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_PW2_DATA + 4) << 32;
    return Data;
}

void XCnn_pipeline_v10_Set_activation_a_rd(XCnn_pipeline_v10 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_RD_DATA, (u32)(Data));
    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_RD_DATA + 4, (u32)(Data >> 32));
}

u64 XCnn_pipeline_v10_Get_activation_a_rd(XCnn_pipeline_v10 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_RD_DATA);
    Data += (u64)XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_RD_DATA + 4) << 32;
    return Data;
}

void XCnn_pipeline_v10_Set_activation_a_wr(XCnn_pipeline_v10 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_WR_DATA, (u32)(Data));
    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_WR_DATA + 4, (u32)(Data >> 32));
}

u64 XCnn_pipeline_v10_Get_activation_a_wr(XCnn_pipeline_v10 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_WR_DATA);
    Data += (u64)XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_A_WR_DATA + 4) << 32;
    return Data;
}

void XCnn_pipeline_v10_Set_activation_b_rd(XCnn_pipeline_v10 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_RD_DATA, (u32)(Data));
    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_RD_DATA + 4, (u32)(Data >> 32));
}

u64 XCnn_pipeline_v10_Get_activation_b_rd(XCnn_pipeline_v10 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_RD_DATA);
    Data += (u64)XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_RD_DATA + 4) << 32;
    return Data;
}

void XCnn_pipeline_v10_Set_activation_b_wr(XCnn_pipeline_v10 *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_WR_DATA, (u32)(Data));
    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_WR_DATA + 4, (u32)(Data >> 32));
}

u64 XCnn_pipeline_v10_Get_activation_b_wr(XCnn_pipeline_v10 *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_WR_DATA);
    Data += (u64)XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ACTIVATION_B_WR_DATA + 4) << 32;
    return Data;
}

void XCnn_pipeline_v10_Set_profile(XCnn_pipeline_v10 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PROFILE_DATA, Data);
}

u32 XCnn_pipeline_v10_Get_profile(XCnn_pipeline_v10 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PROFILE_DATA);
    return Data;
}

void XCnn_pipeline_v10_Set_block_count(XCnn_pipeline_v10 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_BLOCK_COUNT_DATA, Data);
}

u32 XCnn_pipeline_v10_Get_block_count(XCnn_pipeline_v10 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_BLOCK_COUNT_DATA);
    return Data;
}

void XCnn_pipeline_v10_Set_params_words(XCnn_pipeline_v10 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_WORDS_DATA, Data);
}

u32 XCnn_pipeline_v10_Get_params_words(XCnn_pipeline_v10 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_PARAMS_WORDS_DATA);
    return Data;
}

void XCnn_pipeline_v10_Set_slot_words(XCnn_pipeline_v10 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_SLOT_WORDS_DATA, Data);
}

u32 XCnn_pipeline_v10_Get_slot_words(XCnn_pipeline_v10 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_SLOT_WORDS_DATA);
    return Data;
}

void XCnn_pipeline_v10_Set_arena_words(XCnn_pipeline_v10 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ARENA_WORDS_DATA, Data);
}

u32 XCnn_pipeline_v10_Get_arena_words(XCnn_pipeline_v10 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_ARENA_WORDS_DATA);
    return Data;
}

void XCnn_pipeline_v10_Set_flags(XCnn_pipeline_v10 *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XCnn_pipeline_v10_WriteReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_FLAGS_DATA, Data);
}

u32 XCnn_pipeline_v10_Get_flags(XCnn_pipeline_v10 *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XCnn_pipeline_v10_ReadReg(InstancePtr->Control_BaseAddress, XCNN_PIPELINE_V10_CONTROL_ADDR_FLAGS_DATA);
    return Data;
}

