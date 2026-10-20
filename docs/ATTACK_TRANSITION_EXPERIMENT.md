# 完整进攻中的选择性站姿过渡实验

2026-10-20。前序隔离回放显示站姿过渡能缓解部分失稳，本实验检查完整单人进攻中的跌倒、进球与总耗时。候选三次完整进攻均退化，未采纳，默认关闭；实验入口保留用于复现。隔离回放成功不能替代此检查。

## 候选规则

`--side-transition phase` 启用实验候选；默认值 `off` 保留原执行流程。候选仅筛选 DRIBBLE 行为下的直行接左/右侧移，且实际播放时间位于动作时长的后四分之一。触发后执行站姿动作至少 1.2 秒，等待该动作完成，然后使用最新决策继续执行。

后四分之一仅为实验筛选条件，尚未标定为安全支撑相位。等待动作完成也不证明身体稳定；该候选未添加脚力反馈、平衡控制或侧倒起身分类。比赛停止、过期观测、丢球和恢复动作可以取消待执行过渡。代码位于 `Utils/SideTransition.py`，由 `SoccerController.act()` 在现有首段行走时长保护之后调用。

单人进攻模式使用真实球员策略和导航，不回放预定动作。初始机器人与球位置、180 秒仿真时限均与原基线相同。测试入口在 manifest 中记录候选模式，并显式清理继承的模式设置，以保证关闭模式确实运行原流程。

## 操作

在仓库根目录、已激活 `robotics-tdp` 的终端执行，两个输出目录均需尚未用于实验：

```bash
# 关闭候选，重新确认原基线。
python tests/run_webots_check.py --attack --visible --diagnostics --locomotion legacy --side-transition off --seed 27 --output runs/attack_transition_base_next_01
python tools/evaluate_run.py runs/attack_transition_base_next_01 --output runs/attack_transition_base_next_01/metrics.json
python tools/analyze_motion_diagnostics.py runs/attack_transition_base_next_01 --output runs/attack_transition_base_next_01/motion-summary.json

# 同一初始条件，启用候选。
python tests/run_webots_check.py --attack --visible --diagnostics --locomotion legacy --side-transition phase --seed 27 --output runs/attack_transition_candidate_next_01
python tools/evaluate_run.py runs/attack_transition_candidate_next_01 --output runs/attack_transition_candidate_next_01/metrics.json
python tools/analyze_motion_diagnostics.py runs/attack_transition_candidate_next_01 --output runs/attack_transition_candidate_next_01/motion-summary.json
```

候选未进球时测试命令会返回非零并保存 `attack-result.json` 与日志；仍应执行后续分析，不能只保留成功运行。重复实验使用 `_02`、`_03` 等新目录，各次启动独立 Webots 进程。

## 判读

- 先看 `attack-result.json` 的 scored 和 seconds_to_end，再比较诊断中的倾角越界及身体高度。
- 比较侧移时长、恢复尝试和过渡耗时。恢复命令数不是独立跌倒数，姿态越界区间也需要结合低位观测判断。
- 球员日志的 `side_transition` 事件记录 begin/release；站姿命令使用 `SETTLE_BEFORE_SIDE` 行为标签。安全中断可能使 begin 没有对应 release，不能直接将所有 begin 计成完成的过渡。
- 相同条件复测用于检查可复现性；即使三次均进球，仍需变更初始球位与机器人朝向，之后逐级加入对抗。当前进攻夹具固定初始位置，仅更换 seed 不能代替空间条件覆盖。

候选需要在保持进球的同时减少失稳，且整体耗时无明显退化，才适合进一步集成。默认模式保持 off；该实验不表明四对四或真机验证完成。

## 实测结果与后续调试

关闭候选重新测量一次，与此前基线的进攻结果完全一致。候选使用三个独立 Webots 进程，结果与失稳时间均一致；四次对照的控制器源码和动作资源相同，区别由记录在 manifest 中的模式开关控制。

| 条件 | 进球用时 | 恢复命令 | 倾角越界区间 | 侧移命令时长 |
|---|---|---|---|---|
| off 基线复测 | 147.16 s | 2 | 1 | 59.28 s |
| phase 候选，每次结果一致 | 162.92 s | 3 | 2 | 46.80 s |

候选完成 16 次站姿过渡，额外等待共 19.20 s；总进攻用时增加 15.76 s（约 10.7%）。虽然侧移命令时长减少，整体耗时与失稳均未改善，不能采纳为优化。54 项逻辑测试通过并不能代替物理行为验收。

候选的首次倾角越界为 114.88–120.48 s，当时执行 SHOOT 状态下的 `step_left`，不是 `Shoot.motion`。此前命令为 111.80 s 直行、112.88 s 右侧移、114.44 s 左侧移。第二次越界为 132.36–134.52 s，处于重新 INTERCEPT 后的侧移衔接。低位采样也确认两段失稳：约 115.12–119.84 s 与 132.64–133.76 s。

下一轮优先隔离候选中的 111–122 s 射门脚位对齐动作链，并与原始基线的 47–57 s 失稳段分别对照。记录身体横向速度、脚力与实际播放相位，测试有稳定性条件的切换、对齐方向保持与姿态适配；每次仅改变一项。当前不继续增加固定等待或修改速度、足球战术与恢复阈值。

完整匿名证据与对比曲线见 [verification/attack-side-transition](../verification/attack-side-transition/README.md)。完整日志保留在本地 `runs/side_transition_20261020_*`。候选未作为默认行为启用，原始默认仿真仍可按 off 模式复现。
