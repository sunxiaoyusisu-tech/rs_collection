import unittest

from diagnostic_msgs.msg import DiagnosticStatus

from rebot_collection.leader_action_bridge import _diagnostic_level_as_byte


class LeaderBridgeCompatibilityTest(unittest.TestCase):
    def test_diagnostic_level_accepts_jazzy_byte_and_integer(self):
        self.assertEqual(
            _diagnostic_level_as_byte(DiagnosticStatus.WARN),
            b"\x01",
        )
        self.assertEqual(_diagnostic_level_as_byte(2), b"\x02")


if __name__ == "__main__":
    unittest.main()
