"""
The UI font on Linux.

Qt takes its default font from the desktop. On some Linux setups (seen
on Linux Mint with the PySide6 wheels) that comes back as a fixed-width
face, so every button and label looks like a terminal. If so, use the
system's normal sans-serif font instead: fontconfig's choice
(`fc-match sans-serif`), or else a common one that is installed.

Windows and macOS are left alone.
"""

import shutil
import subprocess
import sys

from PySide6.QtGui import QFontDatabase, QFontInfo

# Tried in order when fontconfig can't be asked.
FALLBACK_FAMILIES = ("Ubuntu", "Noto Sans", "Cantarell", "DejaVu Sans",
                     "Liberation Sans", "FreeSans")


def _fontconfig_sans():
    """The family fontconfig uses for "sans-serif", or ""."""
    if not shutil.which("fc-match"):
        return ""
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{family[0]}", "sans-serif"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def fix_linux_ui_font(app):
    """Call after creating the QApplication, before loading QML."""
    if not sys.platform.startswith("linux"):
        return

    font = app.font()
    info = QFontInfo(font)
    print(f"UI font: {info.family()} {font.pointSizeF():g} pt"
          f"{' (fixed-width)' if info.fixedPitch() else ''}")
    if not info.fixedPitch():
        return

    installed = set(QFontDatabase.families())
    for family in (_fontconfig_sans(),) + FALLBACK_FAMILIES:
        if family and family in installed:
            candidate = type(font)(font)
            candidate.setFamily(family)
            if not QFontInfo(candidate).fixedPitch():
                app.setFont(candidate)
                print(f"UI font: using {family} instead")
                return

    print("UI font: no proportional font found; keeping the default")
