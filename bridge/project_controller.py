"""
Qt bridge for project files: New / Open / Save / Save As,
unsaved-changes prompts, and the window title.

The file format itself lives in core/project.py.
"""

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.project import FILE_EXTENSION, ProjectError, load_project, save_project
from core.scene import Scene


FILE_FILTER = f"MediaWall Project (*{FILE_EXTENSION});;All Files (*)"

# Warnings beyond this many are summarized as "...and N more".
MAX_LISTED_WARNINGS = 8


class ProjectController(QObject):

    titleChanged = Signal()
    dirtyChanged = Signal()

    def __init__(self, scene_model, parent=None):
        super().__init__(parent)
        self._model = scene_model
        self._path = ""
        self._dirty = False
        self._last_dir = str(Path.home())

        scene_model.modified.connect(self._on_modified)

    # -------------------------------------------------
    # Properties
    # -------------------------------------------------

    def _get_title(self):
        name = Path(self._path).stem if self._path else "Untitled"
        star = "*" if self._dirty else ""
        return f"{name}{star} — MediaWall"

    title = Property(str, _get_title, notify=titleChanged)

    def _get_dirty(self):
        return self._dirty

    dirty = Property(bool, _get_dirty, notify=dirtyChanged)

    def _set_dirty(self, dirty):
        if dirty != self._dirty:
            self._dirty = dirty
            self.dirtyChanged.emit()
            self.titleChanged.emit()

    def _set_path(self, path):
        self._path = path
        if path:
            self._last_dir = str(Path(path).parent)
        self.titleChanged.emit()

    def _on_modified(self):
        self._set_dirty(True)

    # -------------------------------------------------
    # Actions
    # -------------------------------------------------

    @Slot()
    def newProject(self):
        if not self._confirm_discard():
            return

        self._model.setScene(Scene())
        self._set_path("")
        self._set_dirty(False)

    @Slot()
    def openProject(self):
        if not self._confirm_discard():
            return

        path, _ = QFileDialog.getOpenFileName(
            None, "Open Project", self._last_dir, FILE_FILTER
        )
        if not path:
            return

        self.openPath(path)

    @Slot(str, result=bool)
    def openPath(self, path):
        try:
            scene, warnings = load_project(path)
        except ProjectError as exc:
            QMessageBox.critical(None, "Couldn't Open Project", str(exc))
            return False

        self._model.setScene(scene)
        self._set_path(str(Path(path).resolve()))
        self._set_dirty(False)

        self._report_load_problems(scene, warnings)
        return True

    @Slot(result=bool)
    def save(self):
        if not self._path:
            return self.saveAs()
        return self._write(self._path)

    @Slot(result=bool)
    def saveAs(self):
        start = self._path or str(Path(self._last_dir) / f"Untitled{FILE_EXTENSION}")

        path, _ = QFileDialog.getSaveFileName(
            None, "Save Project As", start, FILE_FILTER
        )
        if not path:
            return False

        if not path.lower().endswith(FILE_EXTENSION):
            path += FILE_EXTENSION

        return self._write(path)

    @Slot(result=bool)
    def confirmClose(self):
        """Called when the window closes. False cancels the close."""
        return self._confirm_discard()

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    def _write(self, path):
        try:
            save_project(self._model.scene, path)
        except OSError as exc:
            QMessageBox.critical(
                None, "Couldn't Save Project",
                f"The project could not be saved to:\n{path}\n\n"
                f"{exc.strerror or exc}"
            )
            return False

        self._set_path(str(Path(path).resolve()))
        self._set_dirty(False)
        return True

    def _confirm_discard(self):
        """True if it's OK to throw away the current scene."""
        if not self._dirty:
            return True

        answer = QMessageBox.question(
            None,
            "Unsaved Changes",
            "Save changes to this project first?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def _report_load_problems(self, scene, warnings):
        missing = [s for s in scene.sources.values() if s.missing]

        if not missing and not warnings:
            return

        lines = []

        if missing:
            count = len(missing)
            if count == 1:
                lead = "1 media file could not be found. It is"
            else:
                lead = f"{count} media files could not be found. They are"
            lines.append(
                f"{lead} shown on the canvas as missing, and the saved "
                f"locations are kept in the project."
            )
            for source in missing[:MAX_LISTED_WARNINGS]:
                lines.append(f"  • {source.path}")
            if count > MAX_LISTED_WARNINGS:
                lines.append(f"  …and {count - MAX_LISTED_WARNINGS} more")

        if warnings:
            if lines:
                lines.append("")
            lines.append("Some parts of the project file could not be read:")
            for warning in warnings[:MAX_LISTED_WARNINGS]:
                lines.append(f"  • {warning}")
            if len(warnings) > MAX_LISTED_WARNINGS:
                lines.append(f"  …and {len(warnings) - MAX_LISTED_WARNINGS} more")

        QMessageBox.warning(None, "Project Opened With Problems", "\n".join(lines))
