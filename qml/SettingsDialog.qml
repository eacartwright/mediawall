import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// App-wide settings (bridge/app_settings.py). Changes apply at once and
// are saved immediately; Close just closes. Opened from the toolbar.
// Tabs: General (the settings), Shortcuts (every key and modifier the
// app responds to, read from AppActions where they're defined), About.

Dialog {
    id: dialog

    // AppActions, for the Shortcuts tab's key list.
    property var actions

    title: "Settings"
    modal: true
    standardButtons: Dialog.Close

    anchors.centerIn: Overlay.overlay
    width: 500

    // Fusion's own border (palette.mid) barely shows on the dark canvas.
    background: Rectangle {
        color: dialog.palette.window
        border.color: dialog.palette.midlight
        radius: 2
    }

    // A shortcut as the platform writes it ("Ctrl+D", or a StandardKey).
    function keys(shortcut) {
        return appSettings.shortcutText(shortcut)
    }

    ColumnLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 10

        TabBar {
            id: tabs
            objectName: "settingsTabs"          // found by tests/app
            Layout.fillWidth: true

            TabButton { text: "General" }
            TabButton { text: "Shortcuts" }
            TabButton { text: "About" }
        }

        StackLayout {
            Layout.fillWidth: true
            currentIndex: tabs.currentIndex

            // =============================================
            // General
            // =============================================

            ColumnLayout {
                spacing: 6

                // ---- Mouse-wheel zoom step ----

                Label {
                    text: "Mouse-wheel zoom step"
                    font.bold: true
                }

                RowLayout {
                    spacing: 8

                    SpinBox {
                        id: zoomStepBox
                        objectName: "zoomStepBox"        // found by tests/app

                        from: appSettings.zoomStepMin
                        to: appSettings.zoomStepMax
                        editable: true

                        value: appSettings.zoomStep
                        onValueModified: appSettings.zoomStep = value

                        textFromValue: function(value) { return value + " %" }
                        valueFromText: function(text) { return parseInt(text) }
                    }

                    Label {
                        text: "per wheel notch"
                        color: "#bbbbbb"
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "Default (" + appSettings.zoomStepDefault + " %)"
                        enabled: appSettings.zoomStep !== appSettings.zoomStepDefault
                        onClicked: appSettings.resetZoomStep()
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "How much each notch of the mouse wheel zooms: free images, "
                          + "containers and their pictures, and browser previews."
                    color: "#999999"
                    font.pixelSize: 12
                }

                // ---- Playback speed range ----

                Label {
                    Layout.topMargin: 12
                    text: "Playback speed range"
                    font.bold: true
                }

                RowLayout {
                    spacing: 8

                    Label { text: "Slowest" }

                    // Hundredths, shown as a speed: 25 -> "0.25×".
                    SpinBox {
                        from: 25
                        to: 100
                        stepSize: 25
                        value: Math.round(appSettings.speedMin * 100)
                        onValueModified: appSettings.speedMin = value / 100
                        textFromValue: function(value) { return (value / 100).toFixed(2) + "×" }
                        valueFromText: function(text) { return Math.round(parseFloat(text) * 100) }
                    }

                    Label { text: "Fastest"; Layout.leftMargin: 8 }

                    SpinBox {
                        from: 100
                        to: 400
                        stepSize: 25
                        value: Math.round(appSettings.speedMax * 100)
                        onValueModified: appSettings.speedMax = value / 100
                        textFromValue: function(value) { return (value / 100).toFixed(2) + "×" }
                        valueFromText: function(text) { return Math.round(parseFloat(text) * 100) }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "Default"
                        enabled: appSettings.speedMin !== appSettings.speedMinDefault
                                 || appSettings.speedMax !== appSettings.speedMaxDefault
                        onClicked: appSettings.resetSpeedRange()
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "The range of the speed slider in the Playback tab (default "
                          + appSettings.speedMinDefault + "× to " + appSettings.speedMaxDefault
                          + "×). With Keep pitch off, pitch follows speed."
                    color: "#999999"
                    font.pixelSize: 12
                }

                // ---- Hold to step through files ----

                Label {
                    Layout.topMargin: 12
                    text: "Holding previous / next file"
                    font.bold: true
                }

                RowLayout {
                    spacing: 8

                    Label { text: "Wait" }

                    SpinBox {
                        objectName: "stepDelayBox"       // found by tests/app
                        from: 100
                        to: 2000
                        stepSize: 50
                        editable: true
                        value: appSettings.stepRepeatDelay
                        onValueModified: appSettings.stepRepeatDelay = value
                        textFromValue: function(value) { return value + " ms" }
                        valueFromText: function(text) { return parseInt(text) }
                    }

                    Label { text: "then every"; Layout.leftMargin: 4 }

                    SpinBox {
                        objectName: "stepIntervalBox"    // found by tests/app
                        from: 30
                        to: 1000
                        stepSize: 10
                        editable: true
                        value: appSettings.stepRepeatInterval
                        onValueModified: appSettings.stepRepeatInterval = value
                        textFromValue: function(value) { return value + " ms" }
                        valueFromText: function(text) { return parseInt(text) }
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "Default"
                        enabled: appSettings.stepRepeatDelay !== appSettings.stepRepeatDelayDefault
                                 || appSettings.stepRepeatInterval !== appSettings.stepRepeatIntervalDefault
                        onClicked: appSettings.resetStepRepeat()
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Holding Left / Right, a back / forward thumb button, a sideways "
                          + "wheel tilt, or a browser's ◀ ▶ steps once, waits, then keeps "
                          + "stepping until let go (default " + appSettings.stepRepeatDelayDefault
                          + " ms, then every " + appSettings.stepRepeatIntervalDefault
                          + " ms). A held tilt can't step faster than the mouse sends it."
                    color: "#999999"
                    font.pixelSize: 12
                }
            }

            // =============================================
            // Shortcuts
            // =============================================

            ScrollView {
                id: shortcutsView
                objectName: "shortcutsList"         // found by tests/app
                Layout.preferredHeight: 360
                contentWidth: availableWidth
                clip: true

                // [group, what it does, keys]. Commands read their keys from
                // AppActions, so this list can't drift from the real ones.
                readonly property var rows: {
                    var a = dialog.actions
                    if (!a)
                        return []
                    var r = []
                    function cmd(group, action, extra) {
                        r.push([group, action.text.replace("…", ""),
                                dialog.keys(action.shortcut) + (extra ? ",  " + extra : "")])
                    }
                    cmd("File", a.newWall)
                    cmd("File", a.open)
                    cmd("File", a.save)
                    cmd("File", a.saveAs)
                    cmd("Edit", a.undo)
                    cmd("Edit", a.redo, dialog.keys("Ctrl+Y"))
                    cmd("Edit", a.duplicate)
                    cmd("Edit", a.deleteSelected)
                    r.push(["Edit", "Deselect", dialog.keys("Esc")])
                    cmd("Arrange", a.bringToFront)
                    cmd("Arrange", a.bringForward)
                    cmd("Arrange", a.sendBackward)
                    cmd("Arrange", a.sendToBack)
                    r.push(["Browsing files", "Previous / next file (hold to repeat)",
                            dialog.keys("Left") + " / " + dialog.keys("Right")])
                    r.push(["Browsing files", "Previous / next file (hold to repeat)",
                            "Mouse back / forward buttons"])
                    r.push(["Browsing files", "Previous / next file",
                            "Tilt the wheel left / right"])
                    cmd("View", a.fullScreen)
                    cmd("View", a.present)
                    r.push(["View", "Leave Present / Full Screen",
                            dialog.keys("Esc") + ",  double-click the canvas"])
                    r.push(["Adjust mode (a container)", "Finish adjusting",
                            dialog.keys("Return") + ",  " + dialog.keys("Space") + ",  "
                            + dialog.keys("Esc")])
                    r.push(["Containers", "Turn the picture, not the container",
                            "Hold Ctrl while dragging the rotate knob"])
                    r.push(["Dragging media", "Place on top instead of into a container",
                            "Hold Shift while dragging"])
                    return r
                }

                ColumnLayout {
                    width: shortcutsView.availableWidth
                    spacing: 2

                    Repeater {
                        model: shortcutsView.rows

                        ColumnLayout {
                            required property var modelData
                            required property int index

                            Layout.fillWidth: true
                            spacing: 2

                            // A heading where a new group starts.
                            Label {
                                visible: index === 0
                                         || shortcutsView.rows[index - 1][0] !== modelData[0]
                                Layout.topMargin: index === 0 ? 0 : 10
                                text: modelData[0]
                                font.bold: true
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Label {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 10
                                    wrapMode: Text.WordWrap
                                    text: modelData[1]
                                }

                                Label {
                                    Layout.maximumWidth: shortcutsView.availableWidth * 0.5
                                    horizontalAlignment: Text.AlignRight
                                    wrapMode: Text.WordWrap
                                    text: modelData[2]
                                    color: "#bbbbbb"
                                    font.family: fixedFontFamily
                                }
                            }
                        }
                    }
                }
            }

            // =============================================
            // About
            // =============================================

            ColumnLayout {
                spacing: 8

                Image {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 12
                    source: appIconUrl
                    sourceSize.width: 96
                    sourceSize.height: 96
                    fillMode: Image.PreserveAspectFit
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "MediaWall"
                    font.bold: true
                    font.pixelSize: 22
                }

                Label {
                    objectName: "aboutVersion"         // found by tests/app
                    Layout.alignment: Qt.AlignHCenter
                    text: "Version " + appVersion
                    color: "#bbbbbb"
                }

                Label {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: "Arrange images, GIFs, video, and viewports freely on a canvas."
                    color: "#999999"
                }

                Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 6
                    Layout.bottomMargin: 12
                    textFormat: Text.StyledText
                    text: "<a href=\"https://evans.tools\" style=\"color:#5da9ff\">evans.tools</a>"
                    onLinkActivated: function(link) { Qt.openUrlExternally(link) }

                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                }
            }
        }
    }
}
