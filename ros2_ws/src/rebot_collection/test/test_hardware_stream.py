import threading
import unittest
from types import SimpleNamespace

import numpy as np
from diagnostic_msgs.msg import DiagnosticStatus
from rclpy.serialization import serialize_message

from rebotarmcontroller.hardware_config import _ensure_rebot_sdk_in_syspath
from rebotarmcontroller.hardware_manager import HardwareManager
from rebotarmcontroller.teleop_stream import _diagnostic_level_as_byte

_ensure_rebot_sdk_in_syspath()
from reBotArm_control_py.actuator.rebotarm import JointCfg, JointGroup  # noqa: E402


class FakeGroup:
    def __init__(self, names, positions):
        self.joint_names = list(names)
        self.mode = "mit"
        self.positions = np.asarray(positions, dtype=np.float64)
        self.sent = []
        self.position_requests = []

    def send_mit(self, pos, **kwargs):
        self.sent.append((np.asarray(pos).copy(), kwargs))

    def get_positions(self, request_feedback=False):
        self.position_requests.append(request_feedback)
        return self.positions.copy()

    def get_velocities(self, request_feedback=False):
        return np.zeros(len(self.positions), dtype=np.float64)


class HardwareTeleopStreamTest(unittest.TestCase):
    def setUp(self):
        arm = FakeGroup([f"joint{i}" for i in range(1, 7)], np.zeros(6))
        gripper = FakeGroup(["gripper"], [0.2])
        motor_state = SimpleNamespace(torq=0.0, status_code=0)
        motor = SimpleNamespace(get_state=lambda: motor_state)

        hardware = HardwareManager.__new__(HardwareManager)
        hardware._cmd_lock = threading.RLock()
        hardware._arm_group = arm
        hardware._gripper_group = gripper
        hardware._robot = SimpleNamespace(
            has_gripper=True,
            _motor_map={"gripper": motor},
        )
        hardware._gripper_name = "gripper"
        hardware._enabled = True
        hardware._state_machine = "LOWLEVEL_STREAMING"
        hardware._arm_mit_kp = np.array([50, 150, 150, 50, 50, 50], dtype=float)
        hardware._arm_mit_kd = np.array([3, 10, 10, 5, 4, 4], dtype=float)
        hardware._teleop_gripper_prev_target = None
        hardware._teleop_gripper_prev_filtered_velocity = None
        hardware._teleop_gripper_prev_state_position = None
        hardware._teleop_gripper_prev_time = None
        hardware._gripper_target_position = None
        self.hardware = hardware
        self.arm = arm
        self.gripper = gripper

    def test_one_sample_uses_one_group_call_for_arm_and_gripper(self):
        target = np.linspace(0.0, 0.5, 6)
        self.hardware.send_teleop_targets(target, 1.0)
        self.assertEqual(len(self.arm.sent), 1)
        self.assertEqual(len(self.gripper.sent), 1)
        np.testing.assert_allclose(self.arm.sent[0][0], target)
        self.assertAlmostEqual(float(self.gripper.sent[0][1]["kd"][0]), 0.5)
        self.assertLessEqual(abs(float(self.gripper.sent[0][1]["tau"][0])), 3.5)
        self.assertEqual(self.gripper.position_requests, [False])

    def test_watchdog_hold_sends_current_position_once(self):
        self.arm.positions = np.linspace(-0.3, 0.2, 6)
        self.hardware.hold_teleop_position()
        self.assertEqual(len(self.arm.sent), 1)
        self.assertEqual(len(self.gripper.sent), 1)
        np.testing.assert_allclose(self.arm.sent[0][0], self.arm.positions)
        self.assertAlmostEqual(float(self.gripper.sent[0][1]["tau"][0]), 0.0)

    def test_rejects_wrong_arm_vector_length(self):
        with self.assertRaises(ValueError):
            self.hardware.send_teleop_targets([0.0, 1.0], 0.0)
        self.assertEqual(len(self.arm.sent), 0)

    def test_ros_diagnostic_byte_constants_are_serializable(self):
        message = DiagnosticStatus()
        message.level = _diagnostic_level_as_byte(DiagnosticStatus.WARN)
        self.assertEqual(message.level, b"\x01")
        self.assertGreater(len(serialize_message(message)), 0)

        message.level = _diagnostic_level_as_byte(2)
        self.assertEqual(message.level, b"\x02")
        self.assertGreater(len(serialize_message(message)), 0)

    def test_robstride_cache_only_position_read_avoids_parameter_transaction(self):
        class FakeMotor:
            def __init__(self):
                self.param_reads = 0

            def robstride_get_param_f32(self, _parameter):
                self.param_reads += 1
                return 1.0

            def get_state(self):
                return SimpleNamespace(pos=0.25)

        motor = FakeMotor()
        joint = JointCfg(
            name="gripper",
            motor_id=7,
            feedback_id=0xFD,
            model="rs-00",
            vendor="robstride",
        )
        group = JointGroup(
            "gripper",
            ["gripper"],
            [joint],
            {"gripper": motor},
            {"robstride": SimpleNamespace()},
        )
        np.testing.assert_allclose(
            group.get_positions(request_feedback=False),
            [0.25],
        )
        self.assertEqual(motor.param_reads, 0)


if __name__ == "__main__":
    unittest.main()
