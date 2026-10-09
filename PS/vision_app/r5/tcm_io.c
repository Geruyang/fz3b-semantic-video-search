/* A53: aligned volatile MMIO only; no memcpy on Device memory. */
#include <stdint.h>
#include <stddef.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <time.h>
#include <errno.h>
static int fd=-1;
static volatile uint32_t *banks[2];
static const off_t addresses[2]={0xffe2c000ULL,0xffebc000ULL};
static inline void barrier(void){__asm__ volatile("dmb sy":::"memory");}
/* Query core RUN bits without touching unpowered TCM. Aligned u32 MMIO. */
int r5_halted(void){
 int control=open("/dev/mem",O_RDONLY|O_SYNC);if(control<0)return -errno;
 void *m=mmap(NULL,4096,PROT_READ,MAP_SHARED,control,0xff9a0000ULL);
 if(m==MAP_FAILED){int e=errno;close(control);return -e;}
 volatile uint32_t *r=m;barrier();int halted=!(r[0x100/4]&1u)&&!(r[0x200/4]&1u);
 munmap(m,4096);close(control);return halted;
}
void r5_close(void){for(unsigned i=0;i<2;i++)if(banks[i]){munmap((void *)banks[i],16384);banks[i]=NULL;}if(fd>=0){close(fd);fd=-1;}}
int r5_open(void){
 fd=open("/dev/mem",O_RDWR|O_SYNC);if(fd<0)return -errno;
 for(unsigned i=0;i<2;i++){
  void *m=mmap(NULL,16384,PROT_READ|PROT_WRITE,MAP_SHARED,fd,addresses[i]);
  if(m==MAP_FAILED){int e=errno;r5_close();return -e;}banks[i]=m;
  if(banks[i][0]!=0x52355631u||banks[i][1]!=1u||banks[i][2]!=i){r5_close();return -ENODEV;}
 }
 return 0;
}
uint32_t r5_read(unsigned core,unsigned word){return core<2&&word<16&&banks[core]?banks[core][word]:0;}
uint32_t r5_read_score(unsigned core,unsigned index){barrier();return core<2&&index<16&&banks[core]?banks[core][16+index]:0;}
int r5_request(unsigned core,uint32_t op,uint32_t arg,const uint8_t *data,uint32_t n,uint32_t *answer){
 if(core>1||n>8192||!banks[core])return -EINVAL;
 volatile uint32_t *b=banks[core];
 if(b[4]!=b[5])return -EBUSY;
 volatile uint8_t *dst=(void *)(b+16);
 for(uint32_t i=0;i<n;i++)dst[i]=data[i];
 b[6]=op;b[7]=n;b[8]=arg;barrier();uint32_t seq=b[4]+1u;if(!seq)seq=1;b[4]=seq;barrier();
 struct timespec start,now,pause={0,100000};clock_gettime(CLOCK_MONOTONIC,&start);
 while(b[5]!=seq){
  clock_gettime(CLOCK_MONOTONIC,&now);
  if((now.tv_sec-start.tv_sec)*1000000000LL+now.tv_nsec-start.tv_nsec>500000000LL)return -ETIMEDOUT;
  nanosleep(&pause,NULL);
 }
 barrier();*answer=b[9];return (int)b[10];
}
