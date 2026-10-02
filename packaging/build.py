"""
Build MediaWall's installer for the platform this runs on.

    Windows:  venv\\Scripts\\python.exe packaging\\build.py
    Linux:    venv/bin/python packaging/build.py

Needs the build requirements (pip install -r requirements-build.txt),
plus Inno Setup 6 on Windows (winget install JRSoftware.InnoSetup) or
dpkg-deb on Linux (already on Mint/Ubuntu).

Steps:
1. Icons: build/icon/ (a .ico and PNGs) from assets/mediawall.svg.
2. The app folder: dist/MediaWall/ (PyInstaller, packaging/mediawall.spec).
3. The installer, in dist/:
   Windows  MediaWall-<version>-Setup.exe  (packaging/windows/mediawall.iss)
   Linux    MediaWall_<version>_<arch>.deb (files in packaging/linux/)

`--app-only` stops after step 2 (to try dist/MediaWall/ directly).
Each platform's installer must be built on that platform.
"""

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.version import VERSION                                     # noqa: E402

PACKAGING = ROOT / "packaging"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
ICON_DIR = BUILD / "icon"
ICON_SVG = ROOT / "assets" / "mediawall.svg"
ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]

# The .deb's Maintainer field (dpkg requires one).
MAINTAINER = "evans.tools <7413334+eacartwright@users.noreply.github.com>"

# System libraries the Linux build needs that PySide6 doesn't bundle.
# apt installs any that are missing along with the .deb.
DEB_DEPENDS = [
    "libxcb-cursor0", "libxkbcommon-x11-0", "libgl1", "libegl1",
    "libfontconfig1", "libdbus-1-3", "libpulse0",
]


def step(text):
    print(f"\n== {text}", flush=True)


# ---- 1. Icons ----

def render_icons():
    """PNGs of the SVG at each size, and a Windows .ico holding them all."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication([])     # noqa: F841 (needed to paint)
    renderer = QSvgRenderer(str(ICON_SVG))
    ICON_DIR.mkdir(parents=True, exist_ok=True)

    pngs = []
    for size in ICON_SIZES:
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter)
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        png = bytes(data)
        (ICON_DIR / f"mediawall-{size}.png").write_bytes(png)
        pngs.append((size, png))

    write_ico(pngs, ICON_DIR / "mediawall.ico")


def write_ico(pngs, path):
    """An .ico file whose images are PNGs (supported since Windows Vista)."""
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = len(header) + 16 * len(pngs)
    entries, images = b"", b""
    for size, png in pngs:
        # Width and height are one byte each; 0 means 256.
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32,
                               len(png), offset + len(images))
        images += png
    path.write_bytes(header + entries + images)


# ---- 2. The app folder ----

def build_app():
    shutil.rmtree(DIST / "MediaWall", ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                    "--distpath", str(DIST), "--workpath", str(BUILD / "pyinstaller"),
                    str(PACKAGING / "mediawall.spec")], check=True, cwd=ROOT)


# ---- 3a. Windows installer (Inno Setup) ----

def find_iscc():
    candidates = [
        shutil.which("iscc"),
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return str(c)
    return None


def build_windows_installer():
    iscc = find_iscc()
    if not iscc:
        sys.exit("Inno Setup 6 wasn't found. Install it (winget install JRSoftware.InnoSetup) "
                 "and run this again.")
    subprocess.run([iscc, "/Qp",
                    f"/DAppVersion={VERSION}",
                    f"/DSourceDir={DIST / 'MediaWall'}",
                    f"/DOutputDir={DIST}",
                    f"/DIconFile={ICON_DIR / 'mediawall.ico'}",
                    str(PACKAGING / "windows" / "mediawall.iss")], check=True)
    return DIST / f"MediaWall-{VERSION}-Setup.exe"


# ---- 3b. Linux installer (.deb) ----

def build_deb():
    if not shutil.which("dpkg-deb"):
        sys.exit("dpkg-deb wasn't found (it comes with Debian, Ubuntu, and Mint).")
    arch = subprocess.run(["dpkg", "--print-architecture"], capture_output=True,
                          text=True, check=True).stdout.strip()
    tree = BUILD / "deb" / "mediawall"
    shutil.rmtree(tree, ignore_errors=True)

    # The app in /opt, started as `mediawall` from the PATH.
    shutil.copytree(DIST / "MediaWall", tree / "opt" / "mediawall", symlinks=True)
    (tree / "usr" / "bin").mkdir(parents=True)
    (tree / "usr" / "bin" / "mediawall").symlink_to("/opt/mediawall/mediawall")

    # Menu entry, icons, and the .mediawall file type.
    share = tree / "usr" / "share"
    linux = PACKAGING / "linux"
    copy(linux / "mediawall.desktop", share / "applications" / "mediawall.desktop")
    copy(linux / "mediawall-mime.xml", share / "mime" / "packages" / "mediawall.xml")
    copy(ICON_SVG, share / "icons" / "hicolor" / "scalable" / "apps" / "mediawall.svg")
    for size in ICON_SIZES:
        copy(ICON_DIR / f"mediawall-{size}.png",
             share / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "mediawall.png")

    size_kb = sum(f.stat().st_size for f in tree.rglob("*") if f.is_file() and not f.is_symlink()) // 1024
    (tree / "DEBIAN").mkdir()
    (tree / "DEBIAN" / "control").write_text("\n".join([
        "Package: mediawall",
        f"Version: {VERSION}",
        f"Architecture: {arch}",
        f"Maintainer: {MAINTAINER}",
        f"Installed-Size: {size_kb}",
        f"Depends: {', '.join(DEB_DEPENDS)}",
        "Section: graphics",
        "Priority: optional",
        "Description: Arrange images, GIFs, video, and audio on a free canvas",
        " MediaWall is a desktop app for building walls of media: place, size,",
        " rotate, and layer photos, GIFs, and videos on one canvas, browse",
        " folders beside it, and present the result full screen.",
        "",
    ]))

    # dpkg wants 755 folders and no group/other write access.
    for path in [tree, *tree.rglob("*")]:
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        if path.is_dir() or mode & 0o111:
            path.chmod(0o755)
        else:
            path.chmod(0o644)

    # The package name must be lowercase (Debian rule), but the file name
    # is free: capitalised to match the Windows installer.
    out = DIST / f"MediaWall_{VERSION}_{arch}.deb"
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(tree), str(out)], check=True)
    return out


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


# ----

def main():
    step(f"MediaWall {VERSION}: icons")
    render_icons()
    step("App folder (PyInstaller)")
    build_app()
    if "--app-only" in sys.argv:
        print(f"\nDone: {DIST / 'MediaWall'}")
        return
    step("Installer")
    out = build_windows_installer() if sys.platform == "win32" else build_deb()
    print(f"\nDone: {out}  ({out.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
