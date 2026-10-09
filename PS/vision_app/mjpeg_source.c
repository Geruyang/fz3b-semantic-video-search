#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <linux/videodev2.h>

static volatile sig_atomic_t stop;
static void interrupted(int s){ (void)s; stop=1; }
static int xio(int fd,unsigned long op,void *p){int r;do{r=ioctl(fd,op,p);}while(r<0&&errno==EINTR&&!stop);return r;}
static int writeall(const void *p,size_t n){const char *c=p;while(n&&!stop){ssize_t k=write(1,c,n);if(k<0&&errno==EINTR)continue;if(k<=0)return -1;c+=k;n-=k;}return n?-1:0;}
#define CHECK(x) do{if((x)<0){perror(#x);goto cleanup;}}while(0)
int main(int argc,char **argv){
 if(argc!=6){fprintf(stderr,"Usage: mjpeg_source DEVICE WIDTH HEIGHT FPS FRAMES\n");return 2;}
 int w=atoi(argv[2]),h=atoi(argv[3]),fps=atoi(argv[4]),count=atoi(argv[5]);
 if(w<1||w>2560||h<1||h>1440||fps<1||fps>30||count<1||count>100000)return 2;
 int fd=-1,rc=1,streaming=0;unsigned mapped=0;void *mem[4]={0};size_t sizes[4]={0};
 enum v4l2_buf_type type=V4L2_BUF_TYPE_VIDEO_CAPTURE;
 signal(SIGINT,interrupted);signal(SIGTERM,interrupted);signal(SIGPIPE,SIG_IGN);
 CHECK(fd=open(argv[1],O_RDWR|O_NONBLOCK));
 struct v4l2_format fmt={0};fmt.type=type;fmt.fmt.pix.width=w;fmt.fmt.pix.height=h;fmt.fmt.pix.pixelformat=V4L2_PIX_FMT_MJPEG;fmt.fmt.pix.field=V4L2_FIELD_ANY;
 CHECK(xio(fd,VIDIOC_S_FMT,&fmt));
 if(fmt.fmt.pix.width!=(unsigned)w||fmt.fmt.pix.height!=(unsigned)h||fmt.fmt.pix.pixelformat!=V4L2_PIX_FMT_MJPEG){fprintf(stderr,"Mode mismatch\n");goto cleanup;}
 struct v4l2_streamparm parm={0};parm.type=type;parm.parm.capture.timeperframe.numerator=1;parm.parm.capture.timeperframe.denominator=fps;
 CHECK(xio(fd,VIDIOC_S_PARM,&parm));
 fprintf(stderr,"NEGOTIATED %ux%u MJPG %u/%u fps\n",fmt.fmt.pix.width,fmt.fmt.pix.height,parm.parm.capture.timeperframe.denominator,parm.parm.capture.timeperframe.numerator);
 struct v4l2_requestbuffers req={0};req.type=type;req.memory=V4L2_MEMORY_MMAP;req.count=4;CHECK(xio(fd,VIDIOC_REQBUFS,&req));
 if(req.count<2||req.count>4){fprintf(stderr,"Unexpected buffer count\n");goto cleanup;}
 for(unsigned i=0;i<req.count;i++){
  struct v4l2_buffer b={0};b.type=type;b.memory=V4L2_MEMORY_MMAP;b.index=i;CHECK(xio(fd,VIDIOC_QUERYBUF,&b));
  sizes[i]=b.length;mem[i]=mmap(NULL,b.length,PROT_READ|PROT_WRITE,MAP_SHARED,fd,b.m.offset);
  if(mem[i]==MAP_FAILED){perror("mmap");goto cleanup;}mapped++;CHECK(xio(fd,VIDIOC_QBUF,&b));
 }
 CHECK(xio(fd,VIDIOC_STREAMON,&type));streaming=1;
 for(int i=0;i<count&&!stop;){
  fd_set fds;FD_ZERO(&fds);FD_SET(fd,&fds);struct timeval timeout={5,0};
  int ready=select(fd+1,&fds,NULL,NULL,&timeout);if(ready<0&&errno==EINTR)continue;
  if(ready<=0){fprintf(stderr,"Capture timeout/select error\n");goto cleanup;}
  struct v4l2_buffer b={0};b.type=type;b.memory=V4L2_MEMORY_MMAP;
  if(xio(fd,VIDIOC_DQBUF,&b)<0){if(errno==EAGAIN)continue;perror("DQBUF");goto cleanup;}
  if(b.index>=mapped||b.bytesused>sizes[b.index]||!b.bytesused||(b.flags&V4L2_BUF_FLAG_ERROR)){fprintf(stderr,"Invalid/error buffer\n");goto cleanup;}
  uint32_t header[4]={0x43414d31,b.bytesused,b.sequence,b.flags};
  uint64_t stamp=(uint64_t)b.timestamp.tv_sec*1000000+b.timestamp.tv_usec;
  CHECK(writeall(header,sizeof header));CHECK(writeall(&stamp,sizeof stamp));CHECK(writeall(mem[b.index],b.bytesused));
  CHECK(xio(fd,VIDIOC_QBUF,&b));i++;
 }
 rc=stop?130:0;
cleanup:
 if(streaming)xio(fd,VIDIOC_STREAMOFF,&type);
 for(unsigned i=0;i<mapped;i++)munmap(mem[i],sizes[i]);
 if(fd>=0)close(fd);
 return rc;
}
