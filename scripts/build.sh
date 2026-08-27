#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "$script_dir/.." && pwd)"
controller_ws="${1:-${REBOT_OFFICIAL_WS:-$HOME/rebotarm_ros2}}"
collection_ws="$repository_root/ros2_ws"

if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo "错误：找不到 /opt/ros/jazzy/setup.bash" >&2
  exit 1
fi
if [[ -z "$(find "$controller_ws" -path '*/rebotarmcontroller/package.xml' -print -quit 2>/dev/null)" ]]; then
  echo "错误：找不到官方控制器工作区：$controller_ws" >&2
  exit 1
fi

set +u
source /opt/ros/jazzy/setup.bash
set -u

(
  cd "$controller_ws"
  colcon build --symlink-install
)

set +u
source "$controller_ws/install/setup.bash"
set -u

(
  cd "$collection_ws"
  colcon build --symlink-install
)

echo "构建完成。"
echo "官方控制器：$controller_ws/install"
echo "采集工作区：$collection_ws/install"
