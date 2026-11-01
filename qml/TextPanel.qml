import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// The Text tab of the Wall Features panel (Sidebar.qml): add text, and
// edit the selected text object's words and style (readme section 5.4).
// Every change goes to the model (undoable); a slider drag or a run of
// typing is one undo step.

ScrollView {
    id: panel

    // The scene item (Main.qml), for finding the selected object's item.
    property Item sceneItem

    // Shared commands (AppActions.qml).
    property var actions

    contentWidth: availableWidth
    // The scroll bar is drawn over the content: keep it clear when shown.
    rightPadding: ScrollBar.vertical.visible ? ScrollBar.vertical.width : 0

    // The selected text object's canvas item, or null. (layers changes
    // with every change, so this never holds on to a replaced item.)
    readonly property Item target: {
        sceneModel.layers
        var item = sceneItem ? sceneItem.itemFor(sceneModel.selectedId) : null
        return item && item.isText === true ? item : null
    }
    readonly property string targetId: target ? target.objectId : ""
    readonly property var style: target ? target.textStyle : ({})

    function set(changes) {
        if (targetId !== "")
            sceneModel.setTextStyle(targetId, changes)
    }

    // Put the cursor in the words field, all selected (a new or
    // double-clicked text object).
    function focusText() {
        textField.forceActiveFocus()
        textField.selectAll()
    }

    // Looks to start from. Each sets every color, outline, and depth
    // value; the font, bold/italic, and stretch stay as they are.
    readonly property var presets: [
        { name: "Classic", style: { fill: "#ffffff", fill2: "", outline: "#000000", outline_width: 4,
                                    depth: 0, depth_color: "#404040" } },
        { name: "Sunset", style: { fill: "#ffd040", fill2: "#ff4020", outline: "#401000", outline_width: 3,
                                   depth: 10, depth_color: "#802000" } },
        { name: "Ocean", style: { fill: "#70e8ff", fill2: "#2050d0", outline: "#ffffff", outline_width: 3,
                                  depth: 0, depth_color: "#102860" } },
        { name: "Candy", style: { fill: "#40c0ff", fill2: "#c040ff", outline: "#ffffff", outline_width: 2,
                                  depth: 6, depth_color: "#502070" } },
        { name: "Chrome", style: { fill: "#ffffff", fill2: "#707070", outline: "#202020", outline_width: 3,
                                   depth: 14, depth_color: "#303030" } },
        { name: "Gold", style: { fill: "#fff0a0", fill2: "#c08000", outline: "#604000", outline_width: 2,
                                 depth: 6, depth_color: "#604000" } },
        { name: "Neon", style: { fill: "#ff60d0", fill2: "", outline: "#ffffff", outline_width: 2,
                                 depth: 0, depth_color: "#404040" } },
        { name: "Plain", style: { fill: "#ffffff", fill2: "", outline: "#000000", outline_width: 0,
                                  depth: 0, depth_color: "#404040" } },
    ]

    // One color dialog, for whichever color is being chosen.
    ColorDialog {
        id: colorDialog
        property string key: ""
        title: "Choose a Color"
        onAccepted: panel.set({ [key]: selectedColor.toString() })
    }

    function chooseColor(key, current) {
        colorDialog.key = key
        colorDialog.selectedColor = current
        colorDialog.open()
    }

    // A color square; click to choose.
    component Swatch: Rectangle {
        id: swatch
        property string key
        property color current: "#ffffff"
        implicitWidth: 28
        implicitHeight: 20
        radius: 3
        color: current
        border.color: swatchArea.containsMouse ? "#ffffff" : "#888888"
        MouseArea {
            id: swatchArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: panel.chooseColor(swatch.key, swatch.current)
        }
    }

    component Caption: Text {
        color: "#cccccc"
        font.pixelSize: 11
    }

    // Every text object, top first (from the Layers list).
    readonly property var texts:
        sceneModel.layers.filter(function(layer) { return layer.type === "text" })

    ColumnLayout {
        width: panel.availableWidth
        spacing: 6

        // Only until there is a text: then the toolbar's Add Text (or
        // the canvas's right-click menu) adds more.
        Button {
            Layout.fillWidth: true
            Layout.margins: 6
            Layout.bottomMargin: 0
            visible: panel.texts.length === 0
            action: panel.actions.addText
            objectName: "addTextButton"
        }

        // ---- The text objects, one a line: click to select. Lock makes
        // one ignore the mouse, so what's behind it can be clicked; it's
        // unlocked here. ----
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 6
            Layout.bottomMargin: 0
            spacing: 2
            visible: panel.texts.length > 0

            Repeater {
                model: panel.texts

                Rectangle {
                    id: textRow
                    required property var modelData
                    readonly property bool isSelected: modelData.id === sceneModel.selectedId
                    readonly property string words: modelData.text.trim()

                    Layout.fillWidth: true
                    Layout.preferredHeight: 26
                    radius: 3
                    color: isSelected ? "#3d7fc4" : rowArea.containsMouse ? "#333333" : "transparent"

                    MouseArea {
                        id: rowArea
                        objectName: "textRow:" + textRow.modelData.id     // found by tests/app
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: sceneModel.select(textRow.modelData.id)
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 6
                        spacing: 4

                        Text {
                            Layout.fillWidth: true
                            text: textRow.words || "(empty text)"
                            color: textRow.words ? "#eeeeee" : "#999999"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }

                        CheckBox {
                            objectName: "textLock:" + textRow.modelData.id    // found by tests/app
                            text: "Lock"
                            checked: textRow.modelData.locked
                            onToggled: {
                                sceneModel.setLocked(textRow.modelData.id, checked)
                                checked = Qt.binding(function() { return textRow.modelData.locked })
                            }
                            ToolTip.visible: hovered
                            ToolTip.text: "Locked text ignores the mouse, so what's behind it "
                                          + "can be clicked. Its words and style still change here."
                            ToolTip.delay: 600
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.margins: 10
            visible: panel.target === null
            text: panel.texts.length === 0
                  ? "Add text with the button above, or right-click the canvas to add it where you click."
                  : "Choose a text above (or click or double-click one on the canvas) "
                    + "to change its words and style."
            color: "#888888"
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }

        Caption {
            Layout.fillWidth: true
            Layout.leftMargin: 6
            Layout.rightMargin: 6
            visible: panel.target !== null && panel.target.locked
            wrapMode: Text.WordWrap
            text: "Locked: the mouse goes through it on the canvas. Untick Lock to move it."
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 6
            spacing: 6
            visible: panel.target !== null

            // ---- Words ----
            TextField {
                id: textField
                objectName: "textField"
                Layout.fillWidth: true
                placeholderText: "Type the text"
                text: panel.target ? panel.target.objText : ""
                onTextEdited: sceneModel.setText(panel.targetId, text)

                // The wheel moves the cursor along a line too long for the
                // field (3 letters a notch), so any spot is easy to reach.
                // When the words fit, the wheel scrolls the panel.
                MouseArea {
                    objectName: "textFieldWheel"        // found by tests/app
                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton        // clicks go to the field
                    cursorShape: Qt.IBeamCursor
                    property real rest: 0               // part of a step (touchpads)
                    onWheel: (wheel) => {
                        var field = textField
                        if (field.contentWidth <= field.width - field.leftPadding - field.rightPadding) {
                            wheel.accepted = false
                            return
                        }
                        var delta = wheel.angleDelta.y !== 0 ? -wheel.angleDelta.y : wheel.angleDelta.x
                        rest += delta / 40
                        var steps = rest < 0 ? Math.ceil(rest) : Math.floor(rest)
                        rest -= steps
                        if (steps === 0)
                            return
                        field.forceActiveFocus()
                        field.cursorPosition = Math.max(0, Math.min(field.length, field.cursorPosition + steps))
                    }
                }
            }

            // ---- Presets ----
            Caption { text: "Style" }

            GridLayout {
                Layout.fillWidth: true
                columns: 4
                rowSpacing: 4
                columnSpacing: 4

                Repeater {
                    model: panel.presets

                    Rectangle {
                        id: presetButton
                        required property var modelData
                        objectName: "preset" + modelData.name      // found by tests/app

                        Layout.fillWidth: true
                        Layout.preferredHeight: 40
                        radius: 3
                        color: presetArea.containsMouse ? "#3a3a3a" : "#1c1c1c"
                        border.color: "#555555"

                        TextArt {
                            anchors.fill: parent
                            anchors.margins: 5
                            text: "Aa"
                            style: Object.assign({}, panel.style, presetButton.modelData.style,
                                                 { stretch: false, wrap: false, arc: 0, tilt: 0 })
                        }

                        MouseArea {
                            id: presetArea
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: panel.set(presetButton.modelData.style)
                        }

                        ToolTip.visible: presetArea.containsMouse
                        ToolTip.text: presetButton.modelData.name
                        ToolTip.delay: 500
                    }
                }
            }

            // ---- Font ----
            Caption { text: "Font" }

            FontPicker {
                objectName: "fontPicker"
                Layout.fillWidth: true
                family: panel.style.font || ""
                onPicked: function(name) { panel.set({ font: name }) }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                CheckBox {
                    text: "Bold"
                    checked: panel.style.bold === true
                    onToggled: {
                        panel.set({ bold: checked })
                        checked = Qt.binding(function() { return panel.style.bold === true })
                    }
                }

                CheckBox {
                    text: "Italic"
                    checked: panel.style.italic === true
                    onToggled: {
                        panel.set({ italic: checked })
                        checked = Qt.binding(function() { return panel.style.italic === true })
                    }
                }
            }

            // ---- Size: the letters' height on the canvas ----
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "Size"; Layout.preferredWidth: 48 }

                Slider {
                    objectName: "sizeSlider"
                    Layout.fillWidth: true
                    from: 8
                    to: 400
                    stepSize: 1
                    value: panel.target ? panel.target.letterSize : 60
                    onMoved: panel.target.setLetterSize(value)
                }

                SpinBox {
                    objectName: "sizeBox"
                    Layout.preferredWidth: 84
                    from: 4
                    to: 2000
                    editable: true
                    value: panel.target ? Math.round(panel.target.letterSize) : 60
                    onValueModified: panel.target.setLetterSize(value)
                }
            }

            // ---- Fill ----
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "Fill"; Layout.preferredWidth: 48 }
                Swatch { key: "fill"; current: panel.style.fill || "#ffffff" }

                CheckBox {
                    id: gradientBox
                    text: "Fade to"
                    checked: (panel.style.fill2 || "") !== ""
                    onToggled: {
                        // Turning it on starts from a darker shade of the fill.
                        panel.set({ fill2: checked ? Qt.darker(panel.style.fill || "#ffffff", 1.8).toString() : "" })
                        checked = Qt.binding(function() { return (panel.style.fill2 || "") !== "" })
                    }
                }

                Swatch {
                    key: "fill2"
                    visible: gradientBox.checked
                    current: panel.style.fill2 || "#ffffff"
                }

                Item { Layout.fillWidth: true }
            }

            // ---- Outline ----
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "Outline"; Layout.preferredWidth: 48 }
                Swatch { key: "outline"; current: panel.style.outline || "#000000" }

                Slider {
                    objectName: "outlineSlider"
                    Layout.fillWidth: true
                    from: 0
                    to: 20
                    stepSize: 0.5
                    value: panel.style.outline_width || 0
                    onMoved: panel.set({ outline_width: value })
                }
            }

            // ---- 3D depth ----
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "3D depth"; Layout.preferredWidth: 48 }
                Swatch { key: "depth_color"; current: panel.style.depth_color || "#404040" }

                Slider {
                    objectName: "depthSlider"
                    Layout.fillWidth: true
                    from: 0
                    to: 40
                    stepSize: 1
                    value: panel.style.depth || 0
                    onMoved: panel.set({ depth: Math.round(value) })
                }
            }

            // ---- Glow ----
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "Glow"; Layout.preferredWidth: 48 }
                Swatch { key: "glow_color"; current: panel.style.glow_color || "#40c0ff" }

                Slider {
                    objectName: "glowSlider"
                    Layout.fillWidth: true
                    from: 0
                    to: 40
                    stepSize: 1
                    value: panel.style.glow || 0
                    onMoved: panel.set({ glow: value })
                }
            }

            // ---- Shape: arc and tilt (0 in the middle) ----
            component CenteredSlider: RowLayout {
                id: centered
                property string caption
                property string key
                property real limit
                Layout.fillWidth: true
                spacing: 6

                Caption { text: centered.caption; Layout.preferredWidth: 48 }

                Slider {
                    id: centeredSlider
                    objectName: centered.key + "Slider"
                    Layout.fillWidth: true
                    from: -centered.limit
                    to: centered.limit
                    stepSize: 1
                    value: panel.style[centered.key] || 0
                    // Snaps to straight near the middle.
                    onMoved: panel.set({ [centered.key]: Math.abs(value) < centered.limit / 30 ? 0 : value })
                }

                Text {
                    Layout.preferredWidth: 34
                    horizontalAlignment: Text.AlignRight
                    text: Math.round(panel.style[centered.key] || 0) + "°"
                    color: "#cccccc"
                    font.pixelSize: 11
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: panel.set({ [centered.key]: 0 })
                    }
                }
            }

            CenteredSlider { caption: "Arc"; key: "arc"; limit: 360 }
            CenteredSlider { caption: "Tilt"; key: "tilt"; limit: 70 }

            // ---- Wrap ----
            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                CheckBox {
                    objectName: "wrapBox"
                    text: "Wrap to box"
                    checked: panel.style.wrap === true
                    onToggled: {
                        panel.target.setWrap(checked)
                        checked = Qt.binding(function() { return panel.style.wrap === true })
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: "Wrap the words onto lines as wide as the box; resize it to rewrap"
                    ToolTip.delay: 600
                }

                Item { Layout.fillWidth: true }

                Repeater {
                    model: [{ value: "left", text: "Left" }, { value: "center", text: "Center" },
                            { value: "right", text: "Right" }]

                    Button {
                        required property var modelData
                        visible: panel.style.wrap === true
                        text: modelData.text
                        checkable: true
                        checked: panel.style.align === modelData.value
                        // Narrower if needed, so the row fits the panel.
                        Layout.fillWidth: true
                        Layout.maximumWidth: 52
                        Layout.minimumWidth: 30
                        onClicked: {
                            panel.set({ align: modelData.value })
                            checked = Qt.binding(function() { return panel.style.align === modelData.value })
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 4
                visible: panel.style.wrap !== true

                CheckBox {
                    text: "Stretch to box"
                    checked: panel.style.stretch === true
                    onToggled: {
                        panel.set({ stretch: checked })
                        checked = Qt.binding(function() { return panel.style.stretch === true })
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: "Fill the box exactly, instead of keeping the letters' proportions"
                    ToolTip.delay: 600
                }
            }

            // ---- Animation: looping, on the canvas (TextArt) ----
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "Animate"; Layout.preferredWidth: 48 }

                ComboBox {
                    objectName: "animationBox"           // found by tests/app
                    Layout.fillWidth: true
                    textRole: "text"
                    valueRole: "value"
                    model: [{ value: "", text: "None" },
                            { value: "wiggle", text: "Wiggle" },
                            { value: "pulse", text: "Pulse" },
                            { value: "glow_pulse", text: "Glow pulse" },
                            { value: "gradient_shift", text: "Gradient shift" },
                            { value: "color_cycle", text: "Color cycle" }]
                    currentIndex: indexOfValue(panel.style.animation || "")
                    onActivated: (index) => panel.set({ animation: valueAt(index) })
                }

                ComboBox {
                    objectName: "animationSpeedBox"      // found by tests/app
                    Layout.preferredWidth: 90
                    enabled: (panel.style.animation || "") !== ""
                    textRole: "text"
                    valueRole: "value"
                    model: [{ value: "slow", text: "Slow" }, { value: "normal", text: "Normal" },
                            { value: "fast", text: "Fast" }]
                    currentIndex: indexOfValue(panel.style.animation_speed || "normal")
                    onActivated: (index) => panel.set({ animation_speed: valueAt(index) })
                }
            }

            Caption {
                Layout.fillWidth: true
                visible: panel.style.animation === "glow_pulse" && !(panel.style.glow > 0)
                wrapMode: Text.WordWrap
                text: "Glow pulse fades the glow in and out: set a Glow above to see it."
            }
        }

        Item { Layout.preferredHeight: 6 }
    }
}
