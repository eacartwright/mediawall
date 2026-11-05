"""
The Library's thumbnails (readme section 44.4): made by background
workers and kept in a disk cache, so QML only ever loads a small file.

What was asked for last is made first, so the tiles on screen come ahead
of those already scrolled past. Timing is in section 44.8: Qt's image
reader leaves Python's global lock free while it decodes, so scrolling
stays smooth while thumbnails are made.
"""

import os
import uuid

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThread, QThreadPool, QUrl, Signal
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter

from core.library import thumbnail_file


THUMBNAIL_SIZE = QSize(320, 320)
JPEG_QUALITY = 85

# Behind a picture with transparency, since JPEG has none: a tile's colour.
BACKGROUND = "#2a2a2a"


def make_thumbnail(source, target):
    """Read `source` scaled down, save it at `target`. False if it can't be read."""
    reader = QImageReader(source)
    reader.setAutoTransform(True)        # EXIF orientation
    size = reader.size()
    if size.isValid():
        reader.setScaledSize(size.scaled(THUMBNAIL_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
                             .expandedTo(QSize(1, 1)))
    image = reader.read()
    if image.isNull():
        return False
    if image.hasAlphaChannel():
        flat = QImage(image.size(), QImage.Format.Format_RGB32)
        flat.fill(QColor(BACKGROUND))
        painter = QPainter(flat)
        painter.drawImage(0, 0, image)
        painter.end()
        image = flat

    # A temporary name first, so a crash can't leave half a thumbnail.
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temporary = f"{target}.{uuid.uuid4().hex}.tmp"
    try:
        if not image.save(temporary, "JPEG", JPEG_QUALITY):
            return False
        os.replace(temporary, target)
    except OSError:
        return False
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


class _Job(QRunnable):

    def __init__(self, key, source, target, finished):
        super().__init__()
        self.key = key
        self.source = source
        self.target = target
        self.finished = finished

    def run(self):
        self.finished.emit(self.key, make_thumbnail(self.source, self.target))


class ThumbnailMaker(QObject):

    # (path, size, mtime): that file's thumbnail is ready, or has failed.
    finished = Signal(object, bool)
    # The same, once this object has noted the result: ask again now.
    updated = Signal(object)

    def __init__(self, cache_dir, parent=None):
        super().__init__(parent)
        self._cache_dir = cache_dir
        self._pool = QThreadPool(self)
        # One thread left for the rest of the app.
        self._pool.setMaxThreadCount(max(1, QThread.idealThreadCount() - 1))
        self._pending = []               # newest last
        self._queued = set()
        self._running = 0
        self._urls = {}                  # key -> file URL
        self._failed = set()
        self.finished.connect(self._job_finished)

    def url(self, path, size, mtime):
        """The thumbnail's URL, or "" while it's being made (or couldn't be)."""
        key = (path, size, mtime)
        url = self._urls.get(key)
        if url is not None:
            return url
        if key in self._failed:
            return ""
        target = thumbnail_file(self._cache_dir, path, size, mtime)
        if target.exists():
            url = QUrl.fromLocalFile(str(target)).toString()
            self._urls[key] = url
            return url
        if key not in self._queued:
            self._queued.add(key)
            self._pending.append(key)
            self._start_more()
        return ""

    def failed(self, path, size, mtime):
        return (path, size, mtime) in self._failed

    def clear_pending(self):
        """Another folder is showing: what's still waiting no longer matters."""
        self._queued.difference_update(self._pending)
        self._pending.clear()

    def shutdown(self):
        self.clear_pending()
        self.finished.disconnect(self._job_finished)
        self._pool.waitForDone()

    def _start_more(self):
        while self._pending and self._running < self._pool.maxThreadCount():
            key = self._pending.pop()
            self._running += 1
            target = thumbnail_file(self._cache_dir, *key)
            self._pool.start(_Job(key, key[0], str(target), self.finished))

    def _job_finished(self, key, ok):
        self._running -= 1
        self._queued.discard(key)
        if not ok:
            self._failed.add(key)
        self._start_more()
        self.updated.emit(key)
