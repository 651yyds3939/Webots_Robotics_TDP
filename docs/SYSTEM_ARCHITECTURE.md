# 系统架构与通信原理

核对日期：2026-10-20。范围为当前工作区的 Webots 足球主流程，包括 guarded 单人进攻、可选视觉和测试夹具。代码入口、设备配置和消息字段均以本仓库实际实现为依据。

## 1. 没有 ROS，模块如何连接

当前系统使用 Webots 自带的控制器接口和模拟收发器，不需要 ROS master、ROS topic、ROS service 或 DDS。需要区分以下四类连接：

| 连接范围 | 实际机制 | 典型数据 |
|---|---|---|
| Webots 仿真器与 Python 控制器 | Webots Controller API，包含 `Robot`、`Supervisor`、传感器、电机和 `Motion` 接口 | 传感器读数、场景状态、关节目标、仿真步进 |
| 不同机器人控制器之间 | Webots `Emitter` / `Receiver` 模拟无线设备；应用消息为 UTF-8 编码的 JSON | 裁判世界观测、传球意图 |
| 单个球员控制器内部 | 普通 Python 导入、对象和函数调用 | `world` 字典、`Decision` 对象、动作名、导航阶段 |
| 同一球员的主线程与视觉线程之间 | `queue.Queue(maxsize=3)` 传图像；`Lock` 保护最近检测结果 | BGRA 图像字节、提交时的位姿/头部角度、球检测结果 |

`Emitter` / `Receiver` 是仿真中的设备。`channel=0` 是模拟通信信道编号，不是网络端口，也不是 ROS 话题。项目没有为主流程编写 TCP、UDP、HTTP 或 MQTT 服务；Webots Controller API 底层与仿真器的连接由 Webots 自身封装，不能据此推断 Webots 内部完全不使用操作系统通信机制。

### 1.1 是否属于线性流程或状态机

**单个控制步内按顺序调用多个模块；整个系统属于多个控制器并行运行的反馈闭环，其中包含比赛状态机、规则决策和有状态的动作调度。** 流程图中的上下箭头表示数据或调用方向，不表示所有机器人必须依次运行，也不表示一个动作完成后才读取下一份观测。

| 层次 | 结构 | 对应程序 |
|---|---|---|
| 整个仿真 | 裁判、八个球员并行运行；视觉线程另行异步处理，受仿真步进协调 | Webots、`Supervisor.py`、八个角色入口、可选 `ImageServer.py` |
| 球员的一次控制步 | 顺序调用和条件分支；保护条件可提前返回，下一步继续检查 | `Base/SoccerController.py` 的 `run()`、`receive()`、`act()` |
| 比赛阶段 | 显式保存 `phase`，按计时、进球、出界等条件转移，属于状态机 | `Utils/MatchEngine.py` 的 `step()`、`transition()`、`begin_restart()` |
| 足球决策 | 根据当前观测重新求值的规则分支，输出行为标签；没有强制执行一次拦截、再一次带球、再一次射门的固定序列 | `Utils/TeamPolicy.py` 的 `decide()`、`attack()` |
| 导航与执行 | 保存到达滞回、当前动作、播放进度和收稳信息，按条件切换 | `Utils/Navigation.py`、`Utils/GuardedLocomotion.py`、`SoccerController.play()` |

例如某一步选择 `DRIBBLE`，下一步仍会接收观测并检查比赛、姿态和执行状态。球离开、对手挡住球路或机器人失稳，都可能改变后续处理；未完成动作也可能暂时限制切换。guarded 等待稳定期间仍会推进 `run()` 循环，但可在进入战术决策前返回。

比赛状态机的主要路径如下；这里的阶段名是 `MatchEngine.phase` 的实际取值，不是额外启动的程序。

```text
[Utils/MatchEngine.py] MatchEngine.step()
   |
   +-- 初始化与开球
   |     INITIAL -> READY -> SET -> PLAYING
   |
   +-- 进球后的开球 / 静止球等触发的 DROP_BALL
   |     PLAYING -> READY -> SET -> PLAYING
   |
   +-- 有归属的边线球、角球或球门球等重启
   |     PLAYING -> STOPPED -> PREPARE -> PLAYING
   |
   +-- 第一半场计时结束
   |     当前阶段 -> HALFTIME -> READY -> SET -> PLAYING
   |
   +-- 第二半场计时结束
         当前阶段 -> FINISHED

转移实现：MatchEngine.transition() / begin_restart()
调用来源：Base/SupervisorBase.py : SupervisorBase.updateMatch()
```

半场计时开始后，时间检查优先于普通阶段转移，因此半场结束也可以发生在 READY、SET 或重启阶段。纯文本图只展示主要路径，具体进球有效性、重启归属和时长由实现中的条件决定。

## 2. 普通八人世界：整体架构图

以下为纯文本图，可直接在 Markdown 源码或终端中阅读。连线统一放在行首的 ASCII 缩进区，中文说明放在连线右侧，避免依靠中英文混排后的空格对齐。`[A]` 表示物理仿真反馈回到同一 Webots 仿真器；图中的 Python 模块框不全是独立进程。

图中的 `Base/`、`Utils/`、`Supervisor/` 和角色目录均相对于 `Wenao/controllers/`；`tests/`、`tools/`、`launch.sh` 相对于仓库根目录。标注“Webots 内置”或“Python 标准库”的接口不对应仓库自行实现的同名程序。

```text
================================================================================
Webots Robotics TDP
普通世界：Observation=supervisor
================================================================================

[启动与配置]
   |
   +-- launch.sh / Webots 界面
   +-- 世界：Wenao/worlds/naotdp.wbt
   +-- 模型：Wenao/protos/NaoV6.proto、球场/球门 PROTO
   +-- Webots 根据 controller 字段自动启动控制器
   +-- 配置：Utils/globalconfig.ini / 环境变量
   |
   v
================================================================================
[A] Webots 仿真器进程（Webots 内置引擎）
   |
   +-- 场景树：球场、球门、足球、8 个 NAO、1 个裁判 Robot
   +-- 物理仿真：关节、电机、重力、摩擦、碰撞、球运动
   +-- 设备仿真：IMU、脚底力传感器、相机、Emitter / Receiver
   +-- 图形界面：3D 渲染、比分叠加、控制台
   +-- 基本时间步：40 ms
   |
   | Controller API：读取场景位置、速度与接触
   v
================================================================================
[Python 进程 S] Supervisor/Supervisor.py：裁判循环
   |
   +-- Base/SupervisorBase.py : SupervisorBase.updateMatch()
   |     +-- 读取场景、接触，处理裁判事件与摆放
   |     +-- Utils/MatchEngine.py : MatchEngine.step()
   |           +-- 比赛阶段、计时、判球
   |
   +-- Base/SupervisorBase.py : sendSupervisorData()
   |     +-- observation()：构造 V2 world
   |
   +-- Base/SupervisorBase.py : updateScoreboard()
   |
   v
Base/SupervisorBase.py : sendSupervisorData()
   | Webots 内置 Emitter.send(JSON -> UTF-8 bytes)
   |
   v
================================================================================
[Webots 模拟无线通信：radio，channel=0]
   |
   | 广播完整 world；不是直接下发走路/射门命令
   v
[8 个独立球员 Python 进程]
   |
   +-- 红队入口
   |     +-- RedGoalkeeper/RedGoalkeeper.py
   |     +-- RedDefender/RedDefender.py
   |     +-- RedForwardB/RedForwardB.py
   |     +-- RedForwardA/RedForwardA.py
   |
   +-- 蓝队入口
   |     +-- BlueGoalkeeper/BlueGoalkeeper.py
   |     +-- BlueDefender/BlueDefender.py
   |     +-- BlueForwardB/BlueForwardB.py
   |     +-- BlueForwardA/BlueForwardA.py
   |
   | 以下调用链在每个球员进程中各自运行
   v
Base/SoccerController.py : main() -> SoccerController.run()
   |
   v
Base/SoccerController.py : SoccerController.receive()
   | Webots Receiver -> Utils/ProcessSupervisor.py : SupervisorData.updateData()
   | 取出广播包、校验并缓存 world
   v
Base/SoccerController.py : SoccerController.act(world)
   | 比赛状态 / 数据时效 / IMU 检查
   | Utils/HeadingFilter.py : HeadingFilter.update()
   |
   v
Utils/TeamPolicy.py : TeamPolicy.decide(world) / attack(...)
   | Decision：行为、目标、朝向、踢球意图
   v
Utils/Navigation.py : Navigator.choose(...)
   | action / stage
   v
Base/SoccerController.py : act() / play()
   | 动作切换与站稳检查
   | Utils/GuardedLocomotion.py : before_decision()（仅 guarded）
   v
Base/SoccerController.py : MotionLibrary.get(action)
   | Wenao/motions/*.motion：预设关节轨迹
   v
Webots 内置 controller.Motion -> Webots 电机
   |
   | Controller API：提交关节目标
   v
[A] Webots 物理更新：关节运动、身体姿态、触球与球运动
   |
   +-- Base/SupervisorBase.py：读取新场景状态
   +-- Base/SoccerController.py：读取新传感器数据，进入下一步

[球员间通信支路]
   |
   +-- Base/SoccerController.py : act() 发送 pass_intent JSON
   +-- channel=0 广播，其他球员 Receiver 接收
   +-- Base/SoccerController.py : receive() 检查同队名称
   +-- Utils/TeamPolicy.py : decide() 按接球者选择响应
================================================================================
[记录与离线分析]
   +-- Base/SupervisorBase.py / Base/SoccerController.py -> JSONL
   +-- Utils/MotionDiagnostics.py / Utils/ImageServer.py -> JSONL、CSV
   +-- tools/evaluate_run.py -> 比赛与行为指标
   +-- tools/analyze_motion_diagnostics.py -> 运动诊断报告
================================================================================
```

普通世界由 **1 个 Webots 仿真器进程和 9 个 Python 控制器进程**构成，即 8 个球员控制器和 1 个裁判控制器；启动器、开发终端和第三方库可能另有进程或线程。八个球员共享同一套源代码，各自持有独立的策略、导航、动作和观测对象，不共享同一个 Python `world` 对象。Webots 会自动启动这些控制器，不需要手动打开九个终端。

裁判负责提供观测和执行比赛管理。追球、守门、支援、传球和射门由各球员自己的 `TeamPolicy` 决定。追球者选择依赖共同观测和确定性规则，不是裁判发出统一战术指令，也不是专门实现了一套分布式共识协议。观测或传球意图暂时不一致时，不能保证所有球员在同一时刻得出完全相同的选择。

## 3. 单个球员：进程内调用与运动闭环

八个角色入口均导入 `Base.SoccerController.main()`，角色由机器人名称确定。以下各模块位于同一个球员 Python 进程中。

```text
[角色入口] RedForwardA/RedForwardA.py
   |
   v
Base/SoccerController.py : main() -> SoccerController().run()
   |
   v
[C] Base/SoccerController.py : SoccerController.run()
   | Webots 内置 Robot.step(40)，每步重复
   |
   +-- Base/SoccerController.py : receive()
   |     +-- pass_intent：校验同队、名称、有效期
   |     +-- Utils/ProcessSupervisor.py : SupervisorData.updateData()
   |           +-- 保存最近有效 world
   |
   +-- Utils/MotionDiagnostics.py : MotionDiagnostics.snapshot()（可选）
   |
   | 已有有效 world 才调用 act(world)
   v
Base/SoccerController.py : SoccerController.act(world)
   |
   +-- 过期观测 / 停赛 / 受罚 -> stand
   +-- IMU 非有限值 -> stand
   +-- 过大 roll / pitch -> recover 动作
   +-- Utils/HeadingFilter.py : HeadingFilter.update() -> 滤波 yaw
   +-- 本文件 visual_world() -> 可选视觉估球，详见视觉流程图
   +-- Utils/GuardedLocomotion.py : before_decision()（仅 guarded）
   |     +-- wait：本步提前返回；settle：先站稳；ready：继续
   |
   | 保护条件允许后继续执行
   v
Utils/TeamPolicy.py : TeamPolicy.decide(world) / attack(...)
   | Decision(behaviour, target, face, kick, receiver)
   v
Utils/Navigation.py : Navigator.choose(...)
   | (action, stage)，例如 (step_left, ...)
   v
Base/SoccerController.py : act() / play()
   | 判断能否切换、是否先站稳
   | 保留的可选实验：Utils/SideTransition.py（默认 off）
   |
   v
Base/SoccerController.py : MotionLibrary.get(action)
   | 读取 .motion；过滤关节、裁剪限位
   v
Webots 内置 controller.Motion
   | play() / stop() / setLoop() / setTime()
   |
   v
[Webots 内置引擎] 电机与物理仿真
   |
   | 下一步的 IMU / 脚力 / 位姿 / 球状态
   v
[C] 返回 SoccerController.run() 的下一次循环
```

`TeamPolicy` 与 `Navigator` 之间没有发送 JSON，也没有消息队列。`SoccerController.act()` 先取得 `Decision`，再把这个 Python 对象作为参数传入 `Navigator.choose()`。`Decision.target` / `face` 为平面目标，`action` 是动作字符串，最终由执行层查找动作文件。

默认 `walk` 对应 `ForwardLoop.motion`，`shoot` 对应 `Shoot.motion`，`pass` 对应 `LongPass.motion`。带球行为 `DRIBBLE` 主要通过朝球门方向行走推进，不等于必然播放动作名 `dribble`。`.motion` 为关节目标随时间变化的轨迹，文件名和动作请求本身不能证明移动、传球或射门成功。

guarded 使用 IMU、双脚受力和动作播放进度约束动作切换，避免在明显摇摆时继续对齐或踢球。它是动作调度保护，不是完整的全身动力学平衡控制器；底层仍依赖预设动作和 Webots 电机模型。

## 4. 控制器之间：模拟无线链路

### 4.1 设备与信道

| 设备位置 | 设备名 | 信道 | 当前用途 |
|---|---|---|---|
| 普通世界的 Supervisor Robot | `emitter` | 0 | 广播裁判 V2 世界观测 |
| 每个 NaoV6 | `receiver` | 0 | 接收世界观测和球员广播 |
| 每个 NaoV6 | `emitter` | 0 | 发送传球意图 |
| 每个 NaoV6 | `super_emitter` | 模型默认 2 | 普通足球控制器不使用；衔接测试中改为 7 |
| 衔接测试临时加入的裁判设备 | `transition_receiver` | 7 | 接收测试探针的开始/完成回执 |

`NaoV6.proto` 的 `channel` 字段默认 0，并同时连接普通 `Emitter` 和 `Receiver`。普通世界未覆盖该值。Supervisor 的 `Emitter {}` 使用 Webots R2023b 默认设备设置：设备名 `emitter`、radio 类型、信道 0。节点默认发射距离和波特率均不设有限上限；当前模型未加入真实 Wi-Fi 的带宽限制、拥塞、认证和测得的丢包模型。上述默认值可在安装目录的 `resources/nodes/Emitter.wrl`、`Receiver.wrl` 核对。

红蓝双方共用信道 0，传球意图并非加密的队内私信。JSON 中的 `receiver` 是逻辑接球者名称，不是设备地址；对方控制器通过名称前缀检查忽略该传球意图。普通 Supervisor 没有 `Receiver`，因此球员广播不会由裁判转发，也不会通过此链路直接修改裁判阶段或比分。

### 4.2 裁判广播：V2 world

发送路径为 `SupervisorBase.observation()` → `json.dumps(..., allow_nan=False)` → `.encode("utf-8")` → `Emitter.send()`。接收端使用 `Receiver.getString()` 和 JSON 解析，再进入 `SupervisorData` 校验。

以下是字段结构示例，数值仅用于说明协议，不是运行记录：

```json
{
  "version": 2,
  "time": 12.0,
  "match": {
    "phase": "PLAYING",
    "half": 1,
    "remaining": 590.0,
    "score": [0, 0],
    "red_direction": 1,
    "restart": "KICKOFF",
    "restart_team": "RED",
    "restart_point": [0.0, 0.0, 0.07],
    "released": true,
    "last_touch": "RedForwardA"
  },
  "ball": {
    "position": [1.2, 0.0, 0.07],
    "velocity": [0.1, 0.0, 0.0]
  },
  "ball_owner": "RedForwardA",
  "robots": {
    "RedGoalkeeper": {"position": [-4.15, 0.0, 0.334], "yaw": 0.0, "standing": true},
    "RedDefender": {"position": [-2.1, 0.0, 0.334], "yaw": 0.0, "standing": true},
    "RedForwardB": {"position": [-0.8, 1.5, 0.334], "yaw": 0.0, "standing": true},
    "RedForwardA": {"position": [0.9, 0.0, 0.334], "yaw": 0.0, "standing": true},
    "BlueGoalkeeper": {"position": [4.15, 0.0, 0.334], "yaw": 3.14, "standing": true},
    "BlueDefender": {"position": [2.1, 0.0, 0.334], "yaw": 3.14, "standing": true},
    "BlueForwardB": {"position": [0.8, -1.5, 0.334], "yaw": 3.14, "standing": true},
    "BlueForwardA": {"position": [0.8, 1.5, 0.334], "yaw": 3.14, "standing": true}
  },
  "penalties": {}
}
```

| 字段 | 含义与来源 |
|---|---|
| `version` | 观测协议版本，当前为 2 |
| `time` | Webots 仿真时间，秒；不是系统日期或运行耗时 |
| `match` | `MatchEngine.snapshot()` 的比赛阶段、半场、剩余时间、比分、红队进攻方向、重启和最近触球等状态 |
| `ball.position` / `velocity` | 裁判从场景读取的世界坐标和线速度，单位 m、m/s |
| `robots[name].position` / `yaw` | 八个机器人的世界位置和绕竖直轴朝向，单位 m、rad |
| `robots[name].standing` | 根据模型朝上分量作出的姿态粗判，不是经过验证的稳定站立结论 |
| `ball_owner` | 旧式距离/角度启发式的控球归属估计，不等同于实际触球 |
| `match.last_touch` | 裁判根据接触位置近似归属后记录的最近触球者；当前策略使用这一共享证据 |
| `penalties` | 受罚机器人名称到解除处罚的仿真时刻的映射；未受罚时为空字典 |

机器人位置是模型根节点位置，不是脚底点。世界坐标为 x/y 平面、z 向上；`red_direction=1/-1` 表示红队朝 +x/-x 进攻，蓝队方向相反。球员导航同时使用本机 IMU 的滤波 yaw；并非所有朝向计算都直接照搬广播中的 yaw。

接收处理包含版本、八个机器人位置、有限数值、比赛阶段、比分、方向、重启位置和处罚数据等检查。比已缓存观测更早的时间戳会被拒绝；无效包增加 `rejected_packets`，最近有效缓存保留。主循环排空当前接收队列后，使用最后接受的有效 world。缓存比当前仿真时间旧超过 0.4 秒时，执行层请求 `stand / STALE_DATA`。

这是输入格式与时效检查，不是身份认证。当前没有为世界广播实现数字签名、可信发送者校验、序列号或应用层 ACK/重传。`ProcessSupervisor.py` 虽然名称包含 Process，实际只是每个球员进程中的解析类，不会创建额外的裁判进程。

旧 CSV 格式仍保留诊断解析，但不会构造完整 V2 `world`；当前主循环不能仅靠旧 CSV 观测运行新版策略。任意测试消息也不会自动成为有效世界观测。

### 4.3 球员广播：pass_intent

实际开始播放射门/传球动作、且 `Decision.receiver` 非空时，球员广播下列结构。当前策略通常在传球时设置接球者；普通无接球者的射门不会发送此包。

```json
{
  "kind": "pass_intent",
  "sender": "RedForwardA",
  "receiver": "RedForwardB",
  "expires": 36.0
}
```

`expires` 为绝对仿真时刻，发送时设置为当前时间加 24 秒。接收端要求发送者和接球者为已知、不同的同队机器人，并要求有效期为有限数值，落在当前时刻至未来 25 秒之间。满足条件后，本地策略可以令接球者 `RECEIVE_PASS`、传球者 `SUPPORT_PASS`，其他队员相应让出追球权。

超过有效期，或裁判观测的 `last_touch` 已变为接球者后，本地意图退出。此处没有独立的“接球成功 ACK”消息；状态来自后续世界广播。意图也没有唯一编号、完成协商和可靠重发，多个有效意图可能覆盖本地缓存。广播表示传球尝试，不保证球确实到达接球者。

## 5. 可选视觉：同进程线程与队列

`[Controller] Observation=vision` 时，每个实际运行 `SoccerController` 的球员启用自己的底部相机和 `ImageServer`。`ImageServer` 创建的是 `threading.Thread`，使用 `queue.Queue` 和 `threading.Lock`；没有创建视觉子进程，也没有启动 HTTP 图像服务器。

```text
================================================================================
[一个球员 Python 进程：Observation=vision]
================================================================================
[主线程] Base/SoccerController.py : SoccerController.visual_world()
   |
   +-- Webots 内置 Camera.getImage()：读取 CameraBottom
   +-- 记录位姿、头部角度和提交时间
   |
   | Utils/ImageServer.py : ImageServer.send(image, metadata)
   v
Python 标准库 queue.Queue(maxsize=3)
   | 满时丢弃一个旧项，再尝试放入新项
   v
[后台视觉线程] Utils/ImageServer.py : ImageServer.run()
   |
   +-- OpenCV cv2.cvtColor()：BGRA -> BGR
   +-- Ultralytics YOLO.predict()：Ball，confidence > 0.5
   |     +-- 权重：Utils/best.pt
   +-- 框宽 -> 光轴深度；框中心 -> 视线方向
   +-- ImageServer.save_data_to_csv()：保存视觉 CSV
   |
   v
Utils/ImageServer.py : self._latest
   | Python 标准库 threading.Lock 保护读写
   |
   | 主线程调用 Utils/ImageServer.py : ImageServer.latest()
   v
[主线程] Base/SoccerController.py : visual_world()
   |
   +-- 无结果 / 提交时间距当前超过 0.8 秒 -> stand / BALL_LOST
   |
   | 有效结果
   v
Utils/VisionGeometry.py : ball_world_position(detection)
   | 使用提交时的位姿、头部角度、假定相机外参
   v
Base/SoccerController.py : visual_world() 返回估计 world
   | 替换 ball.position，ball.velocity=[0,0,0]
   |
   v
Utils/TeamPolicy.py : TeamPolicy.decide()
   |
   v
Utils/Navigation.py : Navigator.choose()
================================================================================
  Supervisor 广播仍提供机器人位置、对手位置和比赛状态
  相机原图和检测结果没有通过模拟无线链路发送给队友
================================================================================
```

检测模型在 `ImageServer` 初始化时加载，检测循环在后台线程执行。队列传递同一 Python 进程内的数据项，没有项目自行实现的图像网络传输协议；结果通过加锁读写 `_latest` 交接，不是另一个 ROS 发布者。所有八个球员同时启用视觉时，各自加载模型并创建视觉线程；不是八个球员共用一个中央 YOLO 服务。

相机采样周期为 `4 × 40 ms = 160 ms`。普通球员的 `visual_world()` 可在每个控制步提交一次，因此可能重复提交相机缓存中的同一帧；队列只在满时移除一个旧项，并不会保证每次推理都直接取得绝对最新帧。检测频率取决于实际推理耗时。

提交信息中的 `time` 是调用 `visual_world()` 时的仿真时间，`pose` 来自当前缓存的裁判广播；不是硬件相机曝光时间戳或严格同步的多传感器采样。此限制与固定外参、直立身体等投影假设，会影响运动中的测距准确率。当前是“相机估球＋外部真值定位”的混合模式，不是独立视觉定位、SLAM 或完整真机感知系统。

`ball_distance = BALL_DIAMETER × focal_length / box_width` 估计的是光轴深度；随后再结合视线和位姿投影到世界平面。没有通过 TF/TF2 广播坐标树。丢球时请求停止，不会悄悄改回真值球位；视觉推理发生异常时线程停止，结果会随时间过期。

## 6. 一次控制步的时序

```text
[仿真时间] t -> t + 0.04 s -> t + 0.08 s -> ...
   |
   +-- Webots 内置引擎：物理与设备更新，推进控制步
   |
   +-- Supervisor/Supervisor.py：裁判 step 返回后运行
   |     +-- Base/SupervisorBase.py : updateMatch()
   |     |     +-- Utils/MatchEngine.py : MatchEngine.step()
   |     +-- Base/SupervisorBase.py : sendSupervisorData()
   |     +-- Base/SupervisorBase.py : updateScoreboard()
   |
   +-- Base/SoccerController.py : run()：球员 step 返回后运行
   |     +-- receive() -> Utils/ProcessSupervisor.py : updateData()
   |     +-- act()：读取传感器，检查保护条件
   |     +-- Utils/TeamPolicy.py : decide() -> 战术决策
   |     +-- Utils/Navigation.py : choose() -> 动作建议
   |     +-- 本文件 play() -> Webots Motion：条件允许时执行
   |
   +-- 下一控制步重复上述循环

[视觉线程] Utils/ImageServer.py : ImageServer.run()
   |
   +-- 从队列取图 -> YOLO.predict() -> 更新 _latest
   +-- 不等待每个物理步，也不要求与控制步一一对应
```

图示表达循环关系，不保证裁判与八个球员在同一仿真步中的执行先后，也不保证新包一定在本步已可读。接收队列、时间戳、缓存和过期保护用于处理这一边界。正常运行时基础步长对应每仿真秒 25 步；guarded 收稳等待、动作完成限制等会使策略和动作切换频率低于 25 Hz。

| 项目 | 当前节奏 |
|---|---|
| 物理基本步长、球员循环、IMU、启用后的脚力传感器 | 40 ms 仿真时间 |
| 普通裁判世界广播 | 每个 40 ms 裁判循环一次 |
| 相机采样 | 160 ms 仿真时间 |
| YOLO 结果更新 | 后台线程异步完成，无固定推理频率 |
| 裁判 `sample` 日志 | 距上次记录至少 0.2 秒，或已 FINISHED；不等于每步原始观测 |
| 球员 decision / command / navigation 日志 | 相应事件或状态变化时记录，不是每步重复写入 |
| 可选 MotionDiagnostics | 主循环逐步采样，并在动作切换前后追加快照 |

40 ms、0.4 秒和 0.8 秒均按仿真时间判断。fast 模式下现实耗时由硬件和计算负载决定；界面的 0.99x、2x 等速度不是通信频率。暂停会停止正常仿真时间推进；系统不提供真机级硬实时保证。

## 7. 测试夹具与普通世界的区别

`tests/run_webots_check.py` 创建临时 Webots 工程，链接现有模型、动作和控制器，把临时世界中的 `Supervisor` 替换成 `CourseCheck`。按模式替换部分球员入口；原始 `naotdp.wbt` 不因此被重写。

```text
[tests/run_webots_check.py：外部测试启动进程]
   |
   +-- 创建临时工程与配置、保存 manifest
   +-- 启动 Webots，收集 stdout/stderr 到 webots.log
   |
   v
临时 worlds/check.wbt
   |
   +-- --match
   |     +-- tests/webots_match_check.py -> CourseCheck.py
   |     +-- 8 个角色入口 -> Base/SoccerController.py
   |     +-- 默认 legacy
   |
   +-- --attack
   |     +-- tests/webots_attack_check.py -> CourseCheck.py
   |     +-- tests/attack_fixture_spec.py：测试布局定义
   |     +-- RedForwardA/RedForwardA.py -> Base/SoccerController.py
   |     |     +-- 默认 guarded
   |     +-- tests/webots_motion_probe.py -> MotionProbe.py（7 个）
   |
   +-- --transitions
         +-- tests/webots_transition_check.py -> CourseCheck.py
         +-- tests/transition_cases.py：动作计划定义
         +-- tests/webots_transition_probe.py -> TransitionProbe.py
         +-- tests/webots_motion_probe.py -> MotionProbe.py（7 个）
```

| 入口 | 控制与通信差异 |
|---|---|
| 普通世界 / `launch.sh` | 8 个实际球员＋正式 Supervisor；未设置 `TDP_LOCOMOTION` 时为 legacy；默认观测来自 supervisor |
| `--match` | 8 个实际球员＋比赛夹具；可缩短时钟、选择测试阵型摆放；默认 legacy |
| `--attack` | 仅 RedForwardA 使用完整球员控制器，其余七个为旁站 MotionProbe；普通入口默认 guarded 并要求无摔倒验收 |
| `--motions` | 用 MotionProbe 响应 `kind=motion_probe` 和 `action`，直接测量指定动作，不是足球战术闭环 |
| `--transitions` | channel 0 下发 `kind=transition_plan`，包含 case、repeat、segments；探针用独立 `super_emitter` 在 channel 7 回传 `transition_status` 的 started/completed 回执 |
| `--vision` | RedForwardA 换为固定场景 VisionProbe；复用 ImageServer 线程和视觉投影，执行检测诊断，不等于完整八人视觉比赛 |

单人进攻场景仍然包含九个控制器进程，只是只有一个在执行足球决策。控制台出现七个 `MotionProbe` 启动行属于预期。guarded 的单人验证不能自动扩展为普通八人世界、四对四或真机已验证。

channel 7 回执是衔接测试专用协议，普通比赛没有该接收设备。模型中的普通 emitter/receiver 共用同一 PROTO channel 字段；测试使用独立 `super_emitter` 发回执，避免状态重置影响命令接收信道。

## 8. 配置、文件与日志不属于实时消息总线

| 文件或配置 | 如何使用 | 是否实时通信 |
|---|---|---|
| `naotdp.wbt`、`.proto` | Webots 加载场景、模型、设备和控制器名称 | 场景定义 |
| `globalconfig.ini` | 控制器构造时读取比赛和观测设置 | 启动配置；修改文件不是实时切换命令 |
| `TDP_LOCOMOTION`、`TDP_SIDE_TRANSITION` | 控制器启动时选择执行路径 | 继承的环境变量；不是机器人间消息 |
| `TDP_FINISHING_AIM` | `centre` 为基线默认；`nearest` 为整体稳定性未通过的近门目标实验，运行器用 `--finishing-aim` 显式设置 | 启动配置；不是实时战术指令 |
| `TDP_MATCH_SEED`、`TDP_RUN_DIR` | 随机种子覆盖和日志目录 | 启动配置 |
| `.setup/python-path`、`.setup/webots-path` | 安装器生成，启动器读取本机可执行文件位置 | 安装状态，不随公开源码提交 |
| `motions/*.motion` | 动作加载器读取关节轨迹，生成临时过滤副本 | 文件输入，不是发布/订阅 |
| `runs/match-*.jsonl` | 裁判观测与规则事件 | 实验记录 |
| `runs/player-*.jsonl` | 策略、导航、动作尝试、视觉估计等 | 实验记录 |
| `Utils/vision_logs/*.csv` | 视觉框、深度和视线角等记录 | 实验记录 |
| `manifest.json`、`webots.log`、测试结果 JSON | 保存源码哈希、配置、控制台输出和验收结果 | 复现证据 |

足球主循环不会靠轮询日志文件交换世界状态或动作指令。分析脚本离线读日志；部分验收夹具会读取球员日志核对恢复次数等证据，这属于测试验收，不是运行时的战术通信。

## 9. 代码与图中模块的对应关系

以下链接相对于本文档，可直接跳转到实现。

| 架构部分 | 实际文件与关键入口 |
|---|---|
| 世界与控制器绑定 | [naotdp.wbt](../Wenao/worlds/naotdp.wbt)：`basicTimeStep`、八个 `controller` 和 Supervisor Robot |
| 模拟通信设备 | [NaoV6.proto](../Wenao/protos/NaoV6.proto)：`channel`、`RECEIVER`、`EMITTER`、`SUPER_EMITTER` |
| 球员入口示例 | [RedForwardA.py](../Wenao/controllers/RedForwardA/RedForwardA.py)：导入并调用共享 `main()` |
| 裁判循环 | [Supervisor.py](../Wenao/controllers/Supervisor/Supervisor.py)：`step → updateMatch → sendSupervisorData → updateScoreboard` |
| 裁判真值与广播 | [SupervisorBase.py](../Wenao/controllers/Base/SupervisorBase.py)：`observation()`、`sendSupervisorData()`、`physical_touch()`、处罚和重置 |
| 比赛规则与状态快照 | [MatchEngine.py](../Wenao/controllers/Utils/MatchEngine.py)：`snapshot()`；同裁判进程内调用 |
| 球员循环、收发与执行 | [SoccerController.py](../Wenao/controllers/Base/SoccerController.py)：`receive()`、`visual_world()`、`act()`、`play()`、`run()`、`MotionLibrary` |
| 观测解析与缓存 | [ProcessSupervisor.py](../Wenao/controllers/Utils/ProcessSupervisor.py)：`validate_world()`、`SupervisorData.updateData()` |
| 战术决策与传球响应 | [TeamPolicy.py](../Wenao/controllers/Utils/TeamPolicy.py)：`Decision`、`decide()`、`attack()` |
| 导航与朝向滤波 | [Navigation.py](../Wenao/controllers/Utils/Navigation.py)、[HeadingFilter.py](../Wenao/controllers/Utils/HeadingFilter.py) |
| guarded 动作调度 | [GuardedLocomotion.py](../Wenao/controllers/Utils/GuardedLocomotion.py)：`before_decision()` 等 |
| 可选旧衔接实验 | [SideTransition.py](../Wenao/controllers/Utils/SideTransition.py)：默认 off；已退化候选，不等同于 guarded |
| 视觉线程和结果交接 | [ImageServer.py](../Wenao/controllers/Utils/ImageServer.py)：`Thread`、`Queue`、`Lock`、`send()`、`latest()`、`run()` |
| 视觉坐标投影 | [VisionGeometry.py](../Wenao/controllers/Utils/VisionGeometry.py)：`ball_world_position()` |
| 几何常量与配置 | [CourseSpecs.py](../Wenao/controllers/Utils/CourseSpecs.py)、[globalconfig.ini](../Wenao/controllers/Utils/globalconfig.ini) |
| 运动数据记录 | [MotionDiagnostics.py](../Wenao/controllers/Utils/MotionDiagnostics.py) |
| 测试装配 | [run_webots_check.py](../tests/run_webots_check.py)：临时工程、控制器替换、启动配置、控制台收集 |
| 旁站/动作探针 | [webots_motion_probe.py](../tests/webots_motion_probe.py) |
| 衔接测试双向通信 | [webots_transition_check.py](../tests/webots_transition_check.py)、[webots_transition_probe.py](../tests/webots_transition_probe.py) |
| 固定场景视觉探针 | [webots_vision_player.py](../tests/webots_vision_player.py) |
| 离线指标 | [evaluate_run.py](../tools/evaluate_run.py)、[analyze_motion_diagnostics.py](../tools/analyze_motion_diagnostics.py)、[analyze_transition_run.py](../tools/analyze_transition_run.py) |
| 多人失稳关联分析 | [analyze_multiplayer_run.py](../tools/analyze_multiplayer_run.py)：恢复命令、倾角过程与最近其他机器人位置，非接触因果判定 |

## 10. 当前边界与真机迁移

当前系统是在同一台计算机内运行的多控制器仿真，尚未实现真实机器人之间的网络通信。Webots 的模拟无线设备不能直接当作 NAO 的 Wi-Fi 驱动；`controller.Robot`、`Supervisor` 和 `Motion` 也不是 NAOqi 接口。

真机迁移需要替换或补充以下接口：

1. 观测源：相机、机器人自身定位、球估计和比赛状态输入，替代 Supervisor 真值。
2. 运动执行：用实际硬件支持的 SDK、动作接口或步态控制器执行移动，重新验证关节、支撑与速度。
3. 队内网络：为传球意图等定义真实传输方式，并处理时钟、延迟、丢包、身份和冲突；当前绝对仿真时间不能直接作为跨设备有效期。
4. 比赛管理：明确真实裁判/比赛控制器输入、自动场外计算与定位边界。无人手动操作不自动等于允许使用所有外部真值。

`TeamPolicy` 和 `Navigation` 的纯 Python 决策接口有利于复用，但接口可复用不代表算法已完成真实硬件验证。`nao_ws/` 中保留的 ROS/Gazebo 工程、`controllers/legacy/` 和历史 Notebook 均不在当前 Webots 足球主链路上。

运行方法见 [RUN.md](RUN.md)，安装见 [INSTALL.md](INSTALL.md)，单人稳定验收见 [SINGLE_PLAYER_STABILITY.md](SINGLE_PLAYER_STABILITY.md)，验证范围见 [VALIDATION.md](VALIDATION.md)。
