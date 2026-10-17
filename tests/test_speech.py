"""
Tests for Speech (core/speech.py) and speech tracks. No Qt required.

Run from the project folder:  python -m unittest
"""

import os
import tempfile
import unittest
import wave
from pathlib import Path

from core.history import snapshot
from core.project import scene_from_dict, scene_to_dict
from core.scene import Scene
from core.speech import (
    SPEECH_DEFAULTS, normalized_speech, piper_settings, piper_text,
    repitch_wav, scan_voices, speech_key, speech_title,
)


class NormalizedSpeechTests(unittest.TestCase):

    def test_no_words_is_not_speech(self):
        self.assertEqual(normalized_speech(None), {})
        self.assertEqual(normalized_speech({"text": "   "}), {})
        self.assertEqual(normalized_speech({"voice": "amy"}), {})

    def test_fills_defaults_and_fixes_bad_values(self):
        speech = normalized_speech({"text": "Hi", "mode": "Nope", "speed": 9,
                                    "pitch": True, "silence": -1, "extra": 1})
        self.assertEqual(speech, dict(SPEECH_DEFAULTS, text="Hi", speed=2.0, silence=0.0))


class PiperTests(unittest.TestCase):

    def test_lines_become_sentences(self):
        self.assertEqual(piper_text("Hello there\n\nHow are you?\n"),
                         "Hello there. How are you?")

    def test_pitch_is_cancelled_out_in_the_length(self):
        speech = normalized_speech({"text": "x", "pitch": 2.0, "speed": 1.0, "silence": 0.5})
        length, silence, rate = piper_settings(speech)
        self.assertEqual((length, silence, rate), (2.0, 1.0, 2.0))

    def test_modes_multiply_the_sliders(self):
        speech = normalized_speech({"text": "x", "mode": "Deep", "speed": 2.0})
        length, _, rate = piper_settings(speech)
        self.assertEqual(rate, 0.75)
        self.assertAlmostEqual(length, 0.75 / 2.0)

    def test_repitch_changes_the_rate_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.wav")
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)
                w.writeframes(b"\x01\x00" * 1000)
            repitch_wav(path, 0.5)
            with wave.open(path, "rb") as r:
                self.assertEqual((r.getframerate(), r.getnframes()), (11025, 1000))


class FilesTests(unittest.TestCase):

    def test_scan_voices(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "en", "us").mkdir(parents=True)
            for name in ("en/us/amy.onnx", "en/us/amy.onnx.json", "zed.onnx", "notes.txt"):
                Path(folder, name).touch()
            voices = scan_voices(folder)
            self.assertEqual(list(voices), ["amy", "zed"])
            self.assertTrue(voices["amy"].endswith("amy.onnx"))
        self.assertEqual(scan_voices(""), {})

    def test_speech_key(self):
        a = speech_key({"text": "Hi", "voice": "amy"})
        self.assertEqual(a, speech_key({"text": "Hi", "voice": "amy", "mode": "Normal"}))
        self.assertNotEqual(a, speech_key({"text": "Hi", "voice": "amy", "pitch": 1.5}))

    def test_speech_title(self):
        self.assertEqual(speech_title({"text": "Hello\n  there"}), "Hello there")
        self.assertEqual(len(speech_title({"text": "word " * 20})), 40)


class SpeechTrackTests(unittest.TestCase):

    def setUp(self):
        self.scene = Scene()

    def test_a_speech_track_has_no_file(self):
        track = self.scene.add_speech_track({"text": "Hello", "voice": "amy"})
        self.assertIsNone(track.source_id)
        self.assertTrue(track.loop)
        self.assertEqual(track.speech["voice"], "amy")
        self.assertEqual(self.scene.display_name(track.id), "Hello")
        self.assertIsNone(self.scene.add_speech_track({"text": " "}))
        plain = self.scene.add_audio_track(self.scene.add_source("/m/a.wav", "audio").id)
        self.assertEqual(plain.speech, {})

    def test_changed(self):
        track = self.scene.add_speech_track({"text": "Hello"})
        copy = self.scene.duplicate_object(track.id)
        track.playing = False
        self.assertTrue(self.scene.set_track_speech(track.id, {"text": "Hello again"}))
        self.assertEqual((track.speech["text"], track.playing), ("Hello again", True))
        self.assertEqual(copy.speech["text"], "Hello")
        self.assertFalse(self.scene.set_track_speech(track.id, {"text": ""}))

    def test_saved_and_loaded(self):
        track = self.scene.add_speech_track({"text": "Hi", "mode": "Deep"})
        data = scene_to_dict(self.scene)
        self.assertEqual(data["media_sources"], {})
        loaded, warnings = scene_from_dict(data)
        self.assertEqual(loaded.get(track.id).speech, track.speech)
        self.assertEqual(warnings, [])
        # Saved with a file (before clips were temporary): the file is dropped.
        data["objects"][0]["source_id"] = "src_old"
        data["media_sources"]["src_old"] = {"path": "/s/hi.wav", "type": "audio"}
        loaded, _ = scene_from_dict(data)
        self.assertIsNone(loaded.get(track.id).source_id)
        self.assertEqual(scene_to_dict(loaded)["media_sources"], {})    # gone at the next save
        # No speech and no file: skipped.
        data["objects"][0]["speech"] = "nonsense"
        data["media_sources"] = {}
        loaded, _ = scene_from_dict(data)
        self.assertIsNone(loaded.get(track.id))

    def test_draft_is_saved_but_not_undone(self):
        self.assertFalse(self.scene.set_speech_draft({"text": ""}))
        self.assertTrue(self.scene.set_speech_draft({"text": "Draft", "mode": "Monster"}))
        self.assertFalse(self.scene.set_speech_draft({"text": "Draft", "mode": "Monster"}))
        loaded, _ = scene_from_dict(scene_to_dict(self.scene))
        self.assertEqual(loaded.speech_draft, self.scene.speech_draft)
        self.assertEqual(snapshot(self.scene).speech_draft, {})     # not in undo steps
        self.scene.set_speech_draft({})
        self.assertNotIn("speech_draft", scene_to_dict(self.scene))


if __name__ == "__main__":
    unittest.main()
