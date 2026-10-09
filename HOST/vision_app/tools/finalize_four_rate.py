"""Write the current four-rate handoff from independently verified receipts."""
import json
from vision_app.tools.board_link import ROOT

def main():
    base=ROOT/'artifacts/ps-application-20261009'
    q=json.loads((base/'qualification.json').read_text(encoding='utf-8'))
    p=json.loads((base/'performance-comparison.json').read_text(encoding='utf-8'))
    assert q['ok'] and q['frequency_scope']['four_rate_completed']
    exe=next(item for item in q['files'] if item['path'].endswith('FZ3BVisionConsole.exe'))
    fixed,live=p['final_fixed'],p['final_camera']
    text=f'''# FZ3B PS应用最终接续：四档频率

日期2026-10-09。用户将此前600–1200MHz/1MHz步进改为 **600/800/1000/1200MHz四档**；此前直接APLL MMIO方案未批准、未实施。当前四档要求已实现并上板核验。继续复用V10.5/A0005，不改PL、位流、PL时钟、模型、量化或冻结部署资源。

## 使用与交付

运行 `deliverables/vision-console/FZ3BVisionConsole/FZ3BVisionConsole.exe`，保留整个同名目录，含_internal/models。EXE SHA256 `{exe['sha256']}`。当前网口板卡地址169.254.220.254，主机169.254.220.34；原板192.168.1.254也保留。主机无需管理员启动；“主机网口”→“一键配置直连网口”点击后独立请求UAC。静态地址限定所选物理网口、IPv4和ActiveStore，不更改WLAN默认路由。

实时预览按摄像头实际帧率，推理异步叠加对应帧ID、年龄，3秒以上标记过期。支持多描述相似度匹配、预设物品/场景分类、最近60个推理帧的图文检索。每行可写“中文标签 | English description”；常见中文词有映射，任意中文长句自动翻译尚未提供。串口COM6/115200为备用，视频是限速缩略图，不能达到以太网全帧率。

## 四档控制与证据

| 目标MHz | 实际Hz | 方式 |
|---:|---:|---|
|600|599999994|既有DPLL，CPU/div2|
|800|799999992|固件授权VPLL，FB48，CPU/div1|
|1000|999999990|固件授权VPLL，FB60，CPU/div1|
|1200|1199999988|既有DPLL，CPU/div1，默认|

NODE_VPLL=51通用PM接口由原2018.3 PMU允许，依据官方pm_config.c:544–570；整数模拟参数依据UG1085 v2.5表37-1。每次先核验真实父链没有其他活动VPLL消费者；CPU停留DPLL/div2时设置VPLL参数并锁定，切父后再核验参数/锁定/保护分支，最后变为div1。该复核保留为PMU保存上下文覆盖的准入门。模块没有MMIO写。保护APLL/DPLL/DDR/IOPLL/RPLL/PL0–3，关闭回到原始CPU/VPLL并独立核验16项raw。

四档私有跨档序列1200→800→600→1000→1200→800→1000→600→1200通过，关闭精确恢复。正式协议四档API及运行中的四档排空/恢复通过。请求600/800/1000/1200以外频率在排空前拒绝；R5同样拒绝601/799/1199。调频先正常停止并排空推理，硬件核验成功恢复之前运行状态；失败保持停止，同一连接停止命令可以取消恢复。未知owner/排空失败不卸模块，恢复失败保留quarantine，禁止force卸载。

当前默认实际1.2GHz，推理STOPPED，相机继续采集。正常重启boot `{q['board']['boot_id']}`，loader/R5/CPU/应用四项服务enabled+active，无手动补救。实际断电冷启动未测试。服务停止顺序应用→CPU→R5→既有loader；不要按旧sysfs缓存调频或直接杀owner。

## 最后测速与验证

最终固定200张输入 `{fixed['fps']:.6f} FPS`，测量{fixed['execution_s']:.3f}秒，排除模型加载及JPEG/预处理。实时180秒证据交付区间 `{live['fps']:.6f} FPS`，相机预览实收{live['preview_fps']:.3f}FPS，结果年龄p50 {live['age_p50_ms']/1000:.3f}秒，错误/结果队列丢弃0；包含模型启动的整窗吞吐需另读原始JSON。实时比原3.67490提升{p['final_gain_percent']:.2f}%，距离原固定4.06694约0.50%。原4.07与3.67都实际约1.0667GHz，原sysfs“1.2GHz”结论已审计更正。差距来自JPEG/缩放/张量准备及PS CPU竞争；最终同步少拷贝预处理31组逐元素等价。两槽异步长窗更慢，没有采用。

{q['tests_count']}项应用回归与3051冻结文件校验通过，新EXE实际文本编码、网口只读界面、非管理员拒绝和四场景模拟后端通过。只读定点代码复审通过，无新增Important/Critical。网口UAC实际写入由用户点击，本轮未自行改主机IP。

R5-0用于命令校验/遥测状态，R5-1用于小报文和串口分片CRC；GEM以太网、UVC摄像头、大JPEG和物理串口驱动仍由Linux持有。不能将当前辅助计算宣称为完整外设栈迁移或未经测量的A53卸载比例。

## 维护入口

- CPU四档源：`vision_app/cpu_clock/fz3b_cpu_clock.c`、`fz3b_cpu_four.h`；仅前者包含four头，旧fine头为未使用历史探索。
- 服务：`vision_app/cpu_clock_service.py`、`board_agent.py`、`r5/worker.c`、`client.py`。
- 构建：`vision_app/build.ps1`、`r5/build.ps1`、`tools/build_cpu_clock.py`。CPU构建只写cpu-clock-build，不覆盖已安装模块。
- 上板：`tools/install_cpu_clock.py`、`tools/update_r5_frequency.py`，先正常停止owner后备份/写入，失败按已核验生命周期回滚。
- 资格总表：`artifacts/ps-application-20261009/qualification.json`，交付目录delivery-manifest.json。
- 四档循环：`{q['four_rate_cycle']['path']}`。
- 正式四档API：`{q['verified_cpu_api']['path']}`。
- 推理暂停恢复：`{q['frequency_lifecycle']['path']}`。
- 重启自启：`{q['autostart_reboot_evidence']['path']}`。
- 性能：`docs/analysis/2026-10-09-vision-console-performance-recovery.md`及performance-comparison.json。

不要公开client-config.json中的专用应用令牌或私有板卡凭据；资格摘要不归档这些秘密。
'''
    handoff=ROOT/'docs/handoffs/2026-10-09-vision-console-four-rate.md'
    handoff.write_text(text,encoding='utf-8')
    (ROOT/'deliverables/vision-console/FZ3BVisionConsole/FOUR-RATE-HANDOFF.md').write_text(text,encoding='utf-8')
    review=base/'review-final.md'
    old=review.read_text(encoding='utf-8')
    marker='> 当前四档定点复审：'
    if not old.startswith(marker):
        review.write_text(marker+'PASS。官方授权VPLL接口无MMIO写，保护分支、消费者门、DPLL/div2安全迁移、切父后上下文复核、失败/关闭恢复无新增Important/Critical；评审独立核对9次跨档与16项raw精确恢复。后续52项回归、四档正式API/推理自动恢复及正常重启通过。此前1MHz/APLL探索记录仅作历史。\n\n'+old,encoding='utf-8')
    print(json.dumps(dict(ok=True,handoff=str(handoff),exe_sha256=exe['sha256'])))

if __name__=='__main__':main()
