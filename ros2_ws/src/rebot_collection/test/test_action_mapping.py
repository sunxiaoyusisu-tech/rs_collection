import math
import unittest

from rebot_collection.action_mapping import map_leader_degrees_to_follower_radians


class ActionMappingTest(unittest.TestCase):
    def test_matches_existing_lerobot_direction_scale_and_clip(self):
        mapped = map_leader_degrees_to_follower_radians(
            {
                "shoulder_pan": 30.0,
                "shoulder_lift": 40.0,
                "elbow_flex": -50.0,
                "wrist_flex": 20.0,
                "wrist_yaw": -25.0,
                "wrist_roll": 60.0,
                "gripper": 20.0,
            }
        )
        expected_deg = [30.0, 40.0, 50.0, -20.0, 25.0, 60.0, 120.0]
        self.assertEqual(len(mapped), 7)
        for actual, expected in zip(mapped, expected_deg, strict=True):
            self.assertAlmostEqual(actual, math.radians(expected))

    def test_clips_after_direction_mapping(self):
        mapped = map_leader_degrees_to_follower_radians(
            {
                "shoulder_pan": 200.0,
                "shoulder_lift": -10.0,
                "elbow_flex": -300.0,
                "wrist_flex": 100.0,
                "wrist_yaw": -200.0,
                "wrist_roll": -200.0,
                "gripper": 100.0,
            }
        )
        expected_deg = [145.0, 0.0, 200.0, -80.0, 90.0, -130.0, 270.0]
        for actual, expected in zip(mapped, expected_deg, strict=True):
            self.assertAlmostEqual(actual, math.radians(expected))

    def test_rejects_incomplete_sample(self):
        with self.assertRaises(ValueError):
            map_leader_degrees_to_follower_radians({"shoulder_pan": 0.0})


if __name__ == "__main__":
    unittest.main()
