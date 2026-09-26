"""
Undo history kept between sessions, in a file next to the project:
<project file>.history (e.g. japan.mediawall.history).

Pure Python, no Qt.

- The file holds the most recent undo (and redo) steps, capped at
  MAX_SAVED_STEPS each. Every step is a whole-scene snapshot, stored in
  the same form as a project file.
- A history only makes sense for the project exactly as it was saved,
  so the file records the saved project's fingerprint. If the project
  doesn't match when it is opened (edited elsewhere, or saved without
  its history), the history is ignored.
- It is separate from the project on purpose: the project file stays
  small and readable, and a lost or damaged history can't affect it.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.history import History
from core.project import scene_from_dict, scene_to_dict, write_json_atomic


FORMAT = "mediawall-history"
VERSION = 1
MAX_SAVED_STEPS = 50


def history_path(project_path) -> Path:
    project_path = Path(project_path)
    return project_path.with_name(project_path.name + ".history")


def save_history(project_path, history: History, project_fingerprint) -> None:
    """
    Write the history next to the project. With nothing to undo or redo,
    a leftover history file is removed instead.
    """
    path = history_path(project_path)
    undo, redo = history.steps()
    undo, redo = undo[-MAX_SAVED_STEPS:], redo[-MAX_SAVED_STEPS:]

    if not undo and not redo:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return

    write_json_atomic(path, {
        "format": FORMAT,
        "version": VERSION,
        "project_fingerprint": project_fingerprint,
        "undo": [scene_to_dict(s) for s in undo],
        "redo": [scene_to_dict(s) for s in redo],
    })


def load_history(project_path, project_fingerprint):
    """
    Return (history, note). history is None when there is no usable
    history file; note says why (for the log), or is "" if none exists.
    """
    path = history_path(project_path)
    if not path.exists():
        return None, ""

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None, f"Undo history couldn't be read ({path.name}); starting fresh."

    if (not isinstance(data, dict) or data.get("format") != FORMAT
            or not isinstance(data.get("version"), int)
            or data["version"] > VERSION):
        return None, f"Undo history isn't in a known format ({path.name}); starting fresh."

    if project_fingerprint is None or data.get("project_fingerprint") != project_fingerprint:
        return None, ("Undo history doesn't match this project (it was changed "
                      "since the history was saved); starting fresh.")

    try:
        undo = [scene_from_dict(d)[0] for d in data.get("undo", [])]
        redo = [scene_from_dict(d)[0] for d in data.get("redo", [])]
    except Exception:                      # any damaged step: ignore it all
        return None, f"Undo history is damaged ({path.name}); starting fresh."

    return History.from_steps(undo, redo), ""
