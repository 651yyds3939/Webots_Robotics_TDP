# 四对四测试与逐项调试

日期：2026-10-20。当前阶段在单人 guarded 稳定进攻基础上，检查八个真实球员控制器同时运行的行为。观测仍来自 Supervisor 真值；不是视觉独立定位或真机比赛验收。

## 测试条件

```bash
python tests/run_webots_check.py --match --locomotion guarded --diagnostics \
  --half-seconds 300 --ready-seconds 45 --stuck-seconds 120 \
  --reset-formation --visible --seed 27 \
  --output runs/match_guarded_next_01
```

从仓库根目录、在已配置的 Python 环境中执行。输出目录必须是新的。总计两个 300 秒半场，半场时间包含 READY 等待；SET 和半场停顿使用开发夹具的短时长。

`--reset-formation` 在每半场开始由夹具初始化合法阵型，不代表自主列队能力。测量中的运动由八个球员的共享控制器和关节动作执行。普通八人世界与 `--match` 默认仍为 legacy，此处显式选择 guarded。

## 第一场完整基线

原始记录目录为 `runs/match_guarded_20261020_baseline_01`，脱敏后的结果见 [baseline](../verification/multiplayer-20261020/baseline/)。

| 指标 | 基线结果 |
|---|---|
| 仿真完成时刻 | 601.08 s，FINISHED |
| PLAYING 时间 | 夹具逐步计时约 508.04 s；轨迹采样估计约 507.56 s |
| 比分 | 0:0 |
| 球轨迹采样长度 | 约 12.068 m，排除已记录的裁判放球 |
| 恢复命令 | 5 次，分别属于红队后卫、蓝队后卫及两名蓝队前锋 |
| IMU 倾角超过 0.8 rad 的连续过程 | 4 段，不等同于经过验证的物理跌倒次数 |
| SHOOT 决策切换 / 实际 shoot 动作启动 | 10 次 / 1 次，属于尝试记录，不是射门成功数 |
| pass 动作启动 | 4 次，不等于完成四次传接球 |
| setup_removal / 长时间倒地移除处罚 | 均为 0，不能据此认定全程没有失稳 |

球轨迹见 [baseline-ball-path.png](../verification/multiplayer-20261020/baseline-ball-path.png)。该基线说明比赛生命周期和自主推进确实运行，但门前完成效率与多人稳定性尚未通过验收。`MATCH_CHECK_OK` 仍明确标注 `behaviour_success_validated=false`。

## 发现的问题

### 1. 近距离争球时出现集中失稳

约 117.36 s，红队后卫在 stand 状态下首先超过倾角阈值。最近两名蓝队前锋的根节点平面距离约 0.256 m 和 0.262 m；随后蓝队前锋 A、B 在约 117.88 s、118.52 s 相继超过阈值。红队后卫同一次连续倾倒期间启动了两次恢复命令。

图示见 [baseline-first-tilt-cluster.png](../verification/multiplayer-20261020/baseline-first-tilt-cluster.png)。图中的圆半径为 0.15 m，仅表示比例，不是实际碰撞几何。

多人接近与失稳存在时间关联，尚未由逐帧接触证据确认完整因果关系。单人 guarded 的站稳门槛不能阻止外部碰撞；后续需要隔离一对一争球、队友靠近和起身后再次接触，分别复测。当前没有据此修改动作速度、质量、摩擦或裁判处罚。

### 2. 门前球路变化引起瞄准点跳变

第一半场末，球停在约 x=-4.552 m、y=-1.061 m，尚未整球越过 x=-4.57 m 的判定平面。实测快照中：

| 仿真时刻 | 决策 | 瞄准目标 |
|---|---|---|
| 约 229.96 s | DRIBBLE，候选球路均被挡住 | (-4.8, 0) |
| 约 250.00 s | SHOOT，侧边球路畅通 | (-4.8, -0.9) |
| 约 280.08 s | SHOOT | (-4.8, -0.9) |
| 约 294.96 s | DRIBBLE，候选球路再次被挡住 | (-4.8, 0) |

实现位置为 [TeamPolicy.attack()](../Wenao/controllers/Utils/TeamPolicy.py)。原逻辑在没有畅通候选球路时退回球门中心；近门时，中心与最近开口形成的方向差较大，容易触发额外转向和重新对齐。动作完成和站稳门槛又使一次修正需要数秒，因此 SHOOT 决策不一定能转化为实际射门动作。

本轮只试验这一处：在沿用原有 0.50 m 近门范围时，全部球路被挡住的 DRIBBLE 回退目标使用最近球门开口。畅通球路选择、被挡住时禁止射门、射门距离、动作资产和裁判判球均保留原条件。该变化不保证绕开守门员，也没有实现完整球路规划。完整对照后未取得整体稳定性收益，现保留为显式开关，默认关闭。

回归测试覆盖正反进攻方向及上下两侧：防守者关闭球路时仍输出 DRIBBLE，开放时输出 SHOOT，两者的最近开口目标一致。该测试在原实现下四个子场景均失败，修正后通过。

### 3. 换边 READY 朝向仍参考旧球位

约 302.08 s，第二半场已初始化阵型，蓝队前锋 A 的 FORMATION 面向仍为上一半场球位 (-4.552, -1.061)。足球要到 SET 才摆到新的重启点，因此 READY 中存在朝旧球位转身的额外开销。

该问题已记录，本轮尚未修改。后续可单独比较 READY 面向 `restart_point` 的候选，避免与门前目标调整混在同一实验中。

### 4. 实际队内传接球尚未出现

两场均有 4 次 pass 动作，分别来自开球 RESTART 或后卫 CLEAR，而不是明确指定接球者的 PASS 配合。所有球员的 `pass_intent_received` 均为 0。此结果不能证明队内传球流程成功，也不能据此判定无线通信失效；需要双人场景检查从传球决策、实际动作启动到接应的完整过程。

## 完整对照与当前采用状态

相同种子、时长、初始化与诊断设置的对照已完成，目录为 `runs/match_guarded_20261020_aim_candidate_02`。汇总见 [comparison.json](../verification/multiplayer-20261020/comparison.json)，逐次结果见 [candidate](../verification/multiplayer-20261020/candidate/)。

| 指标 | 基线 centre | 候选 nearest |
|---|---|---|
| 完成时刻 | 601.08 s | 601.08 s |
| 比分（红:蓝） | 0:0 | 0:1 |
| PLAYING 时间（夹具逐步计时） | 约 508.04 s | 约 470.32 s |
| 恢复命令 | 5 | 12 |
| 超过倾角阈值的连续过程 | 4 | 8 |
| SHOOT 决策切换 | 10 | 2 |
| 实际 shoot 动作启动 | 1 | 1 |
| 球轨迹采样长度 | 约 12.068 m | 约 10.443 m |

两场位置轨迹在 219.32 s 首次出现超过 1e-8 m 的差异，此前共享采样点的位置一致。候选在 262.32 s 出现蓝队进球；此前最近的采样中触球归属于 BlueForwardA，进球前主要动作是 DRIBBLE 下的行走推进，因此不是射门动作精度通过验收。

球在两个半场中的 x 坐标对照见 [comparison-ball-x.png](../verification/multiplayer-20261020/comparison-ball-x.png)。图中仅绘制 PLAYING 阶段，重启/半场摆放间不连接轨迹。

候选后半场蓝队后卫出现 6 次恢复命令、4 段超阈值过程，包含约 376.56 s 的 pass 动作期间失稳。该时刻最近其他机器人根节点距离约 0.569 m，不能把所有失稳都解释成近距离碰撞；解围动作与站姿衔接也需要隔离复测。红队前锋 A 另出现 2 次恢复命令、1 段超阈值过程。

进球改变了后续 READY 等待和比赛轨迹，两场 PLAYING 时长也不同，因此不能把恢复次数差异单独归因于瞄准点。当前结论是：候选完成了一次对抗下的推进进球，但整体稳定性没有通过；**默认保持基线 centre，仅将 nearest 留作复现实验，不作为推荐比赛模式。**

## 实验开关与回归验证

不加参数时使用 `--finishing-aim centre`，恢复基线的回退目标。复现候选时显式运行：

```bash
python tests/run_webots_check.py --match --locomotion guarded \
  --finishing-aim nearest --diagnostics --half-seconds 300 \
  --ready-seconds 45 --stuck-seconds 120 --reset-formation \
  --visible --seed 27 --output runs/match_nearest_experiment_next_01
```

开关只允许 `--attack` 或 `--match` 配合独立输出目录。运行器将选择写入 manifest，并显式传入 `TDP_FINISHING_AIM`；球员 command 日志记录 `finishing_aim`。直接打开世界时未设置该环境变量即为 centre。

1. 最终 66 项逻辑测试通过，包含候选目标连续性、默认基线保留和实验参数限制。
2. 实验版本和最终默认模式各执行一次标准单人严格回归，均在 76.24 s 完成进球，恢复命令为 0，最大躯干倾角约 0.3881 rad，最低高度约 0.2877 m，包含进球后 1.6 s 的停止检查。证据见 [single-regression](../verification/multiplayer-20261020/single-regression/) 和 [default-single-regression](../verification/multiplayer-20261020/default-single-regression/)。最终默认运行的 manifest 和所有 command 记录均为 centre。
3. 将候选移到开关后，分别重放两场的全部裁判采样：当前默认与归档基线的 21,704 个球员决策完全相同，当前 nearest 与归档候选的另 21,704 个决策完全相同。该检查验证记录状态下的决策等价，不替代新场景动力学验收。

`aim_candidate_01` 曾在 Webots 加载阶段持续占用 CPU，尚未生成任何控制器或裁判日志，随后中断。原因未确认，不能算作完成的一场比赛，也没有计入行为统计；记录见 [startup-aborted.json](../verification/multiplayer-20261020/startup-aborted.json)。完整对照在增加实验开关前运行，源码清单只有 `TeamPolicy.py` 与基线不同；归档保留两份当时实际策略源码。

## 下一轮的优先级

先隔离蓝队后卫的解围与动作后站稳，比较无对手、有静止对手及近距离移动对手；再检查同队支援和对手争球的让位与避让。之后单独修正 READY 面向重启点，最后补齐双人自主传接球。每轮只改变一个因素，再回到四对四检查，保留失败结果。

## 分析命令

```bash
python tools/evaluate_run.py runs/match_guarded_next_01 \
  --output runs/match_guarded_next_01/metrics.json
python tools/analyze_multiplayer_run.py runs/match_guarded_next_01 \
  --output runs/match_guarded_next_01/multiplayer-analysis.json
```

`analyze_multiplayer_run.py` 将每名球员的恢复命令、倾角过程、此前动作切换和最近其他机器人位置关联起来，并汇总小于 0.30 m 根节点平面间距的采样时长。位置接近不等于实际接触，时间相邻不等于已证明碰撞原因。已有运动诊断输出可逐机器人查看：

```bash
python tools/analyze_motion_diagnostics.py runs/match_guarded_next_01 \
  --robot RedDefender --output runs/match_guarded_next_01/red-defender-motion.json
```

原始运动诊断日志体积较大，保存在被 Git 忽略的 runs；公开结果只保留汇总、图像和去除本机路径的清单。一次固定种子的对照不是总体成功率，也不能把赛程改变后出现的恢复次数变化直接归因于动作稳定性改善。
