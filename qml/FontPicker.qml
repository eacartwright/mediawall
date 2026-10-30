import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Choosing a font family (the Text tab; readme section 5.4): a button
// showing the current font, opening a list of every installed family,
// each shown in its own font, with a box to type part of a name. The
// wheel scrolls three rows a notch. (A ComboBox's list scrolled only a
// pixel or two a notch through hundreds of fonts.)

Button {
    id: picker

    // The chosen family; "" is the app's own font ("Default").
    property string family: ""

    // A family was picked ("" for Default).
    signal picked(string family)

    readonly property var families: [""].concat(Qt.fontFamilies())
    readonly property int rowHeight: 26

    text: family === "" ? "Default" : family
    font.family: family === "" ? Qt.application.font.family : family
    contentItem: Text {
        text: picker.text
        font: picker.font
        color: picker.palette.buttonText
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        rightPadding: 16
        Text {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: "▾"
            color: picker.palette.buttonText
        }
    }

    onClicked: {
        filterField.text = ""
        popup.open()
    }

    function choose(name) {
        popup.close()
        if (name !== family)
            picked(name)
    }

    Popup {
        id: popup
        objectName: "fontPopup"

        y: picker.height
        width: picker.width
        height: Math.min(420, (picker.Window.height || 600) - picker.mapToItem(null, 0, picker.height).y - 12)
        padding: 4

        onOpened: {
            filterField.forceActiveFocus()
            list.currentIndex = Math.max(0, list.matches.indexOf(picker.family))
            list.positionViewAtIndex(list.currentIndex, ListView.Center)
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 4

            TextField {
                id: filterField
                objectName: "fontFilter"
                Layout.fillWidth: true
                placeholderText: "Type to find a font"
                onTextChanged: list.currentIndex = 0

                Keys.onDownPressed: list.currentIndex = Math.min(list.count - 1, list.currentIndex + 1)
                Keys.onUpPressed: list.currentIndex = Math.max(0, list.currentIndex - 1)
                Keys.onPressed: function(event) {
                    var page = Math.floor(list.height / picker.rowHeight)
                    if (event.key === Qt.Key_PageDown) {
                        list.currentIndex = Math.min(list.count - 1, list.currentIndex + page)
                        event.accepted = true
                    } else if (event.key === Qt.Key_PageUp) {
                        list.currentIndex = Math.max(0, list.currentIndex - page)
                        event.accepted = true
                    }
                }
                onAccepted: {
                    if (list.currentIndex >= 0 && list.currentIndex < list.count)
                        picker.choose(list.matches[list.currentIndex])
                }
            }

            ListView {
                id: list
                objectName: "fontList"

                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                highlightMoveDuration: 0

                // Families whose name holds the typed text (any case).
                readonly property var matches: {
                    var f = filterField.text.trim().toLowerCase()
                    if (f === "")
                        return picker.families
                    return picker.families.filter(function(name) {
                        return name !== "" && name.toLowerCase().indexOf(f) >= 0
                    })
                }
                model: matches
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)

                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOn }

                delegate: Rectangle {
                    id: row
                    required property string modelData
                    required property int index

                    width: ListView.view.width - 12
                    height: picker.rowHeight
                    color: index === list.currentIndex ? "#2f5f9a"
                         : rowArea.containsMouse ? "#3a3a3a" : "transparent"
                    radius: 2

                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 6
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        text: row.modelData === "" ? "Default" : row.modelData
                        font.family: row.modelData === "" ? Qt.application.font.family : row.modelData
                        font.pixelSize: 15
                        color: "#ffffff"
                    }

                    MouseArea {
                        id: rowArea
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: picker.choose(row.modelData)
                    }
                }

                // Three rows a wheel notch (touchpads: as they move).
                WheelHandler {
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: function(event) {
                        var dy = event.pixelDelta.y !== 0 ? event.pixelDelta.y
                                                          : event.angleDelta.y / 120 * 3 * picker.rowHeight
                        var maxY = Math.max(0, list.contentHeight - list.height) + list.originY
                        list.contentY = Math.max(list.originY, Math.min(maxY, list.contentY - dy))
                    }
                }
            }
        }
    }
}
