# reBot B601-RS ROS 2 遥操采集

这是当前 B601-RS 主从遥操与 ROS 2 数据采集链路的独立、可复现仓库。它把
LeRobot 主臂读取、ROS 2 action/state 封装、官方 reBotArm 控制器扩展、双相机
预览以及 MCAP rosbag2 录制整理在一起。

此仓库是从现有可用环境复制整理出来的，不会替换原来的
`~/rebot_collection_ws`、`~/rebotarm_ros2` 或 `~/.local/bin/run_collection`。

## 当前能力

- 主臂目标读取：目标 120 Hz
- `/teleop/action` 到从臂整臂下发：目标 120 Hz
- `/rebotarm/joint_states`：目标 120 Hz
- `head` 与 `camera_wrist` 两路相机：640×480、目标 30 Hz
- 单个半屏 RQT 窗口左右显示两路相机
- Enter 开始录制，再次 Enter 停止并安全写盘
- MCAP + Zstd，按日期和秒级时间自动创建目录
- 输入超时 watchdog、恢复对齐检查以及退出时从臂失能

## 数据流

```mermaid
flowchart LR
    L[reBot Arm 102 leader] -->|UART / LeRobot Python| U[localhost UDP]
    U --> B[leader_action_bridge]
    B -->|sensor_msgs/JointState| A[/teleop/action]
    A --> C[patched reBotArmController]
    C -->|grouped MIT command| CAN[SocketCAN can0 @ 1 Mbps]
    CAN --> F[B601-RS follower]
    C --> S[/rebotarm/joint_states]
    H[head camera] --> HI[/head/image_raw]
    W[camera_wrist] --> WI[/camera_wrist/image_raw]
    A --> R[rosbag2 MCAP]
    S --> R
    HI --> R
    WI --> R
```

只有官方 `reBotArmController` 进程拥有 `can0`。不要同时运行
`run_collection`、`run_teleop`、`lerobot-record` 或 `motorbridge-gateway`。

## 仓库结构

```text
rs_collection/
├── ros2_ws/src/rebot_collection/       # 本项目 ROS 2 包
├── patches/rebotarm_controller_teleop.patch
│                                        # 官方控制器遥操扩展
├── scripts/run_collection               # 一键启动与安全退出
├── scripts/apply_controller_patch.sh    # 带基准检查的补丁脚本
├── scripts/build.sh                     # 构建官方与本项目工作区
├── config/collection.env.example        # 路径和设备覆盖示例
└── docs/                                 # 安装、架构、Topic 与安全说明
```

## 快速开始

完整步骤见 [安装与构建](docs/INSTALL.md)。已准备好依赖后：

```bash
git clone https://github.com/sunxiaoyusisu-tech/rs_collection.git ~/rs_collection
cd ~/rs_collection

./scripts/apply_controller_patch.sh ~/rebotarm_ros2
./scripts/build.sh ~/rebotarm_ros2

mkdir -p ~/.local/bin
install -m 0755 scripts/run_collection ~/.local/bin/run_collection
run_collection
```

默认 rosbag 路径：

```text
~/sun_ws/data/YYYY-MM-DD/YYYY-MM-DD_HH-MM-SS/
```

## 相机与 Topic

| RQT 位置 | 相机名 | 图像 Topic | CameraInfo Topic |
|---|---|---|---|
| 左侧 | `head` | `/head/image_raw` | `/head/camera_info` |
| 右侧 | `camera_wrist` | `/camera_wrist/image_raw` | `/camera_wrist/camera_info` |

完整录制 Topic 和消息语义见 [Topic 与 rosbag](docs/TOPICS.md)。

## 上游版本

- `reBotArmController_ROS2`: `39fbea54c7235b1c38bd025fc2e7308e42bd2fbe`
- `lerobot`: `0f392484458cb5ebca0310c0c4c47390a31c80ed`
- `lerobot-teleoperator-rebot-arm-102`:
  `8203cb8f052a130c303dfe950666e9a2fdc024d8`

`lerobot-robot-seeed-b601` 属于独立的 `run_teleop` 路径，本采集链路不使用它
控制 CAN，因此没有将其本地参数修改混入本仓库。

## 安全

首次运行或修改控制参数前，请先阅读 [安全说明](docs/SAFETY.md)。此软件会向真实
机械臂发送命令；测试时应保持急停和断电手段可用，并确保机械臂周围无人和障碍物。

## License

本仓库原创代码采用 Apache-2.0。`patches/` 中的差异基于 Seeed 上游工程，使用时
同时遵循对应上游项目的许可与声明。
