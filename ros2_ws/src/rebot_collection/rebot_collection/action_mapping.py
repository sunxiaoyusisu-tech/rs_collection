from __future__ import annotations

import math
from collections.abc import Mapping


LEADER_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_yaw",
    "wrist_roll",
    "gripper",
]
FOLLOWER_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper"]

# These are intentionally identical to SeeedB601RSFollowerConfig.  Keeping the
# mapping in one pure, tested function makes the ROS path numerically comparable
# with the established run_teleop path without opening CAN from two processes.
JOINT_DIRECTIONS = [1.0, 1.0, -1.0, -1.0, -1.0, 1.0, 6.0]
JOINT_LIMITS_DEG = [
    (-145.0, 145.0),
    (0.0, 170.0),
    (0.0, 200.0),
    (-80.0, 90.0),
    (-90.0, 90.0),
    (-130.0, 130.0),
    (0.0, 270.0),
]


def map_leader_degrees_to_follower_radians(
    leader_positions: Mapping[str, float],
) -> list[float]:
    """Apply the current LeRobot B601-RS direction, scale and clip mapping."""
    missing = [name for name in LEADER_NAMES if name not in leader_positions]
    if missing:
        raise ValueError(f"leader sample is missing joints: {', '.join(missing)}")

    result: list[float] = []
    for name, direction, (lower, upper) in zip(
        LEADER_NAMES, JOINT_DIRECTIONS, JOINT_LIMITS_DEG, strict=True
    ):
        value = float(leader_positions[name])
        if not math.isfinite(value):
            raise ValueError(f"leader joint {name} is not finite")
        mapped = value * direction
        clipped = max(lower, min(upper, mapped))
        result.append(math.radians(clipped))
    return result
