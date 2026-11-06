import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The Library's right pane: the tags on the selection with their counts
// ("3/12": 3 of the 12 selected files), then the whole tag tree. Clicking
// a tag puts it on the selection or takes it off. The tree is edited here
// too: drag a tag onto another or onto a group, and right-click for the
// rest (readme section 44.3).
//
// A row's handlers return the focus before changing anything: a change can
// rebuild the list, destroying the row whose handler is running.

Rectangle {
    id: pane

    color: "#242424"

    signal focusReturned()

    // A tag as the selection has it: on all, on some, or only implied.
    function nameColor(onSelection, direct) {
        if (direct > 0 && direct === tagLibrary.selectedCount)
            return "#ffffff"
        if (direct > 0)
            return "#c8d8ea"
        return onSelection > 0 ? "#888888" : "#dddddd"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 6
        spacing: 4

        Label {
            visible: !tagLibrary.findMode
            text: "On selection"
            font.bold: true
        }

        ListView {
            id: selectionList
            objectName: "librarySelectionTags"           // found by tests/app

            visible: !tagLibrary.findMode
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, pane.height * 0.3)
            Layout.minimumHeight: 22
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: tagLibrary.selectionTags

            delegate: Rectangle {
                required property var modelData

                width: ListView.view.width
                height: 24
                color: selectionMouse.containsMouse ? "#333a44" : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    spacing: 6

                    Text {
                        Layout.fillWidth: true
                        text: modelData.name + (modelData.direct === 0 ? "  (from " + modelData.via + ")" : "")
                        color: pane.nameColor(modelData.count, modelData.direct)
                        elide: Text.ElideRight
                    }

                    Text {
                        text: modelData.count + "/" + tagLibrary.selectedCount
                        color: "#aaaaaa"
                        font.family: fixedFontFamily
                        font.pixelSize: 11
                    }
                }

                MouseArea {
                    id: selectionMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        pane.focusReturned()
                        tagLibrary.toggleTag(modelData.id)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: selectionList.count === 0
                text: "No tags"
                color: "#777777"
            }
        }

        Rectangle {
            visible: !tagLibrary.findMode
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: "#444444"
        }

        Label {
            text: tagLibrary.findMode ? "In these results" : "All tags"
            font.bold: true
        }

        ListView {
            id: tree
            objectName: "libraryTagTree"                 // found by tests/app

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: tagLibrary.tags

            // Dragging a tag: which one, and the row it would go into
            // (-1 is the empty space below: the top level).
            property int draggedId: -1
            property string draggedName: ""
            property int dropId: -1

            // Keep the scroll position when the tree changes shape.
            property real keepY: 0
            onContentYChanged: if (moving) keepY = contentY
            Connections {
                target: tagLibrary.tags
                function onModelReset() {
                    Qt.callLater(function() {
                        tree.contentY = Math.min(tree.keepY, Math.max(0, tree.contentHeight - tree.height))
                    })
                }
            }

            function rowAt(y) {
                return indexAt(10, y + contentY)
            }

            delegate: Rectangle {
                id: tagRow

                required property int index
                required property int tagId
                required property string name
                required property int depth
                required property bool isGroup
                required property int parentId
                required property bool expandable
                required property bool expanded
                required property int count
                required property int onSelection
                required property int direct

                width: ListView.view.width
                height: 24
                color: tree.dropId === tagId && tree.draggedId !== tagId ? "#3d7fc4"
                       : rowMouse.containsMouse ? "#333a44" : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 4 + tagRow.depth * 14
                    anchors.rightMargin: 6
                    spacing: 4

                    Text {
                        Layout.preferredWidth: 14
                        text: tagRow.expandable ? (tagRow.expanded ? "▾" : "▸") : ""
                        color: "#aaaaaa"
                    }

                    Text {
                        Layout.fillWidth: true
                        text: tagRow.name
                        font.bold: tagRow.isGroup
                        color: tagRow.isGroup ? "#aab4c0" : pane.nameColor(tagRow.onSelection, tagRow.direct)
                        elide: Text.ElideRight
                    }

                    Text {
                        visible: !tagRow.isGroup
                        text: "(" + tagRow.count + ")"
                        color: "#999999"
                        font.pixelSize: 11
                    }
                }

                MouseArea {
                    id: rowMouse

                    anchors.fill: parent
                    hoverEnabled: true
                    preventStealing: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton

                    property point pressedAt
                    property bool dragging: false

                    onPressed: function(mouse) {
                        pressedAt = Qt.point(mouse.x, mouse.y)
                        dragging = false
                    }

                    onPositionChanged: function(mouse) {
                        if (!pressed || !(pressedButtons & Qt.LeftButton))
                            return
                        if (!dragging && Math.abs(mouse.y - pressedAt.y) + Math.abs(mouse.x - pressedAt.x) > 8) {
                            dragging = true
                            tree.draggedId = tagRow.tagId
                            tree.draggedName = tagRow.name
                        }
                        if (dragging) {
                            var p = mapToItem(tree, mouse.x, mouse.y)
                            var row = tree.rowAt(p.y)
                            tree.dropId = row >= 0 ? tree.itemAtIndex(row).tagId : -1
                            dragLabel.x = p.x + 12
                            dragLabel.y = p.y
                        }
                    }

                    onReleased: function(mouse) {
                        if (!dragging)
                            return
                        var moved = tree.draggedId
                        var target = tree.dropId
                        tree.draggedId = -1
                        tree.dropId = -1
                        dragging = false
                        pane.focusReturned()
                        if (moved !== target)
                            tagLibrary.moveTag(moved, target)
                    }

                    onClicked: function(mouse) {
                        if (mouse.button === Qt.RightButton) {
                            rowMenu.open(tagRow.tagId, tagRow.name, tagRow.isGroup)
                            return
                        }
                        pane.focusReturned()
                        if (tagRow.isGroup || (tagRow.expandable && mouse.x < 18 + tagRow.depth * 14))
                            tagLibrary.toggleExpanded(tagRow.tagId)
                        else
                            tagLibrary.toggleTag(tagRow.tagId)
                    }
                }
            }

            ScrollBar.vertical: ScrollBar {}

            // Right-click on the empty space below the rows.
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.RightButton
                z: -1
                onClicked: emptyMenu.popup()
            }

            Text {
                anchors.centerIn: parent
                width: parent.width - 20
                visible: tree.count === 0
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                text: tagLibrary.findMode ? "No tags in these results"
                                          : "No tags yet. Select a file, type a name, and press Enter."
                color: "#777777"
            }

            // The tag being dragged, beside the pointer.
            Label {
                id: dragLabel
                visible: tree.draggedId !== -1
                z: 2
                text: tree.draggedName
                padding: 3
                background: Rectangle { color: "#3c3c3c"; border.color: "#6aa6e8" }
            }
        }
    }

    // ---- Menus ----

    Menu {
        id: rowMenu

        property int tagId: -1
        property string tagName: ""
        property bool isGroup: false

        function open(id, name, group) {
            tagId = id
            tagName = name
            isGroup = group
            popup()
        }

        onClosed: if (!nameDialog.visible && !mergeDialog.visible && !deleteDialog.visible) pane.focusReturned()

        MenuItem {
            text: "New Group…"
            onTriggered: nameDialog.ask("New Group", "", function(name) {
                return tagLibrary.createGroup(name, rowMenu.isGroup ? rowMenu.tagId : -1)
            })
        }
        MenuItem {
            text: "Rename…"
            onTriggered: nameDialog.ask("Rename", rowMenu.tagName, function(name) {
                return tagLibrary.renameTag(rowMenu.tagId, name)
            })
        }
        MenuItem {
            text: "Merge Into…"
            enabled: !rowMenu.isGroup
            onTriggered: mergeDialog.ask(rowMenu.tagId, rowMenu.tagName)
        }
        MenuItem {
            text: rowMenu.isGroup ? "Make Tag" : "Make Group"
            onTriggered: rowMenu.isGroup ? tagLibrary.makeTag(rowMenu.tagId) : tagLibrary.makeGroup(rowMenu.tagId)
        }
        MenuSeparator {}
        MenuItem {
            text: "Delete"
            onTriggered: deleteDialog.ask(rowMenu.tagId, rowMenu.tagName, rowMenu.isGroup)
        }
    }

    Menu {
        id: emptyMenu
        onClosed: if (!nameDialog.visible) pane.focusReturned()

        MenuItem {
            text: "New Group…"
            onTriggered: nameDialog.ask("New Group", "", function(name) {
                return tagLibrary.createGroup(name, -1)
            })
        }
    }

    // ---- Dialogs ----

    Dialog {
        id: nameDialog
        objectName: "libraryNameDialog"                  // found by tests/app

        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        width: 340
        standardButtons: Dialog.Ok | Dialog.Cancel

        property var action: null

        function ask(heading, value, then) {
            title = heading
            nameField.text = value
            action = then
            open()
            nameField.selectAll()
            nameField.forceActiveFocus()
        }

        TextField {
            id: nameField
            objectName: "libraryNameField"               // found by tests/app
            width: parent.width
            onAccepted: nameDialog.accept()
        }

        onAccepted: action(nameField.text)
        onClosed: pane.focusReturned()
    }

    Dialog {
        id: mergeDialog
        objectName: "libraryMergeDialog"                 // found by tests/app

        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        width: 360
        standardButtons: Dialog.Ok | Dialog.Cancel

        property int tagId: -1
        readonly property var choices: mergeField.text === "" ? []
                                       : tagLibrary.mergeChoices(mergeField.text, tagId)

        function ask(id, name) {
            tagId = id
            title = 'Merge "' + name + '" Into'
            mergeField.text = ""
            open()
            mergeField.forceActiveFocus()
        }

        function chosenName() {
            return choices.length > 0 ? choices[0] : mergeField.text
        }

        ColumnLayout {
            width: parent.width
            spacing: 4

            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Its files and child tags move to the tag you choose, and this tag is deleted."
                color: "#bbbbbb"
            }

            TextField {
                id: mergeField
                objectName: "libraryMergeField"          // found by tests/app
                Layout.fillWidth: true
                placeholderText: "Type a tag's name"
                onAccepted: mergeDialog.accept()
            }

            Repeater {
                model: mergeDialog.choices

                Label {
                    required property string modelData
                    required property int index
                    text: modelData
                    font.bold: index === 0

                    MouseArea {
                        anchors.fill: parent
                        onClicked: mergeField.text = parent.modelData
                    }
                }
            }
        }

        onAccepted: tagLibrary.mergeTag(tagId, chosenName())
        onClosed: pane.focusReturned()
    }

    Dialog {
        id: deleteDialog
        objectName: "libraryDeleteDialog"                // found by tests/app

        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        width: 380
        standardButtons: Dialog.Ok | Dialog.Cancel

        property int tagId: -1
        property string question: ""

        function ask(id, name, group) {
            var used = tagLibrary.tagUsage(id)
            if (!group && used === 0) {             // nothing to lose: no need to ask
                tagLibrary.deleteTag(id)
                pane.focusReturned()
                return
            }
            tagId = id
            title = "Delete " + (group ? "Group" : "Tag")
            question = group
                ? 'Delete the group "' + name + '"? What it holds moves up a level; no tags are deleted.'
                : 'Delete the tag "' + name + '"? It\'s on ' + used + (used === 1 ? " file." : " files.")
            open()
        }

        Label {
            width: parent.width
            wrapMode: Text.WordWrap
            text: deleteDialog.question
        }

        onAccepted: tagLibrary.deleteTag(tagId)
        onClosed: pane.focusReturned()
    }
}
