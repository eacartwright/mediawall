import QtQuick
import QtQuick.Controls

// The Library's file grid: large thumbnails, row after row. Delegates are
// reused as it scrolls, so a tile holds nothing of its own: selection is
// in the model (bridge/library_model.py), and it asks for a thumbnail
// just by showing one.
//
// Nothing plays across the grid (section 44.4). There is one player, which
// moves to whichever tile is playing: so at most one file ever decodes.
// A file that moves plays muted while hovered; Ctrl+Space plays the current
// file with sound, and hovering waits until that stops.

Rectangle {
    id: pane

    color: "#1b1b1b"

    required property var files

    signal focusReturned()

    // Ctrl+Space: play the current file with sound, or pause it.
    function togglePlay() {
        var row = tagLibrary.currentRow
        if (row < 0)
            return
        if (tilePlayer.row === row && tilePlayer.withSound) {
            tilePlayer.paused = !tilePlayer.paused
            return
        }
        var file = tagLibrary.fileAt(row)
        if (file.type === "image" && !file.animatable)
            return
        grid.positionViewAtIndex(row, GridView.Contain)
        tilePlayer.start(row, true)
    }

    GridView {
        id: grid
        objectName: "libraryGrid"                        // found by tests/app

        anchors.fill: parent
        anchors.margins: 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        reuseItems: true
        cacheBuffer: 300

        model: pane.files

        // As many tiles as fit, shared out to fill the row.
        readonly property int columns: Math.max(1, Math.floor(width / appSettings.libraryTileSize))
        cellWidth: Math.floor(width / columns)
        cellHeight: cellWidth + 22

        // Scrolling moves other tiles under the pointer: not a reason to play them.
        onContentYChanged: tilePlayer.hoverEnded(-1)

        delegate: Item {
            id: tile

            required property int index
            required property string path
            required property string name
            required property string mediaType
            required property string thumb
            required property string badge
            required property bool moves
            required property bool failed
            required property bool selected
            required property bool current
            required property bool tagged

            readonly property bool isAudio: mediaType === "audio"

            width: GridView.view.cellWidth
            height: GridView.view.cellHeight

            Rectangle {
                anchors.fill: parent
                anchors.margins: 3
                radius: 3
                color: tile.selected ? "#2f4a66" : "#2a2a2a"
                border.width: tile.current ? 2 : tile.selected ? 1 : 0
                border.color: "#6aa6e8"

                Image {
                    id: picture

                    anchors.fill: parent
                    anchors.margins: 4
                    anchors.bottomMargin: 22
                    source: tile.thumb
                    asynchronous: true
                    fillMode: Image.PreserveAspectFit
                }

                // What's in the picture's place until there is one.
                Text {
                    anchors.centerIn: picture
                    visible: !tile.isAudio && picture.status !== Image.Ready
                    text: tile.failed ? "Can't display file" : "…"
                    color: "#888888"
                }

                // Audio has no picture.
                Text {
                    anchors.centerIn: picture
                    visible: tile.isAudio
                    text: "♪"
                    color: "#9fb4d8"
                    font.pixelSize: 40
                }

                Text {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 4
                    text: tile.name
                    color: "#dddddd"
                    font.pixelSize: 11
                    elide: Text.ElideMiddle
                    horizontalAlignment: Text.AlignHCenter
                }

                // The type and length: "GIF 0:04", "1:30".
                Rectangle {
                    objectName: "tileBadge"
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.margins: 6
                    width: badgeText.implicitWidth + 8
                    height: badgeText.implicitHeight + 2
                    radius: 2
                    visible: tile.badge !== ""
                    color: "#c0000000"

                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: tile.badge
                        color: "#ffffff"
                        font.pixelSize: 11
                    }
                }

                // Has tags: shows what's left to do.
                Rectangle {
                    objectName: "tileTagged"
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 6
                    width: 12
                    height: 12
                    radius: 6
                    visible: tile.tagged
                    color: "#4caf50"
                    border.color: "#1b1b1b"
                }
            }

            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                onContainsMouseChanged: {
                    if (containsMouse && tile.moves)
                        tilePlayer.hoverStarted(tile.index)
                    else if (!containsMouse)
                        tilePlayer.hoverEnded(tile.index)
                }
                onClicked: function(mouse) {
                    tagLibrary.clickFile(tile.index,
                                         (mouse.modifiers & Qt.ControlModifier) !== 0,
                                         (mouse.modifiers & Qt.ShiftModifier) !== 0)
                    pane.focusReturned()
                }
            }
        }

        ScrollBar.vertical: ScrollBar {}

        // Stepping by keyboard keeps the file in view; moving on stops what
        // Ctrl+Space started.
        Connections {
            target: tagLibrary
            function onCurrentRowChanged(row) {
                if (tilePlayer.withSound && row !== tilePlayer.row)
                    tilePlayer.stop()
                if (row >= 0)
                    grid.positionViewAtIndex(row, GridView.Contain)
            }
        }

        // The list changed, so the row may now be another file.
        Connections {
            target: pane.files
            function onModelReset() { tilePlayer.stop() }
        }

        Text {
            anchors.centerIn: parent
            visible: grid.count === 0
            color: "#888888"
            text: tagLibrary.scanning ? "Scanning…"
                  : tagLibrary.folder === "" ? "Choose a folder on the left"
                  : tagLibrary.untaggedOnly ? "Nothing untagged here"
                  : "No media in this folder"
        }
    }

    // ---- The one player ----

    // Worked out from the row, not from a delegate, which scrolling may
    // reuse or destroy. In the grid's content, so it scrolls with the tiles.
    Item {
        id: tilePlayer
        objectName: "libraryPlayer"                      // found by tests/app

        parent: grid.contentItem
        z: 1

        property int row: -1
        property bool withSound: false
        property bool paused: false
        property var file: ({})

        readonly property var view: loader.item
        visible: row >= 0
        x: (row % grid.columns) * grid.cellWidth + 7
        y: Math.floor(row / grid.columns) * grid.cellHeight + 7
        width: grid.cellWidth - 14
        height: grid.cellHeight - 36

        function start(newRow, sound) {
            hoverDelay.stop()
            loader.active = false            // from the start, in a player of its own
            file = tagLibrary.fileAt(newRow)
            row = newRow
            withSound = sound
            paused = false
            loader.active = true
        }

        function stop() {
            hoverDelay.stop()
            release()
        }

        function release() {
            loader.active = false
            row = -1
            withSound = false
            paused = false
        }

        function hoverStarted(newRow) {
            if (withSound)
                return
            hoverDelay.row = newRow
            hoverDelay.restart()
        }

        // -1: whatever is hovered. Moving between tiles enters the new one
        // before leaving the old, so leaving must not touch what's starting.
        function hoverEnded(oldRow) {
            if (withSound)
                return
            if (oldRow === -1 || hoverDelay.row === oldRow)
                hoverDelay.stop()
            if (oldRow === -1 || row === oldRow)
                release()
        }

        // So the pointer crossing tiles doesn't start a decoder for each.
        Timer {
            id: hoverDelay
            property int row: -1
            interval: 250
            onTriggered: tilePlayer.start(row, false)
        }

        Loader {
            id: loader

            anchors.fill: parent
            active: false

            sourceComponent: MediaView {
                url: tilePlayer.file.url
                type: tilePlayer.file.type
                animatable: tilePlayer.file.animatable
                name: tilePlayer.file.name
                path: tilePlayer.file.path
                playing: !tilePlayer.paused
                muted: !tilePlayer.withSound
                loop: true
                showErrorState: false            // the tile says so already
                memoryPlace: "library"
            }
        }
    }
}
