# 仿真验证记录

来源：本地几何配置、实现与保存的仿真测量；裁判实现参考[2025 Humanoid League Rules](https://humanoid.robocup.org/wp-content/uploads/RC-HL-2025-Rules.pdf)。

“已实现”表示代码存在；“已验证”仅覆盖列出的试验。完整规则、行为性能、模型与硬件验证尚未完成。

部署与真实接口状态见 [DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md)。

2026-10-20 的单人稳定性更新：guarded 调度、双脚受力与 IMU 站姿门槛、动作重新起播和球门内部瞄准已进入实际无对手进攻验收；标准站位、镜像站位和球偏移布局均完成无倾倒/恢复且进球的测试，包含进球后停止观察。操作与逐次证据见 [SINGLE_PLAYER_STABILITY.md](SINGLE_PLAYER_STABILITY.md)。此范围不等于四对四或真机稳定性验收。

同日四对四排查完成两场 300 秒半场的配对实验：基线 0:0、5 次恢复命令、4 段倾角超阈值过程；门前回退目标候选 0:1、12 次恢复、8 段超阈值过程。候选未作为默认启用，nearest 仅保留显式实验开关。当前 66 项逻辑测试通过，多人稳定性与实际队内传接球仍未验收；条件、源码和结果见 [MULTIPLAYER_DEBUGGING.md](MULTIPLAYER_DEBUGGING.md)。

带球横向滞回的三次对照实验出现性能退化，候选已撤回，当前导航恢复为基线。六次结果与限制见 [dribble-hysteresis/README.md](../verification/dribble-hysteresis/README.md)。

| 要求 | 实现/证据 | 当前验收状态 |
|---|---|---|
| 两队，各四个机器人 | naotdp.wbt；八个共享控制器入口 | 已运行 |
| 场地 9×6 m、边界带 1 m、场线/禁区/球门区 | CourseSpecs.py、CourseSoccerField.proto | 几何检查；后续需完整参数独立测量 |
| 球门净宽 2.6 m、净高 1.2 m、深度 0.6 m | CourseGoal.proto | 净宽/高 Webots 检查通过；模型净深参数已设置 |
| 足球近似直径 14 cm | 模型 r=.07、视觉同一尺寸 | 几何/针孔投影检查；质量、回弹、摩擦未标定 |
| NAO6 构造、驱动、动力学、运动学 | 继承的 NaoV6.proto | 未完成厂商参数和真机对照，名称不是验证证据 |
| 前锋/后卫/守门员角色 | TeamPolicy.py 固定角色，所有成员计算相同追球者 | 策略单元试验；真实比赛性能待评估 |
| 自主控制，没有外部操作员输入 | SoccerController.py 自动决策、关节 motion 执行 | 已运行；默认Supervisor定位用于开发，独立定位尚未验证 |
| 踢球/带球/传球 | 左脚对准、射门/传球/带球分支，支持位 | 策略逻辑通过；物理夹具记录近距离整球进门、带球位移、接球者触球；稳定成功率未验证 |
| 跑动 | 现用 ForwardLoop，ForwardsSprint 资产保留供测量 | 未完成跑动能力验收；实测 Sprint 朝向漂移，未用于新导航 |
| 拦截/守门 | 有界球速预测、球门线交点预测 | 数值逻辑通过；物理拦截/扑救成功率待验证 |
| 比赛状态、计时、半场换边、终场 | MatchEngine.py | 两个缩短半场集成试验；正式默认每半场 600 s |
| 开球和出界重新开始 | READY/SET/PLAYING，整球越界、边线球、球门球、角球 | 纯逻辑检查；开球非法站位移除、重启距离处罚已加入并通过 Webots 检查；其他违规流程待完善 |
| 整球通过球门才进球 | CourseSpecs.goal_crossing；按半场方向计分 | 几何边界单元试验和 Webots 进球检查通过 |
| 间接重启不能直接进球；开球限制 | MatchEngine 触球追踪和中圈约束 | 纯逻辑检查；触球识别依赖位置近似，需验证 |
| 跌倒或在人工草坪外 20 s，移除 10 s | SupervisorBase.enforce_incapable_players | 已实现；回场位置参数测试仍需扩大 |
| 完整 RoboCup 裁判规则 | 当前自动裁判覆盖部分条款 | 未完成：推搡/阻挡/手球/持球、禁区人数、牌罚、罚球、淘汰赛加时/点球、暂停/换人和完整违规重启处理 |
| 视觉测距与行为连接 | Observation=vision 的混合模式 | 已接入；实际底部相机/YOLO 静止场景检测通过，约 1 cm 平面误差；多场景外参/延迟/准确率待测，定位仍来自 Supervisor |
| 独立部署/真实定位/队友通信 | 策略与 Webots 执行分开；消息有版本和验证 | 没有完整机载定位和真实网络适配，实际接口尚未验证 |
| 模型验证、行为评估和对照实验 | tests/、tools/evaluate_run.py、JSONL 日志 | 自动逻辑、单人重复与布局变化、失败负对照已有记录；对抗覆盖与真机对照未完成 |
| 真实NAO6行为和硬件测试 | 可移植策略，尚无完整硬件适配 | 固件、接口、网络及实际测试尚未完成 |

## 可重复检查

仓库根目录、已激活 robotics-tdp 环境：

```bash
python -m unittest discover -s tests -v
python tests/run_webots_check.py --output runs/geometry
python tests/run_webots_check.py --match --output runs/match-seed27 --seed 27
python tests/run_webots_check.py --skills --output runs/skills
python tests/run_webots_check.py --vision --output runs/vision
python tools/evaluate_run.py runs/match-seed27 --output runs/match-seed27/metrics.json
```

--match 默认使用两段 60 s、启动 0 s、READY 2 s、SET 1 s 的测试配置，仅用于快速验证生命周期。现在可通过 --half-seconds、--ready-seconds 和 --stuck-seconds 设置较长观察实验；--reset-formation 明确使用测试夹具在半场开始放置阵型，不能算自主换边验证。建议行为观察使用 300 s / 45 s / 120 s，详见 RUN.md。每次 --output 使用新目录，避免实验日志混合。正式世界的默认配置不会因此改变。--skills 的位置变化由测试夹具设置，不是机器人算法使用瞬移；测量区间内机器人只通过关节运动影响球。结果分别记录 goal_crossed 和 receiver_contact；单次成功不是稳定成功率。

## 尚需实际完成的验证

- 每种行为建立明确成功条件和超时，至少多种位置/方向/球速并重复试验；记录失败，不把一个场景的球位移当成功率。
- 对模型的关节范围、质量/惯量、步行距离/速度、跌倒与起身、球摩擦/回弹进行厂商数据和实测对照。
- 获取实验室固件、SDK、机器人数量、联网方式；匹配实际接口后实现适配和硬件测试。Python 3.10 不能直接加载旧 Python 2.7 NAOqi 二进制。
- 根据实际部署条件确定可用观测、外部计算与规则范围。

## 本次实际结果（2026-10-12）

- 23 个 Python 自动检查通过；语法解析及 git diff --check 通过。
- Webots 净球门几何、整球进球判定、开球非法站位移除和重启距离处罚检查通过。
- 两个缩短 60 秒半场的生命周期检查通过；seed 27/28 的独立运行都结束于 FINISHED。最新四对四短赛比分 0:0，未证明连续比赛的行为效果。
- 三个物理夹具分别记录近距离射门整球越线、带球推动足球、传球后接球者触球。夹具没有统计稳定成功率；传球场景也有对方后卫触球，不能宣称全程无干扰传球成功。
- 实际底部相机＋仓库 YOLO 模型在静止球场景中检测成功，平面误差约 0.010 m。只覆盖这一个场景。
- 可分享的检查快照保存在 verification/development/；完整原始轨迹存放在发布目录外的私有备份中。这些记录仅覆盖列出的开发试验。

## 测试时长与控制修正（2026-10-13）

25 个 Python 检查通过；正常开球队员不被移开、重叠放球分离和原裁判检查通过；物理射门/带球/接球夹具通过。最新开发试跑使用两个 120 秒半场、READY 10 秒、静止球 120 秒重开及明确的半场开始阵型摆放，完成于 241.08 秒：零非法开球站位移除，球轨迹约 6.539 m，14 次触球归属转换，比分仍 0:0。有 20 次恢复动作尝试，整体稳定比赛性能仍未通过。实验条件与原短赛不同，不能直接将差异归因于朝向控制修改。证据及限制见 [test-timing/README.md](../verification/development/test-timing/README.md)。

## 同日后续：导航与射门时机

33 个逻辑检查通过；近距射门/带球/接球夹具通过。实际测量发现原始连续步行约 0.085 m/s，Sprint 有明显偏航，部分转角不符标称。导航改为身体坐标对齐、首段最短行走时长和位置滞回；相同 300/45/120 秒设置的配对四对四中，走路片段中位数 0.44→1.36 秒、恢复尝试 22→16，但仍 0:0，无实际射门。随后修正过早远射：朝球门开口推进，距离目标小于 0.5 m 再射门；真实单球员无干扰连续进攻在 147.16 秒整球进门，速度仍慢。最终射门策略未整场复测，模型/硬件/跑动/多场景成功率仍未验收。完整证据含失败场景，见 [navigation/README.md](../verification/development/navigation/README.md)。

## 发布整理后复测（2026-10-13）

目录改名、路径脱敏和文档整理后，33 项逻辑测试、实际 Webots 几何/裁判集成检查与底部相机检测检查通过。单个静止相机夹具的平面误差为 0.01003 m。全部 Python 源码可解析，项目维护文档的本地链接存在，模型权重内容未改变。运行证据见 [publication/README.md](../verification/publication/README.md)。此次检查不扩展长时间比赛或真实硬件的验证范围。
