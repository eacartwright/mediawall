"""
The recently opened projects list (Open Recent): newest first, no
duplicates, at most MAX_RECENT. Stored by bridge/app_settings.py.
"""

import os

MAX_RECENT = 10


def _same_file(a, b):
    # Windows paths are case-insensitive; Linux paths are not.
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def with_recent(paths, path, limit=MAX_RECENT):
    """`paths` with `path` moved (or added) to the front."""
    rest = [p for p in paths if not _same_file(p, path)]
    return [path] + rest[:limit - 1]


def without_recent(paths, path):
    return [p for p in paths if not _same_file(p, path)]
