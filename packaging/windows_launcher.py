"""
MediaWall.exe on Windows: starts MediaWall-app.exe with a hidden console.

The app itself is a console program, because the Log window can only
capture FFmpeg's output when the process has a console (see
bridge/log_capture.py). This small windowed program starts it with
CREATE_NO_WINDOW, so no console ever shows. It does the same job as
launcher.pyw does when running from source.
"""

import subprocess
import sys
from pathlib import Path

APP = Path(sys.executable).resolve().parent / "MediaWall-app.exe"

try:
    subprocess.Popen(
        [str(APP), *sys.argv[1:]],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
except OSError as error:
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, f"MediaWall couldn't start:\n{APP}\n\n{error}",
                                     "MediaWall", 0x10)
