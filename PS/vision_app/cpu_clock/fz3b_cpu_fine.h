/* APLL-only generic PM protocol, NODE_APLL=50 (official 2018.3 pm_defs.h).
 * Integer/fractional CFG coefficients: UG1085 v2.5, table37-2 pp1140-1141.
 * A53 always moves to known DPLL/div2 before APLL reset/program/restore.
 */
static int (*fw_invoke)(u32,u32,u32,u32,u32,u32*);
static u32 original_pll[10],original_mode,original_cfg,original_frac;
static u32 expected_apll,expected_cfg,expected_frac,target_khz;
static bool pll_dirty;
static int no_apll_consumers(void);
static int pll_get(u32 parameter,u32 *value){
 u32 out[PAYLOAD_ARG_CNT]={0};int rc=fw_invoke(49,50,parameter,0,0,out);*value=out[1];return rc;
}
static int pll_get_mode(u32 *value){
 u32 out[PAYLOAD_ARG_CNT]={0};int rc=fw_invoke(51,50,0,0,0,out);*value=out[1];return rc;
}
static int cpu_safe_dpll(void){
 int rc=pm->clock_setdivider(ACPU_ID,0xffff0002u);if(rc)return rc;
 rc=pm->clock_setparent(ACPU_ID,2);if(rc)return rc;
 return cpu_raw()==((original_ctrl&~0x3f07u)|0x202u)?0:-EUCLEAN;
}
static int pll_wait_locked(void){
 unsigned i;for(i=0;i<1000;i++){
  if((readl((u8 __iomem *)crf+0x44)&9u)==9u&&
      !(readl((u8 __iomem *)crf+0x20)&9u))return 0;
  usleep_range(1000,1500);
 }
 return -ETIMEDOUT;
}
static u32 pll_cfg(const u32 *p){
 u32 mask=(127u<<25)|(1023u<<13)|(3u<<10)|(15u<<5)|15u;
 return (original_cfg&~mask)|(p[5]<<25)|(p[6]<<13)|(p[7]<<10)|(p[8]<<5)|p[9];
}
static int pll_program(const u32 *p,u32 mode){
 unsigned i;u32 value;int rc;
 /* Recheck on every reset, including rollback/close. If a new consumer
  * appeared, keep CPU on DPLL/div2 and fail closed instead of resetting it. */
 rc=no_apll_consumers();if(rc)return rc;
 pll_dirty=true;
 rc=fw_invoke(50,50,0,0,0,NULL);if(rc){pr_warn("fz3b CPU: PM APLL reset denied rc=%d\n",rc);return rc;}
 if((readl((u8 __iomem *)crf+0x20)&9u)!=9u)return -EUCLEAN;
 for(i=0;i<10;i++){
  rc=pll_get(i,&value);if(rc)return rc;
  if(value==p[i])continue;
  rc=fw_invoke(48,50,i,p[i],0,NULL);if(rc){pr_warn("fz3b CPU: PM APLL parameter %u denied rc=%d\n",i,rc);return rc;}
 }
 rc=fw_invoke(50,50,mode,0,0,NULL);if(rc){pr_warn("fz3b CPU: PM APLL mode %u denied rc=%d\n",mode,rc);return rc;}
 rc=pll_wait_locked();if(rc)return rc;
 rc=pll_get_mode(&value);if(rc||value!=mode)return rc?rc:-EUCLEAN;
 for(i=0;i<10;i++){rc=pll_get(i,&value);if(rc||value!=p[i])return rc?rc:-EUCLEAN;}
 expected_apll=(original_ctrl_pll&~0x7f00u)|(p[1]<<8);
 expected_cfg=pll_cfg(p);
 expected_frac=(original_frac&~0x8000ffffu)|p[2]|(mode==2?0x80000000u:0);
 if(readl((u8 __iomem *)crf+0x20)!=expected_apll||
    readl((u8 __iomem *)crf+0x24)!=expected_cfg||
    readl((u8 __iomem *)crf+0x28)!=expected_frac)return -EUCLEAN;
 return 0;
}
static int pll_restore(void){
 int rc;
 if(readl((u8 __iomem *)crf+0x20)==original_ctrl_pll&&
    readl((u8 __iomem *)crf+0x24)==original_cfg&&
    readl((u8 __iomem *)crf+0x28)==original_frac){
  rc=pll_wait_locked();if(rc)return rc;
  expected_apll=original_ctrl_pll;expected_cfg=original_cfg;expected_frac=original_frac;pll_dirty=false;return 0;
 }
 rc=pll_program(original_pll,original_mode);if(rc)return rc;
 if(expected_apll!=original_ctrl_pll||expected_cfg!=original_cfg||expected_frac!=original_frac)return -EUCLEAN;
 pll_dirty=false;return 0;
}
/* Firmware metadata, not CCF's cached topology. Only explicit invalid
 * attribute nodes may be skipped; API failure, unknown parent and loops deny. */
static struct clock_info graph[151];
static u8 graph_loaded[151],graph_path[151];
static int graph_load(u32 id){
 struct zynqmp_pm_query_data q={0};u32 out[PAYLOAD_ARG_CNT]={0};int rc;
 if(id>150)return -EOPNOTSUPP;
 if(graph_loaded[id])return graph_loaded[id]==1?0:-ENODEV;
 q.qid=PM_QID_CLOCK_GET_ATTRIBUTES;q.arg1=id;
 rc=pm->query_data(q,out);if(rc)return rc;
 if(!(out[1]&1u)){graph_loaded[id]=2;return -ENODEV;}
 memset(&graph[id],0,sizeof(graph[id]));graph[id].id=id;
 rc=clock_diagnostic(&graph[id]);if(rc)return rc;
 if(!graph[id].name[0])return -EOPNOTSUPP;
 graph_loaded[id]=1;return 0;
}
static int graph_apll(u32 id,unsigned depth){
 struct clock_info *ci;u32 parent;int rc;
 /* acpu_half -> acpu_full -> acpu is the CPU's own branch, not a
  * separate APLL consumer. CPU mux moves to DPLL before any reset. */
 if(id==ACPU_ID)return 0;
 if(id==APLL_ID||id==7u||id==apll_pm_id)return 1;
 if(id>150||depth>32||graph_path[id])return -EOPNOTSUPP;
 rc=graph_load(id);if(rc)return rc;
 ci=&graph[id];if(ci->parents_error)return -EOPNOTSUPP;
 if(ci->parent_error){
  if(ci->parents[1]!=0xffffffffu)return -EOPNOTSUPP;
  parent=ci->parents[0];
 }else{
  if(ci->parent>=9)return -EOPNOTSUPP;
  parent=ci->parents[ci->parent];
 }
 if(parent==0xffffffffu||parent==0xfffffffeu)return -EOPNOTSUPP;
 /* Official PARENT_CLK_EXTERNAL=5: physical reference, explicit terminus. */
 if((parent>>16)==5u)return 0;
 if((parent>>16)>4u)return -EOPNOTSUPP;
 graph_path[id]=1;rc=graph_apll(parent&0xffffu,depth+1);graph_path[id]=0;
 return rc;
}
static int no_apll_consumers(void){
 unsigned i;int rc;
 memset(graph_loaded,0,sizeof(graph_loaded));memset(graph_path,0,sizeof(graph_path));
 for(i=0;i<=75;i++){
  if(i==ACPU_ID||i==APLL_ID)continue;
  rc=graph_load(i);if(rc&&graph_loaded[i]==2)continue;if(rc)return rc;
  if(!graph[i].enabled&&!graph[i].state_error)continue;
  rc=graph_apll(i,0);if(rc)return rc>0?-EBUSY:rc;
 }
 return 0;
}
static int set_fine(u32 khz){
 u32 p[10],divider,fb,frac;u64 scaled,vco;int rc;
 if(khz==599999)khz=600000;
 if(khz==1199999)khz=1200000;
 if(khz<600000||khz>1200000||khz%1000)return -EINVAL;
 rc=cpu_safe_dpll();if(rc)return rc;
 /* PM setparent requests/releases PLL references. A last-reference suspend
  * would save a context later restored over our parameters. Refuse that
  * platform state before programming; hardware must still match the lease. */
 if((readl((u8 __iomem *)crf+0x44)&9u)!=9u||
    readl((u8 __iomem *)crf+0x20)!=expected_apll||
    readl((u8 __iomem *)crf+0x24)!=expected_cfg||
    readl((u8 __iomem *)crf+0x28)!=expected_frac)return -EUCLEAN;
 if(khz==600000||khz==1200000){
  rc=pll_restore();if(rc)return rc;divider=khz==600000?2:1;
 }else{
  divider=khz<750000?2:1;
  scaled=((u64)khz*1000*divider*2*65536+16666666ULL)/33333333ULL;
  fb=scaled>>16;frac=scaled&0xffffu;if(!frac)frac=1;
  vco=33333333ULL*((u64)fb*65536+frac)/65536;
  if(fb<45||fb>89||vco<1500000000ULL||vco>3000000000ULL)return -ERANGE;
  memcpy(p,original_pll,sizeof(p));p[1]=fb;p[2]=frac;p[5]=63;p[7]=3;p[8]=3;
  p[9]=fb<=47?1:fb<=65?6:fb<=81?10:fb<=87?6:12;
  switch(fb){case 45:p[6]=825;break;case 46:p[6]=800;break;case 47:case 48:p[6]=775;break;case 49:case 50:p[6]=750;break;case 51:p[6]=725;break;case 52:case 53:p[6]=700;break;case 54:case 55:p[6]=675;break;case 56:case 57:p[6]=650;break;case 58:case 59:case 60:p[6]=625;break;default:p[6]=600;}
  rc=pll_program(p,2);if(rc)return rc;
  rc=pm->clock_setparent(ACPU_ID,0);if(rc)return rc;
 }
 rc=pm->clock_setdivider(ACPU_ID,0xffff0000u|divider);if(rc)return rc;
 target_khz=khz;return 0;
}
