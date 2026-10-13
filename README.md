# Webots Robotics TDP

Webots机器人足球开发工程。当前实现包含几何配置、部分裁判规则、共享角色策略、近球导航、关节动作、相机估球实验和测试工具。稳定四对四和真实硬件验证尚未完成。

入口：[运行](docs/RUN.md) · [验证状态](docs/VALIDATION.md) · [发布清理](docs/PUBLICATION_AUDIT.md) · [来源与许可](THIRD_PARTY_NOTICES.md)。

下方为完整技术过程记录，独立副本见 [PROJECT_HISTORY.md](PROJECT_HISTORY.md)。

## 配置、实现与调试记录

记录日期：2026-10-13。项目目录名称：`Webots_Robotics_TDP`。

本文记录环境配置、场景复现、模型与控制修改、失败实验、验证结果和待完成事项。早期完整安装终端记录未全部保存，安装命令属于按已确认环境重建的复现步骤。测试结果依据保存的 JSON、日志与场景图像。

## 1. 当前状态

- 仿真世界：`Wenao/worlds/naotdp.wbt`。
- 运行环境：Ubuntu 20.04.6、Webots R2023b、Conda Python 3.10.22。
- 主流程：Webots Controller API、共享 Python 策略、预设关节动作与 Supervisor 裁判。
- 默认观测：Supervisor 真值；可选相机估球模式仍依赖 Supervisor 定位。
- 无对手连续进攻场景曾在147.16秒完成整球入门。
- 可靠四对四、快速稳定步态、完整比赛规则、独立定位和真实硬件部署尚未完成。

本文陈述实现与实验事实，不将单次夹具成功等同于总体性能验收。

## 2. 工程结构与来源

```text
Webots_Robotics_TDP/
├── README.md
├── PROJECT_HISTORY.md
├── IMPLEMENTATION_NOTES.md
├── THIRD_PARTY_NOTICES.md
├── LICENSE
├── requirements.txt
├── requirements-tested.txt
├── Wenao/
│   ├── worlds/naotdp.wbt
│   ├── protos/
│   ├── controllers/
│   └── motions/
├── tests/
├── tools/
├── docs/
├── verification/development/
├── ball_distance_results/
└── nao_ws/
```

来源与署名集中见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。原项目 Git 历史保存在公开目录外；发布快照使用新的本地历史。`nao_ws/` 是保留的 ROS/Gazebo 工作区，当前足球主流程没有启用它。

## 3. 环境版本

| 项目 | 实际版本 |
|---|---|
| Ubuntu | 20.04.6 LTS |
| Webots | R2023b，包版本2023b |
| Python | 3.10.22 |
| 环境 | Conda，名称robotics-tdp |
| NumPy | 1.26.4 |
| OpenCV | 4.9.0.80 |
| Ultralytics | 8.1.4 |
| PyTorch | 2.2.2+cpu |
| torchvision | 0.17.2+cpu |

系统Python未替换。模型权重 `Wenao/controllers/Utils/best.pt` 保留原内容。

## 4. 安装复现步骤

以下命令适用于新环境；已有正常运行的环境无需重建。完整初始安装记录未保留，因此不能将以下命令视为原始终端逐字记录。

从仓库父目录进入项目：

```bash
cd Webots_Robotics_TDP
```

建立独立Python环境：

```bash
conda create -n robotics-tdp python=3.10 pip -y
conda activate robotics-tdp
python --version
command -v python
```

安装已验证的CPU依赖组合：

```bash
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.2.2 torchvision==0.17.2
python -m pip install -r requirements-tested.txt
python -m pip check
```

直接依赖已经固定；传递依赖和Python构建并非完整锁定。原始requirements只给最低版本，直接安装可能得到不同组合。原安装说明漏掉了pip的install子命令，现有命令已修正。

Webots R2023b可从 [官方发布页](https://github.com/cyberbotics/webots/releases/tag/R2023b) 获取。下载Ubuntu安装包后，以实际路径替换示例：

```bash
sudo apt-get install /path/to/webots_2023b_amd64.deb
command -v webots
dpkg-query -W -f='${Version}\n' webots
```

Miniconda和Webots的初始下载日志没有完整保存；当前版本和实际运行记录已经确认。

## 5. 启动世界与配置解释器

```bash
conda activate robotics-tdp
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH PYTHONNOUSERSITE=1 webots Wenao/worlds/naotdp.wbt
```

环境清理仅作用于本次进程，避免继承其他Python、ROS或Qt路径。

Webots的Python command应使用以下命令输出的可执行文件路径：

```bash
python -c "import sys; print(sys.executable)"
```

设置需要指向python文件，而非仅指向bin目录。控制台Starting controller后的解释器可用于确认实际路径。`controller`模块由Webots提供，普通终端的导入失败不能作为安装同名PyPI包的依据。

首次打开保持暂停，检查资源加载、八个球员和Supervisor，再开始运行。原始证据显示九个控制器均已启动、仿真时钟推进、机器人位置变化；这只证明运行链路建立。

## 6. 原版运行中的诊断现象

| 现象 | 含义与处理 |
|---|---|
| Starting controller信息 | 进程启动信息，不能证明行为有效 |
| LHand/RHand not found | 动作文件包含当前模型没有的通道；原版忽略通道，后续加载器过滤并记录 |
| Ball Distance/Angle连续打印 | Supervisor调试数据，不是视觉准确率证明 |
| 黑色摄像头叠加框 | 暂停、设备未启用或无新图像时可能出现；可关闭UI叠加显示 |
| 重载前保存弹窗 | 保存会改变磁盘世界；恢复已保存初始条件时使用Close without Saving |
| 暂停与退出 | 暂停用于观察，关闭窗口用于结束；自动测试脚本处理Ctrl+C并保存已有输出 |
| 画面模糊 | 与视角、纹理和图像分辨率有关，不能单凭画面推断GPU状态 |

Webots渲染、物理/控制计算与YOLO推理是不同任务。CPU版PyTorch不表示Webots未使用GPU渲染。601.08秒仿真曾用约427秒墙钟时间，平均约1.4倍实时；快进不会自动增加每秒仿真时间内的机器人位移。

原版由规则/状态机、A*、局部避障、YOLO/OpenCV与关节动作组成，没有完成足球决策学习系统。

## 7. 几何配置与原版差异

| 参数 | 当前值 |
|---|---:|
| 球场长×宽 | 9×6 m |
| 边界带 | 1 m |
| 地面长×宽 | 11×8 m |
| 球门净宽×净高×深度 | 2.6×1.2×0.6 m |
| 球门区 | 1×3 m |
| 罚球区 | 2×5 m |
| 罚球点距球门线 | 1.5 m |
| 中圈外径 | 1.5 m |
| 足球半径 | 0.07 m |
| 步长 | 40 ms |

原球场白线内长宽已有9×6 m，主要差异是球门、场线区域、边界和初始姿态。原球模型半径接近现值，明确错误之一是视觉球直径0.48 m。

新增本地CourseSoccerField与CourseGoal，主世界引用本地模型；原周边碰撞墙移除，球员直立从场内阵型开始，最终门框为白色。Webots安装资源没有被修改。

整球判定要求向外穿过x=±4.57 m，并在插值越线位置检查球完全通过门宽和横梁。仅球心过线、返回场内或从横梁上方通过不算进球。

球质量、摩擦、回弹与NAO6质量/惯量尚未完成独立标定。

## 8. 工具、视觉和模型修正

- 权重路径改为相对ImageServer.py定位。
- 视觉球直径统一为0.14 m，焦距由相机宽度和实际FOV计算。
- 图像转换匹配BGRA缓冲，队列、线程初始化和CSV混合字段处理修正。
- A*统一0.1 m网格、[y,x]数组索引、起点到终点路径顺序；当前共享导航不调用旧A*角色代码。
- 旧IMU朝向与当前坐标系不一致且pitch轴关闭，曾使直立机器人误入恢复；现为躯干对齐并启用相关轴。
- 动作加载器过滤缺失通道，裁剪到模型电机限位，站立从当前目标角度过渡。

原CSV/线程/队列部分问题最初来自静态风险检查，不能写成原版每项都曾实际报错。后续测试覆盖修正逻辑。

## 9. 当前控制结构

| 模块 | 职责 |
|---|---|
| CourseSpecs | 尺寸与整球几何 |
| MatchEngine | 比赛阶段、时间、换边、重开与部分规则 |
| SupervisorBase | 仿真裁判适配、接触近似、处罚、广播和轨迹 |
| ProcessSupervisor | V2 JSON验证与状态保存 |
| TeamPolicy | 角色、追球权、带球、传球、射门、守门 |
| SoccerController | IMU、接收、动作加载与执行 |
| HeadingFilter | 环绕角度平滑 |
| Navigation | 接近、身体坐标调整、连续推进和站位滞回 |
| ImageServer/VisionGeometry | 带时间与姿态的检测和球估计 |

八个球员入口共用SoccerController；原角色文件存于legacy，作为对照而非新版独立入口。

## 10. 裁判、观测与部署限制

阶段包括INITIAL、READY、SET、PLAYING、STOPPED、PREPARE、HALFTIME、FINISHED。规则实现覆盖初始开球队/方向、换边、整球出界、部分重开与计分限制、静止球、非法站位、重启距离以及长期倒地/场外移除。

完整推搡、阻挡、手球、持球、禁区人数、牌罚、罚球、换人、暂停与赛事流程尚未完成。

生产流程使用updateMatch而非旧兼容判球方法。重开由状态机组织；测试的半场摆阵型不代表正式比赛中的自主换边。

广播version=2包含球、机器人、时间、比赛和处罚。无效/非有限数据被拒绝，保留上次有效状态。接触点归属是近似，同时接触仍有歧义。

pass_intent记录发送者、接球者和超时，接球者接应、传球者让出追球权。Webots通信尚未替换成真实网络。

默认观测为Supervisor真值；vision模式仅将相机估球接入决策，定位仍来自Supervisor。丢球或过期会停止。投影使用采集时姿态和头部角度，并假设躯干直立。

真实固件、SDK、机载部署、独立定位、网络和硬件适配尚未验证。NAOqi/libqi仅为候选接口。

## 11. 早期验证

逻辑检查从参数阶段扩展到23、25、32，最后为33个。现存证据保留早期23个与最终33个日志，数量不等于行为成功率。

几何、整球判定、非法站位和重启距离场景通过。基础物理夹具分别检查近距射门、带球位移和接球者触球。

实际底部相机/YOLO静止球场景：置信度约0.926、平面误差约0.01003 m。仅一个场景，不是完整相机或真机标定。

## 12. 60秒半场问题

最初开发测试为60秒半场、READY2秒、SET1秒、静止球30秒重开。121.04秒完成，比分0:0；球轨迹0.07566 m，没有触球归属转换。

首次重开四名前锋被移到场边，换边后八个球员来不及返回合法半场，共12次开球站位移除。60秒配置可以检查生命周期，但不足以观察慢步态完整比赛。

max_displacement可包含裁判摆放，不能当真实行走能力。

## 13. 测试时长与放球修正

加入half-seconds、ready-seconds、stuck-seconds、reset-formation、visible和timeout参数。检查退出码、完成标记和异常，并保存控制台输出；中断会停止进程。

放球分离阈值从0.5 m改为0.25 m，避免误移球后0.3 m的合法开球队员；对手距离限制独立执行。

120秒半场、READY10秒、静止球120秒、半场夹具摆阵型的复测：241.08秒完成，PLAYING约218秒，零站位移除，球轨迹6.539 m，14次触球归属转换，3次pass/2次dribble尝试，0:0，20次恢复尝试。

实验时长、夹具和控制同时变化，不能单独归因于算法。一次新裁判检查曾读取step更新前的位置而失败，同步步骤修正后通过；退出码不能代替完成标记。

## 14. 300秒半场基准

300秒半场、READY45秒、静止球120秒、seed27、半场夹具摆阵型：601.08秒完成，PLAYING约460秒，球轨迹12.763 m，24次触球归属转换，22次恢复尝试，0:0。

全部球员连续走路片段中位数0.44秒，两名前锋约0.54/0.56秒。SHOOT意图转换15次，实际shoot动作0次；pass2次、dribble4次。近球的小目标点、到点与朝向条件造成反复调整。

## 15. 动作实测

| 动作 | 观察窗 | 实际结果 |
|---|---:|---|
| ForwardLoop | 8 s | 前进0.682 m，约0.085 m/s |
| Forwards50 | 8 s | 前进0.435 m，约0.054 m/s |
| Sprint | 8 s | 前进0.298 m，约0.037 m/s；偏航约-61° |
| Backwards | 8 s | 后退约0.273 m |
| 左/右侧移 | 各8 s | 约0.102/-0.178 m |
| 左/右转10 | 各4 s | 约4.45/-16.19° |
| 左转20/40 | 各4 s | 约16.87/38.83° |
| 右转20/40 | 各4 s | 约-17.35/-16.40° |

转向观察窗不等于动作文件时长。Shoot约4.8 s、LongPass约3.299 s、Forwards50约6.76 s、左转180约9 s。测量为单次模拟值，不是硬件或统计标定。

当前导航固定使用已测连续步行，Sprint不作为速度开关。右转大角度分段使用右转20，避免仅按文件名选择。

## 16. 导航改写与配对复测

近球导航改为从球后方接近、面向预计球路、身体坐标侧移/后退、射门前站稳和持续带球。角色站位采用滞回，行走保留完整周期，安全与停止条件优先。共同last_touch暂保追球权，CLEAR朝前。

| 指标 | 基准 | 导航版本 |
|---|---:|---:|
| 连续walk片段中位数 | 0.44 s | 1.36 s |
| 恢复动作尝试 | 22 | 16 |
| 球路径 | 12.763 m | 14.757 m |
| 触球归属转换 | 24 | 36 |
| pass尝试 | 2 | 12 |
| shoot尝试 | 0 | 0 |
| 比分 | 0:0 | 0:0 |

同一时长/种子的配对改善部分效率，但未形成可靠攻击。该轮发生在最后射门时机修改之前，不证明最终战术整场已验证。

## 17. 连续攻击失败与修正

单人攻击夹具：初始机器人约[0.5,-0.15,0.334]，球约[1.2,0,0.07]；其余机器人旁站，随后只用关节动作移动。

旧规则在进攻方向x>1.8 m就射门，但已测近距射门只推动球约0.4 m。180秒内仅到球x约3.546 m，未进球，实验明确失败并保留日志。

改为朝球门开口最近可用点带球，距目标小于0.5 m再射门。最终147.16秒完成整球进门，球末位置约[4.578,-0.781,0.070]，仅RedForwardA接触。

最终基础夹具结果：近距射门推进0.406 m并越线，带球最大位移约1.045 m，接球者触球。33个逻辑检查与裁判回归通过。

连续攻击成功仅覆盖一个无对手场景，速度仍慢。最后射门策略尚未整场复测。

## 18. 连续攻击耗时

按动作启动到下一动作或结束的日志估算，含初始化：

| 动作 | 时间 | 次数 |
|---|---:|---:|
| walk | 55.80 s | 24 |
| 左右侧移 | 59.28 s | 39 |
| 普通转向 | 13.92 s | 9 |
| recover_back | 6.80 s | 2 |
| shoot | 8.48 s | 2 |
| stand | 4.48 s | 5 |

此表不是精确技能完成时间，恢复命令不等于完整跌倒统计。

## 19. 安装脚本比较

另有一个外部安装脚本，面向Ubuntu22.04、venv和相同Webots/Python基线，完成系统包、固定依赖、模型加载检查与启动入口生成。

对原始源文件只有两项修正：ImageServer权重路径改为相对目录，WorldInfo步长设为40 ms；另外生成九个runtime.ini。该安装流程不包含现有几何、判球、导航与进攻修改。下载哈希检查和黑图YOLO推理不构成足球行为验证。

## 20. 当前复测命令

所有output目录必须新建命名，历史目录不能混用。命令在仓库根目录、robotics-tdp环境中执行。

```bash
python -m unittest discover -s tests -p 'test_*.py'
python tests/run_webots_check.py --output runs/new_geometry_01
python tests/run_webots_check.py --skills --visible --output runs/new_skills_01
python tests/run_webots_check.py --attack --visible --output runs/new_attack_01
python tests/run_webots_check.py --motions --visible --output runs/new_motions_01
python tests/run_webots_check.py --vision --output runs/new_vision_01
```

较长四对四开发观察：

```bash
python tests/run_webots_check.py --match --half-seconds 300 --ready-seconds 45 --stuck-seconds 120 --reset-formation --visible --seed 27 --output runs/new_match27_01
python tools/evaluate_run.py runs/new_match27_01 --output runs/new_match27_01/metrics.json
```

完成标记分别为COURSE_CHECK_OK、SKILL_CHECK_OK、ATTACK_CHECK_OK、MOTION_CHECK_OK、VISION_CHECK_OK和MATCH_CHECK_OK，含义取决于各测试门槛。

默认match测试仍为60秒半场、READY2秒、静止30秒，只适合生命周期检查。reset-formation仅在半场开始摆阵型，不算自主换边；seed主要改变方向/开球队，并非完整随机场景。

正式默认配置半场600秒、启动120秒、READY45秒、SET5秒，首次PLAYING约在170秒；READY/SET计入半场时钟。默认配置也不表示完整规则已验收。

## 21. 指标与证据解释

| 字段 | 含义与限制 |
|---|---|
| commands | 动作尝试而非成功 |
| decision_transitions | 策略意图而非动作实际播放 |
| contact_transitions | 接触近似的last_touch转换 |
| ball_path_metres_sampled | 排除记录到的裁判放球，不等于净向球门推进 |
| robot_path_metres_sampled | 含躯干摆动，不是标定速度 |
| fallen_removal_penalties | 长期倒地处罚，不是全部跌倒 |
| setup_removals | 开球非法站位移除 |
| fixture_formation_count | 测试摆放次数 |
| median_walk_bout_seconds | walk片段中位数 |
| command_seconds_all_phases | 含等待阶段的命令时间估算 |

manifest保存环境、种子和历史源码散列。发布证据已脱敏并标记，原实验散列不代表当前整理后的文件。单人attack采用几何进球判定，不执行正式计分流程，scored结果与正式goals字段不同。

公开精选证据位于[verification/development](verification/development/README.md)。原始运行目录和未经处理的日志在公开目录外保存。

## 22. 后续验证与优化

- 降低近球横向调整次数，带球和射门采用独立容差，检验滞回。
- 改善动作切换过渡，减少恢复和重新接近。
- 开发更快且经过偏航/平衡/接触测量的步态。
- 扩大初始位置、偏移、朝向和球速；同场景单变量对比。
- 逐级进入传接球、一对一、四对四与视觉实验。
- 标定NAO6物理参数、相机外参、球摩擦/回弹和真实控制接口。

将同一场景从147秒降到100秒以内属于开发目标，尚未实现。稳定进球、最终策略整场复测、完整裁判、独立定位和真机迁移仍未完成。

## 23. 关联资料

- [运行说明](docs/RUN.md)
- [验证状态](docs/VALIDATION.md)
- [部署状态](docs/DEPLOYMENT_STATUS.md)
- [实现说明](IMPLEMENTATION_NOTES.md)
- [发布清理记录](docs/PUBLICATION_AUDIT.md)
- [第三方来源和许可](THIRD_PARTY_NOTICES.md)
- [初期证据](verification/development/README.md)
- [时长问题证据](verification/development/test-timing/README.md)
- [导航与攻击证据](verification/development/navigation/README.md)

后续实验记录应包含日期、源码版本、配置、初始条件、命令、成功门槛、输出目录、失败情况和结论。建议与尚未执行工作均应明确标记。
