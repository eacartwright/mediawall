import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Everything the app would print to a terminal: FFmpeg, Qt, and Python
// messages (bridge/log_capture.py). Opened from the toolbar's Log button.

ApplicationWindow {
    id: logWindow

    title: "MediaWall — Log"

    width: 900
    height: 480

    color: "#1e1e1e"

    // Pause is for reading while the window is open.
    onClosing: appLog.paused = false

    ListView {
        id: lines

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: bar.top
        anchors.margins: 6

        clip: true
        model: appLog

        // Keep following new lines while scrolled to the bottom.
        property bool follow: true
        onMovementEnded: follow = atYEnd
        onCountChanged: if (follow) Qt.callLater(positionViewAtEnd)

        delegate: Text {
            required property string display

            width: ListView.view.width
            text: display
            wrapMode: Text.WrapAnywhere

            color: display.startsWith("[warning]") ? "#e0c060"
                   : display.startsWith("[critical]") || display.startsWith("[fatal]")
                     || display.startsWith("Traceback") ? "#f08070"
                   : "#cccccc"
            font.family: fixedFontFamily     // system fixed-width font
            font.pixelSize: 12
        }

        ScrollBar.vertical: ScrollBar {}
    }

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
                id: statusLabel
                objectName: "logStatus"

                Layout.fillWidth: true
                elide: Text.ElideMiddle
                text: exportedTo !== "" ? "Exported to " + exportedTo
                      : appLog.paused ? "Paused · " + appLog.heldCount + " new lines held back"
                      : lines.count + " lines · also saved to logs/mediawall.log"
                color: appLog.paused && exportedTo === "" ? "#e0c060" : "#999999"

                // The last export's path, shown for a few seconds.
                property string exportedTo: ""

                Timer {
                    id: exportedTimer
                    interval: 4000
                    onTriggered: statusLabel.exportedTo = ""
                }

                function showExported(path) {
                    exportedTo = path
                    exportedTimer.restart()
                }
            }

            // Holds new lines back so the view stays still (they are
            // still captured, and written to the log file).
            Button {
                objectName: "logPauseButton"
                text: appLog.paused ? "Resume" : "Pause"
                onClicked: {
                    if (appLog.paused)
                        lines.follow = true     // show the held lines
                    appLog.paused = !appLog.paused
                }
            }

            Button {
                objectName: "logExportButton"
                text: "Export…"
                onClicked: {
                    var path = appLog.exportLog()
                    if (path !== "")
                        statusLabel.showExported(path)
                }
            }

            Button {
                text: "Copy All"
                onClicked: {
                    copyHelper.text = appLog.allText()
                    copyHelper.selectAll()
                    copyHelper.copy()
                    copyHelper.text = ""
                }
            }

            Button {
                text: "Clear"
                onClicked: appLog.clear()
            }
        }
    }

    // Off-screen helper for putting text on the clipboard.
    TextEdit {
        id: copyHelper
        visible: false
    }
}
