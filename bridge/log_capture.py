"""
Log capture: everything the app would print to a terminal, kept for the
in-app Log window and a log file.

Three sources end up in one place:

- FFmpeg (QtMultimedia) writes straight to the process's stderr file
  descriptor, so fd 1 and fd 2 are redirected into a pipe.
- Qt messages (qWarning, QML errors) go through a message handler.
- Python output and uncaught exceptions go through sys.stdout/stderr.

A reader thread splits the pipe into lines, copies them to the original
terminal (if there is one) and to the log file, and hands them to the
LogModel on the Qt main thread.

FFmpeg's own output is only capturable when the process has a console
(on Windows); launcher.pyw starts the app with a hidden console for that.
"""

import io
import os
import sys
import threading
import time
import traceback
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QObject,
    QStringListModel,
    QtMsgType,
    Signal,
    Slot,
    qInstallMessageHandler,
)
from PySide6.QtWidgets import QFileDialog, QMessageBox


MAX_LINES = 5000

_QT_LEVELS = {
    QtMsgType.QtDebugMsg: "debug",
    QtMsgType.QtInfoMsg: "info",
    QtMsgType.QtWarningMsg: "warning",
    QtMsgType.QtCriticalMsg: "critical",
    QtMsgType.QtFatalMsg: "fatal",
}


class LogModel(QStringListModel):
    """
    The captured lines, newest last, for the Log window.

    While paused, new lines are held back instead of shown, so the view
    stays still. Capture itself never stops (the log file and lineAdded's
    other listeners get every line), and resuming shows the held lines.
    """

    lineAdded = Signal(str)
    pausedChanged = Signal()
    heldCountChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paused = False
        self._held = []
        self._export_dir = str(Path.home())
        self.lineAdded.connect(self._append)

    def _append(self, line):
        if self._paused:
            self._held.append(line)
            if len(self._held) > MAX_LINES:
                del self._held[0]
            self.heldCountChanged.emit()
            return

        row = self.rowCount()
        self.insertRows(row, 1)
        self.setData(self.index(row), line)

        extra = self.rowCount() - MAX_LINES
        if extra > 0:
            self.removeRows(0, extra)

    # ---- Pause ----

    def _get_paused(self):
        return self._paused

    def _set_paused(self, paused):
        if paused == self._paused:
            return
        self._paused = paused
        if not paused and self._held:
            self.setStringList(self._lines()[-MAX_LINES:])
            self._held = []
            self.heldCountChanged.emit()
        self.pausedChanged.emit()

    paused = Property(bool, _get_paused, _set_paused, notify=pausedChanged)

    def _get_held_count(self):
        return len(self._held)

    # Lines captured while paused, not shown yet.
    heldCount = Property(int, _get_held_count, notify=heldCountChanged)

    # ---- Copy, export, clear ----

    def _lines(self):
        """Every line since the last Clear, held ones included."""
        return self.stringList() + self._held

    @Slot(result=str)
    def allText(self):
        return "\n".join(self._lines())

    @Slot(str, result=bool)
    def saveTo(self, path):
        """Write the lines (as allText) to a text file."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.allText() + "\n")
        except OSError as exc:
            QMessageBox.warning(None, "Couldn't Export Log", str(exc))
            return False
        return True

    @Slot(result=str)
    def exportLog(self):
        """Ask where to save, then save. Returns the path, or ""."""
        name = time.strftime("mediawall-log-%Y%m%d-%H%M%S.txt")
        path, _ = QFileDialog.getSaveFileName(
            None, "Export Log", str(Path(self._export_dir) / name),
            "Text Files (*.txt *.log);;All Files (*)")
        if not path or not self.saveTo(path):
            return ""
        self._export_dir = str(Path(path).parent)
        return path

    @Slot()
    def clear(self):
        self.setStringList([])
        if self._held:
            self._held = []
            self.heldCountChanged.emit()


class LogCapture(QObject):
    """
    Start as early as possible (before QApplication), so startup
    messages are captured too. `log_path` is overwritten each run;
    the previous run's log is kept next to it.
    """

    def __init__(self, log_path=None, parent=None):
        super().__init__(parent)

        self.model = LogModel(self)
        self._log_file = self._open_log_file(log_path)

        # The terminal we were started from, if any, so output still
        # shows there (debug launcher, running from a shell).
        self._terminal = self._dup_or_none(2)

        read_fd, self._write_fd = os.pipe()
        for fd in (1, 2):
            try:
                os.dup2(self._write_fd, fd)
            except OSError:
                pass    # no such stream; Python/Qt output still arrives
        self._point_windows_std_handles(self._write_fd)

        # Python's own streams write into the pipe too.
        stream = io.TextIOWrapper(
            os.fdopen(self._write_fd, "wb", buffering=0, closefd=False),
            encoding="utf-8", errors="replace", line_buffering=True,
        )
        sys.stdout = sys.stderr = stream
        sys.excepthook = self._excepthook

        qInstallMessageHandler(self._qt_message)

        threading.Thread(
            target=self._read, args=(read_fd,), daemon=True,
            name="log-capture",
        ).start()

    # -------------------------------------------------
    # Sources
    # -------------------------------------------------

    # Qt messages can come from any thread, so each is one os.write
    # (small pipe writes are atomic) rather than a shared stream.
    def _write(self, text):
        try:
            os.write(self._write_fd, text.encode("utf-8", "replace"))
        except OSError:
            pass

    def _qt_message(self, msg_type, context, message):
        level = _QT_LEVELS.get(msg_type, "debug")
        self._write(f"[{level}] {message}\n")

    def _excepthook(self, exc_type, exc, tb):
        self._write("".join(traceback.format_exception(exc_type, exc, tb)))

    # -------------------------------------------------
    # Reader thread
    # -------------------------------------------------

    def _read(self, read_fd):
        with os.fdopen(read_fd, "rb") as pipe:
            for raw in pipe:
                if self._terminal is not None:
                    try:
                        os.write(self._terminal, raw)
                    except OSError:
                        self._terminal = None

                line = raw.decode("utf-8", "replace").rstrip("\r\n")

                if self._log_file is not None:
                    try:
                        self._log_file.write(line + "\n")
                        self._log_file.flush()
                    except OSError:
                        self._log_file = None

                # Queued to the main thread (the model lives there).
                self.model.lineAdded.emit(line)

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    @staticmethod
    def _point_windows_std_handles(fd):
        """
        On Windows, FFmpeg writes to the process's standard handles, not
        to C file descriptors. dup2 updates those handles only in some
        setups (python.exe, not the installed PyInstaller build), so set
        them here too.
        """
        if sys.platform != "win32":
            return
        import ctypes
        import msvcrt
        try:
            handle = msvcrt.get_osfhandle(fd)
        except OSError:
            return
        for std in (-11, -12):      # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            ctypes.windll.kernel32.SetStdHandle(std, handle)

    @staticmethod
    def _dup_or_none(fd):
        try:
            return os.dup(fd)
        except OSError:
            return None

    @staticmethod
    def _open_log_file(log_path):
        if log_path is None:
            return None
        path = Path(log_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.replace(path.with_suffix(".previous" + path.suffix))
            return open(path, "w", encoding="utf-8")
        except OSError:
            return None
