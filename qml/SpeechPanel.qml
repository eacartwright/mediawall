import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

// The Speech tab of the Wall Features panel (Sidebar.qml): type words,
// choose a voice and how it sounds, listen (Preview), and add it as a
// speech track (Add to Playback; readme section 14.6). The track keeps
// only the words and settings (its clip is made when needed, for the
// session), so Edit… on its Playback card brings them back here to
// change (Update Track).
// Piper does the speaking (bridge/speech.py); its paths are in Settings.
// What's in the tab is saved with the project (sceneModel.speechDraft,
// a moment after each change) and comes back when it's opened.

ScrollView {
    id: panel

    // The scene item (Main.qml), for the master volume.
    property Item sceneItem

    // Shared commands (AppActions.qml), for opening Settings.
    property var actions

    // The speech track being edited, or "".
    property string editingId: ""
    // Its voice, when that voice isn't in the voices folder.
    property string missingVoice: ""

    contentWidth: availableWidth

    // The words and settings as they are now (a speech dict).
    function current() {
        return {
            text: textArea.text,
            voice: voiceBox.currentText,
            mode: modeBox.currentText,
            speed: speedSlider.value,
            pitch: pitchSlider.value,
            silence: silenceBox.value / 10,
        }
    }

    // Put a speech dict in the fields ({} clears them).
    function show(s) {
        textArea.text = s.text || ""
        var v = s.voice ? voiceBox.find(s.voice) : -1
        missingVoice = s.voice && v < 0 ? s.voice : ""
        if (v >= 0)
            voiceBox.currentIndex = v
        modeBox.currentIndex = Math.max(0, modeBox.find(s.mode || "Normal"))
        speedSlider.value = s.speed || 1
        pitchSlider.value = s.pitch || 1
        silenceBox.value = Math.round((s.silence === undefined ? 0.5 : s.silence) * 10)
    }

    // Edit a speech track (its Playback card's Edit…).
    function edit(trackId) {
        var s = sceneModel.trackSpeech(trackId)
        if (!s.text)
            return
        editingId = trackId
        show(s)
        textArea.forceActiveFocus()
    }

    // Save what's in the tab with the project, a moment after a change
    // (one step for a run of typing).
    function changed() {
        if (!restoring)
            saveTimer.restart()
    }

    property bool restoring: false

    Timer {
        id: saveTimer
        interval: 400
        onTriggered: sceneModel.setSpeechDraft(panel.current())
    }

    // A project was opened (or New): show what was in its Speech tab.
    function restore() {
        saveTimer.stop()
        restoring = true
        editingId = ""
        show(sceneModel.speechDraft)
        restoring = false
    }

    Component.onCompleted: restore()

    // The editing track was removed (or undone away).
    Connections {
        target: sceneModel
        function onSpeechDraftChanged() { panel.restore() }
        function onLayersChanged() {
            if (panel.editingId !== "" && !sceneModel.trackSpeech(panel.editingId).text)
                panel.editingId = ""
        }
    }

    // Listening to a clip (Preview).
    readonly property bool previewing: previewPlayer.playbackState === MediaPlayer.PlayingState

    MediaPlayer {
        id: previewPlayer
        objectName: "speechPreviewPlayer"
        audioOutput: AudioOutput {
            volume: panel.sceneItem ? panel.sceneItem.masterVolume : 1
        }
    }

    Connections {
        target: speechEngine
        function onPreviewReady(url) {
            previewPlayer.source = url
            previewPlayer.play()
        }
        function onPreviewStopped() { previewPlayer.stop() }
    }

    component Caption: Text {
        color: "#cccccc"
        font.pixelSize: 11
    }

    // A slider with its value (×) beside it; double-click the value for 1×.
    component Setting: RowLayout {
        id: setting
        property string label
        property alias slider: theSlider
        signal edited()
        Layout.fillWidth: true
        spacing: 6

        Caption { text: setting.label; Layout.preferredWidth: 48 }

        Slider {
            id: theSlider
            Layout.fillWidth: true
            stepSize: 0.05
            value: 1
            onMoved: setting.edited()
        }

        Text {
            Layout.preferredWidth: 38
            text: theSlider.value.toFixed(2) + "×"
            color: Math.abs(theSlider.value - 1) < 0.001 ? "#cccccc" : "#e0c060"
            font.pixelSize: 11
            horizontalAlignment: Text.AlignRight
            MouseArea {
                anchors.fill: parent
                onDoubleClicked: {
                    theSlider.value = 1
                    setting.edited()
                }
            }
        }
    }

    ColumnLayout {
        width: panel.availableWidth
        spacing: 6

        // ---- Not set up yet ----
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 10
            spacing: 8
            visible: !speechEngine.ready

            Text {
                Layout.fillWidth: true
                objectName: "speechProblem"         // found by tests/app
                text: speechEngine.problem + "\n\nSpeech uses Piper, a free text-to-speech "
                      + "program, with voices you download."
                color: "#888888"
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }

            Button {
                text: "Open Settings…"
                onClicked: panel.actions.settingsDialog.openSpeech()
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 6
            spacing: 6
            visible: speechEngine.ready

            // ---- Editing a track ----
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: editRow.implicitHeight + 8
                visible: panel.editingId !== ""
                radius: 3
                color: "#2f4a66"

                RowLayout {
                    id: editRow
                    anchors.fill: parent
                    anchors.margins: 4
                    anchors.leftMargin: 8

                    Text {
                        Layout.fillWidth: true
                        text: "Editing a speech track"
                        color: "#eeeeee"
                        font.pixelSize: 12
                    }
                    Button {
                        Layout.preferredHeight: 22
                        text: "New Clip"
                        onClicked: panel.editingId = ""
                        ToolTip.visible: hovered
                        ToolTip.text: "Stop editing the track (Add to Playback makes a new one)"
                        ToolTip.delay: 500
                    }
                }
            }

            // ---- Words ----
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 120

                TextArea {
                    id: textArea
                    objectName: "speechText"
                    placeholderText: "Type what to say"
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    onTextChanged: panel.changed()
                }
            }

            // ---- Voice ----
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "Voice"; Layout.preferredWidth: 48 }

                ComboBox {
                    id: voiceBox
                    objectName: "speechVoice"
                    Layout.fillWidth: true
                    model: speechEngine.voices
                    onActivated: {
                        panel.missingVoice = ""
                        panel.changed()
                    }
                }

                Button {
                    Layout.preferredWidth: 30
                    text: "↻"
                    onClicked: speechEngine.rescan()
                    ToolTip.visible: hovered
                    ToolTip.text: "Look for new voices in the voices folder"
                    ToolTip.delay: 500
                }
            }

            Text {
                Layout.fillWidth: true
                visible: panel.missingVoice !== ""
                text: "This track's voice (" + panel.missingVoice + ") isn't in the voices "
                      + "folder; the one shown will be used."
                color: "#e0a84c"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "Mode"; Layout.preferredWidth: 48 }

                ComboBox {
                    id: modeBox
                    objectName: "speechMode"
                    Layout.fillWidth: true
                    model: speechEngine.modes
                    onActivated: panel.changed()
                }
            }

            Setting {
                id: speedSetting
                label: "Speed"
                onEdited: panel.changed()
                slider.from: speechEngine.speedRange[0]
                slider.to: speechEngine.speedRange[1]
            }

            Setting {
                id: pitchSetting
                label: "Pitch"
                onEdited: panel.changed()
                slider.from: speechEngine.pitchRange[0]
                slider.to: speechEngine.pitchRange[1]
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Caption { text: "Pause between sentences" }

                Item { Layout.fillWidth: true }

                // Tenths of a second.
                SpinBox {
                    id: silenceBox
                    Layout.preferredWidth: 84
                    from: Math.round(speechEngine.silenceRange[0] * 10)
                    to: Math.round(speechEngine.silenceRange[1] * 10)
                    value: 5
                    editable: true
                    onValueModified: panel.changed()
                    textFromValue: function(value) { return (value / 10).toFixed(1) + " s" }
                    valueFromText: function(text) { return Math.round(parseFloat(text) * 10) }
                }
            }

            // ---- Make it ----
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                spacing: 4

                Button {
                    Layout.fillWidth: true
                    objectName: "speechPreview"
                    text: "Preview"
                    enabled: textArea.text.trim() !== ""
                    onClicked: speechEngine.preview(panel.current())
                }

                Button {
                    Layout.fillWidth: true
                    objectName: "speechStop"
                    text: "Stop"
                    enabled: speechEngine.busy || panel.previewing
                    onClicked: speechEngine.stop()
                }
            }

            Button {
                Layout.fillWidth: true
                objectName: "speechUpdate"
                visible: panel.editingId !== ""
                text: "Update Track"
                enabled: textArea.text.trim() !== ""
                onClicked: sceneModel.setTrackSpeech(panel.editingId, panel.current())
                ToolTip.visible: hovered
                ToolTip.text: "Change the track to these words and settings (undoable)"
                ToolTip.delay: 500
            }

            Button {
                Layout.fillWidth: true
                objectName: "speechAdd"
                text: panel.editingId !== "" ? "Add as a New Track" : "Add to Playback"
                enabled: textArea.text.trim() !== ""
                onClicked: sceneModel.addSpeechTrack(panel.current())
                ToolTip.visible: hovered
                ToolTip.text: "Add it as a speech track in the Playback tab"
                ToolTip.delay: 500
            }

            Text {
                Layout.fillWidth: true
                objectName: "speechStatus"
                visible: text !== ""
                text: speechEngine.status
                color: speechEngine.failed ? "#e08080" : "#aaaaaa"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
        }
    }

    // The sliders, by name (current(), edit()).
    readonly property Slider speedSlider: speedSetting.slider
    readonly property Slider pitchSlider: pitchSetting.slider
}
