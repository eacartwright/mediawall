"""
Create double-clickable launchers for MediaWall on this machine.

Run once per machine, after creating the venv (paths are absolute, and
each machine has its own venv):

    Windows:  venv\\Scripts\\python.exe tools\\create_launchers.py [--desktop] [--start-menu]
    Linux:    venv/bin/python tools/create_launchers.py [--desktop]

Windows: "MediaWall.lnk" (no terminal) and "MediaWall (debug).lnk"
(terminal stays open) in the project folder, and optionally on the
Desktop / in the Start Menu. Pin either to the taskbar as usual.

Linux: "MediaWall" and "MediaWall (debug)" entries in the application
menu (~/.local/share/applications), and optionally on the Desktop.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


# -------------------------------------------------
# Windows
# -------------------------------------------------

def _ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def _windows_shortcut(path, target, arguments, description):
    script = "\n".join([
        "$shell = New-Object -ComObject WScript.Shell",
        f"$s = $shell.CreateShortcut({_ps_quote(path)})",
        f"$s.TargetPath = {_ps_quote(target)}",
        f"$s.Arguments = {_ps_quote(arguments)}",
        f"$s.WorkingDirectory = {_ps_quote(APP_DIR)}",
        f"$s.Description = {_ps_quote(description)}",
        "$s.Save()",
    ])
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                    "-Command", script], check=True)
    print(f"created {path}")


def _windows_folder(name):
    # Ask Windows: the Desktop is often redirected (e.g. to OneDrive).
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"[Environment]::GetFolderPath('{name}')"],
        check=True, capture_output=True, text=True,
    )
    return Path(result.stdout.strip())


def create_windows(folders):
    scripts = APP_DIR / "venv" / "Scripts"
    pythonw = scripts / "pythonw.exe"
    python = scripts / "python.exe"

    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        _windows_shortcut(
            folder / "MediaWall.lnk",
            pythonw, f'"{APP_DIR / "launcher.pyw"}"',
            "MediaWall",
        )
        # cmd /k keeps the terminal open after the app exits.
        _windows_shortcut(
            folder / "MediaWall (debug).lnk",
            os.environ.get("COMSPEC", "cmd.exe"),
            f'/k ""{python}" "{APP_DIR / "main.py"}""',
            "MediaWall with a terminal for messages",
        )


# -------------------------------------------------
# Linux
# -------------------------------------------------

def _desktop_entry(name, exec_line, terminal, comment):
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Comment={comment}",
        f"Exec={exec_line}",
        f"Path={APP_DIR}",
        f"Terminal={'true' if terminal else 'false'}",
        "Categories=AudioVideo;Graphics;",
        "",
    ])


def _write_entry(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    # Cinnamon/GNOME desktops only run launchers marked as trusted.
    subprocess.run(["gio", "set", str(path), "metadata::trusted", "true"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"created {path}")


def create_linux(also_desktop):
    python = APP_DIR / "venv" / "bin" / "python"
    entries = {
        "mediawall.desktop": _desktop_entry(
            "MediaWall",
            f'"{python}" "{APP_DIR / "main.py"}" %f',
            False, "Multimedia wall and presentation canvas",
        ),
        "mediawall-debug.desktop": _desktop_entry(
            "MediaWall (debug)",
            f'sh "{APP_DIR / "tools" / "run_debug.sh"}" %f',
            True, "MediaWall with a terminal for messages",
        ),
    }

    folders = [Path.home() / ".local" / "share" / "applications"]
    if also_desktop:
        folders.append(Path.home() / "Desktop")

    for folder in folders:
        for filename, text in entries.items():
            _write_entry(folder / filename, text)


# -------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--desktop", action="store_true",
                        help="also put the launchers on the Desktop")
    parser.add_argument("--start-menu", action="store_true",
                        help="Windows: also add them to the Start Menu")
    args = parser.parse_args()

    if sys.platform == "win32":
        folders = [APP_DIR]
        if args.desktop:
            folders.append(_windows_folder("Desktop"))
        if args.start_menu:
            folders.append(_windows_folder("Programs"))
        create_windows(folders)
    else:
        create_linux(args.desktop)


if __name__ == "__main__":
    main()
