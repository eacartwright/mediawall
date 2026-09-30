"""
App-wide settings (not per project), shown in the Settings dialog.

Stored with Qt's QSettings: the registry on Windows
(HKEY_CURRENT_USER\\Software\\MediaWall\\MediaWall), and
~/.config/MediaWall/MediaWall.conf on Linux. Set the environment
variable MEDIAWALL_SETTINGS to an .ini file path to use that file
instead (tests use this, so they never touch the real settings).

Each setting is a Qt property that QML binds to, so a change applies
everywhere at once, and is saved immediately.
"""

import os

from PySide6.QtCore import Property, QObject, QSettings, Signal, Slot


# Mouse-wheel zoom: percent larger per wheel notch.
ZOOM_STEP_KEY = "zoom/stepPercent"
ZOOM_STEP_DEFAULT = 10.0
ZOOM_STEP_MIN = 1.0
ZOOM_STEP_MAX = 50.0


class AppSettings(QObject):

    zoomStepChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        path = os.environ.get("MEDIAWALL_SETTINGS")
        if path:
            self._settings = QSettings(path, QSettings.IniFormat)
        else:
            self._settings = QSettings("MediaWall", "MediaWall")

    # ---- Mouse-wheel zoom step ----

    @staticmethod
    def _clamp_zoom_step(value):
        return round(min(ZOOM_STEP_MAX, max(ZOOM_STEP_MIN, float(value))), 1)

    def _get_zoom_step(self):
        try:
            value = float(self._settings.value(ZOOM_STEP_KEY, ZOOM_STEP_DEFAULT))
        except (TypeError, ValueError):
            value = ZOOM_STEP_DEFAULT
        return self._clamp_zoom_step(value)

    def _set_zoom_step(self, value):
        value = self._clamp_zoom_step(value)
        if value == self._get_zoom_step():
            return
        self._settings.setValue(ZOOM_STEP_KEY, value)
        self._settings.sync()
        self.zoomStepChanged.emit()

    # Percent per wheel notch (e.g. 10 = each notch zooms 10%).
    zoomStep = Property(float, _get_zoom_step, _set_zoom_step, notify=zoomStepChanged)

    def _get_zoom_step_default(self):
        return ZOOM_STEP_DEFAULT

    zoomStepDefault = Property(float, _get_zoom_step_default, constant=True)

    def _get_zoom_step_min(self):
        return ZOOM_STEP_MIN

    zoomStepMin = Property(float, _get_zoom_step_min, constant=True)

    def _get_zoom_step_max(self):
        return ZOOM_STEP_MAX

    zoomStepMax = Property(float, _get_zoom_step_max, constant=True)

    @Slot()
    def resetZoomStep(self):
        self._set_zoom_step(ZOOM_STEP_DEFAULT)
