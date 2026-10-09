#include <linux/build_bug.h>
#include <linux/clk.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/io.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/uaccess.h>

#include "fz3b_pl1_iopll_lease_uapi.h"

#define FZ3B_CLK_IOPLL 0U
#define FZ3B_IOPLL_EXPECTED_HZ 1499999985UL
#define CRL_APB_BASE 0xFF5E0000ULL
#define CRL_APB_SIZE 0x1000U
#define CRL_APB_IOPLL_CTRL 0x20U
#define CRL_APB_RPLL_CTRL 0x30U
#define CRL_APB_PLL_STATUS 0x40U
#define CRL_APB_PL0_REF_CTRL 0xC0U
#define CRL_APB_PL1_REF_CTRL 0xC4U
#define CRL_APB_PL2_REF_CTRL 0xC8U
#define CRL_APB_PL3_REF_CTRL 0xCCU
#define CRF_APB_BASE 0xFD1A0000ULL
#define CRF_APB_SIZE 0x1000U
#define CRF_APB_DDR_CTRL 0x80U
#define CRL_APB_PLL_STATUS_IOPLL_LOCK (1U << 0)
#define FZ3B_PL0_BASELINE 0x01010802U
#define FZ3B_UNUSED_PL_BASELINE 0x00052000U

static DEFINE_MUTEX(lease_lock);
static struct clk *iopll;
static void __iomem *crl;
static void __iomem *crf;
static bool opened;
static bool lease_held;
static bool transaction_active;
static bool quarantined;
static bool self_pinned;
static int last_error;
static u32 begin_count;
static u32 baseline_pl[4];
static u32 baseline_iopll_ctrl;
static u32 baseline_rpll_ctrl;
static u32 baseline_pll_status;
static u32 baseline_ddr_ctrl;

static u32 raw_read(u32 offset)
{
	return readl((u8 __iomem *)crl + offset);
}

static u32 crf_read(u32 offset)
{
	return readl((u8 __iomem *)crf + offset);
}

static void read_pl_refs(u32 pl[4])
{
	pl[0] = raw_read(CRL_APB_PL0_REF_CTRL);
	pl[1] = raw_read(CRL_APB_PL1_REF_CTRL);
	pl[2] = raw_read(CRL_APB_PL2_REF_CTRL);
	pl[3] = raw_read(CRL_APB_PL3_REF_CTRL);
}

static bool canonical_entry_state(const u32 pl[4])
{
	return pl[0] == FZ3B_PL0_BASELINE &&
	       pl[1] == FZ3B_UNUSED_PL_BASELINE &&
	       pl[2] == FZ3B_UNUSED_PL_BASELINE &&
	       pl[3] == FZ3B_UNUSED_PL_BASELINE;
}

static bool hardware_release_safe(void)
{
	u32 pl[4];
	u32 ctrl = raw_read(CRL_APB_IOPLL_CTRL);
	u32 rpll = raw_read(CRL_APB_RPLL_CTRL);
	u32 status = raw_read(CRL_APB_PLL_STATUS);
	u32 ddr = crf_read(CRF_APB_DDR_CTRL);

	read_pl_refs(pl);
	return pl[0] == baseline_pl[0] && pl[1] == baseline_pl[1] &&
	       pl[2] == baseline_pl[2] && pl[3] == baseline_pl[3] &&
	       ctrl == baseline_iopll_ctrl && rpll == baseline_rpll_ctrl &&
	       status == baseline_pll_status && ddr == baseline_ddr_ctrl &&
	       (status & CRL_APB_PLL_STATUS_IOPLL_LOCK) != 0U;
}

static struct clk *provider_clk(struct device_node *np, u32 id)
{
	struct of_phandle_args args = {
		.np = np,
		.args_count = 1,
	};

	args.args[0] = id;
	return of_clk_get_from_provider(&args);
}

static int lease_open(struct inode *inode, struct file *file)
{
	int ret = 0;
	u32 status_before;

	mutex_lock(&lease_lock);
	if (opened) {
		ret = -EBUSY;
		goto out;
	}
	opened = true;
	if (lease_held) {
		if (!quarantined || !self_pinned) {
			opened = false;
			ret = -EUCLEAN;
		}
		goto out;
	}
	read_pl_refs(baseline_pl);
	if (!canonical_entry_state(baseline_pl)) {
		opened = false;
		ret = -EBUSY;
		goto out;
	}
	baseline_iopll_ctrl = raw_read(CRL_APB_IOPLL_CTRL);
	baseline_rpll_ctrl = raw_read(CRL_APB_RPLL_CTRL);
	baseline_ddr_ctrl = crf_read(CRF_APB_DDR_CTRL);
	status_before = raw_read(CRL_APB_PLL_STATUS);
	baseline_pll_status = status_before;
	if (!(status_before & CRL_APB_PLL_STATUS_IOPLL_LOCK)) {
		opened = false;
		ret = -ENOLCK;
		goto out;
	}
	ret = clk_prepare_enable(iopll);
	if (ret) {
		opened = false;
		goto out;
	}
	lease_held = true;
	if (!hardware_release_safe()) {
		opened = false;
		quarantined = true;
		if (!self_pinned) {
			__module_get(THIS_MODULE);
			self_pinned = true;
		}
		ret = -EIO;
		goto out;
	}
	last_error = 0;
out:
	if (ret)
		last_error = ret;
	mutex_unlock(&lease_lock);
	return ret;
}

static int lease_release(struct inode *inode, struct file *file)
{
	bool drop_self_pin = false;

	mutex_lock(&lease_lock);
	if (!opened) {
		mutex_unlock(&lease_lock);
		return 0;
	}
	opened = false;
	if (!lease_held) {
		mutex_unlock(&lease_lock);
		return 0;
	}
	if (transaction_active || !hardware_release_safe()) {
		quarantined = true;
		last_error = -EBUSY;
		if (!self_pinned) {
			__module_get(THIS_MODULE);
			self_pinned = true;
		}
		mutex_unlock(&lease_lock);
		return 0;
	}
	clk_disable_unprepare(iopll);
	lease_held = false;
	quarantined = false;
	last_error = 0;
	if (self_pinned) {
		self_pinned = false;
		drop_self_pin = true;
	}
	mutex_unlock(&lease_lock);
	if (drop_self_pin)
		module_put(THIS_MODULE);
	return 0;
}

static long lease_ioctl(struct file *file, unsigned int cmd,
			unsigned long arg)
{
	struct fz3b_pl1_iopll_lease_status status;
	long ret = 0;

	mutex_lock(&lease_lock);
	switch (cmd) {
	case FZ3B_PL1_IOC_BEGIN:
		if (!opened || !lease_held || transaction_active || quarantined) {
			ret = -EBUSY;
			break;
		}
		if (!hardware_release_safe()) {
			ret = -EIO;
			break;
		}
		transaction_active = true;
		begin_count++;
		break;
	case FZ3B_PL1_IOC_FINALIZE:
		if (!opened || !lease_held ||
		    (!transaction_active && !quarantined)) {
			ret = -EINVAL;
			break;
		}
		if (!hardware_release_safe()) {
			ret = -EIO;
			break;
		}
		transaction_active = false;
		quarantined = false;
		last_error = 0;
		break;
	case FZ3B_PL1_IOC_STATUS:
		memset(&status, 0, sizeof(status));
		status.version = FZ3B_PL1_IOPLL_LEASE_VERSION;
		status.flags = (lease_held ? FZ3B_PL1_FLAG_LEASE_HELD : 0U) |
			(opened ? FZ3B_PL1_FLAG_OPEN : 0U) |
			(transaction_active ? FZ3B_PL1_FLAG_TRANSACTION : 0U) |
			(quarantined ? FZ3B_PL1_FLAG_QUARANTINED : 0U) |
			(self_pinned ? FZ3B_PL1_FLAG_SELF_PINNED : 0U) |
			((raw_read(CRL_APB_PLL_STATUS) &
			  CRL_APB_PLL_STATUS_IOPLL_LOCK) ?
			 FZ3B_PL1_FLAG_IOPLL_LOCKED : 0U);
		status.pl0_ref_ctrl = raw_read(CRL_APB_PL0_REF_CTRL);
		status.pl1_ref_ctrl = raw_read(CRL_APB_PL1_REF_CTRL);
		status.pl2_ref_ctrl = raw_read(CRL_APB_PL2_REF_CTRL);
		status.pl3_ref_ctrl = raw_read(CRL_APB_PL3_REF_CTRL);
		status.iopll_ctrl = raw_read(CRL_APB_IOPLL_CTRL);
		status.pll_status = raw_read(CRL_APB_PLL_STATUS);
		status.rpll_ctrl = raw_read(CRL_APB_RPLL_CTRL);
		status.ddr_ctrl = crf_read(CRF_APB_DDR_CTRL);
		status.last_error = last_error;
		status.begin_count = begin_count;
		status.iopll_rate_hz = clk_get_rate(iopll);
		if (copy_to_user((void __user *)arg, &status, sizeof(status)))
			ret = -EFAULT;
		break;
	default:
		ret = -ENOTTY;
		break;
	}
	if (ret)
		last_error = ret;
	mutex_unlock(&lease_lock);
	return ret;
}

static const struct file_operations lease_fops = {
	.owner = THIS_MODULE,
	.open = lease_open,
	.release = lease_release,
	.unlocked_ioctl = lease_ioctl,
#ifdef CONFIG_COMPAT
	.compat_ioctl = lease_ioctl,
#endif
};

static struct miscdevice lease_misc = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = "fz3b_pl1_iopll_lease",
	.fops = &lease_fops,
	.mode = 0600,
};

static int __init lease_init(void)
{
	struct device_node *np;
	int ret;

	BUILD_BUG_ON(sizeof(struct fz3b_pl1_iopll_lease_status) != 64U);
	BUILD_BUG_ON(offsetof(struct fz3b_pl1_iopll_lease_status,
			      iopll_rate_hz) != 48U);
	BUILD_BUG_ON(_IOC_SIZE(FZ3B_PL1_IOC_STATUS) != 64U);
	crl = ioremap(CRL_APB_BASE, CRL_APB_SIZE);
	if (!crl)
		return -ENOMEM;
	crf = ioremap(CRF_APB_BASE, CRF_APB_SIZE);
	if (!crf) {
		ret = -ENOMEM;
		goto err_unmap_crl;
	}
	np = of_find_node_by_path("/clk");
	if (!np) {
		ret = -ENODEV;
		goto err_unmap_crf;
	}
	iopll = provider_clk(np, FZ3B_CLK_IOPLL);
	of_node_put(np);
	if (IS_ERR(iopll)) {
		ret = PTR_ERR(iopll);
		iopll = NULL;
		goto err_unmap_crf;
	}
	if (clk_get_rate(iopll) != FZ3B_IOPLL_EXPECTED_HZ) {
		ret = -ERANGE;
		goto err_put_clk;
	}
	ret = misc_register(&lease_misc);
	if (ret)
		goto err_put_clk;
	pr_info("fz3b_pl1_iopll_lease ready; provider=0; no clock writes\n");
	return 0;

err_put_clk:
	clk_put(iopll);
	iopll = NULL;
err_unmap_crf:
	iounmap(crf);
	crf = NULL;
err_unmap_crl:
	iounmap(crl);
	crl = NULL;
	return ret;
}

static void __exit lease_exit(void)
{
	misc_deregister(&lease_misc);
	if (iopll)
		clk_put(iopll);
	if (crl)
		iounmap(crl);
	if (crf)
		iounmap(crf);
	pr_info("fz3b_pl1_iopll_lease exit\n");
}

module_init(lease_init);
module_exit(lease_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("FZ3B PL1 IOPLL lease with four-branch restore guard");
