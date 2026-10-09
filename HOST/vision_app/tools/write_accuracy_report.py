"""Human-readable accuracy report; preserve fixed-threshold baseline."""
import json
from vision_app.tools.board_link import ROOT

def main():
    folder=ROOT/'artifacts/semantic-video-20261009/web-accuracy'
    value=json.loads((folder/'accuracy-with-user-examples.json').read_text(encoding='utf-8'))
    lines=['# 公开短视频精度实测（2026-10-09）','',
        '四段短视频共725帧，通过客户端同一逐帧上传路径在FZ3B/A0005实板推理，CPU实际1.2GHz，原MobileCLIP模型、量化、PL均保持不变。阈值固定0.20，在看对应视频推理分数前保存视觉参考标注。茶壶末尾171/172两帧太暗，仅茶壶描述的这两项决策排除；其余保留。',
        '', '结果应同时看精确率和召回率。这里精确率100%只表示本小样本没有记录误报，不表示所有场景整体准确率100%。相邻帧高度相关，725帧不能视作725个独立场景。', '',
        '| 指标 | 实测 |','|---|---:|',
        f"|精确率 Precision|{value['micro']['precision']:.2%}|",f"|召回率 Recall|{value['micro']['recall']:.2%}|",f"|F1|{value['micro']['f1']:.2%}|",'|TP / FP / FN / TN|558 / 0 / 464 / 4051|','',
        '| 描述 | 真实正例帧 | 命中 | 漏检 | 召回率 |','|---|---:|---:|---:|---:|']
    for key in ('0','1','2','3','4'):
        row=value['per_query'][key];lines.append('|%s|%d|%d|%d|%.2f%%|'%(row['label'],row['tp']+row['fn'],row['tp'],row['fn'],row['recall']*100))
    lines+=['','“跑动的狗”“行驶的汽车”为负例控制，本组没有命中；不能据此估计它们的正例召回率。','',
        '杯子在咖啡短片中全程可见，但分数范围0.1762–0.2100，固定0.20阈值导致44/131帧漏检。室内人物子片段分数0.0846–0.1881，0.20下全漏；部分画面聚焦餐盘/手臂，属于整帧语义匹配的困难构图。户外运动场描述在射箭片段中也全漏，而“人物在射箭”全部命中。这表明描述用词、构图和阈值显著影响结果，不能用帧传输正确冒充语义准确。','',
        '本文“杯子”参考类按当前英文cup描述指茶杯/马克杯，不把室内餐桌的高脚酒杯归为该类；中文泛称杯子如果包括酒杯，需要另行定义目标描述与标注。对是否“在房间里”的参考，是按视觉可见人/躯干/手臂及室内餐饮背景标注，未要求每帧有完整人脸。','',
        '## 视频来源与范围','',
        '- 茶壶图案：amauta ciriachi，[Teapot stop motion](https://commons.wikimedia.org/wiki/File:Amauta_ciriachi_-_Teapot_stop_motion.webm)，CC BY 3.0；完整174帧、7秒。图案是剪纸/插画，不是实物茶壶。',
        '- 射箭：[nateraw/video-demo公开示例](https://huggingface.co/datasets/nateraw/video-demo/blob/main/archery.mp4)，完整300帧、约10秒；只在本地验证，不随EXE分发。',
        '- 杯子：Queen Asali，[A cup of Kenyan Coffee](https://commons.wikimedia.org/wiki/File:A_cup_of_Kenyan_Coffee.webm)，CC BY-SA 4.0；完整131帧、约4.3秒。原视频未改帧率或画面。',
        '- 室内人物：[nielsr/video-demo eating_spaghetti](https://huggingface.co/datasets/nielsr/video-demo/blob/main/eating_spaghetti.mp4)，取原片6–10秒，120帧，30FPS保持；仅精确裁剪重编码以控制测试时长。官方测试示例说明见[HF spaghetti-video](https://huggingface.co/datasets/hf-internal-testing/spaghetti-video)。仅本地验证。','',
        '完整下载文件、SHA256、源时间与预标注位于artifacts/semantic-video-20261009/web-accuracy。视频源未放入客户端交付目录。每段的results.jsonl、命中原图和clips包含真实板端结果，accuracy-with-user-examples.json记录全部计数与分数范围。','',
        '## 阈值探索（缓存回放，非独立验证）','',
        '|阈值|精确率|召回率|误报帧决策|','|---:|---:|---:|---:|']
    counts={.12:(969,327,53),.14:(935,136,87),.15:(921,65,101),.16:(914,19,108),.17:(908,8,114),.18:(832,2,190),.19:(673,0,349),.20:(558,0,464)}
    for threshold,(tp,fp,fn) in counts.items():lines.append('|%.2f|%.2f%%|%.2f%%|%d|'%(threshold,tp/(tp+fp)*100,tp/(tp+fn)*100,fp))
    lines+=['','该表用已保存R5分数回放，分数在0.20边界附近做过A53精确校验，其他新阈值边界尚未重新实板校验；用于探索趋势。降低阈值改善召回也带来误报，不能把在这些样本上挑选阈值后的成绩当独立测试成绩。本轮保持客户端默认0.20，用户可在开始任务前调整。没有修改或重新优化模型。','']
    text='\n'.join(lines)
    (ROOT/'docs/analysis/2026-10-09-semantic-video-accuracy.md').write_text(text,encoding='utf-8')
    app=ROOT/'deliverables/vision-console/FZ3BVisionConsole'
    (app/'ACCURACY.md').write_text(text,encoding='utf-8')
    for name,credit in [('teapot','amauta ciriachi — CC BY 3.0 — https://commons.wikimedia.org/wiki/File:Amauta_ciriachi_-_Teapot_stop_motion.webm'),('coffee','Queen Asali — CC BY-SA 4.0 — https://commons.wikimedia.org/wiki/File:A_cup_of_Kenyan_Coffee.webm')]:
        (folder/(name+'-board-results')/'ATTRIBUTION.txt').write_text(credit+'\nClips are time-trimmed, re-encoded derivatives for local validation; preserve attribution and applicable license.\n',encoding='utf-8')
    print(json.dumps(dict(ok=True,frames=725,precision=value['micro']['precision'],recall=value['micro']['recall'])))

if __name__=='__main__':main()
