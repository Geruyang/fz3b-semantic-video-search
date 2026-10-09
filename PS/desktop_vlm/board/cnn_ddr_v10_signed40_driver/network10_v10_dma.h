/* SPDX-License-Identifier: GPL-2.0 */
#ifndef NETWORK10_V10_DMA_H
#define NETWORK10_V10_DMA_H

#include <linux/device.h>
#include <linux/dma-mapping.h>
#include <linux/mutex.h>
#include <linux/scatterlist.h>
#include <linux/types.h>

struct dma_chan;
struct network10_v10_arena_set;
struct network10_v10_copy_request;
struct network10_v10_cached_upload;

struct network10_v10_copy_engine {
	struct device *dev;
	struct dma_chan *channel;
	struct mutex lock;
	u32 caps;
	bool quarantined;
	/* A failed synchronous terminate retains these mappings and callback
	 * storage.  Arena transfer refs remain pinned, so remove cannot release
	 * reserved DDR while the provider may still access it. */
	struct completion *quarantine_completion;
	struct device *quarantine_dma_dev;
	dma_addr_t quarantine_source;
	dma_addr_t quarantine_destination;
	u64 quarantine_bytes;
	struct sg_table *quarantine_sgt;
	struct page **quarantine_pages;
	unsigned int quarantine_page_count, quarantine_orig_nents;
	unsigned int quarantine_mapped_nents;
	bool quarantine_sg_mapped;
	struct network10_v10_arena_set *quarantine_arenas;
	u32 quarantine_handle, quarantine_source_handle;
	u64 quarantine_offset;
};

int network10_v10_copy_engine_init(struct network10_v10_copy_engine *engine,
				 struct device *dev);
int network10_v10_copy_engine_destroy(struct network10_v10_copy_engine *engine);
int network10_v10_arena_copy(struct network10_v10_copy_engine *engine,
			   struct network10_v10_arena_set *arenas,
			   struct network10_v10_copy_request *request);
int network10_v10_cached_upload(struct network10_v10_copy_engine *engine,
				struct network10_v10_arena_set *arenas,
				struct network10_v10_cached_upload *request);

#endif
