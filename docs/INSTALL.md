# Ubuntu 自动安装

入口为根目录的 `install.sh`；安装后通过 `launch.sh` 打开足球世界。

## 适配范围

| 系统 | 安装脚本状态 |
|---|---|
| 原生 Ubuntu 20.04 LTS，x86-64 | 适配；20.04.6 为已有仿真验证基准 |
| 原生 Ubuntu 22.04 LTS，x86-64 | 适配系统检查与安装分支；尚未进行该系统的实际安装和仿真验证 |
| 其他 Ubuntu 版本、其他 Linux 发行版 | 拒绝执行安装 |
| Linux ARM64、32 位系统 | 拒绝执行安装 |
| Windows、macOS、WSL、已识别的容器 | 此安装脚本不适配 |

脚本需要 Bash 4+、正常的 Ubuntu 软件源和网络连接。系统软件缺失时使用 `sudo apt-get`，Conda 与 Python 环境以普通账户安装。执行方式为 `bash install.sh`，不是 `sudo bash install.sh`。普通虚拟机不在实际验证范围，脚本没有检测所有虚拟化平台；渲染还依赖图形设备、驱动和 OpenGL 3.3。

Webots 跨平台支持与此安装脚本的范围不同。Windows/macOS 的仿真器支持情况见 [README](../README.md)。Ubuntu 20.04/22.04 的 R2023b 安装包依据 [官方发布页](https://github.com/cyberbotics/webots/releases/tag/R2023b)。

## 克隆后的使用步骤

在项目根目录运行：

```bash
bash install.sh
```

安装结束后，控制台显示实际环境的 Python 路径。在 Webots 的 **Tools → Preferences → General → Python command** 中设置此路径。随后从项目根目录运行：

```bash
bash launch.sh
```

启动器清除常见的 Python/Qt 库路径冲突，并把环境的 `bin` 放到 PATH 前面。Webots 的默认 Python command 为 `python` 时会使用该环境；已有绝对解释器设置仍需按安装输出核对。启动器不写全局 Webots 偏好。[R2023b Python 配置说明](https://github.com/cyberbotics/webots/blob/R2023b/docs/guide/using-python.md)

## 自动完成的步骤

1. 校验系统、架构、环境名和项目文件。
2. 检查 `curl`、CA 证书、OpenGL/GLib 运行库；缺失时通过 apt 安装。
3. 检查并复用 Webots R2023b；缺失时下载固定的 Ubuntu deb，校验 SHA-256 后安装。检测到不同版本时停止，或通过 `--webots` 指定已有 R2023b。
4. 优先查找现有 Conda。缺失时安装 [Miniforge 26.7.2-0](https://github.com/conda-forge/miniforge/releases/tag/26.7.2-0)，采用固定安装包和 SHA-256；安装目录为 `~/.local/share/webots-robotics-tdp/miniforge3`。
5. 创建或复用 `robotics-tdp` 环境。新环境使用 conda-forge 的 Python 3.10；补丁版本由可用包决定，不锁定为历史基准的 3.10.22。已有非 3.10 环境、base 环境或不完整环境会被拒绝。
6. 固定 NumPy 1.26.4、OpenCV 4.9.0.80、Ultralytics 8.1.4、PyTorch 2.2.2+cpu、torchvision 0.17.2+cpu，检查实际导入和 `pip check`。依赖已经符合时跳过 pip 安装；不符合时更新指定的独立环境。
7. 执行 Python 逻辑测试；通过后保存启动路径。

下载缓存位于 `~/.cache/webots-robotics-tdp`，或 `XDG_CACHE_HOME` 下的对应目录。安装日志和本机启动配置位于 `.setup/`，已被 Git 忽略，可能包含本机路径，不作为公开源码上传。缓存以校验和复用，安装失败后可重复执行。脚本不执行 `conda init`，启动器不要求手动激活环境。

直接依赖版本已固定，传递依赖没有完整锁定。网络下载、软件源、现有环境冲突或图形驱动问题仍可能使安装或运行失败。软件安装与逻辑测试通过不代表图形渲染、相机测距、比赛效果或真实硬件已经通过验证。

## 其他模式

```bash
bash install.sh --help
bash install.sh --dry-run
bash install.sh --check
bash install.sh --env-name webots-tdp-clean
bash install.sh --conda /path/to/conda --webots /path/to/webots
```

- `--dry-run`：校验系统并显示现有软件与安装计划，不下载或安装。
- `--check`：检查已存在的环境，不安装依赖、不生成启动配置；Python 库自身仍可能产生本地缓存。
- `--env-name`：为独立实验选择另一环境；最近一次安装保存的环境供 `launch.sh` 使用。
- `--conda` / `--webots`：指定已有软件的实际可执行文件路径。

新安装之后还需进行世界加载检查。已配置 Python command 且具有图形会话时，从项目根目录运行：

```bash
conda activate robotics-tdp
python tests/run_webots_check.py --output runs/geometry_01
```

自动安装的 Miniforge 未初始化到 shell 时，可改用安装输出中的完整 Python 路径。输出目录应为新目录；更多实验模式见 [RUN.md](RUN.md)。

## 安装脚本验证记录（2026-10-13）

- Ubuntu 20.04.6、x86-64 主机：已有环境的 `--check` 与 `--dry-run` 通过。
- 在已有 Conda/Webots 的主机上创建全新的 Python 3.10.22 验证环境，依赖安装、导入与 `pip check` 通过；33 项原逻辑测试和 8 项安装脚本测试全部通过。
- 原 `robotics-tdp` 环境复用流程通过，跳过重复 pip 安装；启动器的 `--version` 显示 R2023b。本机启动配置已恢复为该环境，临时验证环境已移除。
- 从官方发布地址下载 Webots deb，与脚本的 SHA-256 一致；Miniforge 固定安装包的校验和与临时目录中的批量安装、Conda 启动检查通过。
- 脚本测试覆盖系统/架构/WSL 限制、base 环境拒绝、无安装预览、下载缓存复用、校验失败保护、其他 Webots 版本拒绝，以及含空格路径和启动环境隔离。

此次未在全新操作系统上执行 apt 安装全流程，未实测 Ubuntu 22.04，也未通过安装脚本重新评估比赛表现。以上记录仅说明已列出的软件配置与测试范围。
