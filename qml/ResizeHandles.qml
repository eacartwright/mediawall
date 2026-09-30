import QtQuick

// Resize handles for a scene object: four square corners, and a thin bar
// at the middle of each side.
//
// Dragging a corner moves that corner while the opposite corner stays
// pinned in place; dragging an edge moves that side while the opposite
// side stays put. Both work on rotated objects: the math works in the
// object's own rotated frame, then converts back to scene x/y.
//
// With keepAspect (images), an edge drag also changes the other
// dimension, centered on the pinned side's midline.
//
// The handles write the target's x/y/width/height directly during the
// drag; the owner commits to the model in onFinished.

Item {
    id: handles

    // The object being resized. Its x/y must be scene coordinates.
    property Item target

    // The scene item, for mapping the pointer.
    property Item sceneItem

    property bool keepAspect: false
    property real aspectRatio: 1        // width / height, when keepAspect

    property real minWidth: 40
    property real minHeight: 40

    property color color: "#5da9ff"
    property real handleSize: 9

    // Edge bars: visible size, and the (larger) area that grabs them.
    property real edgeLength: 19
    property real edgeThickness: 4
    property real edgeGrab: 12

    signal started()
    signal finished()

    // An edge bar was double-clicked: sx, sy say which (as for Grip).
    signal edgeDoubleClicked(int sx, int sy)

    anchors.fill: parent
    z: 20

    function rotated(x, y, degrees) {
        var r = degrees * Math.PI / 180
        var c = Math.cos(r)
        var s = Math.sin(r)
        return Qt.point(x * c - y * s, x * s + y * c)
    }

    // ---- Shared drag logic ----
    //
    // sx, sy: which side the handle is on (-1 = left/top, +1 = right/
    // bottom, 0 = this axis isn't dragged). `state` is the grabbing
    // MouseArea, which remembers the drag's starting values.

    function begin(state, sx, sy, mouse) {
        var t = handles.target
        state.theta = t.rotation

        var cx = t.x + t.width / 2
        var cy = t.y + t.height / 2

        // The point that stays put: the opposite corner, or the middle
        // of the opposite side.
        var a = rotated(-sx * t.width / 2, -sy * t.height / 2, state.theta)
        state.pinned = Qt.point(cx + a.x, cy + a.y)

        // The dragged point: this corner, or the middle of this side.
        var c = rotated(sx * t.width / 2, sy * t.height / 2, state.theta)
        var p = state.mapToItem(handles.sceneItem, mouse.x, mouse.y)
        state.grabOffset = Qt.point(cx + c.x - p.x, cy + c.y - p.y)

        handles.started()
    }

    function drag(state, sx, sy, mouse) {
        var t = handles.target
        var p = state.mapToItem(handles.sceneItem, mouse.x, mouse.y)

        // Pointer relative to the pinned point, in the object's frame.
        var d = rotated(
            p.x + state.grabOffset.x - state.pinned.x,
            p.y + state.grabOffset.y - state.pinned.y,
            -state.theta
        )

        var w = sx !== 0 ? Math.max(handles.minWidth, sx * d.x) : t.width
        var h = sy !== 0 ? Math.max(handles.minHeight, sy * d.y) : t.height

        if (handles.keepAspect && handles.aspectRatio > 0) {
            if (sx !== 0 && sy !== 0) {
                w = Math.max(w, h * handles.aspectRatio)
                h = w / handles.aspectRatio
            } else if (sx !== 0) {
                h = w / handles.aspectRatio
            } else {
                w = h * handles.aspectRatio
            }
        }

        // New center: from the pinned point, half the new size toward
        // the dragged side(s), in the object's frame.
        var off = rotated(sx * w / 2, sy * h / 2, state.theta)

        t.width = w
        t.height = h
        t.x = state.pinned.x + off.x - w / 2
        t.y = state.pinned.y + off.y - h / 2
    }

    component Grip: MouseArea {
        id: grip

        required property int sx
        required property int sy

        property real theta
        property point pinned
        property point grabOffset

        onPressed: function(mouse) { handles.begin(grip, sx, sy, mouse) }
        onPositionChanged: function(mouse) {
            if (pressed)
                handles.drag(grip, sx, sy, mouse)
        }
        onReleased: handles.finished()
        onDoubleClicked: {
            if (sx === 0 || sy === 0)
                handles.edgeDoubleClicked(sx, sy)
        }
    }


    // ---- Corners ----

    Repeater {
        model: [
            { sx: -1, sy: -1 },
            { sx:  1, sy: -1 },
            { sx: -1, sy:  1 },
            { sx:  1, sy:  1 }
        ]

        delegate: Rectangle {
            id: corner

            required property var modelData

            width: handles.handleSize
            height: handles.handleSize

            x: modelData.sx < 0 ? 0 : handles.width - width
            y: modelData.sy < 0 ? 0 : handles.height - height

            color: handles.color

            // The grab area reaches a little past the small square.
            Grip {
                anchors.fill: parent
                anchors.margins: -4
                sx: corner.modelData.sx
                sy: corner.modelData.sy
                cursorShape: sx * sy > 0 ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor
            }
        }
    }


    // ---- Edges: thin bars at the middle of each side ----

    Repeater {
        model: [
            { sx:  0, sy: -1 },
            { sx:  0, sy:  1 },
            { sx: -1, sy:  0 },
            { sx:  1, sy:  0 }
        ]

        delegate: Item {
            id: edge

            required property var modelData
            readonly property bool horizontal: modelData.sy !== 0   // top/bottom

            // Shorter on small objects, and hidden if it would crowd
            // the corners.
            readonly property real available:
                (horizontal ? handles.width : handles.height) - 2 * handles.handleSize - 8
            readonly property real length: Math.min(handles.edgeLength, available)

            visible: length >= 12

            // The grab area; the visible bar sits on the object's edge.
            width: horizontal ? length : handles.edgeGrab
            height: horizontal ? handles.edgeGrab : length

            x: horizontal ? (handles.width - width) / 2
               : modelData.sx < 0 ? 0 : handles.width - width
            y: horizontal ? (modelData.sy < 0 ? 0 : handles.height - height)
               : (handles.height - height) / 2

            Rectangle {
                width: edge.horizontal ? parent.width : handles.edgeThickness
                height: edge.horizontal ? handles.edgeThickness : parent.height
                x: edge.horizontal ? 0 : (edge.modelData.sx < 0 ? 0 : parent.width - width)
                y: edge.horizontal ? (edge.modelData.sy < 0 ? 0 : parent.height - height) : 0
                radius: 2
                color: handles.color
            }

            Grip {
                anchors.fill: parent
                sx: edge.modelData.sx
                sy: edge.modelData.sy
                cursorShape: edge.horizontal ? Qt.SizeVerCursor : Qt.SizeHorCursor
            }
        }
    }
}
