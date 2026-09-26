import QtQuick
import QtQuick.Controls

// Container: a viewport holding one media instance, clipped to its shape.
//
// Normal mode:  drag moves the container, corner resizes, knob rotates.
// Adjust mode:  drag pans the content, wheel zooms, knob rotates the
//               content. The part outside the frame shows as a ghost.
//               Enter by double-clicking or from the right-click menu.
//
// Content geometry is in the container's local coordinates
// (0, 0 = top-left of the unrotated container).

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
    required property bool lockContent

    required property string contentId
    required property real contentX
    required property real contentY
    required property real contentWidth
    required property real contentHeight
    required property real contentRotation
    required property bool contentPlaying
    required property bool contentMuted
    required property real contentVolume
    required property bool contentLoop
    required property string contentSourceId
    required property string contentSourceType
    required property string contentSourceUrl
    required property string contentSourcePath
    required property string contentSourceName
    required property bool contentSourceAnimatable
    required property bool contentSourceMissing

    property Item sceneItem

    // Shared right-click menu (ObjectContextMenu in Main.qml).
    property var contextMenu

    readonly property bool selected: sceneModel.selectedId === objectId
    readonly property bool hasContent: contentId !== ""
    readonly property bool isDropTarget: sceneModel.dropTargetId === objectId

    // Workspace-only state; not saved.
    property bool adjusting: false

    // True while a corner handle is being dragged.
    property bool resizing: false

    onSelectedChanged: if (!selected) adjusting = false
    onHasContentChanged: if (!hasContent) adjusting = false

    Connections {
        target: sceneModel

        function onAdjustRequested(containerId) {
            if (containerId === root.objectId && root.hasContent)
                root.adjusting = true
        }
    }

    // Used by the context menu.
    readonly property bool isContainer: true
    readonly property string playbackId: contentId
    readonly property bool objPlaying: contentPlaying
    readonly property bool isAnimated: hasContent && contentView.isAnimated
    readonly property bool isVideo: hasContent && contentSourceType === "video"
    readonly property bool mediaMuted: contentMuted
    readonly property bool mediaLoop: contentLoop

    x: posX
    y: posY
    width: objWidth
    height: objHeight
    rotation: objRotation
    z: objZ


    // -------------------------------------------------
    // Container geometry sync (same pattern as other objects)
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


    // -------------------------------------------------
    // Content geometry
    //
    // Held as center + size + rotation. Normally bound to the model.
    // While resizing a locked container, the bindings scale the
    // content live using the same math Python applies on commit.
    // Pan/zoom/rotate assign these directly, then commitContent()
    // sends them to the model and restores the bindings.
    // -------------------------------------------------

    readonly property real liveSX:
        lockContent && objWidth > 0 ? width / objWidth : 1
    readonly property real liveSY:
        lockContent && objHeight > 0 ? height / objHeight : 1
    readonly property real liveS: Math.max(liveSX, liveSY)

    // Independent mode while resizing: shift the content so it stays put
    // on the canvas (matches Scene._keep_content_in_place on commit).
    readonly property point liveShift: {
        if (!resizing || lockContent)
            return Qt.point(0, 0)

        var dcx = (posX + objWidth / 2) - (x + width / 2)
        var dcy = (posY + objHeight / 2) - (y + height / 2)

        var r = -objRotation * Math.PI / 180
        var rx = dcx * Math.cos(r) - dcy * Math.sin(r)
        var ry = dcx * Math.sin(r) + dcy * Math.cos(r)

        return Qt.point(rx - objWidth / 2 + width / 2,
                        ry - objHeight / 2 + height / 2)
    }

    QtObject {
        id: cg

        property real cx
        property real cy
        property real w
        property real h
        property real rot
    }

    function bindContent() {
        cg.w = Qt.binding(function() { return root.contentWidth * root.liveS })
        cg.h = Qt.binding(function() { return root.contentHeight * root.liveS })
        cg.cx = Qt.binding(function() {
            return (root.contentX + root.contentWidth / 2) * root.liveSX
                   + root.liveShift.x
        })
        cg.cy = Qt.binding(function() {
            return (root.contentY + root.contentHeight / 2) * root.liveSY
                   + root.liveShift.y
        })
        cg.rot = Qt.binding(function() { return root.contentRotation })
    }

    Component.onCompleted: bindContent()

    function commitContent() {
        sceneModel.commitContent(
            objectId, cg.cx - cg.w / 2, cg.cy - cg.h / 2, cg.w, cg.h, cg.rot
        )
        bindContent()
    }

    // Zoom by factor f around a point in container coordinates.
    function zoomAt(px, py, f) {
        var newW = Math.max(20, cg.w * f)
        var k = newW / cg.w

        var newCX = px - (px - cg.cx) * k
        var newCY = py - (py - cg.cy) * k
        var newH = cg.h * k

        cg.cx = newCX
        cg.cy = newCY
        cg.w = newW
        cg.h = newH

        // A whole scroll becomes one undo step.
        sceneModel.setMergeKey("zoom:" + objectId)
        commitContent()
    }


    // -------------------------------------------------
    // Ghost: the whole content, faint, shown while adjusting.
    // Drawn below the frame, so only the part outside the frame shows.
    // -------------------------------------------------

    MediaView {
        x: cg.cx - cg.w / 2
        y: cg.cy - cg.h / 2
        width: cg.w
        height: cg.h
        rotation: cg.rot

        visible: root.adjusting
        opacity: 0.35

        // Only load while adjusting. Videos get no ghost (a second copy
        // would play out of sync); the orange outline still shows bounds.
        url: root.adjusting && root.contentSourceType === "image"
             ? root.contentSourceUrl : ""
        type: "image"
        animatable: root.contentSourceAnimatable
        missing: root.contentSourceMissing
        playing: root.contentPlaying
        showErrorState: false
    }


    // -------------------------------------------------
    // Frame: background + clipped content
    // (clip_shape is always "rect" for now; other shapes will
    // replace this clip with a mask.)
    // -------------------------------------------------

    Rectangle {
        id: frame

        anchors.fill: parent

        color: "#252525"
        clip: true

        MediaView {
            id: contentView

            x: cg.cx - cg.w / 2
            y: cg.cy - cg.h / 2
            width: cg.w
            height: cg.h
            rotation: cg.rot

            visible: root.hasContent

            url: root.contentSourceUrl
            type: root.contentSourceType
            animatable: root.contentSourceAnimatable
            missing: root.contentSourceMissing
            playing: root.contentPlaying
            muted: root.contentMuted
            volume: root.contentVolume
            loop: root.contentLoop
            name: root.contentSourceName

            // Shown for the whole frame instead (below), so it's
            // readable however far the content is zoomed.
            showErrorState: false

            onReady: function(naturalWidth, naturalHeight) {
                sceneModel.reportSourceSize(
                    root.contentSourceId, naturalWidth, naturalHeight
                )
            }
        }

        MediaErrorBox {
            anchors.fill: parent

            visible: root.hasContent &&
                     (root.contentSourceMissing || contentView.failed)

            missing: root.contentSourceMissing
            name: root.contentSourceName
            path: root.contentSourcePath
        }

        Text {
            anchors.centerIn: parent
            width: parent.width - 24

            visible: !root.hasContent && !root.isDropTarget

            text: "Empty container\n\nDrag an image or video onto it, or select\n"
                  + "it and use a browser's Add to Container"

            color: "#777777"
            font.pixelSize: 13

            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        // Drop highlight while media is dragged over this container.
        Rectangle {
            anchors.fill: parent

            visible: root.isDropTarget

            color: "#337fc97f"
            border.color: "#7fc97f"
            border.width: 3

            Text {
                anchors.centerIn: parent
                width: parent.width - 24

                text: root.hasContent
                      ? "Release to replace content\n(hold Shift to place on top)"
                      : "Release to place in container\n(hold Shift to place on top)"

                color: "#dff5df"
                font.pixelSize: 13

                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }
    }


    // -------------------------------------------------
    // Outlines
    // -------------------------------------------------

    // Container border / selection
    Rectangle {
        anchors.fill: parent

        color: "transparent"

        border.color: root.adjusting ? "#e0a84c"
                      : root.selected ? "#7fc97f"
                      : "#555555"
        border.width: root.selected ? 2 : 1

        z: 5
    }

    // Full content bounds while adjusting
    Rectangle {
        x: cg.cx - cg.w / 2
        y: cg.cy - cg.h / 2
        width: cg.w
        height: cg.h
        rotation: cg.rot

        visible: root.adjusting

        color: "transparent"
        border.color: "#e0a84c"
        border.width: 1

        z: 5
    }


    // -------------------------------------------------
    // Mouse: move (normal) or pan/zoom (adjusting)
    // -------------------------------------------------

    MouseArea {
        id: area

        anchors.fill: parent

        z: 10

        acceptedButtons: Qt.LeftButton | Qt.RightButton

        property string mode: ""      // "move" | "pan" | ""
        property point startMouse
        property point startPos

        onPressed: function(mouse) {
            sceneModel.select(root.objectId)

            if (mouse.button === Qt.RightButton) {
                mode = ""
                if (root.contextMenu)
                    root.contextMenu.openFor(root)
                return
            }

            if (root.adjusting) {
                // The container doesn't move while panning, so local
                // mouse coordinates are stable.
                mode = "pan"
                startMouse = Qt.point(mouse.x, mouse.y)
                startPos = Qt.point(cg.cx, cg.cy)
            } else {
                mode = "move"
                startMouse = area.mapToItem(root.sceneItem, mouse.x, mouse.y)
                startPos = Qt.point(root.x, root.y)
            }
        }

        onPositionChanged: function(mouse) {
            if (!pressed)
                return

            if (mode === "move") {
                var p = area.mapToItem(root.sceneItem, mouse.x, mouse.y)
                root.x = startPos.x + (p.x - startMouse.x)
                root.y = startPos.y + (p.y - startMouse.y)
            } else if (mode === "pan") {
                cg.cx = startPos.x + (mouse.x - startMouse.x)
                cg.cy = startPos.y + (mouse.y - startMouse.y)
            }
        }

        onReleased: {
            if (mode === "move")
                root.commit()
            else if (mode === "pan")
                root.commitContent()
            mode = ""
        }

        onDoubleClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton && root.hasContent)
                root.adjusting = true
        }

        onWheel: function(wheel) {
            if (!root.adjusting) {
                wheel.accepted = false
                return
            }

            if (wheel.angleDelta.y > 0)
                root.zoomAt(wheel.x, wheel.y, 1.1)
            else if (wheel.angleDelta.y < 0)
                root.zoomAt(wheel.x, wheel.y, 1 / 1.1)
        }
    }


    // -------------------------------------------------
    // Resize handles (normal mode)
    // -------------------------------------------------

    ResizeHandles {
        visible: root.selected && !root.adjusting

        target: root
        sceneItem: root.sceneItem

        minWidth: 60
        minHeight: 40

        color: "#7fc97f"

        onStarted: root.resizing = true
        onFinished: {
            // Commit first, so the content's new position arrives from
            // the model before the live preview switches off.
            root.commit()
            root.resizing = false
        }
    }


    // -------------------------------------------------
    // Rotation handle: rotates the container, or the content
    // while adjusting.
    // -------------------------------------------------

    RotationHandle {
        visible: root.selected

        target: root
        sceneItem: root.sceneItem

        pivot: function() {
            return root.adjusting
                   ? root.mapToItem(root.sceneItem, cg.cx, cg.cy)
                   : root.mapToItem(root.sceneItem, root.width / 2, root.height / 2)
        }
        currentRotation: function() {
            return root.adjusting ? cg.rot : root.rotation
        }
        applyRotation: function(r) {
            if (root.adjusting)
                cg.rot = r
            else
                root.rotation = r
        }

        onFinished: {
            if (root.adjusting)
                root.commitContent()
            else
                root.commit()
        }
    }


    // -------------------------------------------------
    // Video controls (selected, not adjusting)
    // -------------------------------------------------

    VideoControls {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 20        // clear of the corner handles

        visible: root.selected && !root.adjusting && contentView.isPlayer

        z: 25

        view: contentView
        playing: root.contentPlaying
        muted: root.contentMuted

        onTogglePlay: sceneModel.setPlaying(root.contentId, !root.contentPlaying)
        onToggleMute: sceneModel.setMuted(root.contentId, !root.contentMuted)
    }


    // -------------------------------------------------
    // Adjust-mode toolbar
    // -------------------------------------------------

    Rectangle {
        anchors.top: parent.bottom
        anchors.topMargin: 10
        anchors.horizontalCenter: parent.horizontalCenter

        width: toolRow.implicitWidth + 12
        height: toolRow.implicitHeight + 10

        visible: root.adjusting

        color: "#303030"
        border.color: "#e0a84c"
        radius: 4

        z: 30

        // Absorb clicks between buttons so they don't deselect.
        MouseArea {
            anchors.fill: parent
        }

        Row {
            id: toolRow

            anchors.centerIn: parent

            spacing: 4

            Text {
                anchors.verticalCenter: parent.verticalCenter
                rightPadding: 6

                text: "Drag to pan · scroll to zoom"

                color: "#cccccc"
                font.pixelSize: 11
            }

            Button {
                text: "−"
                onClicked: root.zoomAt(root.width / 2, root.height / 2, 1 / 1.2)
            }

            Button {
                text: "+"
                onClicked: root.zoomAt(root.width / 2, root.height / 2, 1.2)
            }

            Button {
                text: "Fit"
                onClicked: sceneModel.fitContent(root.objectId, false)
            }

            Button {
                text: "Fill"
                onClicked: sceneModel.fitContent(root.objectId, true)
            }

            Button {
                text: "Done"
                onClicked: root.adjusting = false
            }
        }
    }
}
