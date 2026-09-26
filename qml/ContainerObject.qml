import QtQuick
import QtQuick.Controls
import "Zoom.js" as Zoom

// Container: a viewport holding one media instance, clipped to its shape.
//
// Normal mode:  drag moves the container, corner resizes, knob rotates.
// Adjust mode:  drag pans the content, wheel zooms, knob rotates the
//               content. The part outside the frame shows as a ghost.
//               Enter by double-clicking or from the right-click menu.
// Browsing:     the wheel steps through the media in a folder, showing
//               each file as the content (right-click > Browse This
//               Folder). Also works in Present: a hand-driven slideshow.
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
    required property string fitMode
    required property bool browseMode
    required property string browseFolder
    required property bool browseSubfolders

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
    required property real contentSpeed
    required property bool contentPreservePitch
    required property real contentLoopA
    required property real contentLoopB
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

    // Present mode: view-only, never shown as selected. Disabled items
    // let clicks through to the canvas (double-click there exits). A
    // browsing container stays enabled for the wheel, but takes no
    // clicks (see the MouseArea below).
    readonly property bool presenting: sceneItem ? sceneItem.presenting : false
    enabled: !presenting || browseMode

    readonly property bool selected:
        !presenting && sceneModel.selectedId === objectId
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
    readonly property real mediaLoopA: contentLoopA
    readonly property real mediaLoopB: contentLoopB
    readonly property var mediaView: contentView

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
    // Browsing: the folder's images and videos (rescanned when the
    // folder or subfolder setting changes), and where the current
    // content is among them.
    // -------------------------------------------------

    property var browseFiles: []

    function rescanBrowse() {
        if (!browseMode || browseFolder === "") {
            browseFiles = []
            return
        }
        browseFiles = browserBackend.scanFolder(browseFolder, browseSubfolders)
            .filter(function(e) { return e.type === "image" || e.type === "video" })
    }

    onBrowseModeChanged: rescanBrowse()
    onBrowseFolderChanged: rescanBrowse()
    onBrowseSubfoldersChanged: rescanBrowse()

    readonly property int browseIndex: {
        for (var i = 0; i < browseFiles.length; i++) {
            if (browseFiles[i].path === contentSourcePath)
                return i
        }
        return -1
    }

    // Wheel up = previous, down = next, wrapping around (as in a browser).
    function browseStep(delta) {
        var n = browseFiles.length
        if (n === 0)
            return
        var i = browseIndex < 0 ? (delta > 0 ? 0 : n - 1)
                                : (browseIndex + delta + n) % n
        sceneModel.showInContainer(objectId, browseFiles[i].path, browseFiles[i].type)
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

    Component.onCompleted: {
        bindContent()
        rescanBrowse()
    }

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

    // Drawn from the content itself (a live texture of contentView,
    // which the frame's clip doesn't affect), so videos and GIFs get a
    // ghost that is always in sync, and nothing is loaded twice.
    ShaderEffectSource {
        x: cg.cx - cg.w / 2
        y: cg.cy - cg.h / 2
        width: cg.w
        height: cg.h
        rotation: cg.rot

        visible: root.adjusting && root.hasContent
        opacity: 0.35

        sourceItem: root.adjusting ? contentView : null
        live: true
        hideSource: false

        // It's faint: no need for full resolution when zoomed far in.
        readonly property real scaleDown: Math.min(1, 1024 / Math.max(1, width, height))
        textureSize: Qt.size(Math.ceil(width * scaleDown), Math.ceil(height * scaleDown))
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
            speed: root.contentSpeed
            preservePitch: root.contentPreservePitch
            loopA: root.contentLoopA
            loopB: root.contentLoopB
            name: root.contentSourceName

            // Registered under the content's id (it changes when the
            // content is replaced or removed).
            property string registeredId: ""

            function register() {
                if (!root.sceneItem)
                    return
                root.sceneItem.unregisterView(registeredId, contentView)
                registeredId = root.contentId
                root.sceneItem.registerView(registeredId, contentView)
            }

            Component.onCompleted: register()
            Component.onDestruction: if (root.sceneItem) root.sceneItem.unregisterView(registeredId, contentView)

            Connections {
                target: root
                function onContentIdChanged() { contentView.register() }
            }

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

                text: "Release to place in container\n(hold Shift to place on top)"

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

        // In Present only the wheel is used (browsing containers).
        acceptedButtons: root.presenting ? Qt.NoButton : Qt.LeftButton | Qt.RightButton

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

        // Adjusting: zoom the content. Browsing: step through the
        // folder (selected or not, and in Present). Otherwise, when
        // selected, scale the whole container like a free image.
        onWheel: function(wheel) {
            if (wheel.angleDelta.y === 0) {
                wheel.accepted = false
                return
            }

            if (root.browseMode && !root.adjusting) {
                root.browseStep(wheel.angleDelta.y > 0 ? -1 : 1)
                return
            }

            if (!(root.adjusting || root.selected)) {
                wheel.accepted = false
                return
            }

            var f = Zoom.wheelFactor(wheel.angleDelta.y)

            if (root.adjusting) {
                root.zoomAt(wheel.x, wheel.y, f)
            } else {
                var p = area.mapToItem(root.sceneItem, wheel.x, wheel.y)
                sceneModel.setMergeKey("scale:" + root.objectId)
                sceneModel.scaleObject(root.objectId, p.x, p.y, f)
            }
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

        // Play/pause and mute are in the right-click menu.
        showButtons: false

        view: contentView
        playing: root.contentPlaying
        muted: root.contentMuted

        onTogglePlay: sceneModel.setPlaying(root.contentId, !root.contentPlaying)
        onToggleMute: sceneModel.setMuted(root.contentId, !root.contentMuted)
    }


    // -------------------------------------------------
    // Browsing badge (selected): position in the folder and file name
    // -------------------------------------------------

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 22                 // clear of the corner handles

        width: Math.min(badgeText.implicitWidth + 12, parent.width - 44)
        height: badgeText.implicitHeight + 6
        radius: 3

        visible: root.browseMode && root.selected && !root.adjusting
        color: "#cc202020"
        z: 25

        Text {
            id: badgeText
            anchors.centerIn: parent
            width: parent.width - 12
            elide: Text.ElideMiddle
            text: root.browseFiles.length === 0
                  ? "Browsing · no media found"
                  : "⇅ " + (root.browseIndex + 1) + " / " + root.browseFiles.length
                    + (root.browseIndex >= 0 ? " · " + root.browseFiles[root.browseIndex].relpath : "")
            color: "#dddddd"
            font.pixelSize: 11
        }
    }


    // -------------------------------------------------
    // Adjust-mode toolbar
    //
    // Lives in scene coordinates rather than inside the (rotated)
    // container, so it stays upright and readable. It sits below the
    // container's on-screen bounds, or above them if there's no room,
    // and is kept inside the visible canvas.
    // -------------------------------------------------

    // Enter / Space finish adjusting, like Done.
    Shortcut {
        enabled: root.adjusting
        sequences: ["Return", "Enter", "Space"]
        onActivated: root.adjusting = false
    }

    Rectangle {
        id: adjustBar

        parent: root.sceneItem

        // Axis-aligned bounds of the rotated container, in scene
        // coordinates (rotation is about the container's center).
        readonly property real rad: root.rotation * Math.PI / 180
        readonly property real halfW:
            Math.abs(root.width / 2 * Math.cos(rad)) + Math.abs(root.height / 2 * Math.sin(rad))
        readonly property real halfH:
            Math.abs(root.width / 2 * Math.sin(rad)) + Math.abs(root.height / 2 * Math.cos(rad))
        readonly property real centerX: root.x + root.width / 2
        readonly property real centerY: root.y + root.height / 2

        readonly property real gap: 10
        readonly property real edge: 4
        readonly property real sceneW: parent ? parent.width : 0
        readonly property real sceneH: parent ? parent.height : 0

        x: Math.max(edge, Math.min(sceneW - width - edge, centerX - width / 2))
        y: {
            var below = centerY + halfH + gap
            if (below + height <= sceneH - edge)
                return below

            var above = centerY - halfH - gap - height
            if (above >= edge)
                return above

            // Neither fits (container fills the view): pin to the bottom.
            return Math.max(edge, sceneH - height - edge)
        }

        width: toolRow.implicitWidth + 12
        height: toolRow.implicitHeight + 10

        visible: root.adjusting

        color: "#303030"
        border.color: "#e0a84c"
        radius: 4

        // Above every object on the canvas.
        z: 2000000

        // Absorb clicks between buttons so they don't deselect.
        MouseArea {
            anchors.fill: parent
        }

        Row {
            id: toolRow

            anchors.centerIn: parent

            spacing: 4

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
