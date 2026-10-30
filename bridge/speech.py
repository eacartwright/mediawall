"""
Qt bridge: Speech (readme section 14.6). Runs Piper, the text-to-speech
program the user installs (its path and the voices folder are app
settings), to make clips for the Speech tab's Preview and for speech
tracks.

Clips are temporary: made into a folder that is deleted when Mediawall
closes, and found again by speech_key(), so each set of words and
settings is made once per session (identical tracks share a clip, and
undo switches back at once). Speech tracks have no file of their own; a
track asks for its clip (request()) when it's about to play.

One clip is made at a time, by a QProcess, so the window never waits.
A Preview goes before the tracks waiting.
"""

import os
import shutil
import tempfile

from PySide6.QtCore import (
    Property, QObject, QProcess, QProcessEnvironment, QUrl, Signal, Slot,
)

from core.speech import (
    VOICE_MODES, SPEECH_PITCH_RANGE, SPEECH_SILENCE_RANGE, SPEECH_SPEED_RANGE,
    normalized_speech, piper_settings, piper_text, repitch_wav, scan_voices, speech_key,
)


def piper_command(program):
    """
    (program, leading arguments) to run Piper. Checks (tests/app)
    replace this to run a stand-in script.
    """
    return program, []


def find_program(path):
    """The Piper program as a full path, or "" if it isn't there. A bare
    name ("piper") is looked up on PATH."""
    if not path:
        return ""
    if os.path.isfile(path):
        return path
    if os.path.dirname(path) == "":
        return shutil.which(path) or ""
    return ""


class _Job:
    """A clip to make, and who wants it: the Preview, tracks, or both."""

    def __init__(self, key, speech):
        self.key = key
        self.speech = speech
        self.preview = False
        self.track = False


class SpeechEngine(QObject):

    voicesChanged = Signal()
    stateChanged = Signal()
    # A clip was made, or failed (tracks re-read clipUrl / clipStatus).
    clipsChanged = Signal()
    # A clip to listen to (a file URL), and: stop listening.
    previewReady = Signal(str)
    previewStopped = Signal()

    def __init__(self, app_settings, parent=None):
        super().__init__(parent)
        self._settings = app_settings
        self._voices = {}
        self._temp = tempfile.TemporaryDirectory(prefix="mediawall-speech-")
        self._clips = {}            # key -> path of a made clip
        self._failed = {}           # key -> why it couldn't be made
        self._queue = []            # _Job, next first
        self._job = None            # the one being made
        self._process = None
        self._status = ""
        self._status_failed = False
        self._clips_version = 0
        app_settings.speechChanged.connect(self.rescan)
        self.rescan()

    # ---- Properties ----

    def _get_voices(self):
        return list(self._voices)

    voices = Property(list, _get_voices, notify=voicesChanged)

    def _get_ready(self):
        return bool(find_program(self._settings.piperPath)) and bool(self._voices)

    ready = Property(bool, _get_ready, notify=voicesChanged)

    def _get_problem(self):
        """Why Speech can't run yet ("" = it can)."""
        if not find_program(self._settings.piperPath):
            return ("Set the Piper program in Settings > Speech." if not self._settings.piperPath
                    else "Piper wasn't found at the path in Settings > Speech.")
        if not self._settings.voicesFolder:
            return "Set the voices folder in Settings > Speech."
        if not self._voices:
            return "No voices (.onnx files) in the voices folder set in Settings > Speech."
        return ""

    problem = Property(str, _get_problem, notify=voicesChanged)

    # The Preview is being made (the Speech tab's Stop).
    busy = Property(bool, lambda self: self._preview_job() is not None, notify=stateChanged)
    status = Property(str, lambda self: self._status, notify=stateChanged)
    failed = Property(bool, lambda self: self._status_failed, notify=stateChanged)
    # Changes whenever a clip is made, asked for, or fails: bind to it
    # to re-read clipUrl / clipStatus.
    clipsVersion = Property(int, lambda self: self._clips_version, notify=clipsChanged)
    modes = Property(list, lambda self: list(VOICE_MODES), constant=True)
    speedRange = Property(list, lambda self: list(SPEECH_SPEED_RANGE), constant=True)
    pitchRange = Property(list, lambda self: list(SPEECH_PITCH_RANGE), constant=True)
    silenceRange = Property(list, lambda self: list(SPEECH_SILENCE_RANGE), constant=True)

    def _set_status(self, status, failed=False):
        self._status = status
        self._status_failed = failed
        self.stateChanged.emit()

    def _jobs(self):
        return ([self._job] if self._job is not None else []) + self._queue

    def _preview_job(self):
        return next((job for job in self._jobs() if job.preview), None)

    def _bump(self):
        self._clips_version += 1
        self.clipsChanged.emit()

    # ---- For speech tracks ----

    @Slot("QVariantMap", result=str)
    def clipUrl(self, speech):
        """A made clip's file URL, or "" (not made yet)."""
        path = self._clips.get(speech_key(dict(speech)))
        return QUrl.fromLocalFile(path).toString() if path else ""

    @Slot("QVariantMap", result=str)
    def clipStatus(self, speech):
        """For a track's card: "" (made, or not asked for yet),
        "Making…", or why it can't be made."""
        key = speech_key(dict(speech))
        if key in self._clips:
            return ""
        if key in self._failed:
            return self._failed[key]
        if any(job.key == key for job in self._jobs()):
            return "Making…"
        return ""

    @Slot("QVariantMap")
    def request(self, speech):
        """A track is about to play: make its clip if it isn't made."""
        speech = normalized_speech(dict(speech))
        if not speech:
            return
        key = speech_key(speech)
        if key in self._clips or key in self._failed:
            return
        self._enqueue(key, speech).track = True
        self._bump()
        self._next()

    # ---- For the Speech tab ----

    @Slot()
    def rescan(self):
        """Look at the voices folder again (and try failed clips again)."""
        self._voices = scan_voices(self._settings.voicesFolder)
        if self._failed:
            self._failed = {}
            self._bump()
        self.voicesChanged.emit()           # tracks waiting ask again

    @Slot("QVariantMap")
    def preview(self, speech):
        speech = normalized_speech(dict(speech))
        if not speech:
            self._set_status("Type some words first.", failed=True)
            return
        self._stop_preview()
        key = speech_key(speech)
        if key in self._clips:
            self._set_status("")
            self.previewReady.emit(QUrl.fromLocalFile(self._clips[key]).toString())
            return
        if self._failed.pop(key, None) is not None:
            self._bump()
        self._enqueue(key, speech, first=True).preview = True
        self._set_status("Making the clip…")
        self._next()

    @Slot()
    def stop(self):
        """Stop the Preview (and making it, unless a track wants it too)."""
        stopping = self._preview_job() is not None
        self._stop_preview()
        if stopping:
            self._set_status("Stopped.")

    @Slot()
    def shutdown(self):
        """The app is closing: stop Piper. (The clips folder goes too.)"""
        self._queue = []
        self._kill()

    # ---- Making clips ----

    def _enqueue(self, key, speech, first=False):
        for job in self._jobs():
            if job.key == key:
                if first and job in self._queue:
                    self._queue.remove(job)
                    self._queue.insert(0, job)
                return job
        job = _Job(key, speech)
        if first:
            self._queue.insert(0, job)
        else:
            self._queue.append(job)
        return job

    def _stop_preview(self):
        self.previewStopped.emit()
        for job in list(self._queue):
            job.preview = False
            if not job.track:
                self._queue.remove(job)
        if self._job is not None and self._job.preview:
            self._job.preview = False
            if not self._job.track:
                self._kill()
                self._next()
        self.stateChanged.emit()
        self._bump()

    def _kill(self):
        process, self._process, self._job = self._process, None, None
        if process is not None:
            process.kill()
            process.waitForFinished(1000)

    def _done(self, job, path=None, error=""):
        """A job finished: keep the clip (or why it failed), tell whoever
        wanted it, and start the next."""
        if path:
            self._clips[job.key] = path
        else:
            self._failed[job.key] = error
        if job.preview:
            if path:
                self._set_status("")
                self.previewReady.emit(QUrl.fromLocalFile(path).toString())
            else:
                self._set_status(error, failed=True)
        self._bump()
        self.stateChanged.emit()
        self._next()

    def _next(self):
        if self._job is not None or not self._queue:
            return
        job = self._queue.pop(0)
        speech = job.speech

        program = find_program(self._settings.piperPath)
        model = self._voices.get(speech["voice"])
        if not program or not model:
            self._done(job, error=self._get_problem()
                       or f"The voice {speech['voice'] or '(none)'} isn't in the voices folder.")
            return

        out = os.path.join(self._temp.name, f"speech-{job.key}.wav")
        length, silence, rate = piper_settings(speech)
        command, lead = piper_command(program)

        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")      # a Python Piper reads UTF-8 words
        process.setProcessEnvironment(env)
        process.setProgram(command)
        process.setArguments(lead + [
            "--model", model,
            "--output_file", out,
            "--length_scale", str(length),
            "--sentence_silence", str(silence),
        ])

        def finished(code, _status):
            if self._process is not process:
                return
            self._process = self._job = None
            errors = bytes(process.readAllStandardError()).decode("utf-8", "replace").strip()
            if code != 0 or not os.path.isfile(out) or os.path.getsize(out) <= 44:
                if errors:
                    print("Piper:", errors, flush=True)       # to the Log window
                last = errors.splitlines()[-1] if errors else f"exit code {code}"
                self._done(job, error=f"Piper failed: {last}")
                return
            try:
                repitch_wav(out, rate)
            except Exception as exc:                          # wave.Error, OSError
                self._done(job, error=f"Couldn't read Piper's clip: {exc}")
                return
            self._done(job, path=out)

        def failed(error):
            if self._process is process and error == QProcess.FailedToStart:
                self._process = self._job = None
                self._done(job, error=f"Piper didn't start: {process.errorString()}")

        process.finished.connect(finished)
        process.errorOccurred.connect(failed)
        self._process = process
        self._job = job
        self.stateChanged.emit()
        process.start()
        process.write(piper_text(speech["text"]).encode("utf-8") + b"\n")
        process.closeWriteChannel()
