import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Browse Object: a workspace object for browsing a folder on the canvas.
//
// The model stores the folder and current index (so browsing state can
// be restored). The file list itself is rescanned from the folder.

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

    readonly property bool selected: sceneModel.selectedId === objectId

    x: posX
    y: posY
    width: objWidth
    height: objHeight
    rotation: objRotation
    z: objZ

    color: "#292929"

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
    onCurrentPathChanged: previewPlaying = true

    // Relative path, so you can see which subfolder a file is in.
    readonly property string currentFileName:
        currentEntry ? currentEntry.relpath : ""

    readonly property string folderName: {
        if (folder === "")
            return "Browse Object"

        var parts = folder.split(/[\\/]/).filter(function(p) { return p !== "" })
        return parts.length > 0 ? parts[parts.length - 1] : folder
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
    // Dragging (below all browser content)
    // -------------------------------------------------

    MouseArea {
        id: dragArea

        anchors.fill: parent

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
                Layout.fillWidth: true

                text: root.folderName

                color: "#eeeeee"
                font.pixelSize: 14
                elide: Text.ElideRight
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
        }
    }


    // -------------------------------------------------
    // Preview
    // -------------------------------------------------

    Rectangle {
        id: previewArea

        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: controls.top
        anchors.leftMargin: 1
        anchors.rightMargin: 1

        color: "#202020"

        MediaView {
            id: previewView

            anchors.fill: parent
            anchors.margins: 8

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

        Text {
            anchors.centerIn: parent
            width: parent.width - 24

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

            color: "#888888"
            font.pixelSize: 15
        }

        // Mouse wheel navigation
        MouseArea {
            anchors.fill: parent

            acceptedButtons: Qt.NoButton

            onWheel: function(wheel) {
                if (wheel.angleDelta.y > 0)
                    root.previousMedia()
                else if (wheel.angleDelta.y < 0)
                    root.nextMedia()
            }
        }

        VideoControls {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 6

            visible: root.currentIsPlayer

            view: previewView
            playing: root.previewPlaying
            muted: root.previewMuted

            onTogglePlay: root.previewPlaying = !root.previewPlaying
            onToggleMute: root.previewMuted = !root.previewMuted
        }
    }


    // -------------------------------------------------
    // Controls
    // -------------------------------------------------

    Rectangle {
        id: controls

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 1

        height: 64

        color: "#303030"

        RowLayout {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top

            anchors.leftMargin: 20
            anchors.rightMargin: 20
            anchors.topMargin: 5

            spacing: 6

            Button {
                text: "◀"
                enabled: root.mediaFiles.length > 0
                onClicked: root.previousMedia()
            }

            Button {
                text: "▶"
                enabled: root.mediaFiles.length > 0
                onClicked: root.nextMedia()
            }

            Button {
                text: "Add to Canvas"
                enabled: root.canPlace
                onClicked: root.addCurrentToCanvas()
            }

            // Only while a container is selected (readme 9.3).
            Button {
                text: "Add to Container"

                visible: sceneModel.selectedType === "container"
                enabled: root.canPlace

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

                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideMiddle
            }
        }

        Text {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom

            anchors.leftMargin: 20
            anchors.rightMargin: 20
            anchors.bottomMargin: 5

            text: root.currentFileName

            color: "#999999"
            font.pixelSize: 11

            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideMiddle
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
