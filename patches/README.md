# reBotArmController ROS 2 patch

`rebotarm_controller_teleop.patch` 基于：

- repository: `https://github.com/Seeed-Projects/reBotArmController_ROS2.git`
- commit: `39fbea54c7235b1c38bd025fc2e7308e42bd2fbe`

补丁增加整臂 `/teleop/action` 输入、`/teleop/applied`、watchdog、恢复对齐检查、
整组 MIT 下发、非阻塞 state cache 发布、夹爪扭矩控制和更可靠的异常失能路径。

使用 `scripts/apply_controller_patch.sh` 应用；不要手工复制单个文件，因为这些修改
跨越 bringup、controller、hardware manager 和 publisher。
