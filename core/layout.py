"""
Layouts: a wall's arrangement of containers, saved for reuse
(readme Phase 5 / section 17).

Pure Python, no Qt.

A layout file (<name>.mediawall.layout) holds only the containers: their
position, size, rotation, stacking, and settings (Fit/Fill, lock,
browse mode). Their content, free media, browsers, and audio tracks are
left out, and a browsing container's folder is cleared (it belonged to
the old media). Saving a layout never changes the wall it came from.

A layout can start a new wall, or have its containers added to the
current one.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from core.project import (
    COMMON_FIELDS, FORMAT, TYPE_FIELDS, ProjectError, scene_from_dict,
    write_json_atomic,
)
from core.scene import Scene, new_id


LAYOUT_FORMAT = "mediawall-layout"
LAYOUT_VERSION = 1
LAYOUT_EXTENSION = ".mediawall.layout"


def with_layout_extension(path) -> str:
    """
    A chosen file name ending in exactly one ".mediawall.layout".
    Save dialogs may add the extension again (Windows treats only
    ".layout" as the extension, so it appends the filter's full one),
    or the user may type part of it; extra endings are removed first.
    """
    path = str(path)
    endings = (LAYOUT_EXTENSION, ".layout", ".mediawall")
    trimmed = True
    while trimmed:
        trimmed = False
        for ending in endings:
            if path.lower().endswith(ending) and len(path) > len(ending):
                path = path[:-len(ending)]
                trimmed = True
    return path + LAYOUT_EXTENSION


def layout_to_dict(scene: Scene) -> dict:
    containers = [o for o in scene._by_z() if o.type == "container"]
    objects = []
    for obj in containers:
        fields = COMMON_FIELDS + TYPE_FIELDS["container"]
        entry = {name: getattr(obj, name) for name in fields}
        entry["browse_folder"] = ""
        objects.append(entry)
    return {
        "format": LAYOUT_FORMAT,
        "version": LAYOUT_VERSION,
        "objects": objects,
    }


def count_layout_containers(scene: Scene) -> int:
    return sum(1 for o in scene.top_level() if o.type == "container")


def save_layout(scene: Scene, path) -> None:
    write_json_atomic(path, layout_to_dict(scene))


def layout_from_dict(data):
    """Return (scene, warnings): a scene holding only the layout's containers."""
    if not isinstance(data, dict) or data.get("format") != LAYOUT_FORMAT:
        if isinstance(data, dict) and data.get("format") == FORMAT:
            raise ProjectError("This is a MediaWall project, not a layout. "
                               "Use Open to open it.")
        raise ProjectError("This file is not a MediaWall layout.")

    version = data.get("version")
    if not isinstance(version, int) or version > LAYOUT_VERSION:
        raise ProjectError(
            f"This layout was saved by a newer version of MediaWall "
            f"(format version {version!r})."
        )

    raw = data.get("objects", [])
    if not isinstance(raw, list):
        raw = []
    containers = [o for o in raw if isinstance(o, dict) and o.get("type") == "container"]
    skipped = len(raw) - len(containers)

    scene, warnings = scene_from_dict({
        "format": FORMAT, "version": 1, "media_sources": {}, "objects": containers,
    })
    if skipped:
        warnings.append(f"Ignored {skipped} item(s) that aren't containers.")
    return scene, warnings


def load_layout(path):
    """Return (scene, warnings). Raises ProjectError on unreadable files."""
    try:
        with open(Path(path), encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise ProjectError(f"Couldn't open the file: {exc.strerror or exc}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ProjectError("The file is damaged or not a MediaWall layout.")
    return layout_from_dict(data)


def add_layout_to_scene(scene: Scene, layout: Scene) -> list:
    """
    Add a layout's containers to a wall, with new ids (so the same layout
    can be added twice), stacked above the wall's ordinary objects in the
    layout's own order. Returns the new containers.
    """
    added = []
    for obj in layout._by_z():                      # bottom to top
        copy = replace(obj, id=new_id("container"), z=scene._top_z() + 1)
        scene.objects.append(copy)
        added.append(copy)
    scene._normalize_z()
    return added
