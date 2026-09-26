import os
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


def natural_key(text):
    """Sort "IMG_2" before "IMG_10", case-insensitively."""
    return [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", text.lower())
    ]


def _entry(file_path, root):
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
    }


def _sort_key(entry):
    # Files directly in the chosen folder come first, then each
    # subfolder in order (depth-first), files naturally sorted within.
    parts = entry["relpath"].split("/")
    return ([natural_key(p) for p in parts[:-1]], natural_key(parts[-1]))


class MediaBrowser:

    def scan_folder(self, folder, recursive=False):
        """
        Return supported media files in a folder as a list of dicts:

            {
                "path":    absolute filesystem path,
                "url":     encoded file:// URL for QML,
                "name":    file name,
                "relpath": path relative to the chosen folder,
                "type":    "image" | "video" | "audio",
                "animatable": True for GIF/WebP
            }

        With recursive=True, subfolders are included. Hidden folders
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

        entries.sort(key=_sort_key)
        return entries
