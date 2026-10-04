import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
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

    // The canvas item (delegate) showing a top-level object, or null.
    function objectItem(objectId) {
        if (!objectId)
            return null
        var items = scene.children
        for (var i = 0; i < items.length; i++)
            if (items[i].objectId === objectId)
                return items[i]
        return null
    }

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

    SettingsDialog {
        id: settingsDialog
        actions: appActions
    }

    // Opening a project (projectController.openWithProgress): a modal
    // popup that blocks the app until the new wall is ready. The spinner
    // is a RotationAnimator, which runs on the render thread, so it keeps
    // turning while the load blocks the UI thread (where the system uses
    // a render thread; otherwise it just stands still).
    Popup {
        id: loadingPopup

        anchors.centerIn: Overlay.overlay
        modal: true
        closePolicy: Popup.NoAutoClose
        visible: projectController.loading

        padding: 20

        background: Rectangle {
            color: loadingPopup.palette.window
            border.color: loadingPopup.palette.midlight
            radius: 4
        }

        contentItem: RowLayout {
            spacing: 14

            Shape {
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    strokeColor: "#5da9ff"
                    strokeWidth: 3
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: 14; centerY: 14
                        radiusX: 11; radiusY: 11
                        startAngle: 0
                        sweepAngle: 270
                    }
                }

                RotationAnimator on rotation {
                    from: 0
                    to: 360
                    duration: 900
                    loops: Animation.Infinite
                    running: loadingPopup.visible
                }
            }

            Label {
                text: "Opening " + projectController.loadingName + "…"
            }
        }
    }


    // -------------------------------------------------
    // Commands (AppActions.qml): each defined once, with its shortcut.
    // -------------------------------------------------

    AppActions {
        id: appActions
        window: window
        settingsDialog: settingsDialog
        logWindow: logWindow
    }

    Shortcut {
        // Redo's second key (both common conventions: Ctrl+Shift+Z is
        // on the action itself).
        sequence: "Ctrl+Y"
        onActivated: appActions.redo.trigger()
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

                Button { action: appActions.newWall }
                // Open, with Open Recent on the ▾ beside it.
                Row {
                    spacing: 1

                    Button { action: appActions.open }

                    Button {
                        id: recentButton
                        objectName: "recentButton"     // found by tests/app
                        width: 22
                        text: "▾"
                        onClicked: recentMenu.popup(recentButton, 0, recentButton.height)

                        ToolTip.visible: hovered && !recentMenu.visible
                        ToolTip.delay: 600
                        ToolTip.text: "Open Recent"

                        Menu {
                            id: recentMenu

                            // Wide enough for the folder paths.
                            width: 480

                            // One item per recent project, newest first:
                            // the file name, then its folder.
                            Instantiator {
                                model: appSettings.recentProjects

                                MenuItem {
                                    required property string modelData
                                    text: {
                                        var parts = modelData.split(/[\\/]/)
                                        var name = parts.pop()
                                        return name + "    " + parts.join("/")
                                    }
                                    onTriggered: projectController.openRecent(modelData)
                                }

                                onObjectAdded: function(index, object) { recentMenu.insertItem(index, object) }
                                onObjectRemoved: function(index, object) { recentMenu.removeItem(object) }
                            }

                            MenuItem {
                                text: "No recent projects"
                                enabled: false
                                visible: appSettings.recentProjects.length === 0
                                height: visible ? implicitHeight : 0
                            }

                            MenuSeparator {
                                visible: appSettings.recentProjects.length > 0
                                height: visible ? implicitHeight : 0
                            }

                            MenuItem {
                                text: "Clear Recent"
                                visible: appSettings.recentProjects.length > 0
                                height: visible ? implicitHeight : 0
                                onTriggered: appSettings.clearRecentProjects()
                            }
                        }
                    }
                }
                Button { action: appActions.save }
                Button { action: appActions.saveAs }

                // Layouts: a wall's containers only, saved for reuse.
                Button {
                    id: layoutButton
                    text: "Layout ▾"
                    onClicked: layoutMenu.popup(layoutButton, 0, layoutButton.height)

                    Menu {
                        id: layoutMenu

                        MenuItem { action: appActions.saveLayout }
                        MenuItem { action: appActions.newFromLayout }
                        MenuItem { action: appActions.addLayout }
                    }
                }

                // Divider
                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 28
                    Layout.leftMargin: 6
                    Layout.rightMargin: 6
                    color: "#555555"
                }

                Button { action: appActions.undo }
                Button { action: appActions.redo }

                // Divider
                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 28
                    Layout.leftMargin: 6
                    Layout.rightMargin: 6
                    color: "#555555"
                }

                Button { action: appActions.addBrowser }
                Button { action: appActions.addContainer }

                Item {
                    Layout.fillWidth: true
                }

                Button { action: appActions.fullScreen }
                Button { action: appActions.present }
                Button { action: appActions.settings }
                Button { action: appActions.log }
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

            // Where a new player should start (e.g. a video converted to
            // an audio track continues from where it was), by media id.
            property var pendingSeeks: ({})

            function setPendingSeek(mediaId, ms) {
                pendingSeeks[mediaId] = ms
            }

            function takePendingSeek(mediaId) {
                var ms = pendingSeeks[mediaId]
                delete pendingSeeks[mediaId]
                return ms === undefined ? -1 : ms
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
                actions: appActions
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

                    // Audio tracks draw nothing; they only host a player.
                    DelegateChoice {
                        roleValue: "audio"
                        AudioTrackObject { sceneItem: scene }
                    }
                }
            }
        }


        // -------------------------------------------------
        // Sidebar (Layers): a flyout on the right edge
        // -------------------------------------------------

        Sidebar {
            sceneItem: scene
            actions: appActions

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

        // Qt also re-sends hover updates without any movement (e.g. each
        // frame while something animates), so only a real change of
        // position counts as the mouse moving.
        HoverHandler {
            property point lastPosition: Qt.point(-1, -1)

            onPointChanged: {
                var p = point.scenePosition
                if (Math.abs(p.x - lastPosition.x) < 1 && Math.abs(p.y - lastPosition.y) < 1)
                    return
                lastPosition = p
                if (window.fullScreen)
                    exitButton.reveal()
            }
        }

        // Present: hide the mouse pointer once it has been still long
        // enough for the exit button to fade; moving it brings both back.
        // (A MouseArea, not a HoverHandler: its cursor change applies at
        // once, while the pointer is still. It takes no buttons, so
        // clicks go through to what's underneath.)
        MouseArea {
            anchors.fill: parent
            z: 2900000              // below only the exit button

            visible: window.presenting
            acceptedButtons: Qt.NoButton

            cursorShape: exitButton.opacity < 0.01 ? Qt.BlankCursor : Qt.ArrowCursor
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
                    if (exitArea.containsMouse || presentArea.containsMouse
                            || saveArea.containsMouse)
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

        // Full Screen (editing) only: go straight to Present. Shows and
        // fades together with the exit button.
        Rectangle {
            id: presentButton

            anchors.top: exitButton.top
            anchors.right: exitButton.left
            anchors.rightMargin: 8

            width: 40
            height: 40
            radius: 20

            z: 3000000

            color: presentArea.containsMouse ? "#e0404040" : "#b0202020"
            border.color: "#80ffffff"

            opacity: exitButton.opacity
            visible: window.fullScreenEditing && !window.presenting && opacity > 0

            // A "play" triangle, drawn (not a font glyph) so it looks the
            // same on every system.
            Shape {
                anchors.centerIn: parent
                anchors.horizontalCenterOffset: 2      // optical center
                width: 14
                height: 16
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    fillColor: "#ffffff"
                    strokeColor: "transparent"
                    startX: 0; startY: 0
                    PathLine { x: 14; y: 8 }
                    PathLine { x: 0; y: 16 }
                    PathLine { x: 0; y: 0 }
                }
            }

            MouseArea {
                id: presentArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: appActions.present.trigger()
            }

            ToolTip.visible: presentArea.containsMouse
            ToolTip.text: "Present (F5)"
            ToolTip.delay: 500
        }

        // Full Screen (editing) only: Save, left of Present. Fades with
        // the exit button too.
        Rectangle {
            id: saveButton

            anchors.top: exitButton.top
            anchors.right: presentButton.left
            anchors.rightMargin: 8

            width: 40
            height: 40
            radius: 20

            z: 3000000

            color: saveArea.containsMouse ? "#e0404040" : "#b0202020"
            border.color: "#80ffffff"

            opacity: exitButton.opacity
            visible: window.fullScreenEditing && !window.presenting && opacity > 0

            // A down arrow into a tray, drawn like the play triangle.
            Shape {
                anchors.centerIn: parent
                width: 16
                height: 16
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    strokeColor: "#ffffff"
                    strokeWidth: 2
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    // The arrow.
                    startX: 8; startY: 1
                    PathLine { x: 8; y: 10 }
                    PathMove { x: 4; y: 6 }
                    PathLine { x: 8; y: 10 }
                    PathLine { x: 12; y: 6 }
                    // The tray.
                    PathMove { x: 1; y: 11 }
                    PathLine { x: 1; y: 15 }
                    PathLine { x: 15; y: 15 }
                    PathLine { x: 15; y: 11 }
                }
            }

            MouseArea {
                id: saveArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: appActions.save.trigger()
            }

            ToolTip.visible: saveArea.containsMouse
            ToolTip.text: "Save (" + appSettings.shortcutText(appActions.save.shortcut) + ")"
            ToolTip.delay: 500
        }
    }
}
