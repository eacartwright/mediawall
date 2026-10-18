"""
Speech (readme section 14.6): the Speech tab with no Piper set up, then
with a stand-in Piper (fake_piper.py): Preview, Add to Playback (a
speech track with no file: its clip is made when it's needed, once per
session), Edit… and Update Track (undoable), a Piper failure, Stop, the
tab's contents saved with the project, and clips made when a project
opens (for tracks that play) or at a track's first Play.
"""

import json
import os
import sys
import wave
from pathlib import Path

from harness import OUT, Check
from core.project import scene_from_dict, scene_to_dict
from core.scene import Scene

import bridge.speech as speech_bridge                                # noqa: E402

c = Check("speech")

FAKE = Path(__file__).resolve().parent / "fake_piper.py"
LOG = OUT / "piper-calls.jsonl"
VOICES = OUT / "voices"
os.environ["FAKE_PIPER_LOG"] = str(LOG)
speech_bridge.piper_command = lambda program: (sys.executable, [str(FAKE)])

VOICES.mkdir(parents=True, exist_ok=True)
for name in ("amy.onnx", "amy.onnx.json", "bob.onnx", "bob.onnx.json"):
    (VOICES / name).touch()
LOG.unlink(missing_ok=True)

scene = Scene()


def calls():
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines()]


def panel(expression):
    return c.item_js("speechPanel", expression)


def click(name):
    x, y, _, _ = c.center_of(name)
    c.click(x, y)


def tracks():
    return [o for o in c.scene.objects if o.type == "audio"]


def step_open():
    c.open_sidebar()


def step_tab():
    c.choose_tab("speechTab")


def step_not_set_up():
    problem = c.item_js("speechProblem", "item.text") or ""
    c.check("not set up: the Speech tab says to set Piper in Settings",
            "Set the Piper program" in problem, problem[:60])
    c.js(f"appSettings.piperPath = {json.dumps(str(FAKE))}")
    c.js(f"appSettings.voicesFolder = {json.dumps(str(VOICES))}")
    c.js("settingsDialog.openSpeech()")


def step_settings():
    status = c.item_js("speechSetupStatus", "item.text")
    c.check("Settings > Speech finds the voices", status == "2 voices found.", str(status))
    c.grab("settings-speech.png")
    c.js("settingsDialog.close()")
    c.check("set up: the Speech tab lists the voices",
            c.js("speechEngine.voices") == ["amy", "bob"] and c.js("speechEngine.ready"))
    c.item_js("speechText", "item.text = 'Hello there\\nSecond line'")
    c.item_js("speechVoice", "item.currentIndex = 1")
    panel("item.pitchSlider.value = 2")
    click("speechPreview")


def step_preview():
    log = calls()
    c.check("Preview runs Piper once with the voice, words, and length for the pitch",
            len(log) == 1 and log[0]["model"].endswith("bob.onnx")
            and log[0]["text"] == "Hello there. Second line."
            and log[0]["length_scale"] == 2.0 and log[0]["sentence_silence"] == 1.0, str(log))
    with wave.open(log[0]["out"], "rb") as w:
        rate = w.getframerate()
    c.check("...and the clip's pitch is raised (sample rate doubled)", rate == 44100, str(rate))
    c.check("...and it plays", panel("item.previewing") is True)
    draft = c.scene.speech_draft
    c.check("what's in the tab is kept for saving with the project",
            draft.get("text") == "Hello there\nSecond line" and draft.get("voice") == "bob"
            and draft.get("pitch") == 2.0, str(draft))
    c.grab("speech-tab.png")
    click("speechAdd")


def track_view(tid, expression):
    return c.js(f"scene.viewFor('{tid}') ? scene.viewFor('{tid}').{expression} : null")


def step_added():
    t = tracks()
    c.check("Add to Playback adds a speech track with no file, that remembers its words",
            len(t) == 1 and t[0].source_id is None
            and t[0].speech.get("text") == "Hello there\nSecond line"
            and t[0].speech.get("voice") == "bob" and t[0].speech.get("pitch") == 2.0, str(t))
    c.check("...and loops, like other tracks", t and t[0].loop)
    c.track = t[0].id if t else ""
    c.check("...and plays the previewed clip (Piper not run again)",
            len(calls()) == 1 and track_view(c.track, "player.playbackState") == 1
            and calls()[0]["out"].replace("\\", "/") in (track_view(c.track, "url") or ""),
            f"{len(calls())} calls, {track_view(c.track, 'url')}")
    c.check("...and the Preview stops, so only the track plays", panel("item.previewing") is False)
    c.item_js("speechText", "item.text = ''")
    c.choose_tab("playbackTab")


def step_edit():
    click("editSpeechButton")
    c.check("Edit… on its Playback card brings the words back to the Speech tab",
            c.item_js("speechText", "item.text") == "Hello there\nSecond line"
            and panel("item.editingId") == c.track and panel("item.pitchSlider.value") == 2)
    c.first_url = track_view(c.track, "url")
    c.item_js("speechText", "item.text = 'Changed words'")
    click("speechUpdate")


def step_updated():
    t = c.scene.get(c.track)
    c.check("Update Track changes the track, and its new clip is made and played",
            len(calls()) == 2 and calls()[1]["text"] == "Changed words."
            and t.speech["text"] == "Changed words" and t.source_id is None
            and track_view(c.track, "url") != c.first_url
            and track_view(c.track, "player.playbackState") == 1, str(calls()[-1:]))
    c.sm.undo()
    t = c.scene.get(c.track)
    c.check("...undoably, and undo uses the earlier clip (not made again)",
            t.speech["text"] == "Hello there\nSecond line" and len(calls()) == 2
            and track_view(c.track, "url") == c.first_url, str(track_view(c.track, "url")))
    c.item_js("speechText", "item.text = 'FAIL please'")
    click("speechPreview")


def step_failed():
    c.check("a Piper error shows in the tab",
            c.js("speechEngine.failed") is True
            and "voice couldn't be loaded" in c.js("speechEngine.status"), c.js("speechEngine.status"))
    c.item_js("speechText", "item.text = 'SLOW words'")
    click("speechPreview")


def step_slow():
    c.check("while Piper works, the tab is busy", c.js("speechEngine.busy") is True)
    click("speechStop")
    c.check("Stop stops it", c.js("speechEngine.busy") is False
            and c.js("speechEngine.status") == "Stopped.")
    # Open the saved project again: the tab shows what was in it.
    loaded, _ = scene_from_dict(scene_to_dict(c.scene))
    c.item_js("speechText", "item.text = ''")
    c.sm.setScene(loaded)
    c.check("opening a project brings back what was in the Speech tab",
            c.item_js("speechText", "item.text") == "SLOW words"
            and panel("item.pitchSlider.value") == 2, c.item_js("speechText", "item.text"))
    c.check("...and undo never changes it", c.scene.speech_draft.get("text") == "SLOW words")
    # A project with speech tracks never made this session: one playing,
    # one paused, one whose voice isn't in the folder.
    c.calls_before = len(calls())
    scene2 = Scene()
    c.new_play = scene2.add_speech_track({"text": "Brand new line", "voice": "amy"}).id
    paused = scene2.add_speech_track({"text": "Paused line", "voice": "amy"})
    paused.playing = False
    c.paused = paused.id
    scene2.add_speech_track({"text": "Nobody speaks", "voice": "zed"})
    c.sm.setScene(scene_from_dict(scene_to_dict(scene2))[0])
    c.choose_tab("playbackTab")


def step_reloaded():
    texts = [call["text"] for call in calls()[c.calls_before:]]
    c.check("opening a project makes the clips of the tracks that play (not the paused one)",
            texts == ["Brand new line."] and track_view(c.new_play, "player.playbackState") == 1,
            str(texts))
    status = c.item_js("speechTrackStatus", "item.text") or ""
    c.check("a track whose voice is missing says so on its card",
            "zed" in status and "isn't in the voices folder" in status, status)
    c.sm.setPlaying(c.paused, True)


def step_first_play():
    texts = [call["text"] for call in calls()[c.calls_before:]]
    c.check("a paused track's clip is made at its first Play",
            texts == ["Brand new line.", "Paused line."]
            and track_view(c.paused, "player.playbackState") == 1, str(texts))
    c.finish()


c.run(scene, [(1500, step_open), (400, step_tab), (500, step_not_set_up), (600, step_settings),
              (1500, step_preview), (2000, step_added), (600, step_edit), (2500, step_updated),
              (2500, step_failed), (1200, step_slow), (2500, step_reloaded),
              (2500, step_first_play)])
