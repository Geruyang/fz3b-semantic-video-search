// SPDX-License-Identifier: GPL-2.0
#include <linux/errno.h>
#include <linux/kernel.h>

#include "network10_v10_submit.h"

static int profile_contract(u32 profile, u32 blocks, u32 *stride_words,
			    u32 *slot_words, u32 *arena_words, u32 *maximum,
				 u32 *output_words)
{
	if (profile == NETWORK10_V10_PROFILE_NETWORK2) {
		*stride_words = NETWORK10_V10_PROFILE0_BLOCK_STRIDE_WORDS;
		*slot_words = NETWORK10_V10_PROFILE0_SLOT_WORDS;
		*arena_words = NETWORK10_V10_PROFILE0_ARENA_WORDS;
		*maximum = NETWORK10_V10_PROFILE0_MAX_BLOCKS;
		*output_words = NETWORK10_V10_PROFILE0_SLOT_WORDS;
	} else if (profile == NETWORK10_V10_PROFILE_NETWORK4) {
		*stride_words = NETWORK10_V10_PROFILE1_BLOCK_STRIDE_WORDS;
		*slot_words = NETWORK10_V10_PROFILE1_SLOT_WORDS;
		*arena_words = NETWORK10_V10_PROFILE1_ARENA_WORDS;
		*maximum = NETWORK10_V10_PROFILE1_MAX_BLOCKS;
		*output_words = NETWORK10_V10_PROFILE1_SLOT_WORDS;
	} else if (profile == NETWORK10_V10_PROFILE_NETWORK0) {
		*stride_words = NETWORK10_V10_PROFILE2_BLOCK_STRIDE_WORDS;
		*slot_words = NETWORK10_V10_PROFILE2_SLOT_WORDS;
		*arena_words = NETWORK10_V10_PROFILE2_ARENA_WORDS;
		*maximum = NETWORK10_V10_PROFILE2_MAX_BLOCKS;
		*output_words = NETWORK10_V10_PROFILE2_SLOT_WORDS;
	} else if (profile == NETWORK10_V10_PROFILE_P3) {
		*stride_words = NETWORK10_V10_PROFILE3_BLOCK_STRIDE_WORDS;
		*slot_words = NETWORK10_V10_PROFILE3_SLOT_WORDS;
		*arena_words = NETWORK10_V10_PROFILE3_ARENA_WORDS;
		*maximum = NETWORK10_V10_PROFILE3_MAX_BLOCKS;
		*output_words = NETWORK10_V10_PROFILE3_FINAL_OUTPUT_WORDS;
	} else {
		return -EINVAL;
	}
	if (!blocks || blocks > *maximum ||
	    *arena_words != 2U * *slot_words + NETWORK10_V10_SCRATCH_WORDS)
		return -EINVAL;
	return 0;
}

static bool spans_overlap(resource_size_t a, u64 a_bytes,
			  resource_size_t b, u64 b_bytes)
{
	if (a <= b)
		return (u64)(b - a) < a_bytes;
	return (u64)(a - b) < b_bytes;
}

void network10_v10_abort_job(struct network10_v10_arena_set *arenas,
			     const struct network10_v10_submit *submit)
{
	if (!arenas || !submit)
		return;
	network10_v10_arena_unpin_job(arenas, submit->params_handle,
				       submit->activation_a_handle,
				       submit->activation_b_handle);
}

int network10_v10_prepare_job(struct network10_v10_arena_set *arenas,
			      const struct network10_v10_submit *submit,
			      struct network10_v10_job_plan *plan)
{
	u64 params_object_bytes, a_object_bytes, b_object_bytes;
	u32 params_arena, a_arena, b_arena, maximum;
	u32 stride_words, slot_words, arena_words, output_words;
	u64 a_base, b_base;
	int ret;

	if (!arenas || !submit || !plan || submit->reserved)
		return -EINVAL;
	ret = network10_v10_arena_pin_job(arenas, submit->params_handle,
					 submit->activation_a_handle,
					 submit->activation_b_handle);
	if (ret)
		return ret;
	ret = profile_contract(submit->profile, submit->block_count,
			       &stride_words, &slot_words, &arena_words, &maximum,
			       &output_words);
	if (ret)
		goto unpin;
	memset(plan, 0, sizeof(*plan));
	plan->params_words = stride_words * submit->block_count;
	plan->slot_words = slot_words;
	plan->arena_words = arena_words;
	plan->params_bytes = (u64)plan->params_words * 16U;
	plan->slot_bytes = (u64)slot_words * 16U;
	plan->arena_bytes = (u64)arena_words * 16U;
	/* Normal profiles retain ping-pong parity.  P3 always completes stage2
	 * into slot0 after using slot1 only as its internal DW intermediate. */
	plan->output_offset_bytes = submit->profile == NETWORK10_V10_PROFILE_P3 ? 0 :
		((submit->block_count & 1U) ? plan->slot_bytes : 0);
	plan->output_bytes = (u64)output_words * 16U;
	a_base = submit->activation_a_base_offset_bytes;
	b_base = submit->activation_b_base_offset_bytes;

	ret = network10_v10_arena_describe(arenas, submit->params_handle,
					  &params_object_bytes, &params_arena);
	if (ret) goto unpin;
	ret = network10_v10_arena_describe(arenas, submit->activation_a_handle,
					  &a_object_bytes, &a_arena);
	if (ret) goto unpin;
	ret = network10_v10_arena_describe(arenas, submit->activation_b_handle,
					  &b_object_bytes, &b_arena);
	if (ret) goto unpin;
	(void)params_arena; (void)a_arena; (void)b_arena; (void)maximum;
	if (params_object_bytes != plan->params_bytes ||
	    (a_base & 15U) || a_base > a_object_bytes ||
	    plan->arena_bytes > a_object_bytes - a_base ||
	    (b_base & 15U) || b_base > b_object_bytes ||
	    plan->arena_bytes > b_object_bytes - b_base) {
		ret = -EMSGSIZE;
		goto unpin;
	}
	ret = network10_v10_arena_require_initialized(
		arenas, submit->params_handle, 0, plan->params_bytes);
	if (ret) goto unpin;
	ret = network10_v10_arena_require_initialized(
		arenas, submit->activation_a_handle, a_base, plan->slot_bytes);
	if (ret) goto unpin;
	ret = network10_v10_arena_require_initialized(
		arenas, submit->activation_b_handle, b_base, plan->slot_bytes);
	if (ret) goto unpin;
	ret = network10_v10_arena_resolve(arenas, submit->params_handle, 0,
					 plan->params_bytes, 16, &plan->params_phys);
	if (ret) goto unpin;
	ret = network10_v10_arena_resolve(arenas, submit->activation_a_handle,
					 a_base, plan->arena_bytes, 16,
					 &plan->activation_a_phys);
	if (ret) goto unpin;
	ret = network10_v10_arena_resolve(arenas, submit->activation_b_handle,
					 b_base, plan->arena_bytes, 16,
					 &plan->activation_b_phys);
	if (ret) goto unpin;
	if (spans_overlap(plan->params_phys, plan->params_bytes,
			  plan->activation_a_phys, plan->arena_bytes) ||
	    spans_overlap(plan->params_phys, plan->params_bytes,
			  plan->activation_b_phys, plan->arena_bytes) ||
	    spans_overlap(plan->activation_a_phys, plan->arena_bytes,
			  plan->activation_b_phys, plan->arena_bytes)) {
		ret = -EINVAL;
		goto unpin;
	}
	return 0;

unpin:
	network10_v10_abort_job(arenas, submit);
	return ret;
}

int network10_v10_complete_job(struct network10_v10_arena_set *arenas,
			       const struct network10_v10_submit *submit,
			       const struct network10_v10_job_plan *plan)
{
	int ret_a, ret_b;
	if (!arenas || !submit || !plan)
		return -EINVAL;
	ret_a = network10_v10_arena_mark_initialized(
		arenas, submit->activation_a_handle,
		(u64)submit->activation_a_base_offset_bytes + plan->output_offset_bytes,
		plan->output_bytes);
	ret_b = network10_v10_arena_mark_initialized(
		arenas, submit->activation_b_handle,
		(u64)submit->activation_b_base_offset_bytes + plan->output_offset_bytes,
		plan->output_bytes);
	network10_v10_abort_job(arenas, submit);
	return ret_a ? ret_a : ret_b;
}
