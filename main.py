import os
import sys
from pathlib import Path

# Don't reuse Qt's compiled-QML cache. The QML files change often during
# development, and a stale cache can make the app fail to start with
# errors like "Type MediaObject unavailable" / "non-existent property".
# For a project this size the cache saves almost no startup time.
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QFileDialog

from bridge.project_controller import ProjectController
from bridge.scene_model import SceneModel
from core.media_browser import MediaBrowser


# Resolve everything relative to this file so the app works
# no matter which directory it is launched from.
APP_DIR = Path(__file__).resolve().parent
MAIN_QML = APP_DIR / "qml" / "Main.qml"


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
    app = QApplication(sys.argv)

    browser_backend = BrowserBackend()
    scene_model = SceneModel()
    project_controller = ProjectController(scene_model)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("browserBackend", browser_backend)
    context.setContextProperty("sceneModel", scene_model)
    context.setContextProperty("projectController", project_controller)

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
