/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef NETWORK10_V10_UAPI_H
#define NETWORK10_V10_UAPI_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define NETWORK10_V10_ABI_VERSION 10U
#define NETWORK10_V10_PROFILE_COUNT 4U
#define NETWORK10_V10_IDENTITY_PROFILE_SLOTS 7U
#define NETWORK10_V10_IDENTITY_BYTES 200U
#define NETWORK10_V10_CORE_ID 0x465A5641U /* FZVA */
#define NETWORK10_V10_CORE_ABI 0x000A0005U
#define NETWORK10_V10_GUARD_CAPS 0x00000fffU
#define NETWORK10_V10_CAP_PW2_SIGNED40_APPROVED_PARAMS_V1 (1U << 11)

#define NETWORK10_V10_PROFILE_NETWORK2 0U
#define NETWORK10_V10_PROFILE_NETWORK4 1U
#define NETWORK10_V10_PROFILE_NETWORK0 2U
#define NETWORK10_V10_PROFILE_P3 3U

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
#define NETWORK10_V10_PROFILE3_CHANNELS 64U
#define NETWORK10_V10_PROFILE3_WIDTH 64U
#define NETWORK10_V10_PROFILE3_MAX_BLOCKS 1U
#define NETWORK10_V10_PROFILE3_BLOCK_STRIDE_WORDS 11280U
#define NETWORK10_V10_PROFILE3_SLOT_WORDS 32768U
#define NETWORK10_V10_PROFILE3_ARENA_WORDS 69632U
#define NETWORK10_V10_PROFILE3_FINAL_OUTPUT_WORDS 16384U
#define NETWORK10_V10_SCRATCH_WORDS 4096U
#define NETWORK10_V10_EXTERNAL_STAGE_RING_WORDS 0U

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
 * envelope. GUARD_CAPS=0xfff adds the A0005 approved-parameter signed40
 * storage contract while retaining ABI10 wire layouts. */
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

/* Additive host-transfer ABI.  It does not change the 200-byte accelerator
 * identity or the frozen SUBMIT/status records. */
#define NETWORK10_V10_TRANSFER_ABI_VERSION 2U
#define NETWORK10_V10_TRANSFER_CAP_WC_MMAP       (1U << 0)
#define NETWORK10_V10_TRANSFER_CAP_CPU_WC_COPY   (1U << 1)
#define NETWORK10_V10_TRANSFER_CAP_DMAENGINE_COPY (1U << 2)
#define NETWORK10_V10_TRANSFER_CAP_CACHED_DMA_UPLOAD (1U << 3)
#define NETWORK10_V10_MAP_READ  1U
#define NETWORK10_V10_MAP_WRITE 2U
#define NETWORK10_V10_SYNC_COMMIT_HOST_WRITE 1U
#define NETWORK10_V10_SYNC_PREPARE_CPU_READ  2U
#define NETWORK10_V10_COPY_ALLOW_CPU_FALLBACK (1U << 0)
#define NETWORK10_V10_COPY_REQUIRE_DMAENGINE  (1U << 1)
#define NETWORK10_V10_COPY_BACKEND_NONE       0U
#define NETWORK10_V10_COPY_BACKEND_CPU_WC     1U
#define NETWORK10_V10_COPY_BACKEND_DMAENGINE  2U
#define NETWORK10_V10_UPLOAD_BACKEND_DMA_CACHED 3U

struct network10_v10_transfer_caps {
	__u32 version, caps, alignment, page_size;
	__u32 max_timeout_ms, reserved0, reserved1, reserved2;
	__u64 max_map_bytes, max_copy_bytes;
};
struct network10_v10_map_request {
	__u32 handle, access;
	__u64 offset, bytes, ticket;
};
struct network10_v10_sync_range {
	__u32 handle, operation;
	__u64 offset, bytes;
};
struct network10_v10_copy_request {
	__u32 source_handle, destination_handle;
	__u64 source_offset, destination_offset, bytes;
	__u32 flags, timeout_ms, backend, reserved;
};

/* Synchronous, read-only user-page to reserved-DDR upload.  Fixed 64-byte
 * layout; reserved words must be zero.  The caller must not modify the source
 * pages until ioctl returns. */
struct network10_v10_cached_upload {
	__u32 destination_handle, flags;
	__aligned_u64 destination_offset, bytes, user_ptr;
	__u32 timeout_ms, backend, segment_count, reserved0;
	__aligned_u64 dma_elapsed_ns, reserved1;
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
#define NETWORK10_V10_IOC_QUERY_TRANSFER_CAPS \
	_IOR(NETWORK10_V10_IOC_MAGIC, 0x48, struct network10_v10_transfer_caps)
#define NETWORK10_V10_IOC_MAP_PREP \
	_IOWR(NETWORK10_V10_IOC_MAGIC, 0x49, struct network10_v10_map_request)
#define NETWORK10_V10_IOC_MAP_CANCEL _IO(NETWORK10_V10_IOC_MAGIC, 0x4a)
#define NETWORK10_V10_IOC_SYNC_RANGE \
	_IOW(NETWORK10_V10_IOC_MAGIC, 0x4b, struct network10_v10_sync_range)
#define NETWORK10_V10_IOC_ARENA_COPY \
	_IOWR(NETWORK10_V10_IOC_MAGIC, 0x4c, struct network10_v10_copy_request)
#define NETWORK10_V10_IOC_UPLOAD_CACHED \
	_IOWR(NETWORK10_V10_IOC_MAGIC, 0x4d, struct network10_v10_cached_upload)

#endif
