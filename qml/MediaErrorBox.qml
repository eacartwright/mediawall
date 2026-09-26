import QtQuick

// "Missing file" / "Can't display file" placeholder.

Rectangle {
    id: box

    property bool missing: true
    property string name: ""
    property string path: ""

    color: "#2a2020"
    border.color: "#a05050"
    border.width: 1

    Column {
        anchors.centerIn: parent
        width: parent.width - 16

        spacing: 4

        Text {
            width: parent.width

            text: box.missing ? "Missing file" : "Can't display file"

            color: "#e08080"
            font.pixelSize: 14
            font.bold: true

            horizontalAlignment: Text.AlignHCenter
        }

        Text {
            width: parent.width

            text: box.name

            color: "#bbbbbb"
            font.pixelSize: 12

            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideMiddle
        }

        Text {
            width: parent.width

            text: box.path

            color: "#888888"
            font.pixelSize: 10

            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideMiddle
        }
    }
}
