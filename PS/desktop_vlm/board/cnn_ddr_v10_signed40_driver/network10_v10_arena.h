/* SPDX-License-Identifier: GPL-2.0 */
#ifndef NETWORK10_V10_ARENA_H
#define NETWORK10_V10_ARENA_H

#include <linux/bitmap.h>
#include <linux/ioport.h>
#include <linux/mutex.h>
#include <linux/types.h>

#define NETWORK10_V10_ARENA_COUNT 2U
#define NETWORK10_V10_LOW_ARENA 0U
#define NETWORK10_V10_HIGH_ARENA 1U
#define NETWORK10_V10_ARENA_GRANULE (64U * 1024U)
#define NETWORK10_V10_MAX_ARENA_GRANULES 16384U
#define NETWORK10_V10_MAX_OBJECTS 512U
#define NETWORK10_V10_MAX_INIT_RANGES 32U
#define NETWORK10_V10_COPY_CHUNK (64U * 1024U)
/* Bound temporary ioremap_wc() virtual address space per transfer ioctl. */
#define NETWORK10_V10_MAX_TRANSFER_BYTES (32U * 1024U * 1024U)
#define NETWORK10_V10_QUIESCE_ALREADY 1
#define NETWORK10_V10_QUIESCE_POISONED 2

struct network10_v10_initialized_range { u64 offset, bytes; };
struct network10_v10_arena {
	resource_size_t base;
	u64 bytes;
	u32 granules;
	bool enabled, claimed;
	unsigned long used[BITS_TO_LONGS(NETWORK10_V10_MAX_ARENA_GRANULES)];
};
struct network10_v10_object {
	u64 offset, bytes;
	u32 granules;
	u16 generation;
	u8 arena_index, init_range_count;
	u16 job_refs, transfer_refs, map_refs;
	u32 map_access;
	u64 map_offset, map_bytes;
	bool active, write_failed;
	struct network10_v10_initialized_range initialized_range[NETWORK10_V10_MAX_INIT_RANGES];
};
struct network10_v10_arena_set {
	struct mutex lock;
	struct network10_v10_arena arena[NETWORK10_V10_ARENA_COUNT];
	struct network10_v10_object object[NETWORK10_V10_MAX_OBJECTS];
	u32 active_transfers;
	bool quiescing, quiesced, poisoned, removing;
};

int network10_v10_arenas_init(struct network10_v10_arena_set *set,
			    resource_size_t low_base, u64 low_bytes,
			    resource_size_t high_base, u64 high_bytes,
			    bool enable_high, const char *owner);
void network10_v10_arenas_destroy(struct network10_v10_arena_set *set, const char *owner);
int network10_v10_arena_alloc(struct network10_v10_arena_set *set, u64 bytes,
			    u64 alignment, u32 flags, u32 *handle, u32 *arena_index);
int network10_v10_arena_free(struct network10_v10_arena_set *set, u32 handle);
int network10_v10_arena_describe(struct network10_v10_arena_set *set, u32 handle,
			       u64 *bytes, u32 *arena_index);
int network10_v10_arena_pin_job(struct network10_v10_arena_set *set, u32 params,
				u32 activation_a, u32 activation_b);
void network10_v10_arena_unpin_job(struct network10_v10_arena_set *set, u32 params,
				   u32 activation_a, u32 activation_b);
int network10_v10_arena_begin_quiesce(struct network10_v10_arena_set *set, bool removing);
void network10_v10_arena_mark_quiesced(struct network10_v10_arena_set *set);
void network10_v10_arena_poison(struct network10_v10_arena_set *set);
int network10_v10_arena_wait_transfers(struct network10_v10_arena_set *set);
bool network10_v10_arena_refs_clear(struct network10_v10_arena_set *set);
int network10_v10_arena_resolve(struct network10_v10_arena_set *set, u32 handle,
			      u64 offset, u64 bytes, u64 alignment, resource_size_t *physical);
int network10_v10_arena_require_initialized(struct network10_v10_arena_set *set,
					  u32 handle, u64 offset, u64 bytes);
int network10_v10_arena_mark_initialized(struct network10_v10_arena_set *set,
				       u32 handle, u64 offset, u64 bytes);
int network10_v10_arena_begin_map(struct network10_v10_arena_set *set,
				u32 handle, u64 offset, u64 bytes, u32 access,
				resource_size_t *physical);
void network10_v10_arena_end_map(struct network10_v10_arena_set *set,
			       u32 handle);
int network10_v10_arena_sync_range(struct network10_v10_arena_set *set,
				 u32 handle, u64 offset, u64 bytes, u32 operation);
int network10_v10_arena_pin_copy(struct network10_v10_arena_set *set,
			       u32 source_handle, u64 source_offset,
			       u32 destination_handle, u64 destination_offset,
			       u64 bytes, resource_size_t *source_physical,
			       resource_size_t *destination_physical);
int network10_v10_arena_pin_upload(struct network10_v10_arena_set *set,
				 u32 handle, u64 offset, u64 bytes,
				 resource_size_t *destination_physical);
void network10_v10_arena_complete_upload(struct network10_v10_arena_set *set,
					 u32 handle, u64 offset, u64 bytes,
					 bool success);
void network10_v10_arena_complete_copy(struct network10_v10_arena_set *set,
				     u32 source_handle,
				     u32 destination_handle,
				     u64 destination_offset, u64 bytes,
				     bool success);
int network10_v10_arena_upload(struct network10_v10_arena_set *set, u32 handle,
			     u64 offset, u64 bytes, const void __user *source);
int network10_v10_arena_download(struct network10_v10_arena_set *set, u32 handle,
			       u64 offset, u64 bytes, void __user *destination);

#endif

