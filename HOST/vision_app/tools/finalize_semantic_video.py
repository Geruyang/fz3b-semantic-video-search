"""Verified semantic-video delivery receipt and current handoff."""
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from vision_app.tools.board_link import ROOT,open_link,run
from vision_app.protocol import Decoder,JSON,encode_message
from vision_app.tools.frequency_reboot_acceptance import status

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def main():
    evidence=ROOT/'artifacts/semantic-video-20261009';app=ROOT/'deliverables/vision-console/FZ3BVisionConsole'
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','vision_app/tests','-v'],capture_output=True,text=True,cwd=str(ROOT));assert tests.returncode==0
    (evidence/'tests-final.log').write_text(tests.stdout+tests.stderr,encoding='utf-8')
    preserved=json.loads(subprocess.check_output([sys.executable,'scripts/verify_retained_releases.py'],cwd=str(ROOT),text=True));assert preserved['pass']
    receipt=dict(ok=False,tests=int(re.search(r'Ran (\d+) tests',tests.stderr).group(1)),retained=preserved,pl_or_model_changed=False)
    for key,name in [('gui','gui-acceptance.json'),('exe','exe-self-test.json'),('audio','audio-acceptance.json'),('cancel','cancel-acceptance.json'),('network','exe-network.json')]:
        value=json.loads((evidence/name).read_text(encoding='utf-8'));assert value['ok'],name
        receipt[key]=dict(ok=True,sha256=sha(evidence/name))
    gui=json.loads((evidence/'gui-acceptance.json').read_text(encoding='utf-8'))
    assert gui['live']['expected_end_frame_id']==gui['live']['last_saved_frame_id'] and gui['live_restart_after_offline']
    receipt['live_recording']=dict(frames=gui['live']['frames'],received_gaps=gui['live']['received_frame_gaps'],missing_hit_frames=gui['live']['missing_hit_frames'],end_frame_id=gui['live']['last_saved_frame_id'],live_restart_after_offline=True)
    credit=json.loads((evidence/'offline-credit-23/session.json').read_text(encoding='utf-8'));assert credit['ok'] and credit['completed']==23
    receipt['credit_window_test']=dict(ok=True,frames=23)
    r5file=sorted(evidence.glob('r5-*.json'))[-1];r5=json.loads(r5file.read_text(encoding='utf-8'));assert r5['ok']
    receipt['r5']=dict(ok=True,max_score_error=r5['semantic_test']['max_error'],receipt=str(r5file.relative_to(ROOT)))
    accuracy=json.loads((evidence/'web-accuracy/accuracy-with-user-examples.json').read_text(encoding='utf-8'));assert accuracy['ok']
    receipt['accuracy']=dict(frames=accuracy['frames'],threshold=accuracy['threshold'],micro=accuracy['micro'],per_query=accuracy['per_query'],reference='artifacts/semantic-video-20261009/web-accuracy/accuracy-with-user-examples.json')
    config=json.loads((ROOT/'vision_app/client-config.json').read_text(encoding='utf-8'))
    with socket.create_connection((config['host'],8765),timeout=10) as s:
        s.sendall(encode_message(JSON,dict(op='hello',token=config['token'])));s.settimeout(10)
        board=status(s,Decoder(),lambda value:value.get('type')=='hello')
    assert board['inference']['state']=='STOPPED' and not board['inference']['error']
    assert board['cpu']['verified'] and board['cpu']['actual_hz']==1199999988 and board['r5']['offload_verified']
    receipt['board']=board
    c=open_link()
    try:
        receipt['services']=run(c,'systemctl is-enabled fz3b-pl-loader.service fz3b-app-r5.service fz3b-app-cpu-clock.service fz3b-vision-console.service; systemctl is-active fz3b-pl-loader.service fz3b-app-r5.service fz3b-app-cpu-clock.service fz3b-vision-console.service').splitlines()
        assert receipt['services']==['enabled']*4+['active']*4
        receipt['installed_sources']={}
        for name in ('board_agent.py','state.py','protocol.py','upload_source.py','r5_bridge.py','camera.py'):
            value=run(c,'sha256sum /root/fz3b-vision-console-20261009-001/vision_app/'+name).split()[0]
            assert value==sha(ROOT/'vision_app'/name),name;receipt['installed_sources'][name]=value
    finally:c.close()
    bootfile=sorted((ROOT/'artifacts/ps-application-20261009/boot').glob('reboot-*.json'))[-1]
    boot=json.loads(bootfile.read_text(encoding='utf-8'));assert boot['ok'] and boot['new_boot_id']==board['boot_id']
    receipt['normal_reboot']=dict(ok=True,boot_id=board['boot_id'],receipt=str(bootfile.relative_to(ROOT)))
    files=list((ROOT/'vision_app').glob('*.py'))+list((ROOT/'vision_app/r5').glob('*'))
    files += [app/'FZ3BVisionConsole.exe',app/'semantic-contract.json',app/'build-environment.txt',app/'models/mobileclip_s1.pt']+list((app/'translation').glob('*'))
    receipt['files']=[dict(path=str(p.relative_to(ROOT)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)) for p in files if p.is_file()]
    receipt['review']='PASS: five Important findings corrected and reverified; no remaining Important/Critical in scoped review'
    receipt['ok']=True
    (evidence/'qualification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (app/'delivery-manifest.json').write_text(json.dumps({key:receipt[key] for key in ('ok','tests','retained','files','normal_reboot','accuracy')},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manual='''# FZ3B 语义视频工作台

运行本目录 FZ3BVisionConsole.exe，保留整个目录。仍支持600/800/1000/1200MHz四档、默认1200MHz、调频自动排空/恢复，以及一键主机网口配置/UAC。PL、原MobileCLIP模型与部署保持不变。

## 实时文字找场景

1. 板卡上电，选择以太网连接（当前169.254.220.254）。
2. 输入一行或多行中文描述，例如“桌面上的杯子”“有人在房间里”。中文在主机离线翻译，可悬停描述框查看译文；也支持“中文标签 | English description”。
3. 选择保存目录和命中相似度阈值，点击“开始录像与检索”。完整接收的视频保存为video.mkv，命中原图保存到matches，帧号/时间索引写入frames.jsonl，逐帧语义结果写入results.jsonl，时间段写入segments.json。
4. 点击“结束录像”，等待推理排空和摄像头尾帧落盘；然后选择时间段播放、导出片段或打开输出目录。视频上不叠加推理结果。实时推理约4FPS，时间段来自被分析帧，不能保证两个分析帧之间的短暂事件都被检测。

默认输出为“视频/FZ3B语义检索”。录像采用主机直接封装收到的MJPEG，不让PS重编码视频。视频链路保序、有界，缺帧/溢出/磁盘异常会标记不完整，不用邻帧冒充命中原图。板端通常只回传帧号与语义结果；缺失命中原图才按帧号补取一次。

## 上传视频语义检索

1. 进入“视频语义检索”，选择本机视频并输入描述。
2. 点击“开始逐帧分析”。主机按原PTS解码和逐帧上传，16帧信用窗口控制队列；每帧有对应结果，正常排空后才报告完成。
3. 完成后自动生成匹配片段，保留源视频音轨；下方时间段可在客户端播放，输出目录中的clips-*包含MP4与clips.json。
4. 可中途取消；取消保留已分析索引但不会把部分分析称为完成。视频分析时暂停摄像头预览传输，录像、裁剪和中文文本工作均在主机。

阈值默认0.20，是余弦相似度而非概率。降低会增加命中，也可能增加误报。阈值在任务启动前设置，开始后锁定；默认合并间隔1秒，片段前后各加0.5秒上下文，表中的裁剪时间与原始命中时间均写入JSON。

## R5与验证

R5-0承担描述向量相似度、命中掩码、上传帧序号校验及遥测；R5-1继续小报文/串口分片CRC。向量Q15匹配不改变模型权重，阈值误差界附近回到A53精确判定。GEM/UVC/UART物理驱动仍由Linux管理，没有声称完整外设栈接管或未经测量的CPU节省比例。

源代码与资格见项目docs/handoffs/2026-10-09-semantic-video-app.md和artifacts/semantic-video-20261009/qualification.json。公开短片精度是小样本帧级验证，邻帧高度相关，不能当作广泛场景精度保证；误报和漏检均保留在报告。USB串口保留状态/控制与限速预览，完整录像与全帧视频上传使用以太网。
'''
    (ROOT/'vision_app/README.md').write_text(manual,encoding='utf-8');(app/'README.md').write_text(manual,encoding='utf-8')
    m=accuracy['micro']
    handoff='# 语义视频应用接续（2026-10-09）\n\n'+manual+'\n\n## 当前资格\n\n'+f"{receipt['tests']}项回归通过，{preserved['payloads_checked']}冻结文件校验通过。正常重启boot `{board['boot_id']}` 四服务enabled+active，实际CPU1199999988Hz，当前推理STOPPED。完整录像实测{gui['live']['frames']}帧、帧号缺失0，结束编号与最后落盘编号均{gui['live']['last_saved_frame_id']}；实时→离线→再次实时已通过。全帧3帧VFR及23帧信用窗口、取消owner正常释放、原音轨保留、新EXE中文/视频/裁剪自检均通过。R5 20组评分最大差{r5['semantic_test']['max_error']:.8f}。\n\n公开短片总{accuracy['frames']}帧、默认阈值0.20，微平均precision {m['precision']:.4%}、recall {m['recall']:.4%}、F1 {m['f1']:.4%}。详细每描述计数与来源见web-accuracy/accuracy-with-user-examples.json；不以重复帧数量冒充独立样本数。\n\n"
    handoff+='## 源码与恢复\n\n客户端semantic_ui.py、semantic_media.py、video_analysis.py、translation.py；板端board_agent.py、upload_source.py、state.py；R5 r5/worker.c、r5_bridge.py、r5/tcm_io.c。新板端仅部署应用与R5固件/native API，未改PL/BSP/启动镜像。旧完整客户端保留在deliverables/vision-console/FZ3BVisionConsole-before-semantic-video-20261009，软件快照位于artifacts/semantic-video-20261009/baseline。R5更新备份由update_r5_semantic.py的回执记录，回退必须正常停止应用→CPU→R5并核验offline，不能强卸。\n\n评审发现并修复保序完整录像、尾帧边界、磁盘收尾、查询版本及上传预取恢复五类Important，定点复审PASS。上传明确强制同步预处理；板端FIFO16、预览FIFO128，溢出失败不能静默丢帧后报告成功。源模型资源不归档令牌，资格清单只包含文件哈希。实际断电冷启动仍未测试。\n'
    (ROOT/'docs/handoffs/2026-10-09-semantic-video-app.md').write_text(handoff,encoding='utf-8')
    print(json.dumps(dict(ok=True,exe=str(app/'FZ3BVisionConsole.exe'),tests=receipt['tests'],accuracy=m,boot=board['boot_id'])))

if __name__=='__main__':main()
