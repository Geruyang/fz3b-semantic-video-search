/* Four CPU rates. Firmware-authorized NODE_VPLL=51 only; no MMIO writes.
 * Integer helper table UG1085 v2.5 table37-1: FB48 CNT775 / FB60 CNT625.
 * CPU stays DPLL/div2 during every PLL reset and parameter transaction. */
static int (*fw_invoke)(u32,u32,u32,u32,u32,u32*);
static u32 original_cfg,original_frac,target_khz;
static u32 v_original[3],v_expected[3],v_params[10],v_mode;
static int pll_param_get(u32 node,u32 parameter,u32 *value){
 u32 out[PAYLOAD_ARG_CNT]={0};int rc=fw_invoke(49,node,parameter,0,0,out);*value=out[1];return rc;
}
static int pll_mode_get(u32 node,u32 *value){
 u32 out[PAYLOAD_ARG_CNT]={0};int rc=fw_invoke(51,node,0,0,0,out);*value=out[1];return rc;
}
static int cpu_safe_dpll(void){
 int rc=pm->clock_setdivider(ACPU_ID,0xffff0002u);if(rc)return rc;
 rc=pm->clock_setparent(ACPU_ID,2);if(rc)return rc;
 return cpu_raw()==((original_ctrl&~0x3f07u)|0x202u)?0:-EUCLEAN;
}
static void v_raw(u32 *p){p[0]=readl((u8 __iomem *)crf+0x38);p[1]=readl((u8 __iomem *)crf+0x3c);p[2]=readl((u8 __iomem *)crf+0x40);}
static bool v_matches(void){
 u32 now[3],status=readl((u8 __iomem *)crf+0x44)&0x24u;v_raw(now);
 return !memcmp(now,v_expected,sizeof(now))&&status==(v_mode?0x24u:(baseline[3]&0x24u));
}
static int v_wait(u32 mode){
 unsigned i;for(i=0;i<1000;i++){
  u32 ctrl=readl((u8 __iomem *)crf+0x38),status=readl((u8 __iomem *)crf+0x44);
  if(mode==1&&!(ctrl&9u)&&(status&0x24u)==0x24u)return 0;
  if(mode==0&&(ctrl&9u)==9u&&!(status&4u))return 0;
  usleep_range(1000,1500);
 }
 return -ETIMEDOUT;
}
/* Real firmware graph. API failures never mean an invalid/reserved node. */
static struct clock_info graph[151];static u8 graph_loaded[151],graph_path[151];
static int graph_load(u32 id){
 struct zynqmp_pm_query_data q={0};u32 out[PAYLOAD_ARG_CNT]={0};int rc;
 if(id>150)return -EOPNOTSUPP;
 if(graph_loaded[id])return graph_loaded[id]==1?0:-ENODEV;
 q.qid=PM_QID_CLOCK_GET_ATTRIBUTES;q.arg1=id;rc=pm->query_data(q,out);if(rc)return rc;
 if(!(out[1]&1u)){graph_loaded[id]=2;return -ENODEV;}
 memset(&graph[id],0,sizeof(graph[id]));graph[id].id=id;
 rc=clock_diagnostic(&graph[id]);if(rc)return rc;if(!graph[id].name[0])return -EOPNOTSUPP;
 graph_loaded[id]=1;return 0;
}
static int graph_vpll(u32 id,unsigned depth){
 struct clock_info *ci;u32 parent;int rc;
 if(id==ACPU_ID)return 0; /* includes CPU half/full descendants */
 if(id==4u||id==96u)return 1;
 if(id>150||depth>32||graph_path[id])return -EOPNOTSUPP;
 rc=graph_load(id);if(rc)return rc;ci=&graph[id];if(ci->parents_error)return -EOPNOTSUPP;
 if(ci->parent_error){if(ci->parents[1]!=0xffffffffu)return -EOPNOTSUPP;parent=ci->parents[0];}
 else{if(ci->parent>=9)return -EOPNOTSUPP;parent=ci->parents[ci->parent];}
 if(parent==0xffffffffu||parent==0xfffffffeu)return -EOPNOTSUPP;
 if((parent>>16)==5u)return 0;if((parent>>16)>4u)return -EOPNOTSUPP;
 graph_path[id]=1;rc=graph_vpll(parent&0xffffu,depth+1);graph_path[id]=0;return rc;
}
static int no_vpll_consumers(void){
 unsigned i;int rc;memset(graph_loaded,0,sizeof(graph_loaded));memset(graph_path,0,sizeof(graph_path));
 for(i=0;i<=75;i++){
  /* 4 is VPLL itself; 9 its ungated cross-domain divider. They are
   * carriers, not terminal consumers. Every downstream output is checked. */
  if(i==ACPU_ID||i==4u||i==9u)continue;
  rc=graph_load(i);if(rc&&graph_loaded[i]==2)continue;if(rc)return rc;
  if(!graph[i].enabled&&!graph[i].state_error)continue;
  rc=graph_vpll(i,0);if(rc)return rc>0?-EBUSY:rc;
 }
 return 0;
}
static u32 v_cfg(const u32 *p){
 u32 mask=(127u<<25)|(1023u<<13)|(7u<<10)|(15u<<5)|15u;
 return (v_original[1]&~mask)|(p[5]<<25)|(p[6]<<13)|(p[7]<<10)|(p[8]<<5)|p[9];
}
static int v_program(const u32 *p,u32 mode){
 unsigned i;u32 value,expected[3];int rc;
 if(mode>1)return -EINVAL;
 if(cpu_raw()!=((original_ctrl&~0x3f07u)|0x202u)||!protected_unchanged())return -EUCLEAN;
 rc=no_vpll_consumers();if(rc)return rc;
 rc=fw_invoke(50,51,0,0,0,NULL);if(rc)return rc;
 rc=v_wait(0);if(rc)return rc;
 for(i=0;i<10;i++){
  rc=pll_param_get(51,i,&value);if(rc)return rc;if(value==p[i])continue;
  rc=fw_invoke(48,51,i,p[i],0,NULL);if(rc)return rc;
 }
 if(mode){rc=fw_invoke(50,51,1,0,0,NULL);if(rc)return rc;rc=v_wait(1);if(rc)return rc;}
 expected[0]=(v_original[0]&~(0x7f00u|9u))|(p[1]<<8)|(mode?0:9u);
 expected[1]=v_cfg(p);expected[2]=v_original[2];
 rc=pll_mode_get(51,&value);if(rc||value!=mode)return rc?rc:-EUCLEAN;
 for(i=0;i<10;i++){rc=pll_param_get(51,i,&value);if(rc||value!=p[i])return rc?rc:-EUCLEAN;}
 memcpy(v_expected,expected,sizeof(expected));v_mode=mode;
 return v_matches()&&protected_unchanged()?0:-EUCLEAN;
}
static int v_restore(void){
 u32 now[3];v_raw(now);
 if(!memcmp(now,v_original,sizeof(now))){memcpy(v_expected,v_original,sizeof(now));v_mode=0;return v_matches()?0:-EUCLEAN;}
 return v_program(v_params,0);
}
static int set_four(u32 khz){
 u32 p[10],now[3];int rc;
 if(khz==599999)khz=600000;if(khz==1199999)khz=1200000;
 if(khz!=600000&&khz!=800000&&khz!=1000000&&khz!=1200000)return -EINVAL;
 rc=cpu_safe_dpll();if(rc)return rc;
 if(!protected_unchanged())return -EUCLEAN;
 if(khz==600000||khz==1200000){rc=v_restore();if(rc)return rc;}
 else{
  memcpy(p,v_params,sizeof(p));p[1]=khz==800000?48:60;p[2]=0;p[5]=63;
  p[6]=khz==800000?775:625;p[7]=3;p[8]=3;p[9]=2;
  rc=v_program(p,1);if(rc)return rc;
  rc=pm->clock_setparent(ACPU_ID,3);if(rc)return rc;
  /* PMU request may restore a saved PLL context. Check BEFORE div1,
   * so even original FB90 can only produce 750MHz at this point. */
  v_raw(now);if(memcmp(now,v_expected,sizeof(now))||!v_matches()||!protected_unchanged())return -EUCLEAN;
 }
 rc=pm->clock_setdivider(ACPU_ID,0xffff0000u|(khz==600000?2:1));if(rc)return rc;
 target_khz=khz;return 0;
}
