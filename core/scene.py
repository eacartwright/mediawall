"""
Scene model: the source of truth for everything on the canvas.

Pure Python with no Qt imports, so it can be saved, loaded, tested,
and eventually undone/redone independently of the UI.

Structure (see readme section 52):

    MediaSource   one per file, however many times it is used
        |
    SceneObject   a use of something on the canvas
                  - "media": a media instance. Free on the canvas when
                    parent_id is None; otherwise it is the content of
                    the container whose id is parent_id.
                  - "browser": workspace object with folder/index state
                  - "container": a viewport that can hold one media
                    instance and clips it to its shape

Coordinates:

    Top-level objects use scene coordinates. x, y is the top-left of
    the unrotated box; rotation (degrees) is about the box's center.

    A container's content uses the same convention, but in the
    container's local, unrotated coordinates (0, 0 = container's
    top-left corner). That local space is what makes pan, zoom, and
    rotation of media inside a container independent of the container.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional


OBJECT_TYPES = {"media", "browser", "container", "audio"}

# Objects with a player and per-instance playback settings.
PLAYABLE_TYPES = {"media", "audio"}

# Objects with no place on the canvas (audio tracks live in the Audio
# tab only): no geometry, no stacking, not in the Layers list.
NON_VISUAL_TYPES = {"audio"}

DEFAULT_SIZES = {
    "media": (300.0, 200.0),
    "browser": (420.0, 300.0),
    "container": (360.0, 260.0),
    "audio": (0.0, 0.0),
}

DEFAULT_MEDIA_WIDTH = 300.0

# Used until a file's real size is known (videos report their size
# only once they start loading).
FALLBACK_ASPECT = 16 / 9

CLIP_SHAPES = {"rect"}      # future: "rounded", "ellipse", "path", ...

FIT_CONTAIN = "contain"     # whole image visible inside the container
FIT_COVER = "cover"         # container completely filled, edges cropped
FIT_MODES = {FIT_CONTAIN, FIT_COVER}

# Which files a browser or browsing container steps through: every
# kind it shows, or one type. Containers show no audio.
MEDIA_FILTERS = {
    "browser": ("all", "image", "video", "audio"),
    "container": ("all", "image", "video"),
}

# Object types that always stack above the others (workspace tools).
OVERLAY_TYPES = {"browser"}

# Playback speed limits (QtMultimedia playbackRate): the outer bounds any
# saved speed is kept within. The Playback tab's slider offers a narrower
# range, set in Settings (bridge/app_settings.py; default 0.5x .. 3x).
SPEED_MIN = 0.25
SPEED_MAX = 4.0

# A-B loop points closer than this are rejected (milliseconds).
MIN_LOOP_MS = 100.0

# Uniform scaling (wheel zoom) stops at these sizes.
SCALE_MIN_SIDE = 20.0       # the shorter side
SCALE_MAX_SIDE = 20000.0    # the longer side


def new_id(prefix: str) -> str:
    # Random rather than sequential, so importing a layout into an
    # existing project can never produce colliding IDs.
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _rotate(x, y, degrees):
    r = math.radians(degrees)
    c, s = math.cos(r), math.sin(r)
    return x * c - y * s, x * s + y * c


def _bounding_box(obj):
    """Axis-aligned ((left, top), (right, bottom)) of a possibly rotated object."""
    r = math.radians(obj.rotation)
    half_w = abs(obj.width / 2 * math.cos(r)) + abs(obj.height / 2 * math.sin(r))
    half_h = abs(obj.width / 2 * math.sin(r)) + abs(obj.height / 2 * math.cos(r))
    cx, cy = obj.center
    return (cx - half_w, cy - half_h), (cx + half_w, cy + half_h)


def clamp_speed(value) -> float:
    return round(min(SPEED_MAX, max(SPEED_MIN, float(value))), 2)


def normalized_loop(loop_a, loop_b):
    """
    Loop points in order, with unset ones as -1.0. Returns (None, None)
    if both are set but too close together.
    """
    a = float(loop_a) if loop_a is not None and loop_a >= 0 else -1.0
    b = float(loop_b) if loop_b is not None and loop_b >= 0 else -1.0

    if a >= 0 and b >= 0:
        if abs(b - a) < MIN_LOOP_MS:
            return None, None
        a, b = min(a, b), max(a, b)

    return a, b


def fitted_size(box_w, box_h, aspect, mode):
    """Size of an item with the given aspect ratio fitted into a box."""
    if aspect <= 0 or box_w <= 0 or box_h <= 0:
        return box_w, box_h

    box_aspect = box_w / box_h
    wider = aspect > box_aspect

    if (mode == FIT_CONTAIN) == wider:
        return box_w, box_w / aspect
    return box_h * aspect, box_h


@dataclass
class MediaSource:
    id: str
    path: str                 # where the file is used from now
    type: str                 # "image" | "video" | "audio"
    width: int = 0            # 0 = unknown
    height: int = 0

    # The path the file was first added from. Never discarded, even if
    # the file is later found somewhere else (readme section 42).
    original_path: str = ""

    # Runtime only, not saved: True if the file can't be found.
    missing: bool = field(default=False, compare=False)

    def __post_init__(self):
        if not self.original_path:
            self.original_path = self.path

    @property
    def aspect(self) -> float:
        if self.width > 0 and self.height > 0:
            return self.width / self.height
        return 0.0


@dataclass
class SceneObject:
    id: str
    type: str                 # one of OBJECT_TYPES

    x: float = 0.0
    y: float = 0.0
    width: float = 300.0
    height: float = 200.0
    rotation: float = 0.0
    z: int = 0                # stacking among top-level objects only

    # media
    source_id: Optional[str] = None
    playing: bool = True          # animated images and video
    parent_id: Optional[str] = None   # container holding this instance
    mirrored: bool = False        # flipped horizontally (any media)

    # video (per instance)
    muted: bool = True            # canvas videos start silent
    volume: float = 1.0           # 0.0 .. 1.0
    loop: bool = True
    speed: float = 1.0            # SPEED_MIN .. SPEED_MAX
    preserve_pitch: bool = False  # off: pitch follows speed (readme 14.4)

    # A-B loop, in milliseconds; -1 = not set. Looping between them
    # happens only when both are set (loop_a < loop_b).
    loop_a: float = -1.0
    loop_b: float = -1.0

    # Runtime only, not saved: the source's size wasn't known when this
    # instance was placed, so it is resized once the size is reported.
    pending_size: bool = False

    # browser (workspace state)
    folder: str = ""
    current_index: int = -1
    include_subfolders: bool = True

    # container
    lock_content: bool = True     # resizing the container scales content
    clip_shape: str = "rect"
    fit_mode: str = FIT_COVER     # how new content is framed (Fit/Fill)

    # A browsing container: the wheel steps through the media in a
    # folder, showing each file as its content. Workspace state, like a
    # browser's: saved, but not undone.
    browse_mode: bool = False
    browse_folder: str = ""
    browse_subfolders: bool = True

    # browser and browsing container: "all" or one media type
    # (MEDIA_FILTERS). Workspace state.
    media_filter: str = "all"

    @property
    def center(self):
        return self.x + self.width / 2, self.y + self.height / 2


class Scene:

    def __init__(self):
        self.sources: dict[str, MediaSource] = {}
        self.objects: list[SceneObject] = []
        self.selected_id: Optional[str] = None

    # -------------------------------------------------
    # Sources
    # -------------------------------------------------

    def add_source(self, path, media_type, width=0, height=0) -> MediaSource:
        """Register a file. Returns the existing source if already known."""
        key = str(Path(path))

        for source in self.sources.values():
            if source.path == key:
                # Fill in dimensions if we learned them since.
                if source.width <= 0 and width > 0:
                    source.width, source.height = width, height
                return source

        source = MediaSource(new_id("src"), key, media_type, width, height)
        self.sources[source.id] = source
        return source

    def set_source_size(self, source_id, width, height) -> list:
        """
        Record a source's real size, once known (e.g. reported by the
        video player). Instances placed before it was known are resized
        to the real aspect ratio. Returns the ids of objects that changed
        (a container's id when its content changed).
        """
        source = self.sources.get(source_id)
        if source is None or width <= 0 or height <= 0:
            return []

        if source.width == width and source.height == height:
            return []

        # The known size turned sideways: a rotation correction (phone
        # videos are stored sideways with a rotation flag; the player may
        # report the stored size first, then the displayed one). Everything
        # sized from the old shape is re-sized, not just pending instances.
        rotated = (source.width, source.height) == (int(height), int(width))

        source.width, source.height = int(width), int(height)
        changed = []

        for obj in self.objects:
            if obj.source_id != source_id or not (obj.pending_size or rotated):
                continue

            was_pending = obj.pending_size
            obj.pending_size = False

            if obj.parent_id is None:
                if was_pending:
                    obj.height = obj.width / source.aspect
                else:
                    # Already placed: fit the corrected shape inside the
                    # box it had, around the same center.
                    cx, cy = obj.center
                    obj.width, obj.height = fitted_size(
                        obj.width, obj.height, source.aspect, FIT_CONTAIN)
                    obj.x, obj.y = cx - obj.width / 2, cy - obj.height / 2
                changed.append(obj.id)
            else:
                container = self._container(obj.parent_id)
                if container is not None:
                    self._frame_content(container, obj, source.aspect,
                                        container.fit_mode)
                    changed.append(container.id)

        return changed

    def refresh_missing(self) -> int:
        """Re-check every source on disk. Returns how many are missing."""
        count = 0
        for source in self.sources.values():
            source.missing = not Path(source.path).is_file()
            count += source.missing
        return count

    def relink_source(self, source_id, new_path) -> list:
        """
        Point a source at a new file (the original path is kept).

        Also relinks any other missing sources that lived in the same
        old folder, if a file with the same name exists in the new
        folder: a moved folder usually moved everything in it.

        Returns the ids of every source that was relinked.
        """
        source = self.sources.get(source_id)
        if source is None:
            return []

        old_dir = Path(source.path).parent
        new_dir = Path(new_path).parent

        source.path = str(Path(new_path))
        source.missing = not Path(source.path).is_file()
        relinked = [source_id]

        for other in self.sources.values():
            if other is source or not other.missing:
                continue
            if Path(other.path).parent != old_dir:
                continue

            candidate = new_dir / Path(other.path).name
            if candidate.is_file():
                other.path = str(candidate)
                other.missing = False
                relinked.append(other.id)

        return relinked

    def used_source_ids(self) -> set:
        return {o.source_id for o in self.objects if o.source_id}

    # -------------------------------------------------
    # Lookup
    # -------------------------------------------------

    def get(self, object_id) -> Optional[SceneObject]:
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        return None

    def index_of(self, object_id) -> int:
        for i, obj in enumerate(self.objects):
            if obj.id == object_id:
                return i
        return -1

    def top_level(self) -> list:
        """Objects placed directly on the canvas, in list order."""
        return [o for o in self.objects if o.parent_id is None]

    def content_of(self, container_id) -> Optional[SceneObject]:
        for obj in self.objects:
            if obj.parent_id == container_id:
                return obj
        return None

    def _container(self, container_id) -> Optional[SceneObject]:
        obj = self.get(container_id)
        if obj is None or obj.type != "container":
            return None
        return obj

    def container_at(self, x, y, exclude_id=None) -> Optional[SceneObject]:
        """The top-most container whose (rotated) box contains a scene point."""
        best = None

        for obj in self.top_level():
            if obj.type != "container" or obj.id == exclude_id:
                continue

            cx, cy = obj.center
            lx, ly = _rotate(x - cx, y - cy, -obj.rotation)

            if abs(lx) <= obj.width / 2 and abs(ly) <= obj.height / 2:
                if best is None or obj.z > best.z:
                    best = obj

        return best

    # -------------------------------------------------
    # Adding / removing
    # -------------------------------------------------

    def add_object(self, object_type, x, y, **fields) -> SceneObject:
        if object_type not in OBJECT_TYPES:
            raise ValueError(f"Unknown object type: {object_type}")

        width, height = DEFAULT_SIZES[object_type]

        obj = SceneObject(
            id=new_id(object_type),
            type=object_type,
            x=float(x),
            y=float(y),
            width=width,
            height=height,
            z=self._top_z() + 1,
        )

        for name, value in fields.items():
            if not hasattr(obj, name):
                raise AttributeError(f"SceneObject has no field {name!r}")
            setattr(obj, name, value)

        self.objects.append(obj)
        return obj

    def add_media(self, source_id, x, y) -> SceneObject:
        """Add a free media instance, sized to the source's aspect ratio."""
        source = self.sources[source_id]

        width = DEFAULT_MEDIA_WIDTH
        aspect = source.aspect or FALLBACK_ASPECT

        return self.add_object(
            "media", x, y,
            width=width, height=width / aspect, source_id=source_id,
            pending_size=source.aspect <= 0,
        )

    def add_audio_track(self, source_id) -> SceneObject:
        """
        Add an audio track: a player with no place on the canvas (it
        lives in the Playback tab). Tracks start audible and looping.
        """
        return self.add_object(
            "audio", 0, 0, source_id=source_id, muted=False, loop=True, z=0,
        )

    def audio_tracks(self) -> list:
        return [o for o in self.objects if o.type == "audio"]

    # ---- Video as audio (readme 14.2) ----
    #
    # Split in two so the Qt bridge can announce the row removal and the
    # row insert separately; convert_to_audio_track() does both.

    def can_convert_to_audio(self, media_id) -> bool:
        media = self.get(media_id)
        if media is None or media.type != "media":
            return False
        source = self.sources.get(media.source_id)
        return source is not None and source.type == "video"

    def audio_track_from(self, media_id) -> Optional[SceneObject]:
        """
        A new audio track (not yet in the scene) playing a video's sound
        with the same playback settings, audible. It gets a new id, so
        undoing the conversion cleanly brings the video back.
        """
        if not self.can_convert_to_audio(media_id):
            return None
        media = self.get(media_id)
        width, height = DEFAULT_SIZES["audio"]
        return replace(
            media, id=new_id("audio"), type="audio", parent_id=None,
            muted=False, x=0.0, y=0.0, width=width, height=height,
            rotation=0.0, z=0, pending_size=False,
        )

    def convert_to_audio_track(self, media_id) -> Optional[SceneObject]:
        """
        Replace a video with an audio track. A video in a container takes
        the container with it, rather than leaving it empty.
        """
        track = self.audio_track_from(media_id)
        if track is None:
            return None
        media = self.get(media_id)
        self.remove_object(media.parent_id or media_id)
        return self.insert_audio_track(track)

    def insert_audio_track(self, track) -> SceneObject:
        """Add a track made by audio_track_from() to the scene."""
        self.objects.append(track)
        return track

    def duplicate_object(self, object_id, offset=20.0) -> Optional[SceneObject]:
        """
        Duplicate a top-level object, slightly offset, on top of the stack.
        Media duplicates are new instances of the same source (no file is
        copied). A container is duplicated with its content.
        """
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None:
            return None

        copy = replace(
            obj,
            id=new_id(obj.type),
            x=obj.x + offset,
            y=obj.y + offset,
            z=self._top_z() + 1,
        )
        self.objects.append(copy)

        if obj.type == "container":
            content = self.content_of(obj.id)
            if content is not None:
                self.objects.append(replace(
                    content, id=new_id("media"), parent_id=copy.id,
                ))

        return copy

    def remove_object(self, object_id) -> bool:
        obj = self.get(object_id)
        if obj is None:
            return False

        # A container takes its content with it.
        doomed = {object_id}
        if obj.type == "container":
            content = self.content_of(object_id)
            if content is not None:
                doomed.add(content.id)

        self.objects = [o for o in self.objects if o.id not in doomed]

        if self.selected_id in doomed:
            self.selected_id = None

        self._normalize_z()
        return True

    # -------------------------------------------------
    # Editing
    # -------------------------------------------------

    def set_geometry(self, object_id, x, y, width, height, rotation) -> bool:
        obj = self.get(object_id)
        if obj is None:
            return False

        new = (float(x), float(y), float(width), float(height), float(rotation))
        old = (obj.x, obj.y, obj.width, obj.height, obj.rotation)
        if new == old:
            return False

        size_changed = (new[2], new[3]) != (obj.width, obj.height)

        if obj.type == "container" and size_changed:
            if obj.lock_content:
                self._scale_content(obj, new[2], new[3])
            else:
                self._keep_content_in_place(obj, *new)

        obj.x, obj.y, obj.width, obj.height, obj.rotation = new
        return True

    def fill_along(self, object_id, axis, canvas_width, canvas_height) -> bool:
        """
        Stretch an unrotated object along one axis ("v" = vertically,
        "h" = horizontally) to fill the free space: up to the nearest
        neighbours in its column (or row), or the canvas edges. Like
        double-clicking a window's top edge in Windows, but it stops at
        other objects, so tiled layouts stay tiled.

        Neighbours are other visual objects (not browsers, which are
        workspace tools) whose span across the axis overlaps this one's
        and that don't already overlap it. It only grows, never shrinks.
        Applied through set_geometry, so content follows the usual
        resize rules. Rotated objects are left alone.
        """
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None or obj.type in NON_VISUAL_TYPES:
            return False
        if abs(((obj.rotation + 180) % 360) - 180) > 0.01:
            return False

        vertical = axis == "v"
        # (start, end) along the axis, and across it.
        along = (obj.y, obj.y + obj.height) if vertical else (obj.x, obj.x + obj.width)
        across = (obj.x, obj.x + obj.width) if vertical else (obj.y, obj.y + obj.height)
        low, high = 0.0, float(canvas_height if vertical else canvas_width)

        for other in self._by_z():
            if other is obj or self._is_overlay(other):
                continue
            (left, top), (right, bottom) = _bounding_box(other)
            o_along = (top, bottom) if vertical else (left, right)
            o_across = (left, right) if vertical else (top, bottom)
            if o_across[1] <= across[0] + 0.5 or o_across[0] >= across[1] - 0.5:
                continue                        # not in this column / row
            if o_along[1] <= along[0] + 0.5:
                low = max(low, o_along[1])      # before it
            elif o_along[0] >= along[1] - 0.5:
                high = min(high, o_along[0])    # after it

        start = min(along[0], low)
        end = max(along[1], high)
        if (start, end) == along:
            return False

        if vertical:
            return self.set_geometry(obj.id, obj.x, start, obj.width, end - start, obj.rotation)
        return self.set_geometry(obj.id, start, obj.y, end - start, obj.height, obj.rotation)

    def scale_object(self, object_id, px, py, factor) -> bool:
        """
        Scale a top-level object uniformly by `factor` around the scene
        point (px, py), as wheel zoom does. Scaling about a point doesn't
        depend on rotation, so only the center and size change.

        A container's content scales with it whatever lock_content says,
        so the view inside the frame stays exactly the same.
        """
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None or factor <= 0:
            return False

        shorter = min(obj.width, obj.height)
        longer = max(obj.width, obj.height)
        if shorter <= 0:
            return False

        # Clamp only in the direction of change, so an object that is
        # already past a limit can still be scaled back.
        if factor < 1:
            factor = max(factor, min(1.0, SCALE_MIN_SIDE / shorter))
        else:
            factor = min(factor, max(1.0, SCALE_MAX_SIDE / longer))

        if factor == 1.0:
            return False

        cx, cy = obj.center
        obj.width *= factor
        obj.height *= factor
        obj.x = px + (cx - px) * factor - obj.width / 2
        obj.y = py + (cy - py) * factor - obj.height / 2

        content = self.content_of(obj.id) if obj.type == "container" else None
        if content is not None:
            content.x *= factor
            content.y *= factor
            content.width *= factor
            content.height *= factor

        return True

    def set_browser_state(self, object_id, folder, current_index) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.type != "browser":
            return False

        if obj.folder == folder and obj.current_index == int(current_index):
            return False

        obj.folder = folder
        obj.current_index = int(current_index)
        return True

    def set_browser_index(self, object_id, current_index) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.type != "browser":
            return False

        if obj.current_index == int(current_index):
            return False

        obj.current_index = int(current_index)
        return True

    def set_browser_subfolders(self, object_id, include) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.type != "browser":
            return False

        if obj.include_subfolders == bool(include):
            return False

        obj.include_subfolders = bool(include)
        return True

    def set_media_filter(self, object_id, media_filter) -> bool:
        obj = self.get(object_id)
        if obj is None or media_filter not in MEDIA_FILTERS.get(obj.type, ()):
            return False
        if obj.media_filter == media_filter:
            return False
        obj.media_filter = media_filter
        return True

    def set_media_option(self, object_id, name, value) -> bool:
        """
        Set a per-instance option: muted, loop, volume, speed,
        preserve_pitch, or mirrored (flipped horizontally).
        """
        obj = self.get(object_id)
        if obj is None or obj.type not in PLAYABLE_TYPES or name not in (
                "muted", "loop", "volume", "speed", "preserve_pitch", "mirrored"):
            return False

        if name == "volume":
            value = min(1.0, max(0.0, float(value)))
        elif name == "speed":
            value = clamp_speed(value)
        else:
            value = bool(value)

        if getattr(obj, name) == value:
            return False

        setattr(obj, name, value)
        return True

    def set_loop(self, object_id, loop_a, loop_b) -> bool:
        """
        Set the A-B loop points (ms; negative = not set). If both are set
        they are put in order; points closer than MIN_LOOP_MS are rejected.
        """
        obj = self.get(object_id)
        if obj is None or obj.type not in PLAYABLE_TYPES:
            return False

        a, b = normalized_loop(loop_a, loop_b)
        if a is None:
            return False

        if (obj.loop_a, obj.loop_b) == (a, b):
            return False

        obj.loop_a, obj.loop_b = a, b
        return True

    def set_playing(self, object_id, playing) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.type not in PLAYABLE_TYPES:
            return False

        if obj.playing == bool(playing):
            return False

        obj.playing = bool(playing)
        return True

    # -------------------------------------------------
    # Containers
    # -------------------------------------------------

    def _frame_content(self, container, content, aspect, mode=FIT_COVER):
        """Center content in the container at a fitted size, unrotated."""
        if aspect <= 0:
            aspect = FALLBACK_ASPECT

        w, h = fitted_size(container.width, container.height, aspect, mode)
        content.width, content.height = w, h
        content.x = (container.width - w) / 2
        content.y = (container.height - h) / 2
        content.rotation = 0.0

    def _scale_content(self, container, new_width, new_height):
        """
        Locked mode: keep the content's center at the same relative
        position and scale it by the larger of the two resize factors,
        so content that filled the container still fills it.
        """
        content = self.content_of(container.id)
        if content is None or container.width <= 0 or container.height <= 0:
            return

        sx = new_width / container.width
        sy = new_height / container.height
        s = max(sx, sy)

        cx = (content.x + content.width / 2) * sx
        cy = (content.y + content.height / 2) * sy

        content.width *= s
        content.height *= s
        content.x = cx - content.width / 2
        content.y = cy - content.height / 2

    def _keep_content_in_place(self, container, x, y, width, height, rotation):
        """
        Independent mode: when the container is resized, the content stays
        exactly where it is on the canvas and only the viewport changes.
        This is what makes dragging any corner crop, not just bottom-right.
        (Plain moves and rotations still carry the content along.)
        """
        content = self.content_of(container.id)
        if content is None:
            return

        # Content center in scene coordinates, from the old geometry.
        lx = content.x + content.width / 2 - container.width / 2
        ly = content.y + content.height / 2 - container.height / 2
        dx, dy = _rotate(lx, ly, container.rotation)
        ocx, ocy = container.center
        scx, scy = ocx + dx, ocy + dy

        # Back into the new geometry's local coordinates.
        ncx, ncy = x + width / 2, y + height / 2
        rx, ry = _rotate(scx - ncx, scy - ncy, -rotation)

        content.x = rx + width / 2 - content.width / 2
        content.y = ry + height / 2 - content.height / 2

    def add_container_with_media(self, source_id, x, y) -> SceneObject:
        """
        Add a new container holding a new instance of a source, shaped
        like the media (a video's real shape isn't known yet, so it
        starts at the fallback aspect). Returns the container.
        """
        source = self.sources[source_id]
        width = DEFAULT_MEDIA_WIDTH
        aspect = source.aspect or FALLBACK_ASPECT

        container = self.add_object("container", x, y,
                                    width=width, height=width / aspect)
        self.add_media_to_container(source_id, container.id)
        return container

    def add_media_to_container(self, source_id, container_id):
        """
        Create a new media instance inside a container, framed to fill it.
        Returns (new_instance, released) where released is the previous
        content (now a free object) or None.
        """
        container = self._container(container_id)
        if container is None:
            return None, None

        released = self.release_content(container_id)

        source = self.sources[source_id]
        content = SceneObject(
            id=new_id("media"),
            type="media",
            source_id=source_id,
            parent_id=container_id,
            pending_size=source.aspect <= 0,
        )
        self._frame_content(container, content, source.aspect, container.fit_mode)
        self.objects.append(content)
        return content, released

    def move_into_container(self, media_id, container_id):
        """
        Put an existing free media instance into a container, framed to
        fill it. The instance keeps its id and state (e.g. paused).
        Returns (moved, released): moved is True on success, released is
        the container's previous content (now free) or None.
        """
        media = self.get(media_id)
        container = self._container(container_id)

        if (media is None or container is None or media.type != "media"
                or media.parent_id is not None):
            return False, None

        released = self.release_content(container_id)

        source = self.sources.get(media.source_id)
        aspect = source.aspect if source else 0.0
        if aspect <= 0 and media.height > 0:
            aspect = media.width / media.height     # keep what we see

        media.parent_id = container_id
        media.z = 0
        self._frame_content(container, media, aspect, container.fit_mode)

        if self.selected_id == media_id:
            self.selected_id = container_id

        self._normalize_z()
        return True, released

    def release_content(self, container_id) -> Optional[SceneObject]:
        """
        Turn a container's content back into a free media object,
        placed where it currently appears on the canvas (unclipped).
        """
        container = self._container(container_id)
        content = self.content_of(container_id) if container else None
        if content is None:
            return None

        # Content center, relative to the container's center, rotated
        # into scene space.
        lx = content.x + content.width / 2 - container.width / 2
        ly = content.y + content.height / 2 - container.height / 2
        dx, dy = _rotate(lx, ly, container.rotation)
        ccx, ccy = container.center

        content.x = ccx + dx - content.width / 2
        content.y = ccy + dy - content.height / 2
        content.rotation = (container.rotation + content.rotation) % 360
        content.parent_id = None
        content.z = self._top_z() + 1
        return content

    def remove_content(self, container_id) -> bool:
        content = self.content_of(container_id)
        if content is None:
            return False
        self.objects = [o for o in self.objects if o.id != content.id]
        return True

    def set_content_geometry(self, container_id, x, y, width, height,
                             rotation) -> bool:
        content = self.content_of(container_id)
        if content is None:
            return False

        new = (float(x), float(y), max(1.0, float(width)),
               max(1.0, float(height)), float(rotation))
        old = (content.x, content.y, content.width, content.height,
               content.rotation)
        if new == old:
            return False

        (content.x, content.y, content.width, content.height,
         content.rotation) = new
        return True

    def fit_content(self, container_id, mode) -> bool:
        """
        Re-frame the content (Fit or Fill). The container remembers the
        mode, and frames new content (e.g. while browsing) the same way.
        """
        container = self._container(container_id)
        if container is None or mode not in FIT_MODES:
            return False

        mode_changed = container.fit_mode != mode
        container.fit_mode = mode

        content = self.content_of(container_id)
        if content is None:
            return mode_changed

        source = self.sources.get(content.source_id)
        before = (content.x, content.y, content.width, content.height,
                  content.rotation)
        self._frame_content(container, content,
                            source.aspect if source else 0.0, mode)
        after = (content.x, content.y, content.width, content.height,
                 content.rotation)
        return mode_changed or after != before

    # ---- Browsing containers ----

    def set_browsing(self, container_id, on, folder=None) -> bool:
        """
        Turn a container's browse mode on or off. Turning it on uses
        `folder`, or else the folder of the file it shows now; with
        neither, it stays off (returns False).
        """
        container = self._container(container_id)
        if container is None:
            return False

        if not on:
            if not container.browse_mode:
                return False
            container.browse_mode = False
            return True

        if not folder:
            content = self.content_of(container_id)
            source = self.sources.get(content.source_id) if content else None
            if source is None:
                return False
            folder = str(Path(source.path).parent)

        if container.browse_mode and container.browse_folder == folder:
            return False
        container.browse_mode = True
        container.browse_folder = folder
        return True

    def set_browse_subfolders(self, container_id, include) -> bool:
        container = self._container(container_id)
        if container is None or container.browse_subfolders == bool(include):
            return False
        container.browse_subfolders = bool(include)
        return True

    def show_file_in_container(self, container_id, source_id) -> bool:
        """
        Show another file in a container (browsing): the content keeps
        its id and playback settings (volume, mute, loop, speed), takes
        the new source, starts playing, and is framed with the
        container's Fit/Fill mode. A-B loop points belonged to the old
        file, so they're cleared. An empty container
        gets new content.
        """
        container = self._container(container_id)
        source = self.sources.get(source_id)
        if container is None or source is None:
            return False

        content = self.content_of(container_id)
        if content is None:
            new, _ = self.add_media_to_container(source_id, container_id)
            return new is not None

        if content.source_id == source_id:
            return False

        content.source_id = source_id
        content.playing = True           # every file starts playing, as in a browser
        content.loop_a = content.loop_b = -1.0
        content.pending_size = source.aspect <= 0
        self._frame_content(container, content, source.aspect, container.fit_mode)
        return True

    # ---- Wrapping a free image in a container ("Crop / Zoom Inside") ----
    #
    # Split into two steps so the Qt bridge can announce the row insert
    # and the row removal separately; wrap_in_container() does both.

    def insert_container_for(self, media_id) -> Optional[SceneObject]:
        """
        Step 1: add a container with exactly the same box, rotation, and
        stacking position as a free media object, just before it.
        """
        media = self.get(media_id)
        if media is None or media.type != "media" or media.parent_id is not None:
            return None

        container = SceneObject(
            id=new_id("container"),
            type="container",
            x=media.x,
            y=media.y,
            width=media.width,
            height=media.height,
            rotation=media.rotation,
            z=media.z,
            # Cropping means the frame edges move without the image
            # scaling, so this container starts in independent mode.
            lock_content=False,
        )
        self.objects.insert(self.index_of(media_id), container)
        return container

    def adopt_as_content(self, container_id, media_id) -> bool:
        """
        Step 2: make the media the container's content, filling it
        exactly, so nothing visibly changes.
        """
        container = self._container(container_id)
        media = self.get(media_id)
        if container is None or media is None or media.parent_id is not None:
            return False

        media.parent_id = container_id
        media.x, media.y = 0.0, 0.0
        media.width, media.height = container.width, container.height
        media.rotation = 0.0

        if self.selected_id == media_id:
            self.selected_id = container_id

        self._normalize_z()
        return True

    def wrap_in_container(self, media_id) -> Optional[SceneObject]:
        container = self.insert_container_for(media_id)
        if container is not None:
            self.adopt_as_content(container.id, media_id)
        return container

    def set_lock_content(self, container_id, locked) -> bool:
        container = self._container(container_id)
        if container is None or container.lock_content == bool(locked):
            return False
        container.lock_content = bool(locked)
        return True

    # -------------------------------------------------
    # Names (for lists such as the Layers panel)
    # -------------------------------------------------

    def source_name(self, source_id) -> str:
        source = self.sources.get(source_id)
        if source is None:
            return "(unknown)"
        # Either separator, so a path saved on another OS still works.
        return re.split(r"[\\/]", source.path)[-1] or source.path

    def display_name(self, object_id) -> str:
        obj = self.get(object_id)
        if obj is None:
            return ""

        if obj.type in PLAYABLE_TYPES:
            return self.source_name(obj.source_id)

        if obj.type == "container":
            content = self.content_of(obj.id)
            if content is None:
                return "Container (empty)"
            return "Container · " + self.source_name(content.source_id)

        if obj.type == "browser":
            parts = [p for p in re.split(r"[\\/]", obj.folder) if p]
            return "Browser · " + parts[-1] if parts else "Browser"

        return obj.type

    # -------------------------------------------------
    # Selection
    # -------------------------------------------------

    def select(self, object_id) -> bool:
        """Select an object, or pass None to clear. Does not change z."""
        if object_id is not None and self.get(object_id) is None:
            return False

        self.selected_id = object_id
        return True

    # -------------------------------------------------
    # Z-order
    #
    # Only top-level objects are stacked; z values are kept as a
    # compact, unique 1..n sequence. Container content has z = 0.
    # -------------------------------------------------

    # Stacking: two groups, ordinary objects below and overlay objects
    # (browsers) above, each ordered by z. Z-order operations move an
    # object only within its own group.

    @staticmethod
    def _is_overlay(obj):
        return obj.type in OVERLAY_TYPES

    def _by_z(self):
        """Top-level visual objects, bottom to top."""
        visual = [o for o in self.top_level() if o.type not in NON_VISUAL_TYPES]
        return sorted(visual, key=lambda o: (self._is_overlay(o), o.z))

    def layer_order(self) -> list:
        """Top-level objects, top to bottom (as a Layers list shows them)."""
        return list(reversed(self._by_z()))

    def _group(self, obj):
        return [o for o in self._by_z() if self._is_overlay(o) == self._is_overlay(obj)]

    def is_at_front(self, object_id) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None or obj.type in NON_VISUAL_TYPES:
            return True
        return self._group(obj)[-1] is obj

    def is_at_back(self, object_id) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None or obj.type in NON_VISUAL_TYPES:
            return True
        return self._group(obj)[0] is obj

    def _top_z(self):
        return max((o.z for o in self._by_z()), default=0)

    def _normalize_z(self):
        for z, obj in enumerate(self._by_z(), start=1):
            obj.z = z
        for obj in self.objects:
            if obj.parent_id is not None or obj.type in NON_VISUAL_TYPES:
                obj.z = 0

    def _z_order_ids(self):
        return [o.id for o in self._by_z()]

    def bring_to_front(self, object_id) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None or obj.type in NON_VISUAL_TYPES:
            return False
        before = self._z_order_ids()
        obj.z = self._top_z() + 1
        self._normalize_z()
        return self._z_order_ids() != before

    def send_to_back(self, object_id) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None or obj.type in NON_VISUAL_TYPES:
            return False
        before = self._z_order_ids()
        obj.z = min(o.z for o in self._by_z()) - 1
        self._normalize_z()
        return self._z_order_ids() != before

    def move_to_layer_position(self, object_id, position) -> bool:
        """
        Move an object to `position` in layer_order() (0 = top), as
        dragging it in the Layers list does. It stays within its own
        group, so a position among the other group is clamped to the
        nearest end of its own.
        """
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None or obj.type in NON_VISUAL_TYPES:
            return False

        order = self.layer_order()               # top first
        group = [o for o in order if self._is_overlay(o) == self._is_overlay(obj)]
        group_start = order.index(group[0])      # groups are contiguous

        target = min(max(position - group_start, 0), len(group) - 1)
        current = group.index(obj)
        if target == current:
            return False

        group.pop(current)
        group.insert(target, obj)

        # Reassign this group's z values, bottom to top, keeping the
        # same set of numbers so the other group is unaffected.
        zs = sorted(o.z for o in group)
        for z, o in zip(zs, reversed(group)):
            o.z = z
        self._normalize_z()
        return True

    def bring_forward(self, object_id) -> bool:
        return self._swap_z(object_id, +1)

    def send_backward(self, object_id) -> bool:
        return self._swap_z(object_id, -1)

    def _swap_z(self, object_id, step) -> bool:
        obj = self.get(object_id)
        if obj is None or obj.parent_id is not None or obj.type in NON_VISUAL_TYPES:
            return False

        order = self._group(obj)
        i = order.index(obj)
        j = i + step

        if not 0 <= j < len(order):
            return False

        order[i].z, order[j].z = order[j].z, order[i].z
        return True
