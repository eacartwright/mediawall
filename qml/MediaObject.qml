import QtQuick

// A free media instance on the canvas.
// State comes from sceneModel; interactions commit back on release.
// Dragging onto a container places the media inside it.

Item {
    id: root

    // ---- Model roles ----
    required property string objectId
    required property real posX
    required property real posY
    required property real objWidth
    required property real objHeight
    required property real objRotation
    required property int objZ
    required property bool objPlaying
    required property bool objMuted
    required property real objVolume
    required property bool objLoop
    required property string sourceId
    required property string sourceType
    required property string sourceUrl
    required property string sourcePath
    required property string sourceName
    required property int sourceWidth
    required property int sourceHeight
    required property bool sourceAnimatable
    required property bool sourceMissing

    // The scene item, for coordinate mapping.
    property Item sceneItem

    // Shared right-click menu (ObjectContextMenu in Main.qml).
    property var contextMenu

    readonly property bool selected: sceneModel.selectedId === objectId

    // Used by the context menu.
    readonly property bool isAnimated: view.isAnimated
    readonly property bool isVideo: sourceType === "video"
    readonly property bool mediaMuted: objMuted
    readonly property bool mediaLoop: objLoop
    readonly property string playbackId: objectId
    readonly property bool isFreeMedia: true

    x: posX
    y: posY
    width: objWidth
    height: objHeight
    rotation: objRotation
    z: objZ


    // -------------------------------------------------
    // Model sync
    //
    // Dragging assigns x/y/etc. directly (fast, no Python per frame),
    // which breaks the bindings above. On release we send the result
    // to the model, then restore the bindings so future model changes
    // (load, undo) flow back in.
    // -------------------------------------------------

    function commit() {
        sceneModel.commitGeometry(objectId, x, y, width, height, rotation)
        rebind()
    }

    function rebind() {
        x = Qt.binding(function() { return root.posX })
        y = Qt.binding(function() { return root.posY })
        width = Qt.binding(function() { return root.objWidth })
        height = Qt.binding(function() { return root.objHeight })
        rotation = Qt.binding(function() { return root.objRotation })
    }


    // Scale by factor f around a point in scene coordinates.
    // Works for rotated objects too: scaling about a point doesn't
    // depend on rotation, so only the center and size change.
    function scaleAround(px, py, f) {
        var newWidth = Math.max(40, Math.min(20000, width * f))
        var k = newWidth / width

        var cx = x + width / 2
        var cy = y + height / 2
        var newCX = px + (cx - px) * k
        var newCY = py + (cy - py) * k

        width = width * k
        height = height * k
        x = newCX - width / 2
        y = newCY - height / 2

        // A whole scroll becomes one undo step.
        sceneModel.setMergeKey("scale:" + objectId)
        commit()
    }


    // -------------------------------------------------
    // Media
    // -------------------------------------------------

    MediaView {
        id: view

        anchors.fill: parent

        url: root.sourceUrl
        type: root.sourceType
        animatable: root.sourceAnimatable
        missing: root.sourceMissing
        playing: root.objPlaying
        muted: root.objMuted
        volume: root.objVolume
        loop: root.objLoop
        name: root.sourceName
        path: root.sourcePath

        // Videos (and images whose size couldn't be read up front)
        // report their real size here; Python resizes placeholders.
        onReady: function(naturalWidth, naturalHeight) {
            if (root.sourceWidth <= 0)
                sceneModel.reportSourceSize(
                    root.sourceId, naturalWidth, naturalHeight
                )
        }
    }


    // -------------------------------------------------
    // Video controls (selected videos only)
    // -------------------------------------------------

    VideoControls {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 20        // clear of the corner handles

        visible: root.selected && view.isPlayer

        z: 25

        view: view
        playing: root.objPlaying
        muted: root.objMuted

        onTogglePlay: sceneModel.setPlaying(root.objectId, !root.objPlaying)
        onToggleMute: sceneModel.setMuted(root.objectId, !root.objMuted)
    }


    // -------------------------------------------------
    // Selection outline
    // -------------------------------------------------

    Rectangle {
        anchors.fill: parent

        color: "transparent"

        border.color: "#5da9ff"
        border.width: 2

        visible: root.selected

        z: 5
    }


    // -------------------------------------------------
    // Move (and drop into a container)
    // -------------------------------------------------

    MouseArea {
        id: moveArea

        anchors.fill: parent

        z: 2

        acceptedButtons: Qt.LeftButton | Qt.RightButton

        // True only while a left-button drag is in progress.
        property bool dragging: false

        // True once the pointer has moved far enough to count as a drag,
        // so a plain click over a container never drops into it.
        property bool moved: false

        property point startMouse
        property point startPos

        onPressed: function(mouse) {
            if (mouse.button === Qt.RightButton) {
                dragging = false
                sceneModel.select(root.objectId)
                if (root.contextMenu)
                    root.contextMenu.openFor(root)
                return
            }

            dragging = true
            moved = false

            sceneModel.select(root.objectId)

            startMouse = moveArea.mapToItem(root.sceneItem, mouse.x, mouse.y)
            startPos = Qt.point(root.x, root.y)
        }

        onPositionChanged: function(mouse) {
            if (!pressed || !dragging)
                return

            var p = moveArea.mapToItem(root.sceneItem, mouse.x, mouse.y)
            var dx = p.x - startMouse.x
            var dy = p.y - startMouse.y

            if (!moved && Math.abs(dx) + Math.abs(dy) < 6)
                return
            moved = true

            root.x = startPos.x + dx
            root.y = startPos.y + dy

            // Highlight the container under the pointer (Shift = place on top).
            var shift = (mouse.modifiers & Qt.ShiftModifier) !== 0
            sceneModel.setDropTarget(
                shift ? "" : sceneModel.containerAt(p.x, p.y, "")
            )
        }

        onReleased: {
            if (!dragging)
                return

            dragging = false

            var target = sceneModel.dropTargetId
            sceneModel.setDropTarget("")

            if (moved && target !== "") {
                // This object's delegate is destroyed by the move, so do it
                // after this handler has finished.
                var id = root.objectId
                Qt.callLater(function() {
                    sceneModel.moveIntoContainer(id, target)
                })
                return
            }

            if (moved)
                root.commit()
        }

        // Mouse wheel over a selected image scales it around the pointer.
        // (Same as the resize handle, just quicker.)
        onWheel: function(wheel) {
            if (!root.selected || wheel.angleDelta.y === 0) {
                wheel.accepted = false
                return
            }

            var f = wheel.angleDelta.y > 0 ? 1.1 : 1 / 1.1
            var p = moveArea.mapToItem(root.sceneItem, wheel.x, wheel.y)
            root.scaleAround(p.x, p.y, f)
        }

        onCanceled: {
            dragging = false
            sceneModel.setDropTarget("")
            root.rebind()
        }
    }


    // -------------------------------------------------
    // Resize handles (aspect ratio kept)
    // -------------------------------------------------

    ResizeHandles {
        visible: root.selected

        target: root
        sceneItem: root.sceneItem

        keepAspect: true
        aspectRatio: (root.sourceWidth > 0 && root.sourceHeight > 0)
                     ? root.sourceWidth / root.sourceHeight
                     : root.objWidth / root.objHeight

        minWidth: 40
        minHeight: 20

        color: "#5da9ff"

        onFinished: root.commit()
    }


    // -------------------------------------------------
    // Rotation handle
    // -------------------------------------------------

    RotationHandle {
        visible: root.selected

        target: root
        sceneItem: root.sceneItem

        pivot: function() {
            return root.mapToItem(root.sceneItem, root.width / 2, root.height / 2)
        }
        currentRotation: function() { return root.rotation }
        applyRotation: function(r) { root.rotation = r }

        onFinished: root.commit()
    }
}
