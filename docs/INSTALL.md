# 安装与构建

本文档对应 Ubuntu 24.04、ROS 2 Jazzy、B601-RS、PCAN-USB 和 reBot Arm 102
主臂。仓库默认克隆到 `~/rs_collection`。

## 1. 系统依赖

```bash
sudo apt update
sudo apt install -y \
  can-utils v4l-utils \
  ros-jazzy-desktop \
  ros-jazzy-usb-cam \
  ros-jazzy-rqt-gui \
  ros-jazzy-rqt-image-view \
  ros-jazzy-rosbag2-storage-mcap
```

ROS 2 和底层 reBot SDK 的完整安装仍以 Seeed 官方文档为准。

## 2. LeRobot 环境

本链路需要能导入 `lerobot_teleoperator_rebot_arm_102` 的 Miniforge 环境：

```bash
conda activate lerobot
pip install -e ~/rebot_lerobot/lerobot
pip install -e ~/rebot_lerobot/lerobot-teleoperator-rebot-arm-102
```

已验证版本：

- Seeed LeRobot commit `0f392484458cb5ebca0310c0c4c47390a31c80ed`
- leader plugin commit `8203cb8f052a130c303dfe950666e9a2fdc024d8`

## 3. 官方 ROS 2 控制器补丁

```bash
git clone https://github.com/Seeed-Projects/reBotArmController_ROS2.git \
  ~/rebotarm_ros2
git -C ~/rebotarm_ros2 checkout 39fbea54c7235b1c38bd025fc2e7308e42bd2fbe

cd ~/rs_collection
./scripts/apply_controller_patch.sh ~/rebotarm_ros2
```

脚本只接受准确的基准提交，并在补丁无法干净应用时停止，不会强制覆盖本地改动。

## 4. 构建

```bash
cd ~/rs_collection
./scripts/build.sh ~/rebotarm_ros2
```

脚本先构建官方工作区，再构建本仓库的 `ros2_ws`。

## 5. 安装启动命令

如果已有 `~/.local/bin/run_collection`，先自行备份；然后：

```bash
mkdir -p ~/.local/bin
install -m 0755 ~/rs_collection/scripts/run_collection \
  ~/.local/bin/run_collection
```

确保 `~/.local/bin` 在 `PATH` 中。若仓库或工作区位于其他目录，参考
`config/collection.env.example` 设置环境变量。

## 6. 启动

```bash
run_collection
```

启动器会请求 sudo，用于加载 `peak_usb`、配置 `can0@1000000` 和设置主臂串口
权限。进入就绪状态后：

- Enter：开始一个 episode
- 再次 Enter：结束并写盘
- Ctrl+C：停止整条链路并最终失能从臂
