"""
The tag library (readme section 44): one SQLite database per machine,
shared by all projects. Pure Python, no Qt.

Design rules:

- Tags belong to a file path. A file gets a row when it's first tagged;
  nothing else in the app needs the library.
- Tags form one tree of groups and tags (44.3). A group only organizes
  the tree and is never on a file. A tag's parent tags are implied by
  it: worked out when read, never stored, so moving a tag updates every
  file at once.
- The whole tree is held in memory, so searching on each key press is
  synchronous and can't return a stale result.
- Tagging has its own session undo, since tags aren't part of the scene.
  Editing the tree isn't undone (deleting asks first): it clears redo,
  and forgets the undo steps of a tag it removes or makes a group.

Use a Library from one thread only (sqlite3 connections are per thread).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from core.media_browser import media_type_for, natural_key
from core.project import write_json_atomic


SCHEMA_VERSION = 1
EXPORT_FORMAT = "mediawall-library"
EXPORT_VERSION = 1

_SCHEMA = f"""
CREATE TABLE tags (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    name_key   TEXT NOT NULL UNIQUE,
    parent_id  INTEGER REFERENCES tags(id),
    is_group   INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    last_used  REAL
);
CREATE TABLE files (
    id          INTEGER PRIMARY KEY,
    path        TEXT NOT NULL,
    path_key    TEXT NOT NULL UNIQUE,
    media_type  TEXT NOT NULL,
    size        INTEGER NOT NULL,
    mtime       REAL NOT NULL,
    fingerprint TEXT
);
CREATE TABLE file_tags (
    file_id  INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    added_at REAL NOT NULL,
    PRIMARY KEY (file_id, tag_id)
) WITHOUT ROWID;
CREATE INDEX file_tags_by_tag ON file_tags(tag_id);
PRAGMA user_version = {SCHEMA_VERSION};
"""

# SQLite allows many more variables than this; it just keeps statements small.
_CHUNK = 500

_FINGERPRINT_CHUNK = 64 * 1024


class LibraryError(Exception):
    """A refused change or an unusable file. The message is shown to the user."""


@dataclass
class Tag:
    id: int
    name: str
    parent_id: int | None = None
    is_group: bool = False
    created_at: float = 0.0
    last_used: float | None = None
    used: int = 0                        # files tagged with this directly


@dataclass
class _Step:
    """One undoable tagging action. Links are (file_id, tag_id, added_at)."""
    tag_id: int
    added: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    created: Tag | None = None           # the tag, if this action created it


def default_library_path():
    """Where this machine's database lives (MEDIAWALL_LIBRARY overrides it)."""
    override = os.environ.get("MEDIAWALL_LIBRARY")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    else:
        base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "Mediawall" / "library.sqlite"


def default_thumbnail_dir():
    """Where thumbnails are cached (MEDIAWALL_THUMBNAILS overrides it)."""
    override = os.environ.get("MEDIAWALL_THUMBNAILS")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(base) / "Mediawall" / "thumbnails"
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "Mediawall" / "thumbnails"


def thumbnail_file(cache_dir, path, size, mtime):
    """
    Where a file's thumbnail is cached. A changed file (other size or
    modification time) gets a new one. In subfolders, as a cache can hold
    more files than one folder handles well.
    """
    name = hashlib.blake2b(f"{path_key(path)}|{size}|{mtime}".encode("utf-8", "surrogatepass"),
                           digest_size=16).hexdigest()
    return Path(cache_dir) / name[:2] / f"{name}.jpg"


def path_key(path):
    """A path's identity: on Windows, a difference in case is the same file."""
    return os.path.normcase(os.path.normpath(str(path)))


def normalized_name(name):
    """A tag's name as stored, or LibraryError if it can't be one."""
    name = " ".join(str(name).split())
    if not name:
        raise LibraryError("A tag needs a name.")
    if name.startswith("-"):
        raise LibraryError('A tag\'s name can\'t start with "-": in Find, that excludes a tag.')
    return name


def _name_key(name):
    return " ".join(str(name).split()).casefold()


def file_fingerprint(path):
    """
    The file's size and a hash of its start, middle, and end: quick on
    large files, and enough to recognize a moved one. None if unreadable.
    """
    try:
        size = os.path.getsize(path)
        digest = hashlib.blake2b(digest_size=16)
        with open(path, "rb") as f:
            for offset in (0, max(0, size // 2 - _FINGERPRINT_CHUNK // 2), max(0, size - _FINGERPRINT_CHUNK)):
                f.seek(offset)
                digest.update(f.read(_FINGERPRINT_CHUNK))
    except OSError:
        return None
    return f"{size}:{digest.hexdigest()}"


def _match_rank(name_key, query):
    """0 exact, 1 start of the name, 2 start of a word, 3 anywhere; None if absent."""
    if name_key == query:
        return 0
    at = name_key.find(query)
    if at < 0:
        return None
    if at == 0:
        return 1
    while at >= 0:
        if not name_key[at - 1].isalnum():
            return 2
        at = name_key.find(query, at + 1)
    return 3


class FileSelection:
    """
    Which rows of a file list are selected (44.1): click, Ctrl+click,
    Shift+click, and stepping. Kept apart from the list's delegates, which
    a grid reuses as it scrolls. `current` is the last row acted on.
    """

    def __init__(self, count=0):
        self.reset(count)

    def reset(self, count):
        """A new list: its first row is selected, so typing can tag straight away."""
        self.count = count
        self.current = 0 if count else -1
        self.anchor = self.current
        self.selected = {0} if count else set()

    def restore(self, count, selected, current):
        """A list changed under the selection: keep these rows, or start over if none are left."""
        selected = {row for row in selected if 0 <= row < count}
        if not selected:
            self.reset(count)
            return
        self.count = count
        self.current = current if current in selected else min(selected)
        self.anchor = self.current
        self.selected = selected

    def click(self, row, ctrl=False, shift=False):
        if not 0 <= row < self.count:
            return
        if shift and self.anchor >= 0:
            span = set(range(min(self.anchor, row), max(self.anchor, row) + 1))
            self.selected = self.selected | span if ctrl else span
        elif ctrl:
            self.selected ^= {row}
            self.anchor = row
        else:
            self.selected = {row}
            self.anchor = row
        self.current = row

    def step(self, delta):
        """Move to the next or previous file, selecting only it. False at either end."""
        row = self.current + delta
        if not 0 <= row < self.count:
            return False
        self.click(row)
        return True

    def select_all(self):
        self.selected = set(range(self.count))


def _chunks(items):
    items = list(items)
    for start in range(0, len(items), _CHUNK):
        yield items[start:start + _CHUNK]


def _marks(items):
    return ",".join("?" * len(items))


class Library:

    def __init__(self, path=":memory:"):
        self.path = path
        self._undo = []
        self._redo = []
        self._db = None
        try:
            if str(path) != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(path))
            self._db.execute("PRAGMA foreign_keys = ON")
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise LibraryError("The tag library was made by a newer version of Mediawall.")
            if version == 0:
                self._db.executescript(_SCHEMA)
            self._load_tags()
        except (LibraryError, OSError, sqlite3.Error) as e:
            if self._db is not None:
                self._db.close()         # or the file stays locked, on Windows
            if isinstance(e, LibraryError):
                raise
            raise LibraryError(f"Can't open the tag library: {e}") from e

    def close(self):
        self._db.close()

    # ---- The tree in memory ----

    def _load_tags(self):
        self._tags = {}
        self._by_key = {}
        self._children = {}
        used = dict(self._db.execute("SELECT tag_id, COUNT(*) FROM file_tags GROUP BY tag_id"))
        rows = self._db.execute("SELECT id, name, parent_id, is_group, created_at, last_used FROM tags")
        for row in rows:
            tag = Tag(row[0], row[1], row[2], bool(row[3]), row[4], row[5], used.get(row[0], 0))
            self._tags[tag.id] = tag
            self._by_key[_name_key(tag.name)] = tag
        for tag in self._tags.values():
            self._children.setdefault(tag.parent_id, []).append(tag)
        for siblings in self._children.values():
            siblings.sort(key=lambda t: natural_key(t.name))

    def tag(self, tag_id):
        return self._tags.get(tag_id)

    def tag_by_name(self, name):
        return self._by_key.get(_name_key(name))

    def _require(self, tag_id):
        tag = self._tags.get(tag_id)
        if tag is None:
            raise LibraryError("That tag no longer exists.")
        return tag

    def tree(self):
        """Every tag and group, depth first, siblings by name: [(tag, depth)]."""
        rows = []

        def walk(parent_id, depth):
            for tag in self._children.get(parent_id, ()):
                rows.append((tag, depth))
                walk(tag.id, depth + 1)

        walk(None, 0)
        return rows

    def ancestors(self, tag_id):
        """Everything above it, nearest first: where it sits in the tree."""
        chain = []
        tag = self._tags.get(tag_id)
        while tag is not None and tag.parent_id is not None:
            tag = self._tags.get(tag.parent_id)
            if tag is not None:
                chain.append(tag)
        return chain

    def implied(self, tag_id):
        """The tags a file with this tag also counts as, nearest first. A group stops it."""
        result = []
        for tag in self.ancestors(tag_id):
            if tag.is_group:
                break
            result.append(tag)
        return result

    def has_children(self, tag_id):
        return bool(self._children.get(tag_id))

    def where(self, tag_id):
        """Where it sits in the tree, from the top: "Location ▸ Massachusetts"."""
        return " ▸ ".join(tag.name for tag in reversed(self.ancestors(tag_id)))

    def descendants(self, tag_id):
        """Everything under it (tags and groups), at any depth."""
        result = []

        def walk(parent_id):
            for tag in self._children.get(parent_id, ()):
                result.append(tag)
                walk(tag.id)

        walk(tag_id)
        return result

    # ---- Searching tags ----

    def search(self, text, include_groups=False, limit=None):
        """
        Tags matching what's been typed, best first (44.2): exact, start
        of the name, start of a word, anywhere; ties go to the most used.
        Groups can't be applied, so they're only results when finding.
        """
        query = _name_key(text)
        if not query:
            return []
        matches = []
        for key, tag in self._by_key.items():
            if tag.is_group and not include_groups:
                continue
            rank = _match_rank(key, query)
            if rank is not None:
                matches.append((rank, -tag.used, -(tag.last_used or 0), natural_key(tag.name), tag.id))
        matches.sort()
        results = [self._tags[m[-1]] for m in matches]
        return results if limit is None else results[:limit]

    # ---- Editing the tree (44.3) ----

    def _check_place(self, tag_is_group, parent_id):
        """A group can hold groups and tags; a tag holds only tags."""
        if parent_id is None:
            return
        parent = self._require(parent_id)
        if tag_is_group and not parent.is_group:
            raise LibraryError(f'A group can\'t go inside the tag "{parent.name}".')

    def _check_name_free(self, name, ignoring=None):
        existing = self._by_key.get(_name_key(name))
        if existing is not None and existing.id != ignoring:
            kind = "group" if existing.is_group else "tag"
            raise LibraryError(f'There is already a {kind} named "{existing.name}".')

    def _tree_changed(self, gone=()):
        """After a tree edit: redo no longer applies, nor undo for a tag in `gone`."""
        self._load_tags()
        self._redo.clear()
        if gone:
            self._undo = [step for step in self._undo if step.tag_id not in gone]

    def _insert_tag(self, name, parent_id, is_group):
        cursor = self._db.execute(
            "INSERT INTO tags (name, name_key, parent_id, is_group, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, _name_key(name), parent_id, int(is_group), time.time()))
        return cursor.lastrowid

    def create_tag(self, name, parent_id=None, is_group=False):
        name = normalized_name(name)
        self._check_name_free(name)
        self._check_place(is_group, parent_id)
        with self._db:
            tag_id = self._insert_tag(name, parent_id, is_group)
        self._tree_changed()
        return self._tags[tag_id]

    def create_group(self, name, parent_id=None):
        return self.create_tag(name, parent_id, is_group=True)

    def rename(self, tag_id, name):
        self._require(tag_id)
        name = normalized_name(name)
        self._check_name_free(name, ignoring=tag_id)
        with self._db:
            self._db.execute("UPDATE tags SET name = ?, name_key = ? WHERE id = ?",
                             (name, _name_key(name), tag_id))
        self._tree_changed()

    def move(self, tag_id, parent_id):
        """Put it under `parent_id` (None for the top level). Refuses loops."""
        tag = self._require(tag_id)
        if parent_id == tag_id or any(t.id == parent_id for t in self.descendants(tag_id)):
            raise LibraryError(f'"{tag.name}" can\'t go inside itself.')
        self._check_place(tag.is_group, parent_id)
        with self._db:
            self._db.execute("UPDATE tags SET parent_id = ? WHERE id = ?", (parent_id, tag_id))
        self._tree_changed()

    def merge(self, source_id, target_id):
        """Every file and child of `source` moves to `target`; `source` is deleted."""
        source = self._require(source_id)
        target = self._require(target_id)
        if source_id == target_id:
            return
        if source.is_group or target.is_group:
            raise LibraryError("Only tags can be merged, not groups.")
        with self._db:
            # Merging a tag into something beneath it: lift that out first,
            # or the children moved below would form a loop with it.
            if any(t.id == source_id for t in self.ancestors(target_id)):
                self._db.execute("UPDATE tags SET parent_id = ? WHERE id = ?", (source.parent_id, target_id))
            self._db.execute("UPDATE tags SET parent_id = ? WHERE parent_id = ? AND id != ?",
                             (target_id, source_id, target_id))
            self._db.execute("""INSERT OR IGNORE INTO file_tags (file_id, tag_id, added_at)
                                SELECT file_id, ?, added_at FROM file_tags WHERE tag_id = ?""",
                             (target_id, source_id))
            self._db.execute("DELETE FROM tags WHERE id = ?", (source_id,))
        self._tree_changed(gone={source_id, target_id})

    def make_group(self, tag_id):
        tag = self._require(tag_id)
        if tag.is_group:
            return
        if tag.used:
            raise LibraryError(f'"{tag.name}" is on {tag.used} file(s), so it can\'t become a group.')
        self._check_place(True, tag.parent_id)
        with self._db:
            self._db.execute("UPDATE tags SET is_group = 1 WHERE id = ?", (tag_id,))
        self._tree_changed(gone={tag_id})

    def make_tag(self, tag_id):
        tag = self._require(tag_id)
        if not tag.is_group:
            return
        if any(child.is_group for child in self._children.get(tag_id, ())):
            raise LibraryError(f'"{tag.name}" holds other groups, so it can\'t become a tag.')
        with self._db:
            self._db.execute("UPDATE tags SET is_group = 0 WHERE id = ?", (tag_id,))
        self._tree_changed()

    def delete(self, tag_id):
        """Delete a tag or group. Whatever it holds moves up a level; files keep their files."""
        tag = self._require(tag_id)
        with self._db:
            self._db.execute("UPDATE tags SET parent_id = ? WHERE parent_id = ?", (tag.parent_id, tag_id))
            self._db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self._tree_changed(gone={tag_id})

    # ---- Tagging files ----

    def _file_ids(self, paths):
        """{path_key: file id} for the paths that have a row."""
        ids = {}
        for chunk in _chunks({path_key(p) for p in paths}):
            rows = self._db.execute(f"SELECT path_key, id FROM files WHERE path_key IN ({_marks(chunk)})", chunk)
            ids.update(rows)
        return ids

    def _ensure_files(self, paths):
        """File ids for `paths`, adding rows for new ones. A file that isn't there is left out."""
        by_key = {path_key(p): p for p in paths}
        ids = self._file_ids(by_key.values())
        for key, path in by_key.items():
            if key in ids:
                continue
            media_type = media_type_for(path)
            try:
                st = os.stat(path)
            except OSError:
                continue
            if media_type is None or not stat.S_ISREG(st.st_mode):
                continue
            cursor = self._db.execute(
                "INSERT INTO files (path, path_key, media_type, size, mtime, fingerprint) VALUES (?, ?, ?, ?, ?, ?)",
                (str(path), key, media_type, st.st_size, st.st_mtime, file_fingerprint(path)))
            ids[key] = cursor.lastrowid
        return list(ids.values())

    def _links_of(self, tag_id, file_ids):
        """{file_id: added_at} for the files in `file_ids` that have this tag directly."""
        links = {}
        for chunk in _chunks(file_ids):
            links.update(self._db.execute(
                f"SELECT file_id, added_at FROM file_tags WHERE tag_id = ? AND file_id IN ({_marks(chunk)})",
                [tag_id] + chunk))
        return links

    def _add_links(self, tag, paths):
        """Tag the files, inside a transaction. Returns the links actually added."""
        file_ids = self._ensure_files(paths)
        had = self._links_of(tag.id, file_ids)
        now = time.time()
        added = [(file_id, tag.id, now) for file_id in file_ids if file_id not in had]
        self._db.executemany("INSERT INTO file_tags (file_id, tag_id, added_at) VALUES (?, ?, ?)", added)
        if added:
            self._db.execute("UPDATE tags SET last_used = ? WHERE id = ?", (now, tag.id))
        return added

    def _record(self, step):
        if step.added or step.removed or step.created:
            self._undo.append(step)
            self._redo.clear()

    def apply_tag(self, tag_id, paths):
        """Tag every file in `paths` (one undo step). Returns how many changed."""
        tag = self._require(tag_id)
        if tag.is_group:
            raise LibraryError(f'"{tag.name}" is a group, so it can\'t be put on a file.')
        with self._db:
            added = self._add_links(tag, paths)
        if added:
            tag.used += len(added)
            tag.last_used = added[0][2]
        self._record(_Step(tag_id, added=added))
        return len(added)

    def create_and_apply(self, name, paths):
        """
        Shift+Enter: a new top-level tag from this name, applied to the
        files. One undo step, which removes the tag too. A name that
        exists just applies that tag, and a group's name is refused.
        """
        existing = self.tag_by_name(name)
        if existing is not None:
            self.apply_tag(existing.id, paths)
            return existing
        name = normalized_name(name)
        with self._db:
            tag_id = self._insert_tag(name, None, False)
            added = self._add_links(Tag(tag_id, name), paths)
        self._tree_changed()
        self._record(_Step(tag_id, added=added, created=self._tags[tag_id]))
        return self._tags[tag_id]

    def remove_tag(self, tag_id, paths):
        """
        Take this tag off the files (one undo step). Only a tag put on
        directly can be: an implied one goes when the tag implying it does.
        """
        tag = self._require(tag_id)
        file_ids = list(self._file_ids(paths).values())
        links = self._links_of(tag_id, file_ids)
        removed = [(file_id, tag_id, added_at) for file_id, added_at in links.items()]
        with self._db:
            self._db.executemany("DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?",
                                 [link[:2] for link in removed])
        tag.used -= len(removed)
        self._record(_Step(tag_id, removed=removed))
        return len(removed)

    # ---- Undo and redo of tagging ----

    def _insert_links(self, links):
        self._db.executemany("INSERT OR IGNORE INTO file_tags (file_id, tag_id, added_at) VALUES (?, ?, ?)", links)

    def _delete_links(self, links):
        self._db.executemany("DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?", [l[:2] for l in links])

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo(self):
        if not self._undo:
            return False
        step = self._undo.pop()
        with self._db:
            self._delete_links(step.added)
            self._insert_links(step.removed)
            if step.created is not None:
                # Gone with its action, unless it has come into use since.
                current = self._tags.get(step.tag_id)
                step.created = replace(current, used=0)
                if not self._children.get(step.tag_id) and not self._db.execute(
                        "SELECT 1 FROM file_tags WHERE tag_id = ? LIMIT 1", (step.tag_id,)).fetchone():
                    self._db.execute("DELETE FROM tags WHERE id = ?", (step.tag_id,))
        self._load_tags()
        self._redo.append(step)
        return True

    def redo(self):
        if not self._redo:
            return False
        step = self._redo.pop()
        with self._db:
            if step.created is not None and step.tag_id not in self._tags:
                tag = step.created
                self._db.execute(
                    """INSERT INTO tags (id, name, name_key, parent_id, is_group, created_at, last_used)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (tag.id, tag.name, _name_key(tag.name), tag.parent_id, int(tag.is_group),
                     tag.created_at, tag.last_used))
            self._insert_links(step.added)
            self._delete_links(step.removed)
        self._load_tags()
        self._undo.append(step)
        return True

    # ---- Reading a file's tags ----

    def _direct_tags_by_file(self, file_ids=None):
        """{file_id: [tag ids put on directly]}, for these files or all of them."""
        result = {}
        if file_ids is None:
            for file_id, tag_id in self._db.execute("SELECT file_id, tag_id FROM file_tags"):
                result.setdefault(file_id, []).append(tag_id)
            return result
        for chunk in _chunks(file_ids):
            rows = self._db.execute(f"SELECT file_id, tag_id FROM file_tags WHERE file_id IN ({_marks(chunk)})", chunk)
            for file_id, tag_id in rows:
                result.setdefault(file_id, []).append(tag_id)
        return result

    def selection_tags(self, paths):
        """
        The tags on these files, for the tags pane: most common first, as
        {"tag", "count" (files counting as it), "direct" (files tagged
        with it directly), "via" (names of the tags implying it)}.
        """
        file_ids = list(self._file_ids(paths).values())
        rows = {}

        def row(tag):
            return rows.setdefault(tag.id, {"tag": tag, "count": 0, "direct": 0, "via": set()})

        for direct in self._direct_tags_by_file(file_ids).values():
            counted = set()
            for tag_id in direct:
                tag = self._tags[tag_id]
                row(tag)["direct"] += 1
                counted.add(tag_id)
                for above in self.implied(tag_id):
                    row(above)["via"].add(tag.name)
                    counted.add(above.id)
            for tag_id in counted:
                row(self._tags[tag_id])["count"] += 1

        for entry in rows.values():
            entry["via"] = sorted(entry["via"], key=natural_key)
        return sorted(rows.values(), key=lambda e: (-e["count"], natural_key(e["tag"].name)))

    def tag_counts(self, file_ids=None):
        """{tag id: files counting as it}, among these files or all of them."""
        counts = {}
        implied = {}                     # worked out once per tag
        for direct in self._direct_tags_by_file(file_ids).values():
            counted = set(direct)
            for tag_id in direct:
                if tag_id not in implied:
                    implied[tag_id] = [t.id for t in self.implied(tag_id)]
                counted.update(implied[tag_id])
            for tag_id in counted:
                counts[tag_id] = counts.get(tag_id, 0) + 1
        return counts

    def untagged(self, paths):
        """The paths with no tags at all, in their given order."""
        paths = list(paths)
        tagged = set()
        for chunk in _chunks({path_key(p) for p in paths}):
            tagged.update(key for (key,) in self._db.execute(
                f"""SELECT path_key FROM files WHERE path_key IN ({_marks(chunk)})
                    AND EXISTS (SELECT 1 FROM file_tags WHERE file_id = files.id)""", chunk))
        return [p for p in paths if path_key(p) not in tagged]

    # ---- Finding files (44.5) ----

    def _matching_ids(self, tag_id):
        """A tag or group and everything under it: what finding it matches."""
        return [tag_id] + [t.id for t in self.descendants(tag_id)]

    def find(self, include=(), exclude=(), folder=None, recursive=True):
        """
        Tagged files, as dicts: each tag in `include` must match (itself
        or anything under it), none in `exclude` may. With nothing
        included, every tagged file. `folder` limits it to one folder.
        Ordered by path. Whether a file is still there is the caller's
        to check, since asking the disk per file can be slow.
        """
        # IN (SELECT ...) builds each tag's set of files once, from the index
        # by tag. A correlated EXISTS would try every tag of a big subtree
        # for every file: 24 s, against milliseconds, on 100,000 files.
        sql = ["SELECT id, path, media_type, size, mtime, path_key FROM files WHERE"
               " id IN (SELECT file_id FROM file_tags)"]
        values = []
        for negate, tag_ids in [("", include), ("NOT ", exclude)]:
            for tag_id in tag_ids:
                ids = self._matching_ids(tag_id)
                sql.append(f"AND id {negate}IN (SELECT file_id FROM file_tags WHERE tag_id IN ({_marks(ids)}))")
                values += ids
        prefix = None
        if folder is not None:
            prefix = path_key(folder)
            inside = prefix.rstrip("/\\") + os.sep
            sql.append("AND substr(path_key, 1, ?) = ?")
            values += [len(inside), inside]
        sql.append("ORDER BY path_key")
        rows = self._db.execute(" ".join(sql), values)
        return [{"id": r[0], "path": r[1], "type": r[2], "size": r[3], "mtime": r[4]} for r in rows
                if recursive or prefix is None or os.path.dirname(r[5]) == prefix]

    # ---- Export and import (44.6) ----

    def export_json(self, path, include_files=True):
        """Export Everything, or (include_files=False) Export Tags Only. Written atomically."""
        data = {
            "format": EXPORT_FORMAT,
            "version": EXPORT_VERSION,
            "tags": [{"name": tag.name,
                      "parent": self._tags[tag.parent_id].name if tag.parent_id is not None else None,
                      "is_group": tag.is_group}
                     for tag, _depth in self.tree()],
        }
        if include_files:
            direct = self._direct_tags_by_file()
            rows = self._db.execute("SELECT id, path, size, mtime, fingerprint FROM files ORDER BY path_key")
            data["files"] = [{"path": r[1], "size": r[2], "mtime": r[3], "fingerprint": r[4],
                              "tags": sorted((self._tags[t].name for t in direct[r[0]]), key=natural_key)}
                             for r in rows if r[0] in direct]
        write_json_atomic(path, data)

    def import_json(self, path):
        """
        Merge an export by tag name; nothing is deleted, and a tag that
        already exists stays where it is. Tolerant like opening a project:
        bad entries become warnings, and only an unreadable file fails.
        Returns {"tags", "files", "links": how many were added, "warnings"}.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            raise LibraryError(f"Can't read that file: {e}") from e
        if not isinstance(data, dict) or data.get("format") != EXPORT_FORMAT:
            raise LibraryError("That file isn't a Mediawall tag library export.")
        if not isinstance(data.get("version"), int) or data["version"] > EXPORT_VERSION:
            raise LibraryError("That file was made by a newer version of Mediawall.")

        report = {"tags": 0, "files": 0, "links": 0, "warnings": []}
        with self._db:
            known = {key: (tag.id, tag.is_group) for key, tag in self._by_key.items()}
            self._import_tags(data.get("tags"), known, report)
            self._import_files(data.get("files"), known, report)
        self._tree_changed()
        return report

    def _import_tags(self, entries, known, report):
        warn = report["warnings"].append
        pending = []
        for entry in entries if isinstance(entries, list) else []:
            try:
                name = normalized_name(entry["name"])
                parent = entry.get("parent")
                parent = None if parent is None else normalized_name(parent)
                pending.append((name, parent, entry.get("is_group") is True))
            except (LibraryError, KeyError, TypeError, AttributeError) as e:
                warn(f"Skipped a tag entry: {e}")

        def add(name, parent_id, is_group):
            known[_name_key(name)] = (self._insert_tag(name, parent_id, is_group), is_group)
            report["tags"] += 1

        # Parents first, whatever order the file has them in.
        while pending:
            waiting = []
            for name, parent, is_group in pending:
                if _name_key(name) in known:
                    if known[_name_key(name)][1] != is_group:
                        warn(f'"{name}" is already here as a different kind; kept as it is.')
                elif parent is None:
                    add(name, None, is_group)
                elif _name_key(parent) not in known:
                    waiting.append((name, parent, is_group))
                elif is_group and not known[_name_key(parent)][1]:
                    warn(f'The group "{name}" can\'t go inside the tag "{parent}"; put at the top level.')
                    add(name, None, is_group)
                else:
                    add(name, known[_name_key(parent)][0], is_group)
            if len(waiting) == len(pending):     # a loop, or a parent that isn't in the file
                for name, parent, is_group in waiting:
                    warn(f'"{name}" has no usable parent "{parent}"; put at the top level.')
                    add(name, None, is_group)
                waiting = []
            pending = waiting

    def _import_files(self, entries, known, report):
        warn = report["warnings"].append
        now = time.time()
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                warn("Skipped a file entry without a path.")
                continue
            path = entry["path"]
            media_type = media_type_for(path)
            if media_type is None:
                warn(f"Skipped {path}: not a supported media file.")
                continue
            key = path_key(path)
            row = self._db.execute("SELECT id FROM files WHERE path_key = ?", (key,)).fetchone()
            if row is not None:
                file_id = row[0]
            else:
                size = entry.get("size")
                mtime = entry.get("mtime")
                fingerprint = entry.get("fingerprint")
                # A path that doesn't exist here is fine: it counts as a
                # missing file, which the fingerprint can reattach later.
                file_id = self._db.execute(
                    "INSERT INTO files (path, path_key, media_type, size, mtime, fingerprint) VALUES (?, ?, ?, ?, ?, ?)",
                    (path, key, media_type,
                     size if type(size) is int else 0,
                     mtime if type(mtime) in (int, float) else 0.0,
                     fingerprint if isinstance(fingerprint, str) else None)).lastrowid
                report["files"] += 1
            tags = entry.get("tags")
            for name in tags if isinstance(tags, list) else []:
                tag = known.get(_name_key(name)) if isinstance(name, str) else None
                if tag is None or tag[1]:
                    warn(f"Skipped the tag {name!r} on {path}: no such tag here.")
                    continue
                cursor = self._db.execute(
                    "INSERT OR IGNORE INTO file_tags (file_id, tag_id, added_at) VALUES (?, ?, ?)",
                    (file_id, tag[0], now))
                report["links"] += cursor.rowcount
