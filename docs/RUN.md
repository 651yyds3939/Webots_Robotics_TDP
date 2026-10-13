# 运行 Webots 足球仿真

环境：Ubuntu 20.04、Webots R2023b、Conda Python 3.10（本机 robotics-tdp）。仿真入口仍是 Wenao/worlds/naotdp.wbt。

```bash
cd Webots_Robotics_TDP
conda activate robotics-tdp
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH PYTHONNOUSERSITE=1 webots Wenao/worlds/naotdp.wbt
```

Webots 的 Python command 应设置为通过 `python -c "import sys; print(sys.executable)"` 获取的解释器路径。按播放键后查看顶部状态：INITIAL → READY → SET → PLAYING。默认初始启动 120 秒、READY 45 秒、SET 5 秒，使用仿真时间；可按快进加速。每半场 600 秒，半场换边后再开球，FINISHED 停止球员。默认球门框为白色，红蓝由球衣区分。

`Wenao/controllers/Utils/globalconfig.ini`：

- `[Match]` 给出所有时间和随机种子。缩短时间只用于开发测试，不代表默认比赛参数。
- `[Controller] Observation=supervisor` 为默认战术开发模式。
- `Observation=vision` 为“摄像头估球＋Supervisor 定位”的混合实验模式，需视觉依赖；丢球或估计过期会停止，不暗中改用球真值。尚未完成视觉准确率验收。
- `DisplayVision=False` 默认不弹出 OpenCV 窗口。
- 当前导航固定使用 ForwardLoop 的连续步行。旧 Sprint 参数保留兼容，本次动作测量发现该资产严重朝向漂移，不作为新版导航的速度开关。
- 原有 `[RedTeam]`、`[BlueTeam]` 和各球员的参数保留给 legacy 对照；新策略的阵型由 TeamPolicy.home 管理，旧的 Vision/Strategy/PlayerMode 不控制新入口。

运行生成 `runs/match-*.jsonl`（轨迹、比赛事件）和 `runs/player-*.jsonl`（策略转换、动作尝试、动作加载修正）。它们已被 Git 忽略。`TDP_RUN_DIR` 可指定独立实验输出目录，`TDP_MATCH_SEED` 可覆盖随机种子。每次硬件/视觉验证都应保存实际配置和日志。

传球意图由机器人通过 Emitter 广播，接球者接应、传球者暂时让出追球权；收到实际接触消息或超时后退出。该模拟通信仍需迁移到真实机器人网络。

八个入口调用 `Base/SoccerController.py`。此前的球员文件保留在 `controllers/legacy/` 作参考，旧参数版本和本次修改前版本还有仓库旁 backups/ 的压缩备份。legacy 文件不是独立可运行的新版比赛入口。

停止仿真可以按暂停；退出 Webots 可以关界面。仅改变运行状态时不必保存世界；若保存世界，会记录场景编辑。再次复现实验应重新加载磁盘世界，而不是保存比赛中机器人姿态作为初始条件。

验收状态见 [VALIDATION.md](VALIDATION.md)。

## 开始观察比赛行为（2026-10-13）

`--match` 的旧默认值是每半场 60 秒、READY 2 秒、静止球 30 秒重开，仅适合快速检查程序生命周期。慢步行还未接近球就可能重开，半场换边也来不及走过全场，导致非法站位被移到场边。这种检查通过不代表比赛行为成功。

建议先用下列开发实验观察连续踢球：

```bash
python tests/run_webots_check.py --match --half-seconds 300 --ready-seconds 45 --stuck-seconds 120 --reset-formation --visible --seed 27 --output runs/behaviour_27_01
python tools/evaluate_run.py runs/behaviour_27_01 --output runs/behaviour_27_01/metrics.json
```

每半场五分钟，READY 45 秒计入半场时间；脚本仍使用开发用 SET、半场停顿和启动时长，并非正式默认比赛。所有时长都是仿真时间，窗口使用 fast 模式；实际等待时间取决于机器运行速度。`--visible` 显示窗口，比赛自动开始和结束，无需手动播放。输出目录必须是新的，控制台日志自动保存为 webots.log。

`--reset-formation` 只在两个半场的开始，由**测试夹具**摆放合法阵型和开球队员，避免用比赛观察时间测试跨场重新列队。球员在测量阶段仍通过关节动作走路、转向和踢球。摆放记录为 fixture_formation，不能视作机器人自主走位能力。它不修改 naotdp.wbt 或正式 Supervisor 的比赛配置；需要测试自主换边时去掉该选项，并给足 READY 时间。改变种子主要改变初始攻防方向和开球队，不等于随机生成所有初始场景。

比较 playing_seconds_sampled、setup_removals、contact_transitions、ball_path_metres_sampled 以及画面。机器人轨迹长度包含身体摆动，不等于标定过的步行速度；commands 只是动作尝试，不能当作成功率。若只有几厘米球位移且没有触球，不应因为 MATCH_CHECK_OK 而认定行为已通过。先修正一个具体问题，再用相同种子和时长复测。

当前导航先从预定踢球方向的后方接近球，再面向踢球方向，用侧移/后退调整脚位；射门前先站稳，带球保持面向目标连续推进。角色站位采用到达/离开阈值，减少在目标附近反复转身。navigation 日志记录这些阶段。连续步行保留一个完整步态周期，安全与比赛停止仍优先处理。没有缩短动作时间或调整球摩擦/机器人质量来人为加速，仍需验证稳定性。

可用 `python tests/run_webots_check.py --motions --output runs/motion_01` 在隔离场景测量动作。一次 8 秒试验中，ForwardLoop 约 0.085 m/s，Forwards50 约 0.054 m/s，Sprint 约 0.037 m/s 且朝向漂移约 -61°；不是硬件校准，也不是多次测量均值。左转 20/40 动作约 17/39°，右转 20 动作约 -17°；旧左转 10 和右转 40 分别只有约 4/-16°，新版导航避免根据文件名推断转角。右转大角度分段执行已测量的右转 20。原始动作本身仍慢，后续要单独开发并校准更快且稳定的步态。

## 先观察无人干扰的连续进攻

```bash
python tests/run_webots_check.py --attack --visible --output runs/attack_01
```

一名 RedForwardA 使用真实共享控制器，其他机器人在旁边站立。测试夹具只设置初始位置，随后通过关节动作接近初始 x=1.2 m 的球、推进并射门；整球越过球门线才出现 ATTACK_CHECK_OK，结果保存 attack-result.json。没有 READY 等待，不统计成正式比分或成功率。2026-10-13 的单次实跑在 147.16 秒完成，速度仍慢。

原策略在 x>1.8 m 就射门，但现有射门动作在近球门夹具中仅推动球约 0.4 m，因此反复在远处射门很低效。现在带球朝向球门开口内最近的可用点，距选定目标不足 0.5 m 时才选择射门。射门距离仍需多场景标定。这项最后的进攻策略修改只做了单人连续进攻与基础检查；不能依据此前导航版本的四对四结果宣称最终策略已经整场验证。
