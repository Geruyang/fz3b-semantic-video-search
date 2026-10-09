"""Promote latest measured result while preserving historical prose verbatim."""
import json
from vision_app.tools.board_link import ROOT

def main():
    base=ROOT/'artifacts/ps-application-20261009'
    report=json.loads((base/'performance-comparison.json').read_text(encoding='utf-8'))
    live,fixed=report['final_camera'],report['final_fixed']
    qualification=json.loads((base/'qualification.json').read_text(encoding='utf-8'))
    boot_id=qualification['board']['boot_id']
    tests=qualification['tests_count']
    summary=(f"CPU已通过官方PM parent/divider与原始寄存器确认实际1199999988Hz，默认1.2GHz。"
             f"正常重启boot `{boot_id}`，loader/R5/CPU/应用四服务enabled+active。"
             f"最终固定200张 `{fixed['fps']:.6f} FPS`；实时{live['elapsed_s']:.3f}秒窗口"
             f"{live['frames']}条结果，交付区间 `{live['fps']:.6f} FPS`，年龄p50/p95 "
             f"{live['age_p50_ms']/1000:.3f}/{live['age_p95_ms']/1000:.3f}秒，预览{live['preview_fps']:.3f}FPS，错误和队列丢弃0。"
             f"现采用逐元素等价的少拷贝同步预处理；PL/模型/量化和部署负载未变。{tests}项应用回归通过。"
             "客户端600/800/1000/1200MHz四档及一键UAC已实现；四档实频、跨档恢复和R5白名单均已上板验证。")
    archive=base/'docs-before-performance-recovery'
    archive.mkdir(exist_ok=True)
    names=['vision_app/README.md','docs/analysis/2026-10-09-vision-console-final-speed.md',
           'docs/handoffs/2026-10-09-vision-console-application.md','docs/handoffs/2026-10-09-vision-console-autostart.md']
    for name in names:
        p=ROOT/name
        old=p.read_text(encoding='utf-8')
        target=archive/p.name
        if not target.exists():target.write_text(old,encoding='utf-8')
        if name.endswith('README.md'):
            if old.startswith(('> 频率证据更正','> 最新性能与实频更正')):old=old.split('\n\n',1)[1]
            old=old.replace('用户随后明确要求CPU默认1.2GHz：应用启动在推理前经R5-0校验，写入并读回内核枚举1199999 kHz。新boot `fc5ec6ca-b2a3-446d-9497-cd962af5d5da` 已验证该默认值。',
                '用户要求CPU默认1.2GHz：专用CPU服务在实际A0005/R5初始化完成后，通过官方PM接口仅控制ACPU mux/divider；应用启动经R5-0验证白名单并用PM/raw回读实频。scaling_cur_freq和CCF值只作为缓存诊断，不能用来验证实频。')
            old=old.replace('并执行共享 cpufreq 写入。','并由专用CPU服务执行PM mux/divider控制。')
            old=old.replace('最终 33 项回归通过',f'最终 {tests} 项回归通过')
            old=old.replace('最终 51 项回归通过',f'最终 {tests} 项回归通过')
            old=old.replace('停止推理并等待 STOPPED 后可设置 A53 共享频率或在途对数；阈值可在运行中设置。',
                '频率选择600/800/1000/1200MHz四档、默认1200；设置频率自动停止/排空推理、硬件核验后恢复，失败保持停止，用户停止可取消恢复。改变在途对数仍需先停止；阈值可运行中设置。')
            old=old.replace('确认变更后由独立助手请求UAC；主界面保持普通权限。',
                '选择网口/地址后点“一键配置直连网口”直接由独立助手请求UAC；主界面保持普通权限。DHCP/恢复另有确认。')
            old=old.replace('频率输入600–1200MHz、1MHz步进、默认1200；设置频率会自动停止/排空推理、硬件核验后恢复，失败保持停止，用户停止可取消恢复。当前中间档受PMU权限限制，界面步进不代表599个中间档已上板。',
                '频率选择600/800/1000/1200MHz四档、默认1200；设置频率自动停止/排空推理、硬件核验后恢复，失败保持停止，用户停止可取消恢复。')
            lines=[]
            for line in old.splitlines():
                if line.startswith(('- 调频经 R5-0 校验后实际写入/读回','- 新R5白名单')):
                    line='- 新R5白名单接受600/800/1000/1200MHz四档并保留端点别名；四档实频、9次跨档切换和关闭16项raw精确恢复均通过。运行推理自动停止/恢复及同连接停止取消恢复实测通过。恢复失败报告并quarantine，禁止force卸载。'
                if line.startswith(('- 用户要求的最后测速在1.2GHz执行：','- CPU已通过官方PM')):
                    line='- '+summary+' 详见 `docs/analysis/2026-10-09-vision-console-performance-recovery.md`。'
                if line.startswith('停用本轮自启（保留 A0005 loader）'):
                    line=line.replace('fz3b-vision-console.service fz3b-app-r5.service','fz3b-vision-console.service fz3b-app-cpu-clock.service fz3b-app-r5.service')
                if line.startswith('用户随后明确要求CPU默认1.2GHz：'):
                    line='CPU服务默认请求1200000kHz（保留1199999别名），以PM parent/divider和raw计算actual_hz确认1199999988Hz；sysfs/CCF缓存仅诊断。每次服务启动恢复默认1.2GHz。'
                lines.append(line)
            old='\n'.join(lines)+'\n'
            p.write_text('> 最新性能与实频更正：'+summary+' 原4.06694/3.67490 FPS属于事后硬件审计的约1.0667GHz，原sysfs-only频率结论已归档更正。\n\n'+old,encoding='utf-8')
        elif name.endswith('final-speed.md'):
            p.write_text('# 最后一次板端测速（真实默认1.2GHz）\n\n'+summary+
              '\n\n详见 [性能恢复分析](2026-10-09-vision-console-performance-recovery.md) 和 `artifacts/ps-application-20261009/performance-comparison.json`。'
              '\n\n固定输入复用原benchmark，预热3对，测量100对/200张，含填排和结果收集，排除模型加载、JPEG/预处理、特征校验；实时FPS是第一条至最后一条结果的交付区间，含启动整窗另见原始JSON。二者口径不可混用。'
              '\n\n原4.06694/3.67490 FPS的“CPU1.2GHz”标记是sysfs缓存误判，事后ACPU raw审计仍为APLL/div1、1066666656Hz；旧原始JSON和旧本文在artifacts中留存，见frequency-audit-correction.json。当前实际频率以PM/raw为准。\n',encoding='utf-8')
        else:
            # These handoffs retain early manual/boot history. Explicitly mark it
            # historical and make the current, independently verified entry first.
            note=('> 当前接续（性能恢复后）：'+summary+'\n> CPU服务 `fz3b-app-cpu-clock.service` 等待loader实际READY和双R5本boot资格后才开始，Type=notify完成后应用启动。'
                  '调频和停止通过该专用owner正常生命周期；不要按旧sysfs读回结论操作。'
                  '默认少拷贝同步预处理 `preprocess_async=false`，停止推理后正常排空，CPU默认继续1.2GHz。\n'
                  '> 最新说明见 [性能恢复分析](../analysis/2026-10-09-vision-console-performance-recovery.md) 与qualification.json。以下较早记录按历史阅读，其中仅以sysfs确认1.2GHz的结论已被硬件审计更正。\n\n')
            if old.startswith('> 当前接续（性能恢复后）'):
                old=old.split('\n\n',1)[1]
            p.write_text(note+old,encoding='utf-8')
    destination=ROOT/'deliverables/vision-console/FZ3BVisionConsole'
    (destination/'README.md').write_text((ROOT/'vision_app/README.md').read_text(encoding='utf-8'),encoding='utf-8')
    print(json.dumps(dict(ok=True,camera_fps=live['fps'],fixed_fps=fixed['fps'],tests=tests)))

if __name__=='__main__':main()
