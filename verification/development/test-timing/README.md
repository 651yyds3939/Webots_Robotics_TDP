# 2026-10-13：短时测试与慢关节动作不匹配

基准实验：半场 60 s、READY 2 s、静止球 30 s 重开。球轨迹 0.0757 m、没有记录到触球、12 次 setup_removal。尤其在换边后，八名球员未能在 2 秒内回到新半场，均被移到场边。baseline-metrics.json 来自原始实验日志的重新汇总。

修正测试支持可调时长与明确记录的半场开始阵型摆放；行走添加朝向平滑和远距离转向滞回；裁判放球时只移开距离不足 0.25 m 的机器人，避免误移球后 0.30 m 的正常开球队员。对手距离检查独立保留。

最新验证命令：

```bash
python tests/run_webots_check.py --match --half-seconds 120 --ready-seconds 10 --stuck-seconds 120 --reset-formation --seed 27 --output runs/diagnostic_20261013_timing27_fixed
python tools/evaluate_run.py runs/diagnostic_20261013_timing27_fixed --output runs/diagnostic_20261013_timing27_fixed/metrics.json
```

241.08 s 仿真时间完成，实际 PLAYING 约 218 s；两次 fixture_formation、零 setup_removal，球路径约 6.539 m，四名机器人产生 14 次 last_touch 转换；有 3 次 pass 和 2 次 dribble **动作尝试**。比分仍 0:0，另有 20 次恢复动作尝试，不能宣称稳定比赛或成功传球。较长时长、夹具摆放和控制修改同时改变了实验条件，不能把球路程增加单独归因于控制算法，后续需要控制变量实验。

match-result.json / match-metrics.json / match-manifest.json / match-webots.log / match-final.png 是本轮证据。referee-webots.log 包含正常开球队员不被移开、重叠放球分离及原判球/距离处罚回归。skills-result.json 和 skills-webots.log 显示近距离射门越线、带球约 0.768 m、接球者触球，各自门槛通过；并非多场景成功率。另有 25 个 Python 自动检查通过（原 23 个加 2 个朝向检查）。

开发观察建议半场 300 s、READY 45 s、静止球 120 s；这组设置尚未在本证据中验证。--reset-formation 是测试摆放，不能证明自主换边，且测试的 SET/启动/半场停顿仍与正式比赛不同。正式默认半场 600 s 未被修改。
