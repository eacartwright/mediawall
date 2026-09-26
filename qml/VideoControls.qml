import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Play/pause, seek, time, and mute for a MediaView that plays video or audio.
// Editor UI: shown on selected objects and in browser previews.

Rectangle {
    id: bar

    // The MediaView being controlled.
    property var view

    // Current state, as the owner stores it.
    property bool playing: true
    property bool muted: true

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

            text: bar.muted ? "Unmute" : "Mute"

            onClicked: bar.toggleMute()
        }
    }
}
