# 单人带球、无摔倒进球

本阶段目标为无对手的单人接近、带球、射门并整球越过球门线，全程无恢复命令、无倾倒，并在进球后继续检查 1.6 秒的停止稳定性。测试使用实际球员控制器、原始关节动作与裁判广播定位，没有在进攻期间摆放机器人或推动足球。

## 运行

在仓库根目录、激活 `robotics-tdp` 后执行：

```bash
python tests/run_webots_check.py --attack --visible --diagnostics --seed 27 --output runs/single_player_stable_next_01
python tools/evaluate_run.py runs/single_player_stable_next_01 --output runs/single_player_stable_next_01/metrics.json
python tools/analyze_motion_diagnostics.py runs/single_player_stable_next_01 --output runs/single_player_stable_next_01/motion-summary.json
```

普通 `--attack` 现在默认使用 `guarded` 调度并启用无摔倒验收。也可以显式添加 `--locomotion guarded --require-no-fall`。已有输出目录不能重复使用；第二次改成 `_02`。测试自动结束并保存结果，Ctrl+C 中断会保存已有日志。

`--attack-layout mirrored` 将机器人初始 y 从 -0.15 m 改为 +0.15 m；`--attack-layout offset` 将球的初始 y 改为 +0.25 m。它们用于空间条件变化，比仅换 seed 更直接。

复现旧控制器使用 `--locomotion legacy`；旧版仅进球并不代表无摔倒，添加 `--require-no-fall` 可检查其原有失稳。正常八人世界与 `--match` 仍保留既有默认调度，本阶段的单人结果不能代替四对四验证。

## 执行调度的修正

1. 直行需要切换动作时，先记录停止请求，等实际播放时间到达周期末端，再收回站姿。连续直行仍循环播放，不在每个周期之间停顿。
2. 单次侧移、转向或踢球完成后先执行站姿动作，再重新判断目标与脚位，避免用动态摇摆中的位置反复左右修正。
3. 站姿动作结束后，还需同时满足 IMU roll/pitch 小于 0.12 rad、roll/pitch 变化率最大值小于 0.35 rad/s、左右脚局部 z 力均大于 5 N，并持续满足 0.16 秒，才继续决策。这些门槛仅按当前 Webots 模型验证，不是通用真机标定。
4. 新动作从播放位置 0 开始，不从此前暂停的中间相位恢复。比赛阶段、观测有效性、视觉丢球和倾倒恢复仍具有优先级。

实现位于 `Utils/GuardedLocomotion.py` 与 `Base/SoccerController.py`；导航、射门距离阈值、动作文件和场地尺寸没有为此放宽或加速。该实现是带稳定性门槛的动作调度，尚非全身平衡控制器。

guarded 模式还将战术瞄准点放在门线后 0.30 m 的球门内部。早期镜像测试虽然无摔倒，但球停在 x=4.556 m，尚未达到整球越线所需的 x=4.57 m；原门线上目标会在此时引导转向偏侧甚至回头。瞄准点前移后，射门的 0.50 m 触发距离仍按门线计算，整球进球判定保持原值。legacy 模式保留原瞄准点用于历史对照。

## 严格验收

`attack-result.json` 必须同时满足 scored 为 true、触球归属于 RedForwardA、no_fall_criterion_passed 为 true。无摔倒条件为：从比赛开始至进球后停止观察结束，躯干 up 分量不低于 cos(0.8)、躯干高度不低于 0.20 m、恢复命令数为 0。测量使用测试裁判，不作为球员的运动控制输入。

仅有 `ATTACK_CHECK_OK` 还需结合 manifest 判断是否启用了严格验收；旧结果只检查进球。严格模式失败会返回非零并保留失败结果，不能仅保留成功运行。

标准初始条件的独立严格测试在 76.24 秒进球，恢复命令为 0、最大躯干倾角约 22.2°、最低高度约 0.288 m，包含进球后 1.6 秒的观察。镜像站位和球偏移布局分别在 129.04 秒、161.16 秒完成同一验收。原始控制器约 147.16 秒进球且发生恢复，被相同严格条件正确判为失败。重复次数、实际结果和开发中的失败记录见 [验收证据](../verification/guarded-single-player/README.md)。

指定初始条件的重复测试不等于通用成功率；视觉独立定位、对抗、硬件适配与规则完整性仍需分别验证。
