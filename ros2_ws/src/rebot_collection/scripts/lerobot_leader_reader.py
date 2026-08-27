#!/usr/bin/env python3
"""Read the existing LeRobot leader driver and stream samples over localhost UDP.

This helper deliberately runs with the established ``lerobot`` Conda Python
(3.10), while the ROS 2 bridge runs with Jazzy's Python (3.12).  The split avoids
mixing incompatible rclpy extension modules and still executes the exact leader
class used by ``run_teleop``.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import socket
import time

from lerobot_teleoperator_rebot_arm_102.config_rebot_arm_102_leader import (
    RebotArm102LeaderConfig,
)
from lerobot_teleoperator_rebot_arm_102.rebot_arm_102_leader import RebotArm102Leader


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--serial-port", default="/dev/ttyUSB0")
    parser.add_argument("--leader-id", default="rebot_arm_102_leader")
    parser.add_argument("--rate", default=120.0, type=float)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False
        # The servo extension may still surface EINTR even with siginterrupt
        # disabled.  Suppress only the upstream emergency log while an orderly
        # shutdown is already in progress; genuine runtime read failures remain
        # fully visible and stop UDP samples for the controller watchdog.
        logging.getLogger(
            "lerobot_teleoperator_rebot_arm_102.rebot_arm_102_leader"
        ).setLevel(logging.CRITICAL)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    # Let an in-flight serial read finish normally on shutdown.  Without this,
    # Python interrupts the syscall and the upstream driver prints its genuine
    # cable-failure emergency warning during an otherwise normal Ctrl+C.
    signal.siginterrupt(signal.SIGINT, False)
    signal.siginterrupt(signal.SIGTERM, False)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    destination = (args.host, args.port)
    config = RebotArm102LeaderConfig(port=args.serial_port, id=args.leader_id)
    leader = RebotArm102Leader(config)
    leader.connect(calibrate=True)

    # get_action() intentionally retains the prior sample on a serial failure.
    # Track successful physical reads so a failure stops UDP output and lets the
    # ROS controller's 100 ms watchdog hold the follower instead of hiding it.
    physical_read_ok = False
    original_read = leader._read_raw_positions

    def tracked_read():
        nonlocal physical_read_ok
        result = original_read()
        physical_read_ok = True
        return result

    leader._read_raw_positions = tracked_read
    sequence = 0
    period = 1.0 / max(1.0, float(args.rate))
    deadline = time.perf_counter()

    try:
        while running:
            physical_read_ok = False
            action = leader.get_action()
            if physical_read_ok:
                positions = {
                    key.removesuffix(".pos"): float(value)
                    for key, value in action.items()
                    if key.endswith(".pos")
                }
                packet = json.dumps(
                    {
                        "sequence": sequence,
                        "source_monotonic_ns": time.monotonic_ns(),
                        "positions_deg": positions,
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                sock.sendto(packet, destination)
                sequence += 1

            deadline += period
            remaining = deadline - time.perf_counter()
            if remaining > 0.0:
                time.sleep(remaining)
            else:
                deadline = time.perf_counter()
    finally:
        if leader.is_connected:
            leader.disconnect()
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
