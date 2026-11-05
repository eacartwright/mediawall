import os
import random
import re
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".3gp"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav"}

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


def file_patterns(media_type=None):
    """
    Glob patterns ("*.jpg", "*.JPG", ...) for a file dialog: every
    supported file, or one media type's. Upper case too, since file
    dialogs on Linux match case-sensitively.
    """
    extensions = {
        "image": IMAGE_EXTENSIONS,
        "video": VIDEO_EXTENSIONS,
        "audio": AUDIO_EXTENSIONS,
    }.get(media_type) or IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
    return [f"*{e}" for e in sorted(extensions)] + [f"*{e.upper()}" for e in sorted(extensions)]


def neighbour_file(path, delta):
    """
    The file `delta` steps from `path` in its folder (not subfolders),
    among files of the same type, by name, going round at either end:
    an audio track's Continue Play and previous/next. The path itself if
    it's the only one; None if the folder has none (or is gone). A file
    no longer there counts from the start.
    """
    media_type = media_type_for(path)
    folder = Path(path).parent
    if media_type is None or not folder.is_dir():
        return None
    files = [e["path"] for e in MediaBrowser().scan_folder(str(folder), False, media_type)]
    if not files:
        return None
    here = os.path.normcase(os.path.normpath(str(path)))
    names = [os.path.normcase(os.path.normpath(p)) for p in files]
    if here in names:
        return files[(names.index(here) + delta) % len(files)]
    return files[0 if delta > 0 else -1]


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


# ---- How long is it? (shown on the Library's tiles) ----
# Read from the file's own frame timings, so nothing needs decoding.

def _gif_duration_ms(f):
    header = f.read(13)
    if len(header) < 13 or header[:3] != b"GIF":
        return 0
    if header[10] & 0x80:                # global color table
        f.seek(3 * (2 << (header[10] & 7)), 1)

    def skip_sub_blocks():
        while True:
            size = f.read(1)
            if not size or size[0] == 0:
                return
            f.seek(size[0], 1)

    total = 0
    while True:
        block = f.read(1)
        if not block or block[0] == 0x3B:
            return total
        if block[0] == 0x2C:             # a frame
            desc = f.read(9)
            if len(desc) < 9:
                return total
            if desc[8] & 0x80:           # local color table
                f.seek(3 * (2 << (desc[8] & 7)), 1)
            f.read(1)                    # LZW minimum code size
            skip_sub_blocks()
        elif block[0] == 0x21:           # extension: label, then sub-blocks
            label = f.read(1)
            if label == b"\xF9":         # graphic control: a frame's delay
                data = f.read(5)
                if len(data) == 5:
                    delay = int.from_bytes(data[2:4], "little") * 10
                    # Too short to be meant: players show these at 100 ms.
                    total += delay if delay >= 20 else 100
            skip_sub_blocks()
        else:
            return total


def _webp_duration_ms(f):
    if f.read(4) != b"RIFF":
        return 0
    f.read(4)
    if f.read(4) != b"WEBP":
        return 0
    total = 0
    while True:
        chunk = f.read(8)
        if len(chunk) < 8:
            return total
        size = int.from_bytes(chunk[4:], "little")
        if chunk[:4] == b"ANMF":         # a frame: position, size, then duration
            data = f.read(15)
            if len(data) < 15:
                return total
            total += int.from_bytes(data[12:15], "little")
            f.seek(size - 15, 1)
        else:
            f.seek(size, 1)
        if size % 2:                     # chunks are padded to even sizes
            f.seek(1, 1)


def animation_duration_ms(path):
    """One loop of an animated GIF or WebP, in ms: 0 if it isn't one or can't be read."""
    suffix = Path(path).suffix.lower()
    if suffix not in ANIMATABLE_EXTENSIONS:
        return 0
    try:
        with open(path, "rb") as f:
            return _gif_duration_ms(f) if suffix == ".gif" else _webp_duration_ms(f)
    except OSError:
        return 0


def format_duration(ms):
    """"0:04", "1:30", "1:02:03". A blank for no length; anything shorter than a second is 0:01."""
    if ms <= 0:
        return ""
    seconds = max(1, (int(ms) + 500) // 1000)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


def matches_filter(entry, media_filter, favorites=()):
    """
    True if a scanned entry passes a browser or container's filter:
    "all", a type ("image", "video", "audio"), "animated" (everything
    that moves: video and animated GIF/WebP), or "favorites" (its path
    is in `favorites`).
    """
    if media_filter in ("all", "", None):
        return True
    if media_filter == "favorites":
        return entry["path"] in favorites
    if media_filter == "animated":
        return entry["type"] == "video" or (entry["animatable"] and is_animated(entry["path"]))
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
