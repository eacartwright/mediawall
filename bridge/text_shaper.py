"""
The outlines of a text object's letters ("WordArt"; readme section 5.4),
for qml/TextArt.qml to draw as one vector path.

Qt's font engine turns the words into glyph outlines (QPainterPath
.addText); this module then wraps them onto lines, bends them onto an
arc, and tilts them in perspective by moving the outline's points, so
the result stays a sharp vector shape at any size. It returns the path
as SVG path data (for QML's PathSvg) with its bounds.

Emoji are left out of the outline: colour emoji fonts (Noto Color Emoji
on Linux) are pictures with no outline at all, and where a font has one
(Segoe UI Emoji on Windows) it would come out in one colour. Instead
each emoji's place, size, and angle (following the arc and tilt) is
returned, and TextArt draws it in colour as ordinary text there.

Everything is laid out with the font 100 px tall (TextArt's base size);
TextArt scales the result to the box.
"""

import math
from functools import lru_cache

from PySide6.QtCore import QObject, QPointF, QRectF, QTextBoundaryFinder, Slot
from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath


BASE_PIXEL_SIZE = 100

# An emoji's size, and the room it takes on its line, as fractions of
# the font size. A fixed advance (rather than the emoji font's own)
# spaces them the same on every system.
EMOJI_SIZE = 0.85
EMOJI_ADVANCE = 0.95

# Straight edges and curves are cut into pieces at most this long (in
# base units) before an arc or tilt moves their points, so they bend
# smoothly instead of staying straight between far-apart points.
MAX_SEGMENT = 8.0


# ---- Emoji ----

# Symbols below U+1F000 that show as emoji even without U+FE0F (Unicode
# Emoji_Presentation). Other symbols there (★ ✓ ♥ →) are ordinary text,
# drawn in the text's style, unless followed by U+FE0F.
_EMOJI_PRESENTATION = set(
    [0x231A, 0x231B, 0x23E9, 0x23EA, 0x23EB, 0x23EC, 0x23F0, 0x23F3, 0x25FD, 0x25FE,
     0x2614, 0x2615, 0x267F, 0x2693, 0x26A1, 0x26AA, 0x26AB, 0x26BD, 0x26BE, 0x26C4,
     0x26C5, 0x26CE, 0x26D4, 0x26EA, 0x26F2, 0x26F3, 0x26F5, 0x26FA, 0x26FD, 0x2705,
     0x270A, 0x270B, 0x2728, 0x274C, 0x274E, 0x2753, 0x2754, 0x2755, 0x2757, 0x2795,
     0x2796, 0x2797, 0x27B0, 0x27BF, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55]
    + list(range(0x2648, 0x2654)))              # zodiac signs


def _is_emoji_char(code):
    return 0x1F000 <= code <= 0x1FAFF or code in _EMOJI_PRESENTATION


def split_emoji(text):
    """
    `text` as (piece, is_emoji) runs, emoji split per grapheme (one
    emoji, with its skin tone, ZWJ family, or flag pair, is one piece).
    """
    finder = QTextBoundaryFinder(QTextBoundaryFinder.Grapheme, text)
    runs = []
    start = 0
    # Positions are in UTF-16 units; walk them alongside the Python string.
    utf16 = text.encode("utf-16-le")
    while True:
        end = finder.toNextBoundary()
        if end < 0:
            break
        piece = utf16[start * 2:end * 2].decode("utf-16-le")
        start = end
        emoji = any(_is_emoji_char(ord(ch)) for ch in piece) or "️" in piece
        if runs and runs[-1][1] == emoji and not emoji:
            runs[-1] = (runs[-1][0] + piece, False)
        elif emoji and runs and _is_flag_half(runs[-1][0]) and _is_flag_half(piece):
            runs[-1] = (runs[-1][0] + piece, True)       # a flag: two letters
        else:
            runs.append((piece, emoji))
    return runs


def text_advance(metrics, text):
    """The width of `text`, with each emoji EMOJI_ADVANCE wide."""
    return sum(EMOJI_ADVANCE * BASE_PIXEL_SIZE if is_emoji else metrics.horizontalAdvance(piece)
               for piece, is_emoji in split_emoji(text))


def _is_flag_half(piece):
    """One regional indicator letter (two make a flag)."""
    return len(piece) == 1 and 0x1F1E6 <= ord(piece) <= 0x1F1FF


def wrap_lines(text, advance, width):
    """
    Break text onto lines no wider than `width`, at spaces; a word too
    long for a line is broken between letters. `advance(s)` is the
    width of a string. width <= 0: one line.
    """
    if width <= 0 or advance(text) <= width:
        return [text]

    lines = []
    line = ""
    for word in text.split(" "):
        candidate = word if line == "" else line + " " + word
        if advance(candidate) <= width:
            line = candidate
            continue
        if line != "":
            lines.append(line)
        # The word starts a line; if it alone is too wide, break it.
        line = ""
        for ch in word:
            if line != "" and advance(line + ch) > width:
                lines.append(line)
                line = ""
            line += ch
    lines.append(line)
    return lines


# ---- Bending and tilting ----

def _arc_mapper(arc_degrees, cx, cy, span):
    """
    Bend a line `span` wide, centered at (cx, cy), so it covers
    arc_degrees of a circle: > 0 arches up (the ends go down), < 0
    sags (the ends go up).
    """
    angle = math.radians(abs(arc_degrees))
    radius = span / angle
    up = arc_degrees > 0

    def warp(x, y):
        theta = (x - cx) / radius
        d = cy - y                       # height above the middle line
        if up:
            r = max(0.0, radius + d)
            return cx + r * math.sin(theta), cy + radius - r * math.cos(theta)
        r = max(0.0, radius - d)
        return cx + r * math.sin(theta), cy - radius + r * math.cos(theta)

    return warp


def _tilt_mapper(tilt_degrees, cx, cy, height):
    """
    Lean the text about its horizontal middle line, seen in perspective:
    > 0 tips the top away from the viewer.
    """
    t = math.radians(tilt_degrees)
    distance = 3.0 * max(height, 1.0)   # eye distance: a clear, WordArt-like taper
    cos_t, sin_t = math.cos(t), math.sin(t)

    def warp(x, y):
        dy = y - cy
        z = -dy * sin_t                  # > 0: farther away
        s = distance / max(distance + z, 1e-3)
        return cx + (x - cx) * s, cy + dy * cos_t * s

    return warp


def _split_cubic(p0, p1, p2, p3):
    """de Casteljau at t = 0.5: two cubics."""
    def mid(a, b):
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    a, b, c = mid(p0, p1), mid(p1, p2), mid(p2, p3)
    d, e = mid(a, b), mid(b, c)
    f = mid(d, e)
    return (p0, a, d, f), (f, e, c, p3)


def _length(*points):
    return sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def _subpaths(path):
    """
    A QPainterPath's outline as a list of closed subpaths, each a list of
    segments: ("L", end) or ("C", c1, c2, end), after a start point.
    """
    result = []
    i, n = 0, path.elementCount()
    while i < n:
        e = path.elementAt(i)
        if e.isMoveTo():
            result.append([(e.x, e.y)])
            i += 1
        elif e.isLineTo():
            result[-1].append(("L", (e.x, e.y)))
            i += 1
        else:                            # a curve: this and the next two elements
            c2 = path.elementAt(i + 1)
            end = path.elementAt(i + 2)
            result[-1].append(("C", (e.x, e.y), (c2.x, c2.y), (end.x, end.y)))
            i += 3
    return result


def _fine_segments(start, segments):
    """Cut segments to at most MAX_SEGMENT long (only needed before a warp)."""
    out = []
    pos = start
    for seg in segments:
        if seg[0] == "L":
            end = seg[1]
            pieces = max(1, math.ceil(math.dist(pos, end) / MAX_SEGMENT))
            for k in range(1, pieces + 1):
                t = k / pieces
                out.append(("L", (pos[0] + (end[0] - pos[0]) * t,
                                  pos[1] + (end[1] - pos[1]) * t)))
        else:
            stack = [(pos, seg[1], seg[2], seg[3])]
            while stack:
                cubic = stack.pop()
                if _length(*cubic) > MAX_SEGMENT * 1.5:
                    first, second = _split_cubic(*cubic)
                    stack.append(second)
                    stack.append(first)
                else:
                    out.append(("C", cubic[1], cubic[2], cubic[3]))
        pos = seg[-1]
    return out


@lru_cache(maxsize=256)
def shape_text(text, family, bold, italic, wrap_width, align, arc, tilt):
    """
    The outline of `text` as SVG path data and its bounds:
    {"path", "x", "y", "width", "height", "lines"}. With wrap_width > 0
    the lines are wrapped to it and aligned within it ("left", "center",
    "right"); otherwise there is one line.
    """
    font = QFont(family)
    font.setPixelSize(BASE_PIXEL_SIZE)
    font.setBold(bold)
    font.setItalic(italic)
    font.setHintingPreference(QFont.PreferNoHinting)
    metrics = QFontMetricsF(font)

    def advance(s):
        return text_advance(metrics, s)

    lines = wrap_lines(text, advance, wrap_width)
    layout_width = wrap_width if wrap_width > 0 else max(
        (advance(line) for line in lines), default=0.0)

    path = QPainterPath()
    emoji = []                   # [text, center x, center y, size] before warping
    bounds = QRectF()
    baseline = metrics.ascent()
    for line in lines:
        offset = layout_width - advance(line)
        px = {"left": 0.0, "right": offset}.get(align, offset / 2)
        for piece, is_emoji in split_emoji(line):
            if not is_emoji:
                path.addText(QPointF(px, baseline), font, piece)
                px += metrics.horizontalAdvance(piece)
                continue
            # A square a little under the font size, centred in its
            # room on the line and on the capitals' middle.
            size = EMOJI_SIZE * BASE_PIXEL_SIZE
            cx = px + EMOJI_ADVANCE * BASE_PIXEL_SIZE / 2
            px += EMOJI_ADVANCE * BASE_PIXEL_SIZE
            cy = baseline - metrics.capHeight() / 2
            emoji.append([piece, cx, cy, size])
            bounds = bounds.united(QRectF(cx - size / 2, cy - size / 2, size, size))
        baseline += metrics.lineSpacing()

    bounds = path.boundingRect().united(bounds) if not path.isEmpty() else bounds
    subpaths = _subpaths(path)

    warps = []
    if abs(arc) >= 0.5 and bounds.width() > 0:
        warps.append(_arc_mapper(arc, bounds.center().x(), bounds.center().y(), bounds.width()))
    if abs(tilt) >= 0.5:
        warps.append(_tilt_mapper(tilt, bounds.center().x(), bounds.center().y(), bounds.height()))

    def warp(p):
        for w in warps:
            p = w(*p)
        return p

    parts = []
    result = QPainterPath()
    for sub in subpaths:
        start, segments = sub[0], sub[1:]
        if warps:
            segments = _fine_segments(start, segments)
        start = warp(start)
        parts.append(f"M{start[0]:.2f} {start[1]:.2f}")
        result.moveTo(*start)
        for seg in segments:
            points = [warp(p) for p in seg[1:]]
            if seg[0] == "L":
                parts.append(f"L{points[0][0]:.2f} {points[0][1]:.2f}")
                result.lineTo(*points[0])
            else:
                parts.append("C" + " ".join(f"{p[0]:.2f} {p[1]:.2f}" for p in points))
                result.cubicTo(*points[0], *points[1], *points[2])
        parts.append("Z")

    # Each emoji moves with the arc and tilt: its centre is warped, it
    # turns with the line there, and shrinks or grows with the tilt.
    placed = []
    box = result.boundingRect() if warps and not result.isEmpty() else QRectF()
    for piece, cx, cy, size in emoji:
        x, y = warp((cx, cy))
        angle, scale = 0.0, 1.0
        if warps:
            left, right = warp((cx - size / 2, cy)), warp((cx + size / 2, cy))
            angle = math.degrees(math.atan2(right[1] - left[1], right[0] - left[0]))
            scale = max(0.05, math.dist(left, right) / size)
        s = size * scale
        placed.append({"text": piece, "x": x, "y": y, "size": s, "angle": angle})
        if warps:
            box = box.united(QRectF(x - s / 2, y - s / 2, s, s))

    if not warps:
        box = bounds
    return {
        "path": "".join(parts),
        "x": box.x(),
        "y": box.y(),
        "width": box.width(),
        "height": box.height(),
        "lines": len(lines),
        "emoji": placed,
    }


class TextShaper(QObject):
    """Exposed to QML as `textShaper` (main.py)."""

    @Slot(str, str, bool, bool, float, str, float, float, result="QVariantMap")
    def shape(self, text, family, bold, italic, wrap_width, align, arc, tilt):
        # Rounded, so a resize drag reuses cached layouts.
        return shape_text(text, family, bold, italic, round(max(0.0, wrap_width), 1),
                          align, round(arc, 1), round(tilt, 1))
