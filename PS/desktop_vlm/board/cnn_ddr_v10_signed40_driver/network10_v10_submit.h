/* SPDX-License-Identifier: GPL-2.0 */
#ifndef NETWORK10_V10_SUBMIT_H
#define NETWORK10_V10_SUBMIT_H

#include <linux/types.h>

#include "network10_v10_arena.h"
#include "network10_v10_uapi.h"

struct network10_v10_job_plan {
	resource_size_t params_phys;
	resource_size_t activation_a_phys;
	resource_size_t activation_b_phys;
	u64 params_bytes;
	u64 slot_bytes;
	u64 arena_bytes;
	u64 output_offset_bytes;
	u64 output_bytes;
	u32 params_words;
	u32 slot_words;
	u32 arena_words;
};

int network10_v10_prepare_job(struct network10_v10_arena_set *arenas,
			      const struct network10_v10_submit *submit,
			      struct network10_v10_job_plan *plan);
int network10_v10_complete_job(struct network10_v10_arena_set *arenas,
			       const struct network10_v10_submit *submit,
			       const struct network10_v10_job_plan *plan);
void network10_v10_abort_job(struct network10_v10_arena_set *arenas,
			     const struct network10_v10_submit *submit);

#endif
