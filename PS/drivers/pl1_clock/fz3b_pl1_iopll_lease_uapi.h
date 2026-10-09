#ifndef FZ3B_PL1_IOPLL_LEASE_UAPI_H
#define FZ3B_PL1_IOPLL_LEASE_UAPI_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define FZ3B_PL1_IOPLL_LEASE_VERSION 2U

#define FZ3B_PL1_FLAG_LEASE_HELD       (1U << 0)
#define FZ3B_PL1_FLAG_OPEN             (1U << 1)
#define FZ3B_PL1_FLAG_TRANSACTION      (1U << 2)
#define FZ3B_PL1_FLAG_QUARANTINED      (1U << 3)
#define FZ3B_PL1_FLAG_SELF_PINNED      (1U << 4)
#define FZ3B_PL1_FLAG_IOPLL_LOCKED     (1U << 5)

struct fz3b_pl1_iopll_lease_status {
	__u32 version;
	__u32 flags;
	__u32 pl0_ref_ctrl;
	__u32 pl1_ref_ctrl;
	__u32 pl2_ref_ctrl;
	__u32 pl3_ref_ctrl;
	__u32 iopll_ctrl;
	__u32 pll_status;
	__u32 rpll_ctrl;
	__u32 ddr_ctrl;
	__s32 last_error;
	__u32 begin_count;
	__u64 iopll_rate_hz;
	__u32 reserved[2];
};

#define FZ3B_PL1_IOC_MAGIC 'M'
#define FZ3B_PL1_IOC_BEGIN _IO(FZ3B_PL1_IOC_MAGIC, 1)
#define FZ3B_PL1_IOC_FINALIZE _IO(FZ3B_PL1_IOC_MAGIC, 2)
#define FZ3B_PL1_IOC_STATUS \
	_IOR(FZ3B_PL1_IOC_MAGIC, 3, struct fz3b_pl1_iopll_lease_status)

#endif
