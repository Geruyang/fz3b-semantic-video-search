"""User-example positive cases, fixed default threshold, no model changes."""
import hashlib
import json
import subprocess
from pathlib import Path
import av
import imageio_ffmpeg
from vision_app.tools.board_link import ROOT
from vision_app.tools.run_web_accuracy import TextEncoder,load_contract,parse_prompts,analyze_video,export_segments

def main():
    root=ROOT/'artifacts/semantic-video-20261009/web-accuracy'
    source=root/'indoor-person-6-10s.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-ss','6','-i',str(root/'eating_spaghetti.mp4'),'-t','4','-c:v','libx264','-preset','veryfast','-crf','18','-fps_mode','passthrough','-an',str(source)],check=True)
    def count(path):
        with av.open(str(path)) as c:return sum(1 for unused in c.decode(video=0))
    annotation={'prepared_before_inference':True,'threshold':.2,
        'coffee.webm':dict(frames=count(root/'coffee.webm'),positive_query_ids=['3'],source='https://commons.wikimedia.org/wiki/File:A_cup_of_Kenyan_Coffee.webm',author='Queen Asali',license='https://creativecommons.org/licenses/by-sa/4.0/',note='Original complete 4.3s video; cup on cafe table. Desk wording retained as in the application.'),
        'indoor-person-6-10s.mp4':dict(frames=count(source),positive_query_ids=['4'],source='https://huggingface.co/datasets/nielsr/video-demo/blob/main/eating_spaghetti.mp4',reference='https://huggingface.co/datasets/hf-internal-testing/spaghetti-video',note='Original video 6–10s excerpt, unchanged 30FPS; torso/arms/person face visibly in indoor dining setting. Re-encoded for exact trim, used only locally.')}
    (root/'user-example-labels.json').write_text(json.dumps(annotation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    old=json.loads((root/'accuracy.json').read_text(encoding='utf-8'))
    descriptions=json.loads((root/'pre-registered-labels.json').read_text(encoding='utf-8'))['items']
    c=json.loads((ROOT/'vision_app/client-config.json').read_text(encoding='utf-8'))
    features,identity=TextEncoder(load_contract(str(ROOT/'vision_app/semantic-contract.json')),c['model_root']).encode(descriptions)
    for name in ('coffee.webm','indoor-person-6-10s.mp4'):
        path=root/(name.split('.')[0]+'-board-results')
        report=analyze_video(root/name,c['host'],c['token'],descriptions,features,identity,path,threshold=.2)
        assert report['ok'] and report['completed']==annotation[name]['frames']
        rows=[json.loads(row) for row in (path/'results.jsonl').read_text(encoding='utf-8').splitlines()]
        counts=dict(tp=0,fp=0,fn=0,tn=0);ranges={key:[] for key in old['per_query']}
        for row in rows:
            for hit in row['ranking']:
                key=hit['id'];actual=key in annotation[name]['positive_query_ids'];predicted=hit['score']>=.2
                category='tp' if actual and predicted else 'fp' if predicted else 'fn' if actual else 'tn'
                counts[category]+=1;old['decision_counts'][category]+=1;old['per_query'][key][category]+=1;ranges[key].append(hit['score'])
        clips=export_segments(root/name,report['segments'],path/'clips')
        old['videos'][name]=dict(frames=report['completed'],elapsed_s=report['elapsed_s'],counts=counts,segments=report['segments'],clips=len(clips),score_ranges={key:[min(v),max(v)] for key,v in ranges.items()},sha256=hashlib.sha256((root/name).read_bytes()).hexdigest())
        old['frames']+=report['completed'];print(json.dumps(dict(video=name,frames=report['completed'],counts=counts),ensure_ascii=False),flush=True)
    def metrics(x):
        tp,fp,fn,tn=(x[k] for k in ('tp','fp','fn','tn'))
        return dict(precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,accuracy=(tp+tn)/(tp+fp+fn+tn))
    old['micro']=metrics(old['decision_counts'])
    for value in old['per_query'].values():value.update(metrics(value))
    old['limitations']=['Four short clips, adjacent frames highly correlated; not a broad accuracy guarantee.','Visual pre-registration, not a benchmark dataset.','Threshold remains 0.20 with original model/PL unchanged.','Person positive is original6–10s excerpt; 30FPS preserved.','Teapot is a paper illustration, not a physical object.']
    (root/'accuracy-with-user-examples.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(ok=True,frames=old['frames'],counts=old['decision_counts'],metrics=old['micro']),ensure_ascii=False))

if __name__=='__main__':main()
