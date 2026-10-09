/* Dual Cortex-R5 application workers. No DDR, GEM, UVC or PL access.
 * CPU0: command validation / telemetry state machine.
 * CPU1: streaming CRC and transport framing metadata.
 * Mailbox in each core's own BTCM at local DA 0x2c000 (16 KiB).
 * Addresses derive from the running 2018.3 kernel's TCM DA mapping;
 * host global addresses are different for the two cores.
 */
#include <stdint.h>
#define MAGIC 0x52355631u
#ifndef CORE_ID
#define CORE_ID 0
#endif
struct mailbox {
 volatile uint32_t magic, version, core, heartbeat;
 volatile uint32_t request, response, opcode, length;
 volatile uint32_t argument, answer, status, telemetry_updates;
 volatile uint32_t current_khz, available_kb, camera_millifps, frame_sequence;
 volatile uint8_t data[8192];
};
static volatile struct mailbox *const box = (void *)0x0002c000u;
static uint32_t crc_table[256];
static int16_t queries[16][512];
static uint32_t query_count,query_loaded,next_frame;
static int valid_vector(const volatile int16_t *p){
 uint64_t norm=0;for(unsigned i=0;i<512;i++){int32_t v=p[i];norm+=(uint32_t)(v*v);}
 return norm>=1070000000ULL && norm<=1080000000ULL;
}
static inline void barrier(void) { __asm__ volatile("dmb sy" ::: "memory"); }
static uint32_t crc(uint32_t seed, uint32_t n) {
 uint32_t v=seed^0xffffffffu;
 for(uint32_t i=0;i<n;i++) v=crc_table[(v^box->data[i])&255u]^(v>>8);
 return v^0xffffffffu;
}
int main(void) {
 for(uint32_t i=0;i<256;i++) {
  uint32_t v=i;
  for(unsigned b=0;b<8;b++) v=(v>>1)^((0u-(v&1u))&0xedb88320u);
  crc_table[i]=v;
 }
 box->magic=0; box->version=1; box->core=CORE_ID; box->heartbeat=0;
 box->request=0; box->response=0; box->status=0; box->telemetry_updates=0;
 barrier(); box->magic=MAGIC; barrier();
 uint32_t last=0, ticks=0;
 for(;;) {
  if(++ticks==100000u) { box->heartbeat++; ticks=0; }
  uint32_t seq=box->request;
  if(seq==last) continue;
  barrier();
  uint32_t op=box->opcode,n=box->length,arg=box->argument;
  uint32_t answer=0,status=0;
  if(n>8192u) status=1;
  else if(op==1u) answer=arg;
  else if(CORE_ID==0 && op==10u) {
   answer=(arg==600000u || arg==800000u || arg==1000000u || arg==1200000u || arg==599999u || arg==1199999u);
   if(!answer) status=2;
  } else if(CORE_ID==0 && op==12u){next_frame=0;answer=1;
  } else if(CORE_ID==0 && op==13u){if(arg!=next_frame)status=4;else{next_frame++;answer=next_frame;}
  } else if(CORE_ID==0 && op==14u){if(arg!=next_frame)status=4;else answer=next_frame;
  } else if(CORE_ID==0 && op==30u){
   if(arg<1u||arg>16u)status=5;else{query_count=arg;query_loaded=0;answer=arg;}
  } else if(CORE_ID==0 && op==31u && n==1024u){
   volatile int16_t *words=(void *)box->data;
   if(arg>=query_count||!valid_vector(words))status=5;
   else{for(unsigned i=0;i<512;i++)queries[arg][i]=words[i];query_loaded|=1u<<arg;answer=arg;}
  } else if(CORE_ID==0 && op==32u && n==1024u){
   volatile int16_t *words=(void *)box->data;int32_t scores[16];
   if(query_loaded!=((1u<<query_count)-1u)||!valid_vector(words))status=5;
   else{
    for(unsigned q=0;q<query_count;q++){
     int32_t score=0;for(unsigned i=0;i<512;i++)score+=(int32_t)queries[q][i]*words[i];
     scores[q]=score;if(score>=(int32_t)arg)answer|=1u<<q;
    }
    volatile uint32_t *out=(void *)box->data;
    for(unsigned q=0;q<query_count;q++)out[q]=(uint32_t)scores[q];
   }
  } else if(CORE_ID==0 && op==11u && n==16u) {
   volatile uint32_t *words=(void *)box->data;
   box->current_khz=words[0]; box->available_kb=words[1];
   box->camera_millifps=words[2]; box->frame_sequence=words[3];
   box->telemetry_updates++; answer=box->telemetry_updates;
  } else if(CORE_ID==1 && op==20u) answer=crc(arg,n);
  else status=3;
  box->answer=answer; box->status=status; barrier(); box->response=seq;
  last=seq;
 }
}
