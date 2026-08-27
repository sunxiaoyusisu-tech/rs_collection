from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from ament_index_python.packages import get_package_share_directory


def main() -> None:
    """Run the saved, side-by-side dual-camera RQT perspective."""
    package_share = Path(get_package_share_directory("rebot_collection"))
    template = package_share / "config" / "dual_camera_rqt.ini"
    if not template.is_file():
        raise FileNotFoundError(f"RQT template is missing: {template}")

    with tempfile.TemporaryDirectory(prefix="rebot_collection_rqt_") as temp_dir:
        config_root = Path(temp_dir)
        rqt_config_dir = config_root / "ros.org"
        rqt_config_dir.mkdir(parents=True)
        shutil.copyfile(template, rqt_config_dir / "rqt_gui.ini")

        environment = os.environ.copy()
        environment["XDG_CONFIG_HOME"] = str(config_root)
        # Force XWayland so the saved 1400x850 centered geometry is restored
        # consistently on this GNOME Wayland desktop.
        environment.setdefault("QT_QPA_PLATFORM", "xcb")
        process = subprocess.Popen(
            [
                "rqt",
                "--force-discover",
                "--lock-perspective",
                "--freeze-layout",
            ],
            env=environment,
            start_new_session=True,
        )
        stopping = False

        def forward_signal(signum: int, _frame) -> None:
            nonlocal stopping
            stopping = True
            if process.poll() is None:
                os.killpg(process.pid, signum)

        signal.signal(signal.SIGINT, forward_signal)
        signal.signal(signal.SIGTERM, forward_signal)
        return_code = process.wait()
        # rqt_image_view can segfault while unloading its C++ plugin during a
        # requested shutdown. Treat that known teardown-only failure as clean.
        if stopping and return_code == -signal.SIGSEGV:
            return
        if return_code not in (0, -signal.SIGINT, -signal.SIGTERM):
            raise SystemExit(return_code)


if __name__ == "__main__":
    main()
