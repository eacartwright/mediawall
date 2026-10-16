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

    // Looks to start from. Each sets every color, outline, depth, and
    // shadow value; the font, bold/italic, and stretch stay as they are.
    readonly property var presets: [
        { name: "Classic", style: { fill: "#ffffff", fill2: "", outline: "#000000", outline_width: 4,
                                    depth: 0, depth_color: "#404040", shadow: true } },
        { name: "Sunset", style: { fill: "#ffd040", fill2: "#ff4020", outline: "#401000", outline_width: 3,
                                   depth: 10, depth_color: "#802000", shadow: true } },
        { name: "Ocean", style: { fill: "#70e8ff", fill2: "#2050d0", outline: "#ffffff", outline_width: 3,
                                  depth: 0, depth_color: "#102860", shadow: true } },
        { name: "Candy", style: { fill: "#40c0ff", fill2: "#c040ff", outline: "#ffffff", outline_width: 2,
                                  depth: 6, depth_color: "#502070", shadow: false } },
        { name: "Chrome", style: { fill: "#ffffff", fill2: "#707070", outline: "#202020", outline_width: 3,
                                   depth: 14, depth_color: "#303030", shadow: false } },
        { name: "Gold", style: { fill: "#fff0a0", fill2: "#c08000", outline: "#604000", outline_width: 2,
                                 depth: 6, depth_color: "#604000", shadow: true } },
        { name: "Neon", style: { fill: "#ff60d0", fill2: "", outline: "#ffffff", outline_width: 2,
                                 depth: 0, depth_color: "#404040", shadow: true } },
        { name: "Plain", style: { fill: "#ffffff", fill2: "", outline: "#000000", outline_width: 0,
                                  depth: 0, depth_color: "#404040", shadow: false } },
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

    ColumnLayout {
        width: panel.availableWidth
        spacing: 6

        Button {
            Layout.fillWidth: true
            Layout.margins: 6
            Layout.bottomMargin: 0
            action: panel.actions.addText
            objectName: "addTextButton"
        }

        Text {
            Layout.fillWidth: true
            Layout.margins: 10
            visible: panel.target === null
            text: "Select a text object to change its words and style "
                  + "(or double-click it). Right-click the canvas to add text where you click."
            color: "#888888"
            font.pixelSize: 12
            wrapMode: Text.WordWrap
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
                                                 { stretch: false })
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

            ComboBox {
                id: fontBox
                Layout.fillWidth: true
                // "" (first) is the app's own font.
                model: [""].concat(Qt.fontFamilies())
                displayText: currentIndex <= 0 ? "Default" : currentText
                currentIndex: Math.max(0, model.indexOf(panel.style.font || ""))
                delegate: ItemDelegate {
                    required property string modelData
                    required property int index
                    width: ListView.view.width
                    text: index === 0 ? "Default" : modelData
                    highlighted: fontBox.highlightedIndex === index
                }
                onActivated: function(index) { panel.set({ font: index === 0 ? "" : model[index] }) }
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

            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                CheckBox {
                    text: "Shadow"
                    checked: panel.style.shadow === true
                    onToggled: {
                        panel.set({ shadow: checked })
                        checked = Qt.binding(function() { return panel.style.shadow === true })
                    }
                }

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
        }

        Item { Layout.preferredHeight: 6 }
    }
}
