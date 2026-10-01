"""
Qt bridge: exposes core.scene.Scene to QML as a list model.

QML never owns object state. It renders rows from this model,
and sends final values back through the slots below when an
interaction (drag, resize, rotate, pan, zoom) finishes.

Rows are the top-level objects only. A container's content is not
a row of its own; it is exposed through the container row's
content* roles, and edited through the container's id.
"""

import copy
import time
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QObject,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QImageIOHandler, QImageReader
from PySide6.QtWidgets import QFileDialog, QMessageBox

from bridge.audio_model import AudioModel
from core.history import History, snapshot
from core.layout import add_layout_to_scene
from core.media_browser import (
    AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, is_animatable,
)
from core.scene import FIT_CONTAIN, FIT_COVER, Scene


# Browser fields are workspace state: saved with the project, but not
# part of undo (undoing a move shouldn't also rewind your browsing).
BROWSER_FIELDS = ("folder", "current_index", "include_subfolders", "media_filter")

# The same for browsing containers: their browse settings, and while
# browsing, the content itself (which file, and how it's framed) and
# the Fit/Fill mode it's framed with.
CONTAINER_BROWSE_FIELDS = ("browse_mode", "browse_folder", "browse_subfolders",
                           "media_filter")


def _media_file_filter():
    patterns = " ".join(
        "*" + ext for ext in
        sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS)
    )
    return f"Media Files ({patterns});;All Files (*)"


# Roles describing the row's own object.
OBJECT_ROLE_NAMES = [
    "objectId",
    "objectType",
    "posX",
    "posY",
    "objWidth",
    "objHeight",
    "objRotation",
    "objZ",
    "objPlaying",
    "objMuted",
    "objVolume",
    "objLoop",
    "objSpeed",
    "objPreservePitch",
    "objLoopA",
    "objLoopB",
    "folder",
    "currentIndex",
    "includeSubfolders",
    "lockContent",
    "clipShape",
    "fitMode",
    "browseMode",
    "browseFolder",
    "browseSubfolders",
    "mediaFilter",
]

# Roles describing a media source. Used as "source*" for a media row,
# and as "contentSource*" (via CONTENT_ROLE_NAMES) for a container's content.
SOURCE_FIELDS = ["Id", "Type", "Path", "Url", "Width", "Height", "Animatable",
                 "Missing", "Name"]

# Roles describing a container's content instance.
CONTENT_ROLE_NAMES = (
    ["contentId", "contentX", "contentY", "contentWidth", "contentHeight",
     "contentRotation", "contentPlaying", "contentMuted", "contentVolume",
     "contentLoop", "contentSpeed", "contentPreservePitch", "contentLoopA",
     "contentLoopB"]
    + ["contentSource" + f for f in SOURCE_FIELDS]
)

ROLE_NAMES = (
    OBJECT_ROLE_NAMES
    + ["source" + f for f in SOURCE_FIELDS]
    + CONTENT_ROLE_NAMES
)

ROLES = {name: int(Qt.UserRole) + 1 + i for i, name in enumerate(ROLE_NAMES)}

GEOMETRY_ROLES = [ROLES[n] for n in
                  ("posX", "posY", "objWidth", "objHeight", "objRotation")]
BROWSER_ROLES = [ROLES[n] for n in
                 ("folder", "currentIndex", "includeSubfolders", "mediaFilter")]
Z_ROLES = [ROLES["objZ"]]
PLAYBACK_ROLES = [ROLES[n] for n in
                  ("objPlaying", "objMuted", "objVolume", "objLoop",
                   "objSpeed", "objPreservePitch", "objLoopA", "objLoopB")]
SOURCE_ROLES = [ROLES["source" + f] for f in SOURCE_FIELDS]
CONTAINER_ROLES = [ROLES[n] for n in
                   ("lockContent", "clipShape", "fitMode", "browseMode",
                    "browseFolder", "browseSubfolders", "mediaFilter")]
CONTENT_ROLES = [ROLES[n] for n in CONTENT_ROLE_NAMES]


def _file_url(path):
    try:
        return Path(path).as_uri()
    except ValueError:
        return ""


def _image_size(path):
    """
    Return (width, height) as displayed, or (0, 0) if unreadable.

    Reads only the file header. Accounts for EXIF orientation: a phone
    photo stored as 4000x3000 with a "rotate 90" tag displays as
    3000x4000, and that is the size the canvas should use.
    """
    reader = QImageReader(path)
    reader.setAutoTransform(True)

    size = reader.size()
    if not size.isValid():
        return 0, 0

    width, height = size.width(), size.height()

    rotate90 = QImageIOHandler.Transformation.TransformationRotate90
    if reader.transformation() & rotate90:
        width, height = height, width

    return width, height


def _source_value(source, field):
    if source is None:
        return {"Id": "", "Type": "", "Path": "", "Url": "", "Width": 0,
                "Height": 0, "Animatable": False, "Missing": False,
                "Name": ""}[field]
    if field == "Id":
        return source.id
    if field == "Type":
        return source.type
    if field == "Path":
        return source.path
    if field == "Url":
        return _file_url(source.path)
    if field == "Width":
        return source.width
    if field == "Height":
        return source.height
    if field == "Animatable":
        return is_animatable(source.path)
    if field == "Missing":
        return source.missing
    if field == "Name":
        return Path(source.path).name
    return None


class SceneModel(QAbstractListModel):

    selectedIdChanged = Signal()
    countChanged = Signal()
    dropTargetIdChanged = Signal()

    # Asks a container's delegate to enter Adjust mode.
    adjustRequested = Signal(str)

    # Emitted whenever something that gets saved changes.
    # (Selection is not saved, so it doesn't count.)
    modified = Signal()

    historyChanged = Signal()

    # Something about the selected object may have changed (its content,
    # its stacking), or the selection itself did.
    selectionStateChanged = Signal()

    # The Layers list changed (objects, names, or stacking).
    layersChanged = Signal()

    # An audio track was added (the sidebar shows its Playback tab).
    audioTrackAdded = Signal(str)

    # A container is about to browse a newly chosen folder: it should
    # move to that folder's first file unless it already shows one.
    browseFolderChosen = Signal(str)

    def __init__(self, scene=None, parent=None):
        super().__init__(parent)
        self._scene = scene if scene is not None else Scene()
        self._role_to_name = {v: k for k, v in ROLES.items()}
        self._drop_target_id = ""

        self._history = History()
        self._current = snapshot(self._scene)
        self._merge_key = None

        self._audio_model = AudioModel(self)
        self._audio_model.refresh()

    @property
    def scene(self):
        return self._scene

    @property
    def history(self):
        return self._history

    def setHistory(self, history):
        """Use a history loaded from disk (after setScene for the same project)."""
        self._history = history
        self._merge_key = None
        self.historyChanged.emit()

    def _get_audio_items(self):
        return self._audio_model

    # Every video/audio instance, for the sidebar's Playback tab.
    audioItems = Property(QObject, _get_audio_items, constant=True)

    # -------------------------------------------------
    # Rows = top-level objects
    # -------------------------------------------------

    def _rows(self):
        return self._scene.top_level()

    def _row_of(self, object_id):
        for i, obj in enumerate(self._rows()):
            if obj.id == object_id:
                return i
        return -1

    def _row_if_top_level(self, obj):
        """The row obj would have if it were top-level (list order)."""
        row = 0
        for other in self._scene.objects:
            if other is obj:
                return row
            if other.parent_id is None:
                row += 1
        return row

    # -------------------------------------------------
    # QAbstractListModel interface
    # -------------------------------------------------

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._rows())

    def roleNames(self):
        return {v: QByteArray(k.encode()) for k, v in ROLES.items()}

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        rows = self._rows()
        row = index.row()
        if not 0 <= row < len(rows):
            return None

        name = self._role_to_name.get(role)
        if name is None:
            return None

        obj = rows[row]
        sources = self._scene.sources

        if name.startswith("contentSource"):
            content = self._scene.content_of(obj.id)
            source = sources.get(content.source_id) if content else None
            return _source_value(source, name[len("contentSource"):])

        if name.startswith("content"):
            content = self._scene.content_of(obj.id)
            if content is None:
                return {"contentId": "", "contentPlaying": True,
                        "contentMuted": True, "contentLoop": True,
                        "contentVolume": 1.0, "contentSpeed": 1.0,
                        "contentPreservePitch": False, "contentLoopA": -1.0,
                        "contentLoopB": -1.0}.get(name, 0.0)
            return {
                "contentId": content.id,
                "contentX": content.x,
                "contentY": content.y,
                "contentWidth": content.width,
                "contentHeight": content.height,
                "contentRotation": content.rotation,
                "contentPlaying": content.playing,
                "contentMuted": content.muted,
                "contentVolume": content.volume,
                "contentLoop": content.loop,
                "contentSpeed": content.speed,
                "contentPreservePitch": content.preserve_pitch,
                "contentLoopA": content.loop_a,
                "contentLoopB": content.loop_b,
            }[name]

        if name.startswith("source"):
            source = sources.get(obj.source_id) if obj.source_id else None
            return _source_value(source, name[len("source"):])

        return {
            "objectId": obj.id,
            "objectType": obj.type,
            "posX": obj.x,
            "posY": obj.y,
            "objWidth": obj.width,
            "objHeight": obj.height,
            "objRotation": obj.rotation,
            "objZ": obj.z,
            "objPlaying": obj.playing,
            "objMuted": obj.muted,
            "objVolume": obj.volume,
            "objLoop": obj.loop,
            "objSpeed": obj.speed,
            "objPreservePitch": obj.preserve_pitch,
            "objLoopA": obj.loop_a,
            "objLoopB": obj.loop_b,
            "folder": obj.folder,
            "currentIndex": obj.current_index,
            "includeSubfolders": obj.include_subfolders,
            "lockContent": obj.lock_content,
            "clipShape": obj.clip_shape,
            "fitMode": obj.fit_mode,
            "browseMode": obj.browse_mode,
            "browseFolder": obj.browse_folder,
            "browseSubfolders": obj.browse_subfolders,
            "mediaFilter": obj.media_filter,
        }.get(name)

    # -------------------------------------------------
    # Whole-scene replacement (new / open)
    # -------------------------------------------------

    def setScene(self, scene):
        self.beginResetModel()
        self._scene = scene
        self._scene.selected_id = None
        self.endResetModel()

        self._history.clear()
        self._current = snapshot(self._scene)
        self.historyChanged.emit()

        self.countChanged.emit()
        self.selectedIdChanged.emit()
        self.selectionStateChanged.emit()
        self.layersChanged.emit()
        self._audio_model.refresh()

    # -------------------------------------------------
    # Change recording (undo history + "modified")
    #
    # Every change to saved state ends with _changed(). It records the
    # previous snapshot in the history, takes a new one, and tells the
    # project controller the project is modified.
    # -------------------------------------------------

    def _changed(self, workspace_only=False):
        if not workspace_only:
            self._history.record(self._current, self._merge_key, time.monotonic())
        self._merge_key = None

        self._current = snapshot(self._scene)
        self.modified.emit()
        self.historyChanged.emit()
        self.selectionStateChanged.emit()
        self.layersChanged.emit()
        self._audio_model.refresh()

    @Slot(str)
    def setMergeKey(self, key):
        """
        The next change merges with the previous one if both carry the
        same key within a short time (used for wheel zoom, so a whole
        scroll becomes one undo step).
        """
        self._merge_key = key or None

    # -------------------------------------------------
    # Undo / redo
    # -------------------------------------------------

    def _get_can_undo(self):
        return self._history.can_undo

    canUndo = Property(bool, _get_can_undo, notify=historyChanged)

    def _get_can_redo(self):
        return self._history.can_redo

    canRedo = Property(bool, _get_can_redo, notify=historyChanged)

    @Slot()
    def undo(self):
        target = self._history.undo(snapshot(self._scene))
        if target is not None:
            self._apply_state(target)

    @Slot()
    def redo(self):
        target = self._history.redo(snapshot(self._scene))
        if target is not None:
            self._apply_state(target)

    def _apply_state(self, target):
        """
        Make the live scene match `target`, announcing only the rows
        that actually appear or disappear. Unaffected objects keep their
        QML delegates, so browsers don't rescan and GIFs keep playing.
        """
        cur = self._scene
        target = snapshot(target)   # never share objects with history

        # Keep current browsing state (workspace, not undoable).
        for obj in target.objects:
            if obj.type == "browser":
                live = cur.get(obj.id)
                if live is not None:
                    for name in BROWSER_FIELDS:
                        setattr(obj, name, getattr(live, name))

        # Browsing containers: keep their browse settings, and while one
        # is browsing, what it shows (undo never changes the file).
        for obj in list(target.objects):
            if obj.type != "container":
                continue
            live = cur.get(obj.id)
            if live is None:
                continue
            for name in CONTAINER_BROWSE_FIELDS:
                setattr(obj, name, getattr(live, name))
            if live.browse_mode:
                obj.fit_mode = live.fit_mode
                target.objects = [o for o in target.objects if o.parent_id != obj.id]
                live_content = cur.content_of(obj.id)
                if live_content is not None:
                    target.objects.append(copy.deepcopy(live_content))
                    source = cur.sources.get(live_content.source_id)
                    if source is not None:
                        target.sources.setdefault(source.id, copy.deepcopy(source))

        target_top = [o.id for o in target.top_level()]
        target_top_set = set(target_top)

        # 1. Remove rows that are not top-level in the target.
        rows = self._rows()
        for row in reversed(range(len(rows))):
            if rows[row].id not in target_top_set:
                self.beginRemoveRows(QModelIndex(), row, row)
                cur.objects = [o for o in cur.objects if o is not rows[row]]
                self.endRemoveRows()

        # Contained items aren't rows; drop them (the target's copies
        # come in at the end).
        cur.objects = [o for o in cur.objects if o.parent_id is None]

        remaining = [o.id for o in cur.objects]
        it = iter(target_top)
        in_order = all(obj_id in it for obj_id in remaining)

        if not in_order:
            # Stacking list order changed in a way rows can't express
            # with inserts; rebuild the view (rare).
            self.beginResetModel()
            self._install(target)
            self.endResetModel()
        else:
            # 2. Insert rows that are new, at their target positions.
            by_id = {o.id: o for o in target.objects}
            for i, obj_id in enumerate(target_top):
                if i < len(cur.objects) and cur.objects[i].id == obj_id:
                    continue
                self.beginInsertRows(QModelIndex(), i, i)
                cur.objects.insert(i, by_id[obj_id])
                self.endInsertRows()

            # 3. Take the target's exact state for everything.
            self._install(target)
            self._emit_all([])

        if cur.selected_id is not None and cur.get(cur.selected_id) is None:
            cur.selected_id = None

        self._current = snapshot(cur)
        self.countChanged.emit()
        self.selectedIdChanged.emit()
        self.selectionStateChanged.emit()
        self.layersChanged.emit()
        self._audio_model.refresh()
        self.modified.emit()
        self.historyChanged.emit()

    def _install(self, target):
        """Replace the live scene's contents with target's (keeps selection)."""
        self._scene.sources = target.sources
        self._scene.objects = target.objects
        self._scene.refresh_missing()

    # -------------------------------------------------
    # Count
    # -------------------------------------------------

    def _get_count(self):
        return len(self._rows())

    # Number of top-level objects; lets QML know whether something is
    # already at the top of the z-order.
    count = Property(int, _get_count, notify=countChanged)

    # -------------------------------------------------
    # Selection
    # -------------------------------------------------

    def _get_selected_id(self):
        return self._scene.selected_id or ""

    selectedId = Property(str, _get_selected_id, notify=selectedIdChanged)

    def _get_selected_type(self):
        obj = self._scene.get(self._scene.selected_id)
        return obj.type if obj else ""

    selectedType = Property(str, _get_selected_type, notify=selectedIdChanged)

    def _get_selected_has_content(self):
        selected = self._scene.selected_id
        return bool(selected) and self._scene.content_of(selected) is not None

    # True when the selected object is a container holding media.
    selectedHasContent = Property(bool, _get_selected_has_content,
                                  notify=selectionStateChanged)

    # Stacking of the selected object within its group (browsers stack
    # above everything else). True when nothing is selected.
    def _get_selected_at_front(self):
        return self._scene.is_at_front(self._scene.selected_id)

    selectedAtFront = Property(bool, _get_selected_at_front,
                               notify=selectionStateChanged)

    def _get_selected_at_back(self):
        return self._scene.is_at_back(self._scene.selected_id)

    selectedAtBack = Property(bool, _get_selected_at_back,
                              notify=selectionStateChanged)

    # -------------------------------------------------
    # Layers list: top-level objects, top to bottom
    # -------------------------------------------------

    def _get_layers(self):
        scene = self._scene
        layers = []
        for obj in scene.layer_order():
            kind = obj.type
            if obj.type == "media":
                source = scene.sources.get(obj.source_id)
                kind = source.type if source else "image"
            layers.append({
                "id": obj.id,
                "type": obj.type,
                "kind": kind,
                "name": scene.display_name(obj.id),
            })
        return layers

    layers = Property("QVariantList", _get_layers, notify=layersChanged)

    @Slot(str)
    def select(self, object_id):
        new = object_id or None
        if new == self._scene.selected_id:
            return
        if self._scene.select(new):
            self.selectedIdChanged.emit()
            self.selectionStateChanged.emit()

    # -------------------------------------------------
    # Drop target (container highlighted while dragging media over it)
    # -------------------------------------------------

    def _get_drop_target_id(self):
        return self._drop_target_id

    dropTargetId = Property(str, _get_drop_target_id,
                            notify=dropTargetIdChanged)

    @Slot(str)
    def setDropTarget(self, container_id):
        if container_id != self._drop_target_id:
            self._drop_target_id = container_id
            self.dropTargetIdChanged.emit()

    @Slot(float, float, str, result=str)
    def containerAt(self, x, y, exclude_id):
        """
        The empty container under a scene point, for dropping media.
        A full container on top blocks the drop rather than letting it
        reach one underneath: content is never replaced by dropping.
        """
        obj = self._scene.container_at(x, y, exclude_id or None)
        if obj is None or self._scene.content_of(obj.id) is not None:
            return ""
        return obj.id

    # -------------------------------------------------
    # Adding / removing
    # -------------------------------------------------

    def _insert(self, create):
        row = len(self._rows())
        self.beginInsertRows(QModelIndex(), row, row)
        obj = create()
        self.endInsertRows()
        self.countChanged.emit()
        self._changed()
        self.select(obj.id)
        return obj.id

    def _register_source(self, path, media_type):
        width = height = 0
        if media_type == "image":
            width, height = _image_size(path)
        return self._scene.add_source(path, media_type, width, height)

    @Slot(float, float, result=str)
    def addBrowser(self, x, y):
        return self._insert(lambda: self._scene.add_object("browser", x, y))

    @Slot(float, float, result=str)
    def addContainer(self, x, y):
        return self._insert(lambda: self._scene.add_object("container", x, y))

    @Slot(str, str, float, float, result=str)
    def addMedia(self, path, media_type, x, y):
        source = self._register_source(path, media_type)
        return self._insert(lambda: self._scene.add_media(source.id, x, y))

    @Slot(str, str, float, float, result=str)
    def addMediaInNewContainer(self, path, media_type, x, y):
        """A browser's New Container: the file in a container of its own."""
        source = self._register_source(path, media_type)
        return self._insert(
            lambda: self._scene.add_container_with_media(source.id, x, y))

    @Slot(str, str, result=str)
    def addAudioTrack(self, path, media_type):
        """
        Add a file as a track in the Playback tab (no canvas item): an audio
        file, or a video used only for its sound. The source keeps its
        real type, so the same video can still go on the canvas.
        """
        source = self._register_source(path, media_type)
        track_id = self._insert(lambda: self._scene.add_audio_track(source.id))
        self.audioTrackAdded.emit(track_id)
        return track_id

    @Slot(str, result=str)
    def convertToAudioTrack(self, media_id):
        """
        Video as audio: replace a video with an audio track of the same
        file and settings. A video in a container takes the container
        with it (no empty container is left behind). One undo step.
        """
        track = self._scene.audio_track_from(media_id)
        if track is None:
            return ""

        # The canvas row that goes: the video, or its container.
        media = self._scene.get(media_id)
        row_id = media.parent_id or media_id
        row = self._row_of(row_id)
        self.beginRemoveRows(QModelIndex(), row, row)
        self._scene.remove_object(row_id)
        self.endRemoveRows()
        self._emit_all(Z_ROLES)

        # _insert records the whole conversion as one undo step.
        track_id = self._insert(lambda: self._scene.insert_audio_track(track))
        self.audioTrackAdded.emit(track_id)
        return track_id

    def addLayout(self, layout):
        """Add a layout's containers to the wall (one undo step)."""
        count = sum(1 for o in layout.top_level() if o.type == "container")
        if count == 0:
            return 0
        start = len(self._rows())
        self.beginInsertRows(QModelIndex(), start, start + count - 1)
        added = add_layout_to_scene(self._scene, layout)
        self.endInsertRows()
        self._emit_all(Z_ROLES)
        self.countChanged.emit()
        self._changed()
        return len(added)

    @Slot(str, result=str)
    def duplicate(self, object_id):
        if self._row_of(object_id) < 0:
            return ""
        return self._insert(lambda: self._scene.duplicate_object(object_id))

    @Slot()
    def duplicateSelected(self):
        if self._scene.selected_id:
            self.duplicate(self._scene.selected_id)

    @Slot(str)
    def locateMissing(self, object_id):
        """Ask for the new location of a missing file used by this object."""
        obj = self._scene.get(object_id)
        if obj is None:
            return

        if obj.type == "container":
            content = self._scene.content_of(object_id)
            obj = content if content is not None else obj

        source = self._scene.sources.get(obj.source_id) if obj.source_id else None
        if source is None:
            return

        old = Path(source.path)
        start = str(old.parent) if old.parent.is_dir() else str(Path.home())

        path, _ = QFileDialog.getOpenFileName(
            None, f"Locate “{old.name}”", start, _media_file_filter()
        )
        if not path:
            return

        relinked = self._scene.relink_source(source.id, path)

        # The new file may have different dimensions.
        for source_id in relinked:
            relinked_source = self._scene.sources[source_id]
            if relinked_source.type == "image":
                w, h = _image_size(relinked_source.path)
                if w > 0:
                    relinked_source.width, relinked_source.height = w, h

        self._emit_all([])
        self._changed()

        others = len(relinked) - 1
        if others > 0:
            noun = "file" if others == 1 else "files"
            QMessageBox.information(
                None, "Files Found",
                f"Also found {others} other missing {noun} in the same "
                f"folder and relinked {'it' if others == 1 else 'them'}."
            )

    @Slot(str)
    def removeObject(self, object_id):
        row = self._row_of(object_id)
        if row < 0:
            return

        content = self._scene.content_of(object_id)
        doomed = {object_id, content.id if content else None}
        was_selected = self._scene.selected_id in doomed

        self.beginRemoveRows(QModelIndex(), row, row)
        self._scene.remove_object(object_id)
        self.endRemoveRows()

        self._emit_all(Z_ROLES)
        self.countChanged.emit()
        self._changed()

        if was_selected:
            self.selectedIdChanged.emit()

    @Slot()
    def removeSelected(self):
        if self._scene.selected_id:
            self.removeObject(self._scene.selected_id)

    # -------------------------------------------------
    # Containers
    # -------------------------------------------------

    @Slot(str, str, str, result=str)
    def addMediaToContainer(self, path, media_type, container_id):
        # A full container must be emptied first (release or remove).
        if (self._row_of(container_id) < 0
                or self._scene.content_of(container_id) is not None):
            return ""

        source = self._register_source(path, media_type)
        content, _ = self._scene.add_media_to_container(source.id, container_id)
        if content is None:
            return ""

        self._emit_row(container_id, CONTENT_ROLES)
        self._changed()
        self.select(container_id)
        return content.id

    @Slot(str, str)
    def moveIntoContainer(self, media_id, container_id):
        media = self._scene.get(media_id)
        if (media is None or media.parent_id is not None
                or self._row_of(container_id) < 0
                or self._scene.content_of(container_id) is not None):
            return

        was_selected = self._scene.selected_id == media_id

        row = self._row_of(media_id)
        self.beginRemoveRows(QModelIndex(), row, row)
        moved, _ = self._scene.move_into_container(media_id, container_id)
        self.endRemoveRows()

        if not moved:
            return

        self._emit_row(container_id, CONTENT_ROLES)
        self._emit_all(Z_ROLES)
        self.countChanged.emit()
        self._changed()

        if was_selected:
            self.selectedIdChanged.emit()

    def _release_with_row(self, container_id):
        content = self._scene.content_of(container_id)
        if content is None:
            return ""

        row = self._row_if_top_level(content)
        self.beginInsertRows(QModelIndex(), row, row)
        self._scene.release_content(container_id)
        self.endInsertRows()

        self._emit_row(container_id, CONTENT_ROLES)
        self.countChanged.emit()
        self._changed()
        return content.id

    @Slot(str, result=str)
    def wrapInContainer(self, media_id):
        """
        "Crop / Zoom Inside": replace a free image with a container of
        the same box holding it, then open that container in Adjust mode.
        """
        row = self._row_of(media_id)
        if row < 0:
            return ""

        self.beginInsertRows(QModelIndex(), row, row)
        container = self._scene.insert_container_for(media_id)
        self.endInsertRows()

        if container is None:
            return ""

        media_row = self._row_of(media_id)
        self.beginRemoveRows(QModelIndex(), media_row, media_row)
        self._scene.adopt_as_content(container.id, media_id)
        self.endRemoveRows()

        self._emit_row(container.id, CONTENT_ROLES)
        self._emit_all(Z_ROLES)
        self._changed()

        self.select(container.id)
        self.selectedIdChanged.emit()
        self.adjustRequested.emit(container.id)
        return container.id

    @Slot(str, result=str)
    def releaseContent(self, container_id):
        released_id = self._release_with_row(container_id)
        if released_id:
            self.select(released_id)
        return released_id

    @Slot(str)
    def removeContent(self, container_id):
        if self._scene.remove_content(container_id):
            self._emit_row(container_id, CONTENT_ROLES)
            self._changed()

    def _browsing(self, container_id):
        """A browsing container's content is workspace state (not undone)."""
        container = self._scene.get(container_id)
        return container is not None and container.browse_mode

    @Slot(str, float, float, float, float, float)
    def commitContent(self, container_id, x, y, width, height, rotation):
        if self._scene.set_content_geometry(container_id, x, y, width,
                                            height, rotation):
            self._emit_row(container_id, CONTENT_ROLES)
            self._changed(workspace_only=self._browsing(container_id))

    @Slot(str, bool)
    def fitContent(self, container_id, fill):
        mode = FIT_COVER if fill else FIT_CONTAIN
        if self._scene.fit_content(container_id, mode):
            self._emit_row(container_id, CONTENT_ROLES + CONTAINER_ROLES)
            self._changed(workspace_only=self._browsing(container_id))

    @Slot(str)
    def resetContentFraming(self, container_id):
        """Back to the container's Fit/Fill framing (e.g. double-click)."""
        container = self._scene.get(container_id)
        if container is not None and self._scene.fit_content(container_id, container.fit_mode):
            self._emit_row(container_id, CONTENT_ROLES)
            self._changed(workspace_only=self._browsing(container_id))

    # -------------------------------------------------
    # Browsing containers (workspace state: saved, not undone)
    # -------------------------------------------------

    @Slot(str)
    def startBrowsing(self, container_id):
        """Browse the current file's folder, or ask for one if empty."""
        folder = None
        if self._scene.content_of(container_id) is None:
            folder = QFileDialog.getExistingDirectory(None, "Choose a Folder to Browse")
            if not folder:
                return
        if self._scene.set_browsing(container_id, True, folder):
            self._emit_row(container_id, CONTAINER_ROLES)
            self._changed(workspace_only=True)

    @Slot(str)
    def chooseBrowseFolder(self, container_id):
        """
        Browse Folder…: browse a folder chosen in a dialog, even when the
        container is already showing something.
        """
        container = self._scene.get(container_id)
        if container is None or container.type != "container":
            return
        content = self._scene.content_of(container_id)
        source = self._scene.sources.get(content.source_id) if content else None
        start = container.browse_folder or (str(Path(source.path).parent) if source else "")

        folder = QFileDialog.getExistingDirectory(None, "Choose a Folder to Browse", start)
        if not folder:
            return
        # Before the change, so the container's rescan knows to move on.
        self.browseFolderChosen.emit(container_id)
        if self._scene.set_browsing(container_id, True, folder):
            self._emit_row(container_id, CONTAINER_ROLES)
            self._changed(workspace_only=True)

    @Slot(str)
    def stopBrowsing(self, container_id):
        if self._scene.set_browsing(container_id, False):
            self._emit_row(container_id, CONTAINER_ROLES)
            self._changed(workspace_only=True)

    @Slot(str, bool)
    def setContainerBrowseSubfolders(self, container_id, include):
        if self._scene.set_browse_subfolders(container_id, include):
            self._emit_row(container_id, CONTAINER_ROLES)
            self._changed(workspace_only=True)

    @Slot(str, str, str)
    def showInContainer(self, container_id, path, media_type):
        """A browsing container steps to another file."""
        source = self._register_source(path, media_type)
        if self._scene.show_file_in_container(container_id, source.id):
            self._emit_row(container_id, CONTENT_ROLES)
            self._changed(workspace_only=True)

    @Slot(str, bool)
    def setLockContent(self, container_id, locked):
        if self._scene.set_lock_content(container_id, locked):
            self._emit_row(container_id, CONTAINER_ROLES)
            self._changed()

    # -------------------------------------------------
    # Editing
    # -------------------------------------------------

    @Slot(str, float, float, float, float, float)
    def commitGeometry(self, object_id, x, y, width, height, rotation):
        if self._scene.set_geometry(object_id, x, y, width, height, rotation):
            # Resizing a locked container also rescales its content.
            self._emit_row(object_id, GEOMETRY_ROLES + CONTENT_ROLES)
            self._changed()

    @Slot(str, str, float, float)
    def fillAlong(self, object_id, axis, canvas_width, canvas_height):
        """Double-click an edge bar: stretch into the free space ("v"/"h")."""
        if self._scene.fill_along(object_id, axis, canvas_width, canvas_height):
            self._emit_row(object_id, GEOMETRY_ROLES + CONTENT_ROLES)
            self._changed()

    @Slot(str, float, float, float)
    def scaleObject(self, object_id, px, py, factor):
        """Wheel zoom: scale around a scene point (content included)."""
        if self._scene.scale_object(object_id, px, py, factor):
            self._emit_row(object_id, GEOMETRY_ROLES + CONTENT_ROLES)
            self._changed()

    @Slot(str, str, int)
    def setBrowserState(self, object_id, folder, current_index):
        if self._scene.set_browser_state(object_id, folder, current_index):
            self._emit_row(object_id, BROWSER_ROLES)
            self._changed(workspace_only=True)

    @Slot(str, int)
    def setBrowserIndex(self, object_id, current_index):
        if self._scene.set_browser_index(object_id, current_index):
            self._emit_row(object_id, BROWSER_ROLES)
            self._changed(workspace_only=True)

    @Slot(str, bool)
    def setBrowserSubfolders(self, object_id, include):
        if self._scene.set_browser_subfolders(object_id, include):
            self._emit_row(object_id, BROWSER_ROLES)
            self._changed(workspace_only=True)

    @Slot(str, str)
    def setMediaFilter(self, object_id, media_filter):
        """Which files a browser or browsing container steps through."""
        if self._scene.set_media_filter(object_id, media_filter):
            obj = self._scene.get(object_id)
            self._emit_row(object_id, BROWSER_ROLES if obj.type == "browser" else CONTAINER_ROLES)
            self._changed(workspace_only=True)

    @Slot(str, bool)
    def setPlaying(self, object_id, playing):
        """object_id may be a free media object or a container's content."""
        if self._scene.set_playing(object_id, playing):
            self._emit_for(object_id, PLAYBACK_ROLES)
            self._changed()

    @Slot(str, bool)
    def setMuted(self, object_id, muted):
        self._set_media_option(object_id, "muted", muted)

    @Slot(str, bool)
    def setLoop(self, object_id, loop):
        self._set_media_option(object_id, "loop", loop)

    @Slot(str, float)
    def setVolume(self, object_id, volume):
        # A whole slider drag becomes one undo step.
        self._merge_key = "volume:" + object_id
        self._set_media_option(object_id, "volume", volume)

    @Slot(str, float)
    def setSpeed(self, object_id, speed):
        # A whole slider drag becomes one undo step.
        self._merge_key = "speed:" + object_id
        self._set_media_option(object_id, "speed", speed)

    @Slot(str, bool)
    def setPreservePitch(self, object_id, preserve):
        self._set_media_option(object_id, "preserve_pitch", preserve)

    @Slot(str, float)
    def setLoopA(self, object_id, ms):
        obj = self._scene.get(object_id)
        if obj is not None:
            self._set_loop(object_id, ms, obj.loop_b)

    @Slot(str, float)
    def setLoopB(self, object_id, ms):
        obj = self._scene.get(object_id)
        if obj is not None:
            self._set_loop(object_id, obj.loop_a, ms)

    @Slot(str)
    def clearLoop(self, object_id):
        self._set_loop(object_id, -1, -1)

    def _set_loop(self, object_id, loop_a, loop_b):
        if self._scene.set_loop(object_id, loop_a, loop_b):
            self._emit_for(object_id, PLAYBACK_ROLES)
            self._changed()

    def _set_media_option(self, object_id, name, value):
        """object_id may be a free media object or a container's content."""
        if self._scene.set_media_option(object_id, name, value):
            self._emit_for(object_id, PLAYBACK_ROLES)
            self._changed()
        else:
            self._merge_key = None

    @Slot(str, int, int)
    def reportSourceSize(self, source_id, width, height):
        """
        Called by QML once a file's real size is known (videos, or images
        whose header couldn't be read). Resizes instances that were placed
        at a placeholder size. Not an undo step of its own.
        """
        source = self._scene.sources.get(source_id)
        if source is None:
            return

        before = (source.width, source.height)
        changed = self._scene.set_source_size(source_id, width, height)
        if (source.width, source.height) == before:
            return

        for object_id in changed:
            self._emit_row(object_id, GEOMETRY_ROLES + CONTENT_ROLES)

        # Source size roles for everything using this source
        self._emit_all(SOURCE_ROLES + CONTENT_ROLES)
        self._changed(workspace_only=True)

    # -------------------------------------------------
    # Z-order
    # -------------------------------------------------

    @Slot(str)
    def bringToFront(self, object_id):
        if self._scene.bring_to_front(object_id):
            self._emit_all(Z_ROLES)
            self._changed()

    @Slot(str, int)
    def moveLayer(self, object_id, position):
        """Drag-to-reorder in the Layers list (position 0 = top)."""
        if self._scene.move_to_layer_position(object_id, position):
            self._emit_all(Z_ROLES)
            self._changed()

    @Slot(str)
    def sendToBack(self, object_id):
        if self._scene.send_to_back(object_id):
            self._emit_all(Z_ROLES)
            self._changed()

    @Slot(str)
    def bringForward(self, object_id):
        if self._scene.bring_forward(object_id):
            self._emit_all(Z_ROLES)
            self._changed()

    @Slot(str)
    def sendBackward(self, object_id):
        if self._scene.send_backward(object_id):
            self._emit_all(Z_ROLES)
            self._changed()

    # -------------------------------------------------
    # Change notification helpers
    # -------------------------------------------------

    def _emit_row(self, object_id, roles):
        row = self._row_of(object_id)
        if row >= 0:
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, roles)

    def _emit_for(self, object_id, roles):
        """Notify for a top-level object, or for its container if contained."""
        obj = self._scene.get(object_id)
        if obj is None:
            return
        if obj.parent_id is None:
            self._emit_row(object_id, roles)
        else:
            self._emit_row(obj.parent_id, CONTENT_ROLES)

    def _emit_all(self, roles):
        n = len(self._rows())
        if n > 0:
            self.dataChanged.emit(self.index(0), self.index(n - 1), roles)
