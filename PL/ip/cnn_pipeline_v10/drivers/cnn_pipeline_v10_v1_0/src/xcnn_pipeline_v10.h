// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XCNN_PIPELINE_V10_H
#define XCNN_PIPELINE_V10_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
#ifndef __linux__
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#else
#include <stdint.h>
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stddef.h>
#endif
#include "xcnn_pipeline_v10_hw.h"

/**************************** Type Definitions ******************************/
#ifdef __linux__
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#else
typedef struct {
#ifdef SDT
    char *Name;
#else
    u16 DeviceId;
#endif
    u64 Control_BaseAddress;
} XCnn_pipeline_v10_Config;
#endif

typedef struct {
    u64 Control_BaseAddress;
    u32 IsReady;
} XCnn_pipeline_v10;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XCnn_pipeline_v10_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XCnn_pipeline_v10_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XCnn_pipeline_v10_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XCnn_pipeline_v10_ReadReg(BaseAddress, RegOffset) \
    *(volatile u32*)((BaseAddress) + (RegOffset))

#define Xil_AssertVoid(expr)    assert(expr)
#define Xil_AssertNonvoid(expr) assert(expr)

#define XST_SUCCESS             0
#define XST_DEVICE_NOT_FOUND    2
#define XST_OPEN_DEVICE_FAILED  3
#define XIL_COMPONENT_IS_READY  1
#endif

/************************** Function Prototypes *****************************/
#ifndef __linux__
#ifdef SDT
int XCnn_pipeline_v10_Initialize(XCnn_pipeline_v10 *InstancePtr, UINTPTR BaseAddress);
XCnn_pipeline_v10_Config* XCnn_pipeline_v10_LookupConfig(UINTPTR BaseAddress);
#else
int XCnn_pipeline_v10_Initialize(XCnn_pipeline_v10 *InstancePtr, u16 DeviceId);
XCnn_pipeline_v10_Config* XCnn_pipeline_v10_LookupConfig(u16 DeviceId);
#endif
int XCnn_pipeline_v10_CfgInitialize(XCnn_pipeline_v10 *InstancePtr, XCnn_pipeline_v10_Config *ConfigPtr);
#else
int XCnn_pipeline_v10_Initialize(XCnn_pipeline_v10 *InstancePtr, const char* InstanceName);
int XCnn_pipeline_v10_Release(XCnn_pipeline_v10 *InstancePtr);
#endif


void XCnn_pipeline_v10_Set_params_pw1(XCnn_pipeline_v10 *InstancePtr, u64 Data);
u64 XCnn_pipeline_v10_Get_params_pw1(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_params_pw2(XCnn_pipeline_v10 *InstancePtr, u64 Data);
u64 XCnn_pipeline_v10_Get_params_pw2(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_activation_a_rd(XCnn_pipeline_v10 *InstancePtr, u64 Data);
u64 XCnn_pipeline_v10_Get_activation_a_rd(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_activation_a_wr(XCnn_pipeline_v10 *InstancePtr, u64 Data);
u64 XCnn_pipeline_v10_Get_activation_a_wr(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_activation_b_rd(XCnn_pipeline_v10 *InstancePtr, u64 Data);
u64 XCnn_pipeline_v10_Get_activation_b_rd(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_activation_b_wr(XCnn_pipeline_v10 *InstancePtr, u64 Data);
u64 XCnn_pipeline_v10_Get_activation_b_wr(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_profile(XCnn_pipeline_v10 *InstancePtr, u32 Data);
u32 XCnn_pipeline_v10_Get_profile(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_block_count(XCnn_pipeline_v10 *InstancePtr, u32 Data);
u32 XCnn_pipeline_v10_Get_block_count(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_params_words(XCnn_pipeline_v10 *InstancePtr, u32 Data);
u32 XCnn_pipeline_v10_Get_params_words(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_slot_words(XCnn_pipeline_v10 *InstancePtr, u32 Data);
u32 XCnn_pipeline_v10_Get_slot_words(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_arena_words(XCnn_pipeline_v10 *InstancePtr, u32 Data);
u32 XCnn_pipeline_v10_Get_arena_words(XCnn_pipeline_v10 *InstancePtr);
void XCnn_pipeline_v10_Set_flags(XCnn_pipeline_v10 *InstancePtr, u32 Data);
u32 XCnn_pipeline_v10_Get_flags(XCnn_pipeline_v10 *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
