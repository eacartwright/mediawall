import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Zoom.js" as Zoom

// Browse Object: a workspace object for browsing a folder on the canvas.
//
// The model stores the folder and current index (so browsing state can
// be restored). The file list itself is rescanned from the folder.
//
// Layout: a header (drag it to move the browser) above a see-through
// preview, with the navigation buttons overlaid on the preview's bottom
// edge. Browsers always draw above other canvas objects.

Rectangle {
    id: root

    // ---- Model roles ----
    required property string objectId
    required property real posX
    required property real posY
    required property real objWidth
    required property real objHeight
    required property real objRotation
    required property int objZ
    required property string folder
    required property int currentIndex
    required property bool includeSubfolders
    required property string mediaFilter        // "all" or a media type

    property Item sceneItem

    // Shared right-click menu (ObjectContextMenu in Main.qml).
    property var contextMenu

    // Present mode: browsers keep working, but without selection
    // outline or handles.
    readonly property bool presenting: sceneItem ? sceneItem.presenting : false

    readonly property bool selected:
        !presenting && sceneModel.selectedId === objectId

    x: posX
    y: posY
    width: objWidth
    height: objHeight
    rotation: objRotation

    // Always above other objects (they use z 1..count). Browsers still
    // stack among themselves by objZ. Adjust-mode toolbars sit higher.
    z: 1000000 + objZ

    // Mostly see-through behind the media, so the canvas shows.
    color: "transparent"

    border.color: selected ? "#5da9ff" : "#555555"
    border.width: 1


    // -------------------------------------------------
    // Transient state (not saved; rebuilt from folder)
    // -------------------------------------------------

    // Each entry: { path, url, name, type }
    property var mediaFiles: []


    // -------------------------------------------------
    // Derived state
    // -------------------------------------------------

    // The model's index, clamped to what's actually in the folder now.
    readonly property int displayIndex:
        mediaFiles.length === 0
        ? -1
        : Math.max(0, Math.min(currentIndex, mediaFiles.length - 1))

    readonly property var currentEntry:
        displayIndex >= 0 ? mediaFiles[displayIndex] : null

    // Images and videos can be placed on the canvas; audio goes to the
    // Audio Rack (coming next).
    readonly property bool canPlace:
        currentEntry !== null &&
        (currentEntry.type === "image" || currentEntry.type === "video")

    // Audio files are added as tracks in the sidebar's Playback tab.
    readonly property bool currentIsAudio:
        currentEntry !== null && currentEntry.type === "audio"

    readonly property bool canAdd: canPlace || currentIsAudio

    readonly property bool currentIsPlayer:
        currentEntry !== null &&
        (currentEntry.type === "video" || currentEntry.type === "audio")

    // Preview playback state (workspace only, not saved).
    property bool previewPlaying: true
    property bool previewMuted: true

    // Audio previews are audible by default (there's nothing to see).
    property bool previewAudioMuted: false
    readonly property bool currentMuted:
        currentIsAudio ? previewAudioMuted : previewMuted

    function toggleMute() {
        if (currentIsAudio)
            previewAudioMuted = !previewAudioMuted
        else
            previewMuted = !previewMuted
    }

    // Every file starts playing when you move to it. Otherwise pausing
    // a video would leave later GIFs frozen, with no button to restart
    // them. Mute carries over. Keyed on the path so a rescan that keeps
    // the same file doesn't restart it.
    readonly property string currentPath: currentEntry ? currentEntry.path : ""
    onCurrentPathChanged: {
        previewPlaying = true
        resetZoom()
    }

    // Relative path, so you can see which subfolder a file is in.
    readonly property string currentFileName:
        currentEntry ? currentEntry.relpath : ""

    readonly property string folderName: {
        if (folder === "")
            return "Browse Object"

        var parts = folder.split(/[\\/]/).filter(function(p) { return p !== "" })
        return parts.length > 0 ? parts[parts.length - 1] : folder
    }

    // -------------------------------------------------
    // Preview zoom (transient; resets when the file changes)
    //
    // The media box is the preview's inset area scaled by previewZoom,
    // with its center moved by (panX, panY).
    // -------------------------------------------------

    property real previewZoom: 1
    property real panX: 0
    property real panY: 0

    readonly property real maxPreviewZoom: 20

    function resetZoom() {
        previewZoom = 1
        panX = 0
        panY = 0
    }

    // Zoom by factor f around (px, py) in preview coordinates.
    function zoomPreviewAt(px, py, f) {
        var newZoom = Math.max(1, Math.min(maxPreviewZoom, previewZoom * f))
        if (newZoom === 1) {
            resetZoom()
            return
        }

        var k = newZoom / previewZoom
        var baseCX = previewFrame.width / 2
        var baseCY = previewFrame.height / 2
        var cx = baseCX + panX
        var cy = baseCY + panY

        panX = px + (cx - px) * k - baseCX
        panY = py + (cy - py) * k - baseCY
        previewZoom = newZoom
    }

    // With a filter (right-click menu), it says which type, e.g. "2 / 3 videos".
    readonly property string positionText: {
        var kind = { "image": "images", "video": "videos", "audio": "audio files" }[mediaFilter]
        if (mediaFiles.length === 0)
            return kind ? "No " + kind : "No media"
        return (displayIndex + 1) + " / " + mediaFiles.length + (kind ? " " + kind : "")
    }

    // Used by the context menu.
    readonly property bool isBrowser: true


    // -------------------------------------------------
    // Model sync
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
    }

    function rescan() {
        // Remember what we were looking at, so toggling subfolders
        // doesn't throw you back to the first file.
        var previousPath = currentEntry ? currentEntry.path : ""

        var filter = mediaFilter
        mediaFiles = folder !== ""
                     ? browserBackend.scanFolder(folder, includeSubfolders)
                         .filter(function(e) { return filter === "all" || e.type === filter })
                     : []

        if (previousPath === "")
            return

        for (var i = 0; i < mediaFiles.length; i++) {
            if (mediaFiles[i].path === previousPath) {
                if (i !== currentIndex)
                    sceneModel.setBrowserIndex(objectId, i)
                return
            }
        }

        // The file shown is gone from the list (e.g. filtered out):
        // start from the first one.
        if (currentIndex !== 0)
            sceneModel.setBrowserIndex(objectId, 0)
    }

    onFolderChanged: rescan()
    onIncludeSubfoldersChanged: rescan()
    onMediaFilterChanged: rescan()
    Component.onCompleted: rescan()


    // -------------------------------------------------
    // Actions
    // -------------------------------------------------

    function loadFolder(newFolder) {
        sceneModel.setBrowserState(objectId, newFolder, 0)
    }

    function nextMedia() {
        if (mediaFiles.length === 0)
            return

        sceneModel.setBrowserIndex(
            objectId, (displayIndex + 1) % mediaFiles.length
        )
    }

    // Left/Right arrow keys (AppActions), thumb buttons, and the
    // horizontal wheel all step through the files.
    readonly property bool stepsFiles: true

    function stepFiles(delta) {
        if (delta < 0)
            previousMedia()
        else
            nextMedia()
    }

    FileStepper {
        id: fileStepper
        step: root.stepFiles
    }

    function previousMedia() {
        if (mediaFiles.length === 0)
            return

        sceneModel.setBrowserIndex(
            objectId,
            (displayIndex - 1 + mediaFiles.length) % mediaFiles.length
        )
    }

    // An audio file, or a video used only for its sound, becomes a track
    // in the Playback tab.
    function addCurrentToAudio() {
        if (!currentIsAudio && !(currentEntry && currentEntry.type === "video"))
            return
        sceneModel.addAudioTrack(currentEntry.path, currentEntry.type)
        previewPlaying = false      // don't play it twice
    }

    // Images and videos go on the canvas; audio becomes a track.
    function addCurrentToCanvas() {
        if (currentIsAudio) {
            addCurrentToAudio()
            return
        }

        if (!canPlace)
            return

        var p = placementBeside(newMediaWidth)
        sceneModel.addMedia(currentEntry.path, currentEntry.type, p.x, p.y)
    }

    // The current image or video in a new container of its own, placed
    // like Add to Canvas.
    function addCurrentInNewContainer() {
        if (!canPlace)
            return

        var p = placementBeside(newMediaWidth)
        sceneModel.addMediaInNewContainer(currentEntry.path, currentEntry.type, p.x, p.y)
    }

    // ---- Where new media goes: beside the browser ----
    //
    // To the right of a browser in the left half of the canvas, to the
    // left of one in the right half (switching sides if that side has
    // too little room and the other has more), level with its top.
    // Repeated adds step down and outward so they don't pile up exactly.

    readonly property real newMediaWidth: 300     // core DEFAULT_MEDIA_WIDTH
    property int placeCount: 0                     // this session

    function placementBeside(w) {
        var sceneW = sceneItem ? sceneItem.width : 1280
        var sceneH = sceneItem ? sceneItem.height : 800
        var gap = 16

        // On-screen bounds (a browser may be rotated about its center).
        var r = rotation * Math.PI / 180
        var halfW = Math.abs(width / 2 * Math.cos(r)) + Math.abs(height / 2 * Math.sin(r))
        var halfH = Math.abs(width / 2 * Math.sin(r)) + Math.abs(height / 2 * Math.cos(r))
        var cx = x + width / 2
        var cy = y + height / 2

        var roomRight = sceneW - (cx + halfW) - gap
        var roomLeft = (cx - halfW) - gap

        var right = cx < sceneW / 2
        if (right && roomRight < w && roomLeft > roomRight)
            right = false
        else if (!right && roomLeft < w && roomRight > roomLeft)
            right = true

        var step = (placeCount % 8) * 24
        placeCount++

        var px = right ? cx + halfW + gap + step : cx - halfW - gap - w - step
        var py = cy - halfH + step

        return Qt.point(Math.max(0, Math.min(sceneW - w, px)),
                        Math.max(0, Math.min(sceneH - 60, py)))
    }


    // -------------------------------------------------
    // Dragging: by the header only (below its controls)
    // -------------------------------------------------

    MouseArea {
        id: dragArea

        anchors.fill: header

        z: -1

        property point startMouse
        property point startPos

        acceptedButtons: Qt.LeftButton | Qt.RightButton

        // True only while a left-button drag is in progress.
        property bool dragging: false

        onPressed: function(mouse) {
            if (mouse.button === Qt.RightButton) {
                dragging = false
                sceneModel.select(root.objectId)
                if (root.contextMenu)
                    root.contextMenu.openFor(root)
                return
            }

            dragging = true
            sceneModel.select(root.objectId)

            startMouse = dragArea.mapToItem(root.sceneItem, mouse.x, mouse.y)
            startPos = Qt.point(root.x, root.y)
        }

        onPositionChanged: function(mouse) {
            if (!pressed || !dragging)
                return

            var p = dragArea.mapToItem(root.sceneItem, mouse.x, mouse.y)

            root.x = startPos.x + (p.x - startMouse.x)
            root.y = startPos.y + (p.y - startMouse.y)
        }

        onReleased: {
            if (dragging)
                root.commit()
            dragging = false
        }
    }


    // -------------------------------------------------
    // Header
    // -------------------------------------------------

    Rectangle {
        id: header

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 1

        height: 36

        color: "#383838"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 22
            anchors.rightMargin: 20

            spacing: 4

            Text {
                Layout.maximumWidth: implicitWidth

                // Shrinks (elides) before the filename does.
                Layout.fillWidth: true
                Layout.horizontalStretchFactor: 1

                text: root.folderName

                color: "#eeeeee"
                font.pixelSize: 14
                elide: Text.ElideRight
            }

            // Relative path, so you can see which subfolder a file is in.
            Text {
                Layout.fillWidth: true
                Layout.horizontalStretchFactor: 3

                visible: text !== ""
                text: root.currentFileName

                color: "#999999"
                font.pixelSize: 12
                elide: Text.ElideMiddle
            }

            // Indicator-only checkbox plus our own label, so the text
            // stays readable on the dark header in every Qt style.
            CheckBox {
                id: subfolderCheck

                checked: root.includeSubfolders

                onToggled: {
                    sceneModel.setBrowserSubfolders(root.objectId, checked)

                    // Clicking breaks the binding; restore it so the
                    // label and future model changes keep it in sync.
                    checked = Qt.binding(function() {
                        return root.includeSubfolders
                    })
                }
            }

            Text {
                text: "Subfolders"

                color: "#cccccc"
                font.pixelSize: 12

                TapHandler {
                    onTapped: sceneModel.setBrowserSubfolders(
                        root.objectId, !root.includeSubfolders
                    )
                }
            }

            Button {
                Layout.preferredHeight: 26

                text: "Choose Folder"

                onClicked: {
                    var chosen = browserBackend.chooseFolder()

                    if (chosen !== "")
                        root.loadFolder(chosen)
                }
            }

            // Close = delete (a browser is a workspace object; undoable).
            Button {
                Layout.preferredWidth: 26
                Layout.preferredHeight: 26

                text: "✕"

                onClicked: sceneModel.removeObject(root.objectId)
            }
        }
    }


    // -------------------------------------------------
    // Preview (qView-style)
    //
    // Wheel: zoom around the pointer; left-drag pans while zoomed.
    // Back/forward mouse buttons: previous/next file. Double-click:
    // add to canvas.
    // -------------------------------------------------

    Rectangle {
        id: previewFrame

        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 1
        anchors.rightMargin: 1
        anchors.bottomMargin: 1

        // About 60% transparent: #AARRGGBB, where AA is the opacity
        // (00 = clear, ff = solid; 80 = 50% opaque, 66 = 40%, 4d = 30%, 33 = 20%) and 202020 the gray.
        color: "#66202020"

        clip: true

        // The inset area the media fits into at zoom 1.
        readonly property real inset: 8
        readonly property real baseW: width - 2 * inset
        readonly property real baseH: height - 2 * inset

        MediaView {
            id: previewView
            objectName: "browserPreview"         // found by tests/app

            width: previewFrame.baseW * root.previewZoom
            height: previewFrame.baseH * root.previewZoom
            x: previewFrame.width / 2 + root.panX - width / 2
            y: previewFrame.height / 2 + root.panY - height / 2

            visible: root.currentEntry !== null

            url: root.currentEntry ? root.currentEntry.url : ""
            type: root.currentEntry ? root.currentEntry.type : "image"
            animatable: root.currentEntry ? root.currentEntry.animatable : false
            name: root.currentEntry ? root.currentEntry.name : ""
            path: root.currentEntry ? root.currentEntry.path : ""

            playing: root.previewPlaying
            muted: root.currentMuted
            loop: true
        }

        // Backing for the message, since the preview is see-through.
        Rectangle {
            anchors.fill: emptyText
            anchors.margins: -12

            visible: emptyText.visible

            color: "#cc202020"
            radius: 4
        }

        Text {
            id: emptyText

            anchors.centerIn: parent
            width: parent.width - 48

            visible: root.currentEntry === null

            wrapMode: Text.WrapAnywhere

            text: {
                if (root.folder === "")
                    return "Choose a folder to browse media"

                if (root.mediaFiles.length === 0)
                    return browserBackend.folderExists(root.folder)
                           ? "No media found in this folder"
                           : "Folder not found:\n" + root.folder

                return "No media selected"
            }

            horizontalAlignment: Text.AlignHCenter

            color: "#aaaaaa"
            font.pixelSize: 15
        }

        MouseArea {
            id: previewArea

            anchors.fill: parent

            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.BackButton | Qt.ForwardButton

            property point startMouse
            property point startPan

            onPressed: function(mouse) {
                if (mouse.button === Qt.BackButton || mouse.button === Qt.ForwardButton) {
                    fileStepper.begin(mouse.button === Qt.BackButton ? -1 : 1)
                    return
                }

                sceneModel.select(root.objectId)

                if (mouse.button === Qt.RightButton) {
                    if (root.contextMenu)
                        root.contextMenu.openFor(root)
                    return
                }

                startMouse = Qt.point(mouse.x, mouse.y)
                startPan = Qt.point(root.panX, root.panY)
            }

            onPositionChanged: function(mouse) {
                if (!(pressedButtons & Qt.LeftButton) || root.previewZoom === 1)
                    return

                root.panX = startPan.x + (mouse.x - startMouse.x)
                root.panY = startPan.y + (mouse.y - startMouse.y)
            }

            onReleased: fileStepper.end()
            onCanceled: fileStepper.end()

            onDoubleClicked: function(mouse) {
                if (mouse.button === Qt.LeftButton)
                    root.addCurrentToCanvas()
            }

            // Audio has nothing to zoom or pan: it stays centered.
            onWheel: function(wheel) {
                if (fileStepper.wheel(wheel.angleDelta))
                    return
                if (wheel.angleDelta.y !== 0 && !root.currentIsAudio)
                    root.zoomPreviewAt(wheel.x, wheel.y,
                                       Zoom.wheelFactor(wheel.angleDelta.y, appSettings.zoomStep))
            }
        }


        // ---- Overlays on the preview's bottom edge ----

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 20       // clear of the corner handles
            anchors.rightMargin: 20
            anchors.bottomMargin: 6

            spacing: 4

            VideoControls {
                width: parent.width

                visible: root.currentIsPlayer

                view: previewView
                playing: root.previewPlaying
                muted: root.currentMuted

                onTogglePlay: root.previewPlaying = !root.previewPlaying
                onToggleMute: root.toggleMute()
            }

            Rectangle {
                width: parent.width
                height: navRow.implicitHeight + 8

                color: "#dd202020"
                radius: 4

                // Absorb clicks between the buttons (so they don't pan
                // or add to canvas); the wheel still navigates.
                MouseArea {
                    anchors.fill: parent
                }

                RowLayout {
                    id: navRow

                    anchors.fill: parent
                    anchors.leftMargin: 4
                    anchors.rightMargin: 8

                    spacing: 4

                    Button {
                        Layout.preferredHeight: 26
                        Layout.preferredWidth: 36     // leave room for the Add buttons
                        text: "◀"
                        autoRepeat: true                // hold to keep stepping
                        enabled: root.mediaFiles.length > 0
                        onClicked: root.previousMedia()
                    }

                    Button {
                        Layout.preferredHeight: 26
                        Layout.preferredWidth: 36     // leave room for the Add buttons
                        text: "▶"
                        autoRepeat: true
                        enabled: root.mediaFiles.length > 0
                        onClicked: root.nextMedia()
                    }

                    Button {
                        Layout.preferredHeight: 26
                        text: root.currentIsAudio ? "Add to Audio" : "Add to Canvas"
                        enabled: root.canAdd
                        onClicked: root.addCurrentToCanvas()
                    }

                    Button {
                        Layout.preferredHeight: 26
                        text: "New Container"
                        visible: !root.currentIsAudio
                        enabled: root.canPlace
                        onClicked: root.addCurrentInNewContainer()
                    }

                    // Video as audio: the sound only, as a track.
                    Button {
                        Layout.preferredHeight: 26
                        text: "Add to Audio"
                        visible: root.currentEntry !== null && root.currentEntry.type === "video"
                        onClicked: root.addCurrentToAudio()
                    }

                    // Only while a container is selected (readme 9.3).
                    Button {
                        Layout.preferredHeight: 26

                        text: "Add to Container"

                        visible: sceneModel.selectedType === "container"

                        // A full container must be emptied first.
                        enabled: root.canPlace && !sceneModel.selectedHasContent

                        onClicked: sceneModel.addMediaToContainer(
                            root.currentEntry.path,
                            root.currentEntry.type,
                            sceneModel.selectedId
                        )
                    }

                    Label {
                        Layout.fillWidth: true

                        text: root.positionText

                        color: "#cccccc"

                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight         // keep the numbers when space is short
                    }
                }
            }
        }
    }


    // -------------------------------------------------
    // Resize handles
    // -------------------------------------------------

    ResizeHandles {
        visible: root.selected

        target: root
        sceneItem: root.sceneItem

        minWidth: 380
        minHeight: 180

        color: "#888888"

        onStarted: sceneModel.select(root.objectId)
        onFinished: root.commit()
    }
}
