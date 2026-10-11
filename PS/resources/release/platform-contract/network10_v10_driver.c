// SPDX-License-Identifier: GPL-2.0
/* FZ3B cnn_ddr_v10 driver candidate. Physical DDR addresses never cross UAPI. */
#include <linux/cdev.h>
#include <linux/build_bug.h>
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/fs.h>
#include <linux/io.h>
#include <linux/ioctl.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/uaccess.h>

#include "network10_v10_arena.h"
#include "network10_v10_regs.h"
#include "network10_v10_submit.h"
#include "network10_v10_uapi.h"

#define DRIVER_NAME "network10_v10"
#define DEVICE_NAME "network10_v10"
#define LOW_BASE  0x0000000040000000ULL
#define LOW_BYTES 0x000000003ff00000ULL
#define HIGH_BASE 0x0000000800000000ULL
#define HIGH_BYTES 0x0000000040000000ULL
#define EXEC_TIMEOUT_MS 30000U
#define QUIESCE_TIMEOUT_MS 2000U

/* Software release identity for the ABI10.1 PW2 r-major parameter layout.
 * The guard has no parameter-hash registers; userspace compares these words
 * with the SHA-bound release manifest before any allocation or submission. */
static const u32 v10_parameter_manifest_words[8] = {
	0x83df8803U, 0xb7a8eb08U, 0x795c6c19U, 0xd8953863U,
	0x7f850df9U, 0x044c407bU, 0x90814d72U, 0x5f0079c4U,
};

struct network10_v10_dev {
	struct device *dev;
	void __iomem *hls;
	void __iomem *guard;
	resource_size_t hls_start;
	resource_size_t hls_size;
	resource_size_t guard_start;
	resource_size_t guard_size;
	bool hls_claimed;
	bool guard_claimed;
	struct network10_v10_arena_set arenas;
	struct network10_v10_identity identity;
	struct network10_v10_status status;
	/* Lock order is job_lock -> status_lock -> arena metadata lock. Paths
	 * release arena metadata before taking status_lock; polling and transfers
	 * never retain the arena lock. */
	struct mutex job_lock;
	struct mutex status_lock;
	atomic_t open_in_use;
	struct cdev cdev;
	dev_t devt;
	struct class *class;
	struct device *char_dev;
	bool running;
	bool module_pinned;
};

static inline u32 hls_read(struct network10_v10_dev *d, u32 offset)
{
	return readl(d->hls + offset);
}

static inline void hls_write(struct network10_v10_dev *d, u32 offset, u32 value)
{
	writel(value, d->hls + offset);
}

static inline u32 guard_read(struct network10_v10_dev *d, u32 offset)
{
	return readl(d->guard + offset);
}

static inline void guard_write(struct network10_v10_dev *d, u32 offset, u32 value)
{
	writel(value, d->guard + offset);
}

static u32 state_flags(struct network10_v10_dev *d)
{
	u32 flags = 0;
	if (d->arenas.poisoned)
		flags |= NETWORK10_V10_FLAG_POISONED;
	if (d->arenas.quiesced)
		flags |= NETWORK10_V10_FLAG_QUIESCED;
	if (d->arenas.removing)
		flags |= NETWORK10_V10_FLAG_REMOVING;
	if (d->running)
		flags |= NETWORK10_V10_FLAG_RUNNING;
	return flags;
}

static void snapshot_status(struct network10_v10_dev *d)
{
	mutex_lock(&d->status_lock);
	mutex_lock(&d->arenas.lock);
	d->status.flags = state_flags(d);
	mutex_unlock(&d->arenas.lock);
	d->status.guard_status = guard_read(d, V10_GUARD_STATUS);
	d->status.guard_acks = guard_read(d, V10_GUARD_ACKS);
	d->status.ar_total = guard_read(d, V10_GUARD_AR_TOTAL);
	d->status.rlast_total = guard_read(d, V10_GUARD_RLAST_TOTAL);
	d->status.aw_total = guard_read(d, V10_GUARD_AW_TOTAL);
	d->status.wlast_total = guard_read(d, V10_GUARD_WLAST_TOTAL);
	d->status.b_total = guard_read(d, V10_GUARD_B_TOTAL);
	d->status.reset_generation = guard_read(d, V10_GUARD_RESET_GENERATION);
	d->status.guard_error_flags = guard_read(d, V10_GUARD_ERROR_FLAGS);
	d->status.job_cycles_lo = guard_read(d, V10_GUARD_JOB_CYCLES_LO);
	d->status.job_cycles_hi = guard_read(d, V10_GUARD_JOB_CYCLES_HI);
	mutex_unlock(&d->status_lock);
}

static void write_address(struct network10_v10_dev *d, u32 low_offset,
			  u32 high_offset, resource_size_t address)
{
	hls_write(d, low_offset, lower_32_bits(address));
	hls_write(d, high_offset, upper_32_bits(address));
}

static bool guard_has_error(struct network10_v10_dev *d)
{
	return (guard_read(d, V10_GUARD_STATUS) & V10_GUARD_BAD_STATUS) ||
		guard_read(d, V10_GUARD_ERROR_FLAGS);
}

static bool guard_has_all_acks(struct network10_v10_dev *d)
{
	return guard_read(d, V10_GUARD_ACKS) == V10_ACK_PACKED_MASK;
}

static int reset_guarded_core(struct network10_v10_dev *d);

static int wait_guard_safe(struct network10_v10_dev *d)
{
	unsigned long deadline = jiffies + msecs_to_jiffies(QUIESCE_TIMEOUT_MS);
	u32 required = V10_GUARD_ST_SHUTDOWN_REQ |
		V10_GUARD_ST_ALL_SHUTDOWN |
		V10_GUARD_ST_ALL_RD_IDLE |
		V10_GUARD_ST_ALL_WR_IDLE |
		V10_GUARD_ST_COUNTERS_EQUAL |
		V10_GUARD_ST_SAFE_TO_RESET;

	do {
		u32 status = guard_read(d, V10_GUARD_STATUS);
		if ((status & V10_GUARD_BAD_STATUS) ||
		    guard_read(d, V10_GUARD_ERROR_FLAGS))
			return -EIO;
		if ((status & required) == required && guard_has_all_acks(d))
			return 0;
		usleep_range(500, 1000);
	} while (time_before(jiffies, deadline));
	return -ETIMEDOUT;
}

/* This terminal path never re-enables the core or clears poison. The guarded
 * core reset is allowed only after every master has drained safely. */
static int wait_guard_terminal_safe(struct network10_v10_dev *d,
				    bool require_hls_idle)
{
	unsigned long deadline = jiffies + msecs_to_jiffies(QUIESCE_TIMEOUT_MS);
	u32 required = V10_GUARD_ST_SHUTDOWN_REQ |
		V10_GUARD_ST_ALL_SHUTDOWN |
		V10_GUARD_ST_ALL_RD_IDLE |
		V10_GUARD_ST_ALL_WR_IDLE |
		V10_GUARD_ST_COUNTERS_EQUAL |
		V10_GUARD_ST_SAFE_TO_RESET;

	do {
		u32 status = guard_read(d, V10_GUARD_STATUS);
		if ((status & required) == required && guard_has_all_acks(d) &&
		    (!require_hls_idle || (status & V10_GUARD_ST_HLS_IDLE)))
			return 0;
		usleep_range(500, 1000);
	} while (time_before(jiffies, deadline));
	return -ETIMEDOUT;
}

/* Caller holds job_lock and has closed admission. This helper is terminal:
 * it tolerates latched error bits but never clears poison/shutdown/counters. */
static int terminal_finalize_guard(struct network10_v10_dev *d)
{
	int ret;
	ret = network10_v10_arena_wait_transfers(&d->arenas);
	if (ret)
		return ret;
	if (!network10_v10_arena_refs_clear(&d->arenas))
		return -EBUSY;
	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_SET_SHUTDOWN);
	ret = wait_guard_terminal_safe(d, false);
	if (ret)
		return ret;
	ret = reset_guarded_core(d);
	if (ret)
		return ret;
	ret = wait_guard_terminal_safe(d, true);
	if (ret)
		return ret;
	network10_v10_arena_mark_quiesced(&d->arenas);
	snapshot_status(d);
	if (d->module_pinned) {
		d->module_pinned = false;
		module_put(THIS_MODULE);
	}
	return 0;
}

static int reset_guarded_core(struct network10_v10_dev *d)
{
	u32 generation = guard_read(d, V10_GUARD_RESET_GENERATION);
	unsigned long deadline = jiffies + msecs_to_jiffies(QUIESCE_TIMEOUT_MS);

	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_SAFE_RESET);
	do {
		u32 status = guard_read(d, V10_GUARD_STATUS);

		if (guard_read(d, V10_GUARD_RESET_GENERATION) != generation &&
		    !(status & V10_GUARD_ST_RESET_ACTIVE) &&
		    (status & V10_GUARD_ST_RESET_FEEDBACK_N))
			return 0;
		usleep_range(500, 1000);
	} while (time_before(jiffies, deadline));
	return -ETIMEDOUT;
}

static int prepare_guard_for_jobs(struct network10_v10_dev *d)
{
	unsigned long deadline;
	u32 status;
	int ret;

	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_SET_SHUTDOWN);
	ret = wait_guard_safe(d);
	if (ret)
		return ret;
	ret = reset_guarded_core(d);
	if (ret)
		return ret;
	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_CLEAR_COUNTERS);
	if (guard_read(d, V10_GUARD_AR_TOTAL) ||
	    guard_read(d, V10_GUARD_RLAST_TOTAL) ||
	    guard_read(d, V10_GUARD_AW_TOTAL) ||
	    guard_read(d, V10_GUARD_WLAST_TOTAL) ||
	    guard_read(d, V10_GUARD_B_TOTAL))
		return -EIO;
	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_CLEAR_SHUTDOWN);
	deadline = jiffies + msecs_to_jiffies(QUIESCE_TIMEOUT_MS);
	do {
		status = guard_read(d, V10_GUARD_STATUS);
		if (guard_has_error(d))
			return -EIO;
		if (!(status & (V10_GUARD_ST_SHUTDOWN_REQ |
				V10_GUARD_ST_RESET_ACTIVE |
				V10_GUARD_ST_JOB_BUSY |
				V10_GUARD_ST_TIMER_RUNNING)) &&
		    (status & (V10_GUARD_ST_COUNTERS_EQUAL |
			       V10_GUARD_ST_HLS_IDLE |
			       V10_GUARD_ST_RESET_FEEDBACK_N)) ==
			      (V10_GUARD_ST_COUNTERS_EQUAL |
			       V10_GUARD_ST_HLS_IDLE |
			       V10_GUARD_ST_RESET_FEEDBACK_N))
			return 0;
		usleep_range(500, 1000);
	} while (time_before(jiffies, deadline));
	return -ETIMEDOUT;
}

static bool guard_counters_match(struct network10_v10_dev *d,
				 u32 ar, u32 rlast, u32 aw, u32 wlast, u32 b)
{
	return guard_read(d, V10_GUARD_AR_TOTAL) == ar &&
		guard_read(d, V10_GUARD_RLAST_TOTAL) == rlast &&
		guard_read(d, V10_GUARD_AW_TOTAL) == aw &&
		guard_read(d, V10_GUARD_WLAST_TOTAL) == wlast &&
		guard_read(d, V10_GUARD_B_TOTAL) == b;
}

static int wait_guard_operational(struct network10_v10_dev *d,
				  u32 expected_generation,
				  u32 ar, u32 rlast, u32 aw, u32 wlast, u32 b)
{
	unsigned long deadline = jiffies + msecs_to_jiffies(QUIESCE_TIMEOUT_MS);
	u32 required = V10_GUARD_ST_COUNTERS_EQUAL |
		V10_GUARD_ST_HLS_IDLE |
		V10_GUARD_ST_RESET_FEEDBACK_N;
	u32 forbidden = V10_GUARD_ST_SHUTDOWN_REQ |
		V10_GUARD_ST_RESET_ACTIVE |
		V10_GUARD_ST_JOB_BUSY |
		V10_GUARD_ST_TIMER_RUNNING;

	do {
		u32 status = guard_read(d, V10_GUARD_STATUS);

		if (guard_has_error(d))
			return -EIO;
		if (!(status & forbidden) && (status & required) == required &&
		    guard_read(d, V10_GUARD_RESET_GENERATION) == expected_generation &&
		    guard_counters_match(d, ar, rlast, aw, wlast, b))
			return 0;
		usleep_range(500, 1000);
	} while (time_before(jiffies, deadline));
	return -ETIMEDOUT;
}

/* The guarded reset clears only the HLS core's internal FSM/FIFO/AXI-adapter
 * state between different completed profiles.  The six external shutdown
 * managers and xbars remain isolated until CLEAR_SHUTDOWN.  This operational
 * mode switch preserves guard counters, completed_pairs, arenas and ranges. */
static int switch_profile_if_needed(struct network10_v10_dev *d, u32 next_profile)
{
	u32 completed_pairs;
	u32 previous_profile;
	u32 generation;
	u32 expected_generation;
	u32 ar, rlast, aw, wlast, b;
	u32 status;
	int ret;

	mutex_lock(&d->status_lock);
	completed_pairs = d->status.completed_pairs;
	previous_profile = d->status.profile;
	mutex_unlock(&d->status_lock);
	if (!completed_pairs || previous_profile == next_profile)
		return 0;
	if (guard_has_error(d))
		return -EIO;

	generation = guard_read(d, V10_GUARD_RESET_GENERATION);
	expected_generation = generation + 1U;
	ar = guard_read(d, V10_GUARD_AR_TOTAL);
	rlast = guard_read(d, V10_GUARD_RLAST_TOTAL);
	aw = guard_read(d, V10_GUARD_AW_TOTAL);
	wlast = guard_read(d, V10_GUARD_WLAST_TOTAL);
	b = guard_read(d, V10_GUARD_B_TOTAL);

	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_SET_SHUTDOWN);
	ret = wait_guard_safe(d);
	if (ret)
		return ret;
	status = guard_read(d, V10_GUARD_STATUS);
	if (!(status & V10_GUARD_ST_HLS_IDLE) ||
	    status & (V10_GUARD_ST_RESET_ACTIVE |
		      V10_GUARD_ST_JOB_BUSY | V10_GUARD_ST_TIMER_RUNNING) ||
	    !guard_counters_match(d, ar, rlast, aw, wlast, b))
		return -EIO;

	ret = reset_guarded_core(d);
	if (ret)
		return ret;
	ret = wait_guard_safe(d);
	if (ret)
		return ret;
	status = guard_read(d, V10_GUARD_STATUS);
	if (guard_has_error(d) ||
	    guard_read(d, V10_GUARD_RESET_GENERATION) != expected_generation ||
	    (status & (V10_GUARD_ST_SHUTDOWN_REQ |
		       V10_GUARD_ST_HLS_IDLE |
		       V10_GUARD_ST_RESET_FEEDBACK_N)) !=
		      (V10_GUARD_ST_SHUTDOWN_REQ |
		       V10_GUARD_ST_HLS_IDLE |
		       V10_GUARD_ST_RESET_FEEDBACK_N) ||
	    status & (V10_GUARD_ST_RESET_ACTIVE |
		      V10_GUARD_ST_JOB_BUSY | V10_GUARD_ST_TIMER_RUNNING) ||
	    !guard_counters_match(d, ar, rlast, aw, wlast, b))
		return -EIO;

	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_CLEAR_SHUTDOWN);
	return wait_guard_operational(d, expected_generation,
				      ar, rlast, aw, wlast, b);
}

static int network10_quiesce_locked(struct network10_v10_dev *d)
{
	int ret;
	bool terminal_cleanup;
	ret = network10_v10_arena_begin_quiesce(&d->arenas, false);
	if (ret == 1)
		return 0;
	if (ret < 0)
		return ret;
	terminal_cleanup = ret == 2;
	/* Quiescing is published before waiting for the active job.  New submits
	 * and transfers now fail; existing unrelated transfers can finish. */
	mutex_lock(&d->job_lock);
	mutex_lock(&d->arenas.lock);
	if (d->arenas.quiesced) {
		mutex_unlock(&d->arenas.lock);
		mutex_unlock(&d->job_lock);
		return 0;
	}
	terminal_cleanup = terminal_cleanup || d->arenas.poisoned;
	mutex_unlock(&d->arenas.lock);
	if (terminal_cleanup) {
		ret = terminal_finalize_guard(d);
		if (ret)
			goto cleanup_failure;
		mutex_unlock(&d->job_lock);
		return 0;
	}
	ret = network10_v10_arena_wait_transfers(&d->arenas);
	if (ret)
		goto cleanup_failure;
	if (!network10_v10_arena_refs_clear(&d->arenas)) {
		ret = -EBUSY;
		goto cleanup_failure;
	}
	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_SET_SHUTDOWN);
	ret = wait_guard_safe(d);
	if (ret)
		goto poison;
	ret = reset_guarded_core(d);
	if (ret)
		goto poison;
	network10_v10_arena_mark_quiesced(&d->arenas);
	snapshot_status(d);
	if (d->module_pinned) {
		d->module_pinned = false;
		module_put(THIS_MODULE);
	}
	mutex_unlock(&d->job_lock);
	return 0;

poison:
	network10_v10_arena_poison(&d->arenas);
	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_PERMANENT_POISON);
	/* Normal cleanup observed an error. Attempt only the same terminal drain
	 * used after failed jobs; poison remains latched even on success. */
	if (!terminal_finalize_guard(d)) {
		mutex_unlock(&d->job_lock);
		return 0;
	}
	snapshot_status(d);
	mutex_unlock(&d->job_lock);
	return ret;

cleanup_failure:
	/* Keep the poison latch and module pin. Retry QUIESCE only after the
	 * guard can prove terminal safety; never force-unload an active engine. */
	snapshot_status(d);
	mutex_unlock(&d->job_lock);
	return ret;
}

static int submit_job(struct network10_v10_dev *d,
		      const struct network10_v10_submit *submit)
{
	struct network10_v10_job_plan plan;
	u32 ar_before;
	u32 rlast_before;
	u32 aw_before;
	u32 wlast_before;
	u32 b_before;
	unsigned long deadline;
	bool pinned = false;
	int ret;

	ret = network10_v10_prepare_job(&d->arenas, submit, &plan);
	if (ret)
		return ret;
	pinned = true;
	ret = switch_profile_if_needed(d, submit->profile);
	if (ret)
		goto fail;
	{
		u32 status = guard_read(d, V10_GUARD_STATUS);
		u32 forbidden = V10_GUARD_ST_SHUTDOWN_REQ |
			V10_GUARD_ST_RESET_ACTIVE |
			V10_GUARD_ST_JOB_BUSY |
			V10_GUARD_ST_TIMER_RUNNING;

		if (guard_has_error(d) || (status & forbidden) ||
		    !(status & V10_GUARD_ST_HLS_IDLE) ||
		    !(status & V10_GUARD_ST_COUNTERS_EQUAL)) {
			ret = -EBUSY;
			goto abort;
		}
	}
	ar_before = guard_read(d, V10_GUARD_AR_TOTAL);
	rlast_before = guard_read(d, V10_GUARD_RLAST_TOTAL);
	aw_before = guard_read(d, V10_GUARD_AW_TOTAL);
	wlast_before = guard_read(d, V10_GUARD_WLAST_TOTAL);
	b_before = guard_read(d, V10_GUARD_B_TOTAL);

	write_address(d, V10_HLS_PARAM1_LO, V10_HLS_PARAM1_HI, plan.params_phys);
	write_address(d, V10_HLS_PARAM2_LO, V10_HLS_PARAM2_HI, plan.params_phys);
	write_address(d, V10_HLS_ACT_A_R_LO, V10_HLS_ACT_A_R_HI,
		      plan.activation_a_phys);
	write_address(d, V10_HLS_ACT_A_W_LO, V10_HLS_ACT_A_W_HI,
		      plan.activation_a_phys);
	write_address(d, V10_HLS_ACT_B_R_LO, V10_HLS_ACT_B_R_HI,
		      plan.activation_b_phys);
	write_address(d, V10_HLS_ACT_B_W_LO, V10_HLS_ACT_B_W_HI,
		      plan.activation_b_phys);
	hls_write(d, V10_HLS_PROFILE, submit->profile);
	hls_write(d, V10_HLS_BLOCK_COUNT, submit->block_count);
	hls_write(d, V10_HLS_PARAMS_WORDS, plan.params_words);
	hls_write(d, V10_HLS_SLOT_WORDS, plan.slot_words);
	hls_write(d, V10_HLS_ARENA_WORDS, plan.arena_words);
	hls_write(d, V10_HLS_FLAGS, 0);
	wmb();
	mutex_lock(&d->status_lock);
	d->running = true;
	d->status.profile = submit->profile;
	d->status.protocol_error = 0;
	mutex_unlock(&d->status_lock);
	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_START);
	deadline = jiffies + msecs_to_jiffies(EXEC_TIMEOUT_MS);
	do {
		u32 status = guard_read(d, V10_GUARD_STATUS);
		u32 ar_now;
		u32 rlast_now;
		u32 aw_now;
		u32 wlast_now;
		u32 b_now;

		if (guard_has_error(d)) {
			ret = -EIO;
			goto fail;
		}
		ar_now = guard_read(d, V10_GUARD_AR_TOTAL);
		rlast_now = guard_read(d, V10_GUARD_RLAST_TOTAL);
		aw_now = guard_read(d, V10_GUARD_AW_TOTAL);
		wlast_now = guard_read(d, V10_GUARD_WLAST_TOTAL);
		b_now = guard_read(d, V10_GUARD_B_TOTAL);
		if ((status & V10_GUARD_COMPLETE_STATUS) ==
				V10_GUARD_COMPLETE_STATUS &&
		    !(status & (V10_GUARD_ST_JOB_BUSY |
				V10_GUARD_ST_TIMER_RUNNING)) &&
		    ar_now > ar_before && rlast_now > rlast_before &&
		    aw_now > aw_before && wlast_now > wlast_before &&
		    b_now > b_before)
			goto complete;
		usleep_range(100, 300);
	} while (time_before(jiffies, deadline));
	ret = -ETIMEDOUT;
	goto fail;

complete:
	mutex_lock(&d->status_lock);
	d->status.protocol_error = guard_read(d, V10_GUARD_PROTOCOL_ERROR);
	mutex_unlock(&d->status_lock);
	if (d->status.protocol_error) {
		ret = -EPROTO;
		goto fail;
	}
	mutex_lock(&d->status_lock);
	d->running = false;
	mutex_unlock(&d->status_lock);
	ret = network10_v10_complete_job(&d->arenas, submit, &plan);
	pinned = false;
	if (ret)
		goto fail;
	mutex_lock(&d->status_lock);
	++d->status.completed_pairs;
	mutex_unlock(&d->status_lock);
	snapshot_status(d);
	return 0;

fail:
	network10_v10_arena_poison(&d->arenas);
	mutex_lock(&d->status_lock);
	d->running = false;
	mutex_unlock(&d->status_lock);
	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_SET_SHUTDOWN);
	guard_write(d, V10_GUARD_CONTROL, V10_GUARD_CTL_PERMANENT_POISON);
	if (pinned)
		network10_v10_abort_job(&d->arenas, submit);
	/* A failed computation is terminal. Reuse QUIESCE's strict guard drain;
	 * the original error remains the ioctl result even if cleanup also fails. */
	if (terminal_finalize_guard(d))
		snapshot_status(d);
	return ret;

abort:
	network10_v10_abort_job(&d->arenas, submit);
	return ret;
}

static int network10_open(struct inode *inode, struct file *file)
{
	struct network10_v10_dev *d = container_of(inode->i_cdev,
						 struct network10_v10_dev, cdev);
	bool stopped;
	int ret;

	if (atomic_cmpxchg(&d->open_in_use, 0, 1))
		return -EBUSY;
	mutex_lock(&d->arenas.lock);
	stopped = d->arenas.quiesced || d->arenas.quiescing ||
		d->arenas.removing || d->arenas.poisoned;
	mutex_unlock(&d->arenas.lock);
	if (stopped) {
		atomic_set(&d->open_in_use, 0);
		return -ESHUTDOWN;
	}
	file->private_data = d;
	ret = nonseekable_open(inode, file);
	if (ret)
		atomic_set(&d->open_in_use, 0);
	return ret;
}

static int network10_release(struct inode *inode, struct file *file)
{
	struct network10_v10_dev *d = file->private_data;
	(void)inode;
	atomic_set(&d->open_in_use, 0);
	return 0;
}

static long network10_ioctl(struct file *file, unsigned int command,
			   unsigned long argument)
{
	struct network10_v10_dev *d = file->private_data;
	void __user *user = (void __user *)argument;
	long ret = 0;

	if (command == NETWORK10_V10_IOC_GET_IDENTITY) {
		if (copy_to_user(user, &d->identity, sizeof(d->identity)))
			return -EFAULT;
		return 0;
	}
	if (command == NETWORK10_V10_IOC_GET_STATUS) {
		snapshot_status(d);
		if (copy_to_user(user, &d->status, sizeof(d->status)))
			ret = -EFAULT;
		return ret;
	}

	if (command == NETWORK10_V10_IOC_ALLOC) {
		struct network10_v10_alloc request;
		if (copy_from_user(&request, user, sizeof(request)))
			ret = -EFAULT;
		else {
			ret = network10_v10_arena_alloc(&d->arenas, request.bytes,
						     request.alignment, request.flags,
						     &request.handle,
						     &request.arena_index);
			if (!ret && copy_to_user(user, &request, sizeof(request))) {
				network10_v10_arena_free(&d->arenas, request.handle);
				ret = -EFAULT;
			}
		}
	} else if (command == NETWORK10_V10_IOC_FREE) {
		struct network10_v10_free request;
		if (copy_from_user(&request, user, sizeof(request)))
			ret = -EFAULT;
		else if (!READ_ONCE(d->arenas.quiesced))
			ret = -EPERM;
		else
			ret = network10_v10_arena_free(&d->arenas, request.handle);
	} else if (command == NETWORK10_V10_IOC_UPLOAD ||
		   command == NETWORK10_V10_IOC_DOWNLOAD) {
		struct network10_v10_transfer request;
		if (copy_from_user(&request, user, sizeof(request)))
			ret = -EFAULT;
		else if (command == NETWORK10_V10_IOC_UPLOAD)
			ret = network10_v10_arena_upload(&d->arenas, request.handle,
						      request.offset, request.bytes,
						      (const void __user *)(unsigned long)request.user_ptr);
		else
			ret = network10_v10_arena_download(&d->arenas, request.handle,
							request.offset, request.bytes,
							(void __user *)(unsigned long)request.user_ptr);
	} else if (command == NETWORK10_V10_IOC_SUBMIT) {
		struct network10_v10_submit request;
		if (copy_from_user(&request, user, sizeof(request)))
			ret = -EFAULT;
		else {
			mutex_lock(&d->job_lock);
			ret = submit_job(d, &request);
			mutex_unlock(&d->job_lock);
		}
	} else if (command == NETWORK10_V10_IOC_QUIESCE) {
		ret = network10_quiesce_locked(d);
	} else {
		ret = -ENOTTY;
	}
	return ret;
}

static const struct file_operations network10_fops = {
	.owner = THIS_MODULE,
	.open = network10_open,
	.release = network10_release,
	.unlocked_ioctl = network10_ioctl,
	.llseek = no_llseek,
};

static bool resource_name_matches(const struct resource *resource,
				  const char *expected)
{
	const char *actual;

	if (!resource || !resource->name || !expected)
		return false;
	actual = resource->name;
	while (*actual && *expected && *actual == *expected) {
		++actual;
		++expected;
	}
	return !*actual && !*expected;
}

static int map_resource(struct network10_v10_dev *d, struct resource *resource,
			bool guard)
{
	resource_size_t size = resource_size(resource);
	void __iomem *mapping;

	if (!request_mem_region(resource->start, size, DRIVER_NAME))
		return -EBUSY;
	mapping = ioremap(resource->start, size);
	if (!mapping) {
		release_mem_region(resource->start, size);
		return -ENOMEM;
	}
	if (guard) {
		d->guard = mapping;
		d->guard_start = resource->start;
		d->guard_size = size;
		d->guard_claimed = true;
	} else {
		d->hls = mapping;
		d->hls_start = resource->start;
		d->hls_size = size;
		d->hls_claimed = true;
	}
	return 0;
}

static void unmap_resources(struct network10_v10_dev *d)
{
	if (d->guard)
		iounmap(d->guard);
	if (d->hls)
		iounmap(d->hls);
	if (d->guard_claimed)
		release_mem_region(d->guard_start, d->guard_size);
	if (d->hls_claimed)
		release_mem_region(d->hls_start, d->hls_size);
}

static int read_window(struct device_node *node, const char *name,
		       u64 expected_base, u64 expected_bytes, bool required)
{
	u32 cells[4];
	u64 base;
	u64 bytes;

	if (of_property_read_u32_array(node, name, cells, ARRAY_SIZE(cells)))
		return required ? -EINVAL : -ENOENT;
	base = ((u64)cells[0] << 32) | cells[1];
	bytes = ((u64)cells[2] << 32) | cells[3];
	return base == expected_base && bytes == expected_bytes ? 0 : -ERANGE;
}

static int network10_probe(struct platform_device *pdev)
{
	struct network10_v10_dev *d;
	struct resource *resource;
	static const u32 max_blocks[NETWORK10_V10_PROFILE_COUNT] = {
		NETWORK10_V10_PROFILE0_MAX_BLOCKS, NETWORK10_V10_PROFILE1_MAX_BLOCKS,
		NETWORK10_V10_PROFILE2_MAX_BLOCKS,
	};
	static const u32 channels[NETWORK10_V10_PROFILE_COUNT] = {
		NETWORK10_V10_PROFILE0_CHANNELS, NETWORK10_V10_PROFILE1_CHANNELS,
		NETWORK10_V10_PROFILE2_CHANNELS,
	};
	static const u32 widths[NETWORK10_V10_PROFILE_COUNT] = {
		NETWORK10_V10_PROFILE0_WIDTH, NETWORK10_V10_PROFILE1_WIDTH,
		NETWORK10_V10_PROFILE2_WIDTH,
	};
	static const u32 strides[NETWORK10_V10_PROFILE_COUNT] = {
		NETWORK10_V10_PROFILE0_BLOCK_STRIDE_WORDS,
		NETWORK10_V10_PROFILE1_BLOCK_STRIDE_WORDS,
		NETWORK10_V10_PROFILE2_BLOCK_STRIDE_WORDS,
	};
	u32 value;
	u32 i;
	bool high_enabled;
	int ret;

	BUILD_BUG_ON(sizeof(struct network10_v10_submit) != 32);
	BUILD_BUG_ON(offsetof(struct network10_v10_submit,
			      activation_a_base_offset_bytes) != 20);
	BUILD_BUG_ON(offsetof(struct network10_v10_submit,
			      activation_b_base_offset_bytes) != 24);
	BUILD_BUG_ON(offsetof(struct network10_v10_submit, reserved) != 28);
	BUILD_BUG_ON(_IOC_SIZE(NETWORK10_V10_IOC_SUBMIT) != 32);

	if (sizeof(struct network10_v10_identity) != NETWORK10_V10_IDENTITY_BYTES ||
	    sizeof(struct network10_v10_alloc) != 32 ||
	    sizeof(struct network10_v10_transfer) != 32 ||
	    sizeof(struct network10_v10_status) != 60)
		return -EINVAL;

	if (!of_device_is_compatible(pdev->dev.of_node, "fz3b,cnn-ddr-v10"))
		return -ENODEV;
	d = kzalloc(sizeof(*d), GFP_KERNEL);
	if (!d)
		return -ENOMEM;
	d->dev = &pdev->dev;
	mutex_init(&d->job_lock);
	mutex_init(&d->status_lock);
	atomic_set(&d->open_in_use, 0);
	platform_set_drvdata(pdev, d);
	if (read_window(pdev->dev.of_node, "fz3b,arena-low",
			LOW_BASE, LOW_BYTES, true)) {
		ret = -EINVAL;
		goto err_state;
	}
	high_enabled = of_property_read_bool(pdev->dev.of_node,
					     "fz3b,high-ddr-path-required");
	ret = read_window(pdev->dev.of_node, "fz3b,arena-high",
			  HIGH_BASE, HIGH_BYTES, high_enabled);
	if ((high_enabled && ret) || (!high_enabled && ret != -ENOENT)) {
		ret = -EINVAL;
		goto err_state;
	}
	if (of_property_read_u32(pdev->dev.of_node, "fz3b,address-bits", &value) ||
	    value != 40 ||
	    of_property_read_u32(pdev->dev.of_node, "fz3b,data-bits", &value) ||
	    value != 128 ||
	    of_property_read_u32(pdev->dev.of_node, "fz3b,core-id", &value) ||
	    value != V10_CORE_ID ||
	    of_property_read_u32(pdev->dev.of_node, "fz3b,abi-version", &value) ||
	    value != V10_CORE_ABI ||
	    !of_find_property(pdev->dev.of_node, "fz3b,factory-handoff-contract", NULL)) {
		ret = -EINVAL;
		goto err_state;
	}
	resource = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!resource_name_matches(resource, "hls-control") ||
	    resource_size(resource) < V10_HLS_REQUIRED_BYTES) {
		ret = -EINVAL;
		goto err_state;
	}
	ret = map_resource(d, resource, false);
	if (ret)
		goto err_state;
	resource = platform_get_resource(pdev, IORESOURCE_MEM, 1);
	if (!resource_name_matches(resource, "guard-identity") || resource_size(resource) < 0x40) {
		ret = -EINVAL;
		goto err_mmio;
	}
	ret = map_resource(d, resource, true);
	if (ret)
		goto err_mmio;
	if (guard_read(d, V10_GUARD_ID) != V10_CORE_ID ||
	    guard_read(d, V10_GUARD_ABI) != V10_CORE_ABI ||
	    guard_read(d, V10_GUARD_CAPS) != V10_CORE_CAPS ||
	    guard_has_error(d) ||
	    !(guard_read(d, V10_GUARD_STATUS) & V10_GUARD_ST_HLS_IDLE)) {
		ret = -ENODEV;
		goto err_mmio;
	}
	ret = prepare_guard_for_jobs(d);
	if (ret)
		goto err_mmio;
	ret = network10_v10_arenas_init(&d->arenas, LOW_BASE, LOW_BYTES,
				      HIGH_BASE, HIGH_BYTES, high_enabled,
				      DRIVER_NAME);
	if (ret)
		goto err_mmio;

	d->identity.core_id = V10_CORE_ID;
	d->identity.core_abi = V10_CORE_ABI;
	d->identity.guard_caps = V10_CORE_CAPS;
	d->identity.abi_version = NETWORK10_V10_ABI_VERSION;
	d->identity.caps = NETWORK10_V10_CAP_LOW_ARENA |
		NETWORK10_V10_CAP_SIX_M_AXI |
		(high_enabled ? NETWORK10_V10_CAP_HIGH_ARENA : 0);
	d->identity.address_bits = 40;
	d->identity.data_bits = 128;
	d->identity.arena_count = high_enabled ? 2 : 1;
	d->identity.profile_count = NETWORK10_V10_PROFILE_COUNT;
	for (i = 0; i < NETWORK10_V10_PROFILE_COUNT; ++i) {
		d->identity.max_blocks[i] = max_blocks[i];
		d->identity.channels[i] = channels[i];
		d->identity.widths[i] = widths[i];
		d->identity.block_stride_words[i] = strides[i];
	}
	d->identity.arena_bytes[0] = LOW_BYTES;
	d->identity.arena_bytes[1] = high_enabled ? HIGH_BYTES : 0;
	for (i = 0; i < ARRAY_SIZE(v10_parameter_manifest_words); ++i)
		d->identity.software_parameter_manifest_words[i] =
			v10_parameter_manifest_words[i];
	snapshot_status(d);

	ret = alloc_chrdev_region(&d->devt, 0, 1, DRIVER_NAME);
	if (ret)
		goto err_arenas;
	cdev_init(&d->cdev, &network10_fops);
	d->cdev.owner = THIS_MODULE;
	ret = cdev_add(&d->cdev, d->devt, 1);
	if (ret)
		goto err_chrdev;
	d->class = class_create(THIS_MODULE, DRIVER_NAME);
	if (IS_ERR(d->class)) {
		ret = PTR_ERR(d->class);
		goto err_cdev;
	}
	d->char_dev = device_create(d->class, NULL, d->devt, NULL, DEVICE_NAME);
	if (IS_ERR(d->char_dev)) {
		ret = PTR_ERR(d->char_dev);
		goto err_class;
	}
	__module_get(THIS_MODULE);
	d->module_pinned = true;
	dev_info(d->dev, "cnn_ddr_v10 ready: low=%llu high=%llu profiles=%u\n",
		 (unsigned long long)LOW_BYTES,
		 (unsigned long long)(high_enabled ? HIGH_BYTES : 0),
		 NETWORK10_V10_PROFILE_COUNT);
	return 0;

err_class:
	class_destroy(d->class);
err_cdev:
	cdev_del(&d->cdev);
err_chrdev:
	unregister_chrdev_region(d->devt, 1);
err_arenas:
	network10_v10_arenas_destroy(&d->arenas, DRIVER_NAME);
err_mmio:
	unmap_resources(d);
err_state:
	platform_set_drvdata(pdev, NULL);
	kfree(d);
	return ret;
}

static int network10_remove(struct platform_device *pdev)
{
	struct network10_v10_dev *d = platform_get_drvdata(pdev);
	int ret;

	if (!d)
		return 0;
	ret = network10_v10_arena_begin_quiesce(&d->arenas, true);
	if (ret)
		return ret;
	mutex_lock(&d->job_lock);
	ret = network10_v10_arena_wait_transfers(&d->arenas);
	if (ret || d->running || atomic_read(&d->open_in_use) ||
	    !network10_v10_arena_refs_clear(&d->arenas)) {
		mutex_unlock(&d->job_lock);
		return ret ? ret : -EBUSY;
	}
	mutex_unlock(&d->job_lock);
	device_destroy(d->class, d->devt);
	class_destroy(d->class);
	cdev_del(&d->cdev);
	unregister_chrdev_region(d->devt, 1);
	network10_v10_arenas_destroy(&d->arenas, DRIVER_NAME);
	unmap_resources(d);
	platform_set_drvdata(pdev, NULL);
	kfree(d);
	return 0;
}

static const struct of_device_id network10_of_match[] = {
	{ .compatible = "fz3b,cnn-ddr-v10" },
	{ }
};
MODULE_DEVICE_TABLE(of, network10_of_match);

static struct platform_driver network10_driver = {
	.probe = network10_probe,
	.remove = network10_remove,
	.driver = {
		.name = DRIVER_NAME,
		.of_match_table = network10_of_match,
		/* Deployment uses QUIESCE -> close -> rmmod -> remove overlay. */
		.suppress_bind_attrs = true,
	},
};
module_platform_driver(network10_driver);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("OpenAI");
MODULE_DESCRIPTION("FZ3B cnn_ddr_v10 opaque-handle reserved DDR driver candidate");

