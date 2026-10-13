"""Schedule narration, duck original upbeat music, normalize audio and preserve every video packet."""
from pathlib import Path
import json,wave,subprocess,re,hashlib,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
TEMP=ROOT/'.work/video-audio'
SOURCE=Path('C:/Users/ruyangge/Videos/FZ3B语义检索/test/FZ3B_应用演示_实时文字找场景与视频语义检索.mp4')
TARGET=SOURCE.with_name(SOURCE.stem+'_解说配乐版.mp4')
ASSETS=SOURCE.parent/'配音素材'
if TARGET.exists():
    expected='4874eaa065dc589eaff3670711c0fc4ca4d02291a935ef7d2292dc96442eea60'
    if hashlib.sha256(TARGET.read_bytes()).hexdigest()!=expected:raise RuntimeError('Existing output changed since the 2.1 draft')
ffmpeg=next((ROOT/'deliverables/vision-console/FZ3BVisionConsole/_internal/imageio_ffmpeg/binaries').glob('*.exe'))
cue_doc=json.loads((Path(__file__).parent/'cues.json').read_text(encoding='utf-8'))
duration=cue_doc['duration'];sr=24000
voice=np.zeros(round(duration*sr),np.float32);segments=[]

def read_wav(path):
    with wave.open(str(path),'rb') as f:
        assert f.getnchannels()==1 and f.getsampwidth()==2 and f.getframerate()==sr
        data=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
    return data

for cue in cue_doc['cues']:
    path=TEMP/'voice'/(cue['id']+'.wav')
    data=read_wav(path)
    nonzero=np.flatnonzero(np.abs(data)>.003)
    if not len(nonzero):raise RuntimeError('Narration is silent: '+cue['id'])
    start=max(0,int(nonzero[0])-.08*sr);end=min(len(data),int(nonzero[-1])+.12*sr)
    data=data[int(start):int(end)];original_duration=len(data)/sr;speed=1
    if original_duration>cue['limit']:
        speed=original_duration/cue['limit']
        if speed>1.30:raise RuntimeError('Narration exceeds its available time window: '+cue['id'])
        adjusted=TEMP/'voice'/(cue['id']+'-timed.wav')
        subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-n','-i',str(path),'-af','atempo=%.8f'%speed,str(adjusted)],check=True)
        data=read_wav(adjusted);nonzero=np.flatnonzero(np.abs(data)>.003);data=data[max(0,int(nonzero[0])//1-int(.08*sr)):min(len(data),int(nonzero[-1])+int(.12*sr))]
    active=data[np.abs(data)>.01]
    active_rms=float(np.sqrt(np.mean(active**2)))
    gain=min(.14/max(active_rms,1e-6),.86/max(float(np.max(np.abs(data))),1e-6))
    data*=gain
    fade=min(240,len(data)//3);data[:fade]*=np.linspace(0,1,fade);data[-fade:]*=np.linspace(1,0,fade)
    offset=round(cue['start']*sr)
    if offset+len(data)>len(voice):raise RuntimeError('Narration ends after video')
    if np.any(voice[offset:offset+len(data)]):raise RuntimeError('Overlapping narration')
    voice[offset:offset+len(data)]=data
    segments.append({**cue,'end':cue['start']+len(data)/sr,'actual_duration':len(data)/sr,'original_duration':original_duration,'playback_rate':speed,'gain':gain})

voice_path=TEMP/'narration-timeline.wav'
with wave.open(str(voice_path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr);f.writeframes((voice*32767).astype('<i2').tobytes())
mix_filter='[0:a]highpass=f=85,lowpass=f=10500,alimiter=limit=0.9:level=false,asplit=2[voice][side];[1:a]volume=0.48[music];[music][side]sidechaincompress=threshold=0.02:ratio=5:attack=20:release=520[ducked];[voice][ducked]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.90:level=false'
inputs=['-i',str(voice_path),'-i',str(TEMP/'original-tech-upbeat.wav')]
measure=subprocess.run([str(ffmpeg),'-hide_banner','-nostats']+inputs+['-filter_complex',mix_filter+',loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json[out]','-map','[out]','-f','null','-'],capture_output=True,check=True)
match=re.findall(r'\{\s*"input_i".*?\}',measure.stderr.decode(errors='replace'),re.S)
if not match:raise RuntimeError('No loudness measurement returned')
levels=json.loads(match[-1])
norm='loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={target_offset}:linear=true:print_format=json'.format(**levels)
mixed=TEMP/'final-upbeat-mix.wav'
result=subprocess.run([str(ffmpeg),'-hide_banner','-nostats','-n']+inputs+['-filter_complex',mix_filter+','+norm+'[out]','-map','[out]','-ar','48000','-ac','2','-c:a','pcm_s16le','-t',str(duration),str(mixed)],capture_output=True,check=True)
(TEMP/'mix-loudness.log').write_bytes(result.stderr)
candidate=TARGET.with_name(TARGET.stem+'.processing.mp4')
if candidate.exists():candidate.unlink()
subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-n','-i',str(SOURCE),'-i',str(mixed),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t',str(duration),'-movflags','+faststart','-metadata','title=FZ3B Semantic Video Search — narrated applications demo','-metadata','comment=AI voice-over; original upbeat futuristic electronic score Bright Circuit',str(candidate)],check=True)
decoded=subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-i',str(candidate),'-f','null','-'],capture_output=True)
assert decoded.returncode==0 and not decoded.stderr,decoded.stderr.decode(errors='replace')
def stream_hash(path):
    p=subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-i',str(path),'-map','0:v:0','-c:v','copy','-f','hash','-hash','sha256','-'],capture_output=True,check=True)
    return p.stdout.decode().strip()
assert stream_hash(SOURCE)==stream_hash(candidate),'Video packets changed during audio mux'
verification=subprocess.run([str(ffmpeg),'-hide_banner','-nostats','-i',str(candidate),'-map','0:a:0','-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,check=True)
final_levels=json.loads(re.findall(r'\{\s*"input_i".*?\}',verification.stderr.decode(errors='replace'),re.S)[-1])
assert -18<=float(final_levels['input_i'])<=-14,final_levels
assert float(final_levels['input_tp'])<=-.9,final_levels
candidate_bytes=candidate.stat().st_size;candidate_sha=hashlib.sha256(candidate.read_bytes()).hexdigest()
ASSETS.mkdir(exist_ok=True)
for original,name in [(voice_path,'中文解说.wav'),(TEMP/'original-tech-upbeat.wav','原创科技配乐.wav'),(mixed,'完整混音.wav')]:shutil.copy2(original,ASSETS/name)
candidate.replace(TARGET)
receipt={'version':'2.1','source':SOURCE.name,'output':TARGET.name,'duration':duration,'voice':'AI 配音','synthetic_voice':True,'music':'Bright Circuit — original upbeat futuristic electronic composition, 118 BPM','audio_format':'AAC 192 kbit/s, 48 kHz stereo','music_ducked_under_narration':True,'loudness':final_levels,'segments':segments,'video_stream_identity_preserved':True,'decode':'PASS','video_bytes':candidate_bytes,'video_sha256':candidate_sha,'local_output':str(TARGET),'local_audio_assets':str(ASSETS)}
meta=Path(__file__).parent/'audio-receipt.json';meta.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(meta,ASSETS/'配音时间轴与混音回执.json')
text='\n\n'.join('%.2f–%.2f 秒\n%s'%(s['start'],s['end'],s['text']) for s in segments)
(Path(__file__).parent/'script.md').write_text('# 2.1 视频解说词\n\n'+text+'\n',encoding='utf-8',newline='\n')
shutil.copy2(Path(__file__).parent/'script.md',ASSETS/'解说词.md')
shutil.copy2(TARGET,ROOT/'docs/media/fz3b-applications-demo.mp4')
print(json.dumps(receipt),flush=True)
