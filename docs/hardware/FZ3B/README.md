> 清理更新（2026-10-01）：LiteSeg 工程及交付包已按用户要求删除。本文的旧工程描述仅为历史背景，当前目录保留 FZ3B 板卡资料与技能。

# 当前目标：百度 EdgeBoard FZ3B

> 最新平台（2026-10-09）：A0005 PS–PL推理、Linux FPGA Manager开机加载与运行切换已通过。[PS应用交接](../../handoffs/2026-10-09-ps-application-development-handoff.md)为当前入口，[完整复盘](../../analysis/2026-10-09-project-development-retrospective.md)记录演进与边界。下方“尚未连接”及旧artifact链接是历史快照；实物revision/完整料号/可重建原厂preset仍未完全核验。

记录日期：2026-10-01（Asia/Shanghai）。用户在本轮对话明确说明其开发板是 **FZ3B**，因此更正此前以 MYD-CZU3EG-V3 为当前目标的记录。尚未连接或读取实物。

## 开发入口

- [PS–PL DMA 回环实板记录](../../../artifacts/board-debug-20261004/acceleration/jtag/dma-loopback-board-002/WINDOW-002-FZL1-LOOPBACK-PASS.md)：2026-10-05，保留运行 PS 初始化，HPM0 控制、HP0 64位数据口配官方 AXI DMA，1B至4MiB回环和正常驱动卸载通过，原厂 PL/驱动/USB已恢复。证明该运行态下的自定义 PL/DDR 数据通路；不证明冷启动 DDR/MIO preset 可重建、原厂AI与自定义PL共存或完整实物等级/revision 已核验。[四阶段接续记录](../../handoffs/2026-10-04-four-stage-model-transition.md)持续记录后续状态，历史原厂恢复快照不能替代当前窗口检查。

- [已验证功能与后续开发参考](verified-development-reference.md)：2026-10-03，仅整理 20261002 实板测试与 USB-A 摄像头诊断的已保存证据；列出限量通过范围、工具配置、未测/失败、开发与恢复注意事项。该运行截止 01:26:56 的暂停快照，不覆盖其他会话当前板状态，未启动新测试。

- [CM717 摄像头最新交接](CM717-CONTINUATION.md)：2026-10-03，实板采集、并行解码优化、30fps 模式上限、最后恢复状态与全部记录索引；新会话从这里接续摄像头工作。

- [Windows ARM64 仿真运行验证](WINDOWS-QEMU-VALIDATION.md)：2026-10-02，Ubuntu 用户空间两次启动，30 项测试通过；通用仿真内核，不等同于 FZ3B 实板验证。

- [官方 Linux TF 卡安装记录](TF-LINUX-INSTALL.md)：2026-10-01 已制作 FZ3B Ubuntu 18.04.5 / 软核 1.8.1 TF 卡，全量回读通过；尚未实板启动或扩容。下文首次资料整理的“未烧录”描述保留为历史记录，本次仅写 TF 卡，未更新板载 eMMC/QSPI。

- [FPGA-vibecoding 技能](../../../skills/fpga-vibecoding/SKILL.md)：路径选择、流程与按需参考。
- [百度官方资料整理](../../../skills/fpga-vibecoding/references/baidu-fz3b.md)：板型、软件配套、接口文档冲突、资料申请与阅读覆盖。
- [本地工程证据](../../../skills/fpga-vibecoding/references/project-context.md)：LiteSeg 旧目标、历史仿真/OOC 结果与复用范围。
- [结构化板卡记录](board-profile.json)：用户声明、文档声明、工程配置和未知字段分别记录。

## 已确认的资料与未确认的实物

[百度 FZ3B 硬件说明](https://ai.baidu.com/ai-doc/HWCE/nkq9b5ncu)，页面日期 2023-07-04，第一至五章声明 `XAZU3EG-1SFVC784I`、4GB/64bit DDR4、8GB eMMC、256Mbit QSPI。以上是文档声明，不代表已核验用户板上的芯片、颗粒或 PCB revision。旧工程的 `XCZU3EG` 与网页的 `XAZU3EG` 差异保留待核验。

当前未取得与用户实物 revision 绑定的原理图、PS DDR/MIO preset、正式 XDC、可重建板级参考工程或 BSP。硬件网页包含接口/引脚资料，但部分内容存在图文或跨版本冲突；不能拼接成未经验证的板级初始化配置。

[百度硬件 FAQ](https://ai.baidu.com/ai-doc/HWCE/akqgdblqi)（2022-01-19）说明 Vivado 工程源码不开放、自定义 FPGA 固件会失去原百度 AI 能力，并提供购买后申请原理图的方式。因此先确定任务使用原厂推理环境还是独立自研 PL；自研逻辑可以先完成仿真和器件级验证。

## 下一次真实上板时补充

只收集与当前任务有关的证据：板卡丝印/revision、完整芯片标记、匹配原理图与接口电压、PS preset、启动介质/拨码、UART/JTAG 接法、当前镜像及软件版本、备份和恢复记录。记录日志/照片/文件的来源、日期和哈希。

现有 MYC/MYB/MYD 资料、ALINX 示例、MYIR FZ3 PDF 和旧 PPT 均不能自动充当 FZ3B 的板级证据。本次仅创建知识与技能，没有运行综合实现、升级系统或烧录硬件。

