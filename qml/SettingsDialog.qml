import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// App-wide settings (bridge/app_settings.py). Changes apply at once and
// are saved immediately; Close just closes. Opened from the toolbar.
// Tabs: General (the settings), Performance (video decoding, image
// size, and the Media Memory window), Speech (Piper and its voices;
// readme section 14.6), Shortcuts (every key and modifier the app
// responds to, read from AppActions where they're defined), About (with
// the button that opens the Log window).

Dialog {
    id: dialog

    // AppActions, for the Shortcuts tab's key list and the window buttons.
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

    // Open on the Speech tab (from the Speech panel).
    function openSpeech() {
        tabs.currentIndex = speechTabButton.TabBar.index
        open()
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
            TabButton { text: "Performance" }
            TabButton { id: speechTabButton; text: "Speech"; objectName: "speechSettingsTab" }
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

                // ---- Container background ----

                Label {
                    Layout.topMargin: 12
                    text: "Container background"
                    font.bold: true
                }

                RowLayout {
                    spacing: 8

                    Rectangle {
                        objectName: "containerColorSwatch"   // found by tests/app
                        implicitWidth: 40
                        implicitHeight: 24
                        radius: 3
                        color: appSettings.containerColor
                        border.color: swatchArea.containsMouse ? "#ffffff" : "#888888"

                        MouseArea {
                            id: swatchArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                containerColorDialog.selectedColor = appSettings.containerColor
                                containerColorDialog.open()
                            }
                        }
                    }

                    Label {
                        text: appSettings.containerColor
                        color: "#bbbbbb"
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "Default"
                        enabled: appSettings.containerColor !== appSettings.containerColorDefault
                        onClicked: appSettings.resetContainerColor()
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Shown where a container's picture doesn't reach (around a "
                          + "Fit picture, or an empty container)."
                    color: "#999999"
                    font.pixelSize: 12
                }

                ColorDialog {
                    id: containerColorDialog
                    title: "Container Background"
                    onAccepted: appSettings.containerColor = selectedColor.toString()
                }

                // ---- Snapping ----

                CheckBox {
                    objectName: "snappingBox"            // found by tests/app
                    Layout.topMargin: 8
                    text: "Snap to the wall's edges and other objects"
                    font.bold: true
                    checked: appSettings.snapping
                    onToggled: appSettings.snapping = checked
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Moving or resizing a container, picture, video, or text lines its "
                          + "edges and middle up with the screen's edges and other objects. "
                          + "Hold Ctrl while dragging to place it freely."
                    color: "#999999"
                    font.pixelSize: 12
                }
            }

            // =============================================
            // Performance
            // =============================================

            ColumnLayout {
                spacing: 6

                // ---- Hardware video decoding (applies after a restart) ----

                Label {
                    text: "Hardware video decoding"
                    font.bold: true
                }

                RowLayout {
                    spacing: 8

                    ComboBox {
                        id: hwBox
                        objectName: "hwDecodingBox"      // found by tests/app
                        Layout.preferredWidth: 220

                        model: appSettings.hwDecodingChoices
                        textRole: "text"
                        valueRole: "value"
                        enabled: !appSettings.hwDecodingExternal

                        Component.onCompleted: currentIndex = indexOfValue(appSettings.hwDecoding)
                        onActivated: appSettings.hwDecoding = currentValue
                    }

                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        visible: appSettings.hwDecodingExternal
                                 || appSettings.hwDecoding !== appSettings.hwDecodingActive
                        text: appSettings.hwDecodingExternal
                              ? "Set by QT_FFMPEG_DECODING_HW_DEVICE_TYPES"
                              : "Restart MediaWall to apply"
                        color: "#e0c060"
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Each video decoded on the graphics card keeps a pool of frames in "
                          + "video memory (roughly 60–100 MB at 1080p, several hundred at 4K). "
                          + "Off decodes on the CPU instead: far less video memory, more CPU. "
                          + "When the card runs out, FFmpeg falls back to the CPU for that video "
                          + "by itself."
                    color: "#999999"
                    font.pixelSize: 12
                }

                // ---- Largest still image size ----

                Label {
                    Layout.topMargin: 12
                    text: "Largest still image size"
                    font.bold: true
                }

                ComboBox {
                    id: maxImageSizeBox
                    objectName: "maxImageSizeBox"        // found by tests/app
                    Layout.preferredWidth: 220

                    model: appSettings.maxImageSizeChoices
                    textRole: "text"
                    valueRole: "value"

                    function showSetting() { currentIndex = indexOfValue(appSettings.maxImageSize) }
                    Component.onCompleted: showSetting()
                    onActivated: appSettings.maxImageSize = currentValue

                    Connections {
                        target: appSettings
                        function onMaxImageSizeChanged() { maxImageSizeBox.showSetting() }
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Photos are loaded no bigger than this (applies at once). A 24-megapixel "
                          + "photo takes about 128 MB of video memory at full size, 15 MB at "
                          + "2048 px. Zoomed far in, a smaller limit looks softer. GIFs and "
                          + "videos aren't affected."
                    color: "#999999"
                    font.pixelSize: 12
                }

                Button {
                    objectName: "openMemoryButton"       // found by tests/app
                    Layout.topMargin: 12
                    action: dialog.actions ? dialog.actions.memory : null
                    text: "Open Media Memory…"
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Every loaded image and video with the video memory it's estimated to "
                          + "use, biggest first, and the graphics card's actual usage where "
                          + "nvidia-smi is available."
                    color: "#999999"
                    font.pixelSize: 12
                }
            }

            // =============================================
            // Speech
            // =============================================

            ColumnLayout {
                spacing: 6

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Speech turns typed words into a voice clip with Piper, a free "
                          + "text-to-speech program. Install Piper and download voices "
                          + "yourself (a voice is a .onnx file with its .onnx.json); "
                          + "MediaWall doesn't include them. Clips are made when they're "
                          + "needed and deleted when MediaWall closes; a project keeps "
                          + "only the words and settings."
                    color: "#bbbbbb"
                    font.pixelSize: 12
                }

                // One path: a field (saved when edited) and Browse….
                component PathRow: RowLayout {
                    id: pathRow
                    property string value
                    property string placeholder
                    signal edited(string text)
                    signal browse()
                    spacing: 8
                    Layout.fillWidth: true

                    TextField {
                        Layout.fillWidth: true
                        text: pathRow.value
                        placeholderText: pathRow.placeholder
                        selectByMouse: true
                        onEditingFinished: pathRow.edited(text)
                    }
                    Button {
                        text: "Browse…"
                        onClicked: pathRow.browse()
                    }
                }

                Label {
                    Layout.topMargin: 8
                    text: "Piper program"
                    font.bold: true
                }

                PathRow {
                    value: appSettings.piperPath
                    placeholder: Qt.platform.os === "windows" ? "e.g. C:\piper\piper.exe"
                                                               : "e.g. ~/venv/bin/piper"
                    onEdited: function(text) { appSettings.piperPath = text }
                    onBrowse: piperDialog.open()
                }

                Label {
                    Layout.topMargin: 8
                    text: "Voices folder"
                    font.bold: true
                }

                PathRow {
                    value: appSettings.voicesFolder
                    placeholder: "The folder holding your downloaded voices"
                    onEdited: function(text) { appSettings.voicesFolder = text }
                    onBrowse: voicesDialog.open()
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    objectName: "speechSetupStatus"     // found by tests/app
                    text: speechEngine.problem !== "" ? speechEngine.problem
                          : speechEngine.voices.length + (speechEngine.voices.length === 1
                                                          ? " voice found." : " voices found.")
                    color: speechEngine.problem !== "" ? "#e0a84c" : "#88cc88"
                    font.pixelSize: 12
                }

                FileDialog {
                    id: piperDialog
                    title: "Choose the Piper Program"
                    onAccepted: appSettings.piperPath = appSettings.localPath(selectedFile)
                }
                FolderDialog {
                    id: voicesDialog
                    title: "Choose the Voices Folder"
                    onAccepted: appSettings.voicesFolder = appSettings.localPath(selectedFolder)
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
                    r.push(["View", "Leave Present", dialog.keys("Esc")])
                    r.push(["View", "Leave Full Screen",
                            dialog.keys("Esc") + ",  double-click the canvas"])
                    r.push(["Animated images", "Start the animation over (also unfreezes it)",
                            "Double-click it (in a container too)"])
                    r.push(["Adjust mode (a container)", "Finish adjusting",
                            dialog.keys("Return") + ",  " + dialog.keys("Space") + ",  "
                            + dialog.keys("Esc")])
                    r.push(["Containers", "Turn the picture, not the container",
                            "Hold Ctrl while dragging the rotate knob"])
                    r.push(["Dragging media", "Place on top instead of into a container",
                            "Hold Shift while dragging"])
                    r.push(["Moving and resizing", "Place freely, without snapping",
                            "Hold Ctrl while dragging or resizing"])
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
                    text: "Arrange images, GIFs, video, audio, and text freely on a canvas."
                    color: "#999999"
                }

                // Highlights of this version (update with core/version.py).
                Label {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    wrapMode: Text.WordWrap
                    textFormat: Text.StyledText
                    color: "#999999"
                    text: "<b>New in 0.9.11</b><br>"
                          + "• Speech: type words and hear them in a Piper voice, as a track in the Playback tab<br>"
                          + "• Speech: voices, modes, speed, and pitch; set up Piper in Settings > Speech<br>"
                          + "• Browsing containers: Continue Play replaces Loop (off = the video loops)<br>"
                          + "• Wall Features tabs: Layers, Playback, Speech, Text"
                }

                // The Log window: everything the app would print to a
                // terminal (FFmpeg, Qt, Python), in its own larger window.
                Button {
                    objectName: "openLogButton"        // found by tests/app
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 6
                    action: dialog.actions ? dialog.actions.log : null
                    text: "Open Log…"
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
