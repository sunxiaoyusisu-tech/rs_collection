# 架构与频率语义

## 1. 主臂输入

`lerobot_leader_reader.py` 在 LeRobot Conda Python 中运行，直接复用
`RebotArm102Leader` SDK 从 `/dev/ttyUSB0` 读取七个主臂关节。它以 localhost UDP
把最新成功读取的角度发送给 ROS 2 Jazzy Python 进程，避免把 Python 3.10 的
LeRobot 依赖与 Python 3.12 的 `rclpy` 混在同一进程。

`leader_action_bridge` 完成以下工作：

1. 校验关节名称和样本新鲜度。
2. 应用与既有 LeRobot 遥操一致的方向、限位和夹爪比例映射。
3. 发布 `/leader/joint_states` 和 `/teleop/action`。

## 2. 从臂控制

`/teleop/action` 使用 `sensor_msgs/msg/JointState`，名称固定为
`joint1..joint6, gripper`。官方控制器补丁增加 `WholeArmTeleopStream`，每个样本
使用一次整臂 grouped MIT 下发，而不是对七颗电机做逐关节读改写。

控制器包含：

- 时间戳、名称、有限值和关节范围校验
- 100 ms 输入 watchdog
- watchdog 后保持当前姿态
- 恢复输入前的主臂/从臂对齐检查
- 夹爪速度滤波和移动/保持扭矩限制
- 退出与异常路径的最终失能

## 3. State

`/rebotarm/joint_states` 是从臂 state。低层流模式下，控制器读取 motorbridge 后台
CAN 响应更新的最新缓存，避免在 120 Hz 命令路径中额外插入七电机同步查询。

缓存并不等于永久旧值：每个下发周期产生的 CAN 响应会持续更新它。若底层响应停止，
diagnostics/watchdog 和样本时间应被用于识别异常，而不是把旧缓存当作有效新反馈。

## 4. 采集

两颗 UVC 相机分别发布 `/head/*` 与 `/camera_wrist/*`。RQT 只负责显示；
`keyboard_collection_node` 独立启动 `ros2 bag record`，因此关闭 RQT 不会改变 Topic
名称或录包结构。

录制结束后打印的频率含义：

| 字段 | 含义 |
|---|---|
| `action_in` | rosbag 中收到的 `/teleop/action` 频率 |
| `action_applied` | 控制器通过校验并实际应用的 `/teleop/applied` 频率 |
| `state` | `/rebotarm/joint_states` 频率 |
| `head_image` | `/head/image_raw` 频率 |
| `camera_wrist_image` | `/camera_wrist/image_raw` 频率 |

这些值是 rosbag 元数据中的消息数除以 bag 时长，不是仅依据配置值推断。
