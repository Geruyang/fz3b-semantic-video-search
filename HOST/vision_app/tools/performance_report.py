"""Extract measured stage comparisons and document verified CPU evidence."""
import json
from pathlib import Path
import statistics
import numpy as np
from vision_app.tools.board_link import ROOT

BASE=ROOT/'artifacts/ps-application-20261009'

def fixed(path, actual_hz):
    value=json.loads(path.read_text(encoding='utf-8'))
    measured=value['measured']
    summary=measured['runtime_summary']
    stages={}
    for pair in summary['pair_timings']:
        for event in pair['ps_events']:
            stages.setdefault(event['partition'],[]).append(event['call_wall_ms'])
    return dict(path=str(path.relative_to(ROOT)).replace('\\','/'), actual_hz=actual_hz,
                fps=measured['fps_including_fill_and_drain'],frames=measured['real_frames'],
                execution_s=measured['execution_ms']/1000,
                stages_ms={k:statistics.mean(v) for k,v in stages.items()},
                owners_ms_per_frame={k:summary[k]/measured['real_frames'] for k in
                    ('ps_front_worker_busy_ms','ps_suffix_worker_busy_ms','pl_worker_busy_ms')},
                quality_pass=measured['feature_protocol_pass'], cleanup=value['cleanup'])

def live(path):
    value=json.loads(path.read_text(encoding='utf-8'))
    status=value['last_board_status']
    ages=[e['message']['result_age_ms'] for e in value['events'] if e['message'].get('type')=='result'][:value['inference_results_received']]
    return dict(path=str(path.relative_to(ROOT)).replace('\\','/'),fps=value['inference_result_interval_fps'],
                frames=value['inference_results_received'],elapsed_s=value['elapsed_s'],
                actual_hz=status['cpu'].get('actual_hz',1066666656),
                async_preprocess=status['inference'].get('preprocess_async',False),
                preview_fps=value['preview_received_fps'],age_p50_ms=value['result_age_p50_ms'],
                age_p95_ms=float(np.percentile(ages,95)),
                stages=status['inference'].get('performance',{}),
                errors=value['errors'],delivery_drops=status['result_delivery_drops'],
                cpu=status['cpu'],boot_id=status['boot_id'])

def main():
    old=fixed(BASE/'speed-1p2-20261009T080850Z/result.json',1066666656)
    last=fixed(sorted(BASE.glob('speed-1p2-*/result.json'))[-1],1199999988)
    original=live(BASE/'live-smoke-20261009T161328/evidence.json')
    sync=live(BASE/'live-smoke-20261009T165323/evidence.json')
    async_first=live(BASE/'live-smoke-20261009T165806/evidence.json')
    async_long=live(BASE/'live-smoke-20261009T171622/evidence.json')
    baseline=live(BASE/'live-smoke-20261009T170101/evidence.json')
    final=live(sorted(BASE.glob('live-smoke-*/evidence.json'))[-1])
    assert final['cpu']['verified'] and final['actual_hz']==1199999988
    assert not final['errors'] and final['delivery_drops']==0
    report=dict(original_fixed=old,original_camera=original,matched_baseline=baseline,
                verified_1p2_sync=sync,verified_1p2_async_first=async_first,verified_1p2_async_long=async_long,
                final_fixed=last,final_camera=final,
                original_effective_ms_per_frame=dict(fixed=1000/old['fps'],camera=1000/original['fps']),
                final_gain_percent=(final['fps']/original['fps']-1)*100,
                notes=['Fixed resident tensor benchmark excludes JPEG/resize/camera/network.',
                       'Stage wall times overlap; cannot add them to obtain reciprocal FPS.',
                       'CPU parent/divider verified via PM and raw; sysfs/CCF cache is diagnostic only.',
                       'Video forwards native camera MJPEG independent of inference selection.',
                       'Selected synchronous copy-reduced preprocessing is pixel-identical (31/31 board cases).',
                       'First short async window is not the final result; long-window CPU contention was worse.'])
    (BASE/'performance-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    stage=lambda run,key:run['stages'][key]['mean_ms']
    text=f'''# 实时推理从3.67 FPS恢复的分析与结果

日期2026-10-09（Asia/Shanghai）。复用V10.5/A0005，保持PL位流、设计、时钟配置、模型、量化、部署负载和PS分区线程配置。只修改PS应用调度及CPU频率控制。

## 结论和计时口径

最初4.06694 FPS是驻留固定tensor到feature的吞吐，3.67490 FPS是摄像头完整应用的结果交付区间吞吐。前者排除JPEG解码、resize/crop/张量准备、语义匹配和网络回传；后者承受这些新增工作及CPU竞争。折算每帧有效时间为{1000/old['fps']:.3f}ms与{1000/original['fps']:.3f}ms，差{1000/original['fps']-1000/old['fps']:.3f}ms，吞吐下降{(1-original['fps']/old['fps'])*100:.2f}%。流水线各阶段并行，不能把原始阶段耗时直接相加。

真实1.2GHz加少拷贝同步预处理后，最终{final['elapsed_s']:.3f}秒窗口收到{final['frames']}条结果，交付区间 **{final['fps']:.6f} FPS**，较原3.67490 FPS提升 **{report['final_gain_percent']:.2f}%**，距原固定输入4.06694 FPS约{abs(final['fps']/old['fps']-1)*100:.2f}%。最后固定200张输入为 **{last['fps']:.6f} FPS / {last['execution_s']:.3f}秒**，通过原数值/协议及正常close/quiesce工程门。

| 场景 | 实际CPU | 推理结果FPS | 结果年龄p50 |
|---|---:|---:|---:|
| 原固定tensor benchmark | 1.0667GHz | {old['fps']:.6f} | — |
| 原实时相机应用 | 1.0667GHz，事后raw审计更正 | {original['fps']:.6f} | {original['age_p50_ms']/1000:.3f}s |
| 相同相机重新对照，同步预处理 | 1.0667GHz，PM/raw确认 | {baseline['fps']:.6f} | {baseline['age_p50_ms']/1000:.3f}s |
| 仅修正实频，同步预处理 | 1.2GHz，PM/raw确认 | {sync['fps']:.6f} | {sync['age_p50_ms']/1000:.3f}s |
| 两槽异步预处理首轮90秒 | 1.2GHz，PM/raw确认 | {async_first['fps']:.6f} | {async_first['age_p50_ms']/1000:.3f}s |
| 两槽异步预处理180秒 | 1.2GHz，PM/raw确认 | {async_long['fps']:.6f} | {async_long['age_p50_ms']/1000:.3f}s |
| 最终少拷贝同步预处理180秒 | 1.2GHz，PM/raw确认 | {final['fps']:.6f} | {final['age_p50_ms']/1000:.3f}s |
| 最终固定tensor benchmark | 1.2GHz，PM/raw确认 | {last['fps']:.6f} | — |

## 哪里慢了

以下为每张图像的平均wall耗时。固定tensor的PS阶段取原benchmark原始pair_timing，实时阶段取应用内有界统计。场景输入与缓存状态有差异，不能把所有分区差异单独归因于某一因素。

| 工作 | 原固定输入1.0667GHz | 同场景实时对照1.0667GHz | 实频1.2GHz同步 |
|---|---:|---:|---:|
| JPEG解码 | 排除 | {stage(baseline,'jpeg_decode_ms'):.3f}ms | {stage(sync,'jpeg_decode_ms'):.3f}ms |
| 双线性缩放 | 排除 | {stage(baseline,'resize_ms'):.3f}ms | {stage(sync,'resize_ms'):.3f}ms |
| 中心crop/FP32/CHW张量 | 排除 | {stage(baseline,'tensor_ms'):.3f}ms | {stage(sync,'tensor_ms'):.3f}ms |
| 预处理合计 | 排除 | {stage(baseline,'preprocess_ms'):.3f}ms | {stage(sync,'preprocess_ms'):.3f}ms |
| stem-prefix调用 | {old['stages_ms']['stem-prefix']:.3f}ms | {stage(baseline,'stem-prefix_call_ms'):.3f}ms | {stage(sync,'stem-prefix_call_ms'):.3f}ms |
| network3-bridge调用 | {old['stages_ms']['network3-bridge']:.3f}ms | {stage(baseline,'network3-bridge_call_ms'):.3f}ms | {stage(sync,'network3-bridge_call_ms'):.3f}ms |
| suffix调用 | {old['stages_ms']['suffix']:.3f}ms | {stage(baseline,'suffix_call_ms'):.3f}ms | {stage(sync,'suffix_call_ms'):.3f}ms |
| 语义匹配/结果发布 | 固定benchmark未做 | {stage(baseline,'result_postprocess_ms'):.3f}ms | {stage(sync,'result_postprocess_ms'):.3f}ms |
| 等待相机latest帧 | 驻留输入 | {stage(baseline,'input_wait_ms'):.3f}ms | {stage(sync,'input_wait_ms'):.3f}ms |

同步输入生成器在流水线admit/take路径中解码和缩放。等待next(input)期间调度线程不能及时处理已完成owner或提交下一阶段，且这些CPU工作与PS前段/suffix竞争A53。原固定输入后缀约237.5ms/张，实时对照约248.4ms/张；JPEG/缩放占新增应用开销的大部分。相机等待约0.05ms，主机交付与板端result_interval_fps接近，传输无记录错误、结果队列丢弃0，支持主要瓶颈在PS计算和调度的判断。

## 改进与实际频率更正

1. 先前scaling_setspeed/scaling_cur_freq的1199999仅是旧cpufreq缓存；事后ACPU_CTRL=0x03000100、APLL/div1、CCF1066666656Hz。原4.07和3.67两个成绩都应归为实际约1.0667GHz。因此缓存误标是必须修复的默认频率问题，不是二者原始差距的独立原因。旧JSON原文保留，并有frequency-audit-correction.json索引。
2. 默认1.2GHz复用DPLL1199999988Hz，官方PM接口把ACPU parent设2、divider设1；600MHz使用divider2。用户改为四档后，800/1000MHz用固件明确允许的NODE_VPLL=51整数配置，先核验没有其他活动消费者，CPU停留在DPLL/div2期间配置并锁定，再切父并复核后改divider1。模块无MMIO写；APLL/DPLL/DDR/IOPLL/RPLL/PL分支保持原值，关闭独立核验16项raw精确恢复。状态同时保留cached_sysfs_khz与ccf_hz，界面使用actual_hz。
3. 新CPU服务独占root控制socket和模块FD，默认1199999kHz。等待loader真实READY_A0005及双R5当前boot资格后接管，Type=notify就绪后才启动应用。曾记录过早抓基线的启动失败，现已修复；第二次完整正常重启{final['boot_id']}四服务enabled+active，getty停止/启动生命周期正常。
4. 比较了原同步输入与两槽有界异步预取。异步首轮90秒4.118 FPS，但180秒仅{async_long['fps']:.6f} FPS，suffix平均{stage(async_long,'suffix_call_ms'):.3f}ms/张，比同步{stage(sync,'suffix_call_ms'):.3f}ms/张更慢；CPU竞争抵消了调度重叠收益。因此最终采用同步方案，不以短窗4.118作为交付成绩。
5. 仅去掉已是RGB的JPEG解码后整图复制，并将float32除255改为原位运算。Pillow5.1板端31种相机/随机/几何/极值输入逐元素完全相等，单独预处理约69.66→67.42ms。最终应用下预处理平均{stage(final,'preprocess_ms'):.3f}ms、suffix平均{stage(final,'suffix_call_ms'):.3f}ms/张，默认4对在途、前段1线程/suffix3线程和冻结模型均保留。另一种ROI resize候选出现1/255像素差异，已拒绝且未启用。最终年龄p50/p95为{final['age_p50_ms']/1000:.3f}/{final['age_p95_ms']/1000:.3f}s，保留3秒旧结果标记。

客户端预览保持独立，最终实收{final['preview_fps']:.3f}FPS，与该次摄像头实际输出接近；配置请求30FPS不是实测30FPS。未以推理FPS限制视频。结果年龄从应用读取相机JPEG开始，不包含光学曝光时间。

## 证据与接续

机械摘要：`artifacts/ps-application-20261009/performance-comparison.json`。其中记录全部原始路径、stage耗时、CPU实频、boot、数值工程门和清理结果。最终实时原始证据：`{final['path']}`；最终固定输入：`{last['path']}`。CPU短周期、API调频、关闭raw恢复、安装备份和失败启动日志在`artifacts/ps-application-20261009/cpu-clock/`。

Linux3种owner停止顺序为应用→CPU→R5，再到既有loader。CPU close在驱动restore后独立只读核对全部原始寄存器；失败报告service failed并保留quarantine，禁止force卸载。板卡现保留实际1.2GHz默认、相机采集服务、推理STOPPED。主机EXE加入600/800/1000/1200MHz四档选择和“一键配置直连网口”，静态配置点击直接交给独立UAC helper。调频控制先排空推理，核验成功后恢复先前运行状态；同一连接的停止命令可取消恢复。

最终频率需求已由用户改为600/800/1000/1200MHz四档。原APLL细调被PMU拒绝，直接MMIO替代未获批准、没有实施。正式四档采用PMU允许的VPLL/DPLL方案，跨档1200→800→600→1000→1200→800→1000→600→1200全部通过，实频分别599999994/799999992/999999990/1199999988Hz，关闭16项raw精确恢复；R5拒绝601/799/1199等非法档。官方依据pmufw-2018.3/pm_config.c:544–570与UG1085 v2.5表37-1。
'''
    (ROOT/'docs/analysis/2026-10-09-vision-console-performance-recovery.md').write_text(text,encoding='utf-8')
    print(json.dumps(dict(ok=True,final_camera_fps=final['fps'],final_fixed_fps=last['fps'],gain_percent=report['final_gain_percent']),indent=2))

if __name__=='__main__':main()
