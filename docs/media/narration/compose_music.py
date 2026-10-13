"""Original upbeat, futuristic electronic music synthesized from oscillators and seeded noise."""
from pathlib import Path
import json,wave
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'.work/video-audio'
SR=48000
DURATION=10343/30
BPM=118
BEAT=60/BPM
rng=np.random.default_rng(210013)
audio=np.zeros((round(DURATION*SR),2),np.float32)

def hz(note):return 440*2**((note-69)/12)
def add(signal,start,gain=.1,pan=0):
    offset=round(start*SR)
    if offset<0 or offset>=len(audio):return
    count=min(len(signal),len(audio)-offset)
    left=np.sqrt((1-pan)/2);right=np.sqrt((1+pan)/2)
    audio[offset:offset+count,0]+=signal[:count]*gain*left
    audio[offset:offset+count,1]+=signal[:count]*gain*right

def pad(note,duration,seed):
    t=np.arange(round(duration*SR),dtype=np.float32)/SR
    f=hz(note);phase=seed*.37
    sound=(np.sin(2*np.pi*f*t+phase)+.38*np.sin(2*np.pi*f*1.003*t+phase+.8)+.20*np.sin(2*np.pi*f*2*t+phase))/.95
    envelope=np.minimum(t/.35,1)*np.minimum(np.maximum(duration-t,0)/.7,1)
    return (sound*envelope).astype(np.float32)

def pluck(note,duration=1.3):
    t=np.arange(round(duration*SR),dtype=np.float32)/SR;f=hz(note)
    sound=np.sin(2*np.pi*f*t)+.24*np.sin(2*np.pi*f*2*t)*np.exp(-t*3)+.09*np.sin(2*np.pi*f*3*t)*np.exp(-t*6)
    envelope=(1-np.exp(-t*140))*np.exp(-t*2.8)
    return (sound*envelope).astype(np.float32)

# D(add9), Gmaj7, Bm7, A(add9): bright major-key synth-pop progression.
chords=[([62,66,69,76],38),([55,59,62,66],43),([59,62,66,69],35),([57,61,64,71],45)]
for chord_index,start in enumerate(np.arange(0,DURATION,BEAT*4)):
    notes,bass=chords[chord_index%4]
    for j,note in enumerate(notes):add(pad(note,BEAT*4+1,chord_index*4+j),start,.030,[-.62,.26,-.18,.68][j])
    bass_t=np.arange(round(BEAT*3.8*SR),dtype=np.float32)/SR
    bass_signal=(np.sin(2*np.pi*hz(bass)*bass_t)+.18*np.sin(2*np.pi*hz(bass)*2*bass_t))*np.minimum(bass_t/.04,1)*np.minimum((BEAT*3.8-bass_t)/.2,1)
    add(bass_signal,start,.064,0)
    order=[0,2,1,2,3,2,1,2] if chord_index%2 else [0,1,2,1,3,2,1,2]
    for k,at in enumerate(np.arange(start+.08,start+BEAT*4,BEAT*.5)):
        if at<3 or at>DURATION-7:continue
        note=notes[order[k%len(order)]]+12
        gain=.052 if 251.3<=at<303.1 else .045
        signal=pluck(note,.92)
        pan=.46*np.sin(chord_index*.7+k*.8)
        add(signal,at,gain,pan)

for beat_index,start in enumerate(np.arange(0,DURATION,BEAT)):
    if start<12 or start>DURATION-10 or 184<start<191:continue
    section=.72 if start<186.3 else .87
    if beat_index%4 in (0,2):
        t=np.arange(round(.40*SR),dtype=np.float32)/SR
        phase=2*np.pi*(48*t+70*.032*(1-np.exp(-t/.032)))
        kick=np.sin(phase)*(1-np.exp(-t*900))*np.exp(-t*12)
        add(kick,start,.092*section,0)
    if beat_index%4 in (1,3):
        t=np.arange(round(.20*SR),dtype=np.float32)/SR
        noise=rng.standard_normal(len(t)).astype(np.float32)
        soft=np.convolve(noise,np.ones(7,dtype=np.float32)/7,mode='same')
        snare=(soft*.68+.32*np.sin(2*np.pi*165*t))*np.exp(-t*29)*(1-np.exp(-t*450))
        add(snare,start,.035*section,.10)
    for k in (0,1):
        if k and beat_index%8 in (5,7):continue
        t=np.arange(round(.07*SR),dtype=np.float32)/SR
        noise=rng.standard_normal(len(t)).astype(np.float32)
        low=np.convolve(noise,np.ones(13,dtype=np.float32)/13,mode='same')
        hat=(noise-low)*np.exp(-t*85)*(1-np.exp(-t*1500))
        add(hat,start+k*BEAT*.5,.011*section,(-.32 if k else .32))

# Short bright sweeps accent chapter changes and the labeled accelerated interval.
for at in (0,186.3,251.3,303.1):
    t=np.arange(round(2.5*SR),dtype=np.float32)/SR
    noise=rng.standard_normal(len(t)).astype(np.float32)
    filtered=np.convolve(noise,np.ones(97,dtype=np.float32)/97,mode='same')
    envelope=np.sin(np.pi*t/2.5)**2
    add(filtered*envelope,at,.022,.45)

t=np.arange(len(audio),dtype=np.float32)/SR
master=np.minimum(t/3,1)*np.minimum(np.maximum(DURATION-t,0)/8,1)
audio*=master[:,None]
peak=float(np.max(np.abs(audio)));audio*=.65/max(peak,1e-6)
pcm=(np.clip(audio,-1,1)*32767).astype('<i2')
p=OUT/'original-tech-upbeat.wav'
with wave.open(str(p),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes(pcm.tobytes())
receipt={'title':'Bright Circuit','composition':'Original upbeat, bright futuristic electronic score with buoyant synth plucks, a crisp dance-pop beat, warm bass and bright chord stabs','bpm':BPM,'sample_rate':SR,'seconds':DURATION,'channels':2,'oscillators_and_seeded_noise':True,'third_party_audio_samples':False,'path':str(p),'seed':210013}
(OUT/'music.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt),flush=True)
