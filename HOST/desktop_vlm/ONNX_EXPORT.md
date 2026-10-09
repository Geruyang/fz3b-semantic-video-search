# S1 图像编码器导出与数值核验

2026-10-04：用于当前 FZ3B 初版程序的研究验证。沿用原始 S1 权重许可，导出文件留在本机实验目录，不随源码分发。

`scripts/export_s1_onnx.py` 使用现有 `MobileCLIPEncoder` 核验官方 revision、源码状态与权重 SHA，加载并重参数化真实 S1；导出固定输入 `float32[1,3,256,256]`、输出原始 `float32[1,512]` 的图像编码器。候选文本由同一模型编码并保存 L2 特征。ONNX 产物使用独立 manifest，不冒充原 PyTorch 缓存身份。

运行环境为原已验证 Python 3.12 venv，另在 `artifacts/board-debug-20261004/host/onnx-deps/` 安装 `onnx==1.17.0`、`onnxruntime==1.20.1`、`protobuf==5.29.5`、`flatbuffers==24.3.25`、`coloredlogs==15.0.1`、`humanfriendly==10.0`；未升级原 venv 的 NumPy/PyTorch 等依赖。

从项目根目录在 PowerShell 中复现；`--output` 必须是新的目录：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TORCH_FORCE_WEIGHTS_ONLY_LOAD = '1'
$env:HF_HUB_OFFLINE = '1'
$env:PYTHONPATH = 'E:/AIProject/FPGAVibecoding/artifacts/board-debug-20261004/host/onnx-deps;E:/AIProject/FPGAVibecoding/desktop_vlm/src'
& 'artifacts/desktop-vlm-20261003/reviewer/venv/Scripts/python.exe' -B `
  'desktop_vlm/scripts/export_s1_onnx.py' `
  --official-repo 'artifacts/desktop-vlm-20261003/reviewer/official-mobileclip' `
  --weights 'artifacts/desktop-vlm-20261003/reviewer/mobileclip_s1.pt' `
  --prompts 'desktop_vlm/configs/prompts.en-zh.json' `
  --image 'artifacts/cm717-capture-20261003/sample-1280x720.jpg' `
  --output 'artifacts/board-debug-20261004/host/s1-onnx-new'
```

`--image` 可重复。脚本对每张图使用官方预处理，导出输入浮点数据、PyTorch 与 ORT 输出，验证特征 `rtol=1e-3, atol=1e-4`、候选余弦分数绝对差 `<=1e-5`。ONNX checker 必须通过；任一对拍失败抛异常，不生成 PASS manifest。`manifest.json` 记录原模型完整身份、opset/IR、算子统计、提示词、输入来源、文件大小及 SHA。

本轮 `artifacts/board-debug-20261004/host/s1-onnx-001/` 实际产物为 IR8/opset17、86,077,972 B。三张历史真实 JPEG 的主机 ONNX/PyTorch 特征最大绝对误差为 `4.023313522338867e-7`，候选分数最大绝对误差为 `1.1920928955078125e-7`；执行日志 `host/export-001.log`。这一步仅证明导出数值一致，板端执行和本次新图必须另有实机证据。

ONNX Runtime 的官方 [CPU Python 平台说明](https://onnxruntime.ai/docs/get-started/with-python.html) 支持 Linux ARM64；具体板端库仍须核实际 glibc、架构和运行结果，不能由主机 wheel 推断板兼容。
