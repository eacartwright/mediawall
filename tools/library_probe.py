"""
Measures the Library's unknowns (readme section 44.8, "To check first"),
so the same numbers can be taken on Windows and Mint. Throwaway: delete
this once the results are in the readme. From the project folder:

    python tools/library_probe.py images [--count 2000] [--threads 0]
    python tools/library_probe.py video  [--count 200] [--thread] [--keep DIR]
    python tools/library_probe.py drag   [--smoke]

`images` and `video` make a temporary folder of hard links to tests/media
(no extra disk space) and remove it afterwards. `drag` opens two windows
to try by hand: drag the blue box from one onto the other.
"""

import argparse
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import (QElapsedTimer, QObject, QRunnable, QSize, Qt, QThread, QThreadPool,
                            QTimer, QUrl, Signal, Slot)
from PySide6.QtGui import QGuiApplication, QImage, QImageReader

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "tests" / "media"
THUMB = QSize(320, 320)


def make_folder(sources, count):
    """A temporary folder of `count` links, cycling through `sources`."""
    folder = Path(tempfile.mkdtemp(prefix="mediawall-probe-"))
    for i in range(count):
        source = Path(sources[i % len(sources)])
        target = folder / f"{i:05}{source.suffix}"
        try:
            os.link(source, target)
        except OSError:                  # another drive, or no hard links
            shutil.copy(source, target)
    return folder


class StallWatch(QObject):
    """How long the UI thread was kept from running, by a fast timer's gaps."""

    def __init__(self):
        super().__init__()
        self.gaps = []
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(4)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self.gaps.clear()
        self._clock.start()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        self.gaps.append(self._clock.restart())

    def report(self):
        gaps = sorted(self.gaps) or [0]
        over = lambda ms: sum(1 for g in gaps if g > ms)
        return (f"UI thread: longest gap {gaps[-1]} ms, 99th percentile "
                f"{gaps[int(len(gaps) * 0.99)]} ms, over 33 ms {over(33)} times, "
                f"over 100 ms {over(100)} times, {len(gaps)} ticks")


# ---- images: QImageReader with a scaled size on a QThreadPool ----

class ThumbSignals(QObject):
    done = Signal(float, bool)


class ThumbJob(QRunnable):

    def __init__(self, path, out_dir, signals):
        super().__init__()
        self.path = path
        self.out_dir = out_dir
        self.signals = signals

    def run(self):
        started = time.perf_counter()
        reader = QImageReader(str(self.path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(THUMB, Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        ok = not image.isNull() and image.save(str(self.out_dir / f"{self.path.stem}.jpg"), "JPEG", 85)
        self.signals.done.emit(time.perf_counter() - started, ok)


def big_jpeg(folder):
    """A 24-megapixel photo-sized JPEG, scaled up from the sample."""
    image = QImage(str(MEDIA / "test_jpg.jpg"))
    big = image.scaled(6000, 4000, Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    path = Path(folder) / "big.jpg"
    big.save(str(path), "JPEG", 90)
    return path


def run_images(app, count, threads):
    work = Path(tempfile.mkdtemp(prefix="mediawall-probe-"))
    sources = [MEDIA / "test_jpg.jpg", big_jpeg(work), MEDIA / "test_png.png"]
    for source in sources:
        size = QImageReader(str(source)).size()
        print(f"  {source.name}: {size.width()}x{size.height()}, {source.stat().st_size // 1024} KB")
    folder = make_folder(sources, count)
    out_dir = work / "out"
    out_dir.mkdir()

    pool = QThreadPool.globalInstance()
    if threads:
        pool.setMaxThreadCount(threads)
    print(f"{count} images on {pool.maxThreadCount()} threads")

    watch = StallWatch()
    signals = ThumbSignals()
    times = []
    failed = [0]
    clock = time.perf_counter()

    def finished(seconds, ok):
        times.append(seconds)
        failed[0] += not ok
        if len(times) == count:
            app.quit()

    signals.done.connect(finished)
    for path in sorted(folder.iterdir()):
        pool.start(ThumbJob(path, out_dir, signals))
    watch.start()
    app.exec()
    watch.stop()
    total = time.perf_counter() - clock

    print(f"  {count / total:.0f} a second overall ({total:.1f} s), failed {failed[0]}; each: "
          f"median {statistics.median(times) * 1000:.0f} ms, longest {max(times) * 1000:.0f} ms")
    print("  " + watch.report())
    shutil.rmtree(folder, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)


def run_animated():
    """How long the frame at about 10% takes to reach in an animated file."""
    for name in ("test_gif.gif",):
        started = time.perf_counter()
        reader = QImageReader(str(MEDIA / name))
        frames = reader.imageCount()
        counted = time.perf_counter() - started
        image = QImage()
        for _ in range(max(1, frames // 10)):
            image = reader.read()
        print(f"  {name}: {frames} frames, counting {counted * 1000:.0f} ms, "
              f"frame at 10% in {(time.perf_counter() - started) * 1000:.0f} ms total, "
              f"{'ok' if not image.isNull() else 'FAILED'}")


# ---- video: one QMediaPlayer with a QVideoSink, on the UI thread ----

def is_blank(image):
    """True if a picture is one flat colour (a black frame, say)."""
    small = image.convertToFormat(QImage.Format.Format_Grayscale8).scaled(8, 8)
    values = [small.pixelColor(x, y).value() for x in range(8) for y in range(8)]
    return max(values) - min(values) < 8


class VideoGrabber(QObject):
    """One file at a time: load, seek to 10%, take one frame, save a thumbnail."""

    TIMEOUT_MS = 15000
    all_done = Signal()

    def __init__(self, files, out_dir):
        super().__init__()
        self.files = list(files)
        self.out_dir = out_dir
        self.index = -1
        self.state = "idle"
        self.results = []                # (suffix, seconds, ok, frame error ms)
        self.blank = 0

    @Slot()
    def begin(self):
        # Made here so that they belong to the thread this runs on.
        from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
        self.Status = QMediaPlayer.MediaStatus
        self.player = QMediaPlayer(self)
        self.sink = QVideoSink(self)
        self.player.setVideoSink(self.sink)
        self.player.mediaStatusChanged.connect(self.on_status)
        self.player.errorOccurred.connect(lambda *_: self.finish(False, None))
        self.sink.videoFrameChanged.connect(self.on_frame)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(lambda: self.finish(False, None))
        self.next()

    def next(self):
        self.index += 1
        if self.index >= len(self.files):
            self.player.deleteLater()
            self.all_done.emit()
            return
        self.started = time.perf_counter()
        self.state = "loading"
        self.timeout.start(self.TIMEOUT_MS)
        self.player.setSource(QUrl.fromLocalFile(str(self.files[self.index])))

    def on_status(self, status):
        if self.state == "loading" and status in (self.Status.LoadedMedia, self.Status.BufferedMedia):
            self.target_ms = self.player.duration() // 10
            self.state = "seeking"
            self.player.setPosition(self.target_ms)
            self.player.pause()

    def on_frame(self, frame):
        if self.state != "seeking" or not frame.isValid():
            return
        start = frame.startTime()
        # A frame left from before the seek doesn't count.
        if start >= 0 and start / 1000 < self.target_ms - 1000:
            return
        image = frame.toImage().scaled(THUMB, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
        self.blank += is_blank(image)
        ok = image.save(str(self.out_dir / f"{self.index:05}.jpg"), "JPEG", 85)
        self.finish(ok, start / 1000 - self.target_ms if start >= 0 else None)

    def finish(self, ok, error_ms):
        if self.state in ("idle", "done"):
            return
        self.state = "done"
        self.timeout.stop()
        self.results.append((self.files[self.index].suffix, time.perf_counter() - self.started, ok, error_ms))
        self.player.stop()
        self.player.setSource(QUrl())
        QTimer.singleShot(0, self.next)


def run_video(app, count, use_thread, keep):
    sources = [MEDIA / n for n in ("test_mp4.mp4", "test_mov.mov", "test_webm.webm")]
    folder = make_folder(sources, count)
    out_dir = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="mediawall-probe-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    grabber = VideoGrabber(sorted(folder.iterdir()), out_dir)
    grabber.all_done.connect(app.quit)
    thread = QThread()
    if use_thread:
        grabber.moveToThread(thread)
        thread.started.connect(grabber.begin)
    watch = StallWatch()
    clock = time.perf_counter()
    watch.start()
    if use_thread:
        thread.start()
    else:
        QTimer.singleShot(0, grabber.begin)
    app.exec()
    watch.stop()
    total = time.perf_counter() - clock
    thread.quit()
    thread.wait()

    print(f"{count} videos, {'own thread' if use_thread else 'UI thread'}: {count / total:.1f} a second "
          f"overall ({total:.1f} s), blank frames {grabber.blank}")
    for suffix in sorted({r[0] for r in grabber.results}):
        rows = [r for r in grabber.results if r[0] == suffix]
        times = [r[1] for r in rows]
        errors = [abs(r[3]) for r in rows if r[3] is not None]
        print(f"  {suffix}: median {statistics.median(times) * 1000:.0f} ms, longest "
              f"{max(times) * 1000:.0f} ms, failed {sum(1 for r in rows if not r[2])}/{len(rows)}, "
              f"frame off target by {max(errors) if errors else 0:.0f} ms at most")
    print("  " + watch.report())
    shutil.rmtree(folder, ignore_errors=True)
    if not keep:
        shutil.rmtree(out_dir, ignore_errors=True)


# ---- drag: a real file drag between two windows, tried by hand ----

DRAG_QML = """
import QtQuick
Item {
    Window {
        title: "Library (drag from here)"; width: 420; height: 300; x: 80; y: 120; visible: true
        Rectangle {
            id: box; width: 160; height: 100; x: 40; y: 40; color: "steelblue"
            Text { anchors.centerIn: parent; color: "white"; text: "drag me" }
            Drag.active: mouse.drag.active
            Drag.dragType: Drag.Automatic
            Drag.supportedActions: Qt.CopyAction
            Drag.mimeData: ({ "text/uri-list": dragUrl })
            Drag.onDragFinished: function (action) { console.log("drag finished, action", action) }
            MouseArea { id: mouse; anchors.fill: parent; drag.target: box }
        }
    }
    Window {
        title: "Wall (drop here)"; width: 420; height: 300; x: 520; y: 120; visible: true
        Rectangle {
            anchors.fill: parent
            color: drop.containsDrag ? "#c8e6c9" : "#eeeeee"
            Text {
                id: result; anchors.fill: parent; anchors.margins: 12; wrapMode: Text.WrapAnywhere
                text: "Drop the blue box here, or a file from the file manager."
            }
            DropArea {
                id: drop; anchors.fill: parent; keys: ["text/uri-list"]
                onDropped: function (d) {
                    result.text = "OK, dropped:\\n" + d.urls.join("\\n")
                    console.log("dropped", d.urls)
                    d.acceptProposedAction()
                }
            }
        }
    }
}
"""


def run_drag(app, smoke):
    from PySide6.QtQml import QQmlApplicationEngine
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda warnings: [print("QML:", w.toString()) for w in warnings])
    engine.rootContext().setContextProperty("dragUrl", QUrl.fromLocalFile(str(MEDIA / "test_jpg.jpg")).toString())
    engine.loadData(DRAG_QML.encode())
    if not engine.rootObjects():
        print("QML failed to load")
        return 1
    print("Drag the blue box into the other window; the result shows there. Close both to finish.")
    if smoke:
        QTimer.singleShot(500, app.quit)
    app.exec()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["images", "video", "drag"])
    parser.add_argument("--count", type=int)
    parser.add_argument("--threads", type=int, default=0, help="worker threads; 0 is Qt's default")
    parser.add_argument("--thread", action="store_true", help="video: run the player on its own thread")
    parser.add_argument("--keep", help="video: keep the thumbnails in this folder")
    parser.add_argument("--smoke", action="store_true", help="drag: just check that it opens")
    args = parser.parse_args()

    print(f"{sys.platform}, Qt {__import__('PySide6').__version__}, "
          f"{QThreadPool.globalInstance().maxThreadCount()} ideal threads")
    app = QGuiApplication(sys.argv[:1])
    if args.what == "images":
        run_animated()
        run_images(app, args.count or 2000, args.threads)
    elif args.what == "video":
        run_video(app, args.count or 200, args.thread, args.keep)
    else:
        return run_drag(app, args.smoke)
    return 0


if __name__ == "__main__":
    sys.exit(main())
