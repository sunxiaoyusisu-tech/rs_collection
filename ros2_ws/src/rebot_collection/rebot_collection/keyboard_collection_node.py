from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import rclpy
import yaml
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


RECORDED_TOPICS = [
    "/leader/joint_states",
    "/teleop/action",
    "/teleop/applied",
    "/rebotarm/joint_states",
    "/rebotarm/gripper/state",
    "/rebotarm/arm_status",
    "/head/image_raw",
    "/head/camera_info",
    "/camera_wrist/image_raw",
    "/camera_wrist/camera_info",
    "/tf",
    "/tf_static",
    "/diagnostics",
    "/collection/event",
]
REQUIRED_LIVE_TOPICS = {
    "/leader/joint_states",
    "/teleop/action",
    "/teleop/applied",
    "/rebotarm/joint_states",
    "/head/image_raw",
    "/camera_wrist/image_raw",
}


def _unique_timestamp_path(parent: Path, timestamp_name: str) -> Path:
    """Return a timestamped rosbag path without overwriting an existing bag."""
    candidate = parent / timestamp_name
    suffix = 2
    while candidate.exists():
        candidate = parent / f"{timestamp_name}_{suffix:02d}"
        suffix += 1
    return candidate


class KeyboardCollectionNode(Node):
    def __init__(self) -> None:
        super().__init__("keyboard_collection_node")
        self.declare_parameter("bag_root", str(Path.home() / "sun_ws/data"))
        self.declare_parameter("minimum_free_gib", 20.0)

        self._bag_root = Path(str(self.get_parameter("bag_root").value)).expanduser()
        self._minimum_free_bytes = int(
            float(self.get_parameter("minimum_free_gib").value) * 1024**3
        )
        self._bag_root.mkdir(parents=True, exist_ok=True)

        self._event_publisher = self.create_publisher(
            String,
            "/collection/event",
            QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=10,
                reliability=ReliabilityPolicy.RELIABLE,
            ),
        )
        self._record_start_monotonic: float | None = None
        self._record_process: subprocess.Popen | None = None
        self._episode_path: Path | None = None
        self._episode_started_at: str | None = None

    @property
    def recording(self) -> bool:
        return self._record_process is not None

    def missing_required_topics(self) -> list[str]:
        available = {name for name, _types in self.get_topic_names_and_types()}
        return sorted(REQUIRED_LIVE_TOPICS - available)

    def start_recording(self) -> None:
        if self.recording:
            raise RuntimeError("an episode is already recording")
        missing = self.missing_required_topics()
        if missing:
            raise RuntimeError("required topics are missing: " + ", ".join(missing))
        usage = shutil.disk_usage(self._bag_root)
        if usage.free < self._minimum_free_bytes:
            raise RuntimeError(
                f"only {usage.free / 1024**3:.1f}GiB free; "
                f"at least {self._minimum_free_bytes / 1024**3:.1f}GiB is required"
            )

        started_at = datetime.now().astimezone()
        date_dir = self._bag_root / started_at.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        timestamp_name = started_at.strftime("%Y-%m-%d_%H-%M-%S")
        self._episode_path = _unique_timestamp_path(date_dir, timestamp_name)
        command = [
            "ros2",
            "bag",
            "record",
            "--storage",
            "mcap",
            "--compression-mode",
            "file",
            "--compression-format",
            "zstd",
            "--disable-keyboard-controls",
            "--output",
            str(self._episode_path),
            "--topics",
            *RECORDED_TOPICS,
        ]
        self._record_process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(0.8)
        if self._record_process.poll() is not None:
            code = self._record_process.returncode
            self._record_process = None
            self._record_start_monotonic = None
            raise RuntimeError(f"ros2 bag record exited immediately with code {code}")
        subscription_deadline = time.monotonic() + 3.0
        while (
            self._event_publisher.get_subscription_count() == 0
            and time.monotonic() < subscription_deadline
        ):
            time.sleep(0.05)
        if self._event_publisher.get_subscription_count() == 0:
            self.get_logger().warn(
                "rosbag event subscription was not discovered before recording start"
            )
        self._episode_started_at = started_at.isoformat()
        self._record_start_monotonic = time.monotonic()
        self._publish_event("start")
        print(f"\n[RECORDING] {self._episode_path}", flush=True)
        print("再次按 Enter：结束并安全写盘", flush=True)

    def stop_recording(self) -> None:
        process = self._record_process
        if process is None:
            return
        self._publish_event("stop")
        time.sleep(0.25)
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=20.0)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2.0)

        ended_at = datetime.now().astimezone().isoformat()
        wall_elapsed = max(
            1e-9,
            time.monotonic() - (self._record_start_monotonic or time.monotonic()),
        )
        duration_s, counts, rates = self._read_rosbag_statistics(wall_elapsed)
        self._write_metadata(
            ended_at, duration_s, counts, rates, process.returncode
        )
        episode_path = self._episode_path
        self._record_process = None
        self._record_start_monotonic = None
        self._episode_path = None
        print(f"\n[SAVED] {episode_path}", flush=True)
        print(
            "实测频率：action_in={:.1f}Hz, action_applied={:.1f}Hz, "
            "state={:.1f}Hz, head_image={:.1f}Hz, "
            "camera_wrist_image={:.1f}Hz".format(
                rates["action_input"],
                rates["action_applied"],
                rates["state"],
                rates["image_head"],
                rates["image_camera_wrist"],
            ),
            flush=True,
        )
        print("按 Enter：开始下一段；Ctrl+C：退出整条链路", flush=True)

    def _read_rosbag_statistics(
        self, fallback_duration_s: float
    ) -> tuple[float, dict[str, int], dict[str, float]]:
        if self._episode_path is None:
            return fallback_duration_s, {}, {}
        metadata_path = self._episode_path / "metadata.yaml"
        try:
            data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
            info = data["rosbag2_bagfile_information"]
            duration_s = max(
                1e-9, float(info["duration"]["nanoseconds"]) / 1_000_000_000.0
            )
            by_topic = {
                item["topic_metadata"]["name"]: int(item["message_count"])
                for item in info["topics_with_message_count"]
            }
            counts = {
                "action_input": by_topic.get("/teleop/action", 0),
                "action_applied": by_topic.get("/teleop/applied", 0),
                "state": by_topic.get("/rebotarm/joint_states", 0),
                "image_head": by_topic.get("/head/image_raw", 0),
                "image_camera_wrist": by_topic.get(
                    "/camera_wrist/image_raw", 0
                ),
            }
            rates = {key: count / duration_s for key, count in counts.items()}
            return duration_s, counts, rates
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
            self.get_logger().warn(f"could not parse rosbag statistics: {exc}")
            counts = {
                "action_input": 0,
                "action_applied": 0,
                "state": 0,
                "image_head": 0,
                "image_camera_wrist": 0,
            }
            rates = {key: 0.0 for key in counts}
            return fallback_duration_s, counts, rates

    def _publish_event(self, event: str) -> None:
        message = String()
        message.data = json.dumps(
            {
                "event": event,
                "episode": None if self._episode_path is None else self._episode_path.name,
                "wall_time": datetime.now().astimezone().isoformat(),
            },
            ensure_ascii=False,
        )
        self._event_publisher.publish(message)

    def _write_metadata(
        self,
        ended_at: str,
        duration_s: float,
        counts: dict[str, int],
        rates: dict[str, float],
        rosbag_return_code: int | None,
    ) -> None:
        if self._episode_path is None:
            return
        home = Path.home()
        official_workspace = Path(
            os.environ.get("REBOT_OFFICIAL_WS", home / "rebotarm_ros2")
        )
        official_repository = official_workspace
        if not (official_repository / ".git").is_dir():
            official_repository = (
                official_workspace / "src" / "reBotArmController_ROS2"
            )
        lerobot_root = Path(
            os.environ.get("REBOT_LEROBOT_ROOT", home / "rebot_lerobot")
        )
        metadata = {
            "format_version": 2,
            "architecture": "LeRobot leader -> ROS 2 /teleop/action -> official reBotArm controller",
            "robot": "reBotArm B601-RS",
            "output_path": str(self._episode_path),
            "started_at": self._episode_started_at,
            "ended_at": ended_at,
            "duration_s": duration_s,
            "hostname": socket.gethostname(),
            "target_rates_hz": {
                "control": 120.0,
                "state": 120.0,
                "image_head": 30.0,
                "image_camera_wrist": 30.0,
            },
            "observed_message_counts": counts,
            "observed_rates_hz": rates,
            "cameras": {
                "head": {
                    "image_topic": "/head/image_raw",
                    "camera_info_topic": "/head/camera_info",
                    "resolution": [640, 480],
                    "pixel_source": "MJPG",
                    "recorded_message": "sensor_msgs/msg/Image (raw)",
                },
                "camera_wrist": {
                    "image_topic": "/camera_wrist/image_raw",
                    "camera_info_topic": "/camera_wrist/camera_info",
                    "resolution": [640, 480],
                    "pixel_source": "MJPG",
                    "recorded_message": "sensor_msgs/msg/Image (raw)",
                },
            },
            "rosbag": {
                "storage": "mcap",
                "compression": "zstd",
                "compression_mode": "file",
                "return_code": rosbag_return_code,
                "topics": RECORDED_TOPICS,
            },
            "git_revisions": {
                "official_ros2": _git_revision(official_repository),
                "lerobot": _git_revision(lerobot_root / "lerobot"),
                "leader_plugin": _git_revision(
                    lerobot_root / "lerobot-teleoperator-rebot-arm-102"
                ),
                "follower_plugin": _git_revision(
                    lerobot_root / "lerobot-robot-seeed-b601"
                ),
            },
        }
        target = self._episode_path / "collection_metadata.json"
        target.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

def _git_revision(repository: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(args=None) -> None:
    rclpy.init(args=args)
    node = KeyboardCollectionNode()
    commands: queue.Queue[str] = queue.Queue()

    def read_keyboard() -> None:
        while True:
            line = sys.stdin.readline()
            if line == "":
                commands.put("exit")
                return
            commands.put("toggle")

    input_thread = threading.Thread(target=read_keyboard, daemon=True)
    input_thread.start()
    try:
        print("\nreBot RS ROS 2 数据采集已就绪。", flush=True)
        print("按 Enter：开始录制；再次按 Enter：结束并写盘；Ctrl+C：退出。", flush=True)
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            try:
                command = commands.get_nowait()
            except queue.Empty:
                continue
            if command == "exit":
                break
            try:
                if node.recording:
                    node.stop_recording()
                else:
                    node.start_recording()
            except Exception as exc:
                print(f"\n[ERROR] {exc}", flush=True)
                print("排除问题后再次按 Enter。", flush=True)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        if node.recording:
            print("\n正在结束 rosbag 并写入索引，请稍候……", flush=True)
            node.stop_recording()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
