#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "$script_dir/.." && pwd)"
controller_repo="${1:-$HOME/rebotarm_ros2}"
patch_file="$repository_root/patches/rebotarm_controller_teleop.patch"
expected_commit="39fbea54c7235b1c38bd025fc2e7308e42bd2fbe"

if [[ ! -d "$controller_repo/.git" && -d "$controller_repo/src/reBotArmController_ROS2/.git" ]]; then
  controller_repo="$controller_repo/src/reBotArmController_ROS2"
fi
if [[ ! -d "$controller_repo/.git" ]]; then
  echo "错误：不是 reBotArmController_ROS2 Git 仓库：$controller_repo" >&2
  exit 1
fi
if [[ ! -f "$patch_file" ]]; then
  echo "错误：找不到补丁：$patch_file" >&2
  exit 1
fi

actual_commit="$(git -C "$controller_repo" rev-parse HEAD)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
  echo "错误：控制器基准提交不匹配。" >&2
  echo "期望：$expected_commit" >&2
  echo "实际：$actual_commit" >&2
  exit 1
fi

if git -C "$controller_repo" apply --reverse --check "$patch_file" 2>/dev/null; then
  echo "控制器遥操补丁已经应用，无需重复操作。"
  exit 0
fi

if [[ -n "$(git -C "$controller_repo" status --porcelain --untracked-files=normal)" ]]; then
  echo "错误：控制器仓库存在未提交改动，拒绝覆盖：" >&2
  git -C "$controller_repo" status --short >&2
  exit 1
fi

git -C "$controller_repo" apply --check "$patch_file"
git -C "$controller_repo" apply "$patch_file"
echo "控制器遥操补丁已应用到：$controller_repo"
