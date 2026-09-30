import os
import sys
from pathlib import Path

# Don't reuse Qt's compiled-QML cache. The QML files change often during
# development, and a stale cache can make the app fail to start with
# errors like "Type MediaObject unavailable" / "non-existent property".
# For a project this size the cache saves almost no startup time.
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtGui import QFontDatabase, QIcon, QSurfaceFormat
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QFileDialog

from bridge.app_settings import AppSettings
from bridge.log_capture import LogCapture
from bridge.project_controller import ProjectController
from bridge.scene_model import SceneModel
from core.media_browser import MediaBrowser


# An installed build (PyInstaller, see packaging/) is "frozen": its
# files are unpacked under sys._MEIPASS, and its own folder may not be
# writable (Program Files, /opt).
FROZEN = getattr(sys, "frozen", False)

# Resolve everything relative to the app's files so it works no matter
# which directory it is launched from.
APP_DIR = Path(sys._MEIPASS) if FROZEN else Path(__file__).resolve().parent
MAIN_QML = APP_DIR / "qml" / "Main.qml"
ICON_PATH = APP_DIR / "assets" / "mediawall.svg"


def log_dir():
    """
    Run from source: logs/ in the project folder. Installed: the user's
    own data folder, %LOCALAPPDATA%/MediaWall/logs on Windows and
    ~/.local/state/MediaWall/logs on Linux ($XDG_STATE_HOME if set).
    """
    if not FROZEN:
        return APP_DIR / "logs"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "MediaWall" / "logs"


LOG_PATH = log_dir() / "mediawall.log"


class BrowserBackend(QObject):

    def __init__(self):
        super().__init__()
        self.media_browser = MediaBrowser()

    @Slot(result=str)
    def chooseFolder(self):
        return QFileDialog.getExistingDirectory(
            None,
            "Choose Media Folder"
        )

    @Slot(str, result=bool)
    def folderExists(self, folder):
        return bool(folder) and Path(folder).is_dir()

    @Slot(str, bool, result=list)
    def scanFolder(self, folder, recursive):
        return self.media_browser.scan_folder(folder, recursive)


def main():
    # First, so startup messages are captured too: terminal output
    # (FFmpeg, Qt, Python) goes to the in-app Log window and LOG_PATH.
    log_capture = LogCapture(LOG_PATH)

    # 4x multisample anti-aliasing, so the edges of rotated media and
    # containers are smooth instead of jagged. (Per-item antialiasing
    # can't smooth a rotated container's clip.) Must be set before the
    # window is created.
    surface_format = QSurfaceFormat()
    surface_format.setSamples(4)
    QSurfaceFormat.setDefaultFormat(surface_format)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))

    # One Qt Quick Controls style on every platform, so Windows and Linux
    # look and behave the same. (The native Windows style also drew the
    # last button of a row with white text on a light face.)
    QQuickStyle.setStyle("Fusion")

    app_settings = AppSettings()
    browser_backend = BrowserBackend()
    scene_model = SceneModel()
    project_controller = ProjectController(scene_model)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("browserBackend", browser_backend)
    context.setContextProperty("sceneModel", scene_model)
    context.setContextProperty("projectController", project_controller)
    context.setContextProperty("appLog", log_capture.model)
    context.setContextProperty("appSettings", app_settings)
    context.setContextProperty(
        "fixedFontFamily",
        QFontDatabase.systemFont(QFontDatabase.FixedFont).family(),
    )

    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))

    if not engine.rootObjects():
        sys.exit(1)

    # Optional: open a project given on the command line,
    # e.g.  python main.py ~/walls/japan.mediawall
    if len(sys.argv) > 1:
        project_controller.openPath(sys.argv[1])

    exit_code = app.exec()

    # Shut down in the right order: destroy the QML engine (and every
    # binding in it) while the Python objects it references still exist.
    # Otherwise Python may free sceneModel first, and QML bindings
    # briefly see null during teardown.
    del engine

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
