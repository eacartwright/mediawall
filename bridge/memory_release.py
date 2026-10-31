"""
Gives memory back after the whole wall is replaced (New, Open, New from
Layout). Destroyed media items free their memory inside the process, but
not all of it goes back to the system on its own:

- the QML engine frees destroyed objects' JavaScript wrappers only when
  its garbage collector runs;
- the scene graph keeps caches (textures, glyphs) until asked to drop
  them (QQuickWindow.releaseResources);
- on Linux, glibc keeps freed heap memory in the process for reuse, so
  the app still looks big in system tools. malloc_trim returns it.
  Windows has no equivalent call (its heap returns large blocks itself).

The before/after resident size goes to the log (Linux only).
"""

import ctypes
import ctypes.util
import sys

from PySide6.QtCore import QObject, QTimer

# Long enough for removed delegates (deleted on a later event-loop turn)
# and their video players to finish tearing down.
RELEASE_DELAY_MS = 500


def _load_malloc_trim():
    if not sys.platform.startswith("linux"):
        return None
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
        trim = libc.malloc_trim        # glibc only (not musl)
    except (OSError, AttributeError):
        return None
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    return trim


def _resident_mb():
    """This process's resident size in MB (Linux), or None."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return None


class MemoryRelease(QObject):

    def __init__(self, engine, scene_model, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._malloc_trim = _load_malloc_trim()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(RELEASE_DELAY_MS)
        self._timer.timeout.connect(self.release)

        scene_model.sceneReplaced.connect(self._timer.start)

    def release(self):
        before = _resident_mb()

        self._engine.collectGarbage()
        for window in self._engine.rootObjects():
            if hasattr(window, "releaseResources"):
                window.releaseResources()
        if self._malloc_trim is not None:
            self._malloc_trim(0)

        after = _resident_mb()
        if before is not None and after is not None:
            print(f"Memory released after replacing the wall: "
                  f"{before:.0f} MB -> {after:.0f} MB resident", flush=True)
