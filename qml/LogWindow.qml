import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Everything the app would print to a terminal: FFmpeg, Qt, and Python
// messages (bridge/log_capture.py). Opened from the toolbar's Log button.

ApplicationWindow {
    id: logWindow

    title: "Media Wall — Log"

    width: 900
    height: 480

    color: "#1e1e1e"

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
                Layout.fillWidth: true
                text: lines.count + " lines · also saved to logs/mediawall.log"
                color: "#999999"
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
