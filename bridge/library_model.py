"""
The Library window's data (readme section 44): what's in the folder being
shown, which files are selected, the tag tree, and the search box's
results. core/library.py does the real work; this keeps QML up to date.

Nothing is opened until the window first needs it (open()), so the
library costs nothing while it isn't used.
"""

import sqlite3
import threading

from PySide6.QtCore import (
    Property, QAbstractListModel, QDir, QModelIndex, QObject, Qt, QTimer, Signal, Slot,
)
from PySide6.QtWidgets import QFileDialog, QFileSystemModel

from bridge.thumbnails import ThumbnailMaker
from core.library import (
    FileSelection, Library, LibraryError, default_library_path, default_thumbnail_dir,
    normalized_name, path_key,
)
from core.media_browser import MediaBrowser


# Pictures for now; video and audio are the next step (section 44.8).
FILE_FILTER = "image"

# How many search results to offer: more than this means keep typing.
MAX_RESULTS = 12

# Counts for the whole tree wait until tagging pauses: at a very large
# library they take most of a second (section 44.8).
COUNTS_DELAY_MS = 300

# How long a refusal or result stays in the status bar.
MESSAGE_MS = 8000


class FilesModel(QAbstractListModel):
    """The grid's tiles. Selection lives here, as the grid reuses its delegates."""

    PathRole = Qt.UserRole + 1
    NameRole = Qt.UserRole + 2
    ThumbRole = Qt.UserRole + 3
    FailedRole = Qt.UserRole + 4
    SelectedRole = Qt.UserRole + 5
    CurrentRole = Qt.UserRole + 6
    TaggedRole = Qt.UserRole + 7

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
        }

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        entry = self._entries[row]
        if role == self.PathRole:
            return entry["path"]
        if role == self.NameRole:
            return entry["relpath"]
        if role == self.ThumbRole:
            # Asked for only by tiles that exist, so thumbnails are made
            # as they come into view, not for the whole folder.
            return self._thumbnails.url(entry["path"], entry["size"], entry["mtime"])
        if role == self.FailedRole:
            return self._thumbnails.failed(entry["path"], entry["size"], entry["mtime"])
        if role == self.SelectedRole:
            return row in self.selection.selected
        if role == self.CurrentRole:
            return row == self.selection.current
        if role == self.TaggedRole:
            return row in self._tagged
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
            self.dataChanged.emit(index, index, [self.ThumbRole, self.FailedRole])


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
    selectionChanged = Signal()
    resultsChanged = Signal()
    historyChanged = Signal()
    treeChanged = Signal()
    currentRowChanged = Signal(int)

    _scanned = Signal(int, object)

    def __init__(self, app_settings, parent=None):
        super().__init__(parent)
        self._settings = app_settings
        self._library = None
        self._error = ""
        self._message = ""
        self._folder = ""
        self._scanning = False
        self._untagged_only = False
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
        self._counts_timer.timeout.connect(self._refresh_counts)
        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.setInterval(MESSAGE_MS)
        self._message_timer.timeout.connect(lambda: self._say(""))
        self._scanned.connect(self._scan_finished)

    # -------------------------------------------------
    # Opening and closing
    # -------------------------------------------------

    @Slot()
    def open(self):
        """The window opened. Later openings find everything as it was left."""
        if self._library is None and not self._error:
            try:
                self._library = Library(default_library_path())
            except LibraryError as e:
                self._error = str(e)
                self.errorChanged.emit()
                return
            self._thumbnails = ThumbnailMaker(default_thumbnail_dir(), self)
            self._files = FilesModel(self._thumbnails, self)
            self._files.selectionChanged.connect(self._selection_updated)
            self._tags.set_library(self._library)
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
        return self._library is not None

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
        return self._folder

    folder = Property(str, _get_folder, notify=folderChanged)

    @Slot(str)
    def setFolder(self, path):
        # As the folder tree writes it (with "/"), so it can show which is current.
        path = QDir.fromNativeSeparators(path)
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
        On a thread of its own: a big tree or a slow drive can take a long
        time, and can't be interrupted, so it's left behind if another
        scan starts or the app closes (hence the generation, and daemon).
        """
        self._scan_generation += 1
        generation = self._scan_generation
        folder, recursive = self._folder, self._settings.librarySubfolders
        self._scanning = True
        self.scanningChanged.emit()

        def work():
            entries = MediaBrowser().scan_folder(folder, recursive, FILE_FILTER)
            self._scanned.emit(generation, entries)

        threading.Thread(target=work, daemon=True).start()

    def _scan_finished(self, generation, entries):
        if generation != self._scan_generation or self._library is None:
            return
        self._scanning = False
        self.scanningChanged.emit()
        untagged = self._library.untagged([e["path"] for e in entries])
        if self._untagged_only:
            left = {path_key(p) for p in untagged}
            entries = [e for e in entries if path_key(e["path"]) in left]
        self._files.set_entries(entries, untagged)

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
        self._selection_rows = [{
            "id": row["tag"].id,
            "name": row["tag"].name,
            "count": row["count"],
            "direct": row["direct"],
            "via": ", ".join(row["via"]),
        } for row in rows]
        self._tags.set_on_selection(rows)

    def _get_selected_count(self):
        return len(self._files.selection.selected) if self._files is not None else 0

    selectedCount = Property(int, _get_selected_count, notify=selectionChanged)

    def _get_selection_tags(self):
        return self._selection_rows

    # [{id, name, count, direct, via}]: the tags on the selection, most common first.
    selectionTags = Property(list, _get_selection_tags, notify=selectionChanged)

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
        tags = self._library.search(text, limit=MAX_RESULTS)
        rows = [{"id": t.id, "name": t.name, "where": self._library.where(t.id), "create": False}
                for t in tags]
        if not rows and text.strip():
            rows = [{"id": -1, "name": " ".join(text.split()), "where": "", "create": True}]
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
        if chosen["create"]:
            return self.createAndApply(text)
        return self._apply(chosen["id"])

    @Slot(str, result=bool)
    def createAndApply(self, text):
        """Shift+Enter: a tag of exactly what was typed."""
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
        """Backspace in an empty box: take the last tag applied off the selection."""
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
        """A click in the tags pane: on every selected file, or else off them all."""
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
        self._counts_timer.start()

    def _refresh_counts(self):
        if self._library is not None:
            self._tags.set_counts(self._library.tag_counts())

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
