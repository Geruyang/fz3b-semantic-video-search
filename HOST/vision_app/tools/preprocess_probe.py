"""Pixel-equivalence and on-board timing for crop-limited resize."""
import datetime
import json
from vision_app.tools.board_link import ROOT, open_link, run

PROGRAM='''import io,json,time
import numpy as np
from PIL import Image
from vision_app.camera import preprocess_jpeg

def candidate(jpeg):
 with Image.open(io.BytesIO(jpeg)) as opened:
  opened.load()
  image=opened if opened.mode=='RGB' else opened.convert('RGB')
  w,h=image.size
  long=int(256*max(w,h)/min(w,h))
  rw,rh=(256,long) if w<=h else (long,256)
  left,top=int(round((rw-256)/2.)),int(round((rh-256)/2.))
  resized=image.resize((rw,rh),Image.BILINEAR)
  array=np.asarray(resized.crop((left,top,left+256,top+256)),dtype=np.uint8).astype(np.float32)
  array/=np.float32(255)
  return np.ascontiguousarray(array.transpose(2,0,1)[None])

jpegs=[open('preprocess-source.jpg','rb').read()]
random=np.random.RandomState(42)
for w,h in ((1280,720),(720,1280),(640,480),(1920,1080),(1280,720)):
 for kind in range(6):
  if kind==0: pixels=random.randint(0,256,size=(h,w,3)).astype(np.uint8)
  elif kind==1: pixels=np.zeros((h,w,3),np.uint8);pixels[h//2,w//2]=255
  elif kind==2: pixels=np.tile((np.arange(w)%256).astype(np.uint8)[None,:,None],(h,1,3))
  elif kind==3: pixels=np.tile((np.arange(h)%256).astype(np.uint8)[:,None,None],(1,w,3))
  elif kind==4: pixels=np.tile(((np.arange(w)%2)*255).astype(np.uint8)[None,:,None],(h,1,3))
  else:pixels=np.full((h,w,3),255,dtype=np.uint8)
  stream=io.BytesIO();Image.fromarray(pixels).save(stream,'JPEG',quality=90);jpegs.append(stream.getvalue())
differences=[]
for i,jpeg in enumerate(jpegs):
 a=preprocess_jpeg(jpeg);b=candidate(jpeg)
 differences.append(dict(index=i,equal=bool(np.array_equal(a,b)),max_abs=float(np.max(np.abs(a-b))),different=int(np.count_nonzero(a!=b))))
timings={}
for name,fn in (('original',preprocess_jpeg),('candidate',candidate)):
 samples=[]
 for unused in range(80):
  start=time.perf_counter();fn(jpegs[0]);samples.append((time.perf_counter()-start)*1000)
 timings[name]=dict(mean_ms=float(np.mean(samples)),p50_ms=float(np.median(samples)),p95_ms=float(np.percentile(samples,95)))
print(json.dumps(dict(variant='copy_only_full_resize',equal=all(x['equal'] for x in differences),cases=differences,timings=timings)))
'''

def main():
    remote='/root/fz3b-vision-console-20261009-001'
    client=open_link()
    try:
        s=client.open_sftp()
        latest=sorted((ROOT/'artifacts/ps-application-20261009').glob('live-smoke-*/inference-frame.jpg'))[-1]
        s.put(str(latest),remote+'/preprocess-source.jpg')
        with s.file(remote+'/preprocess_probe.py','w') as handle:handle.write(PROGRAM)
        s.close()
        report=json.loads(run(client,'cd '+remote+'; python3 -B preprocess_probe.py',timeout=180))
        path=ROOT/'artifacts/ps-application-20261009'/('preprocess-probe-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:client.close()

if __name__=='__main__':main()
