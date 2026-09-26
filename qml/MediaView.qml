import QtQuick
import QtMultimedia

// Displays one media source: a still image, an animated GIF/WebP,
// a video, or an audio file (shown as a placeholder while it plays).
// Used by free media objects, container content, adjust-mode ghosts,
// and browser previews, so every place that shows media behaves the same.

Item {
    id: view

    property string url: ""
    property string type: "image"           // "image" | "video" | "audio"
    property bool animatable: false
    property bool missing: false

    // Playback (animated images, video, audio)
    property bool playing: true
    property bool muted: true
    property real volume: 1.0
    property bool loop: true

    property string name: ""
    property string path: ""

    // Show the red "Missing / Can't display" box inside this view.
    property bool showErrorState: true

    readonly property bool isPlayer: type === "video" || type === "audio"
    readonly property bool isVideo: type === "video"

    // The QtMultimedia player, for videos and audio (null otherwise).
    readonly property var player:
        isPlayer && loader.item ? loader.item.player : null

    // True only for images that actually have more than one frame.
    readonly property bool isAnimated:
        !isPlayer &&
        loader.item !== null &&
        loader.item.frameCount !== undefined &&
        loader.item.frameCount > 1

    // The file exists but couldn't be decoded or played.
    readonly property bool failed:
        loader.item !== null &&
        (isPlayer ? loader.item.failed === true
                  : loader.item.status === Image.Error)

    // Player position/length in milliseconds.
    readonly property real position: player ? player.position : 0
    readonly property real duration: player ? player.duration : 0
    readonly property bool ended:
        player !== null && player.mediaStatus === MediaPlayer.EndOfMedia

    function seek(ms) {
        if (player)
            player.position = ms
    }

    function replay() {
        if (player) {
            player.position = 0
            player.play()
        }
    }

    // Emitted once the media's natural size is known.
    signal ready(real naturalWidth, real naturalHeight)


    Loader {
        id: loader

        anchors.fill: parent

        // Don't try to load a file we already know is missing.
        active: !view.missing && view.url !== ""

        sourceComponent: view.isPlayer ? playerComponent
                         : view.animatable ? animatedComponent
                         : stillComponent
    }

    Component {
        id: stillComponent

        Image {
            source: view.url

            fillMode: Image.PreserveAspectFit
            autoTransform: true         // EXIF orientation

            asynchronous: true
            smooth: true
            cache: true

            onStatusChanged: {
                if (status === Image.Ready)
                    view.ready(implicitWidth, implicitHeight)
            }
        }
    }

    Component {
        id: animatedComponent

        AnimatedImage {
            source: view.url

            fillMode: Image.PreserveAspectFit
            autoTransform: true

            asynchronous: true
            smooth: true

            playing: view.playing

            onStatusChanged: {
                if (status === Image.Ready)
                    view.ready(implicitWidth, implicitHeight)
            }
        }
    }

    Component {
        id: playerComponent

        Item {
            id: playerItem

            property alias player: mediaPlayer
            property bool failed: false

            function sync() {
                if (view.playing)
                    mediaPlayer.play()
                else
                    mediaPlayer.pause()      // shows the first frame
            }

            MediaPlayer {
                id: mediaPlayer

                source: view.url

                videoOutput: videoOutput
                audioOutput: AudioOutput {
                    muted: view.muted
                    volume: view.volume
                }

                loops: view.loop ? MediaPlayer.Infinite : 1

                onErrorOccurred: playerItem.failed = true
            }

            VideoOutput {
                id: videoOutput

                anchors.fill: parent

                fillMode: VideoOutput.PreserveAspectFit

                onSourceRectChanged: {
                    if (sourceRect.width > 0 && sourceRect.height > 0)
                        view.ready(sourceRect.width, sourceRect.height)
                }
            }

            // Audio files have nothing to show; say what's playing.
            Rectangle {
                anchors.fill: parent

                visible: view.type === "audio"

                color: "#262a33"

                Column {
                    anchors.centerIn: parent
                    width: parent.width - 16
                    spacing: 4

                    Text {
                        width: parent.width
                        text: "♪"
                        color: "#9fb4d8"
                        font.pixelSize: 28
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Text {
                        width: parent.width
                        text: view.name
                        color: "#cccccc"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideMiddle
                    }
                }
            }

            Component.onCompleted: sync()

            Connections {
                target: view
                function onPlayingChanged() { playerItem.sync() }
            }
        }
    }


    // Error state (readme section 45)
    MediaErrorBox {
        anchors.fill: parent

        visible: view.showErrorState && (view.missing || view.failed)

        missing: view.missing
        name: view.name
        path: view.path
    }
}
