// SPDX-License-Identifier: GPL-2.0
#include <linux/errno.h>
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/jiffies.h>
#include <linux/kernel.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include <linux/uaccess.h>

#include "network10_v10_arena.h"
#include "network10_v10_uapi.h"

#define NETWORK10_V10_TRANSFER_DRAIN_TIMEOUT_MS 2000U

static void copy_initialized_range(struct network10_v10_initialized_range *dst,
				   const struct network10_v10_initialized_range *src)
{
	dst->offset = src->offset;
	dst->bytes = src->bytes;
}

static int decode_handle(struct network10_v10_arena_set *set, u32 handle,
			 struct network10_v10_object **object)
{
	u32 slot = handle & 0xffffU;
	u16 generation = handle >> 16;
	struct network10_v10_object *candidate;

	if (!slot || slot > NETWORK10_V10_MAX_OBJECTS || !generation)
		return -ENOENT;
	candidate = &set->object[slot - 1];
	if (!candidate->active || candidate->generation != generation)
		return -ENOENT;
	*object = candidate;
	return 0;
}

static int claim_arena(struct network10_v10_arena *arena, resource_size_t base,
		       u64 bytes, const char *owner)
{
	if (!bytes || bytes % NETWORK10_V10_ARENA_GRANULE ||
	    bytes / NETWORK10_V10_ARENA_GRANULE > NETWORK10_V10_MAX_ARENA_GRANULES ||
	    base + bytes < base)
		return -EINVAL;
	if (!request_mem_region(base, bytes, owner))
		return -EBUSY;
	arena->base = base;
	arena->bytes = bytes;
	arena->granules = bytes / NETWORK10_V10_ARENA_GRANULE;
	arena->enabled = arena->claimed = true;
	bitmap_zero(arena->used, NETWORK10_V10_MAX_ARENA_GRANULES);
	return 0;
}

int network10_v10_arenas_init(struct network10_v10_arena_set *set,
			    resource_size_t low_base, u64 low_bytes,
			    resource_size_t high_base, u64 high_bytes,
			    bool enable_high, const char *owner)
{
	int ret;
	if (!set || !owner)
		return -EINVAL;
	memset(set, 0, sizeof(*set));
	mutex_init(&set->lock);
	ret = claim_arena(&set->arena[NETWORK10_V10_LOW_ARENA], low_base, low_bytes, owner);
	if (ret)
		return ret;
	if (enable_high) {
		ret = claim_arena(&set->arena[NETWORK10_V10_HIGH_ARENA], high_base,
				  high_bytes, owner);
		if (ret) {
			release_mem_region(low_base, low_bytes);
			memset(set, 0, sizeof(*set));
			return ret;
		}
	}
	return 0;
}

void network10_v10_arenas_destroy(struct network10_v10_arena_set *set, const char *owner)
{
	u32 i;
	if (!set || !owner)
		return;
	mutex_lock(&set->lock);
	for (i = 0; i < NETWORK10_V10_ARENA_COUNT; ++i)
		if (set->arena[i].claimed)
			release_mem_region(set->arena[i].base, set->arena[i].bytes);
	memset(set->arena, 0, sizeof(set->arena));
	memset(set->object, 0, sizeof(set->object));
	mutex_unlock(&set->lock);
}

static int find_free_run(struct network10_v10_arena *arena, u32 needed,
			 u32 alignment_granules, u32 *first)
{
	u32 start, bit;
	if (!needed || needed > arena->granules)
		return -ENOSPC;
	for (start = 0; start <= arena->granules - needed;) {
		start = ALIGN(start, alignment_granules);
		if (start > arena->granules - needed)
			break;
		for (bit = start; bit < start + needed; ++bit)
			if (test_bit(bit, arena->used))
				break;
		if (bit == start + needed) {
			*first = start;
			return 0;
		}
		start = bit + 1;
	}
	return -ENOSPC;
}

static void set_granule_run(struct network10_v10_arena *arena, u32 first,
			    u32 count, bool value)
{
	u32 bit;
	for (bit = first; bit < first + count; ++bit) {
		u32 word = bit / BITS_PER_LONG;
		unsigned long mask = 1UL << (bit % BITS_PER_LONG);
		if (value) arena->used[word] |= mask;
		else arena->used[word] &= ~mask;
	}
}

int network10_v10_arena_alloc(struct network10_v10_arena_set *set, u64 bytes,
			    u64 alignment, u32 flags, u32 *handle, u32 *arena_index)
{
	struct network10_v10_object *object = NULL;
	u32 needed, alignment_granules, first = 0, object_index, i;
	int ret = -ENOSPC;
	if (!set || !handle || !arena_index || !bytes || (bytes & 15U) ||
	    (flags & ~NETWORK10_V10_ALLOC_MASK) || flags == NETWORK10_V10_ALLOC_MASK)
		return -EINVAL;
	if (bytes > (u64)NETWORK10_V10_MAX_ARENA_GRANULES * NETWORK10_V10_ARENA_GRANULE)
		return -E2BIG;
	if (!alignment) alignment = 16;
	if (alignment < 16 || !is_power_of_2(alignment) || alignment > (1ULL << 30))
		return -EINVAL;
	needed = DIV_ROUND_UP_ULL(bytes, NETWORK10_V10_ARENA_GRANULE);
	alignment_granules = max_t(u32, 1, DIV_ROUND_UP_ULL(alignment, NETWORK10_V10_ARENA_GRANULE));
	if (!is_power_of_2(alignment_granules))
		alignment_granules = roundup_pow_of_two(alignment_granules);
	mutex_lock(&set->lock);
	if (set->quiescing || set->quiesced || set->poisoned || set->removing) {
		ret = -ESHUTDOWN;
		goto out;
	}
	for (object_index = 0; object_index < NETWORK10_V10_MAX_OBJECTS; ++object_index)
		if (!set->object[object_index].active) {
			object = &set->object[object_index];
			break;
		}
	if (!object) goto out;
	for (i = 0; i < NETWORK10_V10_ARENA_COUNT; ++i) {
		struct network10_v10_arena *arena = &set->arena[i];
		if (!arena->enabled || ((flags & NETWORK10_V10_ALLOC_LOW_ONLY) && i != 0) ||
		    ((flags & NETWORK10_V10_ALLOC_HIGH_ONLY) && i != 1))
			continue;
		ret = find_free_run(arena, needed, alignment_granules, &first);
		if (ret) continue;
		set_granule_run(arena, first, needed, true);
		object->offset = (u64)first * NETWORK10_V10_ARENA_GRANULE;
		object->bytes = bytes;
		object->granules = needed;
		object->arena_index = i;
		object->init_range_count = 0;
		object->job_refs = object->transfer_refs = object->map_refs = 0;
		object->map_access = 0;
		object->map_offset = object->map_bytes = 0;
		object->write_failed = false;
		if (++object->generation == 0) object->generation = 1;
		object->active = true;
		*handle = ((u32)object->generation << 16) | (object_index + 1);
		*arena_index = i;
		ret = 0;
		break;
	}
out:
	mutex_unlock(&set->lock);
	return ret;
}

int network10_v10_arena_free(struct network10_v10_arena_set *set, u32 handle)
{
	struct network10_v10_object *object;
	struct network10_v10_arena *arena;
	int ret;
	if (!set) return -EINVAL;
	mutex_lock(&set->lock);
	if (set->removing || (set->poisoned && !set->quiesced)) {
		ret = -ESHUTDOWN;
		goto out;
	}
	ret = decode_handle(set, handle, &object);
	if (ret) goto out;
	if (object->job_refs || object->transfer_refs || object->map_refs) { ret = -EBUSY; goto out; }
	arena = &set->arena[object->arena_index];
	set_granule_run(arena, object->offset / NETWORK10_V10_ARENA_GRANULE,
			object->granules, false);
	object->active = false;
	object->offset = object->bytes = 0;
	object->granules = object->init_range_count = 0;
	object->map_access = 0;
	object->map_offset = object->map_bytes = 0;
	object->write_failed = false;
out:
	mutex_unlock(&set->lock);
	return ret;
}

int network10_v10_arena_describe(struct network10_v10_arena_set *set, u32 handle,
			       u64 *bytes, u32 *arena_index)
{
	struct network10_v10_object *object;
	int ret;
	if (!set || !bytes || !arena_index) return -EINVAL;
	mutex_lock(&set->lock);
	ret = decode_handle(set, handle, &object);
	if (!ret) { *bytes = object->bytes; *arena_index = object->arena_index; }
	mutex_unlock(&set->lock);
	return ret;
}

static bool span_covered(struct network10_v10_object *object, u64 offset, u64 bytes)
{
	u64 end = offset + bytes;
	u32 i;
	if (object->write_failed) return false;
	for (i = 0; i < object->init_range_count; ++i) {
		struct network10_v10_initialized_range *range = &object->initialized_range[i];
		if (range->offset <= offset && end <= range->offset + range->bytes)
			return true;
	}
	return false;
}

static void range_remove(struct network10_v10_object *object, u64 offset, u64 bytes)
{
	struct network10_v10_initialized_range temp[NETWORK10_V10_MAX_INIT_RANGES + 1];
	u64 end = offset + bytes;
	u32 i, count = 0;
	for (i = 0; i < object->init_range_count; ++i) {
		u64 a = object->initialized_range[i].offset;
		u64 b = a + object->initialized_range[i].bytes;
		if (b <= offset || a >= end) {
			copy_initialized_range(&temp[count++],
					       &object->initialized_range[i]);
		} else {
			if (a < offset) { temp[count].offset = a; temp[count++].bytes = offset - a; }
			if (b > end) { temp[count].offset = end; temp[count++].bytes = b - end; }
		}
	}
	if (count > NETWORK10_V10_MAX_INIT_RANGES) {
		object->init_range_count = 0;
		object->write_failed = false;
		return;
	}
	for (i = 0; i < count; ++i)
		copy_initialized_range(&object->initialized_range[i], &temp[i]);
	object->init_range_count = count;
}

static int range_add(struct network10_v10_object *object, u64 offset, u64 bytes)
{
	u64 start = offset, end = offset + bytes;
	u32 i, out = 0;
	struct network10_v10_initialized_range temp[NETWORK10_V10_MAX_INIT_RANGES];
	for (i = 0; i < object->init_range_count; ++i) {
		u64 a = object->initialized_range[i].offset;
		u64 b = a + object->initialized_range[i].bytes;
		if (b < start || a > end) {
			copy_initialized_range(&temp[out++],
					       &object->initialized_range[i]);
		}
		else { start = min(start, a); end = max(end, b); }
	}
	if (out >= NETWORK10_V10_MAX_INIT_RANGES) return -ENOSPC;
	temp[out].offset = start;
	temp[out++].bytes = end - start;
	/* Keep ranges sorted; max count is deliberately small. */
	for (i = 1; i < out; ++i) {
		struct network10_v10_initialized_range item;
		u32 j = i;
		copy_initialized_range(&item, &temp[i]);
		while (j && temp[j - 1].offset > item.offset) {
			copy_initialized_range(&temp[j], &temp[j - 1]);
			--j;
		}
		copy_initialized_range(&temp[j], &item);
	}
	for (i = 0; i < out; ++i)
		copy_initialized_range(&object->initialized_range[i], &temp[i]);
	object->init_range_count = out;
	return 0;
}

int network10_v10_arena_require_initialized(struct network10_v10_arena_set *set,
					  u32 handle, u64 offset, u64 bytes)
{
	struct network10_v10_object *object;
	int ret;
	if (!set || !bytes) return -EINVAL;
	mutex_lock(&set->lock);
	ret = decode_handle(set, handle, &object);
	if (!ret) {
		if (offset > object->bytes || bytes > object->bytes - offset)
			ret = -ERANGE;
		else if (!span_covered(object, offset, bytes))
			ret = -ENODATA;
	}
	mutex_unlock(&set->lock);
	return ret;
}

int network10_v10_arena_mark_initialized(struct network10_v10_arena_set *set,
				       u32 handle, u64 offset, u64 bytes)
{
	struct network10_v10_object *object;
	int ret;
	if (!set || !bytes) return -EINVAL;
	mutex_lock(&set->lock);
	ret = decode_handle(set, handle, &object);
	if (!ret) {
		if (offset > object->bytes || bytes > object->bytes - offset) ret = -ERANGE;
		else ret = range_add(object, offset, bytes);
	}
	mutex_unlock(&set->lock);
	return ret;
}

static int resolve_locked(struct network10_v10_arena_set *set, u32 handle,
			  u64 offset, u64 bytes, u64 alignment,
			  resource_size_t *physical)
{
	struct network10_v10_object *object;
	struct network10_v10_arena *arena;
	u64 address;
	int ret = decode_handle(set, handle, &object);
	if (ret) return ret;
	if (offset > object->bytes || bytes > object->bytes - offset) return -ERANGE;
	arena = &set->arena[object->arena_index];
	address = (u64)arena->base + object->offset + offset;
	if (address < (u64)arena->base || address + bytes < address ||
	    address + bytes > (u64)arena->base + arena->bytes ||
	    address >= (1ULL << 40) || address + bytes > (1ULL << 40) ||
	    (address & (alignment - 1))) return -ERANGE;
	*physical = (resource_size_t)address;
	return 0;
}

int network10_v10_arena_resolve(struct network10_v10_arena_set *set, u32 handle,
			      u64 offset, u64 bytes, u64 alignment, resource_size_t *physical)
{
	int ret;
	if (!set || !physical || !bytes || !alignment || !is_power_of_2(alignment)) return -EINVAL;
	mutex_lock(&set->lock);
	ret = resolve_locked(set, handle, offset, bytes, alignment, physical);
	mutex_unlock(&set->lock);
	return ret;
}

int network10_v10_arena_pin_job(struct network10_v10_arena_set *set, u32 params,
				u32 activation_a, u32 activation_b)
{
	struct network10_v10_object *p, *a, *b;
	int ret;
	mutex_lock(&set->lock);
	if (set->quiescing || set->quiesced || set->poisoned || set->removing) { ret = -ESHUTDOWN; goto out; }
	ret = decode_handle(set, params, &p);
	if (ret) goto out;
	ret = decode_handle(set, activation_a, &a);
	if (ret) goto out;
	ret = decode_handle(set, activation_b, &b);
	if (ret) goto out;
	if (p == a || p == b || a == b) { ret = -EINVAL; goto out; }
	if (p->job_refs || a->job_refs || b->job_refs || p->transfer_refs ||
	    a->transfer_refs || b->transfer_refs || p->map_refs ||
	    a->map_refs || b->map_refs) { ret = -EBUSY; goto out; }
	++p->job_refs;
	++a->job_refs;
	++b->job_refs;
	ret = 0;
out:
	mutex_unlock(&set->lock);
	return ret;
}

int network10_v10_arena_begin_quiesce(struct network10_v10_arena_set *set, bool removing)
{
	int ret = 0;
	mutex_lock(&set->lock);
	if (removing) {
		if (!set->quiesced)
			ret = -EBUSY;
		else
			set->removing = true;
	} else if (set->quiesced) {
		ret = NETWORK10_V10_QUIESCE_ALREADY;
	} else {
		set->quiescing = true;
		ret = set->poisoned ? NETWORK10_V10_QUIESCE_POISONED : 0;
	}
	mutex_unlock(&set->lock);
	return ret;
}

void network10_v10_arena_mark_quiesced(struct network10_v10_arena_set *set)
{
	mutex_lock(&set->lock);
	set->quiescing = true;
	set->quiesced = true;
	mutex_unlock(&set->lock);
}

void network10_v10_arena_poison(struct network10_v10_arena_set *set)
{
	mutex_lock(&set->lock);
	set->poisoned = true;
	set->quiescing = true;
	mutex_unlock(&set->lock);
}

int network10_v10_arena_wait_transfers(struct network10_v10_arena_set *set)
{
	unsigned long deadline;
	if (!set)
		return -EINVAL;
	deadline = jiffies +
		msecs_to_jiffies(NETWORK10_V10_TRANSFER_DRAIN_TIMEOUT_MS);
	do {
		if (!READ_ONCE(set->active_transfers))
			return 0;
		usleep_range(500, 1000);
	} while (time_before(jiffies, deadline));
	return READ_ONCE(set->active_transfers) ? -ETIMEDOUT : 0;
}

bool network10_v10_arena_refs_clear(struct network10_v10_arena_set *set)
{
	u32 i;
	bool clear = true;
	mutex_lock(&set->lock);
	for (i = 0; i < NETWORK10_V10_MAX_OBJECTS; ++i) {
		if (set->object[i].job_refs || set->object[i].transfer_refs ||
		    set->object[i].map_refs) {
			clear = false;
			break;
		}
	}
	mutex_unlock(&set->lock);
	return clear;
}

void network10_v10_arena_unpin_job(struct network10_v10_arena_set *set, u32 params,
				   u32 activation_a, u32 activation_b)
{
	struct network10_v10_object *p, *a, *b;
	mutex_lock(&set->lock);
	if (!decode_handle(set, params, &p) && p->job_refs) --p->job_refs;
	if (!decode_handle(set, activation_a, &a) && a->job_refs) --a->job_refs;
	if (!decode_handle(set, activation_b, &b) && b->job_refs) --b->job_refs;
	mutex_unlock(&set->lock);
}

static void transfer_chunk(void __iomem *mapping, u64 offset, void *bounce,
			   size_t bytes, bool upload)
{
	size_t word;
	void __iomem *window = mapping + offset;

	if (upload) {
		for (word = 0; word < bytes / sizeof(u64); ++word)
			writeq(((u64 *)bounce)[word], window + word * sizeof(u64));
	} else {
		for (word = 0; word < bytes / sizeof(u64); ++word)
			((u64 *)bounce)[word] = readq(window + word * sizeof(u64));
	}
}

static int arena_transfer(struct network10_v10_arena_set *set, u32 handle,
			  u64 offset, u64 bytes, void __user *user, bool upload)
{
	void *bounce;
	void __iomem *mapping = NULL;
	struct network10_v10_object *object;
	resource_size_t physical, map_base;
	u64 map_offset;
	size_t map_bytes;
	u64 done = 0;
	int ret = 0;
	if (!bytes || bytes > NETWORK10_V10_MAX_TRANSFER_BYTES || !user ||
	    (offset & 15U) || (bytes & 15U)) return -EINVAL;
	bounce = kmalloc(NETWORK10_V10_COPY_CHUNK, GFP_KERNEL);
	if (!bounce) return -ENOMEM;
	mutex_lock(&set->lock);
	if (set->quiescing || set->quiesced || set->poisoned || set->removing) { ret = -ESHUTDOWN; goto out_unlock; }
	ret = decode_handle(set, handle, &object);
	if (ret) goto out_unlock;
	if (offset > object->bytes || bytes > object->bytes - offset) { ret = -ERANGE; goto out_unlock; }
	if (object->job_refs || object->transfer_refs) { ret = -EBUSY; goto out_unlock; }
	if (!upload && !span_covered(object, offset, bytes)) { ret = -ENODATA; goto out_unlock; }
	/* The arena allocator owns one physically contiguous reserved-DDR window.
	 * Resolve and pin the complete request before mapping it once. This avoids
	 * creating a new WC mapping for every 64 KiB copy chunk. It is a temporary
	 * per-ioctl mapping, not a persistent handle mapping: the DT/kernel contract
	 * does not yet prove that these bytes lack a normal WB alias. */
	ret = resolve_locked(set, handle, offset, bytes, 1, &physical);
	if (ret) goto out_unlock;
	++object->transfer_refs;
	++set->active_transfers;
	mutex_unlock(&set->lock);
	map_base = physical & PAGE_MASK;
	map_offset = physical & ~PAGE_MASK;
	if (map_offset + bytes > SIZE_MAX - (PAGE_SIZE - 1)) {
		ret = -EOVERFLOW;
		goto transfer_done;
	}
	map_bytes = PAGE_ALIGN((size_t)map_offset + (size_t)bytes);
	mapping = ioremap_wc(map_base, map_bytes);
	if (!mapping) {
		ret = -ENOMEM;
		goto transfer_done;
	}
	if (!upload)
		/* Order CPU reads after the device completion observed by the caller. */
		rmb();
	while (done < bytes) {
		size_t chunk = min_t(u64, NETWORK10_V10_COPY_CHUNK, bytes - done);
		if (upload && copy_from_user(bounce, (u8 __user *)user + done, chunk)) { ret = -EFAULT; break; }
		transfer_chunk(mapping, map_offset + done, bounce, chunk, upload);
		if (!upload && copy_to_user((u8 __user *)user + done, bounce, chunk)) { ret = -EFAULT; break; }
		done += chunk;
	}
	if (upload)
		/* Flush/order WC writes before releasing the mapping and publishing init. */
		wmb();

transfer_done:
	if (mapping)
		iounmap(mapping);
	mutex_lock(&set->lock);
	if (upload) {
		if (ret) {
			range_remove(object, offset, bytes);
			object->write_failed = false;
		} else if (range_add(object, offset, bytes)) {
			range_remove(object, offset, bytes);
			ret = -ENOSPC;
		}
	}
	--object->transfer_refs;
	--set->active_transfers;
	mutex_unlock(&set->lock);
	kfree(bounce);
	return ret;
out_unlock:
	mutex_unlock(&set->lock);
	kfree(bounce);
	return ret;
}

int network10_v10_arena_upload(struct network10_v10_arena_set *set, u32 handle,
			     u64 offset, u64 bytes, const void __user *source)
{ return arena_transfer(set, handle, offset, bytes, (void __user *)source, true); }
int network10_v10_arena_download(struct network10_v10_arena_set *set, u32 handle,
			       u64 offset, u64 bytes, void __user *destination)
{ return arena_transfer(set, handle, offset, bytes, destination, false); }

int network10_v10_arena_begin_map(struct network10_v10_arena_set *set,
				u32 handle, u64 offset, u64 bytes, u32 access,
				resource_size_t *physical)
{
	struct network10_v10_object *object;
	int ret;
	if (!set || !physical || !bytes || (offset & ~PAGE_MASK) ||
	    (bytes & ~PAGE_MASK) ||
	    (access != NETWORK10_V10_MAP_READ &&
	     access != NETWORK10_V10_MAP_WRITE))
		return -EINVAL;
	mutex_lock(&set->lock);
	if (set->quiescing || set->quiesced || set->poisoned || set->removing) {
		ret = -ESHUTDOWN;
		goto out;
	}
	ret = decode_handle(set, handle, &object);
	if (ret)
		goto out;
	if (object->job_refs || object->transfer_refs || object->map_refs) {
		ret = -EBUSY;
		goto out;
	}
	if (access == NETWORK10_V10_MAP_READ &&
	    !span_covered(object, offset, bytes)) {
		ret = -ENODATA;
		goto out;
	}
	ret = resolve_locked(set, handle, offset, bytes, PAGE_SIZE, physical);
	if (!ret) {
		/* Exposure of a writable WC alias invalidates the covered range
		 * before userspace can modify it.  Only SYNC_COMMIT_HOST_WRITE
		 * republishes the range; conversion/copy failures therefore cannot
		 * leave partially overwritten bytes marked initialized. */
		if (access == NETWORK10_V10_MAP_WRITE)
			range_remove(object, offset, bytes);
		++object->map_refs;
		object->map_access = access;
		object->map_offset = offset;
		object->map_bytes = bytes;
	}
out:
	mutex_unlock(&set->lock);
	return ret;
}

void network10_v10_arena_end_map(struct network10_v10_arena_set *set,
			       u32 handle)
{
	struct network10_v10_object *object;
	mutex_lock(&set->lock);
	if (!decode_handle(set, handle, &object) && object->map_refs) {
		--object->map_refs;
		if (!object->map_refs) {
			object->map_access = 0;
			object->map_offset = object->map_bytes = 0;
		}
	}
	mutex_unlock(&set->lock);
}

int network10_v10_arena_sync_range(struct network10_v10_arena_set *set,
				 u32 handle, u64 offset, u64 bytes, u32 operation)
{
	struct network10_v10_object *object;
	int ret;
	if (!set || !bytes || (offset & 15U) || (bytes & 15U))
		return -EINVAL;
	mutex_lock(&set->lock);
	ret = decode_handle(set, handle, &object);
	if (ret)
		goto out;
	if (offset > object->bytes || bytes > object->bytes - offset) {
		ret = -ERANGE;
		goto out;
	}
	if (operation == NETWORK10_V10_SYNC_COMMIT_HOST_WRITE) {
		if (object->map_refs != 1 || object->job_refs || object->transfer_refs) {
			ret = -EBUSY;
			goto out;
		}
		if (object->map_access != NETWORK10_V10_MAP_WRITE ||
		    offset < object->map_offset ||
		    offset + bytes > object->map_offset + object->map_bytes) {
			ret = -EACCES;
			goto out;
		}
		wmb();
		ret = range_add(object, offset, bytes);
	} else if (operation == NETWORK10_V10_SYNC_PREPARE_CPU_READ) {
		if (object->map_refs != 1 || object->job_refs || object->transfer_refs) {
			ret = -EBUSY;
			goto out;
		}
		if (object->map_access != NETWORK10_V10_MAP_READ ||
		    offset < object->map_offset ||
		    offset + bytes > object->map_offset + object->map_bytes) {
			ret = -EACCES;
			goto out;
		}
		ret = span_covered(object, offset, bytes) ? 0 : -ENODATA;
		if (!ret)
			rmb();
	} else {
		ret = -EINVAL;
	}
out:
	mutex_unlock(&set->lock);
	return ret;
}

int network10_v10_arena_pin_upload(struct network10_v10_arena_set *set,
				 u32 handle, u64 offset, u64 bytes,
				 resource_size_t *destination_physical)
{
	struct network10_v10_object *object;
	int ret;
	if (!set || !destination_physical || !bytes || (offset & 15U) ||
	    (bytes & 15U))
		return -EINVAL;
	mutex_lock(&set->lock);
	if (set->quiescing || set->quiesced || set->poisoned || set->removing) {
		ret = -ESHUTDOWN;
		goto out;
	}
	ret = decode_handle(set, handle, &object);
	if (ret)
		goto out;
	if (offset > object->bytes || bytes > object->bytes - offset) {
		ret = -ERANGE;
		goto out;
	}
	if (object->job_refs || object->transfer_refs || object->map_refs) {
		ret = -EBUSY;
		goto out;
	}
	ret = resolve_locked(set, handle, offset, bytes, 16,
			     destination_physical);
	if (ret)
		goto out;
	/* Invalidate before DMA can partially modify the destination. */
	range_remove(object, offset, bytes);
	++object->transfer_refs;
	++set->active_transfers;
out:
	mutex_unlock(&set->lock);
	return ret;
}

void network10_v10_arena_complete_upload(struct network10_v10_arena_set *set,
					 u32 handle, u64 offset, u64 bytes,
					 bool success)
{
	struct network10_v10_object *object;
	mutex_lock(&set->lock);
	if (!decode_handle(set, handle, &object)) {
		if (success) {
			if (range_add(object, offset, bytes))
				range_remove(object, offset, bytes);
		} else {
			range_remove(object, offset, bytes);
		}
		if (object->transfer_refs)
			--object->transfer_refs;
	}
	if (set->active_transfers)
		--set->active_transfers;
	mutex_unlock(&set->lock);
}

int network10_v10_arena_pin_copy(struct network10_v10_arena_set *set,
			       u32 source_handle, u64 source_offset,
			       u32 destination_handle, u64 destination_offset,
			       u64 bytes, resource_size_t *source_physical,
			       resource_size_t *destination_physical)
{
	struct network10_v10_object *source, *destination;
	u64 source_end, destination_end;
	int ret;
	if (!set || !source_physical || !destination_physical || !bytes ||
	    (source_offset & 15U) || (destination_offset & 15U) || (bytes & 15U))
		return -EINVAL;
	mutex_lock(&set->lock);
	if (set->quiescing || set->quiesced || set->poisoned || set->removing) {
		ret = -ESHUTDOWN;
		goto out;
	}
	ret = decode_handle(set, source_handle, &source);
	if (ret)
		goto out;
	ret = decode_handle(set, destination_handle, &destination);
	if (ret)
		goto out;
	if (source_offset > source->bytes || bytes > source->bytes - source_offset ||
	    destination_offset > destination->bytes ||
	    bytes > destination->bytes - destination_offset) {
		ret = -ERANGE;
		goto out;
	}
	source_end = source_offset + bytes;
	destination_end = destination_offset + bytes;
	if (source->job_refs || source->transfer_refs || source->map_refs ||
	    destination->job_refs || destination->transfer_refs ||
	    destination->map_refs) {
		ret = -EBUSY;
		goto out;
	}
	if (!span_covered(source, source_offset, bytes)) {
		ret = -ENODATA;
		goto out;
	}
	if (source == destination && source_offset < destination_end &&
	    destination_offset < source_end) {
		ret = -EINVAL;
		goto out;
	}
	ret = resolve_locked(set, source_handle, source_offset, bytes, 16,
			     source_physical);
	if (ret)
		goto out;
	ret = resolve_locked(set, destination_handle, destination_offset, bytes, 16,
			     destination_physical);
	if (ret)
		goto out;
	++source->transfer_refs;
	++destination->transfer_refs;
	set->active_transfers += 2;
out:
	mutex_unlock(&set->lock);
	return ret;
}

void network10_v10_arena_complete_copy(struct network10_v10_arena_set *set,
				     u32 source_handle,
				     u32 destination_handle,
				     u64 destination_offset, u64 bytes,
				     bool success)
{
	struct network10_v10_object *source, *destination;
	mutex_lock(&set->lock);
	if (!decode_handle(set, source_handle, &source) && source->transfer_refs)
		--source->transfer_refs;
	if (!decode_handle(set, destination_handle, &destination)) {
		if (destination->transfer_refs)
			--destination->transfer_refs;
		if (success) {
			if (range_add(destination, destination_offset, bytes))
				range_remove(destination, destination_offset, bytes);
		} else {
			range_remove(destination, destination_offset, bytes);
		}
	}
	if (set->active_transfers >= 2)
		set->active_transfers -= 2;
	mutex_unlock(&set->lock);
}

