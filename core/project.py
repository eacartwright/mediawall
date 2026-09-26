"""
Project save/load: Scene <-> JSON file.

Pure Python, no Qt.

Design rules (readme sections 16, 42, 45, 46):

- Media files are stored as paths, never as bytes.
- The original path of every file is kept forever.
- A path relative to the project file is also stored, so a project
  and its media can be moved together (or opened on another machine
  with the same folder layout) and still be found.
- Loading is tolerant: a missing file, an unknown object type, or a
  bad value produces a warning and a recoverable state, never a
  failed load. Only an unreadable or non-project file fails.
- Saving is atomic: the file is written to a temporary name and then
  swapped in, so a crash mid-save can't destroy the previous version.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from core.scene import (
    CLIP_SHAPES, OBJECT_TYPES, MediaSource, Scene, SceneObject,
    clamp_speed, new_id, normalized_loop,
)


FORMAT = "mediawall-project"
VERSION = 1
FILE_EXTENSION = ".mediawall"


COMMON_FIELDS = ["id", "type", "x", "y", "width", "height", "rotation", "z"]

TYPE_FIELDS = {
    "media": ["source_id", "playing", "parent_id", "muted", "volume", "loop",
              "speed", "preserve_pitch", "loop_a", "loop_b"],
    "browser": ["folder", "current_index", "include_subfolders"],
    "container": ["lock_content", "clip_shape"],
}


class ProjectError(Exception):
    """The file couldn't be read as a project at all."""


# -------------------------------------------------
# Saving
# -------------------------------------------------

def _relative_path(path, project_dir):
    if project_dir is None:
        return None
    try:
        return Path(os.path.relpath(path, project_dir)).as_posix()
    except ValueError:
        # Windows: file and project are on different drives.
        return None


def scene_to_dict(scene: Scene, project_path=None) -> dict:
    project_dir = Path(project_path).parent if project_path else None

    # Only save sources that something still uses.
    used = scene.used_source_ids()

    sources = {}
    for source in scene.sources.values():
        if source.id not in used:
            continue

        entry = {
            "path": source.path,
            "original_path": source.original_path,
            "type": source.type,
            "width": source.width,
            "height": source.height,
        }

        rel = _relative_path(source.path, project_dir)
        if rel is not None:
            entry["relative_path"] = rel

        sources[source.id] = entry

    objects = []
    # Top-level objects in stacking order, each container's content
    # right after it, so the file reads naturally.
    for obj in scene._by_z():
        for item in [obj, scene.content_of(obj.id)]:
            if item is None:
                continue
            fields = COMMON_FIELDS + TYPE_FIELDS.get(item.type, [])
            objects.append({name: getattr(item, name) for name in fields})

    return {
        "format": FORMAT,
        "version": VERSION,
        "media_sources": sources,
        "objects": objects,
    }


def save_project(scene: Scene, path) -> None:
    path = Path(path)
    data = scene_to_dict(scene, path)

    # Write to a temp file in the same folder, then replace atomically.
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# -------------------------------------------------
# Loading
# -------------------------------------------------

def _coerce(value, default):
    """Convert value to the type of default, or raise ValueError."""
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        raise ValueError("expected true/false")
    if isinstance(default, int):
        if isinstance(value, bool):
            raise ValueError("expected a number")
        return int(value)
    if isinstance(default, float):
        if isinstance(value, bool):
            raise ValueError("expected a number")
        return float(value)
    if default is None and value is None:
        return None             # optional reference left empty
    if isinstance(default, str) or default is None:
        if not isinstance(value, str):
            raise ValueError("expected text")
        return value
    return value


def _resolve_source_path(entry, project_dir):
    """
    Find where a source's file is now. Tries the saved path first,
    then the path relative to the project file.
    """
    path = entry.get("path", "")
    if path and Path(path).is_file():
        return path

    rel = entry.get("relative_path")
    if rel and project_dir is not None:
        candidate = (project_dir / rel).resolve()
        if candidate.is_file():
            return str(candidate)

    return path


def scene_from_dict(data, project_path=None):
    """Return (scene, warnings). Raises ProjectError if data isn't a project."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProjectError("This file is not a Media Wall project.")

    version = data.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise ProjectError(
            f"This project was saved by a newer version of Media Wall "
            f"(format version {version!r})."
        )

    project_dir = Path(project_path).parent if project_path else None
    warnings = []
    scene = Scene()

    # ---- Sources ----
    raw_sources = data.get("media_sources", {})
    if not isinstance(raw_sources, dict):
        raw_sources = {}
        warnings.append("Media source list was unreadable and was skipped.")

    for source_id, entry in raw_sources.items():
        if not isinstance(entry, dict) or not entry.get("path"):
            warnings.append(f"Skipped an unreadable media source ({source_id}).")
            continue

        try:
            width = int(entry.get("width", 0) or 0)
            height = int(entry.get("height", 0) or 0)
        except (TypeError, ValueError):
            width = height = 0

        scene.sources[source_id] = MediaSource(
            id=source_id,
            path=_resolve_source_path(entry, project_dir),
            type=str(entry.get("type", "image")),
            width=width,
            height=height,
            original_path=str(entry.get("original_path") or entry["path"]),
        )

    # ---- Objects ----
    raw_objects = data.get("objects", [])
    if not isinstance(raw_objects, list):
        raw_objects = []
        warnings.append("Object list was unreadable and was skipped.")

    seen_ids = set()

    for raw in raw_objects:
        if not isinstance(raw, dict):
            warnings.append("Skipped an unreadable object.")
            continue

        object_type = raw.get("type")
        if object_type not in OBJECT_TYPES:
            warnings.append(f"Skipped an object of unknown type {object_type!r}.")
            continue

        object_id = raw.get("id")
        if not isinstance(object_id, str) or object_id in seen_ids:
            object_id = new_id(object_type)
        seen_ids.add(object_id)

        obj = SceneObject(id=object_id, type=object_type)

        for name in COMMON_FIELDS[2:] + TYPE_FIELDS[object_type]:
            if name not in raw:
                continue
            try:
                setattr(obj, name, _coerce(raw[name], getattr(obj, name)))
            except (TypeError, ValueError) as exc:
                warnings.append(f"Ignored bad value for {name!r} ({exc}).")

        if object_type == "media" and obj.source_id not in scene.sources:
            warnings.append("Skipped a media object whose source is unknown.")
            continue

        if object_type == "media":
            obj.volume = min(1.0, max(0.0, obj.volume))
            obj.speed = clamp_speed(obj.speed)
            obj.loop_a, obj.loop_b = normalized_loop(obj.loop_a, obj.loop_b)
            if obj.loop_a is None:
                warnings.append("Ignored an A-B loop with points too close together.")
                obj.loop_a = obj.loop_b = -1.0

        if object_type == "container" and obj.clip_shape not in CLIP_SHAPES:
            warnings.append(
                f"Unknown container shape {obj.clip_shape!r}; using rectangle."
            )
            obj.clip_shape = "rect"

        scene.objects.append(obj)

    _check_containment(scene, warnings)

    scene._normalize_z()
    scene.refresh_missing()

    return scene, warnings


def _check_containment(scene, warnings):
    """
    Every contained media instance must point at a real container, and
    each container holds at most one. Anything else becomes a free
    object rather than being dropped.
    """
    containers = {o.id for o in scene.objects if o.type == "container"}
    filled = set()

    for obj in scene.objects:
        if obj.parent_id is None:
            continue

        if obj.type != "media" or obj.parent_id not in containers:
            warnings.append("A contained item had no valid container; "
                            "it was placed on the canvas instead.")
            obj.parent_id = None
            obj.z = scene._top_z() + 1
        elif obj.parent_id in filled:
            warnings.append("A container held more than one item; "
                            "the extra was placed on the canvas.")
            obj.parent_id = None
            obj.z = scene._top_z() + 1
        else:
            filled.add(obj.parent_id)


def load_project(path):
    """Return (scene, warnings). Raises ProjectError on unreadable files."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise ProjectError(f"Couldn't open the file: {exc.strerror or exc}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ProjectError("The file is damaged or not a Media Wall project.")

    return scene_from_dict(data, path)
