# 动作衔接隔离与历史回放

测试通过临时世界加载 `TransitionProbe` 和测试裁判，复用实际 `MotionLibrary` 与模型，不修改比赛球员的导航、动作文件或恢复策略。测试球员按固定时间表播放关节动作，不做战术判断和自动起身。其他球员站在远处。所有摆放与重置均属于测试夹具。

## 运行方法

在仓库根目录、已激活 `robotics-tdp` 环境的终端执行：

```bash
# 11 种短动作组合，每种三次，自动开启运动诊断。
python tests/run_webots_check.py --transitions --visible --seed 27 --output runs/transition_isolation_next
python tools/analyze_transition_run.py runs/transition_isolation_next --output runs/transition_isolation_next/summary.json

# 首次侧倒之前的真实命令历史：四种对照，每种三次。
python tests/run_webots_check.py --transitions --transition-profile replay --visible --seed 27 --output runs/transition_replay_next
python tools/analyze_transition_run.py runs/transition_replay_next --output runs/transition_replay_next/summary.json
```

输出目录必须独立。回放测试需要比短组合更长的时间，默认墙钟超时 600 秒；较慢设备可另加 `--timeout 1200`。Ctrl+C 中止后保留已有记录。`TRANSITION_CHECK_OK` 表示安排的测量均完成，不表示全部动作稳定或足球技能通过。

只测某项时使用 `--transition-case CASE`，该参数可重复指定。默认每项三次，均在同一个 Webots 世界内重置状态；复核全新世界时使用 `--transition-repeats 1` 并分别启动进程：

```bash
python tests/run_webots_check.py --transitions --transition-profile replay --transition-case replay_ball_present_direct --transition-repeats 1 --output runs/replay_fresh_direct_next
python tests/run_webots_check.py --transitions --transition-profile replay --transition-case replay_ball_present_stand --transition-repeats 1 --output runs/replay_fresh_stand_next
```

局部状态重置和全新世界不完全等价。长动作历史中的微小状态差异可能累积成不同身体轨迹，即使命令和播放相位相同；两种复核方式的结果需分别报告。

## 短组合

- 直行、左侧移、右侧移分别执行 8 秒，随后停止播放并保持末目标 1 秒。
- 单次右侧移接左侧移，以及两者间插入 1.2 秒站姿动作。
- 直行从 0、480、840 ms 播放位置开始，持续 1 秒；随后直接接右、左侧移，或先插入 1.2 秒站姿动作。

每次从相同站姿和新的动作缓存开始，机器人置于场地中央，球移至远处。侧移动作 1536 ms，测试时按 40 ms 时间步执行 39 帧，即 1560 ms。实际播放位置和完成状态记录在日志中，不用启动时长代替动作相位。

## 历史回放

`tests/transition_replay.json` 保存固定种子 27 的已接受命令，从 1.68 秒首次走路到 49.60 秒首次失稳前的左侧移动作。命令间隔保持为原始 40 ms 帧数；不回放自动起身，最后的左侧移继续执行并观察保持末目标后的状态。

四种对照使用相同动作历史：原始球位与球移远处，各自配直接切换和在原始 48.04 秒直行接右侧移之前插入 1.2 秒站姿过渡。活动球员初始位置为 `[0.5, -0.15, 0.334]`，原始球位为 `[1.2, 0, 0.07]`。

回放的输入为固定命令，不能证明战术正确。移走球会改变接触和此前身体状态；站姿过渡会增加时间、改变球速及后续姿态。它们用于检验机制，不构成只改变一个瞬时接触力的实验，也不能替代完整进攻回归。

## 判读与证据

`transition-result.json` 保留每项安排、开始/完成确认、躯干最低高度、最低 up 分量、最大空间倾角、位移、偏航以及低位倾倒观测。`motion-*.jsonl` 保存逐帧 IMU、脚力、关节误差与动作切换。`manifest.json` 包含源码、夹具和动作文件的 SHA256；完整日志按既有规则只存于本地 `runs/`。

最大空间倾角为 `acos(up)`，与每个 IMU 轴的阈值不完全相同。低位倾倒观测要求至少三个采样满足高度小于 0.20 m 且 up 小于 0.5；这些采样不要求连续，不作为已标定的独立跌倒计数。尾部保持目标时发生的失稳仍计入测量。

重复的固定条件用于验证可复现性；成功三次不能证明不同球位、朝向、步态历史或真机条件下均稳定。只有候选在隔离测试和完整进攻回归均改善，才适合接入比赛控制器。

## 已完成的测量

2026-10-13 完成 47 项有效对照。短组合未复现原侧倒；完整历史回放在有球和球移远处时均能复现。关键切换前加入站姿过渡的六项重置对照均未出现低位倾倒；全新进程的单独复核同样改善。但有球直接切换的重置重复结果存在差异，尚未验证进攻成功与整体耗时。证据与方法修正见 [verification/transition-tests](../verification/transition-tests/README.md)。

下一项为完整进攻中的选择性过渡候选：记录过渡增加的时间，比较侧移、跌倒、恢复与进球；每种条件使用独立输出目录。当前比赛控制器尚未接入该候选。固定插入 1.2 秒的安排仅用于机制对照，不能据此保证所有动作衔接均安全。
