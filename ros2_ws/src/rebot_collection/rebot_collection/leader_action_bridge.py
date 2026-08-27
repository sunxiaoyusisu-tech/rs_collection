from __future__ import annotations

import json
import socket
import subprocess
import threading
import time
from pathlib import Path

import rclpy
from ament_index_python.packages import get_package_share_directory
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState

from .action_mapping import (
    FOLLOWER_NAMES,
    LEADER_NAMES,
    map_leader_degrees_to_follower_radians,
)


def _diagnostic_level_as_byte(level: int | bytes | bytearray) -> bytes:
    """Accept both ROS/Jazzy byte constants and ordinary integer levels."""
    if isinstance(level, (bytes, bytearray)):
        if len(level) != 1:
            raise ValueError(f"diagnostic level must contain one byte: {level!r}")
        return bytes(level)
    value = int(level)
    if not 0 <= value <= 255:
        raise ValueError(f"diagnostic level is outside byte range: {value}")
    return bytes([value])


class LeaderActionBridge(Node):
    def __init__(self) -> None:
        super().__init__("leader_action_bridge")
        self.declare_parameter("serial_port", "/dev/ttyUSB0")
        self.declare_parameter("leader_id", "rebot_arm_102_leader")
        self.declare_parameter("rate", 120.0)
        self.declare_parameter(
            "conda_python",
            str(Path.home() / "miniforge3/envs/lerobot/bin/python"),
        )
        self.declare_parameter("source_timeout_s", 0.1)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self._action_publisher = self.create_publisher(
            JointState, "/teleop/action", qos
        )
        self._leader_publisher = self.create_publisher(
            JointState, "/leader/joint_states", qos
        )
        self._diagnostic_publisher = self.create_publisher(
            DiagnosticArray,
            "/diagnostics",
            QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE),
        )

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.settimeout(0.1)
        udp_port = int(self._socket.getsockname()[1])
        share = Path(get_package_share_directory("rebot_collection"))
        reader = share / "scripts" / "lerobot_leader_reader.py"
        conda_python = Path(str(self.get_parameter("conda_python").value))
        if not conda_python.is_file():
            raise FileNotFoundError(f"LeRobot Conda Python not found: {conda_python}")
        if not reader.is_file():
            raise FileNotFoundError(f"leader reader helper not found: {reader}")

        command = [
            str(conda_python),
            str(reader),
            "--host",
            "127.0.0.1",
            "--port",
            str(udp_port),
            "--serial-port",
            str(self.get_parameter("serial_port").value),
            "--leader-id",
            str(self.get_parameter("leader_id").value),
            "--rate",
            str(float(self.get_parameter("rate").value)),
        ]
        self._reader_process = subprocess.Popen(command)
        self._latest: dict | None = None
        self._latest_received_monotonic: float | None = None
        self._last_published_sequence = -1
        self._lock = threading.Lock()
        self._stop_receiver = threading.Event()
        self._receiver = threading.Thread(target=self._receive_loop, daemon=True)
        self._receiver.start()

        rate = max(1.0, float(self.get_parameter("rate").value))
        self._source_timeout_s = max(
            0.02, float(self.get_parameter("source_timeout_s").value)
        )
        self._timer = self.create_timer(1.0 / rate, self._publish_latest)
        self._health_timer = self.create_timer(1.0, self._publish_health)
        self.get_logger().info(
            f"LeRobot leader bridge started at {rate:.1f}Hz using {command[7]}"
        )

    def _receive_loop(self) -> None:
        while not self._stop_receiver.is_set():
            try:
                payload, _ = self._socket.recvfrom(65535)
                sample = json.loads(payload.decode("utf-8"))
                sequence = int(sample["sequence"])
                positions = sample["positions_deg"]
                if set(positions) != set(LEADER_NAMES):
                    raise ValueError("leader packet has unexpected joint names")
            except socket.timeout:
                continue
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                if not self._stop_receiver.is_set():
                    self.get_logger().warn(f"invalid leader packet: {exc}")
                continue
            with self._lock:
                self._latest = sample
                self._latest_received_monotonic = time.monotonic()

    def _publish_latest(self) -> None:
        if self._reader_process.poll() is not None:
            return
        with self._lock:
            sample = self._latest
            received = self._latest_received_monotonic
        if sample is None or received is None:
            return
        if time.monotonic() - received > self._source_timeout_s:
            return
        sequence = int(sample["sequence"])
        if sequence == self._last_published_sequence:
            return

        positions_deg = sample["positions_deg"]
        try:
            target_rad = map_leader_degrees_to_follower_radians(positions_deg)
        except ValueError as exc:
            self.get_logger().warn(f"leader mapping failed: {exc}")
            return

        stamp = self.get_clock().now().to_msg()
        leader_msg = JointState()
        leader_msg.header.stamp = stamp
        leader_msg.name = list(LEADER_NAMES)
        leader_msg.position = [
            float(positions_deg[name]) * 3.141592653589793 / 180.0
            for name in LEADER_NAMES
        ]
        self._leader_publisher.publish(leader_msg)

        action_msg = JointState()
        action_msg.header.stamp = stamp
        action_msg.name = list(FOLLOWER_NAMES)
        action_msg.position = target_rad
        self._action_publisher.publish(action_msg)
        self._last_published_sequence = sequence

    def _publish_health(self) -> None:
        process_code = self._reader_process.poll()
        with self._lock:
            received = self._latest_received_monotonic
        age = None if received is None else time.monotonic() - received
        if process_code is not None:
            level = DiagnosticStatus.ERROR
            message = f"LeRobot leader reader exited with code {process_code}"
        elif age is None:
            level = DiagnosticStatus.WARN
            message = "waiting for leader samples"
        elif age > self._source_timeout_s:
            level = DiagnosticStatus.ERROR
            message = f"leader sample stale for {age:.3f}s"
        else:
            level = DiagnosticStatus.OK
            message = "leader samples active"
        status = DiagnosticStatus()
        # In Jazzy these constants may already be one-byte bytes objects.
        status.level = _diagnostic_level_as_byte(level)
        status.name = "rebot_collection/leader_bridge"
        status.hardware_id = str(self.get_parameter("serial_port").value)
        status.message = message
        status.values = [
            KeyValue(
                key="last_sequence", value=str(self._last_published_sequence)
            ),
            KeyValue(
                key="sample_age_s", value="unknown" if age is None else f"{age:.4f}"
            ),
        ]
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.status = [status]
        self._diagnostic_publisher.publish(array)

    def close(self) -> None:
        self._stop_receiver.set()
        try:
            self._socket.close()
        except OSError:
            pass
        if self._reader_process.poll() is None:
            self._reader_process.terminate()
            try:
                self._reader_process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._reader_process.kill()
                self._reader_process.wait(timeout=2.0)
        self._receiver.join(timeout=1.0)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LeaderActionBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
