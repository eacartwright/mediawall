import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Play/pause, seek, time, and mute for a MediaView that plays video or audio.
// Editor UI: shown on selected objects and in browser previews.
// Canvas objects show only the seek bar and time (showButtons: false);
// their play/pause and mute are in the right-click menu.

Rectangle {
    id: bar

    // The MediaView being controlled.
    property var view

    // Current state, as the owner stores it.
    property bool playing: true
    property bool muted: true

    // Show the Play/Pause and Mute buttons.
    property bool showButtons: true

    signal togglePlay()
    signal toggleMute()

    height: 34
    radius: 4
    color: "#dd202020"

    function formatTime(ms) {
        var total = Math.floor(ms / 1000)
        var minutes = Math.floor(total / 60)
        var seconds = total % 60
        return minutes + ":" + (seconds < 10 ? "0" : "") + seconds
    }

    // Absorb clicks between the controls so they don't drag the object.
    MouseArea {
        anchors.fill: parent
        onWheel: function(wheel) { wheel.accepted = true }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 4
        anchors.rightMargin: 4

        spacing: 4

        Button {
            Layout.preferredHeight: 26

            visible: bar.showButtons

            text: bar.view && bar.view.ended ? "Replay"
                  : bar.playing ? "Pause" : "Play"

            onClicked: {
                if (bar.view && bar.view.ended) {
                    if (!bar.playing)
                        bar.togglePlay()
                    bar.view.replay()
                } else {
                    bar.togglePlay()
                }
            }
        }

        Slider {
            id: seekSlider

            Layout.fillWidth: true

            from: 0
            to: Math.max(1, bar.view ? bar.view.duration : 1)

            // Follow playback, except while the user is dragging.
            Binding on value {
                when: !seekSlider.pressed
                value: bar.view ? bar.view.position : 0
            }

            onMoved: {
                if (bar.view)
                    bar.view.seek(value)
            }

            // A-B loop markers (and the looped span, when both are set).
            function xFor(ms) {
                return leftPadding + availableWidth * Math.min(1, Math.max(0, ms / to))
            }

            readonly property real loopA: bar.view ? bar.view.loopA : -1
            readonly property real loopB: bar.view ? bar.view.loopB : -1

            Rectangle {
                visible: seekSlider.loopA >= 0 && seekSlider.loopB > seekSlider.loopA
                x: seekSlider.xFor(seekSlider.loopA)
                width: seekSlider.xFor(seekSlider.loopB) - x
                y: seekSlider.topPadding + seekSlider.availableHeight / 2 - height / 2
                height: 6
                radius: 2
                color: "#60e0a84c"
            }

            Repeater {
                model: [
                    { label: "A", ms: seekSlider.loopA },
                    { label: "B", ms: seekSlider.loopB },
                ]

                Rectangle {
                    required property var modelData

                    visible: modelData.ms >= 0 && seekSlider.to > 1
                    x: seekSlider.xFor(modelData.ms) - width / 2
                    y: 0
                    width: 2
                    height: seekSlider.height
                    color: "#e0a84c"

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: -2
                        text: parent.modelData.label
                        color: "#e0a84c"
                        font.pixelSize: 9
                        font.bold: true
                    }
                }
            }
        }

        Text {
            visible: bar.width > 280

            text: bar.view
                  ? bar.formatTime(bar.view.position) + " / "
                    + bar.formatTime(bar.view.duration)
                  : ""

            color: "#cccccc"
            font.pixelSize: 11
        }

        Button {
            Layout.preferredHeight: 26

            visible: bar.showButtons

            text: bar.muted ? "Unmute" : "Mute"

            onClicked: bar.toggleMute()
        }
    }
}
