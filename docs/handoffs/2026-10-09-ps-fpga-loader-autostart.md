# PS 开机加载、运行切换与重启测速

2026-10-09（北京时间），按用户要求实现。当前正式加载器为 `desktop_vlm/board/pl_loader/`，冻结包为 `releases/current/pl-loader-a0005-002/`。旧 `pl-loader-a0005` 为初轮原型，不作为后续部署入口。

## 已验证行为

PS 通过板上 Linux 4.14 的 `/sys/class/fpga_manager/fpga0/firmware` 加载完整 PL 位流，无需 JTAG。Linux 启动后由 `fz3b-pl-loader.service` 自动加载 A0005，应用匹配 overlay 与驱动并严格核验身份。服务持续持有 IOPLL 时钟引用，PL1 输入约 100 MHz、计算/PW 时钟约 200/400 MHz。BOOT.BIN、image.ub 与原厂 SD 备份未改写。

服务互斥控制所有切换，先检查设备没有推理进程占用，正常排空与终止驱动、卸载旧模块与 overlay，再加载目标位流。切换原厂时在原厂位流加载成功后恢复 PL1 并正常释放 lease。切换失败不自动跳到原厂；需检查服务状态和日志。

已完成真实设备占用拒绝测试、A0005→原厂→A0005 正常往返，以及一次受控重启后的自动加载。旧 boot ID `3d55761c-99d6-4985-8fdf-f13e5ca7ed73`，重启后 `4f5883a9-ed2f-4d4c-9f00-6b1d6c70f978`；新启动后未借助 JTAG 或手动下载。实际断电后的独立复验尚未再由用户执行。

## 板端使用

以 root 运行：

```sh
python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py status
python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py prepare-a0005
python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py switch-a0005
python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py switch-factory
```

`prepare-a0005` 用于上一轮程序结束并 quiesce 后重新准备驱动；在当前 A0005 下不会重新编程位流。切换原厂必须由用户明确要求；此次临时往返已获得单独确认。服务开机默认仍为 A0005，运行中切到原厂不会改变下一次启动默认值。

```sh
systemctl status fz3b-pl-loader.service
journalctl -u fz3b-pl-loader.service -b
```

不要手工 kill 服务或卸载时钟模块。若后续要求永久恢复原厂启动，应先通过加载器切回原厂，再禁用该自定义开机服务，由新任务按当时状态操作。

## 位流格式

A0005 源 bit SHA256 `a7950894715edd4e0f535b094e4a7866a220bd44f7158d153bb8e927d07bdebc`。
PS/PCAP 文件由官方 Bootgen 从该 bit 导出，SHA256 `ab2397203562cf9c5bcbe19437d5bbc440055a1277de7dc756659a3e5e40a852`，与 Vivado 原始 bin 为逐 32 位字节序转换；不能直接加载旧 `504eb3...` bin。
原厂 PCAP 文件 SHA256 `0fde8e95fc96388d2e04732d4f90e7fb339cce707ebd0aec84298ee0d14de81b`，与冻结原厂 `59e1...` 原始文件逐字对应，已通过此次真实往返加载。

官方机制依据：[AMD ZynqMP PL Programming](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841847)。本项目同时核对了与板上匹配的内核源码和实际 sysfs 权限；不把其他板型配置当成本板证据。

## 同配置推理结果

3 对预热、100 对正式输入，共 200 帧；两张固定工程输入重复使用，包括流水填充与排空。

| 项目 | 原 A0005 | 重启后 PS 自动加载 |
|---|---:|---:|
| 吞吐 FPS | 4.097891941 | 4.043501591 |
| 本次差异 | — | -1.3273% |
| 正式计算总用时 | — | 49.462 秒 |

CPU 1.066666 GHz、PL/PW 200/400 MHz，PS 前段 1 线程、suffix 3 线程，最多 4 对在途；这些条件与历史 100 对记录一致。单次差异不足以证明加载方式造成性能下降，未额外改模型、位流计算设计或线程策略。

四个 profile 各完成 100 次，共 400 次协议/guard 检查通过。最低特征 cosine 0.9990328381，最大 relative-L2 0.0442316415，通过已有工程回归门槛；不代表独立自然样本准确率评测。结果 SHA256 `7ecd1f54a4776b12a52e4a9fe53e2b78d778f4f25992f92751e4bd143d60b580`。

测速后已 prepare 为 fresh A0005 驱动，服务 active/enabled、clock lease 正常、设备没有推理 owner，原厂三项备份 SHA 复核通过。

## 实施过程记录

初版切换缺少驱动 terminal quiesce，rmmod 被正常阻止，未强制卸载。旧 daemon 失败后 target 为 unknown，不能直接继续切换。恢复过程中先验证原厂加载、保护寄存器及旧 lease owner，再利用现有 lease 驱动的 quarantine/recovery-open/FINALIZE 通路安全回收，随后启动修正版恢复 A0005。初版与修正版、审批拒绝和错误日志均保留在本轮 maintenance 证据中；最终正式切换与重启验证通过。

网口 agent 未正常启动后，主会话接手了后半段执行。全程未使用 ptrace、任意 FD 注入、强制 rmmod 或新的内核编译。详细证据位于 `artifacts/maintenance-20261009/reboot-benchmark-001/`，加载器资格验证副本保存在正式包 `evidence/` 下。
