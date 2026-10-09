/* CPU-only clock lease for the verified FZ3B 2018.3 platform.
 * Use official PM ACPU mux/divider and NODE_APLL parameter/mode APIs.
 * Never write MMIO or change a DDR/PL branch or any shared non-APLL PLL.
 */
#include <linux/clk.h>
#include <linux/clk-provider.h>
#include <linux/delay.h>
#include <linux/kallsyms.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/io.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/uaccess.h>
#include <linux/firmware/xilinx/zynqmp/firmware.h>
#define ACPU_ID 10U
#define DPLL_ID 3U
#define GET_STATE _IOR('C',0,struct cpu_state)
#define SET_KHZ _IOW('C',1,__u32)
#define GET_PLL _IOR('C',2,struct pll_info)
#define GET_CLOCK _IOWR('C',3,struct clock_info)
#define APLL_ID 2U
struct pll_info {u32 mode,mode_error,frac,frac_error,fbdiv,divider_error,enabled,state_error,ctrl,frac_raw,reference_hz,clock_id;};
struct clock_info {u32 id;char name[16];u32 enabled,state_error,parent,parent_error,parents[9],parents_error;};
struct cpu_state {
 __u64 actual_hz, ccf_hz;
 __u32 acpu_ctrl, parent, divider;
 __s32 last_error;
 __u32 held, reserved;
};
static DEFINE_MUTEX(lock);
static struct clk *acpu,*mux,*dpll,*apll;
static const struct zynqmp_eemi_ops *pm;
static void __iomem *crf,*crl;
static bool opened,held,quarantined;
static int last_error;
static u32 apll_pm_id;
static u32 original_ctrl,baseline[11];
static u32 original_ctrl_pll;
static const u32 crf_offsets[]={0x20,0x2c,0x38,0x44,0x80};
static const u32 crl_offsets[]={0x20,0x30,0xc0,0xc4,0xc8,0xcc};
static u32 cpu_raw(void){return readl((u8 __iomem *)crf+0x60);}
static void snapshot(u32 *values){unsigned i;for(i=0;i<5;i++)values[i]=readl((u8 __iomem *)crf+crf_offsets[i]);for(i=0;i<6;i++)values[5+i]=readl((u8 __iomem *)crl+crl_offsets[i]);}
static int clock_diagnostic(struct clock_info *p);
static bool protected_unchanged(void);
#include "fz3b_cpu_four.h"
static bool protected_unchanged(void){
 u32 now[11];snapshot(now);
 return now[0]==baseline[0]&&now[1]==baseline[1]&&
        (now[3]&~0x24u)==(baseline[3]&~0x24u)&&
        !memcmp(now+4,baseline+4,7*sizeof(u32))&&
        readl((u8 __iomem *)crf+0x24)==original_cfg&&readl((u8 __iomem *)crf+0x28)==original_frac;
}
static bool unchanged(void){return protected_unchanged()&&v_matches();}
static int read_state(struct cpu_state *s){
 u32 parent,divider,raw=cpu_raw();u64 rate;
 int rc;if(!unchanged())return -EUCLEAN;
 rc=pm->clock_getparent(ACPU_ID,&parent);if(rc)return rc;
 rc=pm->clock_getdivider(ACPU_ID,&divider);if(rc)return rc;
 if(parent!=(raw&7u)||(divider&0xffffu)!=((raw>>8)&63u))return -EUCLEAN;
 if(parent==2)rate=clk_get_rate(dpll);
 else if(parent==0||parent==3){
  u32 offset=parent==0?0x20:0x38,node=parent==0?50:51;
  u32 pll=readl((u8 __iomem *)crf+offset),fraction=readl((u8 __iomem *)crf+offset+8),fb,mode,data;
  rc=pll_param_get(node,1,&fb);if(rc||fb!=((pll>>8)&127u))return rc?rc:-EUCLEAN;
  rc=pll_mode_get(node,&mode);if(rc||mode!=((fraction>>31)?2u:1u))return rc?rc:-EUCLEAN;
  rc=pll_param_get(node,2,&data);if(rc||data!=(fraction&0xffffu))return rc?rc:-EUCLEAN;
  rate=33333333ULL*((u64)fb*65536+((fraction>>31)?data:0))/65536;
  if(pll&(1u<<16))rate/=2;
 }else return -EUCLEAN;
 if(!(divider&0xffffu))return -EUCLEAN;
 memset(s,0,sizeof(*s));s->actual_hz=rate/(divider&0xffffu);s->ccf_hz=clk_get_rate(acpu);
 s->acpu_ctrl=raw;s->parent=parent;s->divider=divider&0xffffu;s->last_error=last_error;s->held=held;s->reserved=target_khz;
 if((raw&~0x3f07u)!=(original_ctrl&~0x3f07u))return -EUCLEAN;
 return 0;
}
static int restore(void){
 int rc;u32 div=(original_ctrl>>8)&63u;
 rc=cpu_safe_dpll();if(rc)return rc;
 rc=v_restore();if(rc)return rc;
 rc=pm->clock_setparent(ACPU_ID,original_ctrl&7u);if(rc)return rc;
 rc=pm->clock_setdivider(ACPU_ID,0xffff0000u|div);if(rc)return rc;
 if(cpu_raw()!=original_ctrl||!unchanged())return -EUCLEAN;
 target_khz=0;
 return 0;
}
static int cpu_open(struct inode *inode,struct file *file){
 unsigned i;int rc=0;mutex_lock(&lock);
 if(opened||quarantined){rc=-EBUSY;goto done;}
 if(cpu_raw()!=0x03000100u||readl((u8 __iomem *)crf+0x20)!=0x00014000u||readl((u8 __iomem *)crf+0x2c)!=0x00014800u||clk_get_rate(dpll)!=1199999988UL||(readl((u8 __iomem *)crf+0x44)&9u)!=9u){rc=-EUCLEAN;goto done;}
 original_ctrl=cpu_raw();snapshot(baseline);
 original_ctrl_pll=baseline[0];original_cfg=readl((u8 __iomem *)crf+0x24);original_frac=readl((u8 __iomem *)crf+0x28);
 v_raw(v_original);
 for(i=0;i<10;i++){rc=pll_param_get(51,i,&v_params[i]);if(rc)goto done;}
 rc=pll_mode_get(51,&v_mode);if(rc)goto done;
 if(v_mode!=0||v_params[0]!=1||v_params[1]!=90||v_params[2]||v_params[3]||v_params[4]||v_original[2]||(v_original[0]&9u)!=9u){rc=-EUCLEAN;goto done;}
 memcpy(v_expected,v_original,sizeof(v_expected));target_khz=0;
 /* The 2018.3 CCF has no exported prepare-count query. Call the very same
  * firmware mux API as its provider directly so no CCF parent gate migration
  * can occur. CCF/sysfs caches are diagnostic only; PM + raw are authoritative.
  */
 held=true;opened=true;
done:mutex_unlock(&lock);return rc;
}
static void pll_diagnostic(struct pll_info *p){
 u32 payload[PAYLOAD_ARG_CNT]={0};memset(p,0,sizeof(*p));
 p->mode_error=pm->ioctl(0,IOCTL_GET_PLL_FRAC_MODE,apll_pm_id,0,payload);p->mode=payload[1];
 memset(payload,0,sizeof(payload));p->frac_error=pm->ioctl(0,IOCTL_GET_PLL_FRAC_DATA,apll_pm_id,0,payload);p->frac=payload[1];
 p->divider_error=pm->clock_getdivider(apll_pm_id,&p->fbdiv);
 p->state_error=pm->clock_getstate(apll_pm_id,&p->enabled);
 p->ctrl=readl((u8 __iomem *)crf+0x20);p->frac_raw=readl((u8 __iomem *)crf+0x28);
 p->reference_hz=33333333;p->clock_id=apll_pm_id;
}
static int clock_diagnostic(struct clock_info *p){
 struct zynqmp_pm_query_data query={0};u32 payload[PAYLOAD_ARG_CNT]={0};unsigned i,j;int rc;
 query.qid=PM_QID_CLOCK_GET_NAME;query.arg1=p->id;
 /* 2018.3 GET_NAME returns the four name words without a status word.
  * firmware.c incorrectly interprets word0 as a status; official clkc.c
  * zynqmp_pm_clock_get_name also ignores that return. Validate payload;
  * graph_load separately requires successful GET_ATTRIBUTES + valid bit. */
 pm->query_data(query,payload);
 memcpy(p->name,payload,sizeof(p->name));p->name[15]=0;
 for(i=0;i<15&&p->name[i];i++)if((u8)p->name[i]<32||(u8)p->name[i]>126)return -EOPNOTSUPP;
 p->state_error=pm->clock_getstate(p->id,&p->enabled);
 p->parent_error=pm->clock_getparent(p->id,&p->parent);
 query.qid=PM_QID_CLOCK_GET_PARENTS;p->parents_error=0;
 memset(p->parents,0xff,sizeof(p->parents));
 for(i=0;i<3;i++){
  query.arg2=i*3;memset(payload,0,sizeof(payload));rc=pm->query_data(query,payload);
  if(rc){p->parents_error=rc;return 0;}
  memcpy(p->parents+i*3,payload+1,12);
  for(j=0;j<3;j++)if(payload[j+1]==0xffffffffu)return 0;
 }
 return 0;
}
static long cpu_ioctl(struct file *file,unsigned int cmd,unsigned long arg){
 struct cpu_state s;struct pll_info pi;struct clock_info ci;u32 khz;u64 desired,error;int rc=0;
 mutex_lock(&lock);
 if(!opened){rc=-EBADF;goto done;}
 if(cmd==GET_STATE){rc=read_state(&s);if(!rc&&copy_to_user((void __user *)arg,&s,sizeof(s)))rc=-EFAULT;goto done;}
 if(cmd==GET_PLL){pll_diagnostic(&pi);if(copy_to_user((void __user *)arg,&pi,sizeof(pi)))rc=-EFAULT;goto done;}
 if(cmd==GET_CLOCK){
  if(copy_from_user(&ci,(void __user *)arg,sizeof(ci))){rc=-EFAULT;goto done;}
  if(ci.id>150){rc=-EINVAL;goto done;}rc=clock_diagnostic(&ci);if(rc)goto done;
  if(copy_to_user((void __user *)arg,&ci,sizeof(ci)))rc=-EFAULT;
  goto done;
 }
 if(cmd!=SET_KHZ){rc=-ENOTTY;goto done;}
 if(quarantined){rc=-EBUSY;goto done;}
 if(copy_from_user(&khz,(void __user *)arg,sizeof(khz))){rc=-EFAULT;goto done;}
 if(khz==599999)khz=600000;
 if(khz==1199999)khz=1200000;
 if(khz!=600000&&khz!=800000&&khz!=1000000&&khz!=1200000){rc=-EINVAL;goto done;}
 if(!unchanged()){rc=-EUCLEAN;goto done;}
 rc=no_vpll_consumers();if(rc)goto done;
 rc=set_four(khz);if(rc)goto failed;
 rc=read_state(&s);if(rc)goto failed;
 desired=(u64)target_khz*1000;error=s.actual_hz>desired?s.actual_hz-desired:desired-s.actual_hz;
 if(error>300||!unchanged()){rc=-EUCLEAN;goto failed;}
 last_error=0;goto done;
failed:last_error=rc;
 if(restore()){if(!quarantined){__module_get(THIS_MODULE);quarantined=true;}}
done:if(rc)last_error=rc;mutex_unlock(&lock);return rc;
}
static int cpu_release(struct inode *inode,struct file *file){
 int rc;mutex_lock(&lock);rc=restore();last_error=rc;opened=false;
 if(!rc){held=false;}else if(!quarantined){__module_get(THIS_MODULE);quarantined=true;}
 mutex_unlock(&lock);return rc;
}
static const struct file_operations fops={.owner=THIS_MODULE,.open=cpu_open,.unlocked_ioctl=cpu_ioctl,.release=cpu_release,.llseek=no_llseek};
static struct miscdevice device={.minor=MISC_DYNAMIC_MINOR,.name="fz3b_cpu_clock",.fops=&fops,.mode=0600};
static struct clk *provider(struct device_node *np,u32 id){struct of_phandle_args args={.np=np,.args_count=1};args.args[0]=id;return of_clk_get_from_provider(&args);}
static int __init cpu_init(void){
 struct device_node *np;struct clock_info ci;unsigned i;int rc;
 BUILD_BUG_ON(sizeof(struct cpu_state)!=40);
 BUILD_BUG_ON(sizeof(struct pll_info)!=48);BUILD_BUG_ON(sizeof(struct clock_info)!=76);
 fw_invoke=(void *)kallsyms_lookup_name("zynqmp_pm_invoke_fn");if(!fw_invoke)return -ENODEV;
 pm=zynqmp_pm_get_eemi_ops();if(!pm||!pm->clock_getparent||!pm->clock_setparent||!pm->clock_getdivider||!pm->clock_setdivider||!pm->ioctl||!pm->query_data||!pm->clock_getstate)return -ENODEV;
 for(i=75;i<=100;i++){memset(&ci,0,sizeof(ci));ci.id=i;clock_diagnostic(&ci);if(!strcmp(ci.name,"apll_int")){apll_pm_id=i;break;}}
 if(!apll_pm_id)return -ENODEV;
 np=of_find_node_by_path("/clk");if(!np)return -ENODEV;
 acpu=provider(np,ACPU_ID);dpll=provider(np,DPLL_ID);apll=provider(np,APLL_ID);of_node_put(np);
 if(IS_ERR(acpu)||IS_ERR(dpll)||IS_ERR(apll)){rc=-ENODEV;goto put;}
 mux=clk_get_parent(acpu);
 if(!mux||strcmp(__clk_get_name(acpu),"acpu")||strcmp(__clk_get_name(mux),"acpu_mux")||strcmp(__clk_get_name(dpll),"dpll")||strcmp(__clk_get_name(apll),"apll")){rc=-ENODEV;goto put;}
 crf=ioremap(0xfd1a0000ULL,4096);crl=ioremap(0xff5e0000ULL,4096);
 if(!crf||!crl){rc=-ENOMEM;goto unmap;}
 rc=misc_register(&device);if(!rc)return 0;
unmap:if(crf)iounmap(crf);if(crl)iounmap(crl);
put:if(!IS_ERR(acpu)&&acpu)clk_put(acpu);if(!IS_ERR(dpll)&&dpll)clk_put(dpll);if(!IS_ERR(apll)&&apll)clk_put(apll);return rc;
}
static void __exit cpu_exit(void){misc_deregister(&device);iounmap(crf);iounmap(crl);clk_put(acpu);clk_put(dpll);clk_put(apll);}
module_init(cpu_init);module_exit(cpu_exit);
MODULE_LICENSE("GPL");MODULE_DESCRIPTION("FZ3B CPU four-rate firmware VPLL lease; no MMIO, PL or DDR writes");
