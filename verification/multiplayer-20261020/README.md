# 四对四首次排查证据

日期：2026-10-20。完整方法见 [四对四调试记录](../../docs/MULTIPLAYER_DEBUGGING.md)。

- `baseline/`：两个 300 秒半场、READY 45 秒、静止球 120 秒、seed 27、半场初始化阵型、guarded、逐步运动诊断。601.08 秒完成，0:0；5 次恢复命令、4 段倾角超过阈值的过程。
- [baseline-ball-path.png](baseline-ball-path.png)：两个半场的球轨迹，颜色表示仿真时间。
- [baseline-first-tilt-cluster.png](baseline-first-tilt-cluster.png)：首次集中失稳前的三名球员及球轨迹。圆半径仅表示 0.15 m 比例，不是碰撞体形状。

- `candidate/`：相同条件的门前 nearest 回退目标候选，601.08 秒完成，红 0:蓝 1；12 次恢复命令、8 段倾角超阈值过程。进球发生于 262.32 秒，主要来自行走推进，不代表射门精度验收。
- `single-regression/`：候选策略的标准单人严格回归，76.24 秒进球，0 恢复，含进球后停止观察。
- `default-single-regression/`：最终默认 centre 模式的独立严格回归，同样在 76.24 秒进球且无恢复。
- [comparison.json](comparison.json)：两场完整汇总与限制；`candidate_default_enabled=false`。候选稳定性未通过，默认仍为 centre，nearest 仅通过显式实验开关复现。
- [comparison-ball-x.png](comparison-ball-x.png)：两个半场中球的 x 坐标对照，非 PLAYING 阶段不连接。
- [checks.txt](checks.txt)：66 项逻辑测试、决策回放与单人回归的检查摘要。
- `baseline/TeamPolicy.py.txt`、`candidate-TeamPolicy.py.txt`：两场运行时的实际策略源码；前者 SHA-256 已与基线清单核对。
- [startup-aborted.json](startup-aborted.json)：一次未进入仿真的加载中断，不计入完整比赛数量。

完整对照在实验开关引入前执行。引入开关后，默认与归档基线、nearest 与归档候选分别在 21,704 个记录状态的球员决策中等价。该回放检查不替代新场景物理测试。

公开清单去除解释器和仿真器的本机绝对路径；完整 JSONL、运动诊断及失败启动记录留在被 Git 忽略的 runs。集成完成、根节点接近和恢复命令都不能直接替代比赛成功率或经过验证的实际跌倒次数。
