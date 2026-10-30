"""
The Media Memory window's data: every loaded media view (free media,
container content, browser previews) with an estimate of the video
memory it uses (core/media_cost.py), the GPU's measured usage where
nvidia-smi is available, and how often FFmpeg has had to give up on a
hardware decoder (counted from the log).

Each MediaView reports what it has loaded (report/forget); nothing is
computed until the window asks (refresh), so this costs nothing while
the window is closed.
"""

import os

from PySide6.QtCore import Property, QObject, QProcess, QUrl, Signal, Slot

from bridge.scene_model import _image_size
from core.media_cost import (
    HW_SOFTWARE,
    classify_log_line,
    estimate_bytes,
    format_bytes,
    parse_gpu_memory,
    parse_process_memory,
)


NVIDIA_SMI = "nvidia-smi"
GPU_QUERY = ["--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"]
PROCESS_QUERY = ["--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"]


class MediaMemory(QObject):

    changed = Signal()
    logCountsChanged = Signal()

    def __init__(self, hw_mode, parent=None):
        super().__init__(parent)
        self._hardware = hw_mode != HW_SOFTWARE
        self._views = {}            # token -> info dict from QML
        self._next_token = 1

        self._rows = []
        self._total = 0
        self._gpu_text = ""
        self._process_text = ""

        self._fallbacks = 0
        self._oom = 0

        # nvidia-smi runs in the background, so a slow call never stalls
        # playback. False once it's known not to be there.
        self._smi_available = True
        self._smi = None

    # -------------------------------------------------
    # Views (called by MediaView.qml)
    # -------------------------------------------------

    @Slot(result=int)
    def newToken(self):
        token = self._next_token
        self._next_token += 1
        return token

    @Slot(int, "QVariantMap")
    def report(self, token, info):
        """
        info: name, place ("canvas" | "container" | "browser" | "audio
        track"), objectId (what to select), url, kind ("image" |
        "animated" | "video" | "audio" | "none"), width and height (as
        decoded).
        """
        self._views[token] = dict(info)

    @Slot(int)
    def forget(self, token):
        self._views.pop(token, None)

    @Slot(str, result=list)
    def imageSize(self, url):
        """A still image's full size [w, h] (header only), or [0, 0]."""
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        return list(_image_size(path)) if path else [0, 0]

    # -------------------------------------------------
    # Log counts
    # -------------------------------------------------

    @Slot(str)
    def onLogLine(self, line):
        kind = classify_log_line(line)
        if kind == "fallback":
            self._fallbacks += 1
        elif kind == "oom":
            self._oom += 1
        else:
            return
        self.logCountsChanged.emit()

    def _get_fallbacks(self):
        return self._fallbacks

    # Videos FFmpeg moved to CPU decoding after a hardware decoder failed.
    fallbacks = Property(int, _get_fallbacks, notify=logCountsChanged)

    def _get_oom(self):
        return self._oom

    # Out-of-memory messages from the GPU driver.
    oomErrors = Property(int, _get_oom, notify=logCountsChanged)

    # -------------------------------------------------
    # Refresh (the window calls this every couple of seconds)
    # -------------------------------------------------

    @Slot()
    def refresh(self):
        rows = []
        # Still images of the same file at the same size share one
        # texture (Qt's image cache): charge it once. Each video and
        # animated image decodes on its own.
        charged = set()
        for token in sorted(self._views):
            info = self._views[token]
            kind = info.get("kind", "none")
            if kind == "none":
                continue
            width = int(info.get("width") or 0)
            height = int(info.get("height") or 0)
            shared = False
            if kind == "image":
                key = (info.get("url", ""), width, height)
                shared = key in charged
                charged.add(key)
            cost = 0 if shared else estimate_bytes(kind, width, height,
                                                   hardware=self._hardware)
            rows.append({
                "name": info.get("name", ""),
                "place": info.get("place", ""),
                "objectId": info.get("objectId", ""),
                "kind": kind,
                "size": f"{width} × {height}" if width > 0 and height > 0 else "",
                "bytes": cost,
                "cost": "shared" if shared else format_bytes(cost),
            })
        rows.sort(key=lambda r: (-r["bytes"], r["name"]))

        self._rows = rows
        self._total = sum(r["bytes"] for r in rows)
        self._query_gpu()
        self.changed.emit()

    def _get_rows(self):
        return self._rows

    # [{name, place, objectId, kind, size, bytes, cost}], biggest first.
    rows = Property(list, _get_rows, notify=changed)

    def _get_total_text(self):
        return format_bytes(self._total)

    totalText = Property(str, _get_total_text, notify=changed)

    def _get_hardware(self):
        return self._hardware

    # Videos counted as hardware-decoded (this run's setting).
    hardwareDecoding = Property(bool, _get_hardware, constant=True)

    def _get_gpu_text(self):
        return self._gpu_text

    # "7.6 GB of 8.00 GB" (whole GPU, all apps), or "" if unknown.
    gpuText = Property(str, _get_gpu_text, notify=changed)

    def _get_process_text(self):
        return self._process_text

    # This process's CUDA memory (the hardware decoders), or "".
    processText = Property(str, _get_process_text, notify=changed)

    # -------------------------------------------------
    # nvidia-smi
    # -------------------------------------------------

    def _query_gpu(self):
        if not self._smi_available or self._smi is not None:
            return
        self._run_smi(GPU_QUERY, self._gpu_done)

    @Slot()
    def shutdown(self):
        """
        On quit: stop a running nvidia-smi without its handlers, which
        would otherwise run while Python is shutting down.
        """
        self._smi_available = False
        process, self._smi = self._smi, None
        if process is not None:
            process.blockSignals(True)
            process.kill()
            process.waitForFinished(1000)

    def _run_smi(self, args, done):
        process = QProcess(self)
        self._smi = process

        def finished():
            text = bytes(process.readAllStandardOutput()).decode("utf-8", "replace")
            ok = process.exitStatus() == QProcess.NormalExit and process.exitCode() == 0
            process.deleteLater()
            self._smi = None
            done(text if ok else "")

        def failed(error):
            if error == QProcess.FailedToStart:
                self._smi_available = False
                process.deleteLater()
                self._smi = None

        process.finished.connect(finished)
        process.errorOccurred.connect(failed)
        process.start(NVIDIA_SMI, args)

    def _gpu_done(self, text):
        memory = parse_gpu_memory(text)
        self._gpu_text = (f"{format_bytes(memory[0])} of {format_bytes(memory[1])}"
                          if memory else "")
        self.changed.emit()
        if memory:
            self._run_smi(PROCESS_QUERY, self._process_done)

    def _process_done(self, text):
        used = parse_process_memory(text, os.getpid())
        self._process_text = format_bytes(used) if used is not None else ""
        self.changed.emit()
