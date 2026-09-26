import QtQuick

// The orange rotation knob above an object, with its guide line.
//
// Rotation is relative: the object turns by however far the pointer
// turns around the pivot, so grabbing the handle never makes the
// object jump.
//
// Double-clicking the knob resets the rotation to 0°.

Item {
    id: handle

    // The object the handle sits above (for placement).
    property Item target

    // The scene item, for coordinate mapping.
    property Item sceneItem

    // Functions supplied by the owner, so the same handle can rotate
    // an object or the content inside a container.
    property var pivot              // () -> point, in scene coordinates
    property var currentRotation    // () -> degrees
    property var applyRotation      // (degrees) -> void

    signal finished()

    width: 16
    height: 28

    anchors.horizontalCenter: target ? target.horizontalCenter : undefined
    anchors.bottom: target ? target.top : undefined

    z: 20

    // Guide line
    Rectangle {
        width: 2
        height: 12

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom

        color: "#e0a84c"
    }

    // Knob
    Rectangle {
        width: 16
        height: 16
        radius: 8

        anchors.top: parent.top

        color: "#e0a84c"

        MouseArea {
            id: area

            anchors.fill: parent

            property point center
            property real startAngle
            property real startRotation

            function angleTo(mouse) {
                var p = area.mapToItem(handle.sceneItem, mouse.x, mouse.y)
                return Math.atan2(p.y - center.y, p.x - center.x) * 180 / Math.PI
            }

            onPressed: function(mouse) {
                center = handle.pivot()
                startAngle = angleTo(mouse)
                startRotation = handle.currentRotation()
            }

            onPositionChanged: function(mouse) {
                if (!pressed)
                    return

                handle.applyRotation(startRotation + angleTo(mouse) - startAngle)
            }

            onReleased: handle.finished()

            onDoubleClicked: {
                handle.applyRotation(0)
                handle.finished()
            }
        }
    }
}
