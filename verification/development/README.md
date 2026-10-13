# 本机实际验证快照

Ubuntu 20.04 / Webots R2023b / Conda Python 3.10，2026-10-12。

- unit-tests.log：23 个自动检查通过。
- referee-webots.log：实际模型加载、整球计分、非法开球位置移除和重启距离处罚检查。
- match-webots.log / match-result.json：两个缩短 60 秒半场，121.04 秒仿真时间，FINISHED，比分 0:0。
- skills-webots.log / skills-result.json：独立物理夹具，近距离射门整球越线、带球位移超过 0.1 m、接球者触球。三项各自作为测试通过条件；不证明多场景成功率或完整比赛性能。
- vision-webots.log / vision-result.json / bottom-camera.png：真实模拟相机和仓库 YOLO 检测，在一个静止球场景中的平面误差约 1 cm。不是硬件标定或泛化准确率。
- skills-manifest.json：技能验证运行时的源码散列和环境信息。

完整原始轨迹保存在发布目录外的私有备份中；验收缺口见 docs/VALIDATION.md。没有真机测试证据。
