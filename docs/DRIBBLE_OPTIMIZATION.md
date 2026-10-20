# 单人进攻对照实验操作

当前阶段以固定单人场景检验一次导航修改；四对四、视觉与步态开发另行评估。

## 本轮已完成的操作

1. 检查三份基线目录 `runs/dribble_baseline_01/02/03`，确认仿真源码散列一致，三次均在 147.16 秒进球。
2. 在 `optimize-dribble-alignment` 实验分支测试带球横向滞回；进入阈值 0.10 m、退出阈值 0.08 m，保留射门和传球判定。
3. 执行候选单元测试，44 项通过；在 `runs/dribble_hysteresis_01/02/03` 保存三次实际物理测试。
4. 三次候选均在 180 秒内未进球，侧移与起身尝试增加；恢复基线控制代码与测试，保留失败补丁和结果。

完整对照记录见 [verification/dribble-hysteresis/README.md](../verification/dribble-hysteresis/README.md)。本轮候选不用于后续正式实验。

## 重新运行当前基线

从项目根目录、已激活的独立环境运行：

```bash
conda activate robotics-tdp
python tests/run_webots_check.py --attack --visible --locomotion legacy --seed 27 --output runs/dribble_baseline_new_01
python tools/evaluate_run.py runs/dribble_baseline_new_01 --output runs/dribble_baseline_new_01/metrics.json
cat runs/dribble_baseline_new_01/attack-result.json
```

第二、三次将命令中的输出目录分别替换为 `runs/dribble_baseline_new_02`、`runs/dribble_baseline_new_03`。输出目录必须为新目录；已有数据保留。脚本自动启动与结束，最多观察 180 秒仿真时间。`--half-seconds` 不延长此夹具，`--timeout` 控制墙钟等待上限。

## 后续候选的对照方法

首先保存已有代码和文档修改，再建立独立实验分支；每轮只改变一个行为环节，并记录参数、初始条件、源码版本和失败。

修改后先执行逻辑检查：

```bash
python -m unittest discover -s tests -v
```

随后以同样的模式、种子和初始条件运行三次，每次使用新的候选目录，例如：

```bash
python tests/run_webots_check.py --attack --visible --locomotion legacy --seed 27 --output runs/dribble_candidate_next_01
python tools/evaluate_run.py runs/dribble_candidate_next_01 --output runs/dribble_candidate_next_01/metrics.json
```

第二、三次分别使用 `_02`、`_03`。本历史实验使用标准初始场景和 legacy 调度，改变种子不能替代位置、朝向和球速覆盖。当前稳定模式与布局变化见 [SINGLE_PLAYER_STABILITY.md](SINGLE_PLAYER_STABILITY.md)。

| 判定项 | 数据来源 |
|---|---|
| 是否整球进门、成功耗时或失败截止 | `attack-result.json` 的 `scored`、`seconds_to_end` |
| 左右侧移、行走、恢复尝试 | `metrics.json` 的 `commands` |
| 对齐、行走和恢复指令间隔 | `command_seconds_all_phases`；包含全部阶段并省略末条指令尾段 |
| 问题发生前后的行为、导航阶段、位置与朝向 | `player-RedForwardA-*.jsonl` 的 command/decision/navigation 事件 |
| 机器人和球的观测、触球归属 | `match-*.jsonl`；触球归属使用接触位置近似 |

保留候选需要进球能力没有退化，成功耗时或其他目标指标改善，且恢复尝试没有明显增加。只有侧移次数下降不足以判定改进。重复固定场景通过之后，再增加初始位置/方向覆盖与近距技能回归，最后进入对抗实验。

## 下一轮测量重点

本轮结果支持先诊断侧移、转向与直行衔接时的姿态稳定性。可从起身动作前后的日志定位触发阶段；进一步记录 IMU roll/pitch、当前动作完成状态和实际横向误差，区分测量摇摆与动作过渡问题。新的诊断日志或切换策略应作为独立实验。

更快步态需要单独标定位移、偏航和恢复表现，再接入带球；现有 Sprint 测量仍不能作为可靠加速依据。
