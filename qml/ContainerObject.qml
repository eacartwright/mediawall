import QtQuick
import QtQuick.Controls
import "Zoom.js" as Zoom

// Container: a viewport holding one media instance, clipped to its shape.
//
// Every container works like a picture viewer (qView): left-drag pans
// the picture, the wheel zooms it, double-click resets the zoom. The
// border strip (move cursor) moves the container on a left-drag and
// scales it on the wheel; a middle-button drag moves it too. An empty
// container moves and scales from anywhere. Handles resize; the knob
// rotates (with Ctrl: the picture inside). Pan and zoom also work in
// Present.
// Browsing:     back/forward mouse buttons (and more) step through a
//               folder's media (right-click > Browse This Folder).
// Adjust mode:  (right-click > Adjust Content...) the knob turns the
//               picture, and the part outside the frame shows as a ghost.
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
    required property string mediaFilter        // "all", "image", or "video"

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

    // Present mode: never shown as selected, and the container can't be
    // moved or scaled, but its picture still zooms and pans (and a
    // browsing one steps through files). An empty one is disabled, so
    // clicks reach the canvas (double-click there exits).
    readonly property bool presenting: sceneItem ? sceneItem.presenting : false
    enabled: !presenting || hasContent

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

        function onBrowseFolderChosen(containerId) {
            if (containerId === root.objectId)
                root.startAtFirstFile = true
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
        var filter = mediaFilter
        browseFiles = browserBackend.scanFolder(browseFolder, browseSubfolders)
            .filter(function(e) {
                return (e.type === "image" || e.type === "video")
                       && (filter === "all" || e.type === filter)
            })

        // An empty container starts on the folder's first file, rather
        // than sitting empty until the first step. So does one given a
        // new folder (Browse Folder…) that doesn't hold its current file.
        // Decided once the model's changes have all arrived (browse mode
        // and folder update one at a time).
        if (!hasContent || startAtFirstFile)
            Qt.callLater(showFirstFileIfNeeded)
    }

    // Set by Browse Folder… just before the folder changes.
    property bool startAtFirstFile: false

    function showFirstFileIfNeeded() {
        var first = !hasContent || (startAtFirstFile && browseIndex < 0)
        startAtFirstFile = false
        if (first && browseMode && browseFiles.length > 0)
            sceneModel.showInContainer(objectId, browseFiles[0].path, browseFiles[0].type)
    }

    onBrowseModeChanged: rescanBrowse()
    onBrowseFolderChanged: rescanBrowse()
    onBrowseSubfoldersChanged: rescanBrowse()
    // A new filter that hides the file shown moves on to the first one.
    onMediaFilterChanged: {
        startAtFirstFile = true
        rescanBrowse()
    }

    readonly property int browseIndex: {
        for (var i = 0; i < browseFiles.length; i++) {
            if (browseFiles[i].path === contentSourcePath)
                return i
        }
        return -1
    }

    // A browsing container moves by this band just inside its edge (or
    // by a middle-button drag); elsewhere left-drag pans the picture.
    readonly property real borderStrip: 10

    function inBorderStrip(px, py) {
        return px < borderStrip || py < borderStrip
               || px > width - borderStrip || py > height - borderStrip
    }

    // Left/Right arrow keys (AppActions), thumb buttons, and the
    // horizontal wheel step through the folder while browsing.
    readonly property bool stepsFiles: browseMode

    function stepFiles(delta) {
        browseStep(delta)
    }

    FileStepper {
        id: fileStepper
        step: root.browseStep
    }

    // -1 = previous, +1 = next, wrapping around (as in a browser).
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

            text: "Empty container\n\nDouble-click to browse a folder, drag an image "
                  + "or video onto it, or select it and use a browser's Add to Container"

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

    // Selection / adjust outline, or a faint one while empty. A filled,
    // unselected container has none, so a wall reads as pictures, not boxes.
    Rectangle {
        anchors.fill: parent

        visible: root.selected || root.adjusting
                 || (!root.hasContent && !root.presenting)
        color: "transparent"

        border.color: root.adjusting ? "#e0a84c"
                      : root.selected ? "#7fc97f"
                      : "#555555"
        border.width: root.adjusting ? 2 : 1

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
    // Mouse (qView-style, browsing or not): left-drag pans the picture,
    // the wheel zooms it around the pointer, double-click resets it to
    // the Fit/Fill framing. The container itself moves by its border
    // strip (move cursor) or a middle-button drag, and the wheel on the
    // border strip scales it. An empty container moves and scales from
    // anywhere. None of this needs the container to be selected.
    // -------------------------------------------------

    MouseArea {
        id: area

        anchors.fill: parent

        z: 10

        // Browsing containers also step through files with the
        // back/forward buttons. In Present only pan, zoom, and stepping
        // respond.
        acceptedButtons: {
            if (root.presenting)
                return Qt.LeftButton
                       | (root.browseMode ? Qt.BackButton | Qt.ForwardButton : 0)
            return Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                   | Qt.BackButton | Qt.ForwardButton
        }

        // The move cursor shows where a left-drag moves the container
        // (and the wheel scales it).
        hoverEnabled: !root.presenting
        cursorShape: hoverEnabled && movesAt(mouseX, mouseY)
                     ? Qt.SizeAllCursor : Qt.ArrowCursor

        // Over the border strip, or anywhere on an empty container
        // (never while adjusting, where every drag pans).
        function movesAt(px, py) {
            return !root.adjusting && !root.presenting
                   && (!root.hasContent || root.inBorderStrip(px, py))
        }

        property string mode: ""      // "move" | "pan" | ""
        property point startMouse
        property point startPos

        function startMove(mouse) {
            mode = "move"
            startMouse = area.mapToItem(root.sceneItem, mouse.x, mouse.y)
            startPos = Qt.point(root.x, root.y)
        }

        // The container doesn't move while panning, so local mouse
        // coordinates are stable.
        function startPan(mouse) {
            mode = "pan"
            startMouse = Qt.point(mouse.x, mouse.y)
            startPos = Qt.point(cg.cx, cg.cy)
        }

        onPressed: function(mouse) {
            mode = ""

            if (mouse.button === Qt.BackButton || mouse.button === Qt.ForwardButton) {
                if (root.browseMode)
                    fileStepper.begin(mouse.button === Qt.BackButton ? -1 : 1)
                else
                    mouse.accepted = false
                return
            }

            if (!root.presenting)
                sceneModel.select(root.objectId)

            if (mouse.button === Qt.RightButton) {
                if (root.contextMenu)
                    root.contextMenu.openFor(root)
                return
            }

            if (mouse.button === Qt.MiddleButton) {
                if (!root.adjusting)
                    startMove(mouse)
                return
            }

            // Left button
            if (movesAt(mouse.x, mouse.y))
                startMove(mouse)
            else if (root.hasContent)
                startPan(mouse)
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

        onCanceled: fileStepper.end()

        onReleased: {
            fileStepper.end()
            if (mode === "move")
                root.commit()
            else if (mode === "pan")
                root.commitContent()
            mode = ""
        }

        // Reset the zoom (the container's Fit/Fill framing). Empty (and
        // not yet browsing a folder): choose one to browse.
        onDoubleClicked: function(mouse) {
            if (mouse.button !== Qt.LeftButton)
                return
            if (!root.hasContent) {
                if (!root.presenting && !(root.browseMode && root.browseFolder !== ""))
                    sceneModel.startBrowsing(root.objectId)
                return
            }
            if (!movesAt(mouse.x, mouse.y))
                sceneModel.resetContentFraming(root.objectId)
        }

        // Zoom the picture around the pointer; on the border strip (or
        // an empty container), scale the whole container like a free
        // image.
        onWheel: function(wheel) {
            if (root.browseMode && fileStepper.wheel(wheel.angleDelta))
                return

            if (wheel.angleDelta.y === 0) {
                wheel.accepted = false
                return
            }

            var f = Zoom.wheelFactor(wheel.angleDelta.y, appSettings.zoomStep)

            if (!movesAt(wheel.x, wheel.y)) {
                if (root.hasContent)
                    root.zoomAt(wheel.x, wheel.y, f)
                else
                    wheel.accepted = false
                return
            }

            var p = area.mapToItem(root.sceneItem, wheel.x, wheel.y)
            sceneModel.setMergeKey("scale:" + root.objectId)
            sceneModel.scaleObject(root.objectId, p.x, p.y, f)
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

        // Like double-clicking a window's top edge in Windows: stretch
        // into the free space (up to neighbours, or the canvas edge).
        onEdgeDoubleClicked: function(sx, sy) {
            if (root.sceneItem)
                sceneModel.fillAlong(root.objectId, sy !== 0 ? "v" : "h",
                                     root.sceneItem.width, root.sceneItem.height)
        }
        onFinished: {
            // Commit first, so the content's new position arrives from
            // the model before the live preview switches off.
            root.commit()
            root.resizing = false
        }
    }


    // -------------------------------------------------
    // Rotation handle: rotates the container, or the content while
    // adjusting or when grabbed with Ctrl held.
    // -------------------------------------------------

    RotationHandle {
        id: rotationHandle

        visible: root.selected

        target: root
        sceneItem: root.sceneItem

        function turnsContent() {
            return root.hasContent
                   && (root.adjusting || (pressModifiers & Qt.ControlModifier) !== 0)
        }

        pivot: function() {
            return turnsContent()
                   ? root.mapToItem(root.sceneItem, cg.cx, cg.cy)
                   : root.mapToItem(root.sceneItem, root.width / 2, root.height / 2)
        }
        currentRotation: function() {
            return turnsContent() ? cg.rot : root.rotation
        }
        applyRotation: function(r) {
            if (turnsContent())
                cg.rot = r
            else
                root.rotation = r
        }

        onFinished: {
            if (turnsContent())
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
        mediaId: root.contentId
        playing: root.contentPlaying
        muted: root.contentMuted

        onTogglePlay: sceneModel.setPlaying(root.contentId, !root.contentPlaying)
        onToggleMute: sceneModel.setMuted(root.contentId, !root.contentMuted)
    }


    // -------------------------------------------------
    // Browsing badge (selected): marks a browsing container
    // -------------------------------------------------

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 12                 // just clear of the 9 px corner square

        width: Math.min(badgeText.implicitWidth + 12, parent.width - 24)
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
                  : "⇅"
            color: "#dddddd"
            font.pixelSize: 11
        }
    }


    // -------------------------------------------------
    // Adjust mode (right-click > Adjust Content..., or Crop / Zoom
    // Inside): the knob turns the picture, and the part outside the
    // frame shows as a ghost. Enter / Space, Esc, or clicking elsewhere
    // finish.
    // -------------------------------------------------

    Shortcut {
        enabled: root.adjusting
        sequences: ["Return", "Enter", "Space"]
        onActivated: root.adjusting = false
    }
}
