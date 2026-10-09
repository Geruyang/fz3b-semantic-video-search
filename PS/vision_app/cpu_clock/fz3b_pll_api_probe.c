/* READ-only generic PLL API probe for the matching 4.14 firmware entry.
 * API IDs/node/parameters are from official xilinx-v2018.3 pm_defs.h.
 * The PM entry is public in firmware.h but not exported to modules in this
 * old kernel; resolve it without modifying kernel code or firmware state.
 */
#include <linux/module.h>
#include <linux/kallsyms.h>
#include <linux/firmware/xilinx/zynqmp/firmware.h>
static char report[2048];
module_param_string(report,report,sizeof(report),0444);
static int __init probe_init(void){
 int (*invoke)(u32,u32,u32,u32,u32,u32*);
 unsigned i,node;int rc,used=0;u32 out[PAYLOAD_ARG_CNT];
 invoke=(void *)kallsyms_lookup_name("zynqmp_pm_invoke_fn");
 if(!invoke)return -ENODEV;
 for(node=50;node<=51;node++){
  for(i=0;i<10;i++){
   memset(out,0,sizeof(out));rc=invoke(49,node,i,0,0,out);
   used+=scnprintf(report+used,sizeof(report)-used,"node %u param %u rc %d value %u\n",node,i,rc,out[1]);
  }
  memset(out,0,sizeof(out));rc=invoke(51,node,0,0,0,out);
  used+=scnprintf(report+used,sizeof(report)-used,"node %u mode rc %d value %u\n",node,rc,out[1]);
 }
 return 0;
}
static void __exit probe_exit(void){}
module_init(probe_init);module_exit(probe_exit);
MODULE_LICENSE("GPL");MODULE_DESCRIPTION("FZ3B READ-only APLL generic PM parameter/mode capability probe");
