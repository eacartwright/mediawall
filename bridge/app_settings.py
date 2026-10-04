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
from PySide6.QtGui import QKeySequence

from core.recent import with_recent, without_recent


# Mouse-wheel zoom: percent larger per wheel notch.
ZOOM_STEP_KEY = "zoom/stepPercent"
ZOOM_STEP_DEFAULT = 10.0
ZOOM_STEP_MIN = 1.0
ZOOM_STEP_MAX = 50.0


# Playback speed range offered by the Playback tab's speed slider. The
# outer limits are core's SPEED_MIN / SPEED_MAX (0.25x .. 4x).
SPEED_MIN_KEY = "playback/speedMin"
SPEED_MIN_DEFAULT = 0.5
SPEED_MIN_RANGE = (0.25, 1.0)
SPEED_MAX_KEY = "playback/speedMax"
SPEED_MAX_DEFAULT = 3.0
SPEED_MAX_RANGE = (1.0, 4.0)


# Holding a key or button that steps through files (Left/Right arrows,
# thumb buttons, a held wheel tilt, the browser's arrow buttons): one
# step, a pause, then a step every interval until released. In ms.
STEP_DELAY_KEY = "stepping/repeatDelay"
STEP_DELAY_DEFAULT = 400
STEP_DELAY_RANGE = (100, 2000)
STEP_INTERVAL_KEY = "stepping/repeatInterval"
STEP_INTERVAL_DEFAULT = 150
STEP_INTERVAL_RANGE = (30, 1000)


# Recently opened or saved projects (Open Recent), newest first.
RECENT_KEY = "recent/projects"


class AppSettings(QObject):

    zoomStepChanged = Signal()
    speedRangeChanged = Signal()
    stepRepeatChanged = Signal()
    recentProjectsChanged = Signal()

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

    # ---- Playback speed range (the Playback tab's speed slider) ----

    def _read(self, key, default, low, high):
        try:
            value = float(self._settings.value(key, default))
        except (TypeError, ValueError):
            value = default
        return round(min(high, max(low, value)), 2)

    def _write(self, key, value, default, low, high, signal):
        value = round(min(high, max(low, float(value))), 2)
        if value == self._read(key, default, low, high):
            return
        self._settings.setValue(key, value)
        self._settings.sync()
        signal.emit()

    def _get_speed_min(self):
        return self._read(SPEED_MIN_KEY, SPEED_MIN_DEFAULT, *SPEED_MIN_RANGE)

    def _set_speed_min(self, value):
        self._write(SPEED_MIN_KEY, value, SPEED_MIN_DEFAULT, *SPEED_MIN_RANGE,
                    self.speedRangeChanged)

    # Slowest speed offered (0.25 .. 1).
    speedMin = Property(float, _get_speed_min, _set_speed_min, notify=speedRangeChanged)

    def _get_speed_max(self):
        return self._read(SPEED_MAX_KEY, SPEED_MAX_DEFAULT, *SPEED_MAX_RANGE)

    def _set_speed_max(self, value):
        self._write(SPEED_MAX_KEY, value, SPEED_MAX_DEFAULT, *SPEED_MAX_RANGE,
                    self.speedRangeChanged)

    # Fastest speed offered (1 .. 4).
    speedMax = Property(float, _get_speed_max, _set_speed_max, notify=speedRangeChanged)

    def _get_speed_min_default(self):
        return SPEED_MIN_DEFAULT

    speedMinDefault = Property(float, _get_speed_min_default, constant=True)

    def _get_speed_max_default(self):
        return SPEED_MAX_DEFAULT

    speedMaxDefault = Property(float, _get_speed_max_default, constant=True)

    @Slot()
    def resetSpeedRange(self):
        self._set_speed_min(SPEED_MIN_DEFAULT)
        self._set_speed_max(SPEED_MAX_DEFAULT)

    # ---- Hold to step through files ----

    def _get_step_delay(self):
        return int(self._read(STEP_DELAY_KEY, STEP_DELAY_DEFAULT, *STEP_DELAY_RANGE))

    def _set_step_delay(self, value):
        self._write(STEP_DELAY_KEY, int(value), STEP_DELAY_DEFAULT, *STEP_DELAY_RANGE,
                    self.stepRepeatChanged)

    # ms from the first step to the second while held.
    stepRepeatDelay = Property(int, _get_step_delay, _set_step_delay,
                               notify=stepRepeatChanged)

    def _get_step_interval(self):
        return int(self._read(STEP_INTERVAL_KEY, STEP_INTERVAL_DEFAULT,
                              *STEP_INTERVAL_RANGE))

    def _set_step_interval(self, value):
        self._write(STEP_INTERVAL_KEY, int(value), STEP_INTERVAL_DEFAULT,
                    *STEP_INTERVAL_RANGE, self.stepRepeatChanged)

    # ms between the steps after that.
    stepRepeatInterval = Property(int, _get_step_interval, _set_step_interval,
                                  notify=stepRepeatChanged)

    def _get_step_delay_default(self):
        return STEP_DELAY_DEFAULT

    stepRepeatDelayDefault = Property(int, _get_step_delay_default, constant=True)

    def _get_step_interval_default(self):
        return STEP_INTERVAL_DEFAULT

    stepRepeatIntervalDefault = Property(int, _get_step_interval_default, constant=True)

    @Slot()
    def resetStepRepeat(self):
        self._set_step_delay(STEP_DELAY_DEFAULT)
        self._set_step_interval(STEP_INTERVAL_DEFAULT)

    # ---- Shortcut display (the Settings dialog's Shortcuts tab) ----

    @Slot("QVariant", result=str)
    def shortcutText(self, shortcut):
        """
        An Action's shortcut as the platform writes it: a key string
        ("Ctrl+D") or a StandardKey number (QML passes those as ints).
        """
        if isinstance(shortcut, (int, float)) and not isinstance(shortcut, bool):
            seq = QKeySequence(QKeySequence.StandardKey(int(shortcut)))
        else:
            seq = QKeySequence(str(shortcut or ""))
        return seq.toString(QKeySequence.NativeText)

    # ---- Recent projects ----

    def _get_recent_projects(self):
        value = self._settings.value(RECENT_KEY, [])
        # QSettings returns a single string for a one-item list (ini files).
        if isinstance(value, str):
            value = [value]
        return [str(p) for p in (value or []) if p]

    def _set_recent_projects(self, paths):
        self._settings.setValue(RECENT_KEY, paths)
        self._settings.sync()
        self.recentProjectsChanged.emit()

    recentProjects = Property(list, _get_recent_projects, notify=recentProjectsChanged)

    @Slot(str)
    def addRecentProject(self, path):
        self._set_recent_projects(with_recent(self._get_recent_projects(), path))

    @Slot(str)
    def removeRecentProject(self, path):
        self._set_recent_projects(without_recent(self._get_recent_projects(), path))

    @Slot()
    def clearRecentProjects(self):
        self._set_recent_projects([])
