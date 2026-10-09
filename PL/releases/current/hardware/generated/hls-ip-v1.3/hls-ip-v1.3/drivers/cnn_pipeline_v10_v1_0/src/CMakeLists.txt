# ==============================================================
# Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2026.1 (64-bit)
# Tool Version Limit: 2026.06
# Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
# Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
# 
# ==============================================================
cmake_minimum_required(VERSION 3.15)
project(cnn_pipeline_v10)
find_package(common)
collector_create (PROJECT_LIB_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}")
collect (PROJECT_LIB_SOURCES xcnn_pipeline_v10.c)
collect (PROJECT_LIB_SOURCES xcnn_pipeline_v10_sinit.c)
collect (PROJECT_LIB_SOURCES xcnn_pipeline_v10_linux.c)
collect (PROJECT_LIB_SOURCES xcnn_pipeline_v10_g.c)
collector_list (_sources PROJECT_LIB_SOURCES)
collector_create (PROJECT_LIB_HEADERS "${CMAKE_CURRENT_SOURCE_DIR}")
collect (PROJECT_LIB_HEADERS xcnn_pipeline_v10.h)
collect (PROJECT_LIB_HEADERS xcnn_pipeline_v10_hw.h)
collector_list (_headers PROJECT_LIB_HEADERS)
file(COPY ${_headers} DESTINATION ${CMAKE_BINARY_DIR}/include)
include_directories(${CMAKE_BINARY_DIR}/include)
add_library(cnn_pipeline_v10 STATIC ${_sources})
set_target_properties(cnn_pipeline_v10 PROPERTIES LINKER_LANGUAGE C)

