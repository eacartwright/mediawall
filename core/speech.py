"""
Speech: text to speech with Piper (readme section 14.6), the parts that
need no Qt. Piper is a separate program the user installs, with voices
they download (a voice is a .onnx file beside its .onnx.json); the paths
are app settings. bridge/speech.py runs it.

A speech track is an audio track with no file: its `speech` dict (the
words, the voice, and the settings) is its source. Its clip is made when
it's needed (when the project opens, or at its first Play) into a
temporary folder that is deleted when Mediawall closes, so no clips pile
up on disk. Clips are found again by speech_key(), so identical tracks
share one, and undo switches back without making it again.

Pitch and speed: Piper only has a speed (length_scale). Pitch is changed
afterwards by rewriting the WAV's sample rate, which also changes its
speed, so Piper is asked for a length that cancels that out:
length_scale = pitch / speed. A lower pitch also lowers the highest
frequencies, which is what the original "deep" low-pass did.
"""

from __future__ import annotations

import hashlib
import json
import os
import wave


# Voice modes: a starting (pitch, speed), multiplied by the sliders.
VOICE_MODES = {
    "Normal":    (1.0, 1.0),
    "Deep":      (0.75, 1.0),
    "Very Deep": (0.55, 0.95),
    "Bright":    (1.25, 1.05),
    "Chipmunk":  (1.6, 1.1),
    "Monster":   (0.45, 0.9),
    "Whisper":   (0.85, 0.95),
}

# The Speech tab's sliders, and the sentence pause (seconds).
SPEECH_SPEED_RANGE = (0.5, 2.0)
SPEECH_PITCH_RANGE = (0.5, 2.0)
SPEECH_SILENCE_RANGE = (0.0, 3.0)

# Limits for mode x slider.
_PITCH_LIMITS = (0.3, 2.5)
_SPEED_LIMITS = (0.25, 4.0)

SPEECH_DEFAULTS = {
    "text": "",
    "voice": "",          # the voice's name: its file name without .onnx
    "mode": "Normal",
    "speed": 1.0,
    "pitch": 1.0,
    "silence": 0.5,       # pause between sentences, in seconds
}


def _clamp(value, limits):
    return min(limits[1], max(limits[0], value))


def normalized_speech(raw) -> dict:
    """
    A complete, valid speech dict from any input, or {} when there are
    no words (not a speech track).
    """
    if not isinstance(raw, dict):
        return {}
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        return {}

    speech = dict(SPEECH_DEFAULTS, text=text)
    if isinstance(raw.get("voice"), str):
        speech["voice"] = raw["voice"]
    if raw.get("mode") in VOICE_MODES:
        speech["mode"] = raw["mode"]
    for key, limits in (("speed", SPEECH_SPEED_RANGE), ("pitch", SPEECH_PITCH_RANGE),
                        ("silence", SPEECH_SILENCE_RANGE)):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            speech[key] = round(_clamp(float(value), limits), 2)
    return speech


def piper_text(text: str) -> str:
    """
    The words as one line for Piper (some versions write only the last
    line of their input to the file). A line that doesn't end a sentence
    gets a full stop, so lines stay separate sentences.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(line if line[-1] in ".!?,;:" else line + "." for line in lines)


def piper_settings(speech: dict):
    """
    (length_scale, sentence_silence, rate_factor) for a speech dict:
    what to ask Piper for, and the sample-rate factor that then sets the
    pitch (repitch_wav).
    """
    mode_pitch, mode_speed = VOICE_MODES.get(speech["mode"], (1.0, 1.0))
    pitch = _clamp(mode_pitch * speech["pitch"], _PITCH_LIMITS)
    speed = _clamp(mode_speed * speech["speed"], _SPEED_LIMITS)
    # The rate change divides every length by `pitch`, the pauses too.
    return round(pitch / speed, 4), round(speech["silence"] * pitch, 3), pitch


def repitch_wav(path, factor):
    """Change a WAV's pitch (and speed) by `factor`, in place."""
    if abs(factor - 1.0) < 0.005:
        return
    with wave.open(str(path), "rb") as src:
        params = src.getparams()
        frames = src.readframes(params.nframes)
    with wave.open(str(path), "wb") as dst:
        dst.setparams(params._replace(framerate=max(1000, round(params.framerate * factor))))
        dst.writeframes(frames)


def scan_voices(folder) -> dict:
    """{voice name: model path} for every .onnx file in a folder (and its
    subfolders), by name. The first of two with the same name wins."""
    voices = {}
    if not folder or not os.path.isdir(folder):
        return voices
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for name in sorted(files):
            if name.lower().endswith(".onnx"):
                voices.setdefault(name[:-5], os.path.join(root, name))
    return dict(sorted(voices.items(), key=lambda item: item[0].lower()))


def speech_key(speech: dict) -> str:
    """Names a clip: the same for the same words, voice, and settings."""
    data = json.dumps(normalized_speech(speech), sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(data.encode("utf-8")).hexdigest()[:16]


def speech_title(speech: dict) -> str:
    """A speech track's name: its first words."""
    words = " ".join(speech.get("text", "").split())
    return words if len(words) <= 40 else words[:39].rstrip() + "…"
