# PL 侧

releases/current/hardware/src/a0005 为正式 HLS 源码，src/half2x 与 src/fused-alu 为生成依赖；generated 保存规范 RTL/IP 和可追溯的转换阶段；implementation 保存 BD、约束和重建脚本。

此目录是源码导出，不包含 DCP、bit/bin 或大型数值 fixture。原 release 校验器需要完整发布包；导出完整性请用仓库工具 verify_source.py。
