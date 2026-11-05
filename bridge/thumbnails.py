"""
The Library's thumbnails (readme section 44.4): made in the background and
kept in a disk cache, so QML only ever loads a small file. A file with a
length (animated image, video, audio) also gets that length, saved beside
its thumbnail, so it needn't be opened again to show it.

Pictures and animated images go to a pool of workers. Qt's image reader
leaves Python's global lock free while it decodes, so scrolling stays
smooth (section 44.8). Video and audio go one at a time to a single
QMediaPlayer with no output, on a thread of its own: on the UI thread its
work stalled the UI for up to 129 ms.

What was asked for last is made first, so the tiles on screen come ahead
of those already scrolled past.
"""

import os
import uuid
from pathlib import Path

from PySide6.QtCore import (
    QObject, QRunnable, QSize, Qt, QThread, QThreadPool, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink

from core.library import thumbnail_file
from core.media_browser import animation_duration_ms, is_animated


THUMBNAIL_SIZE = QSize(320, 320)
JPEG_QUALITY = 85

# Behind a picture with transparency, since JPEG has none: a tile's colour.
BACKGROUND = "#2a2a2a"

# Video and audio: give up on a file after this long.
GRAB_TIMEOUT_MS = 10000


def _duration_file(target):
    return Path(target).with_suffix(".txt")


def _write_duration(target, ms):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    _duration_file(target).write_text(str(int(ms)), encoding="ascii")


def _save_jpeg(image, target):
    """A temporary name first, so a crash can't leave half a thumbnail."""
    if image.hasAlphaChannel():
        flat = QImage(image.size(), QImage.Format.Format_RGB32)
        flat.fill(QColor(BACKGROUND))
        painter = QPainter(flat)
        painter.drawImage(0, 0, image)
        painter.end()
        image = flat
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


def make_thumbnail(source, target, animatable=False):
    """
    Read a picture scaled down, and save it at `target`. An animated one
    shows the frame at about 10%, to skip a blank start. False if it can't
    be read.
    """
    reader = QImageReader(source)
    reader.setAutoTransform(True)        # EXIF orientation
    size = reader.size()
    if size.isValid():
        reader.setScaledSize(size.scaled(THUMBNAIL_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
                             .expandedTo(QSize(1, 1)))
    if animatable and is_animated(source):
        try:
            _write_duration(target, animation_duration_ms(source))
        except OSError:
            pass
        image = QImage()
        for _ in range(max(1, reader.imageCount() // 10)):
            frame = reader.read()
            if frame.isNull():
                break
            image = frame
    else:
        image = reader.read()
    return not image.isNull() and _save_jpeg(image, target)


class _ImageJob(QRunnable):

    def __init__(self, key, source, target, animatable, finished):
        super().__init__()
        self.key = key
        self.source = source
        self.target = target
        self.animatable = animatable
        self.finished = finished

    def run(self):
        self.finished.emit(self.key, make_thumbnail(self.source, self.target, self.animatable))


class _PlayerWorker(QObject):
    """
    On its own thread: open one video or audio file, note its length, and
    for a video save the frame at about 10%.
    """

    finished = Signal(object, bool)

    def __init__(self):
        super().__init__()
        self._player = None
        self._key = None

    @Slot(object, str, str)
    def grab(self, key, media_type, target):
        if self._player is None:         # made here, to belong to this thread
            self._player = QMediaPlayer(self)
            self._sink = QVideoSink(self)
            self._player.setVideoSink(self._sink)
            self._player.mediaStatusChanged.connect(self._status_changed)
            self._player.errorOccurred.connect(lambda *_: self._finish(False))
            self._sink.videoFrameChanged.connect(self._frame)
            self._timeout = QTimer(self)
            self._timeout.setSingleShot(True)
            self._timeout.timeout.connect(lambda: self._finish(False))
        self._key = key
        self._media_type = media_type
        self._target = target
        self._seek_ms = None
        self._timeout.start(GRAB_TIMEOUT_MS)
        self._player.setSource(QUrl.fromLocalFile(key[0]))

    def _status_changed(self, status):
        loaded = (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia)
        if self._key is None or self._seek_ms is not None or status not in loaded:
            return
        try:
            _write_duration(self._target, self._player.duration())
        except OSError:
            pass
        if self._media_type == "audio":
            self._finish(True)
        elif not self._player.hasVideo():
            self._finish(False)          # a video file with only sound: no picture
        else:
            self._seek_ms = self._player.duration() // 10
            self._player.setPosition(self._seek_ms)
            self._player.pause()

    def _frame(self, frame):
        if self._key is None or self._seek_ms is None or not frame.isValid():
            return
        start = frame.startTime()
        # A frame left from before the seek doesn't count.
        if start >= 0 and start / 1000 < self._seek_ms - 1000:
            return
        image = frame.toImage().scaled(THUMBNAIL_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
        self._finish(not image.isNull() and _save_jpeg(image, self._target))

    def _finish(self, ok):
        if self._key is None:
            return
        key, self._key = self._key, None
        self._timeout.stop()
        self._player.stop()
        self._player.setSource(QUrl())
        self.finished.emit(key, ok)

    @Slot()
    def stop(self):
        """On quitting: the player must go on the thread it belongs to."""
        if self._player is not None:
            self._key = None
            self._player.stop()
            self._player.setSource(QUrl())
            self._player.setParent(None)
            self._player.deleteLater()
            self._player = None
        QThread.currentThread().quit()


class ThumbnailMaker(QObject):

    # (path, size, mtime): that file's thumbnail is ready, or has failed.
    finished = Signal(object, bool)
    # The same, once this object has noted the result: ask again now.
    updated = Signal(object)

    _grab = Signal(object, str, str)
    _stop_worker = Signal()

    def __init__(self, cache_dir, parent=None):
        super().__init__(parent)
        self._cache_dir = cache_dir
        self._pool = QThreadPool(self)
        # One thread left for the rest of the app.
        self._pool.setMaxThreadCount(max(1, QThread.idealThreadCount() - 1))
        self._images = []                # waiting, newest last: (key, animatable)
        self._players = []               # waiting, newest last: (key, media type)
        self._queued = set()
        self._running_images = 0
        self._player_busy = False
        self._urls = {}                  # key -> file URL
        self._durations = {}             # key -> ms
        self._failed = set()
        self._thread = None              # the player's, made when first needed
        self._worker = None
        self.finished.connect(self._job_finished)

    def url(self, path, size, mtime, media_type="image", animatable=False):
        """The thumbnail's URL, or "" while it's being made (or if there is none)."""
        key = (path, size, mtime)
        url = self._urls.get(key)
        if url is not None:
            return url
        if key in self._failed or key in self._queued:
            return ""
        target = thumbnail_file(self._cache_dir, path, size, mtime)
        if media_type == "audio":
            if not _duration_file(target).exists():
                self._queued.add(key)
                self._players.append((key, media_type))
                self._start_more()
            return ""
        if target.exists():
            url = QUrl.fromLocalFile(str(target)).toString()
            self._urls[key] = url
            return url
        self._queued.add(key)
        if media_type == "video":
            self._players.append((key, media_type))
        else:
            self._images.append((key, animatable))
        self._start_more()
        return ""

    def duration_ms(self, path, size, mtime):
        """The file's length, once known: 0 for a still picture, or until then."""
        key = (path, size, mtime)
        if key not in self._durations:
            target = thumbnail_file(self._cache_dir, path, size, mtime)
            try:
                self._durations[key] = int(_duration_file(target).read_text(encoding="ascii"))
            except (OSError, ValueError):
                return 0                 # not noted: it may still be coming
        return self._durations[key]

    def failed(self, path, size, mtime):
        return (path, size, mtime) in self._failed

    def clear_pending(self):
        """Another folder is showing: what's still waiting no longer matters."""
        self._queued.difference_update(key for key, _ in self._images)
        self._queued.difference_update(key for key, _ in self._players)
        self._images.clear()
        self._players.clear()

    def shutdown(self):
        self.clear_pending()
        self.finished.disconnect(self._job_finished)
        self._pool.waitForDone()
        if self._thread is not None:
            self._stop_worker.emit()
            self._thread.wait(3000)

    def _start_more(self):
        while self._images and self._running_images < self._pool.maxThreadCount():
            key, animatable = self._images.pop()
            self._running_images += 1
            target = thumbnail_file(self._cache_dir, *key)
            self._pool.start(_ImageJob(key, key[0], str(target), animatable, self.finished))
        if self._players and not self._player_busy:
            key, media_type = self._players.pop()
            self._player_busy = True
            self._ensure_worker()
            self._grab.emit(key, media_type, str(thumbnail_file(self._cache_dir, *key)))

    def _ensure_worker(self):
        if self._thread is not None:
            return
        self._thread = QThread(self)
        self._worker = _PlayerWorker()
        self._worker.moveToThread(self._thread)
        self._grab.connect(self._worker.grab)
        self._stop_worker.connect(self._worker.stop)
        self._worker.finished.connect(self._player_finished)
        self._thread.start()

    def _player_finished(self, key, ok):
        self._player_busy = False
        self._note(key, ok)

    def _job_finished(self, key, ok):
        self._running_images -= 1
        self._note(key, ok)

    def _note(self, key, ok):
        self._queued.discard(key)
        if not ok:
            self._failed.add(key)
        self._start_more()
        self.updated.emit(key)
