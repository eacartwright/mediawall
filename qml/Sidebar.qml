import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Right-hand flyout panel, opened and closed with the tab on its left
// edge. Tabs: Layers, and Playback (every video and audio track's sound
// and playback settings; readme section 14).
// Overlays the canvas; hidden in Present mode (Main.qml).

Item {
    id: sidebar

    property bool open: false

    // The scene item (Main.qml), for looking up players by media id.
    property Item sceneItem

    // Shared commands (AppActions.qml), set in Main.qml.
    property var actions

    // Show the Playback tab when a track is added.
    Connections {
        target: sceneModel
        function onAudioTrackAdded(trackId) {
            sidebar.open = true
            tabs.currentIndex = 1
        }
    }

    function formatMs(ms) {
        var t = Math.max(0, ms) / 1000
        var m = Math.floor(t / 60)
        var sec = Math.floor(t - m * 60)
        return m + ":" + (sec < 10 ? "0" : "") + sec
    }

    function formatMsPrecise(ms) {
        var t = Math.max(0, ms) / 1000
        var m = Math.floor(t / 60)
        var sec = (t - m * 60).toFixed(1)
        return m + ":" + (sec < 10 ? "0" : "") + sec
    }

    readonly property int panelWidth: 280

    width: handle.width + panelWidth


    // ---- Edge tab ----

    Rectangle {
        id: handle
        objectName: "sidebarHandle"      // objectNames: found by tests/app

        anchors.verticalCenter: parent.verticalCenter
        x: panel.x - width

        width: 22
        height: 160
        radius: 4

        color: handleArea.containsMouse ? "#3a3a3a" : "#2c2c2c"
        border.color: "#555555"

        Text {
            anchors.centerIn: parent
            rotation: -90
            text: sidebar.open ? "Layers · Playback  ▸" : "◂  Layers · Playback"
            color: "#dddddd"
            font.pixelSize: 12
        }

        MouseArea {
            id: handleArea
            anchors.fill: parent
            hoverEnabled: true
            onClicked: sidebar.open = !sidebar.open
        }
    }


    // ---- Panel ----

    Rectangle {
        id: panel

        y: 0
        width: sidebar.panelWidth
        height: sidebar.height

        // Slides out past the window's right edge when closed.
        x: sidebar.open ? handle.width : handle.width + sidebar.panelWidth
        Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

        visible: x < sidebar.width

        color: "#262626"
        border.color: "#444444"

        // Keep clicks and scrolling on the panel from reaching the canvas.
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: function(wheel) { wheel.accepted = true }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 1
            spacing: 0

            TabBar {
                id: tabs
                Layout.fillWidth: true

                TabButton { text: "Layers"; objectName: "layersTab" }
                TabButton { text: "Playback"; objectName: "playbackTab" }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabs.currentIndex

                // ---- Layers ----

                ColumnLayout {
                    spacing: 0

                    ListView {
                        id: layerList
                        objectName: "layerList"

                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        clip: true
                        model: sceneModel.layers
                        boundsBehavior: Flickable.StopAtBounds

                        ScrollBar.vertical: ScrollBar {}

                        delegate: Rectangle {
                            id: row

                            required property int index
                            required property var modelData
                            readonly property bool isSelected:
                                modelData.id === sceneModel.selectedId

                            width: ListView.view.width
                            height: layerList.rowHeight

                            opacity: layerList.dragId === modelData.id ? 0.5 : 1

                            color: isSelected ? "#3d7fc4"
                                   : rowArea.containsMouse ? "#333333"
                                   : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 8

                                // Type badge
                                Rectangle {
                                    Layout.preferredWidth: 42
                                    Layout.preferredHeight: 18
                                    radius: 3

                                    color: {
                                        switch (row.modelData.kind) {
                                        case "video": return "#7a4a9a"
                                        case "audio": return "#9a7a3a"
                                        case "container": return "#3a7a5a"
                                        case "browser": return "#4a5a7a"
                                        default: return "#5a5a5a"
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: {
                                            switch (row.modelData.kind) {
                                            case "video": return "video"
                                            case "audio": return "audio"
                                            case "container": return "box"
                                            case "browser": return "browse"
                                            default: return "image"
                                            }
                                        }
                                        color: "#ffffff"
                                        font.pixelSize: 10
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: row.modelData.name
                                    color: "#eeeeee"
                                    font.pixelSize: 12
                                    elide: Text.ElideMiddle
                                }
                            }

                            // Press selects; dragging up or down reorders.
                            MouseArea {
                                id: rowArea
                                anchors.fill: parent
                                hoverEnabled: true

                                property real pressY
                                property bool dragging: false

                                // Keep the list from taking the drag to scroll.
                                preventStealing: true

                                cursorShape: dragging ? Qt.ClosedHandCursor : Qt.ArrowCursor

                                onPressed: function(mouse) {
                                    pressY = mouse.y
                                    dragging = false
                                    sceneModel.select(row.modelData.id)
                                }

                                onPositionChanged: function(mouse) {
                                    if (!pressed)
                                        return
                                    if (!dragging && Math.abs(mouse.y - pressY) > 6) {
                                        dragging = true
                                        layerList.startDrag(row.modelData.id, row.index)
                                    }
                                    if (dragging) {
                                        var p = mapToItem(layerList.contentItem, mouse.x, mouse.y)
                                        layerList.dropSlot = layerList.slotAt(p.y)
                                    }
                                }

                                onReleased: {
                                    if (dragging)
                                        layerList.finishDrag()
                                    dragging = false
                                }

                                onCanceled: {
                                    layerList.cancelDrag()
                                    dragging = false
                                }
                            }
                        }

                        readonly property int rowHeight: 30

                        // ---- Drag-to-reorder ----
                        // dropSlot is the gap the row would go into:
                        // 0 = above the first row, count = below the last.

                        property string dragId: ""
                        property int dragFrom: -1
                        property int dropSlot: -1

                        function slotAt(contentY) {
                            return Math.max(0, Math.min(count, Math.round(contentY / rowHeight)))
                        }

                        function startDrag(id, from) {
                            dragId = id
                            dragFrom = from
                            dropSlot = from
                        }

                        function finishDrag() {
                            var position = dropSlot > dragFrom ? dropSlot - 1 : dropSlot
                            if (dragId !== "" && position !== dragFrom)
                                sceneModel.moveLayer(dragId, position)
                            cancelDrag()
                        }

                        function cancelDrag() {
                            dragId = ""
                            dragFrom = -1
                            dropSlot = -1
                        }

                        // Where the dragged row would land.
                        Rectangle {
                            parent: layerList.contentItem
                            z: 10
                            visible: layerList.dragId !== ""
                                     && layerList.dropSlot !== layerList.dragFrom
                                     && layerList.dropSlot !== layerList.dragFrom + 1
                            x: 4
                            width: layerList.width - 8
                            y: Math.max(0, layerList.dropSlot * layerList.rowHeight - height / 2)
                            height: 3
                            radius: 1
                            color: "#3d7fc4"
                        }

                        // Keep the selected row in view.
                        function revealSelected() {
                            var layers = sceneModel.layers
                            for (var i = 0; i < layers.length; i++) {
                                if (layers[i].id === sceneModel.selectedId) {
                                    positionViewAtIndex(i, ListView.Contain)
                                    return
                                }
                            }
                        }

                        Connections {
                            target: sceneModel
                            function onSelectedIdChanged() { Qt.callLater(layerList.revealSelected) }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: layerList.count === 0
                            text: "Nothing on the canvas yet"
                            color: "#888888"
                            font.pixelSize: 12
                        }
                    }

                    // Stacking for the selected object. (Browsers stay
                    // above everything else; they reorder among themselves.)
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.margins: 6
                        spacing: 4


                        Button {
                            Layout.fillWidth: true
                            action: sidebar.actions.bringToFront
                            text: "Top"            // shorter than the action's name
                        }

                        Button {
                            Layout.fillWidth: true
                            action: sidebar.actions.bringForward
                            text: "Up"            // shorter than the action's name
                        }

                        Button {
                            Layout.fillWidth: true
                            action: sidebar.actions.sendBackward
                            text: "Down"            // shorter than the action's name
                        }

                        Button {
                            Layout.fillWidth: true
                            action: sidebar.actions.sendToBack
                            text: "Bottom"            // shorter than the action's name
                        }
                    }
                }

                // ---- Playback ----

                ListView {
                    id: audioList

                    clip: true
                    spacing: 1
                    model: sceneModel.audioItems

                    ScrollBar.vertical: ScrollBar {}

                    delegate: Rectangle {
                        id: card

                        required property int index
                        required property string itemId
                        required property string ownerId
                        required property string name
                        required property string kind
                        required property bool isTrack
                        required property bool inContainer
                        required property bool missing
                        required property bool playing
                        required property bool muted
                        required property real volume
                        required property bool loop
                        required property real speed
                        required property bool preservePitch
                        required property real loopA
                        required property real loopB

                        // The player on the canvas, for position (A/B).
                        readonly property var view: {
                            var scene = sidebar.sceneItem
                            if (!scene)
                                return null
                            scene.mediaViewsVersion        // re-evaluate on changes
                            return scene.viewFor(itemId)
                        }

                        readonly property bool isSelected: ownerId === sceneModel.selectedId

                        width: ListView.view.width
                        height: cardColumn.implicitHeight + 12

                        color: isSelected ? "#2f4a66" : "#2c2c2c"

                        // Clicking the card (not a control) selects the
                        // video, or the container holding it.
                        MouseArea {
                            anchors.fill: parent
                            onClicked: sceneModel.select(card.ownerId)
                        }

                        ColumnLayout {
                            id: cardColumn

                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 6
                            spacing: 2

                            // ---- Name and position ----
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                Rectangle {
                                    Layout.preferredWidth: 38
                                    Layout.preferredHeight: 16
                                    radius: 3
                                    color: card.kind === "audio" ? "#9a7a3a" : "#7a4a9a"
                                    Text {
                                        anchors.centerIn: parent
                                        text: card.kind
                                        color: "#ffffff"
                                        font.pixelSize: 10
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: card.name + (card.inContainer ? "  (in container)" : "")
                                          + (card.isTrack && card.kind === "video" ? "  (audio only)" : "")
                                          + (card.missing ? "  — missing" : "")
                                    color: card.missing ? "#e08080" : "#eeeeee"
                                    font.pixelSize: 12
                                    elide: Text.ElideMiddle
                                }

                                Text {
                                    visible: card.view !== null && card.view.duration > 0
                                    text: card.view
                                          ? sidebar.formatMs(card.view.position) + " / "
                                            + sidebar.formatMs(card.view.duration)
                                          : ""
                                    color: "#aaaaaa"
                                    font.pixelSize: 11
                                }

                                Button {
                                    Layout.preferredHeight: 22
                                    visible: card.missing
                                    text: "Locate…"
                                    onClicked: sceneModel.locateMissing(card.itemId)
                                }

                                // Tracks have no canvas item, so they're
                                // removed here (undoable).
                                Button {
                                    Layout.preferredHeight: 22
                                    Layout.preferredWidth: 26
                                    visible: card.isTrack
                                    text: "✕"
                                    onClicked: sceneModel.removeObject(card.itemId)
                                    ToolTip.visible: hovered
                                    ToolTip.text: "Remove this audio track"
                                    ToolTip.delay: 500
                                }
                            }

                            // ---- Play, mute, volume ----
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                Button {
                                    Layout.preferredHeight: 24
                                    Layout.preferredWidth: 52
                                    text: card.playing ? "Pause" : "Play"
                                    onClicked: sceneModel.setPlaying(card.itemId, !card.playing)
                                }

                                Button {
                                    Layout.preferredHeight: 24
                                    Layout.preferredWidth: 60
                                    text: card.muted ? "Unmute" : "Mute"
                                    onClicked: sceneModel.setMuted(card.itemId, !card.muted)
                                }

                                // The mouse wheel over the slider changes the volume.
                                Slider {
                                    Layout.fillWidth: true
                                    from: 0
                                    to: 1
                                    value: card.volume
                                    wheelEnabled: true
                                    stepSize: 0.05
                                    opacity: card.muted ? 0.5 : 1
                                    onMoved: sceneModel.setVolume(card.itemId, value)
                                }

                                Text {
                                    Layout.preferredWidth: 32
                                    text: Math.round(card.volume * 100) + "%"
                                    color: "#cccccc"
                                    font.pixelSize: 11
                                    horizontalAlignment: Text.AlignRight
                                }
                            }

                            // ---- Speed and pitch ----
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                Text {
                                    text: "Speed"
                                    color: "#cccccc"
                                    font.pixelSize: 11
                                }

                                // Log scale over the range set in Settings
                                // (default 0.5x .. 3x).
                                Slider {
                                    objectName: "speedSlider"
                                    Layout.fillWidth: true
                                    from: Math.log2(appSettings.speedMin)
                                    to: Math.log2(appSettings.speedMax)
                                    value: Math.log2(card.speed)
                                    onMoved: {
                                        var v = Math.abs(value) < 0.05 ? 0 : value  // snap to 1x
                                        sceneModel.setSpeed(card.itemId, Math.pow(2, v))
                                    }
                                }

                                Text {
                                    Layout.preferredWidth: 38
                                    text: card.speed.toFixed(2) + "×"
                                    color: card.speed === 1 ? "#cccccc" : "#e0c060"
                                    font.pixelSize: 11
                                    horizontalAlignment: Text.AlignRight

                                    // Double-click resets to normal speed.
                                    MouseArea {
                                        anchors.fill: parent
                                        onDoubleClicked: sceneModel.setSpeed(card.itemId, 1.0)
                                    }
                                }

                                CheckBox {
                                    checked: card.preservePitch
                                    onToggled: {
                                        sceneModel.setPreservePitch(card.itemId, checked)
                                        checked = Qt.binding(function() { return card.preservePitch })
                                    }
                                }

                                Text {
                                    text: "Keep pitch"
                                    color: "#cccccc"
                                    font.pixelSize: 11
                                    TapHandler {
                                        onTapped: sceneModel.setPreservePitch(card.itemId, !card.preservePitch)
                                    }
                                }
                            }

                            // ---- Loop and A-B ----
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                CheckBox {
                                    checked: card.loop
                                    onToggled: {
                                        sceneModel.setLoop(card.itemId, checked)
                                        checked = Qt.binding(function() { return card.loop })
                                    }
                                }

                                Text {
                                    text: "Loop"
                                    color: "#cccccc"
                                    font.pixelSize: 11
                                    TapHandler {
                                        onTapped: sceneModel.setLoop(card.itemId, !card.loop)
                                    }
                                }

                                Item { Layout.preferredWidth: 6 }

                                Button {
                                    Layout.preferredHeight: 24
                                    Layout.preferredWidth: 30
                                    text: "A"
                                    enabled: card.view !== null
                                    onClicked: sceneModel.setLoopA(card.itemId, card.view.position)
                                    ToolTip.visible: hovered
                                    ToolTip.text: "Set loop start here"
                                    ToolTip.delay: 500
                                }

                                Button {
                                    Layout.preferredHeight: 24
                                    Layout.preferredWidth: 30
                                    text: "B"
                                    enabled: card.view !== null
                                    onClicked: sceneModel.setLoopB(card.itemId, card.view.position)
                                    ToolTip.visible: hovered
                                    ToolTip.text: "Set loop end here"
                                    ToolTip.delay: 500
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: {
                                        if (card.loopA < 0 && card.loopB < 0)
                                            return ""
                                        return (card.loopA >= 0 ? sidebar.formatMsPrecise(card.loopA) : "–")
                                               + " → "
                                               + (card.loopB >= 0 ? sidebar.formatMsPrecise(card.loopB) : "–")
                                    }
                                    color: "#e0a84c"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }

                                Button {
                                    Layout.preferredHeight: 24
                                    Layout.preferredWidth: 30
                                    text: "✕"
                                    visible: card.loopA >= 0 || card.loopB >= 0
                                    onClicked: sceneModel.clearLoop(card.itemId)
                                    ToolTip.visible: hovered
                                    ToolTip.text: "Clear the A–B loop"
                                    ToolTip.delay: 500
                                }
                            }
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        width: parent.width - 32
                        visible: audioList.count === 0
                        text: "No videos or audio tracks yet.\n\nDouble-click an audio file in a "
                              + "Browser (or use Add to Audio) to add a track."
                        color: "#888888"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }
}
