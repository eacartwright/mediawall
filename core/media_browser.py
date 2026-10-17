import os
import random
import re
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".3gp"}
AUDIO_EXTENSIONS = {".mp3", ".m4a"}

# Image formats that may contain animation. Displayed with an animated
# image element; a static file in one of these formats still just shows
# as a still image.
ANIMATABLE_EXTENSIONS = {".gif", ".webp"}


def media_type_for(path):
    """Return "image", "video", "audio", or None for unsupported files."""
    suffix = Path(path).suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    return None


def is_animatable(path):
    """True if the file's format can contain animation (GIF, WebP)."""
    return Path(path).suffix.lower() in ANIMATABLE_EXTENSIONS


# ---- Is it actually animated? (the "Animated Only" filter) ----
# GIF and WebP files can be animated or still. Telling them apart means
# reading the file: a GIF is animated if it holds more than one frame,
# a WebP if its header sets the animation flag. Results are cached by
# path, size, and modification time, so a rescan doesn't read again.

_animated_cache = {}


def _gif_frames_over_one(f):
    """Walk a GIF's blocks; True as soon as a second frame appears."""
    header = f.read(13)                  # signature + logical screen descriptor
    if len(header) < 13 or header[:3] != b"GIF":
        return False
    if header[10] & 0x80:                # global color table
        f.seek(3 * (2 << (header[10] & 7)), 1)

    def skip_sub_blocks():
        while True:
            size = f.read(1)
            if not size or size[0] == 0:
                return
            f.seek(size[0], 1)

    frames = 0
    while True:
        block = f.read(1)
        if not block:
            return False
        if block[0] == 0x2C:             # image descriptor: a frame
            frames += 1
            if frames > 1:
                return True
            desc = f.read(9)
            if len(desc) < 9:
                return False
            if desc[8] & 0x80:           # local color table
                f.seek(3 * (2 << (desc[8] & 7)), 1)
            f.read(1)                    # LZW minimum code size
            skip_sub_blocks()
        elif block[0] == 0x21:           # extension: label, then sub-blocks
            f.read(1)
            skip_sub_blocks()
        else:                            # trailer (0x3B), or damaged
            return False


def _webp_animated(f):
    header = f.read(21)
    # RIFF....WEBP, then an extended-format (VP8X) chunk whose flags
    # byte has the animation bit.
    return (len(header) == 21 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
            and header[12:16] == b"VP8X" and bool(header[20] & 0x02))


def is_animated(path):
    """True if a GIF or WebP file really is animated (more than one frame)."""
    suffix = Path(path).suffix.lower()
    if suffix not in ANIMATABLE_EXTENSIONS:
        return False
    try:
        st = os.stat(path)
    except OSError:
        return False
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key in _animated_cache:
        return _animated_cache[key]
    try:
        with open(path, "rb") as f:
            result = _gif_frames_over_one(f) if suffix == ".gif" else _webp_animated(f)
    except OSError:
        result = False
    _animated_cache[key] = result
    return result


def matches_filter(entry, media_filter, favorites=()):
    """
    True if a scanned entry passes a browser or container's filter:
    "all", a type ("image", "video", "audio"), "animated" (animated
    GIF/WebP only), or "favorites" (its path is in `favorites`).
    """
    if media_filter in ("all", "", None):
        return True
    if media_filter == "favorites":
        return entry["path"] in favorites
    if media_filter == "animated":
        return entry["animatable"] and is_animated(entry["path"])
    return entry["type"] == media_filter


def natural_key(text):
    """Sort "IMG_2" before "IMG_10", case-insensitively."""
    return [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", text.lower())
    ]


def _stat(file_path):
    """(modification time, size), or (0.0, 0) if unreadable."""
    try:
        st = file_path.stat()
        return st.st_mtime, st.st_size
    except OSError:
        return 0.0, 0


def _entry(file_path, root):
    mtime, size = _stat(file_path)
    return {
        "path": str(file_path),
        # as_uri() percent-encodes #, ?, %, spaces, and handles
        # Windows drive letters (file:///C:/...).
        "url": file_path.as_uri(),
        "name": file_path.name,
        # Path relative to the chosen folder, always with "/",
        # e.g. "Japan/Kyoto/IMG_001.jpg". Shown in the browser.
        "relpath": file_path.relative_to(root).as_posix(),
        "type": media_type_for(file_path),
        "animatable": is_animatable(file_path),
        "mtime": mtime,
        # 0 while a download is still being written (e.g. Firefox's
        # placeholder beside its .part file).
        "size": size,
    }


def _sort_key(entry):
    # Files directly in the chosen folder come first, then each
    # subfolder in order (depth-first), files naturally sorted within.
    parts = entry["relpath"].split("/")
    return ([natural_key(p) for p in parts[:-1]], natural_key(parts[-1]))


# Grouped this way by "type": images (still, then animated), videos, audio.
_TYPE_ORDER = {"image": 0, "video": 1, "audio": 2}


def sort_entries(entries, sort_by="name", descending=False, seed=""):
    """
    Put scanned entries in a browser or container's order (SORT_KEYS in
    core/scene.py): "name" (natural, folder by folder), "date" (modified),
    "type" (then extension, then name), or "random". The random order is
    fixed by `seed` (the object's id), so stepping back and forth and
    rescanning keep the same order; descending doesn't apply to it.
    """
    entries = sorted(entries, key=_sort_key)
    if sort_by == "random":
        random.Random(seed).shuffle(entries)
        return entries
    if sort_by == "date":
        entries.sort(key=lambda e: e["mtime"])          # stable: ties by name
    elif sort_by == "type":
        entries.sort(key=lambda e: (_TYPE_ORDER.get(e["type"], 3), e["animatable"],
                                    Path(e["name"]).suffix.lower()))
    if descending:
        entries.reverse()
    return entries


class MediaBrowser:

    def scan_folder(self, folder, recursive=False, media_filter="all",
                    sort_by="name", descending=False, seed="", favorites=()):
        """
        Return supported media files in a folder as a list of dicts:

            {
                "path":    absolute filesystem path,
                "url":     encoded file:// URL for QML,
                "name":    file name,
                "relpath": path relative to the chosen folder,
                "type":    "image" | "video" | "audio",
                "animatable": True for GIF/WebP,
                "mtime":   modification time (seconds),
                "size":    size in bytes
            }

        With recursive=True, subfolders are included. media_filter keeps
        only matching files (matches_filter; "favorites" keeps the paths
        in `favorites`); sort_by, descending, and seed
        set the order (sort_entries). Hidden folders
        (names starting with ".") are skipped, symlinked folders are
        not followed (avoids loops), and unreadable folders are skipped
        rather than failing the whole scan.
        """

        if not folder:
            return []

        root = Path(folder).expanduser().resolve()

        if not root.is_dir():
            return []

        entries = []

        if recursive:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

                for filename in filenames:
                    file_path = Path(dirpath) / filename
                    if media_type_for(file_path) is not None:
                        entries.append(_entry(file_path, root))
        else:
            try:
                items = list(root.iterdir())
            except OSError:
                return []

            for item in items:
                try:
                    if not item.is_file():
                        continue
                except OSError:
                    continue

                if media_type_for(item) is not None:
                    entries.append(_entry(item, root))

        favorites = set(favorites or ())
        entries = [e for e in entries if matches_filter(e, media_filter, favorites)]
        return sort_entries(entries, sort_by, descending, seed)
