import QtQuick
import QtQuick.Controls

// The Library's file grid: large thumbnails, row after row. Delegates are
// reused as it scrolls, so a tile holds nothing of its own: selection is
// in the model (bridge/library_model.py), and it asks for a thumbnail
// just by showing one.

Rectangle {
    id: pane

    color: "#1b1b1b"

    required property var files

    signal focusReturned()

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

        delegate: Item {
            id: tile

            required property int index
            required property string path
            required property string name
            required property string thumb
            required property bool failed
            required property bool selected
            required property bool current
            required property bool tagged

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

                Text {
                    anchors.centerIn: picture
                    visible: picture.status !== Image.Ready
                    text: tile.failed ? "Can't display file" : "…"
                    color: "#888888"
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
                onClicked: function(mouse) {
                    tagLibrary.clickFile(tile.index,
                                         (mouse.modifiers & Qt.ControlModifier) !== 0,
                                         (mouse.modifiers & Qt.ShiftModifier) !== 0)
                    pane.focusReturned()
                }
            }
        }

        ScrollBar.vertical: ScrollBar {}

        // Stepping by keyboard keeps the file in view.
        Connections {
            target: tagLibrary
            function onCurrentRowChanged(row) {
                if (row >= 0)
                    grid.positionViewAtIndex(row, GridView.Contain)
            }
        }

        Text {
            anchors.centerIn: parent
            visible: grid.count === 0
            color: "#888888"
            text: tagLibrary.scanning ? "Scanning…"
                  : tagLibrary.folder === "" ? "Choose a folder on the left"
                  : tagLibrary.untaggedOnly ? "Nothing untagged here"
                  : "No pictures in this folder"
        }
    }
}
