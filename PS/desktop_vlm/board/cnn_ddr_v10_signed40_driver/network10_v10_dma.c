// SPDX-License-Identifier: GPL-2.0
#include <linux/completion.h>
#include <linux/dmaengine.h>
#include <linux/dma-mapping.h>
#include <linux/err.h>
#include <linux/io.h>
#include <linux/jiffies.h>
#include <linux/mm.h>
#include <linux/ktime.h>
#include <linux/of.h>
#include <linux/scatterlist.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/uaccess.h>

#include "network10_v10_arena.h"
#include "network10_v10_dma.h"
#include "network10_v10_uapi.h"

#define NETWORK10_V10_COPY_MAX_BYTES (32U * 1024U * 1024U)
#define NETWORK10_V10_COPY_MAX_TIMEOUT_MS 30000U
#define NETWORK10_V10_REQUIRED_DMA_BITS 36U

/* The factory DT registers sixteen ZynqMP PS DMA memcpy channels but does not
 * publish them through #dma-cells/of_dma_controller_register.  Keep global
 * allocation opt-in: direct_wc remains the default and an unrelated memcpy
 * provider can never satisfy the filter. */
static bool allow_global_zynqmp_memcpy;
module_param_named(allow_global_zynqmp_memcpy,
		   allow_global_zynqmp_memcpy, bool, 0400);
MODULE_PARM_DESC(allow_global_zynqmp_memcpy,
	"opt in to an idle xlnx,zynqmp-dma-1.0 global DMA_MEMCPY channel");

#if IS_ENABLED(CONFIG_DMA_ENGINE)
static int dmaengine_cached_upload(struct network10_v10_copy_engine *engine,
				   struct network10_v10_arena_set *arenas,
				   struct network10_v10_cached_upload *request,
				   resource_size_t destination);
#endif

static void network10_v10_dma_complete(void *argument)
{
	complete(argument);
}

static bool network10_v10_dma_device_usable(struct dma_device *dma_device)
{
	struct device *dev;
	u64 mask;

	if (!dma_device || !dma_device->dev ||
	    !dma_device->device_prep_dma_memcpy ||
	    !dma_device->device_terminate_all ||
	    !dma_device->device_synchronize)
		return false;
	dev = dma_device->dev;
	if (!dev->of_node ||
	    !of_device_is_compatible(dev->of_node, "xlnx,zynqmp-dma-1.0"))
		return false;
	mask = dma_get_mask(dev);
	return mask >= DMA_BIT_MASK(NETWORK10_V10_REQUIRED_DMA_BITS);
}

static bool network10_v10_zynqmp_memcpy_filter(struct dma_chan *channel,
						void *parameter)
{
	(void)parameter;
	return channel &&
		dma_has_cap(DMA_MEMCPY, channel->device->cap_mask) &&
		network10_v10_dma_device_usable(channel->device);
}

static bool network10_v10_dma_range_supported(struct device *dev,
					       dma_addr_t address, u64 bytes)
{
	u64 mask;

	if (!dev || !bytes)
		return false;
	mask = dma_get_mask(dev);
	return (u64)address <= mask && bytes - 1 <= mask - (u64)address;
}

int network10_v10_copy_engine_init(struct network10_v10_copy_engine *engine,
				 struct device *dev)
{
	if (!engine || !dev)
		return -EINVAL;
	memset(engine, 0, sizeof(*engine));
	engine->dev = dev;
	mutex_init(&engine->lock);
	engine->caps = NETWORK10_V10_TRANSFER_CAP_WC_MMAP |
		NETWORK10_V10_TRANSFER_CAP_CPU_WC_COPY;
#if IS_ENABLED(CONFIG_DMA_ENGINE)
	engine->channel = dma_request_chan(dev, "memcpy");
	if (IS_ERR(engine->channel)) {
		int ret = PTR_ERR(engine->channel);
		engine->channel = NULL;
		/* An explicitly described provider that is not ready must defer.  A
		 * board with no named channel remains usable through WC fallback. */
		if (ret == -EPROBE_DEFER)
			return ret;
		if (allow_global_zynqmp_memcpy) {
			dma_cap_mask_t mask;

			dma_cap_zero(mask);
			dma_cap_set(DMA_MEMCPY, mask);
			engine->channel = dma_request_channel(
				mask, network10_v10_zynqmp_memcpy_filter, NULL);
		}
	} else if (!network10_v10_dma_device_usable(engine->channel->device)) {
		/* A timeout cannot safely release dma_map_resource mappings,
		 * callback storage, or arena pins unless the provider supports a
		 * synchronous terminate.  The candidate also requires the proven PS
		 * provider and a 36-bit DMA mask for the high reserved arena. */
		dma_release_channel(engine->channel);
		engine->channel = NULL;
	}
	if (engine->channel) {
		engine->caps |= NETWORK10_V10_TRANSFER_CAP_DMAENGINE_COPY;
		engine->caps |= NETWORK10_V10_TRANSFER_CAP_CACHED_DMA_UPLOAD;
	}
#endif
	return 0;
}

int network10_v10_copy_engine_destroy(struct network10_v10_copy_engine *engine)
{
	int ret = 0;

	if (!engine)
		return 0;
	mutex_lock(&engine->lock);
#if IS_ENABLED(CONFIG_DMA_ENGINE)
	if (engine->channel) {
		ret = dmaengine_terminate_sync(engine->channel);
		if (ret)
			goto out;
		dmaengine_synchronize(engine->channel);
		if (engine->quarantine_completion) {
			if (engine->quarantine_sg_mapped) {
				dma_unmap_resource(engine->quarantine_dma_dev,
					engine->quarantine_destination,
					engine->quarantine_bytes, DMA_FROM_DEVICE, 0);
				dma_unmap_sg(engine->quarantine_dma_dev,
					engine->quarantine_sgt->sgl,
					engine->quarantine_orig_nents,
					DMA_TO_DEVICE);
				sg_free_table(engine->quarantine_sgt);
				kfree(engine->quarantine_sgt);
				while (engine->quarantine_page_count)
					put_page(engine->quarantine_pages[
						--engine->quarantine_page_count]);
				kfree(engine->quarantine_pages);
				if (engine->quarantine_arenas)
					network10_v10_arena_complete_upload(
						engine->quarantine_arenas,
						engine->quarantine_handle,
						engine->quarantine_offset,
						engine->quarantine_bytes, false);
			} else {
				dma_unmap_resource(engine->quarantine_dma_dev,
					engine->quarantine_destination,
					engine->quarantine_bytes, DMA_FROM_DEVICE, 0);
				dma_unmap_resource(engine->quarantine_dma_dev,
					engine->quarantine_source,
					engine->quarantine_bytes, DMA_TO_DEVICE, 0);
				if (engine->quarantine_arenas)
					network10_v10_arena_complete_copy(
						engine->quarantine_arenas,
						engine->quarantine_source_handle,
						engine->quarantine_handle,
						engine->quarantine_offset,
						engine->quarantine_bytes, false);
			}
			kfree(engine->quarantine_completion);
			engine->quarantine_completion = NULL;
			engine->quarantine_dma_dev = NULL;
			engine->quarantine_sgt = NULL;
			engine->quarantine_pages = NULL;
			engine->quarantine_page_count = 0;
			engine->quarantine_orig_nents = 0;
			engine->quarantine_mapped_nents = 0;
			engine->quarantine_sg_mapped = false;
			engine->quarantine_arenas = NULL;
			engine->quarantine_handle = 0;
			engine->quarantine_source_handle = 0;
			engine->quarantine_offset = 0;
			engine->quarantine_bytes = 0;
			engine->quarantine_source = 0;
			engine->quarantine_destination = 0;
			engine->quarantined = false;
		}
		dma_release_channel(engine->channel);
	}
#endif
	engine->channel = NULL;
	engine->caps &= ~(NETWORK10_V10_TRANSFER_CAP_DMAENGINE_COPY |
			  NETWORK10_V10_TRANSFER_CAP_CACHED_DMA_UPLOAD);
out:
	mutex_unlock(&engine->lock);
	return ret;
}

int network10_v10_cached_upload(struct network10_v10_copy_engine *engine,
				struct network10_v10_arena_set *arenas,
				struct network10_v10_cached_upload *request)
{
	resource_size_t destination;
	unsigned long user_start;
	bool safe_to_release = true, arena_pinned = false;
	int ret;

	if (!engine || !arenas || !request || !request->bytes ||
	    request->bytes > NETWORK10_V10_MAX_TRANSFER_BYTES ||
	    request->destination_offset & 15U || request->bytes & 15U ||
	    !request->user_ptr || request->user_ptr & 15U ||
	    !request->timeout_ms ||
	    request->timeout_ms > NETWORK10_V10_COPY_MAX_TIMEOUT_MS ||
	    request->flags || request->backend || request->segment_count ||
	    request->reserved0 || request->dma_elapsed_ns || request->reserved1)
		return -EINVAL;
	if (request->user_ptr > ULONG_MAX || request->bytes > ULONG_MAX)
		return -EOVERFLOW;
	user_start = (unsigned long)request->user_ptr;
	if ((unsigned long)request->bytes - 1 > ULONG_MAX - user_start)
		return -EOVERFLOW;
	if (!access_ok(VERIFY_READ, (void __user *)user_start,
		       (unsigned long)request->bytes))
		return -EFAULT;
	mutex_lock(&engine->lock);
	if (engine->quarantined) {
		ret = -EIO;
		goto unlock;
	}
	if (!engine->channel ||
	    !(engine->caps & NETWORK10_V10_TRANSFER_CAP_CACHED_DMA_UPLOAD)) {
		ret = -EOPNOTSUPP;
		goto unlock;
	}
	ret = network10_v10_arena_pin_upload(arenas, request->destination_handle,
						request->destination_offset,
						request->bytes, &destination);
	if (ret)
		goto unlock;
	arena_pinned = true;
#if IS_ENABLED(CONFIG_DMA_ENGINE)
	ret = dmaengine_cached_upload(engine, arenas, request, destination);
	if (!ret)
		request->backend = NETWORK10_V10_UPLOAD_BACKEND_DMA_CACHED;
	else if (engine->quarantined)
		safe_to_release = false;
#else
	ret = -EOPNOTSUPP;
#endif
unlock:
	mutex_unlock(&engine->lock);
	if (arena_pinned && safe_to_release)
		network10_v10_arena_complete_upload(arenas, request->destination_handle,
						    request->destination_offset,
						    request->bytes, !ret);
	return ret;
}

static int cpu_wc_copy(resource_size_t source, resource_size_t destination,
		       u64 bytes)
{
	void __iomem *source_map, *destination_map;
	u64 offset;

	source_map = ioremap_wc(source, bytes);
	if (!source_map)
		return -ENOMEM;
	destination_map = ioremap_wc(destination, bytes);
	if (!destination_map) {
		iounmap(source_map);
		return -ENOMEM;
	}
	rmb();
	for (offset = 0; offset < bytes; offset += sizeof(u64))
		writeq(readq(source_map + offset), destination_map + offset);
	wmb();
	iounmap(destination_map);
	iounmap(source_map);
	return 0;
}

#if IS_ENABLED(CONFIG_DMA_ENGINE)
static int dmaengine_copy(struct network10_v10_copy_engine *engine,
			  resource_size_t source, resource_size_t destination,
			  u64 bytes, u32 timeout_ms, bool *submitted,
			  bool *safe_to_release)
{
	struct device *dma_dev = engine->channel->device->dev;
	struct dma_async_tx_descriptor *descriptor;
	struct completion *completion;
	dma_cookie_t cookie;
	dma_addr_t source_dma, destination_dma;
	int ret = 0;

	*submitted = false;
	*safe_to_release = true;
	completion = kzalloc(sizeof(*completion), GFP_KERNEL);
	if (!completion)
		return -ENOMEM;
	source_dma = dma_map_resource(dma_dev, source, bytes, DMA_TO_DEVICE, 0);
	if (dma_mapping_error(dma_dev, source_dma)) {
		ret = -EOPNOTSUPP;
		goto free_completion;
	}
	destination_dma = dma_map_resource(
		dma_dev, destination, bytes, DMA_FROM_DEVICE, 0);
	if (dma_mapping_error(dma_dev, destination_dma)) {
		ret = -EOPNOTSUPP;
		goto unmap_source;
	}
	descriptor = dmaengine_prep_dma_memcpy(
		engine->channel, destination_dma, source_dma, bytes,
		DMA_PREP_INTERRUPT | DMA_CTRL_ACK);
	if (!descriptor) {
		ret = -EOPNOTSUPP;
		goto unmap_both;
	}
	init_completion(completion);
	descriptor->callback = network10_v10_dma_complete;
	descriptor->callback_param = completion;
	cookie = dmaengine_submit(descriptor);
	ret = dma_submit_error(cookie);
	if (ret)
		goto unmap_both;
	*submitted = true;
	dma_async_issue_pending(engine->channel);
	if (!wait_for_completion_timeout(
			completion, msecs_to_jiffies(timeout_ms)))
		ret = -ETIMEDOUT;
	else if (dma_async_is_tx_complete(engine->channel, cookie, NULL, NULL) !=
		 DMA_COMPLETE)
		ret = -EIO;
	if (ret) {
		int stop_ret = dmaengine_terminate_sync(engine->channel);
		if (stop_ret) {
			/* Any failed post-submit result retains provider-visible state. */
			engine->quarantined = true;
			engine->caps &= ~(NETWORK10_V10_TRANSFER_CAP_DMAENGINE_COPY |
					  NETWORK10_V10_TRANSFER_CAP_CACHED_DMA_UPLOAD);
			engine->quarantine_completion = completion;
			engine->quarantine_dma_dev = dma_dev;
			engine->quarantine_source = source_dma;
			engine->quarantine_destination = destination_dma;
			engine->quarantine_bytes = bytes;
			*safe_to_release = false;
			return stop_ret;
		}
	}
	/* Callback completion alone does not release callback-owned storage. */
	dmaengine_synchronize(engine->channel);
unmap_both:
	dma_unmap_resource(dma_dev, destination_dma, bytes, DMA_FROM_DEVICE, 0);
unmap_source:
	dma_unmap_resource(dma_dev, source_dma, bytes, DMA_TO_DEVICE, 0);
free_completion:
	kfree(completion);
	return ret;
}

static void release_user_pages(struct page **pages, unsigned int count)
{
	while (count)
		put_page(pages[--count]);
}

static int dmaengine_cached_upload(struct network10_v10_copy_engine *engine,
				   struct network10_v10_arena_set *arenas,
				   struct network10_v10_cached_upload *request,
				   resource_size_t destination)
{
	struct device *dma_dev = engine->channel->device->dev;
	struct dma_async_tx_descriptor *descriptor;
	struct completion *completion = NULL;
	struct sg_table *sgt = NULL;
	struct scatterlist *sg;
	struct page **pages = NULL;
	unsigned long user_start;
	unsigned long first_page, last_byte;
	unsigned int page_count, pinned = 0, mapped_nents, orig_nents;
	unsigned int i;
	dma_addr_t destination_dma = 0;
	dma_cookie_t cookie;
	unsigned long deadline;
	bool submitted = false, sg_mapped = false;
	int got, ret = 0;
	u8 copy_align = engine->channel->device->copy_align;
	u64 remain, dest_offset = 0;
	u64 start_ns = 0;

	if (request->user_ptr > ULONG_MAX || request->bytes > ULONG_MAX)
		return -EOVERFLOW;
	user_start = (unsigned long)request->user_ptr;
	if ((unsigned long)request->bytes - 1 > ULONG_MAX - user_start)
		return -EOVERFLOW;
	last_byte = user_start + (unsigned long)request->bytes - 1;
	if (!access_ok(VERIFY_READ, (void __user *)user_start,
		       (unsigned long)request->bytes))
		return -EFAULT;
	deadline = jiffies + msecs_to_jiffies(request->timeout_ms);
	first_page = user_start & PAGE_MASK;
	page_count = (unsigned int)(((last_byte & PAGE_MASK) - first_page) /
				    PAGE_SIZE) + 1;
	if (!page_count || page_count > (NETWORK10_V10_MAX_TRANSFER_BYTES /
					 PAGE_SIZE) + 1)
		return -E2BIG;
	pages = kcalloc(page_count, sizeof(*pages), GFP_KERNEL);
	if (!pages)
		return -ENOMEM;
	/* Linux 4.14 GUP API: write=0 pins the source read-only. */
	got = get_user_pages_fast(first_page, page_count, 0, pages);
	if (got < 0) {
		ret = got;
		goto out;
	}
	pinned = got;
	if (got != page_count) {
		ret = -EFAULT;
		goto out;
	}
	sgt = kzalloc(sizeof(*sgt), GFP_KERNEL);
	if (!sgt) {
		ret = -ENOMEM;
		goto out;
	}
	ret = sg_alloc_table_from_pages(sgt, pages, page_count,
					 user_start & ~PAGE_MASK,
					 request->bytes, GFP_KERNEL);
	if (ret) {
		kfree(sgt);
		sgt = NULL;
		goto out;
	}
	orig_nents = sgt->nents;
	mapped_nents = dma_map_sg(dma_dev, sgt->sgl, orig_nents,
				  DMA_TO_DEVICE);
	if (!mapped_nents) {
		ret = -EIO;
		goto out_sg;
	}
	sg_mapped = true;
	destination_dma = dma_map_resource(dma_dev, destination,
					   request->bytes, DMA_FROM_DEVICE, 0);
	if (dma_mapping_error(dma_dev, destination_dma)) {
		ret = -EIO;
		goto out_mapped;
	}
	if (!network10_v10_dma_range_supported(dma_dev, destination_dma,
					      request->bytes)) {
		ret = -ERANGE;
		goto out_destination;
	}
	if (copy_align >= sizeof(unsigned long) * 8) {
		ret = -EOPNOTSUPP;
		goto out_destination;
	}
	{
		unsigned long alignment = copy_align ? 1UL << copy_align : 1UL;
		for_each_sg(sgt->sgl, sg, mapped_nents, i) {
			u64 length = sg_dma_len(sg);
			if (!length || dest_offset > request->bytes ||
			    length > request->bytes - dest_offset ||
			    !network10_v10_dma_range_supported(
				    dma_dev, sg_dma_address(sg), length) ||
			    ((sg_dma_address(sg) | (destination_dma + dest_offset) |
			      length) & (alignment - 1))) {
				ret = -EINVAL;
				goto out_destination;
			}
			dest_offset += length;
		}
		if (dest_offset != request->bytes) {
			ret = -EIO;
			goto out_destination;
		}
	}
	completion = kzalloc(sizeof(*completion), GFP_KERNEL);
	if (!completion) {
		ret = -ENOMEM;
		goto out_destination;
	}
	init_completion(completion);
	dest_offset = 0;
	for_each_sg(sgt->sgl, sg, mapped_nents, i) {
		unsigned long left;
		u64 length = sg_dma_len(sg);
		if (!length || dest_offset > request->bytes ||
		    length > request->bytes - dest_offset) {
			ret = -EIO;
			break;
		}
		if (time_after_eq(jiffies, deadline)) {
			ret = -ETIMEDOUT;
			break;
		}

		descriptor = dmaengine_prep_dma_memcpy(
			engine->channel, destination_dma + dest_offset,
			sg_dma_address(sg), length,
			DMA_PREP_INTERRUPT | DMA_CTRL_ACK);
		if (!descriptor) {
			ret = -EOPNOTSUPP;
			break;
		}
		reinit_completion(completion);
		descriptor->callback = network10_v10_dma_complete;
		descriptor->callback_param = completion;
		cookie = dmaengine_submit(descriptor);
		ret = dma_submit_error(cookie);
		if (ret)
			break;
		submitted = true;
		if (!start_ns)
			start_ns = ktime_get_ns();
		dma_async_issue_pending(engine->channel);
		left = time_after(deadline, jiffies) ? deadline - jiffies : 0;
		if (!left || !wait_for_completion_timeout(completion, left)) {
			ret = -ETIMEDOUT;
			break;
		}
		if (dma_async_is_tx_complete(engine->channel, cookie, NULL, NULL) !=
		    DMA_COMPLETE) {
			ret = -EIO;
			break;
		}
		remain = request->bytes - (dest_offset + length);
		dest_offset += length;
		++request->segment_count;
		if (!remain)
			break;
	}
	if (!ret && dest_offset != request->bytes)
		ret = -EIO;
	if (submitted && ret) {
		int stop_ret = dmaengine_terminate_sync(engine->channel);
		if (stop_ret) {
			engine->quarantined = true;
			engine->caps &= ~(NETWORK10_V10_TRANSFER_CAP_DMAENGINE_COPY |
					  NETWORK10_V10_TRANSFER_CAP_CACHED_DMA_UPLOAD);
			engine->quarantine_completion = completion;
			engine->quarantine_dma_dev = dma_dev;
			engine->quarantine_destination = destination_dma;
			engine->quarantine_bytes = request->bytes;
			engine->quarantine_sgt = sgt;
			engine->quarantine_pages = pages;
			engine->quarantine_page_count = pinned;
			engine->quarantine_orig_nents = orig_nents;
			engine->quarantine_mapped_nents = mapped_nents;
			engine->quarantine_sg_mapped = true;
			engine->quarantine_arenas = arenas;
			engine->quarantine_handle = request->destination_handle;
			engine->quarantine_offset = request->destination_offset;
			return stop_ret;
		}
	}
	if (submitted)
		dmaengine_synchronize(engine->channel);
	request->dma_elapsed_ns = start_ns ? ktime_get_ns() - start_ns : 0;
	if (!ret)
		wmb();
	kfree(completion);
out_destination:
	dma_unmap_resource(dma_dev, destination_dma, request->bytes,
			   DMA_FROM_DEVICE, 0);
out_mapped:
	if (sg_mapped)
		dma_unmap_sg(dma_dev, sgt->sgl, orig_nents, DMA_TO_DEVICE);
out_sg:
	if (sgt) {
		sg_free_table(sgt);
		kfree(sgt);
	}
out:
	release_user_pages(pages, pinned);
	kfree(pages);
	return ret;
}
#endif

int network10_v10_arena_copy(struct network10_v10_copy_engine *engine,
			   struct network10_v10_arena_set *arenas,
			   struct network10_v10_copy_request *request)
{
	resource_size_t source, destination;
	bool submitted = false;
	bool success = false;
	bool safe_to_release = true;
	int ret;

	if (!engine || !arenas || !request || !request->bytes ||
	    request->bytes > NETWORK10_V10_COPY_MAX_BYTES ||
	    request->timeout_ms == 0 ||
	    request->timeout_ms > NETWORK10_V10_COPY_MAX_TIMEOUT_MS ||
	    request->reserved || request->backend ||
	    request->flags & ~(NETWORK10_V10_COPY_ALLOW_CPU_FALLBACK |
			       NETWORK10_V10_COPY_REQUIRE_DMAENGINE) ||
	    (request->flags & NETWORK10_V10_COPY_ALLOW_CPU_FALLBACK &&
	     request->flags & NETWORK10_V10_COPY_REQUIRE_DMAENGINE))
		return -EINVAL;
	ret = network10_v10_arena_pin_copy(
		arenas, request->source_handle, request->source_offset,
		request->destination_handle, request->destination_offset,
		request->bytes, &source, &destination);
	if (ret)
		return ret;
	mutex_lock(&engine->lock);
	if (engine->quarantined) {
		ret = -EIO;
		goto done;
	}
#if IS_ENABLED(CONFIG_DMA_ENGINE)
	if (engine->channel) {
		ret = dmaengine_copy(engine, source, destination, request->bytes,
				     request->timeout_ms, &submitted,
				     &safe_to_release);
		if (!ret) {
			request->backend = NETWORK10_V10_COPY_BACKEND_DMAENGINE;
			success = true;
			goto done;
		}
		/* No CPU replay after submit: timeout/error leaves destination
		 * invalid so an unknown DMA outcome cannot be published twice. */
		if (submitted) {
			if (!safe_to_release) {
				engine->quarantine_arenas = arenas;
				engine->quarantine_source_handle = request->source_handle;
				engine->quarantine_handle = request->destination_handle;
				engine->quarantine_offset = request->destination_offset;
			}
			goto done;
		}
	}
#endif
	if (request->flags & NETWORK10_V10_COPY_REQUIRE_DMAENGINE) {
		ret = -EOPNOTSUPP;
		goto done;
	}
	if (!(request->flags & NETWORK10_V10_COPY_ALLOW_CPU_FALLBACK)) {
		ret = -EOPNOTSUPP;
		goto done;
	}
	ret = cpu_wc_copy(source, destination, request->bytes);
	if (!ret) {
		request->backend = NETWORK10_V10_COPY_BACKEND_CPU_WC;
		success = true;
	}
done:
	mutex_unlock(&engine->lock);
	if (safe_to_release)
		network10_v10_arena_complete_copy(
			arenas, request->source_handle, request->destination_handle,
			request->destination_offset, request->bytes, success);
	return ret;
}
