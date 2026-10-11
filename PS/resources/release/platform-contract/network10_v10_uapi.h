/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef NETWORK10_V10_UAPI_H
#define NETWORK10_V10_UAPI_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define NETWORK10_V10_ABI_VERSION 10U
#define NETWORK10_V10_PROFILE_COUNT 3U
#define NETWORK10_V10_IDENTITY_PROFILE_SLOTS 7U
#define NETWORK10_V10_IDENTITY_BYTES 200U
#define NETWORK10_V10_CORE_ID 0x465A5641U /* FZVA */
#define NETWORK10_V10_CORE_ABI 0x000A0001U
#define NETWORK10_V10_GUARD_CAPS 0x000007ffU

#define NETWORK10_V10_PROFILE_NETWORK2 0U
#define NETWORK10_V10_PROFILE_NETWORK4 1U
#define NETWORK10_V10_PROFILE_NETWORK0 2U

#define NETWORK10_V10_PROFILE0_CHANNELS 128U
#define NETWORK10_V10_PROFILE0_WIDTH 32U
#define NETWORK10_V10_PROFILE0_MAX_BLOCKS 12U
#define NETWORK10_V10_PROFILE0_BLOCK_STRIDE_WORDS 21081U
#define NETWORK10_V10_PROFILE0_SLOT_WORDS 16384U
#define NETWORK10_V10_PROFILE0_ARENA_WORDS 36864U
#define NETWORK10_V10_PROFILE1_CHANNELS 256U
#define NETWORK10_V10_PROFILE1_WIDTH 16U
#define NETWORK10_V10_PROFILE1_MAX_BLOCKS 20U
#define NETWORK10_V10_PROFILE1_BLOCK_STRIDE_WORDS 59705U
#define NETWORK10_V10_PROFILE1_SLOT_WORDS 8192U
#define NETWORK10_V10_PROFILE1_ARENA_WORDS 20480U
#define NETWORK10_V10_PROFILE2_CHANNELS 64U
#define NETWORK10_V10_PROFILE2_WIDTH 64U
#define NETWORK10_V10_PROFILE2_MAX_BLOCKS 4U
#define NETWORK10_V10_PROFILE2_BLOCK_STRIDE_WORDS 10985U
#define NETWORK10_V10_PROFILE2_SLOT_WORDS 32768U
#define NETWORK10_V10_PROFILE2_ARENA_WORDS 69632U
#define NETWORK10_V10_SCRATCH_WORDS 4096U

#define NETWORK10_V10_CAP_LOW_ARENA  (1U << 0)
#define NETWORK10_V10_CAP_HIGH_ARENA (1U << 1)
#define NETWORK10_V10_CAP_SIX_M_AXI  (1U << 2)
#define NETWORK10_V10_FLAG_POISONED (1U << 0)
#define NETWORK10_V10_FLAG_QUIESCED (1U << 1)
#define NETWORK10_V10_FLAG_REMOVING (1U << 2)
#define NETWORK10_V10_FLAG_RUNNING  (1U << 3)
#define NETWORK10_V10_ALLOC_LOW_ONLY  (1U << 0)
#define NETWORK10_V10_ALLOC_HIGH_ONLY (1U << 1)
#define NETWORK10_V10_ALLOC_MASK \
	(NETWORK10_V10_ALLOC_LOW_ONLY | NETWORK10_V10_ALLOC_HIGH_ONLY)

/* The identity record deliberately retains the proven 200-byte software
 * envelope. CAPS=0x7ff has ABI10 six-master semantics and rejects V8/V9. */
struct network10_v10_identity {
	__u32 core_id, core_abi, guard_caps, abi_version;
	__u32 caps, address_bits, data_bits, arena_count, profile_count;
	__u32 max_blocks[NETWORK10_V10_IDENTITY_PROFILE_SLOTS];
	__u32 channels[NETWORK10_V10_IDENTITY_PROFILE_SLOTS];
	__u32 widths[NETWORK10_V10_IDENTITY_PROFILE_SLOTS];
	__u32 block_stride_words[NETWORK10_V10_IDENTITY_PROFILE_SLOTS];
	__u32 reserved0;
	__u64 arena_bytes[2];
	__u32 software_parameter_manifest_words[8];
};

struct network10_v10_alloc {
	__u64 bytes, alignment;
	__u32 flags, handle, arena_index, reserved;
};
struct network10_v10_free { __u32 handle, reserved; };
struct network10_v10_transfer {
	__u32 handle, reserved;
	__u64 offset, bytes, user_ptr;
};

/* Frozen host descriptor. The driver writes the one parameter physical
 * address to both HLS parameter pointers. Each activation handle supplies
 * both read and write pointers for one independent image arena. */
struct network10_v10_submit {
	__u32 profile, block_count, params_handle;
	__u32 activation_a_handle, activation_b_handle;
	__u32 activation_a_base_offset_bytes;
	__u32 activation_b_base_offset_bytes;
	__u32 reserved;
};

/* The 60-byte status wire layout is retained; guard fields use ABI10's
 * six-master ACK/capability semantics and are not compatible with V8/V9. */
struct network10_v10_status {
	__u32 completed_pairs, protocol_error, flags, profile;
	__u32 guard_status, guard_acks, ar_total, rlast_total, aw_total;
	__u32 wlast_total, b_total, reset_generation, guard_error_flags;
	__u32 job_cycles_lo, job_cycles_hi;
};

#define NETWORK10_V10_IOC_MAGIC 'X'
#define NETWORK10_V10_IOC_GET_IDENTITY \
	_IOR(NETWORK10_V10_IOC_MAGIC, 0x40, struct network10_v10_identity)
#define NETWORK10_V10_IOC_ALLOC \
	_IOWR(NETWORK10_V10_IOC_MAGIC, 0x41, struct network10_v10_alloc)
#define NETWORK10_V10_IOC_FREE \
	_IOW(NETWORK10_V10_IOC_MAGIC, 0x42, struct network10_v10_free)
#define NETWORK10_V10_IOC_UPLOAD \
	_IOW(NETWORK10_V10_IOC_MAGIC, 0x43, struct network10_v10_transfer)
#define NETWORK10_V10_IOC_DOWNLOAD \
	_IOW(NETWORK10_V10_IOC_MAGIC, 0x44, struct network10_v10_transfer)
#define NETWORK10_V10_IOC_SUBMIT \
	_IOW(NETWORK10_V10_IOC_MAGIC, 0x45, struct network10_v10_submit)
#define NETWORK10_V10_IOC_GET_STATUS \
	_IOR(NETWORK10_V10_IOC_MAGIC, 0x46, struct network10_v10_status)
#define NETWORK10_V10_IOC_QUIESCE _IO(NETWORK10_V10_IOC_MAGIC, 0x47)

#endif
