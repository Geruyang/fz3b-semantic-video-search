# FZ3B Semantic Video Search

百度 EdgeBoard FZ3B 上的 MobileCLIP-S1 PS–PL 混合推理与语义视频检索。
此仓库保存 2026-10-09 的最新源码：V10.5 / A0005 计算平台、Linux/R5 应用、Windows 语义视频工作台。

| 目录 | 内容 |
| --- | --- |
| `PS/` | A53/Linux 应用、R5 固件、CPU 调频驱动、A0005 runtime/兼容依赖、signed40 驱动、FPGA Manager 加载服务 |
| `PL/` | A0005 HLS C++、生成 RTL/IP、时钟/DDR guard、约束、BD Tcl、综合/布局布线和验证脚本 |
| `HOST/` | Windows Qt 客户端、中文离线翻译接口、录像/视频上传/片段导出、文本编码与语义检索、模型准备和部署工具 |

三端代码独立存放；共享协议、语义契约等在 PS/HOST 中各保留字节相同的副本。
`SOURCE_MANIFEST.json` 逐文件记录原工程路径、SHA256、大小和导出范围。
原工作目录没有 Git 历史；本仓库从经过校验的当前源码快照建立首次提交。

## 功能与版本

- 实时录像并用文字检索场景，按原帧保存命中图、结果、时间段及完整 MJPEG 录像。
- 本机视频按原 PTS 逐帧上传分析，16 帧信用窗口，输出匹配片段并保留音轨。
- 主机中文离线翻译和 MobileCLIP 文本编码；A53/PL 产生图像特征，R5 辅助向量匹配、帧序校验和小报文 CRC。
- A0005：PL job 200 MHz / PW 400 MHz；PS FPGA Manager 服务加载；四档 CPU 频率控制。
- 已保存的实板/应用结果见 `docs/handoffs/` 与 `docs/evidence/`。此次上传不重新运行实板测试或综合。

## 恢复原路径运行

部分现有构建、测试和部署脚本绑定原工程相对目录。为了保持源码和冻结 SHA 不变，可在仓库根执行：

```sh
python tools/materialize_workspace.py --output workspace
```

该操作把三端源码按清单还原到独立 `workspace/`，拒绝覆盖不同内容；不会改变 PS/PL/HOST 的组织。
Windows 使用 Python 3.12 和主机依赖，板端现有 Python 3.6 / Linux 4.14 / ORT 1.16.3。
在还原目录中运行 `python -m vision_app.launch`；客户端打包入口为 `vision_app/build.ps1`。
HOST 中记录的依赖见 `requirements-host.txt`；R5 工具链入口为 PS 下的 `vision_app/r5/build.ps1`。
旧脚本中的 Vivado 安装路径及开发机绝对路径需要在新机器显式配置。

## 外部资源

源码仓库不包含连接令牌、SSH 密码、私钥、虚拟环境、EXE、位流/DCP、ORT 二进制、官方系统镜像或模型权重。
MobileCLIP-S1 原始权重、ONNX 分区、量化参数及 OPUS-MT 翻译权重需单独准备；相关配置/身份和模型许可证随代码保留。
冻结 release manifest 描述原完整发布包，源码导出清单由 `SOURCE_MANIFEST.json` 定义；不要将源码快照当成完整可部署包。
主机复制 `client-config.example.json` 为 `client-config.json` 并填写自己的连接令牌和模型路径。
部署工具使用 `FZ3B_SSH_USER` / `FZ3B_SSH_PASSWORD`、已核验的主机指纹；开发机原账户资料未归档。

Apple MobileCLIP 上游代码按附带 MIT LICENSE 保留，模型另受 LICENSE_MODELS 约束。
原始设计的 XA/XC 器件差异、板卡 revision 和 PS preset 证据边界见 `docs/hardware/FZ3B/`。
