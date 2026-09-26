"""
Start Media Wall without a terminal window.

Runs main.py with this project's own venv Python, passing any arguments
on (e.g. a project file). On Windows the app gets a hidden console
(CREATE_NO_WINDOW) rather than none at all, so the Log window can still
capture FFmpeg's output.

The Windows shortcut made by tools/create_launchers.py runs this with
venv\\Scripts\\pythonw.exe. (Linux menu entries start main.py directly.)
"""

import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent

if sys.platform == "win32":
    PYTHON = APP_DIR / "venv" / "Scripts" / "python.exe"
else:
    PYTHON = APP_DIR / "venv" / "bin" / "python"


def show_error(message):
    # pythonw has no terminal, so say what went wrong in a message box.
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "Media Wall", 0x10)
    else:
        print(message, file=sys.stderr)


def main():
    if not PYTHON.exists():
        show_error(f"Media Wall's virtual environment wasn't found:\n{PYTHON}\n\n"
                   "Create it first (see readme section 37).")
        return

    options = dict(
        cwd=APP_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True

    subprocess.Popen([str(PYTHON), str(APP_DIR / "main.py"), *sys.argv[1:]],
                     **options)


if __name__ == "__main__":
    main()
