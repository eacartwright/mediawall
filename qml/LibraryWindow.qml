import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The Library (readme section 44): tag media as quickly as possible. The
// search box keeps the keyboard focus through tagging, so the hands stay
// on the keys; the panes around it hand focus back after every click.
//
// A window of its own, free to go behind the wall (unlike the Log and
// Media Memory windows, which stay in front of it), since it's as large.
// Main.qml's Loader creates it when opened and destroys it when closed,
// so it costs nothing otherwise. What it shows lives in tagLibrary
// (bridge/library_model.py), so nothing is lost by closing it.

ApplicationWindow {
    id: libraryWindow

    title: "Mediawall — Library"
    transientParent: null

    width: 1280
    height: 800
    color: "#1e1e1e"

    readonly property var files: tagLibrary.opened ? tagLibrary.files : null

    // The middle pane: the grid, or one large file above a row of the others.
    property bool stripView: false

    function refocus() {
        searchBox.forceActiveFocus()
    }

    Component.onCompleted: {
        tagLibrary.open()
        refocus()
    }

    readonly property string selectionText: {
        var n = tagLibrary.selectedCount
        return n === 0 ? "No files selected"
             : n === 1 ? "Tagging 1 file"
             : "Tagging " + n + " files"
    }

    // ---- Search box, and what's selected ----

    Rectangle {
        id: topBar

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 50
        color: "#303030"
        z: 2                             // its results lie over the panes

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 10

            TextField {
                id: searchBox
                objectName: "librarySearch"              // found by tests/app

                Layout.preferredWidth: 340
                placeholderText: "Type a tag, then Enter"
                activeFocusOnTab: false

                onTextChanged: tagLibrary.setQuery(text)

                function applied(ok) {
                    if (ok)
                        clear()
                }

                Keys.onPressed: function(event) {
                    var empty = text === ""
                    var plain = !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier))
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        if (event.modifiers & Qt.ShiftModifier)
                            applied(!empty && tagLibrary.createAndApply(text))
                        else if (empty)
                            tagLibrary.stepFile(1)
                        else
                            applied(tagLibrary.applyResult(text))
                    } else if (event.key === Qt.Key_Up && plain) {
                        tagLibrary.moveHighlight(-1)
                    } else if (event.key === Qt.Key_Down && plain) {
                        tagLibrary.moveHighlight(1)
                    } else if (event.key === Qt.Key_Left && plain && empty) {
                        tagLibrary.stepFile(-1)
                    } else if (event.key === Qt.Key_Right && plain && empty) {
                        tagLibrary.stepFile(1)
                    } else if (event.key === Qt.Key_Backspace && plain && empty) {
                        tagLibrary.removeLastApplied()
                    } else if (event.key === Qt.Key_Space && (event.modifiers & Qt.ControlModifier)) {
                        if (libraryWindow.stripView)
                            fileStrip.togglePlay()
                        else
                            fileGrid.togglePlay()
                    } else if (event.key === Qt.Key_Escape) {
                        if (empty)
                            libraryWindow.stripView = false
                        else
                            clear()
                    } else if (event.matches(StandardKey.SelectAll) && empty) {
                        tagLibrary.selectAll()
                    } else if (event.matches(StandardKey.Undo)) {
                        tagLibrary.undo()         // not the field's own undo
                    } else if (event.matches(StandardKey.Redo) || event.matches(StandardKey.Back)
                               || (event.key === Qt.Key_Y && (event.modifiers & Qt.ControlModifier))) {
                        tagLibrary.redo()
                    } else {
                        return
                    }
                    event.accepted = true
                }
                // Keep focus here (Tab will switch to Find, section 44.2).
                Keys.onTabPressed: function(event) { event.accepted = true }
                Keys.onBacktabPressed: function(event) { event.accepted = true }
            }

            Label {
                objectName: "librarySelection"           // found by tests/app
                text: libraryWindow.selectionText
                color: tagLibrary.selectedCount > 0 ? "#ffffff" : "#999999"
                font.bold: true
            }

            Item { Layout.fillWidth: true }

            Row {
                spacing: 1

                Button {
                    objectName: "libraryGridButton"      // found by tests/app
                    text: "Grid"
                    focusPolicy: Qt.NoFocus
                    highlighted: !libraryWindow.stripView
                    onClicked: libraryWindow.stripView = false
                }

                Button {
                    objectName: "libraryStripButton"     // found by tests/app
                    text: "Strip"
                    focusPolicy: Qt.NoFocus
                    highlighted: libraryWindow.stripView
                    onClicked: libraryWindow.stripView = true
                }
            }

            Button {
                text: "Undo"
                focusPolicy: Qt.NoFocus
                enabled: tagLibrary.canUndo
                onClicked: tagLibrary.undo()
            }

            Button {
                text: "Redo"
                focusPolicy: Qt.NoFocus
                enabled: tagLibrary.canRedo
                onClicked: tagLibrary.redo()
            }

            Button {
                id: libraryMenuButton
                text: "Library ▾"
                focusPolicy: Qt.NoFocus
                onClicked: libraryMenu.popup(libraryMenuButton, 0, libraryMenuButton.height)

                Menu {
                    id: libraryMenu
                    width: 220
                    onClosed: libraryWindow.refocus()

                    MenuItem { text: "Export Everything…"; onTriggered: tagLibrary.chooseExport(true) }
                    MenuItem { text: "Export Tags Only…"; onTriggered: tagLibrary.chooseExport(false) }
                    MenuSeparator {}
                    MenuItem { text: "Import…"; onTriggered: tagLibrary.chooseImport() }
                }
            }
        }

        // Results, below the box. Not a popup, which would take the focus.
        Rectangle {
            id: resultsPanel
            objectName: "libraryResults"                 // found by tests/app

            anchors.top: parent.bottom
            x: searchBox.x + 10
            width: 420
            height: resultsColumn.implicitHeight + 8
            visible: tagLibrary.results.length > 0
            color: "#2d2d2d"
            border.color: "#5a5a5a"

            Column {
                id: resultsColumn

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 4

                Repeater {
                    model: tagLibrary.results

                    Rectangle {
                        required property var modelData
                        required property int index

                        width: resultsColumn.width
                        height: 26
                        color: index === tagLibrary.highlight ? "#3d7fc4" : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 10

                            Text {
                                Layout.maximumWidth: parent.width * 0.65
                                text: modelData.create ? 'Create "' + modelData.name + '"' : modelData.name
                                color: "#ffffff"
                                font.italic: modelData.create
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.where
                                color: "#bbbbbb"
                                font.pixelSize: 11
                                elide: Text.ElideLeft
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- The panes ----

    SplitView {
        anchors.top: topBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: statusBar.top

        LibraryFolders {
            SplitView.preferredWidth: 250
            SplitView.minimumWidth: 140
            onFocusReturned: libraryWindow.refocus()
        }

        Item {
            SplitView.fillWidth: true
            SplitView.minimumWidth: 200

            LibraryGrid {
                id: fileGrid
                anchors.fill: parent
                visible: !libraryWindow.stripView
                files: libraryWindow.files
                onFocusReturned: libraryWindow.refocus()
                onOpenStrip: libraryWindow.stripView = true
            }

            LibraryStrip {
                id: fileStrip
                anchors.fill: parent
                visible: libraryWindow.stripView
                files: libraryWindow.files
                onFocusReturned: libraryWindow.refocus()
            }
        }

        LibraryTags {
            SplitView.preferredWidth: 300
            SplitView.minimumWidth: 180
            onFocusReturned: libraryWindow.refocus()
        }
    }

    // ---- Status bar ----

    Rectangle {
        id: statusBar

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 30
        color: "#2a2a2a"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 10

            Label {
                objectName: "libraryMessage"             // found by tests/app
                Layout.fillWidth: true
                elide: Text.ElideMiddle
                text: tagLibrary.error !== "" ? tagLibrary.error : tagLibrary.message
                color: tagLibrary.error !== "" ? "#e06060" : "#e0c060"
            }

            Label { text: "Tile size"; color: "#999999" }

            Slider {
                objectName: "libraryTileSize"            // found by tests/app
                Layout.preferredWidth: 120
                focusPolicy: Qt.NoFocus
                from: 100
                to: 320
                stepSize: 10
                value: appSettings.libraryTileSize
                onMoved: appSettings.libraryTileSize = value
            }
        }
    }
}
