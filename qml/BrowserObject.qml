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
    border.width: selected ? 2 : 1


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

    readonly property bool currentIsPlayer:
        currentEntry !== null &&
        (currentEntry.type === "video" || currentEntry.type === "audio")

    // Preview playback state (workspace only, not saved).
    property bool previewPlaying: true
    property bool previewMuted: true

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

    readonly property string positionText:
        mediaFiles.length === 0
        ? "No media"
        : (displayIndex + 1) + " / " + mediaFiles.length


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

        mediaFiles = folder !== ""
                     ? browserBackend.scanFolder(folder, includeSubfolders)
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
    }

    onFolderChanged: rescan()
    onIncludeSubfoldersChanged: rescan()
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

    function previousMedia() {
        if (mediaFiles.length === 0)
            return

        sceneModel.setBrowserIndex(
            objectId,
            (displayIndex - 1 + mediaFiles.length) % mediaFiles.length
        )
    }

    function addCurrentToCanvas() {
        if (!canPlace)
            return

        sceneModel.addMedia(
            currentEntry.path,
            currentEntry.type,
            80 + Math.random() * 180,
            80 + Math.random() * 180
        )
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
    // Preview
    //
    // Wheel: previous/next file. Left button + wheel: zoom around the
    // pointer; left-drag pans while zoomed. Double-click: add to canvas.
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

        // About 90% transparent.
        color: "#1a202020"

        clip: true

        // The inset area the media fits into at zoom 1.
        readonly property real inset: 8
        readonly property real baseW: width - 2 * inset
        readonly property real baseH: height - 2 * inset

        MediaView {
            id: previewView

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
            muted: root.previewMuted
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

            acceptedButtons: Qt.LeftButton | Qt.RightButton

            property point startMouse
            property point startPan

            onPressed: function(mouse) {
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

            onDoubleClicked: function(mouse) {
                if (mouse.button === Qt.LeftButton)
                    root.addCurrentToCanvas()
            }

            onWheel: function(wheel) {
                if (wheel.angleDelta.y === 0)
                    return

                if (wheel.buttons & Qt.LeftButton) {
                    root.zoomPreviewAt(wheel.x, wheel.y,
                                       Zoom.wheelFactor(wheel.angleDelta.y))
                } else if (wheel.angleDelta.y > 0) {
                    root.previousMedia()
                } else {
                    root.nextMedia()
                }
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
                muted: root.previewMuted

                onTogglePlay: root.previewPlaying = !root.previewPlaying
                onToggleMute: root.previewMuted = !root.previewMuted
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
                        text: "◀"
                        enabled: root.mediaFiles.length > 0
                        onClicked: root.previousMedia()
                    }

                    Button {
                        Layout.preferredHeight: 26
                        text: "▶"
                        enabled: root.mediaFiles.length > 0
                        onClicked: root.nextMedia()
                    }

                    Button {
                        Layout.preferredHeight: 26
                        text: "Add to Canvas"
                        enabled: root.canPlace
                        onClicked: root.addCurrentToCanvas()
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
                        elide: Text.ElideLeft
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
