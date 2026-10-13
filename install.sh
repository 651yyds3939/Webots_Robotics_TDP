#!/usr/bin/env bash
# Ubuntu desktop setup. Run with Bash as a normal account; sudo is used for apt only.
set -Eeuo pipefail

PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
ENV_NAME=robotics-tdp
CONDA_BIN=
WEBOTS_BIN=
MODE=install
WEBOTS_URL=https://github.com/cyberbotics/webots/releases/download/R2023b/webots_2023b_amd64.deb
WEBOTS_SHA=49abb5387a86d84796c42b96eadf485d9cf961974c46477b687caf03f49fcfda
MINIFORGE_VERSION=26.7.2-0
MINIFORGE_SHA=281b0ac7d550802efc81af633225a5e6116d29ae72f3ab4eae7168c3931a4c05

die() { printf '\n错误：%s\n' "$*" >&2; exit 1; }
info() { printf '\n%s\n' "$*"; }
clean_env() {
  env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH \
    -u QT_QPA_PLATFORM_PLUGIN_PATH PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 "$@"
}

usage() {
  cat <<'HELP'
用法：bash install.sh [选项]
  默认            安装/复用 Webots R2023b、Conda Python 3.10 和 CPU 依赖
  --check         仅检查已有环境，不下载或安装，不写项目配置
  --dry-run       预览安装计划，不下载或安装
  --env-name NAME 指定独立 Conda 环境名称（默认 robotics-tdp；不能为 base）
  --conda PATH    指定已有 conda 可执行文件
  --webots PATH   指定已有 Webots 可执行文件（须为 R2023b）
  -h, --help      显示说明
适配：原生 Ubuntu 20.04 / 22.04，Intel/AMD x86-64，Bash 4+。
Windows、macOS、WSL、容器和其他 Ubuntu 版本不适配此安装脚本。
HELP
}

validate_platform() {
  local os=$1 version=$2 architecture=$3 kernel=$4
  [[ $os == ubuntu && ( $version == 20.04 || $version == 22.04 ) ]] || \
    die "仅适配 Ubuntu 20.04/22.04；检测到 $os $version。"
  [[ $architecture == x86_64 ]] || die "仅适配 x86-64；检测到 $architecture。"
  case "$kernel" in
    *[Mm]icrosoft*|*WSL*) die 'WSL 未适配；此脚本用于原生 Ubuntu 桌面。' ;;
  esac
}

check_platform() {
  [[ ${BASH_VERSINFO[0]} -ge 4 ]] || die '需要 Bash 4 或更新版本。'
  [[ -r /etc/os-release ]] || die '无法读取系统版本；仅适配 Ubuntu。'
  # shellcheck source=/dev/null
  source /etc/os-release
  validate_platform "${ID:-unknown}" "${VERSION_ID:-unknown}" "$(uname -m)" "$(uname -r)"
  [[ ! -e /.dockerenv && ! -e /run/.containerenv ]] || die '容器安装尚未适配。'
  info "系统：Ubuntu $VERSION_ID / $(uname -m)"
}

find_conda() {
  local candidate
  if [[ -n $CONDA_BIN ]]; then
    [[ -x $CONDA_BIN && -f $CONDA_BIN ]] || die '--conda 必须指向可执行文件。'
    CONDA_BIN=$(realpath -- "$CONDA_BIN")
    return
  fi
  for candidate in "${CONDA_EXE:-}" "$(type -P conda || true)" \
    "$HOME/miniconda3/bin/conda" "$HOME/miniforge3/bin/conda" \
    "$HOME/anaconda3/bin/conda" "$HOME/mambaforge/bin/conda" \
    "$HOME/.local/share/webots-robotics-tdp/miniforge3/bin/conda"; do
    if [[ -f $candidate && -x $candidate ]]; then
      CONDA_BIN=$candidate
      return
    fi
  done
}

find_environment() {
  ENV_PREFIX=
  [[ -n $CONDA_BIN ]] || return 0
  local base
  base=$(clean_env "$CONDA_BIN" info --base)
  [[ -x $base/bin/python ]] || die '现有 Conda 的基础解释器不可用。'
  ENV_PREFIX=$(clean_env "$CONDA_BIN" env list --json | clean_env "$base/bin/python" -c '
import json, pathlib, sys
name = sys.argv[1]
matches = [p for p in json.load(sys.stdin)["envs"] if pathlib.Path(p).name == name]
if len(matches) > 1:
    raise SystemExit("存在多个同名环境；通过 --env-name 指定另一个独立名称。")
print(matches[0] if matches else "")
' "$ENV_NAME")
  if [[ -n $ENV_PREFIX ]]; then
    [[ $ENV_PREFIX != "$base" ]] || die '目标环境不能是 Conda base。'
    [[ -x $ENV_PREFIX/bin/python ]] || die '已有环境不完整；通过 --env-name 使用另一个名称。'
    clean_env "$ENV_PREFIX/bin/python" -I -c \
      'import sys; assert sys.version_info[:2] == (3, 10), "已有环境不是 Python 3.10；使用 --env-name 创建另一个环境。"'
  fi
}

find_webots() {
  if [[ -z $WEBOTS_BIN ]]; then
    WEBOTS_BIN=$(type -P webots || true)
    if [[ -z $WEBOTS_BIN && -x /usr/local/webots/webots ]]; then
      WEBOTS_BIN=/usr/local/webots/webots
    fi
  else
    [[ -f $WEBOTS_BIN && -x $WEBOTS_BIN ]] || die '--webots 必须指向可执行文件。'
  fi
  if [[ -n $WEBOTS_BIN ]]; then
    WEBOTS_BIN=$(realpath -- "$WEBOTS_BIN")
    local version
    version=$(clean_env "$WEBOTS_BIN" --version)
    [[ $version == 'Webots version: R2023b' ]] || \
      die "发现其他 Webots 版本：$version。未覆盖；可用 --webots 指定 R2023b。"
  fi
  local package_version
  package_version=$(dpkg-query -W -f='${Version}' webots 2>/dev/null || true)
  if [[ -z $WEBOTS_BIN && -n $package_version && $package_version != 2023b ]]; then
    die "已有 Webots 软件包版本 $package_version；未覆盖。"
  fi
}

download_verified() {
  local url=$1 checksum=$2 destination=$3
  if [[ -f $destination ]] && printf '%s  %s\n' "$checksum" "$destination" | sha256sum -c --status; then
    info "复用已验证下载：$(basename -- "$destination")"
    return
  fi
  curl --fail --location --retry 3 --connect-timeout 20 "$url" -o "$destination.part"
  printf '%s  %s\n' "$checksum" "$destination.part" | sha256sum -c
  mv -- "$destination.part" "$destination"
}

dependencies_ok() {
  clean_env "$ENV_PREFIX/bin/python" -I - <<'PY'
import importlib, importlib.metadata, sys
assert sys.version_info[:2] == (3, 10), "Python 3.10 required"
expected = {
    "numpy": "1.26.4", "opencv-python": "4.9.0.80", "ultralytics": "8.1.4",
    "torch": "2.2.2+cpu", "torchvision": "0.17.2+cpu",
}
try:
    for package, version in expected.items():
        actual = importlib.metadata.version(package)
        if actual != version:
            raise ValueError(f"{package}: {actual}; expected {version}")
    for module in ("numpy", "cv2", "torch", "torchvision", "ultralytics"):
        importlib.import_module(module)
    import torch
    assert torch.version.cuda is None, "CPU PyTorch required"
except Exception as error:
    raise SystemExit(f"依赖尚未满足：{error}")
print("Python 3.10 与固定版本 CPU 依赖导入通过。")
PY
}

show_next_steps() {
  printf '\nPython command：%s\n' "$ENV_PREFIX/bin/python"
  printf 'Webots Preferences → General → Python command 设置为上述路径。\n'
  if [[ -r $PROJECT_DIR/.setup/python-path ]]; then
    printf '启动（使用最近一次安装保存的环境）：cd %q && bash launch.sh\n' "$PROJECT_DIR"
  else
    printf '启动配置尚未生成；运行 bash install.sh 后可用 bash launch.sh。\n'
  fi
  printf '几何检查：cd %q && %q tests/run_webots_check.py --output runs/geometry_01\n' \
    "$PROJECT_DIR" "$ENV_PREFIX/bin/python"
  printf '启动前关闭旧的 Webots 窗口，避免继续使用旧进程的解释器环境。\n'
}

main() {
  while (($#)); do
    case "$1" in
      -h|--help) usage; return 0 ;;
      --check|--dry-run)
        [[ $MODE == install ]] || die '--check 与 --dry-run 不能重复或组合。'
        MODE=${1#--}; shift ;;
      --env-name|--conda|--webots)
        [[ $# -ge 2 && -n $2 && $2 != --* ]] || die "$1 缺少参数。"
        case "$1" in
          --env-name) ENV_NAME=$2 ;;
          --conda) CONDA_BIN=$2 ;;
          --webots) WEBOTS_BIN=$2 ;;
        esac
        shift 2 ;;
      *) die "未知选项：$1；参见 --help。" ;;
    esac
  done
  [[ $ENV_NAME =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ && $ENV_NAME != base ]] || \
    die '环境名只允许字母、数字、下划线、连字符，且不能为 base。'
  check_platform
  [[ -r $PROJECT_DIR/requirements-tested.txt && -f $PROJECT_DIR/Wenao/worlds/naotdp.wbt \
    && -f $PROJECT_DIR/Wenao/controllers/Utils/best.pt ]] || die '项目文件不完整。'
  if [[ $MODE == install && $EUID -eq 0 ]]; then
    die '使用普通桌面账户运行 bash install.sh；不要 sudo bash install.sh。'
  fi
  find_conda
  find_environment
  find_webots
  if [[ $MODE == dry-run ]]; then
    info '预览：未进行下载或安装。'
    printf 'Conda：%s\n环境：%s\nWebots：%s\n' \
      "${CONDA_BIN:-将安装 Miniforge $MINIFORGE_VERSION}" \
      "${ENV_PREFIX:-将创建 $ENV_NAME（Python 3.10，conda-forge）}" \
      "${WEBOTS_BIN:-将安装 R2023b Ubuntu deb}"
    printf '计划：检查 apt 依赖、固定 CPU 依赖、pip check、逻辑测试、写入本机启动配置。\n'
    return 0
  fi
  if [[ $MODE == check ]]; then
    [[ -n $CONDA_BIN && -n $ENV_PREFIX && -n $WEBOTS_BIN ]] || die '缺少环境；运行 bash install.sh 安装。'
    dependencies_ok
    clean_env "$ENV_PREFIX/bin/python" -I -m pip check
    info '已有环境检查通过；未进行安装，未写启动配置。'
    show_next_steps
    return 0
  fi

  umask 077
  local cache_dir setup_dir log_file
  cache_dir=${XDG_CACHE_HOME:-$HOME/.cache}/webots-robotics-tdp
  [[ $cache_dir == /* ]] || die '缓存目录必须是绝对路径。'
  setup_dir=$PROJECT_DIR/.setup
  mkdir -p -- "$cache_dir" "$setup_dir"
  command -v flock >/dev/null || die '缺少 flock（Ubuntu util-linux 软件包）。'
  exec 9>"$cache_dir/install.lock"
  flock -n 9 || die '另一个安装过程正在使用下载缓存。'
  log_file=$setup_dir/install-$(date +%Y%m%d-%H%M%S)-$$.log
  exec > >(tee -a "$log_file") 2>&1
  trap 'printf "\n安装失败：第 %s 行，退出码 %s。日志：%s\n" "$LINENO" "$?" "$log_file" >&2' ERR
  info '安装 Webots Robotics TDP；已有环境可复用，失败后可再次运行。'
  info '[1/5] 系统依赖与 Webots'
  local package status
  local missing=()
  for package in curl:amd64 ca-certificates libgl1:amd64 libglib2.0-0:amd64; do
    status=$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true)
    [[ $status == installed ]] || missing+=("$package")
  done
  if ((${#missing[@]})) || [[ -z $WEBOTS_BIN ]]; then
    command -v sudo >/dev/null || die '缺少 sudo；系统软件安装需要管理员权限。'
    sudo -v
    clean_env sudo apt-get update
    if ((${#missing[@]})); then
      clean_env sudo apt-get install -y "${missing[@]}"
    fi
  fi
  if [[ -z $WEBOTS_BIN ]]; then
    download_verified "$WEBOTS_URL" "$WEBOTS_SHA" "$cache_dir/webots_2023b_amd64.deb"
    dpkg-deb --info "$cache_dir/webots_2023b_amd64.deb" >/dev/null
    clean_env sudo apt-get install -y "$cache_dir/webots_2023b_amd64.deb"
    find_webots
    [[ -n $WEBOTS_BIN ]] || die 'Webots 安装后仍未找到可执行文件。'
  fi

  info '[2/5] Conda 与 Python 3.10'
  if [[ -z $CONDA_BIN ]]; then
    local prefix installer url
    prefix=$HOME/.local/share/webots-robotics-tdp/miniforge3
    [[ ! -e $prefix ]] || die 'Miniforge 目标目录已存在但不完整；未覆盖。'
    installer=$cache_dir/Miniforge3-$MINIFORGE_VERSION-Linux-x86_64.sh
    url=https://github.com/conda-forge/miniforge/releases/download/$MINIFORGE_VERSION/Miniforge3-$MINIFORGE_VERSION-Linux-x86_64.sh
    download_verified "$url" "$MINIFORGE_SHA" "$installer"
    mkdir -p -- "$(dirname -- "$prefix")"
    clean_env bash "$installer" -b -p "$prefix"
    CONDA_BIN=$prefix/bin/conda
  fi
  if [[ -z $ENV_PREFIX ]]; then
    clean_env "$CONDA_BIN" create -y --quiet --override-channels -c conda-forge -n "$ENV_NAME" python=3.10 pip
    find_environment
    [[ -n $ENV_PREFIX ]] || die '创建后未找到 Python 环境。'
  fi

  info '[3/5] 固定版本 CPU 依赖'
  if dependencies_ok && clean_env "$ENV_PREFIX/bin/python" -I -m pip check; then
    info '固定版本依赖已满足，跳过 pip 安装。'
  else
    clean_env "$ENV_PREFIX/bin/python" -I -m pip install \
      --index-url https://download.pytorch.org/whl/cpu -c "$PROJECT_DIR/requirements-tested.txt" \
      'torch==2.2.2+cpu' 'torchvision==0.17.2+cpu'
    clean_env "$ENV_PREFIX/bin/python" -I -m pip install -r "$PROJECT_DIR/requirements-tested.txt"
    dependencies_ok
    clean_env "$ENV_PREFIX/bin/python" -I -m pip check
  fi
  info '[4/5] 逻辑测试'
  (cd -- "$PROJECT_DIR" && clean_env "$ENV_PREFIX/bin/python" -B -m unittest discover -s tests -v)
  info '[5/5] 保存本机启动配置'
  printf '%s\n' "$ENV_PREFIX/bin/python" > "$setup_dir/python-path"
  printf '%s\n' "$WEBOTS_BIN" > "$setup_dir/webots-path"
  info '软件环境安装与逻辑测试通过；图形驱动、实际世界加载和比赛性能需另行验证。'
  show_next_steps
  printf '安装日志：%s（.setup/ 已被 Git 忽略）\n' "$log_file"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
