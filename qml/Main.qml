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
    // Full Screen and Present (window state; not saved)
    //
    // Full Screen: the editor fills the screen, toolbar hidden.
    // Present: full screen, canvas objects view-only and unselectable,
    // no editing chrome. Browsers keep working.
    // -------------------------------------------------

    property bool fullScreenEditing: false
    property bool presenting: false
    readonly property bool fullScreen: fullScreenEditing || presenting

    // Restored on leaving full screen (windowed or maximized).
    property int windowedVisibility: Window.Windowed

    onFullScreenChanged: {
        if (fullScreen) {
            if (visibility !== Window.FullScreen)
                windowedVisibility = visibility
            showFullScreen()
            exitButton.reveal()
        } else {
            visibility = windowedVisibility
        }
    }

    onPresentingChanged: if (presenting) sceneModel.select("")

    // Back one level: Present -> where you were; Full Screen -> window.
    function stepOut() {
        if (presenting)
            presenting = false
        else
            fullScreenEditing = false
    }


    LogWindow {
        id: logWindow
        palette: window.palette
    }


    // -------------------------------------------------
    // Keyboard shortcuts
    // -------------------------------------------------

    Shortcut {
        sequences: [StandardKey.New]
        enabled: !window.presenting
        onActivated: projectController.newProject()
    }

    Shortcut {
        sequences: [StandardKey.Open]
        enabled: !window.presenting
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
        enabled: !window.presenting
        onActivated: sceneModel.undo()
    }

    Shortcut {
        // Both common conventions (Linux/macOS and Windows).
        sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]
        enabled: !window.presenting
        onActivated: sceneModel.redo()
    }

    Shortcut {
        sequence: "Ctrl+D"
        enabled: !window.presenting
        onActivated: sceneModel.duplicateSelected()
    }

    Shortcut {
        // Leave Present; otherwise deselect (also leaves a container's
        // Adjust mode); with nothing selected, leave Full Screen.
        sequence: "Escape"
        onActivated: {
            if (window.presenting)
                window.presenting = false
            else if (sceneModel.selectedId !== "")
                sceneModel.select("")
            else if (window.fullScreenEditing)
                window.fullScreenEditing = false
        }
    }

    Shortcut {
        sequence: "F11"
        onActivated: {
            if (window.presenting)
                window.presenting = false
            else
                window.fullScreenEditing = !window.fullScreenEditing
        }
    }

    Shortcut {
        sequence: "F5"
        onActivated: window.presenting = !window.presenting
    }

    Shortcut {
        sequences: [StandardKey.Delete]
        enabled: !window.presenting
        onActivated: sceneModel.removeSelected()
    }

    Shortcut {
        sequence: "Ctrl+Shift+Up"
        enabled: !window.presenting
        onActivated: sceneModel.bringToFront(sceneModel.selectedId)
    }

    Shortcut {
        sequence: "Ctrl+Up"
        enabled: !window.presenting
        onActivated: sceneModel.bringForward(sceneModel.selectedId)
    }

    Shortcut {
        sequence: "Ctrl+Down"
        enabled: !window.presenting
        onActivated: sceneModel.sendBackward(sceneModel.selectedId)
    }

    Shortcut {
        sequence: "Ctrl+Shift+Down"
        enabled: !window.presenting
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

            // Overlays the canvas (rather than pushing it down), so
            // nothing moves when entering or leaving full screen.
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right

            visible: !window.fullScreen

            height: 50
            z: 1

            color: "#303030"

            // Keep clicks on the bar from reaching the canvas below.
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
                onWheel: function(wheel) { wheel.accepted = true }
            }

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

                Button {
                    text: "Full Screen"
                    onClicked: window.fullScreenEditing = true
                }

                Button {
                    text: "Present"
                    onClicked: window.presenting = true
                }

                // Messages the app would print to a terminal.
                Button {
                    text: "Log"
                    onClicked: {
                        logWindow.show()
                        logWindow.raise()
                        logWindow.requestActivate()
                    }
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

            anchors.fill: parent

            clip: true

            // Read by every object: in Present, canvas objects are
            // view-only and show no selection; browsers keep working.
            readonly property bool presenting: window.presenting

            // Media players by media instance id, so panels and menus
            // can read a player's position (e.g. to set A-B loop points).
            // mediaViewsVersion changes whenever the set changes, so
            // bindings that look views up re-evaluate.
            property var mediaViews: ({})
            property int mediaViewsVersion: 0

            function registerView(mediaId, view) {
                if (!mediaId)
                    return
                mediaViews[mediaId] = view
                mediaViewsVersion++
            }

            function unregisterView(mediaId, view) {
                if (mediaId && mediaViews[mediaId] === view) {
                    delete mediaViews[mediaId]
                    mediaViewsVersion++
                }
            }

            function viewFor(mediaId) {
                return mediaViews[mediaId] || null
            }


            // Clicking empty canvas clears the selection.
            // Right-clicking it opens the canvas menu.
            // Double-clicking it leaves Full Screen / Present. (In
            // Present, media objects let clicks through, so double-
            // clicking them does too.)
            MouseArea {
                anchors.fill: parent
                z: -1000000

                acceptedButtons: Qt.LeftButton | Qt.RightButton

                onPressed: function(mouse) {
                    sceneModel.select("")

                    if (mouse.button === Qt.RightButton && !window.presenting) {
                        canvasMenu.clickPoint = Qt.point(mouse.x, mouse.y)
                        canvasMenu.popup()
                    }
                }

                onDoubleClicked: function(mouse) {
                    if (mouse.button === Qt.LeftButton && window.fullScreen)
                        window.stepOut()
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


        // -------------------------------------------------
        // Sidebar (Layers): a flyout on the right edge
        // -------------------------------------------------

        Sidebar {
            sceneItem: scene

            anchors.top: toolbar.visible ? toolbar.bottom : parent.top
            anchors.bottom: parent.bottom
            anchors.right: parent.right

            visible: !window.presenting

            z: 2
        }


        // -------------------------------------------------
        // Exit button (Full Screen / Present): shows when the mouse
        // moves, fades out after a moment unless hovered.
        // -------------------------------------------------

        HoverHandler {
            onPointChanged: if (window.fullScreen) exitButton.reveal()
        }

        Rectangle {
            id: exitButton

            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 12

            width: 40
            height: 40
            radius: 20

            z: 3000000      // above everything on the canvas

            color: exitArea.containsMouse ? "#e0404040" : "#b0202020"
            border.color: "#80ffffff"

            opacity: 0
            visible: window.fullScreen && opacity > 0

            Behavior on opacity { NumberAnimation { duration: 250 } }

            function reveal() {
                opacity = 1
                hideTimer.restart()
            }

            Timer {
                id: hideTimer
                interval: 2000
                onTriggered: {
                    if (exitArea.containsMouse)
                        restart()
                    else
                        exitButton.opacity = 0
                }
            }

            Text {
                anchors.centerIn: parent
                text: "✕"
                color: "#ffffff"
                font.pixelSize: 18
            }

            MouseArea {
                id: exitArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: window.stepOut()
            }

            ToolTip.visible: exitArea.containsMouse
            ToolTip.text: window.presenting
                          ? "Stop presenting (Esc, or double-click the canvas)"
                          : "Leave full screen (F11, or double-click the canvas)"
            ToolTip.delay: 500
        }
    }
}
