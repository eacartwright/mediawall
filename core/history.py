"""
Undo/redo history.

Pure Python, no Qt.

The history stores whole-scene snapshots. A scene is small (a few
hundred objects at most, and media files are only paths), so copying
it per change is cheap, and snapshots make undo correct for every
action automatically, including ones added later.

Rapid repeated changes can be merged into one step (e.g. each notch
of a zoom wheel) by giving them the same merge key.
"""

from __future__ import annotations

import copy
import time

from core.scene import Scene


MAX_STEPS = 200
MERGE_WINDOW_SECONDS = 1.0


def snapshot(scene: Scene) -> Scene:
    """An independent copy of the scene's saved state (not selection)."""
    copy_ = Scene()
    copy_.sources = copy.deepcopy(scene.sources)
    copy_.objects = copy.deepcopy(scene.objects)
    return copy_


class History:

    def __init__(self, max_steps=MAX_STEPS):
        self._undo = []
        self._redo = []
        self._max = max_steps
        self._merge_key = None
        self._merge_time = 0.0

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    def clear(self):
        self._undo.clear()
        self._redo.clear()
        self._merge_key = None

    def record(self, before: Scene, merge_key=None, now=None):
        """
        Record that the scene just changed from `before`.

        If merge_key matches the previous change's key and it happened
        within the merge window, the two become one undo step.
        """
        now = time.monotonic() if now is None else now

        if (merge_key is not None and merge_key == self._merge_key
                and now - self._merge_time < MERGE_WINDOW_SECONDS
                and self._undo):
            self._merge_time = now
            self._redo.clear()
            return

        self._undo.append(before)
        if len(self._undo) > self._max:
            del self._undo[0]

        self._redo.clear()
        self._merge_key = merge_key
        self._merge_time = now

    def undo(self, current: Scene):
        """Return the state to go back to, or None."""
        if not self._undo:
            return None
        self._redo.append(current)
        self._merge_key = None
        return self._undo.pop()

    def redo(self, current: Scene):
        """Return the state to go forward to, or None."""
        if not self._redo:
            return None
        self._undo.append(current)
        self._merge_key = None
        return self._redo.pop()
