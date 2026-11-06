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
    minimumWidth: 800
    minimumHeight: 500
    color: "#1e1e1e"

    readonly property var files: tagLibrary.opened ? tagLibrary.files : null

    // The middle pane: the grid, or one large file above a row of the others.
    property bool stripView: false

    property alias cleanUp: cleanUpDialog     // found by tests/app

    // The main window, set when it opens this one: where Add to Wall goes.
    property var wall: null

    // Add to Wall: the selection, a little way in from the corner.
    function addToWall(inContainers) {
        var files = tagLibrary.selectedForWall()
        if (files.length === 0 || !wall)
            return
        if (wall.presenting) {
            tagLibrary.say("Leave Present first to add to the wall.")
            return
        }
        tagLibrary.reportAdded(wall.addFilesToWall(files, 100 + Math.random() * 100,
                                                   100 + Math.random() * 100, inContainers))
    }

    // A browsing container whose files come from the search in the box.
    function addSearchContainer() {
        if (!wall)
            return
        if (!wall.addSearchContainer(tagLibrary.currentSearch())) {
            tagLibrary.say("Leave Present first to add to the wall.")
            return
        }
        tagLibrary.say("Added a browsing container for this search."
                       + (tagLibrary.folder !== "" ? " It looks everywhere, not only in the folder." : ""))
    }

    // A file drag, of what a tile says. A real one, so it reaches the wall
    // or anything else that takes files, and only ends with a real mouse.
    function dragFiles(row) {
        dragSource.urls = tagLibrary.dragUrls(row)
        if (dragSource.urls !== "")
            dragSource.Drag.active = true
    }

    Item {
        id: dragSource
        objectName: "libraryDragSource"                  // found by tests/app

        property string urls: ""

        width: 1
        height: 1
        Drag.dragType: Drag.Automatic
        Drag.supportedActions: Qt.CopyAction
        Drag.mimeData: ({ "text/uri-list": urls })
        Drag.onDragFinished: function(action) {
            Drag.active = false
            libraryWindow.refocus()
        }
    }

    function refocus() {
        searchBox.forceActiveFocus()
    }

    function setFindMode(on) {
        searchBox.clear()
        tagLibrary.findMode = on
        refocus()
    }

    // What a tile's MouseArea moves when a drag starts. Never shown.
    Item {
        id: dragProxyItem
        width: 1
        height: 1
    }

    Component.onCompleted: {
        tagLibrary.open()
        refocus()
    }

    readonly property string selectionText: {
        var n = tagLibrary.selectedCount
        if (tagLibrary.findMode)
            return "Found " + tagLibrary.fileCount + (tagLibrary.fileCount === 1 ? " file" : " files")
                   + (n > 1 ? ", " + n + " selected" : "")
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
        height: tagLibrary.findMode ? 86 : 50
        // Clearly different, so a search can't be mistaken for tagging.
        color: tagLibrary.findMode ? "#17484a" : "#303030"
        z: 2                             // its results lie over the panes

        // The search in the middle of the window, whatever is either side of it.
        Item {
            id: topRow

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 50
            anchors.leftMargin: 10
            anchors.rightMargin: 10

            // ---- Left: the Library menu, Undo and Redo ----

            Row {
                id: topLeft

                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

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
                        MenuSeparator {}
                        MenuItem { text: "Clean Up…"; onTriggered: tagLibrary.startCleanUp() }
                    }
                }

                Row {
                    spacing: 1

                    Button {
                        text: "Undo"
                        width: 56
                        focusPolicy: Qt.NoFocus
                        enabled: tagLibrary.canUndo
                        onClicked: tagLibrary.undo()
                    }

                    Button {
                        text: "Redo"
                        width: 56
                        focusPolicy: Qt.NoFocus
                        enabled: tagLibrary.canRedo
                        onClicked: tagLibrary.redo()
                    }
                }
            }

            // ---- Middle: Tag or Find, and the search box ----

            Row {
                id: topCenter

                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Row {
                    id: tagFind
                    spacing: 1

                    Button {
                        objectName: "libraryTagButton"   // found by tests/app
                        text: "Tag"
                        width: 56
                        focusPolicy: Qt.NoFocus
                        highlighted: !tagLibrary.findMode
                        onClicked: libraryWindow.setFindMode(false)
                    }

                    Button {
                        objectName: "libraryFindButton"  // found by tests/app
                        text: "Find"
                        width: 56
                        focusPolicy: Qt.NoFocus
                        highlighted: tagLibrary.findMode
                        onClicked: libraryWindow.setFindMode(true)
                    }
                }

                TextField {
                    id: searchBox
                    objectName: "librarySearch"              // found by tests/app

                    // 300, less whatever a narrow window can't spare beside the sides.
                    width: Math.max(160, Math.min(300,
                        topRow.width - 2 * Math.max(topLeft.width, topRight.width) - 40
                        - tagFind.width - topCenter.spacing))
                    placeholderText: tagLibrary.findMode ? "Find a tag, then Enter (-tag excludes it)"
                                                         : "Type a tag, then Enter"
                    activeFocusOnTab: false

                    onTextChanged: tagLibrary.setQuery(text)

                    function applied(ok) {
                        if (ok)
                            clear()
                    }

                    Keys.onPressed: function(event) {
                        var empty = text === ""
                        var plain = !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier))
                        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                && (event.modifiers & Qt.ControlModifier)) {
                            libraryWindow.addToWall(false)
                        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
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
                    // Tab switches between Tag and Find, and focus stays here.
                    Keys.onTabPressed: function(event) {
                        libraryWindow.setFindMode(!tagLibrary.findMode)
                        event.accepted = true
                    }
                    Keys.onBacktabPressed: function(event) {
                        libraryWindow.setFindMode(!tagLibrary.findMode)
                        event.accepted = true
                    }
                }
            }

            // Beside the search, not part of it: its length changes, and that
            // mustn't move the box. Gone if a narrow window has no room for it.
            Label {
                objectName: "librarySelection"           // found by tests/app
                anchors.left: topCenter.right
                anchors.right: topRight.left
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                visible: width >= 60
                elide: Text.ElideRight
                text: libraryWindow.selectionText
                color: tagLibrary.selectedCount > 0 ? "#ffffff" : "#999999"
                font.bold: true
            }

            // ---- Right: what to do with the files, and how to show them ----

            Row {
                id: topRight

                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Row {
                    spacing: 1

                    Button {
                        objectName: "libraryAddToWall"       // found by tests/app
                        text: "Add to Wall"
                        focusPolicy: Qt.NoFocus
                        enabled: tagLibrary.selectedCount > 0
                        onClicked: libraryWindow.addToWall(false)

                        ToolTip.visible: hovered
                        ToolTip.delay: 600
                        ToolTip.text: "Pictures and videos on the canvas, audio in the Playback tab (Ctrl+Enter)"
                    }

                    Button {
                        id: addMenuButton
                        width: 22
                        text: "▾"
                        focusPolicy: Qt.NoFocus
                        onClicked: addMenu.popup(addMenuButton, 0, addMenuButton.height)

                        Menu {
                            id: addMenu
                            width: 300
                            onClosed: libraryWindow.refocus()

                            MenuItem {
                                text: "In New Containers"
                                enabled: tagLibrary.selectedCount > 0
                                onTriggered: libraryWindow.addToWall(true)
                            }
                            MenuItem {
                                objectName: "libraryNewSearchContainer"   // found by tests/app
                                text: "New Browsing Container from This Search"
                                enabled: tagLibrary.findMode && tagLibrary.filters.length > 0
                                onTriggered: libraryWindow.addSearchContainer()
                            }
                        }
                    }
                }

                Row {
                    spacing: 1

                    Button {
                        objectName: "libraryGridButton"      // found by tests/app
                        text: "Grid"
                        width: 56
                        focusPolicy: Qt.NoFocus
                        highlighted: !libraryWindow.stripView
                        onClicked: libraryWindow.stripView = false
                    }

                    Button {
                        objectName: "libraryStripButton"     // found by tests/app
                        text: "Strip"
                        width: 56
                        focusPolicy: Qt.NoFocus
                        highlighted: libraryWindow.stripView
                        onClicked: libraryWindow.stripView = true
                    }
                }
            }
        }

        // Finding: the search so far, each filter as a chip to take off.
        Row {
            objectName: "libraryChips"                   // found by tests/app

            anchors.top: topRow.bottom
            anchors.left: parent.left
            anchors.leftMargin: 10
            height: 28
            spacing: 6
            visible: tagLibrary.findMode

            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: tagLibrary.filters.length === 0 && tagLibrary.folder === ""
                text: "Everything tagged"
                color: "#a8c8c8"
            }

            Repeater {
                model: tagLibrary.filters

                Rectangle {
                    required property var modelData

                    height: 24
                    width: chipText.implicitWidth + 36
                    radius: 12
                    color: modelData.exclude ? "#6b3030" : "#26767a"

                    Text {
                        id: chipText
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: (parent.modelData.exclude ? "not " : "") + parent.modelData.name
                        color: "#ffffff"
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: "✕"
                        color: "#ffffff"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            libraryWindow.refocus()
                            tagLibrary.removeFilter(parent.modelData.id)
                        }
                    }
                }
            }

            // Limited to a folder, as another chip.
            Rectangle {
                visible: tagLibrary.folder !== ""
                height: 24
                width: folderChip.implicitWidth + 36
                radius: 12
                color: "#4a5a7a"

                Text {
                    id: folderChip
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: "in " + tagLibrary.folder.replace(/^.*[\\/]/, "")
                    color: "#ffffff"
                }

                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    text: "✕"
                    color: "#ffffff"
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        libraryWindow.refocus()
                        tagLibrary.setFolder("")
                    }
                }
            }
        }

        // Results, below the box. Not a popup, which would take the focus.
        Rectangle {
            id: resultsPanel
            objectName: "libraryResults"                 // found by tests/app

            anchors.top: parent.bottom
            // Under the box, kept inside the window when that's narrow.
            x: Math.min(topRow.x + topCenter.x + searchBox.x, parent.width - width)
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
                                text: modelData.create ? 'Create "' + modelData.name + '"'
                                      : modelData.exclude ? "not " + modelData.name
                                      : modelData.name
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
                dragProxy: dragProxyItem
                onFocusReturned: libraryWindow.refocus()
                onOpenStrip: libraryWindow.stripView = true
                onDragStarted: function(row) { libraryWindow.dragFiles(row) }
            }

            LibraryStrip {
                id: fileStrip
                anchors.fill: parent
                visible: libraryWindow.stripView
                files: libraryWindow.files
                dragProxy: dragProxyItem
                onFocusReturned: libraryWindow.refocus()
                onDragStarted: function(row) { libraryWindow.dragFiles(row) }
            }
        }

        LibraryTags {
            SplitView.preferredWidth: 200
            SplitView.minimumWidth: 140
            onFocusReturned: libraryWindow.refocus()
        }
    }

    // ---- Clean Up: it can't be undone, so it says what it will do ----

    Dialog {
        id: cleanUpDialog

        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        width: 480
        title: "Clean Up"
        standardButtons: Dialog.Ok | Dialog.Cancel

        property int count: 0
        property string where: ""

        Connections {
            target: tagLibrary
            function onCleanUpReady(count, where) {
                cleanUpDialog.count = count
                cleanUpDialog.where = where
                cleanUpDialog.open()
            }
        }

        Label {
            width: parent.width
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            text: "Forget the tags of " + cleanUpDialog.count
                  + (cleanUpDialog.count === 1 ? " missing file?" : " missing files?")
                  + "\n\nThey were in: " + cleanUpDialog.where
                  + "\n\nIf a drive isn't connected, its files count as missing: connect it first. "
                  + "This can't be undone. (A moved file keeps its tags when its new folder is opened here.)"
        }

        onAccepted: tagLibrary.confirmCleanUp()
        onClosed: libraryWindow.refocus()
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
                wheelEnabled: true               // the wheel changes it, while over it
                value: appSettings.libraryTileSize
                onMoved: appSettings.libraryTileSize = value
            }
        }
    }
}
