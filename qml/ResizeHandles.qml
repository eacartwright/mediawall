import QtQuick

// Four corner resize handles for a scene object.
//
// Dragging a corner moves that corner while the opposite corner stays
// pinned in place, including on rotated objects. The math works in the
// object's own rotated frame, then converts back to scene x/y.
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
    property real handleSize: 16

    signal started()
    signal finished()

    anchors.fill: parent
    z: 20

    function rotated(x, y, degrees) {
        var r = degrees * Math.PI / 180
        var c = Math.cos(r)
        var s = Math.sin(r)
        return Qt.point(x * c - y * s, x * s + y * c)
    }

    Repeater {
        // sx, sy: which corner (-1 = left/top, +1 = right/bottom)
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

            MouseArea {
                id: area

                anchors.fill: parent

                cursorShape: corner.modelData.sx * corner.modelData.sy > 0
                             ? Qt.SizeFDiagCursor
                             : Qt.SizeBDiagCursor

                property real theta
                property point pinned        // opposite corner, scene coords
                property point grabOffset    // pointer -> exact corner

                onPressed: function(mouse) {
                    var t = handles.target
                    var sx = corner.modelData.sx
                    var sy = corner.modelData.sy

                    theta = t.rotation

                    var cx = t.x + t.width / 2
                    var cy = t.y + t.height / 2

                    var a = handles.rotated(-sx * t.width / 2, -sy * t.height / 2, theta)
                    pinned = Qt.point(cx + a.x, cy + a.y)

                    var c = handles.rotated(sx * t.width / 2, sy * t.height / 2, theta)
                    var p = area.mapToItem(handles.sceneItem, mouse.x, mouse.y)
                    grabOffset = Qt.point(cx + c.x - p.x, cy + c.y - p.y)

                    handles.started()
                }

                onPositionChanged: function(mouse) {
                    if (!pressed)
                        return

                    var t = handles.target
                    var sx = corner.modelData.sx
                    var sy = corner.modelData.sy

                    var p = area.mapToItem(handles.sceneItem, mouse.x, mouse.y)

                    // Pointer relative to the pinned corner, in the object's frame.
                    var d = handles.rotated(
                        p.x + grabOffset.x - pinned.x,
                        p.y + grabOffset.y - pinned.y,
                        -theta
                    )

                    var w = Math.max(handles.minWidth, sx * d.x)
                    var h = Math.max(handles.minHeight, sy * d.y)

                    if (handles.keepAspect && handles.aspectRatio > 0) {
                        w = Math.max(w, h * handles.aspectRatio)
                        h = w / handles.aspectRatio
                    }

                    // New center: from the pinned corner, half the new size
                    // toward the dragged corner, in the object's frame.
                    var off = handles.rotated(sx * w / 2, sy * h / 2, theta)

                    t.width = w
                    t.height = h
                    t.x = pinned.x + off.x - w / 2
                    t.y = pinned.y + off.y - h / 2
                }

                onReleased: handles.finished()
            }
        }
    }
}
