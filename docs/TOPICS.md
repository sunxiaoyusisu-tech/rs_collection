# Topic 与 rosbag

## 控制和状态

| Topic | 类型 | 目标频率 | 作用 |
|---|---|---:|---|
| `/leader/joint_states` | `sensor_msgs/msg/JointState` | 120 Hz | 主臂 SDK 读数 |
| `/teleop/action` | `sensor_msgs/msg/JointState` | 120 Hz | 映射后的期望动作 |
| `/teleop/applied` | `sensor_msgs/msg/JointState` | ≤120 Hz | 控制器接受并实际下发的动作 |
| `/rebotarm/joint_states` | `sensor_msgs/msg/JointState` | 120 Hz | 从臂反馈 state |
| `/rebotarm/gripper/state` | `rebotarm_msgs/msg/JointMotorState` | 120 Hz | 夹爪电机状态 |
| `/rebotarm/arm_status` | `rebotarm_msgs/msg/ArmStatus` | 事件更新 | 控制器状态机和使能状态 |
| `/diagnostics` | `diagnostic_msgs/msg/DiagnosticArray` | 事件/1 Hz | 主臂与控制器健康信息 |

## 相机

| Topic | 类型 | 目标频率 |
|---|---|---:|
| `/head/image_raw` | `sensor_msgs/msg/Image` | 30 Hz |
| `/head/camera_info` | `sensor_msgs/msg/CameraInfo` | 30 Hz |
| `/camera_wrist/image_raw` | `sensor_msgs/msg/Image` | 30 Hz |
| `/camera_wrist/camera_info` | `sensor_msgs/msg/CameraInfo` | 30 Hz |

没有标定 YAML 时 `CameraInfo` 仍会发布，但内参为空/默认值。正式用于几何任务前应分别
标定两颗相机，并提供 `~/.ros/camera_info/head.yaml` 与
`~/.ros/camera_info/camera_wrist.yaml`。

## TF 与采集事件

| Topic | 类型 | 作用 |
|---|---|---|
| `/tf` | `tf2_msgs/msg/TFMessage` | 动态坐标变换 |
| `/tf_static` | `tf2_msgs/msg/TFMessage` | 静态坐标变换 |
| `/collection/event` | `std_msgs/msg/String` | episode 开始/结束事件 |

上述 Topic 全部写入 MCAP。输出目录格式为：

```text
$REBOT_BAG_ROOT/YYYY-MM-DD/YYYY-MM-DD_HH-MM-SS/
```

同一秒重复开始录制时自动追加 `_02`、`_03`，不会覆盖已有数据。
