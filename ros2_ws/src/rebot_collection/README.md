# reBotArm B601-RS ROS 2 teleoperation collection

The selected ownership model is:

`LeRobot leader driver -> /leader/joint_states + /teleop/action -> official ROS 2 controller -> can0`

Only the official `reBotArmController` process owns `can0`. The action and arm
state paths target 120 Hz. Two ROS `usb_cam` nodes decode the cameras' MJPG
streams and publish raw 640x480 images at 30 Hz. `keyboard_collection_node`
records MCAP rosbag2 episodes with lossless Zstd file compression.

Run from any terminal:

```bash
run_collection
```

Press Enter to start an episode, Enter again to finish it, and Ctrl+C to stop
the complete chain. The date is evaluated whenever recording starts. Bags are
stored as `~/sun_ws/data/YYYY-MM-DD/YYYY-MM-DD_HH-MM-SS/` by default; a same-second
collision receives `_02`, `_03`, and so on instead of overwriting data.

`run_collection` starts two `usb_cam` nodes and one half-screen RQT window with
side-by-side Image View panels. The physical camera/topic mapping is fixed:

- left panel: `head` camera on `/head/image_raw` and `/head/camera_info`
- right panel: `camera_wrist` on `/camera_wrist/image_raw` and
  `/camera_wrist/camera_info`

Both raw image streams and both camera-info streams are recorded in every bag.

The established `run_teleop` and `run_record` commands are independent and were
not replaced. Do not run either command concurrently with `run_collection`,
because only one process may own the CAN interface and leader serial port.
