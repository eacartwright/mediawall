"""
Qt bridge: every sound-producing media instance, for the sidebar's
Audio tab (readme section 14).

Rows are media instances whose source is a video or an audio file, in
Layers order (top first); a container's content is listed as itself,
with ownerId pointing at the container (what selecting the row selects).

SceneModel calls refresh() after every change. When the set of rows is
unchanged, rows are updated in place, so a slider being dragged in the
Audio tab isn't recreated under the pointer.
"""

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt


AUDIO_SOURCE_TYPES = {"video", "audio"}

ROLE_NAMES = [
    "itemId", "ownerId", "name", "kind", "inContainer", "missing",
    "playing", "muted", "volume", "loop", "speed", "preservePitch",
    "loopA", "loopB",
]
ROLES = {name: int(Qt.UserRole) + 1 + i for i, name in enumerate(ROLE_NAMES)}


class AudioModel(QAbstractListModel):

    def __init__(self, scene_model):
        super().__init__(scene_model)
        self._scene_model = scene_model
        self._role_to_name = {v: k for k, v in ROLES.items()}
        self._ids = []

    def _scene(self):
        return self._scene_model.scene

    def _collect(self):
        scene = self._scene()
        items = []
        for obj in scene.layer_order():
            media = scene.content_of(obj.id) if obj.type == "container" else obj
            if media is None or media.type != "media":
                continue
            source = scene.sources.get(media.source_id)
            if source is not None and source.type in AUDIO_SOURCE_TYPES:
                items.append(media.id)
        return items

    def refresh(self):
        ids = self._collect()
        if ids == self._ids:
            if ids:
                self.dataChanged.emit(self.index(0), self.index(len(ids) - 1), [])
            return
        self.beginResetModel()
        self._ids = ids
        self.endResetModel()

    # ---- QAbstractListModel ----

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._ids)

    def roleNames(self):
        return {role: QByteArray(name.encode()) for name, role in ROLES.items()}

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._ids):
            return None
        name = self._role_to_name.get(role)
        scene = self._scene()
        media = scene.get(self._ids[index.row()])
        if name is None or media is None:
            return None

        source = scene.sources.get(media.source_id)
        return {
            "itemId": media.id,
            "ownerId": media.parent_id or media.id,
            "name": scene.source_name(media.source_id),
            "kind": source.type if source else "video",
            "inContainer": media.parent_id is not None,
            "missing": bool(source and source.missing),
            "playing": media.playing,
            "muted": media.muted,
            "volume": media.volume,
            "loop": media.loop,
            "speed": media.speed,
            "preservePitch": media.preserve_pitch,
            "loopA": media.loop_a,
            "loopB": media.loop_b,
        }[name]
