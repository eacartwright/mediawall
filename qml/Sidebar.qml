import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Right-hand flyout panel, opened and closed with the tab on its left
// edge. Tabs: Layers (Audio comes with the Audio Rack).
// Overlays the canvas; hidden in Present mode (Main.qml).

Item {
    id: sidebar

    property bool open: false

    readonly property int panelWidth: 280

    width: handle.width + panelWidth


    // ---- Edge tab ----

    Rectangle {
        id: handle

        anchors.verticalCenter: parent.verticalCenter
        x: panel.x - width

        width: 22
        height: 96
        radius: 4

        color: handleArea.containsMouse ? "#3a3a3a" : "#2c2c2c"
        border.color: "#555555"

        Text {
            anchors.centerIn: parent
            rotation: -90
            text: sidebar.open ? "Layers  ▸" : "◂  Layers"
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

                TabButton { text: "Layers" }
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

                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        clip: true
                        model: sceneModel.layers

                        ScrollBar.vertical: ScrollBar {}

                        delegate: Rectangle {
                            id: row

                            required property var modelData
                            readonly property bool isSelected:
                                modelData.id === sceneModel.selectedId

                            width: ListView.view.width
                            height: 30

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

                            MouseArea {
                                id: rowArea
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: sceneModel.select(row.modelData.id)
                            }
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

                        readonly property bool hasSelection: sceneModel.selectedId !== ""

                        Button {
                            Layout.fillWidth: true
                            text: "Top"
                            enabled: parent.hasSelection && !sceneModel.selectedAtFront
                            onClicked: sceneModel.bringToFront(sceneModel.selectedId)
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Up"
                            enabled: parent.hasSelection && !sceneModel.selectedAtFront
                            onClicked: sceneModel.bringForward(sceneModel.selectedId)
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Down"
                            enabled: parent.hasSelection && !sceneModel.selectedAtBack
                            onClicked: sceneModel.sendBackward(sceneModel.selectedId)
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Bottom"
                            enabled: parent.hasSelection && !sceneModel.selectedAtBack
                            onClicked: sceneModel.sendToBack(sceneModel.selectedId)
                        }
                    }
                }
            }
        }
    }
}
