from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    serial_port = LaunchConfiguration("serial_port")
    conda_python = LaunchConfiguration("conda_python")
    head_camera_device = LaunchConfiguration("head_camera_device")
    camera_wrist_device = LaunchConfiguration("camera_wrist_device")

    official_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("rebotarm_bringup"), "launch", "bringup.launch.py"]
            )
        ),
        launch_arguments={
            "model": "rs",
            "channel": "can0",
            "joint_state_rate": "120.0",
            "cmd_arbitration": "reject",
            "arm_namespace": "rebotarm",
            "use_rviz": "false",
            "disable_after_safe_home": "true",
            "teleop_action_topic": "/teleop/action",
            "teleop_watchdog_s": "0.1",
            "teleop_max_command_age_s": "0.1",
            "teleop_resume_max_delta_rad": "0.35",
            "teleop_gripper_resume_max_delta_rad": "1.0",
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("serial_port", default_value="/dev/ttyUSB0"),
            DeclareLaunchArgument(
                "conda_python",
                default_value=PathJoinSubstitution(
                    [
                        EnvironmentVariable("HOME"),
                        "miniforge3",
                        "envs",
                        "lerobot",
                        "bin",
                        "python",
                    ]
                ),
            ),
            DeclareLaunchArgument(
                "head_camera_device",
                default_value=(
                    "/dev/v4l/by-id/"
                    "usb-icSpring_icspring_camera_20240307110322-video-index0"
                ),
            ),
            DeclareLaunchArgument(
                "camera_wrist_device",
                default_value=(
                    "/dev/v4l/by-id/"
                    "usb-RYS_USB_Camera_200901010001-video-index0"
                ),
            ),
            official_bringup,
            Node(
                package="rebot_collection",
                executable="leader_action_bridge",
                name="leader_action_bridge",
                output="screen",
                on_exit=Shutdown(reason="leader action bridge exited"),
                parameters=[
                    {
                        "serial_port": serial_port,
                        "leader_id": "rebot_arm_102_leader",
                        "conda_python": conda_python,
                        "rate": 120.0,
                        "source_timeout_s": 0.1,
                    }
                ],
            ),
            Node(
                package="usb_cam",
                executable="usb_cam_node_exe",
                namespace="head",
                name="camera",
                output="screen",
                parameters=[
                    {
                        "video_device": head_camera_device,
                        "framerate": 30.0,
                        "io_method": "mmap",
                        "frame_id": "head_optical_frame",
                        "pixel_format": "mjpeg2rgb",
                        "av_device_format": "YUV422P",
                        "image_width": 640,
                        "image_height": 480,
                        "camera_name": "head",
                        "camera_info_url": "",
                    }
                ],
            ),
            Node(
                package="usb_cam",
                executable="usb_cam_node_exe",
                namespace="camera_wrist",
                name="camera",
                output="screen",
                parameters=[
                    {
                        "video_device": camera_wrist_device,
                        "framerate": 30.0,
                        "io_method": "mmap",
                        "frame_id": "camera_wrist_optical_frame",
                        "pixel_format": "mjpeg2rgb",
                        "av_device_format": "YUV422P",
                        "image_width": 640,
                        "image_height": 480,
                        "camera_name": "camera_wrist",
                        "camera_info_url": "",
                    }
                ],
            ),
            Node(
                package="rebot_collection",
                executable="dual_camera_rqt",
                name="dual_camera_rqt",
                output="screen",
            ),
        ]
    )
