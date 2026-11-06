"""
The Library window's data (readme section 44): what's in the folder being
shown, which files are selected, the tag tree, and the search box's
results. core/library.py does the real work; this keeps QML up to date.

Nothing is opened until the window first needs it (open()), so the
library costs nothing while it isn't used.
"""

import os
import sqlite3
import threading

from PySide6.QtCore import (
    Property, QAbstractListModel, QDir, QFile, QModelIndex, QObject, Qt, QTimer, Signal, Slot,
)
from PySide6.QtWidgets import QFileDialog, QFileSystemModel

from bridge.thumbnails import ThumbnailMaker
from core.library import (
    FileSelection, Library, LibraryError, default_library_path, default_thumbnail_dir,
    found_entries, missing_summary, normalized_name, path_key,
)
from core.media_browser import MediaBrowser, format_duration


# How many search results to offer: more than this means keep typing.
MAX_RESULTS = 12

# Counts for the whole tree wait until tagging pauses: at a very large
# library they take most of a second (section 44.8).
COUNTS_DELAY_MS = 300

# How long a refusal or result stays in the status bar.
MESSAGE_MS = 8000


TRASH_NAME = "Recycle Bin" if os.name == "nt" else "Trash"


def move_to_trash(path):
    """False if the file stays where it is."""
    return QFile.moveToTrash(path)


class FilesModel(QAbstractListModel):
    """The grid's tiles. Selection lives here, as the grid reuses its delegates."""

    PathRole = Qt.UserRole + 1
    NameRole = Qt.UserRole + 2
    ThumbRole = Qt.UserRole + 3
    FailedRole = Qt.UserRole + 4
    SelectedRole = Qt.UserRole + 5
    CurrentRole = Qt.UserRole + 6
    TaggedRole = Qt.UserRole + 7
    TypeRole = Qt.UserRole + 8
    BadgeRole = Qt.UserRole + 9
    MovesRole = Qt.UserRole + 10
    MissingRole = Qt.UserRole + 11

    selectionChanged = Signal()

    def __init__(self, thumbnails, parent=None):
        super().__init__(parent)
        self._thumbnails = thumbnails
        self._entries = []
        self._rows = {}                  # path -> row
        self._tagged = set()             # rows with tags
        self.selection = FileSelection()
        thumbnails.updated.connect(self._thumbnail_updated)

    def roleNames(self):
        return {
            self.PathRole: b"path",
            self.NameRole: b"name",
            self.ThumbRole: b"thumb",
            self.FailedRole: b"failed",
            self.SelectedRole: b"selected",
            self.CurrentRole: b"current",
            self.TaggedRole: b"tagged",
            self.TypeRole: b"mediaType",
            self.BadgeRole: b"badge",
            self.MovesRole: b"moves",
            self.MissingRole: b"missing",
        }

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._entries)

    def _duration_ms(self, entry):
        return self._thumbnails.duration_ms(entry["path"], entry["size"], entry["mtime"])

    def _badge(self, entry):
        """The type and length on a tile: "GIF 0:04", "1:30" (a video or audio), or nothing."""
        length = format_duration(self._duration_ms(entry))
        if entry["type"] == "image" and entry["animatable"] and length:
            kind = "GIF" if entry["name"].lower().endswith(".gif") else "WEBP"
            return f"{kind} {length}"
        return "" if entry["type"] == "image" else length

    def file_at(self, row):
        """What a player needs to show this row."""
        if not 0 <= row < len(self._entries):
            return {}
        entry = self._entries[row]
        missing = entry.get("missing", False)
        thumb = "" if missing else self._thumbnails.url(entry["path"], entry["size"], entry["mtime"],
                                                        entry["type"], entry["animatable"])
        return {"url": entry["url"], "path": entry["path"], "name": entry["name"],
                "type": entry["type"], "animatable": entry["animatable"], "thumb": thumb,
                "missing": missing}

    def selected_entries(self):
        return [self._entries[row] for row in sorted(self.selection.selected)]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        entry = self._entries[row]
        if role == self.MissingRole:
            return entry.get("missing", False)
        if entry.get("missing", False) and role in (self.ThumbRole, self.BadgeRole, self.MovesRole,
                                                    self.FailedRole):
            return False if role in (self.MovesRole, self.FailedRole) else ""
        if role == self.PathRole:
            return entry["path"]
        if role == self.NameRole:
            return entry["relpath"]
        if role == self.ThumbRole:
            # Asked for only by tiles that exist, so thumbnails are made
            # as they come into view, not for the whole folder.
            return self._thumbnails.url(entry["path"], entry["size"], entry["mtime"],
                                        entry["type"], entry["animatable"])
        if role == self.FailedRole:
            return self._thumbnails.failed(entry["path"], entry["size"], entry["mtime"])
        if role == self.SelectedRole:
            return row in self.selection.selected
        if role == self.CurrentRole:
            return row == self.selection.current
        if role == self.TaggedRole:
            return row in self._tagged
        if role == self.TypeRole:
            return entry["type"]
        if role == self.BadgeRole:
            return self._badge(entry)
        if role == self.MovesRole:
            # Plays on hover. Audio doesn't, and a still GIF has no length.
            return entry["type"] == "video" or (entry["animatable"] and self._duration_ms(entry) > 0)
        return None

    def set_entries(self, entries, untagged):
        """A new list. Files selected before stay selected if they're still in it."""
        was_selected = {self._entries[r]["path"] for r in self.selection.selected}
        was_current = (self._entries[self.selection.current]["path"]
                       if 0 <= self.selection.current < len(self._entries) else None)

        self.beginResetModel()
        self._entries = entries
        self._rows = {e["path"]: row for row, e in enumerate(entries)}
        left = {path_key(p) for p in untagged}
        self._tagged = {row for row, e in enumerate(entries) if path_key(e["path"]) not in left}
        self.selection.restore(len(entries),
                               {self._rows[p] for p in was_selected if p in self._rows},
                               self._rows.get(was_current, -1))
        self.endResetModel()
        self.selectionChanged.emit()

    def remove_paths(self, paths):
        """
        These files have gone. Row by row, so the view stays where it's
        scrolled to. What's left of the selection stays selected; if nothing
        is, the next file (or the last, if the end went) is.
        """
        gone = sorted(self._rows[p] for p in set(paths) if p in self._rows)
        if not gone:
            return
        selected = {self._entries[r]["path"] for r in self.selection.selected - set(gone)}
        tagged = {self._entries[r]["path"] for r in self._tagged}
        current = self._entries[self.selection.current]["path"] if self.selection.current >= 0 else None

        spans = []                       # (first, last) of each run of rows
        for row in gone:
            if spans and spans[-1][1] == row - 1:
                spans[-1][1] = row
            else:
                spans.append([row, row])
        for first, last in reversed(spans):
            self.beginRemoveRows(QModelIndex(), first, last)
            del self._entries[first:last + 1]
            self.endRemoveRows()

        self._rows = {e["path"]: row for row, e in enumerate(self._entries)}
        self._tagged = {self._rows[p] for p in tagged if p in self._rows}
        rows = {self._rows[p] for p in selected}
        fallback = min(gone[0], len(self._entries) - 1)
        if not rows and fallback >= 0:
            rows = {fallback}
        self.selection.restore(len(self._entries), rows, self._rows.get(current, fallback))
        self._emit_rows(self.selection.selected | {self.selection.current} - {-1},
                        [self.SelectedRole, self.CurrentRole])
        self.selectionChanged.emit()

    def paths(self):
        return [e["path"] for e in self._entries]

    def selected_paths(self):
        return [self._entries[row]["path"] for row in sorted(self.selection.selected)]

    def _emit_rows(self, rows, roles):
        if len(rows) > 64:               # select all, say: one signal is enough
            self.dataChanged.emit(self.index(min(rows)), self.index(max(rows)), roles)
            return
        for row in rows:
            self.dataChanged.emit(self.index(row), self.index(row), roles)

    def change_selection(self, change):
        """Run `change` on the selection, then tell the tiles that differ."""
        before, current = set(self.selection.selected), self.selection.current
        change(self.selection)
        rows = before ^ self.selection.selected
        if current != self.selection.current:
            rows |= {r for r in (current, self.selection.current) if r >= 0}
        if rows:
            self._emit_rows(rows, [self.SelectedRole, self.CurrentRole])
        self.selectionChanged.emit()

    def update_tagged(self, untagged):
        """The library changed: which rows have tags now."""
        left = {path_key(p) for p in untagged}
        tagged = {row for row, e in enumerate(self._entries) if path_key(e["path"]) not in left}
        rows = tagged ^ self._tagged
        self._tagged = tagged
        if rows:
            self._emit_rows(rows, [self.TaggedRole])

    def _thumbnail_updated(self, key):
        row = self._rows.get(key[0])
        if row is not None:
            index = self.index(row)
            self.dataChanged.emit(index, index, [self.ThumbRole, self.FailedRole,
                                                 self.BadgeRole, self.MovesRole])


class TagsModel(QAbstractListModel):
    """The tag tree as a flat list: what's visible with its parents open, depth first."""

    IdRole = Qt.UserRole + 1
    NameRole = Qt.UserRole + 2
    DepthRole = Qt.UserRole + 3
    GroupRole = Qt.UserRole + 4
    ParentRole = Qt.UserRole + 5
    ExpandableRole = Qt.UserRole + 6
    ExpandedRole = Qt.UserRole + 7
    CountRole = Qt.UserRole + 8
    OnSelectionRole = Qt.UserRole + 9
    DirectRole = Qt.UserRole + 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._library = None
        self._rows = []                  # (tag, depth)
        self._collapsed = set()
        self._counts = {}
        self._on_selection = {}          # tag id -> selection_tags row
        self._only = None                # finding: only these tags, and what holds them

    def roleNames(self):
        return {
            self.IdRole: b"tagId",
            self.NameRole: b"name",
            self.DepthRole: b"depth",
            self.GroupRole: b"isGroup",
            self.ParentRole: b"parentId",
            self.ExpandableRole: b"expandable",
            self.ExpandedRole: b"expanded",
            self.CountRole: b"count",
            self.OnSelectionRole: b"onSelection",
            self.DirectRole: b"direct",
        }

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        tag, depth = self._rows[index.row()]
        if role == self.IdRole:
            return tag.id
        if role == self.NameRole:
            return tag.name
        if role == self.DepthRole:
            return depth
        if role == self.GroupRole:
            return tag.is_group
        if role == self.ParentRole:
            return -1 if tag.parent_id is None else tag.parent_id
        if role == self.ExpandableRole:
            return self._library.has_children(tag.id)
        if role == self.ExpandedRole:
            return tag.id not in self._collapsed
        if role == self.CountRole:
            return self._counts.get(tag.id, 0)
        if role == self.OnSelectionRole:
            row = self._on_selection.get(tag.id)
            return row["count"] if row else 0
        if role == self.DirectRole:
            row = self._on_selection.get(tag.id)
            return row["direct"] if row else 0
        return None

    def set_library(self, library):
        self._library = library
        self.rebuild()

    def rebuild(self):
        """The tree's shape changed."""
        self.beginResetModel()
        self._rows = []
        hidden_below = None
        for tag, depth in self._library.tree():
            if self._only is not None and tag.id not in self._only:
                continue
            if hidden_below is not None and depth > hidden_below:
                continue
            hidden_below = depth if tag.id in self._collapsed else None
            self._rows.append((tag, depth))
        self.endResetModel()

    def toggle(self, tag_id):
        self._collapsed ^= {tag_id}
        self.rebuild()

    def expand(self, tag_id):
        self._collapsed.discard(tag_id)

    def _changed_all(self, roles):
        if self._rows:
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1), roles)

    def set_counts(self, counts):
        self._counts = counts
        self._changed_all([self.CountRole])

    def set_only(self, tag_ids):
        """Finding: show only these tags and what holds them. None: all of them."""
        only = None
        if tag_ids is not None:
            only = set()
            for tag_id in tag_ids:
                only.add(tag_id)
                only.update(tag.id for tag in self._library.ancestors(tag_id))
        if only != self._only:
            self._only = only
            self.rebuild()

    def set_on_selection(self, rows):
        self._on_selection = {row["tag"].id: row for row in rows}
        self._changed_all([self.OnSelectionRole, self.DirectRole])


class TagLibrary(QObject):
    """Everything the Library window calls."""

    openedChanged = Signal()
    errorChanged = Signal()
    messageChanged = Signal()
    folderChanged = Signal()
    scanningChanged = Signal()
    untaggedOnlyChanged = Signal()
    findModeChanged = Signal()
    filtersChanged = Signal()
    selectionChanged = Signal()
    resultsChanged = Signal()
    historyChanged = Signal()
    treeChanged = Signal()
    # Tagging has paused: browsing containers with a saved search look again.
    searchesChanged = Signal()
    # Clean Up has counted what's missing: (how many, where), to ask first.
    cleanUpReady = Signal(int, str)
    currentRowChanged = Signal(int)

    _scanned = Signal(int, object)
    _missing_counted = Signal(object)
    _trashed = Signal(object, object)

    def __init__(self, app_settings, parent=None):
        super().__init__(parent)
        self._settings = app_settings
        self._library = None
        self._error = ""
        self._message = ""
        self._folder = ""
        self._scanning = False
        self._untagged_only = False
        self._find_mode = False
        self._filters = []               # finding: [{id, name, exclude}]
        self._find_folder = ""           # finding: limited to this folder
        self._scan_generation = 0
        self._results = []
        self._highlight = 0
        self._selection_rows = []
        self._applied = []               # tags applied this session, for Backspace
        self._thumbnails = None
        self._files = None
        self._tags = TagsModel(self)
        self._folder_model = None
        self._counts_timer = QTimer(self)
        self._counts_timer.setSingleShot(True)
        self._counts_timer.setInterval(COUNTS_DELAY_MS)
        self._counts_timer.timeout.connect(self._tagging_paused)
        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.setInterval(MESSAGE_MS)
        self._message_timer.timeout.connect(lambda: self._say(""))
        self._scanned.connect(self._scan_finished)
        self._missing_counted.connect(self._clean_up_counted)
        self._clean_up_ids = []
        self._trashed.connect(self._trash_finished)
        self._trashing = False

    # -------------------------------------------------
    # Opening and closing
    # -------------------------------------------------

    def _open_database(self):
        """
        The first time anything needs it: the window opening, or a project
        with a browsing container that has a saved search. True if it's open.
        """
        if self._library is None and not self._error:
            try:
                self._library = Library(default_library_path())
            except LibraryError as e:
                self._error = str(e)
                self.errorChanged.emit()
                return False
            self._tags.set_library(self._library)
        return self._library is not None

    @Slot()
    def open(self):
        """The window opened. Later openings find everything as it was left."""
        if self._files is None and self._open_database():
            self._thumbnails = ThumbnailMaker(default_thumbnail_dir(), self)
            self._files = FilesModel(self._thumbnails, self)
            self._files.selectionChanged.connect(self._selection_updated)
            self._refresh_counts()
            self.openedChanged.emit()
            self._folder = self._settings.libraryFolder
            self.folderChanged.emit()
            if self._folder:
                self._scan()

    @Slot()
    def shutdown(self):
        if self._thumbnails is not None:
            self._thumbnails.shutdown()
        if self._library is not None:
            self._library.close()
            self._library = None

    def _get_opened(self):
        return self._files is not None

    opened = Property(bool, _get_opened, notify=openedChanged)

    def _get_error(self):
        return self._error

    # Why the library couldn't be opened, or "".
    error = Property(str, _get_error, notify=errorChanged)

    def _get_message(self):
        return self._message

    # The latest refusal or result, for the status bar.
    message = Property(str, _get_message, notify=messageChanged)

    def _say(self, text):
        self._message = text
        self.messageChanged.emit()
        if text:
            self._message_timer.start()

    def _attempt(self, action):
        """Run a change to the library. A refusal is shown, not raised. True if it worked."""
        if self._library is None:
            return False
        try:
            action()
        except LibraryError as e:
            self._say(str(e))
            return False
        except sqlite3.Error as e:
            self._say(f"Couldn't save to the tag library: {e}")
            return False
        return True

    # -------------------------------------------------
    # The folder pane
    # -------------------------------------------------

    def _get_folder_model(self):
        if self._folder_model is None:
            self._folder_model = QFileSystemModel(self)
            self._folder_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Drives)
            self._folder_model.setRootPath(QDir.rootPath())
            self._folder_model.sort(0)
        return self._folder_model

    folderModel = Property(QObject, _get_folder_model, constant=True)

    @Slot(str, result=QModelIndex)
    def folderIndex(self, path):
        return self._get_folder_model().index(path) if path else QModelIndex()

    def _get_folder(self):
        return self._find_folder if self._find_mode else self._folder

    # What the folder tree shows as chosen. When finding, nothing means the whole library.
    folder = Property(str, _get_folder, notify=folderChanged)

    @Slot(str)
    def setFolder(self, path):
        # As the folder tree writes it (with "/"), so it can show which is current.
        path = QDir.fromNativeSeparators(path)
        if self._find_mode:
            if path != self._find_folder:
                self._find_folder = path
                self.folderChanged.emit()
                self.filtersChanged.emit()
                self._scan()
            return
        if path == self._folder:
            return
        self._folder = path
        self._settings.libraryFolder = path
        self.folderChanged.emit()
        if self._thumbnails is not None:
            self._thumbnails.clear_pending()
        self._scan()

    @Slot()
    def chooseFolder(self):
        path = QFileDialog.getExistingDirectory(None, "Choose Media Folder", self._folder)
        if path:
            self.setFolder(path)

    def _get_subfolders(self):
        return self._settings.librarySubfolders

    def _set_subfolders(self, value):
        if value != self._settings.librarySubfolders:
            self._settings.librarySubfolders = value
            self.folderChanged.emit()
            self._scan()

    subfolders = Property(bool, _get_subfolders, _set_subfolders, notify=folderChanged)

    def _get_untagged_only(self):
        return self._untagged_only

    def _set_untagged_only(self, value):
        if value != self._untagged_only:
            self._untagged_only = value
            self.untaggedOnlyChanged.emit()
            self._scan()

    # Files tagged while this is on stay in view until the next scan, so
    # a series of tags can go on the same file without it disappearing.
    untaggedOnly = Property(bool, _get_untagged_only, _set_untagged_only, notify=untaggedOnlyChanged)

    def _scan(self):
        """
        Fill the file list: a folder's files, or when finding, the search's.
        On a thread of its own: a big tree or a slow drive can take a long
        time, and can't be interrupted, so it's left behind if another
        scan starts or the app closes (hence the generation, and daemon).
        """
        self._scan_generation += 1
        generation = self._scan_generation
        recursive = self._settings.librarySubfolders
        self._scanning = True
        self.scanningChanged.emit()

        if self._find_mode:
            # The database belongs to this thread; only the disk is asked there.
            rows = self._library.find(
                [f["id"] for f in self._filters if not f["exclude"]],
                [f["id"] for f in self._filters if f["exclude"]],
                self._find_folder or None, recursive)

            def work():
                self._scanned.emit(generation, found_entries(rows))
        else:
            folder = self._folder

            def work():
                self._scanned.emit(generation, MediaBrowser().scan_folder(folder, recursive))

        threading.Thread(target=work, daemon=True).start()

    def _scan_finished(self, generation, entries):
        if generation != self._scan_generation or self._library is None:
            return
        self._scanning = False
        self.scanningChanged.emit()
        if self._find_mode:
            # What's left to narrow by: the tags in these results.
            self._found_counts = self._library.tag_counts([e["id"] for e in entries])
            self._tags.set_counts(self._found_counts)
            self._tags.set_only(self._found_counts.keys())
        else:
            self._reattach_moved(entries)
        untagged = self._library.untagged([e["path"] for e in entries])
        if self._untagged_only and not self._find_mode:
            left = {path_key(p) for p in untagged}
            entries = [e for e in entries if path_key(e["path"]) in left]
        self._files.set_entries(entries, untagged)
        self.currentRowChanged.emit(self._files.selection.current)

    def _reattach_moved(self, entries):
        moved = []
        if self._attempt(lambda: moved.extend(self._library.relink(entries))) and moved:
            for old, new in moved:
                print(f"Library: tags moved from {old} to {new}", flush=True)  # the Log window
            self._say(f'Kept the tags of {len(moved)} moved {"file" if len(moved) == 1 else "files"}.')
            self._counts_timer.start()

    def _get_scanning(self):
        return self._scanning

    scanning = Property(bool, _get_scanning, notify=scanningChanged)

    # -------------------------------------------------
    # Files and selection
    # -------------------------------------------------

    def _get_files(self):
        return self._files

    files = Property(QObject, _get_files, notify=openedChanged)

    def _selected_paths(self):
        return self._files.selected_paths() if self._files is not None else []

    def _selection_updated(self):
        self._refresh_selection_tags()
        self.selectionChanged.emit()

    def _refresh_selection_tags(self):
        rows = self._library.selection_tags(self._selected_paths())
        if self._find_mode:
            self._selection_rows = []
            self._tags.set_on_selection([])
            return
        self._selection_rows = [{
            "id": row["tag"].id,
            "name": row["tag"].name,
            "count": row["count"],
            "direct": row["direct"],
            "via": ", ".join(row["via"]),
        } for row in rows]
        self._tags.set_on_selection(rows)

    def _get_file_count(self):
        return self._files.rowCount() if self._files is not None else 0

    # How many files are listed.
    fileCount = Property(int, _get_file_count, notify=selectionChanged)

    def _get_selected_count(self):
        return len(self._files.selection.selected) if self._files is not None else 0

    selectedCount = Property(int, _get_selected_count, notify=selectionChanged)

    def _get_selection_tags(self):
        return self._selection_rows

    # [{id, name, count, direct, via}]: the tags on the selection, most common first.
    selectionTags = Property(list, _get_selection_tags, notify=selectionChanged)

    def _get_current_row(self):
        return self._files.selection.current if self._files is not None else -1

    currentRow = Property(int, _get_current_row, notify=currentRowChanged)

    @Slot(int, result="QVariantMap")
    def fileAt(self, row):
        return self._files.file_at(row) if self._files is not None else {}

    @Slot(int, bool, bool)
    def clickFile(self, row, ctrl, shift):
        self._files.change_selection(lambda s: s.click(row, ctrl, shift))
        self.currentRowChanged.emit(self._files.selection.current)

    @Slot(int)
    def stepFile(self, delta):
        """Left, Right, and Enter in an empty box: the previous or next file."""
        if self._files is not None:
            self._files.change_selection(lambda s: s.step(delta))
            self.currentRowChanged.emit(self._files.selection.current)

    @Slot()
    def selectAll(self):
        if self._files is not None:
            self._files.change_selection(lambda s: s.select_all())

    # -------------------------------------------------
    # To the wall (section 44.5)
    # -------------------------------------------------

    @Slot(result=list)
    def selectedForWall(self):
        """[{path, type}]: the selected files that are still there."""
        if self._files is None:
            return []
        return [{"path": e["path"], "type": e["type"]}
                for e in self._files.selected_entries() if not e.get("missing", False)]

    @Slot(int)
    def reportAdded(self, added):
        """Say what Add to Wall did, with anything left out."""
        left_out = self._get_selected_count() - added
        text = f"Added {added} to the wall." if added else "Nothing added."
        if left_out:
            text += f" {left_out} missing or left out."
        self._say(text)

    @Slot(str)
    def say(self, text):
        self._say(text)

    @Slot(int, result=str)
    def dragUrls(self, row):
        """
        What dragging this tile carries, as a text/uri-list: the selection
        if it's among it, otherwise it alone (which it then selects).
        """
        if self._files is None:
            return ""
        if row not in self._files.selection.selected:
            self.clickFile(row, False, False)
        return "\r\n".join(e["url"] for e in self._files.selected_entries() if e["url"])

    # -------------------------------------------------
    # Deleting files (section 44.1)
    # -------------------------------------------------

    trashName = Property(str, lambda self: TRASH_NAME, constant=True)

    @Slot()
    def trashSelected(self):
        """
        Move the selected files that are still there to the Trash, off the
        UI thread: a large selection or a slow drive can take a while.
        QML has asked first, and let go of any file it was playing.
        """
        if self._files is None or self._trashing:
            return
        paths = [e["path"] for e in self._files.selected_entries() if not e.get("missing", False)]
        if not paths:
            return
        self._trashing = True
        self._say(f"Moving to the {TRASH_NAME}…")

        def work():
            gone, failed = [], []
            for path in paths:
                (gone if move_to_trash(path) else failed).append(path)
            self._trashed.emit(gone, failed)

        threading.Thread(target=work, daemon=True).start()

    def _trash_finished(self, gone, failed):
        self._trashing = False
        if self._library is None:
            return
        self._say("")
        self._files.remove_paths(gone)
        if gone:
            self._tree_edited(lambda: self._library.forget_files(gone))
        for path in failed:
            print(f"Library: couldn't move {path} to the {TRASH_NAME}", flush=True)  # the Log window
        text = f'Moved {len(gone)} {"file" if len(gone) == 1 else "files"} to the {TRASH_NAME}.' if gone else ""
        if failed:
            many = len(failed) > 1
            text += (f' {len(failed)} {"files" if many else "file"} couldn\'t be moved'
                     f' ({"they may be" if many else "it may be"} open on the wall): see the Log.')
        self._say(text.strip())
        self.currentRowChanged.emit(self._files.selection.current)

    # -------------------------------------------------
    # Finding (section 44.5)
    # -------------------------------------------------

    def _get_find_mode(self):
        return self._find_mode

    def _set_find_mode(self, value):
        if value == self._find_mode or self._library is None:
            return
        self._find_mode = value
        self.findModeChanged.emit()
        self.folderChanged.emit()
        self.setQuery("")
        if value:
            self._tags.set_on_selection([])
        else:
            self._tags.set_only(None)
            self._refresh_counts()
        self._scan()

    # Tab: the box builds a search rather than tagging.
    findMode = Property(bool, _get_find_mode, _set_find_mode, notify=findModeChanged)

    def _get_filters(self):
        return self._filters

    # [{id, name, exclude}], combined as AND.
    filters = Property(list, _get_filters, notify=filtersChanged)

    def _add_filter(self, tag_id, exclude=False):
        tag = self._library.tag(tag_id)
        if tag is None:
            return
        self._filters = [f for f in self._filters if f["id"] != tag_id]
        self._filters.append({"id": tag_id, "name": tag.name, "exclude": exclude})
        self.filtersChanged.emit()
        self._scan()

    @Slot(int)
    def removeFilter(self, tag_id):
        self._filters = [f for f in self._filters if f["id"] != tag_id]
        self.filtersChanged.emit()
        self._scan()

    def _forget_gone_filters(self):
        kept = [f for f in self._filters if self._library.tag(f["id"]) is not None]
        for f in kept:
            f["name"] = self._library.tag(f["id"]).name
        self._filters = kept
        self.filtersChanged.emit()

    # -------------------------------------------------
    # The search box
    # -------------------------------------------------

    def _get_results(self):
        return self._results

    # [{id, name, where, create}]: what Enter can apply. `create` is the
    # offer to make a tag of what was typed, when nothing matches.
    results = Property(list, _get_results, notify=resultsChanged)

    def _get_highlight(self):
        return self._highlight

    highlight = Property(int, _get_highlight, notify=resultsChanged)

    @Slot(str)
    def setQuery(self, text):
        self._highlight = 0
        self._results = self._results_for(text)
        self.resultsChanged.emit()

    def _results_for(self, text):
        if self._library is None:
            return []
        if self._find_mode:
            words = " ".join(text.split())
            exclude = words.startswith("-")
            tags = self._library.search(words[1:] if exclude else words, include_groups=True,
                                        limit=MAX_RESULTS)
            return [{"id": t.id, "name": t.name, "where": self._library.where(t.id),
                     "create": False, "exclude": exclude} for t in tags]
        tags = self._library.search(text, limit=MAX_RESULTS)
        rows = [{"id": t.id, "name": t.name, "where": self._library.where(t.id), "create": False,
                 "exclude": False} for t in tags]
        if not rows and text.strip():
            rows = [{"id": -1, "name": " ".join(text.split()), "where": "", "create": True,
                     "exclude": False}]
        return rows

    @Slot(int)
    def moveHighlight(self, delta):
        if self._results:
            self._highlight = (self._highlight + delta) % len(self._results)
            self.resultsChanged.emit()

    @Slot(str, result=bool)
    def applyResult(self, text):
        """Enter. Works from `text` itself, so a fast Enter can't apply an old result."""
        results = self._results_for(text)
        if not results:
            return False
        if self._results != results:
            self._results = results
            self._highlight = 0
            self.resultsChanged.emit()
        chosen = results[self._highlight]
        if self._find_mode:
            self._add_filter(chosen["id"], chosen["exclude"])
            return True
        if chosen["create"]:
            return self.createAndApply(text)
        return self._apply(chosen["id"])

    @Slot(str, result=bool)
    def createAndApply(self, text):
        """Shift+Enter: a tag of exactly what was typed."""
        if self._find_mode:
            return False
        paths = self._selected_paths()
        if not paths:
            self._say("Select a file to tag first.")
            return False
        created = []
        if not self._attempt(lambda: created.append(self._library.create_and_apply(text, paths))):
            return False
        self._applied.append(created[0].id)
        self._tags.rebuild()
        self._tagging_changed()
        return True

    def _apply(self, tag_id):
        paths = self._selected_paths()
        if not paths:
            self._say("Select a file to tag first.")
            return False
        if not self._attempt(lambda: self._library.apply_tag(tag_id, paths)):
            return False
        self._applied.append(tag_id)
        self._tagging_changed()
        return True

    @Slot()
    def removeLastApplied(self):
        """Backspace in an empty box: take the last tag applied off the selection (or filter off the search)."""
        if self._find_mode:
            if self._filters:
                self.removeFilter(self._filters[-1]["id"])
            return
        while self._applied:
            tag_id = self._applied.pop()
            if self._library.tag(tag_id) is not None:
                self._remove(tag_id)
                return

    def _remove(self, tag_id):
        if self._attempt(lambda: self._library.remove_tag(tag_id, self._selected_paths())):
            self._tagging_changed()

    @Slot(int)
    def toggleTag(self, tag_id):
        """A click in the tags pane: on every selected file, or else off them all. Finding: narrow by it."""
        if self._find_mode:
            self._add_filter(tag_id)
            return
        count = len(self._selected_paths())
        if not count:
            self._say("Select a file to tag first.")
            return
        row = next((r for r in self._selection_rows if r["id"] == tag_id), None)
        if row is not None and row["direct"] == count:
            self._remove(tag_id)
        else:
            self._apply(tag_id)

    def _tagging_changed(self):
        if self._files is not None:
            self._files.update_tagged(self._library.untagged(self._files.paths()))
        self._refresh_selection_tags()
        self.selectionChanged.emit()
        self.historyChanged.emit()
        self.setQuery("")
        if self._find_mode:
            self._forget_gone_filters()
            self._scan()                 # the results may have changed
        self._counts_timer.start()

    def _refresh_counts(self):
        if self._library is not None and not self._find_mode:
            self._tags.set_counts(self._library.tag_counts())

    def _tagging_paused(self):
        self._refresh_counts()
        self.searchesChanged.emit()

    # -------------------------------------------------
    # A browsing container's saved search (section 44.5)
    # -------------------------------------------------

    @Slot(list, list, str, str, bool, str, list, result=list)
    def searchFiles(self, include, exclude, media_filter, sort_by, descending, seed, favorites):
        """Like BrowserBackend.scanContainerFolder, for a search rather than a folder."""
        if not self._open_database():
            return []
        try:
            return self._library.search_files([str(n) for n in include], [str(n) for n in exclude],
                                              media_filter, sort_by, descending, seed,
                                              [str(p) for p in favorites])
        except sqlite3.Error as e:
            print(f"Tag library: {e}", flush=True)  # the Log window
            return []

    @Slot(result="QVariantMap")
    def currentSearch(self):
        """What New Browsing Container from This Search saves: {include, exclude} names."""
        return {"include": [f["name"] for f in self._filters if not f["exclude"]],
                "exclude": [f["name"] for f in self._filters if f["exclude"]]}

    # -------------------------------------------------
    # Undo (tagging only: section 44.6)
    # -------------------------------------------------

    def _get_can_undo(self):
        return self._library is not None and self._library.can_undo()

    canUndo = Property(bool, _get_can_undo, notify=historyChanged)

    def _get_can_redo(self):
        return self._library is not None and self._library.can_redo()

    canRedo = Property(bool, _get_can_redo, notify=historyChanged)

    @Slot()
    def undo(self):
        self._attempt(self._library.undo)
        self._tags.rebuild()             # it may have removed a tag it created
        self._tagging_changed()

    @Slot()
    def redo(self):
        self._attempt(self._library.redo)
        self._tags.rebuild()
        self._tagging_changed()

    # -------------------------------------------------
    # The tags pane: the tree (section 44.3)
    # -------------------------------------------------

    def _get_tags(self):
        return self._tags

    tags = Property(QObject, _get_tags, constant=True)

    @Slot(int)
    def toggleExpanded(self, tag_id):
        self._tags.toggle(tag_id)

    def _tree_edited(self, action):
        if not self._attempt(action):
            return False
        self._tags.rebuild()
        self._tagging_changed()
        return True

    @Slot(str, int, result=bool)
    def createGroup(self, name, parent_id):
        return self._tree_edited(lambda: self._library.create_group(
            name, None if parent_id < 0 else parent_id))

    @Slot(int, str, result=bool)
    def renameTag(self, tag_id, name):
        return self._tree_edited(lambda: self._library.rename(tag_id, name))

    @Slot(int, int)
    def moveTag(self, tag_id, parent_id):
        """A drag in the tree. -1: to the top level."""
        if parent_id >= 0:
            self._tags.expand(parent_id)
        self._tree_edited(lambda: self._library.move(tag_id, None if parent_id < 0 else parent_id))

    @Slot(int, str, result=bool)
    def mergeTag(self, tag_id, target_name):
        target = self._library.tag_by_name(target_name)
        if target is None:
            self._say(f'There is no tag named "{" ".join(target_name.split())}".')
            return False
        return self._tree_edited(lambda: self._library.merge(tag_id, target.id))

    @Slot(int)
    def makeGroup(self, tag_id):
        self._tree_edited(lambda: self._library.make_group(tag_id))

    @Slot(int)
    def makeTag(self, tag_id):
        self._tree_edited(lambda: self._library.make_tag(tag_id))

    @Slot(int)
    def deleteTag(self, tag_id):
        self._tree_edited(lambda: self._library.delete(tag_id))

    @Slot(int, result=int)
    def tagUsage(self, tag_id):
        """How many files have this tag directly (asked before deleting it)."""
        tag = self._library.tag(tag_id) if self._library is not None else None
        return tag.used if tag is not None else 0

    @Slot(str, int, result=list)
    def mergeChoices(self, text, excluding):
        """Tags to merge into, for the dialog's list."""
        if self._library is None:
            return []
        return [t.name for t in self._library.search(text, limit=MAX_RESULTS) if t.id != excluding]

    @Slot(str, result=str)
    def nameProblem(self, name):
        """What's wrong with a new tag or group name, or "" (for a dialog's OK button)."""
        try:
            normalized_name(name)
        except LibraryError as e:
            return str(e)
        return ""

    # -------------------------------------------------
    # Clean Up (section 44.6)
    # -------------------------------------------------

    @Slot()
    def startCleanUp(self):
        """Look for what's missing, off the UI thread: a slow drive can take a while."""
        if self._library is None:
            return
        self._say("Looking for missing files…")
        rows = self._library.file_rows()

        def work():
            self._missing_counted.emit([row for row in rows if not os.path.exists(row[1])])

        threading.Thread(target=work, daemon=True).start()

    def _clean_up_counted(self, missing):
        self._clean_up_ids = [file_id for file_id, _ in missing]
        if not missing:
            self._say("No files are missing.")
            return
        self._say("")
        self.cleanUpReady.emit(len(missing), missing_summary([path for _, path in missing]))

    @Slot()
    def confirmCleanUp(self):
        count = []
        ids, self._clean_up_ids = self._clean_up_ids, []
        if self._tree_edited(lambda: count.append(self._library.clean_up(ids))):
            self._say(f'Forgot the tags of {count[0]} missing {"file" if count[0] == 1 else "files"}.')

    # -------------------------------------------------
    # Export and import (section 44.6)
    # -------------------------------------------------

    @Slot(bool)
    def chooseExport(self, include_files):
        title = "Export Everything" if include_files else "Export Tags Only"
        path, _ = QFileDialog.getSaveFileName(None, title, "mediawall-tags.json", "JSON (*.json)")
        if path:
            self.exportTo(path, include_files)

    @Slot(str, bool)
    def exportTo(self, path, include_files):
        def export():
            try:
                self._library.export_json(path, include_files)
            except OSError as e:
                raise LibraryError(f"Couldn't write that file: {e}") from e
        if self._attempt(export):
            self._say(f"Exported to {path}")

    @Slot()
    def chooseImport(self):
        path, _ = QFileDialog.getOpenFileName(None, "Import Tags", "", "JSON (*.json)")
        if path:
            self.importFrom(path)

    @Slot(str)
    def importFrom(self, path):
        report = []
        if not self._tree_edited(lambda: report.append(self._library.import_json(path))):
            return
        added = report[0]
        for warning in added["warnings"]:
            print(f"Library import: {warning}", flush=True)  # the Log window
        text = f'Imported {added["tags"]} tags, {added["files"]} files, {added["links"]} file tags.'
        if added["warnings"]:
            text += f' {len(added["warnings"])} problems: see the Log.'
        self._say(text)
