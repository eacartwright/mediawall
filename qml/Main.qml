import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.qmlmodels

ApplicationWindow {
    id: window

    visible: true
    width: 1280
    height: 800
    title: projectController.title

    color: "#181818"

    // A fixed dark palette for the Fusion style (set in main.py), so
    // controls look the same on every machine whatever the OS theme.
    palette.window: "#1e1e1e"
    palette.windowText: "#ffffff"
    palette.base: "#2d2d2d"
    palette.alternateBase: "#353535"
    palette.text: "#ffffff"
    palette.button: "#3c3c3c"
    palette.buttonText: "#ffffff"
    palette.brightText: "#ffffff"
    palette.highlight: "#3d7fc4"
    palette.highlightedText: "#ffffff"
    palette.light: "#787878"
    palette.midlight: "#5a5a5a"
    palette.mid: "#282828"
    palette.dark: "#1e1e1e"
    palette.shadow: "#000000"
    palette.placeholderText: "#80ffffff"
    palette.toolTipBase: "#3c3c3c"
    palette.toolTipText: "#d4d4d4"
    palette.link: "#6aa6e8"
    palette.disabled.buttonText: "#9d9d9d"
    palette.disabled.windowText: "#9d9d9d"
    palette.disabled.text: "#9d9d9d"

    // Ask about unsaved changes before closing.
    onClosing: function(close) {
        close.accepted = projectController.confirmClose()
    }


    // -------------------------------------------------
    // Keyboard shortcuts
    // -------------------------------------------------

    Shortcut {
        sequences: [StandardKey.New]
        onActivated: projectController.newProject()
    }

    Shortcut {
        sequences: [StandardKey.Open]
        onActivated: projectController.openProject()
    }

    Shortcut {
        sequences: [StandardKey.Save]
        onActivated: projectController.save()
    }

    Shortcut {
        // Explicit: StandardKey.SaveAs has no binding on Windows.
        sequence: "Ctrl+Shift+S"
        onActivated: projectController.saveAs()
    }

    Shortcut {
        sequences: [StandardKey.Undo]
        onActivated: sceneModel.undo()
    }

    Shortcut {
        // Both common conventions (Linux/macOS and Windows).
        sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]
        onActivated: sceneModel.redo()
    }

    Shortcut {
        sequence: "Ctrl+D"
        onActivated: sceneModel.duplicateSelected()
    }

    Shortcut {
        // Deselect (also leaves a container's Adjust mode).
        sequence: "Escape"
        onActivated: sceneModel.select("")
    }

    Shortcut {
        sequences: [StandardKey.Delete]
        onActivated: sceneModel.removeSelected()
    }

    Shortcut {
        sequence: "Ctrl+Shift+Up"
        onActivated: sceneModel.bringToFront(sceneModel.selectedId)
    }

    Shortcut {
        sequence: "Ctrl+Up"
        onActivated: sceneModel.bringForward(sceneModel.selectedId)
    }

    Shortcut {
        sequence: "Ctrl+Down"
        onActivated: sceneModel.sendBackward(sceneModel.selectedId)
    }

    Shortcut {
        sequence: "Ctrl+Shift+Down"
        onActivated: sceneModel.sendToBack(sceneModel.selectedId)
    }


    // -------------------------------------------------
    // Main canvas
    // -------------------------------------------------

    Rectangle {
        id: canvas

        anchors.fill: parent
        color: "#202020"


        // -------------------------------------------------
        // Top toolbar
        // -------------------------------------------------

        Rectangle {
            id: toolbar

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right

            height: 50
            z: 1

            color: "#303030"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10

                spacing: 8

                Button {
                    text: "New"
                    onClicked: projectController.newProject()
                }

                Button {
                    text: "Open"
                    onClicked: projectController.openProject()
                }

                Button {
                    text: "Save"
                    onClicked: projectController.save()
                }

                Button {
                    text: "Save As"
                    onClicked: projectController.saveAs()
                }

                // Divider
                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 28
                    Layout.leftMargin: 6
                    Layout.rightMargin: 6
                    color: "#555555"
                }

                Button {
                    text: "Undo"
                    enabled: sceneModel.canUndo
                    onClicked: sceneModel.undo()
                }

                Button {
                    text: "Redo"
                    enabled: sceneModel.canRedo
                    onClicked: sceneModel.redo()
                }

                // Divider
                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 28
                    Layout.leftMargin: 6
                    Layout.rightMargin: 6
                    color: "#555555"
                }

                Button {
                    text: "Add Browser"
                    onClicked: sceneModel.addBrowser(
                        100 + Math.random() * 100,
                        100 + Math.random() * 100
                    )
                }

                Button {
                    text: "Add Container"
                    onClicked: sceneModel.addContainer(
                        150 + Math.random() * 100,
                        150 + Math.random() * 100
                    )
                }

                Item {
                    Layout.fillWidth: true
                }

                Label {
                    text: "Media Wall"
                    color: "#dddddd"
                    font.pixelSize: 16
                }
            }
        }


        // -------------------------------------------------
        // Scene
        //
        // Every object here is a row in sceneModel.
        // QML renders them; Python owns their state.
        // -------------------------------------------------

        Item {
            id: scene

            anchors.top: toolbar.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom

            clip: true


            // Clicking empty canvas clears the selection.
            // Right-clicking it opens the canvas menu.
            MouseArea {
                anchors.fill: parent
                z: -1000000

                acceptedButtons: Qt.LeftButton | Qt.RightButton

                onPressed: function(mouse) {
                    sceneModel.select("")

                    if (mouse.button === Qt.RightButton) {
                        canvasMenu.clickPoint = Qt.point(mouse.x, mouse.y)
                        canvasMenu.popup()
                    }
                }
            }


            // Right-click menu for empty canvas.
            // New objects appear where you clicked.
            Menu {
                id: canvasMenu

                property point clickPoint

                MenuItem {
                    text: "Add Browser Here"
                    onTriggered: sceneModel.addBrowser(
                        canvasMenu.clickPoint.x, canvasMenu.clickPoint.y
                    )
                }

                MenuItem {
                    text: "Add Container Here"
                    onTriggered: sceneModel.addContainer(
                        canvasMenu.clickPoint.x, canvasMenu.clickPoint.y
                    )
                }
            }


            ObjectContextMenu {
                id: objectMenu
            }


            Repeater {
                model: sceneModel

                delegate: DelegateChooser {
                    role: "objectType"

                    DelegateChoice {
                        roleValue: "media"
                        MediaObject { sceneItem: scene; contextMenu: objectMenu }
                    }

                    DelegateChoice {
                        roleValue: "browser"
                        BrowserObject { sceneItem: scene; contextMenu: objectMenu }
                    }

                    DelegateChoice {
                        roleValue: "container"
                        ContainerObject { sceneItem: scene; contextMenu: objectMenu }
                    }
                }
            }
        }
    }
}
