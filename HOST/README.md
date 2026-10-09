# 主机端

vision_app 为 Windows Qt 语义视频工作台，desktop_vlm 为语义匹配 CLI/模型准备脚本，vision_app/tools 为开发与部署工具。tests/vision_app 为现有跨端回归。

按根 README 还原 workspace 后运行现有脚本。客户端需要填写连接配置并单独准备模型；SSH 凭据从环境变量提供。requirements-host.txt 记录当前主机环境依赖。
