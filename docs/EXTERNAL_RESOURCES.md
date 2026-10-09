# 外部资源与运行边界

此仓库保存源码，不代替原完整 `releases/current` 运行包。

| 资源 | 获取/核对入口 |
| --- | --- |
| MobileCLIP-S1 原始权重 | Apple 官方 MobileCLIP；源 revision 和权重 SHA256 见 `HOST/vision_app/semantic-contract.json` |
| PS ONNX 分区、suffix11、量化参数 | 按 HOST 模型准备脚本重建并核对 PS release/selection manifest；板端当前冻结版本已有这些资源 |
| ONNX Runtime AArch64 | 当前目标 1.16.3；主机拆分环境版本不能替代板端版本 |
| OPUS-MT 中文→英文 | `Helsinki-NLP/opus-mt-zh-en`；HOST 内保留模型 README、配置与 tokenizer 元数据 |
| A0005 bitstream、DCP、DTBO/KO/ELF | 原完整发布包或按对应工具链重建；本仓库只保留源码与清单 |
| SSH 指纹 | 核验实际板卡后自行准备 `releases/current/ps/tools/ssh/board-known_hosts`；账户密码通过环境变量提供 |

原有构建脚本会引用大型 fixture、模型、DCP 等完整发布包文件。这些依赖没有通过源码导出自动变成可用文件。
`PL/releases/current/hardware/tools/materialize-original-layout.ps1` 可在取得完整发布包后进一步还原被冻结的历史构建路径。

复制客户端配置示例并填写板端令牌；令牌必须与板端配置对应。部署/维护脚本会操作板卡，执行前需核对当前 owner、加载器和生命周期。
