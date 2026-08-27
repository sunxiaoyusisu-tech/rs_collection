#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "$script_dir/.." && pwd)"
controller_ws="${1:-${REBOT_OFFICIAL_WS:-$HOME/rebotarm_ros2}}"
collection_ws="$repository_root/ros2_ws"

bash -n "$repository_root/scripts/run_collection"
bash -n "$repository_root/scripts/apply_controller_patch.sh"
bash -n "$repository_root/scripts/build.sh"

python3 -m compileall -q "$collection_ws/src/rebot_collection"

set +u
source /opt/ros/jazzy/setup.bash
source "$controller_ws/install/setup.bash"
source "$collection_ws/install/setup.bash"
set -u

(
  cd "$collection_ws"
  colcon test \
    --packages-select rebot_collection \
    --event-handlers console_direct+
  colcon test-result --verbose
)
