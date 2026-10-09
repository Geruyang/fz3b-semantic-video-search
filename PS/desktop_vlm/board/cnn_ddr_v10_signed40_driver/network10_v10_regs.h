/* SPDX-License-Identifier: GPL-2.0 */
#ifndef NETWORK10_V10_REGS_H
#define NETWORK10_V10_REGS_H

/* Six-master FZVA guard candidate. These offsets retain the prior guard
 * envelope, but CAPS=0x7ff and ACKS packing have ABI10-only semantics.
 * Do not bind an older driver by treating the common offsets as compatibility.
 * HLS offsets below are frozen against the HLS004 generated driver header
 * (SHA256 edd8e1e683a06817f6c91843d375d0d29e266372a819a58ea1cd6cc4fb18e3bc)
 * and control RTL
 * (SHA256 ea1748e5979c61e1c5f7d704a0e8577192d4bef938e2bc5396c2c0c07f5c68c4).
 * A later packaged HLS revision must reproduce this map before deployment. */
#define V10_GUARD_ID                0x00
#define V10_GUARD_ABI               0x04
#define V10_GUARD_CAPS              0x08
#define V10_GUARD_CONTROL           0x0c
#define V10_GUARD_STATUS            0x10
#define V10_GUARD_ACKS              0x14
#define V10_GUARD_AR_TOTAL          0x18
#define V10_GUARD_RLAST_TOTAL       0x1c
#define V10_GUARD_AW_TOTAL          0x20
#define V10_GUARD_WLAST_TOTAL       0x24
#define V10_GUARD_B_TOTAL           0x28
#define V10_GUARD_ERROR_FLAGS       0x2c
#define V10_GUARD_RESET_GENERATION  0x30
#define V10_GUARD_JOB_CYCLES_LO     0x34
#define V10_GUARD_JOB_CYCLES_HI     0x38
#define V10_GUARD_PROTOCOL_ERROR    0x3c

/* The guard owns ap_start; software must not write the HLS ap_ctrl register. */
#define V10_HLS_PARAM1_LO      0x10
#define V10_HLS_PARAM1_HI      0x14
#define V10_HLS_PARAM2_LO      0x1c
#define V10_HLS_PARAM2_HI      0x20
#define V10_HLS_ACT_A_R_LO     0x28
#define V10_HLS_ACT_A_R_HI     0x2c
#define V10_HLS_ACT_A_W_LO     0x34
#define V10_HLS_ACT_A_W_HI     0x38
#define V10_HLS_ACT_B_R_LO     0x40
#define V10_HLS_ACT_B_R_HI     0x44
#define V10_HLS_ACT_B_W_LO     0x4c
#define V10_HLS_ACT_B_W_HI     0x50
#define V10_HLS_PROFILE        0x58
#define V10_HLS_BLOCK_COUNT    0x60
#define V10_HLS_PARAMS_WORDS   0x68
#define V10_HLS_SLOT_WORDS     0x70
#define V10_HLS_ARENA_WORDS    0x78
#define V10_HLS_FLAGS          0x80
#define V10_HLS_REQUIRED_BYTES 0x84

#define V10_GUARD_CTL_SET_SHUTDOWN      (1U << 0)
#define V10_GUARD_CTL_CLEAR_SHUTDOWN    (1U << 1)
#define V10_GUARD_CTL_SAFE_RESET        (1U << 2)
#define V10_GUARD_CTL_CLEAR_COUNTERS    (1U << 3)
#define V10_GUARD_CTL_PERMANENT_POISON  (1U << 4)
#define V10_GUARD_CTL_START             (1U << 5)

#define V10_GUARD_ST_SHUTDOWN_REQ       (1U << 0)
#define V10_GUARD_ST_ALL_SHUTDOWN       (1U << 1)
#define V10_GUARD_ST_ALL_RD_IDLE        (1U << 2)
#define V10_GUARD_ST_ALL_WR_IDLE        (1U << 3)
#define V10_GUARD_ST_COUNTERS_EQUAL     (1U << 4)
#define V10_GUARD_ST_SAFE_TO_RESET      (1U << 5)
#define V10_GUARD_ST_RESET_ACTIVE       (1U << 6)
#define V10_GUARD_ST_POISON             (1U << 7)
#define V10_GUARD_ST_AXI_RESP_ERROR     (1U << 8)
#define V10_GUARD_ST_COUNTER_ERROR      (1U << 9)
#define V10_GUARD_ST_HLS_IDLE           (1U << 10)
#define V10_GUARD_ST_DONE_LATCHED       (1U << 11)
#define V10_GUARD_ST_RESET_FEEDBACK_N   (1U << 12)
#define V10_GUARD_ST_JOB_BUSY           (1U << 13)
#define V10_GUARD_ST_HLS_READY          (1U << 14)
#define V10_GUARD_ST_TIMER_RUNNING      (1U << 15)

#define V10_GUARD_ERR_POISON            (1U << 1)
#define V10_GUARD_ERR_AXI_RESP          (1U << 2)
#define V10_GUARD_ERR_COUNTER           (1U << 3)
#define V10_GUARD_ERR_HLS_PROTOCOL      (1U << 4)

#define V10_GUARD_BAD_STATUS (V10_GUARD_ST_POISON | \
	V10_GUARD_ST_AXI_RESP_ERROR | V10_GUARD_ST_COUNTER_ERROR)
#define V10_GUARD_COMPLETE_STATUS (V10_GUARD_ST_COUNTERS_EQUAL | \
	V10_GUARD_ST_HLS_IDLE | V10_GUARD_ST_DONE_LATCHED)

/* Master bit order: PARAM1, PARAM2, A_READ, A_WRITE, B_READ, B_WRITE. */
#define V10_MASTER_PARAM1  0U
#define V10_MASTER_PARAM2  1U
#define V10_MASTER_A_READ  2U
#define V10_MASTER_A_WRITE 3U
#define V10_MASTER_B_READ  4U
#define V10_MASTER_B_WRITE 5U
#define V10_MASTER_MASK    0x3fU
#define V10_ACK_ALL_SHIFT   0U
#define V10_ACK_READ_SHIFT  6U
#define V10_ACK_WRITE_SHIFT 12U
#define V10_ACK_ALL_MASK    (V10_MASTER_MASK << V10_ACK_ALL_SHIFT)
#define V10_ACK_READ_MASK   (V10_MASTER_MASK << V10_ACK_READ_SHIFT)
#define V10_ACK_WRITE_MASK  (V10_MASTER_MASK << V10_ACK_WRITE_SHIFT)
#define V10_ACK_PACKED_MASK 0x3ffffU

#define V10_CORE_ID   0x465a5641U
#define V10_CORE_ABI  0x000a0005U
#define V10_CORE_CAPS 0x00000fffU

#endif
