"""
Tells QML when a key is really let go, so holding Left/Right can step
through files at the app's own pace (Settings) instead of the system's
key-repeat rate. QML's Shortcut fires on the press but has no release
signal, and a release only reaches whichever item has focus.

An application-wide event filter that only watches: it never consumes
an event. Key repeats (a held key's synthetic press/release pairs on
Linux X11) are skipped, so `released` means the key is really up.
"""

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtGui import QWindow


class KeyReleaseWatcher(QObject):

    # A Qt.Key value.
    released = Signal(int)

    def eventFilter(self, obj, event):
        # Each key event is also sent on to every item it passes through;
        # the window sees it once.
        if (event.type() == QEvent.KeyRelease
                and isinstance(obj, QWindow)
                and not event.isAutoRepeat()):
            self.released.emit(event.key())
        return False
