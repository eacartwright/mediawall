import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The Library's left pane: the folder tree, and which of a folder's files
// to show. The tree comes from Qt's own file system model, which reads
// folders in the background and notices changes.

Rectangle {
    id: pane

    color: "#242424"

    signal focusReturned()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 6
        spacing: 4

        RowLayout {
            Layout.fillWidth: true

            Label {
                Layout.fillWidth: true
                text: "Folders"
                font.bold: true
            }

            Button {
                text: "Folder…"
                focusPolicy: Qt.NoFocus
                onClicked: {
                    tagLibrary.chooseFolder()
                    pane.focusReturned()
                }
            }
        }

        TreeView {
            id: tree
            objectName: "libraryFolderTree"              // found by tests/app

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            pointerNavigationEnabled: false
            keyNavigationEnabled: false
            activeFocusOnTab: false

            model: tagLibrary.folderModel

            // Only the name: the model's other columns are size, type, and
            // date. Wider than the pane, so a deep folder's name still shows,
            // with the scroll bar below to reach it.
            readonly property real nameWidth: Math.max(width, 900)
            columnWidthProvider: function(column) { return column === 0 ? nameWidth : 0 }

            delegate: TreeViewDelegate {
                id: row

                implicitHeight: 24
                indentation: tree.rowIndent

                readonly property string folderPath: model.filePath

                highlighted: folderPath === tagLibrary.folder
                contentItem: Label {
                    text: model.fileName || model.filePath
                    verticalAlignment: Text.AlignVCenter
                }

                TapHandler {
                    // Beside the arrow, which opens and closes the folder.
                    acceptedButtons: Qt.LeftButton
                    onTapped: function(point) {
                        if (point.position.x >= row.leftMargin) {
                            tagLibrary.setFolder(row.folderPath)
                            pane.focusReturned()
                        }
                    }
                }
            }

            readonly property int rowIndent: 14

            ScrollBar.vertical: ScrollBar {}
            ScrollBar.horizontal: ScrollBar {}

            // Show where the Library last was.
            function showFolder(path) {
                if (!path)
                    return
                var index = tagLibrary.folderIndex(path)
                if (!index.valid)
                    return
                expandToIndex(index)
                forceLayout()
                var row = rowAtIndex(index)
                if (row >= 0)
                    positionViewAtRow(row, TableView.Contain)
                // Across too, so the name itself is in view: rows start 30
                // px in, past the arrow, plus their indentation.
                contentX = Math.max(0, Math.min(depth(row) * rowIndent + 6, nameWidth - width))
            }

            // Once it's been laid out, when the window opens.
            Timer {
                interval: 100
                running: true
                onTriggered: tree.showFolder(tagLibrary.folder)
            }

            Connections {
                target: tagLibrary
                function onFolderChanged() { Qt.callLater(tree.showFolder, tagLibrary.folder) }
            }
        }

        CheckBox {
            objectName: "librarySubfolders"              // found by tests/app
            text: "Subfolders"
            focusPolicy: Qt.NoFocus
            checked: tagLibrary.subfolders
            onToggled: {
                tagLibrary.subfolders = checked
                pane.focusReturned()
            }
        }

        CheckBox {
            objectName: "libraryUntaggedOnly"            // found by tests/app
            text: "Untagged only"
            focusPolicy: Qt.NoFocus
            checked: tagLibrary.untaggedOnly
            onToggled: {
                tagLibrary.untaggedOnly = checked
                pane.focusReturned()
            }
        }
    }
}
