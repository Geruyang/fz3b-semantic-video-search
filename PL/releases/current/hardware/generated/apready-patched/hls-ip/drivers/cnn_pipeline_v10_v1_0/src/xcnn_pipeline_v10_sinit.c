// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
// Tool Version Limit: 2026.06
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef __linux__

#include "xstatus.h"
#ifdef SDT
#include "xparameters.h"
#endif
#include "xcnn_pipeline_v10.h"

extern XCnn_pipeline_v10_Config XCnn_pipeline_v10_ConfigTable[];

#ifdef SDT
XCnn_pipeline_v10_Config *XCnn_pipeline_v10_LookupConfig(UINTPTR BaseAddress) {
	XCnn_pipeline_v10_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XCnn_pipeline_v10_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XCnn_pipeline_v10_ConfigTable[Index].Control_BaseAddress == BaseAddress) {
			ConfigPtr = &XCnn_pipeline_v10_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XCnn_pipeline_v10_Initialize(XCnn_pipeline_v10 *InstancePtr, UINTPTR BaseAddress) {
	XCnn_pipeline_v10_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XCnn_pipeline_v10_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XCnn_pipeline_v10_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XCnn_pipeline_v10_Config *XCnn_pipeline_v10_LookupConfig(u16 DeviceId) {
	XCnn_pipeline_v10_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XCNN_PIPELINE_V10_NUM_INSTANCES; Index++) {
		if (XCnn_pipeline_v10_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XCnn_pipeline_v10_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XCnn_pipeline_v10_Initialize(XCnn_pipeline_v10 *InstancePtr, u16 DeviceId) {
	XCnn_pipeline_v10_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XCnn_pipeline_v10_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XCnn_pipeline_v10_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

