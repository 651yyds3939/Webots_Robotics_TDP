# 部署与验证状态

## 已验证的开发环境

Ubuntu 20.04.6、Webots R2023b、独立 Conda Python 3.10.22。当前足球世界入口为 `Wenao/worlds/naotdp.wbt`，运行链路不依赖 ROS。

## 当前观测与执行

- `Observation=supervisor`：仿真真值驱动的开发模式。
- `Observation=vision`：相机估球与 Supervisor 定位的混合模式。
- 执行器使用 Webots Controller API 和关节动作资产。
- 模拟 Emitter/Receiver 提供比赛广播与传球意图通信。

## 尚未完成的部署验证

- 独立定位和完整传感器闭环。
- 机载执行或外部计算部署的适用范围。
- NAO6 实际固件、SDK、控制接口、网络与基础例程匹配。
- 真机相机、步态、接触、恢复与足球行为测试。
- 完整比赛规则和行为成功率评估。

NAOqi/libqi 仅是候选接口路线，现有实现没有完整硬件适配。当前仿真测量不构成真机验证。
