#!/usr/bin/env bash
# Uses the local installation state; no shell rc files or Webots preferences are changed.
set -Eeuo pipefail
PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=install.sh
source "$PROJECT_DIR/install.sh"
check_platform
[[ -r $PROJECT_DIR/.setup/python-path && -r $PROJECT_DIR/.setup/webots-path ]] || \
  die '缺少本机启动配置；先运行 bash install.sh。'
IFS= read -r PYTHON_BIN < "$PROJECT_DIR/.setup/python-path"
IFS= read -r WEBOTS_BIN < "$PROJECT_DIR/.setup/webots-path"
[[ -x $PYTHON_BIN && -x $WEBOTS_BIN ]] || die '软件路径已变化；重新运行 bash install.sh。'
[[ -n ${DISPLAY:-} || -n ${WAYLAND_DISPLAY:-} ]] || die '需要正常的桌面图形会话。'
printf '环境解释器：%s\n' "$PYTHON_BIN"
printf 'Python command 为 python 时自动使用此环境；已有绝对路径设置需在 Preferences 中核对。\n'
cd -- "$PROJECT_DIR"
exec env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH \
  -u QT_QPA_PLATFORM_PLUGIN_PATH PYTHONNOUSERSITE=1 \
  PATH="$(dirname -- "$PYTHON_BIN"):$PATH" "$WEBOTS_BIN" "$@" "$PROJECT_DIR/Wenao/worlds/naotdp.wbt"
