# FZ3B Semantic Video Search — 最终版本

百度 EdgeBoard FZ3B 的 MobileCLIP-S1 PS–PL 混合推理与语义视频工作台。
当前版本：2026-10-09，V10.5 / A0005，PL 200/400 MHz，PS 四档 CPU 调频。

| 目录 | 最终内容 |
| --- | --- |
| `PS/` | 板端实际部署的 Linux 应用、唯一的推理 runtime、A0005/CPU/PL1 驱动、R5 源码、FPGA Manager 加载器和实际服务定义 |
| `PL/` | 最终 HLS 源包、唯一的规范 IP、最终平台 RTL/约束与所采用的综合/PREG 布局/布线脚本 |
| `HOST/` | 最终 Windows 客户端、录像/视频上传/检索/片段导出、文本编码与翻译接口及固定版本 MobileCLIP 源依赖 |

本仓库已经替换此前范围过宽的导出。旧 CLI、实验/测速/探测/维护脚本、旧兼容运行时副本、软件快照、旧 RTL 转换结果、旧部署记录均已移出当前仓库目录。
`SOURCE_MANIFEST.json` 列出每个保留源文件的来源、保留原因和 SHA256；`FINAL_VERSION.json` 固定本次版本。
少数 runtime 模块沿用 v5/v6 名称，是最终版本的实际 import 依赖，不是额外部署版本。

## 使用

PS Python 包保持板端 Python 3.6 兼容；运行路径与当前服务一致。板端完整运行包、模型、驱动二进制和已启用服务已经备份到项目本地 `backups/board-final-20261009/final.tar.gz`。
该备份包含私有配置，只在本地保存，不上传 GitHub。

Windows 使用 Python 3.12，在 `HOST/.venv-vision-client` 建立环境并安装 `HOST/requirements.txt`，在 HOST 目录执行 `python -m vision_app.launch`。
将 `HOST/vision_app/client-config.example.json` 复制为 `client-config.json`，填写板端连接令牌与模型目录；主机 EXE 构建入口为 `HOST/vision_app/build.ps1`。

模型资源单独准备：MobileCLIP-S1 权重放到 `HOST/releases/current/model-source/mobileclip_s1.pt`，官方源码已随当前依赖保存；OPUS-MT 中文→英文资源放到 `HOST/releases/application-resources/opus-mt-zh-en`。
权重身份、预处理和 ABI 以 semantic-contract 为准。PS 的 ONNX 分区、suffix11 与参数从经校验的本地板端备份恢复，不混用其他版本。

PL 的规范 IP 可直接在 Vivado IP Repository 中使用。HLS 和平台脚本保留原冻结的参数/路径合同，重建时需配置本机工具路径及外部模型/签核输入；本次整理未重新综合或烧录。
原厂 PS preset 的可重建性、XA/XC 料号和实物 revision 仍保留既有证据边界。

MobileCLIP 上游代码 LICENSE 与模型 LICENSE_MODELS 随依赖保留。
