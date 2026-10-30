"""
Snapping while moving or resizing (readme section 25, Snapping).

Edges snap to the wall's edges and to other objects' edges: touching
(my right edge to your left) or lined up (left to left). Centers snap to
centers (the wall's middle too). Everything works on axis-aligned
bounding boxes (left, top, right, bottom), so rotated objects snap by
the box around them.

Each axis snaps on its own, to the nearest line within `distance`. The
result includes guide lines to draw while snapped: (x1, y1, x2, y2),
spanning the moving box and what it snapped to.
"""

import math

SNAP_DISTANCE = 8.0

EDGE = "edge"
CENTER = "center"


def bounding_box(x, y, width, height, rotation=0.0):
    """(left, top, right, bottom) around a box rotated about its center."""
    r = math.radians(rotation)
    half_w = abs(width / 2 * math.cos(r)) + abs(height / 2 * math.sin(r))
    half_h = abs(width / 2 * math.sin(r)) + abs(height / 2 * math.cos(r))
    cx, cy = x + width / 2, y + height / 2
    return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def _lines(box, axis):
    """A box's lines across one axis: [(value, kind, span_lo, span_hi)]."""
    left, top, right, bottom = box
    if axis == "x":
        lo, hi = top, bottom
        return [(left, EDGE, lo, hi), (right, EDGE, lo, hi),
                ((left + right) / 2, CENTER, lo, hi)]
    lo, hi = left, right
    return [(top, EDGE, lo, hi), (bottom, EDGE, lo, hi),
            ((top + bottom) / 2, CENTER, lo, hi)]


def _snap_axis(moving, targets, distance):
    """
    moving: [(value, kind)]; targets: [(value, kind, lo, hi)].
    The smallest shift (target - moving) within distance between lines
    of the same kind, and the target lines it lands on. (0, []) if none.
    """
    best = None
    for value, kind in moving:
        for target in targets:
            if target[1] != kind:
                continue
            delta = target[0] - value
            if abs(delta) <= distance and (best is None or abs(delta) < abs(best)):
                best = delta
    if best is None:
        return 0.0, []
    hits = []
    for value, kind in moving:
        for target in targets:
            if target[1] == kind and abs(target[0] - (value + best)) < 0.5:
                hits.append(target)
    return best, hits


def _guides(hits, axis, box):
    """One guide line per snapped value, spanning the box and its targets."""
    left, top, right, bottom = box
    spans = {}
    for value, _, lo, hi in hits:
        key = round(value, 1)
        own_lo, own_hi = (top, bottom) if axis == "x" else (left, right)
        a, b = spans.get(key, (min(own_lo, lo), max(own_hi, hi)))
        spans[key] = (min(a, lo), max(b, hi))
    if axis == "x":
        return [(v, a, v, b) for v, (a, b) in spans.items()]
    return [(a, v, b, v) for v, (a, b) in spans.items()]


def _targets(others, wall, axis):
    targets = []
    for box in others:
        targets.extend(_lines(box, axis))
    if wall is not None:
        targets.extend(_lines((0.0, 0.0, wall[0], wall[1]), axis))
    return targets


def snap_move(box, others, wall, distance=SNAP_DISTANCE):
    """
    Snap a box being moved. `others`: the other objects' boxes; `wall`:
    (width, height) or None. Returns (dx, dy, guides).
    """
    dx, hits_x = _snap_axis([(v, k) for v, k, _, _ in _lines(box, "x")],
                            _targets(others, wall, "x"), distance)
    dy, hits_y = _snap_axis([(v, k) for v, k, _, _ in _lines(box, "y")],
                            _targets(others, wall, "y"), distance)
    moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
    return dx, dy, _guides(hits_x, "x", moved) + _guides(hits_y, "y", moved)


def snap_resize(box, sx, sy, others, wall, distance=SNAP_DISTANCE):
    """
    Snap the edges being dragged in a resize: sx -1/+1 = the left/right
    edge (0 = neither), sy likewise for top/bottom. Edges only snap to
    edges. Returns (dx, dy, guides_x, guides_y): the shift for each
    dragged edge, and the guides for each axis, kept apart so a resize
    that keeps its aspect ratio can use just one of them.
    """
    left, top, right, bottom = box
    dx, guides_x = 0.0, []
    if sx:
        edge = right if sx > 0 else left
        dx, hits = _snap_axis([(edge, EDGE)], _targets(others, wall, "x"), distance)
        if hits:
            moved = (left + (dx if sx < 0 else 0), top, right + (dx if sx > 0 else 0), bottom)
            guides_x = _guides(hits, "x", moved)
    dy, guides_y = 0.0, []
    if sy:
        edge = bottom if sy > 0 else top
        dy, hits = _snap_axis([(edge, EDGE)], _targets(others, wall, "y"), distance)
        if hits:
            moved = (left, top + (dy if sy < 0 else 0), right, bottom + (dy if sy > 0 else 0))
            guides_y = _guides(hits, "y", moved)
    return dx, dy, guides_x, guides_y
