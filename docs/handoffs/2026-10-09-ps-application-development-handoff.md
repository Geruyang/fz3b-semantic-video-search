# 下一会话交接：FZ3B PS 应用开发

日期：2026-10-09（Asia/Shanghai）。这是下一会话首读文件。用户决定后续重点开发PS应用；当前A0005计算位流、现成驱动、模型和性能基线保留，不默认开始新HLS、布局布线或提频。

## 1. 可复制到新会话的任务说明

> 在 `E:\AIProject\FPGAVibecoding` 继续PS应用开发。先读取AGENTS.md、FPGA-vibecoding技能及本交接。当前正式版本V10.5/A0005已由Linux FPGA Manager的systemd服务自动加载，运行中切换和受控重启已通过。最新100对/200帧4.043501591FPS，历史同配置4.097891941FPS；这是固定tensor到feature，不是摄像头FPS。先只读确认真实boot/service/位流身份/无owner，再按新应用目标开发。复用现有PS/PL runtime及loader的prepare接口，正常关闭会terminal-quiesce，下一次需fresh驱动。不要用旧PID、旧artifact路径、已删除内核树或旧A0004设备路径；不要默认恢复原厂、改USB角色、重新编译PL。仍缺实时相机→预处理→流水→语义匹配/图库→结果交付的统一适配及独立样本精度评估。沿用原厂SD恢复备份，不打印凭据。

## 2. 首读顺序和最后验证状态

1. `AGENTS.md`、`docs/hardware/FZ3B/README.md`：板型/实物未知项和平台证据。
2. 本交接；需要查历史再读[完整复盘](../analysis/2026-10-09-project-development-retrospective.md)和[错误台账](../analysis/2026-10-09-errors-and-solutions.md)。
3. [PS自动加载与切换](2026-10-09-ps-fpga-loader-autostart.md)及`releases/current/pl-loader-a0005-002/{manifest,board-qualification,config}.json`。
4. `releases/current/ps/{README.md,manifest.json,run-a0005-fair30.sh}`、`release/models/manifest.json`、`suffix11-selection/selection-manifest.json`。
5. 下节runtime及`desktop_vlm/src/desktop_vlm/`，相机工作再按需读CM717交接。

最后状态：A0005 fresh驱动就绪、无推理owner，service active/enabled，manager operating，时钟FD由加载器daemon持有。最后boot `4f5883a9-ed2f-4d4c-9f00-6b1d6c70f978`只是记录，不要求下一会话boot相同。

CPU约1.0667GHz、PL1输入100MHz、job/PW200/400MHz；CPU1.2GHz没有永久保留。前段1线程/suffix3线程、最多4对在途，spinning/prealloc关闭。最近固定A/B重复200帧/49.462秒为4.043501591FPS，质量和400次profile completion均通过。

同一原始结果的平均计时：PS stem/N3/suffix调用分别146.383/43.223/238.836ms每张；PL P2/P3/P0/P1硬件分别41.270/7.789/99.914/172.072ms每对。完整owner平均PS_FRONT/PL/PS_SUFFIX为379.937/409.939/477.969ms每对，后缀当前最忙。准入到完成p50约1897ms包含排队，不是1/FPS。[详细计时及口径](../analysis/2026-10-09-project-development-retrospective.md#121-当前流水及各部分耗时)，[机械提取数据](../../artifacts/maintenance-20261009/project-handoff-001/timing-extract.json)。

## 3. 路径、依赖与磁盘

| 内容 | 当前路径 |
|---|---|
| SSH网络 | FZ3B `192.168.1.254`；确认实际接口和可信fingerprint |
| 模型/inputs/refs/suffix/runner/native/compat | `/root/network10-v10.5-a0005-retained-current` |
| runtime/validation/deployment/results | `/root/workspace/network10-v10.5-a0005-board-validation-001` |
| 加载器/服务 | `/root/workspace/network10-v10.5-pl-loader`；`/etc/systemd/system/fz3b-pl-loader.service` |
| PCAP固件 | `/lib/firmware/network10-v10.5/` |
| 状态/日志 | `/run/fz3b-pl-loader/`，root-only control.sock；`/var/log/fz3b-pl-loader.jsonl` |
| 现成时钟KO | `/root/workspace/network10-v10.4-pl1-iopll-lease-candidate-001/fz3b_pl1_iopll_lease.ko` |
| raw只读工具 | `/root/workspace/network10-v10.4-clock-raw-baseline-001` |
| ORT实体 | `/root/board-debug-runtime-20261004/runtime/onnxruntime-linux-aarch64-1.16.3` |
| ORT兼容链 | `/root/board-debug-acceleration-20261004/runtime/` |
| 原厂SD备份 | `/root/workspace/factory-backups/network10-factory-20261009-a0005-retained` |
| 相机历史程序 | `/root/workspace/cm717-fps-20261003/`，先重新确认文件/设备 |
| 内核编译树 | `/root/board-debug-kernel-20261004` **已删除**，只有重新编译驱动才需恢复 |

旧名ORT/lease/runtime目录仍是当前依赖，不能凭日期删除。旧PS包README/SIGSTOP-holder、protected-paths里的kernel条目已被本交接覆盖，冻结文件内容清单仍有效。

`/`是SD第二分区，`/root/workspace`是约249MB独立第三分区，不能混算空闲容量。清理后根分区曾可用约2.10GiB，后续输出会改变；新模型/环境先核磁盘。内核完整备份在 `releases/current/tools/kernel/board-prepared-kernel-20261009/`，RESTORE.md仅在需要板上编译时使用；原厂OS ZIP在 `releases/factory/os/`。

主机SSH助手 `releases/current/tools/fz3b-ssh-python.ps1` 使用 `C:\Users\ruyangge\.codex\mcp\serial\.venv\Scripts\python.exe`，包内独立Paramiko/CFFI及known_hosts。凭据使用现有受保护来源或用户环境变量，不能输出/写入新交接，也不要从已删除artifact导入依赖。

## 4. 最小操作流程

板端root：

```sh
python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status
systemctl is-active fz3b-pl-loader.service
systemctl is-enabled fz3b-pl-loader.service
cat /sys/class/fpga_manager/fpga0/state
fuser /dev/network10_v10_signed40
```

先核真实READY_A0005/身份/无占用。上一轮已经退出并terminal-quiesce后：

```sh
python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py prepare-a0005
```

此命令在已加载A5时只刷新驱动/身份，不重新program。runtime必须`with`或显式close；停止迭代也需关闭，不留下runner/device handle。应用运行时不直接rmmod、去overlay、kill加载器或写clock。

用户明确要求时才用 `switch-a0005`/`switch-factory`。本次临时往返批准不是以后自动恢复授权。开机默认A5；运行切factory不改下次默认。永久原厂启动需新任务先正常切回、再禁用自定义开机服务。

## 5. 可复用应用接口与数据链

正式软件尚无单一应用SDK工厂；经验证的组装逻辑位于 `benchmark_cnn_pipeline_v10_live.py`：

- `build_v10_mixed_components()`创建PS client/原生转换。
- `LinuxIoctlV10Signed40CandidateTransport`严格打开A0005设备和参数合同。
- `V10Signed40ChainMixin + V10MixedBoundaryMixin + V10SplitPsLiveRuntime`组成正式流水。
- `V10LiveRuntime.iter_results(items,max_in_flight=1..4,record_history=False)`为流式适配点，另有有限批`run()`/`run_one()`。

先从该组装逻辑抽应用工厂，不独立重写驱动协议。板Python3.6；runtime-current与runtime-compat必须同时提供PYTHONPATH。builder仍创建network1 ORT client，即使P3已经卸载N1，精简时先核接口/生命周期。

输入 `(frame_id,tensor)`：ID非负严格递增，finite contiguous FP32 NCHW `[1,3,256,256]`。输出每帧独立FP32 `[512]` features及ID/pair_timing/completions，不别名到会被下帧覆盖的共享缓冲。

```text
RGB → 官方Resize/CenterCrop256 → FP32 [1,3,256,256]
→ PS stem → FP32 [1,64,64,64]
→ INT16 HCW量化写WC → 单PL owner连续执行P2(N0)→P3(N1)→P0(N2)
→ FP32 [1,128,32,32]
→ PS network3 bridge → FP32 [1,256,16,16]
→ INT16 HCW量化写WC → PL P1(N4)
→ FP32 [1,256,16,16] → PS suffix11 → raw FP32 [1,512]
→ L2归一化 → text/gallery cosine → 应用交付
```

PL两lane处理A/B，不允许两个应用任意同时操控设备。P2→P3→P0必须连续占PL owner，避免共用arena被别的批次插入。PS_FRONT负责stem/N3，PS_SUFFIX负责suffix，PL负责核及边界；pair之间可重叠，返回仍按输入顺序。

量化：FP32/scale使用FP64及ties-even，饱和为little-endian INT16 HCW。native NEON融合CHW→HCW并直接写WC，反量化逆布局再乘scale。常量以manifest为准：P2 input约0.00016495765799892816；P0 output约8.010273432023655e-06；P1 input/output约7.726196825520674e-05/2.462270113096634e-05。

signed40仅normal P0/P1/P2的PW2累加/FIFO存储，激活仍INT16，P3敏感宽度按合同保留。suffix11是**6个Conv+5个MatMul的W8A8 QDQ**，其余suffix节点FP32；不是11个卷积或全图整数。

正式使用direct_wc。cached-DMA候选被Linux4.14同步回收能力阻挡，禁止把 `allow_global_zynqmp_memcpy=0` 改掉强开；CPU写DDR不是DMA。

ShmOrtPartitionClient用tmpfs+mmap（64-byte ORTSHM3头+输入/输出），runner继承FD，pipe只传请求ID/JSON ack。仍有输入写入mmap和输出独立ndarray复制，不称完全零复制。I/O采用非阻塞FD/select/deadline，保留shape/finite/ID检查。

异常停止准入，owner drain后terminal QUIESCE、FREE opaque handles、关闭device和ORT clients。正常close也是当前probe终态，下次prepare。不能宣称Python可以强杀任意阻塞线程。

## 6. 已有语义功能与缺口

桌面 `desktop_vlm/src/desktop_vlm/` 实现：MobileCLIPEncoder图/文本编码；build/load_text_cache；build/load/query_gallery；normalize_rows/cosine_scores/rank_scores；doctor/cache-text/match/gallery-build/gallery-query CLI。

NPZ禁pickle、元数据/特征绑定；text含id/text/label，gallery含item_id/label/image_sha256。当前英文提示/中文标签为杯子、遥控器、螺丝刀、钳子、食品包装、瓶子、键盘、手机，可按新目标明确修改。host包Python≥3.10/PyTorch，不能直接装到板Python3.6。

当前保留树只有prompt JSON，没有已生成可直接加载的text-cache/gallery NPZ；应在主机重建并校验，再提供板Python3.6轻量reader。按文字prompt做物品类别匹配与读取物品上的文字/OCR是不同能力；当前S1后端不提供OCR。

仍缺：

1. UVC采集/解码/预处理接到iter_results。
2. 接受板端已计算raw512 feature的正式匹配/图库API。现match/query_gallery会在主机重新编码图片。
3. PS量化图像流水身份与host文本/图库身份的兼容合同。只有同维512不能跳过模型/预处理/归一化检查；Board release没有文本encoder。
4. unknown阈值、去抖/时序聚合、显示或HTTP/网络结果交付、应用健康监控。
5. 独立真实物品/角度样本准确率及长时间端到端性能。

建议兼容合同分别记录源模型+预处理身份、有效图像流水身份、text/gallery身份。图库可统一由当前图像后端编码，或独立对拍后明确跨后端兼容，不删除cache身份检查。余弦不是概率，工程特征阈值不是分类准确率。

## 7. 下一阶段建议与验收

第一批抽出应用会话工厂、prepare/close、固定身份、流输入和输出，并先在主机实现接收raw-feature的matcher/缓存兼容合同及文本缓存生成；用固定tensor对照原benchmark，核同feature、帧号、量化、语义匹配和无泄漏。bit不变的软件改动不重复综合。

第二批接真实相机。CM717历史四线程2K BGR约25FPS、占3.6核，不能与4FPS推理简单相加；优先V4L2压缩流、仅解拟推理帧、较低分辨率和有界latest-frame队列，解码后BGR→RGB再保持官方resize/crop一致。旧本机相机源码/artifact及USB串口脚本已删除，先查历史板端目录并审查取回/纳管源码；不存在则按已记录协议重新实现，不依赖不存在的链接。实时低延迟和离线吞吐分别测max_in_flight1/2/4，4对在途等于8张图，1对仍含双图配对等待，不是最低显示延迟保证。奇数尾shadow不计真实吞吐。

第三批完善图库预计算、经真实样本校准的unknown/去抖和结果交付，再按用户选定的显示/网络界面实现；未指定UI先用结构化日志，不擅自搭框架/升级Python。

第四批独立真实样本及长期测试：分段计时、camera/inference帧率、队列延迟、丢帧/重复/乱序、CPU/RSS、异常/early-stop排空。重启自动加载已验证；实际再断电上电、温度/供电/长期稳定性仍单独记录。

## 8. 不要沿用的旧状态

- 旧desktop_vlm README/artifact/venv命令已清理，读新入口；旧说明“尚未接PS–PL”不再成立。
- 冻结PSREADME的SIGSTOP holder、protected-paths的kernel条目过时；4.0979FPS是保留基线。
- loader manifest/README的manual-gate/factory未验证描述是冻结时信息，board-qualification记录后续通过。
- suffix selection的p3_domain=UNTESTED是生成快照，后续A5真实feature通过工程门，自然样本仍未验。
- models manifest ORT1.20.1是host拆分环境，目标runner1.16.3；runtime-current不能单独复制。
- 旧设备 `/dev/network10_v10`、A0004 ABI、旧PID/READY、已删b/w和kernel不可复用。
- 全宽200停止、V9 180仅OOC、CPU1.2恢复、cached DMA禁用、HP128/HP1/新suffix PL未采用。
- A5无ILA/ltx；波形需求另建debug并重新签核、保存原生.ila；原厂AI共存未证明。

## 9. 固定身份与恢复

core `0x465A5641`、ABI `0x000A0005`、caps `0xFFF`、UAPI10。
source manifest `f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593`；combined `4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690`。
bit `a7950894715edd4e0f535b094e4a7866a220bd44f7158d153bb8e927d07bdebc`；PCAP `ab2397203562cf9c5bcbe19437d5bbc440055a1277de7dc756659a3e5e40a852`。
factory native `59e1a6176194eccc05603738ba3c2e71ea25c3c09cdf9dce47ed1ad1ddf5fc2e`；factory KO `a482b11d47a117e60f98efd43631b45a3a33ba98e81ff610204d2f301dbb0b6f`；完整已配置kernel归档 `23ffa35bc99c7c3828bce61862e5a5ec82ea979be62c2a624510641ecb1e62cf`。

所有摘要从实际文件/manifest机械取值，不手抄；不原地修改冻结bit/model/driver合同。主机只读校验：`python scripts/verify_retained_releases.py`；硬件还可verify-bundle.ps1。普通应用开发不为校验反复启动Vivado、restore kernel或切factory。
