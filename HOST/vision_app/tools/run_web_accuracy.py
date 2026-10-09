"""Pre-registered frame labels; unchanged board inference on public videos."""
import hashlib
import json
from pathlib import Path
import time
from vision_app.tools.board_link import ROOT
from vision_app.text_encoder import TextEncoder,parse_prompts
from vision_app.contract import load_contract
from vision_app.video_analysis import analyze_video
from vision_app.semantic_media import export_segments

def main():
    root=ROOT/'artifacts/semantic-video-20261009/web-accuracy'
    descriptions='\n'.join(['茶壶图案 | a picture of an ornate teapot','人物在射箭 | a photo of people practicing archery','户外运动场 | a photo of an outdoor sports field','桌面上的杯子 | a photo of a cup on a desk','有人在房间里 | a photo of a person in a room','跑动的狗 | a photo of a running dog','行驶的汽车 | a photo of a car driving on a road'])
    items=parse_prompts(descriptions)
    labels={'schema':'pre-registered-visual-reference-v1','threshold':.2,'prepared_before_inference':True,'annotation':'visual review of 12-frame contact sheets and all final 24 teapot fade frames; correlated frames, not an independent dataset',
       'teapot.webm':{'frames':174,'positive_query_ids':{'0':[[0,170]]},'ignore_query_frames':{'0':[171,172]},'source':'https://commons.wikimedia.org/wiki/File:Amauta_ciriachi_-_Teapot_stop_motion.webm','author':'amauta ciriachi','license':'https://creativecommons.org/licenses/by/3.0/'},
       'archery.mp4':{'frames':300,'positive_query_ids':{'1':[[0,299]],'2':[[0,299]]},'ignore_query_frames':{},'source':'https://huggingface.co/datasets/nateraw/video-demo/blob/main/archery.mp4','use':'local validation only, not bundled in executable'},'items':items}
    (root/'pre-registered-labels.json').write_text(json.dumps(labels,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    config=json.loads((ROOT/'vision_app/client-config.json').read_text(encoding='utf-8'))
    encoder=TextEncoder(load_contract(str(ROOT/'vision_app/semantic-contract.json')),config['model_root']);features,identity=encoder.encode(items)
    reports={};totals=dict(tp=0,fp=0,fn=0,tn=0);per_query={item['id']:dict(label=item['label'],tp=0,fp=0,fn=0,tn=0) for item in items}
    for name in ('teapot.webm','archery.mp4'):
        target=root/(name.split('.')[0]+'-board-results')
        result=analyze_video(root/name,config['host'],config['token'],items,features,identity,target,threshold=.2)
        assert result['ok'] and result['completed']==labels[name]['frames']
        rows=[json.loads(line) for line in (target/'results.jsonl').read_text(encoding='utf-8').splitlines()]
        counts=dict(tp=0,fp=0,fn=0,tn=0);examples=[]
        for row in rows:
            fid=row['frame_id']
            for entry in row['ranking']:
                key=entry['id']
                if fid in labels[name]['ignore_query_frames'].get(key,[]):continue
                actual=any(a<=fid<=b for a,b in labels[name]['positive_query_ids'].get(key,[]))
                predicted=entry['score']>=.2
                category='tp' if actual and predicted else 'fp' if predicted else 'fn' if actual else 'tn'
                counts[category]+=1;totals[category]+=1;per_query[key][category]+=1
                if category in ('fp','fn') and len(examples)<30:examples.append(dict(frame_id=fid,time_s=row['time_s'],query=entry['label'],score=entry['score'],kind=category))
        clips=export_segments(root/name,result['segments'],target/'clips')
        reports[name]=dict(frames=result['completed'],elapsed_s=result['elapsed_s'],counts=counts,segments=result['segments'],clips=len(clips),errors_sample=examples,sha256=hashlib.sha256((root/name).read_bytes()).hexdigest())
        print(json.dumps(dict(video=name,frames=result['completed'],counts=counts,clips=len(clips)),ensure_ascii=False),flush=True)
    def metrics(x):
        tp,fp,fn,tn=(x[k] for k in ('tp','fp','fn','tn'))
        return dict(precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,accuracy=(tp+tn)/(tp+fp+fn+tn))
    output=dict(ok=True,threshold=.2,frames=474,decision_counts=totals,micro=metrics(totals),per_query={key:dict(value,**metrics(value)) for key,value in per_query.items()},videos=reports,limitations=['Two short videos; adjacent frames highly correlated.', 'Reference annotations are visual review, not a benchmark dataset.', 'Teapot is a paper picture; this tests visual semantic matching, not physical object detection.', 'Default threshold retained at 0.20; no tuning using these results.'])
    (root/'accuracy.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(ok=True,frames=474,counts=totals,metrics=output['micro']),ensure_ascii=False))

if __name__=='__main__':main()
