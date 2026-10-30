import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Media Memory: every loaded image, GIF, and video (free, in containers,
// in browser previews) with an estimate of the video memory it uses,
// biggest first (bridge/media_memory.py, core/media_cost.py). Refreshes
// in place every two seconds while open. Clicking a row selects its
// object. Opened from Settings > Performance.

ApplicationWindow {
    id: memoryWindow

    title: "Mediawall — Media Memory"

    width: 760
    height: 520

    color: "#1e1e1e"

    property bool paused: false

    function refresh() {
        mediaMemory.refresh()
    }

    onVisibleChanged: if (visible) refresh()

    Timer {
        interval: 2000
        repeat: true
        running: memoryWindow.visible && !memoryWindow.paused
        onTriggered: memoryWindow.refresh()
    }

    readonly property var columnWidths: [0, 90, 80, 110, 90]   // 0 = the rest

    // ---- Summary ----

    Rectangle {
        id: summary

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: summaryColumn.implicitHeight + 16
        color: "#2a2a2a"

        ColumnLayout {
            id: summaryColumn

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 3

            Label {
                objectName: "memoryTotal"            // found by tests/app
                text: "Estimated for loaded media: <b>" + mediaMemory.totalText + "</b>"
                      + " in " + rows.count + (rows.count === 1 ? " item" : " items")
                textFormat: Text.StyledText
            }

            Label {
                visible: mediaMemory.gpuText !== ""
                text: "GPU in use (all apps): " + mediaMemory.gpuText
                      + (mediaMemory.processText !== ""
                         ? "  ·  Mediawall's video decoders: " + mediaMemory.processText : "")
                color: "#cccccc"
            }

            Label {
                text: "Hardware video decoding: "
                      + (mediaMemory.hardwareDecoding ? "on (" + appSettings.hwDecodingActive + ")"
                                                      : "off")
                      + "  ·  Fell back to CPU: " + mediaMemory.fallbacks
                      + "  ·  GPU out-of-memory messages: " + mediaMemory.oomErrors
                color: mediaMemory.oomErrors > 0 ? "#e0c060" : "#cccccc"
            }

            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Estimates from each item's decoded size. Videos decoded in hardware keep "
                      + "a pool of frames on the GPU; the app, driver, and other programs use "
                      + "more besides."
                color: "#888888"
                font.pixelSize: 11
            }
        }
    }

    // ---- Table ----

    Row {
        id: header

        anchors.top: summary.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 6
        anchors.leftMargin: 10
        height: 24

        Repeater {
            model: ["Name", "Where", "Kind", "Decoded size", "Estimate"]

            Label {
                required property string modelData
                required property int index

                width: memoryWindow.columnWidth(index, header.width)
                height: header.height
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: index === 4 ? Text.AlignRight : Text.AlignLeft
                text: modelData
                font.bold: true
                color: "#bbbbbb"
            }
        }
    }

    function columnWidth(index, total) {
        if (columnWidths[index] > 0)
            return columnWidths[index]
        var fixed = 0
        for (var i = 0; i < columnWidths.length; i++)
            fixed += columnWidths[i]
        return Math.max(120, total - fixed)
    }

    ListView {
        id: rows
        objectName: "memoryRows"                    // found by tests/app

        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: bar.top
        anchors.leftMargin: 4
        anchors.rightMargin: 4

        clip: true
        model: mediaMemory.rows

        // Keep the scroll position when the list is replaced.
        property real keepY: 0
        onContentYChanged: if (moving) keepY = contentY
        onModelChanged: Qt.callLater(function() {
            rows.contentY = Math.min(rows.keepY, Math.max(0, rows.contentHeight - rows.height))
        })

        delegate: Rectangle {
            id: row

            required property var modelData
            required property int index

            width: ListView.view.width
            height: 24
            color: rowMouse.containsMouse ? "#333a44"
                   : index % 2 ? "#232323" : "transparent"

            readonly property var cells: [
                modelData.name, modelData.place, modelData.kind,
                modelData.size, modelData.cost
            ]

            Row {
                anchors.fill: parent
                anchors.leftMargin: 6

                Repeater {
                    model: row.cells

                    Text {
                        required property string modelData
                        required property int index

                        width: memoryWindow.columnWidth(index, header.width)
                        height: row.height
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: index === 4 ? Text.AlignRight : Text.AlignLeft
                        elide: Text.ElideMiddle
                        text: modelData
                        color: "#dddddd"
                        font.family: index >= 3 ? fixedFontFamily : Qt.application.font.family
                        font.pixelSize: 12
                    }
                }
            }

            MouseArea {
                id: rowMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (row.modelData.objectId) sceneModel.select(row.modelData.objectId)
            }
        }

        ScrollBar.vertical: ScrollBar {}

        Text {
            anchors.centerIn: parent
            visible: rows.count === 0
            text: "No images or videos loaded"
            color: "#888888"
        }
    }

    // ---- Bottom bar ----

    Rectangle {
        id: bar

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        height: 40
        color: "#2a2a2a"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8

            spacing: 6

            Label {
                Layout.fillWidth: true
                text: memoryWindow.paused ? "Paused" : "Updates every 2 seconds · click a row to select it"
                color: "#999999"
            }

            Button {
                text: memoryWindow.paused ? "Resume" : "Pause"
                onClicked: memoryWindow.paused = !memoryWindow.paused
            }

            Button {
                text: "Refresh"
                onClicked: memoryWindow.refresh()
            }
        }
    }
}
