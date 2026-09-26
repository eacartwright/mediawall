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
    property real speed: 1.0
    property bool preservePitch: false  // off: pitch follows speed

    // A-B loop in milliseconds (-1 = not set); active when both are set.
    property real loopA: -1
    property real loopB: -1
    readonly property bool abLooping: loopA >= 0 && loopB > loopA

    property string name: ""
    property string path: ""

    // Show the red "Missing / Can't display" box inside this view.
    property bool showErrorState: true

    // url, type, and animatable often change together but through
    // separate bindings (e.g. the browser moving to the next file), so
    // they update one at a time. Apply them as one change on the next
    // event-loop turn, so the loader never builds a video player for an
    // image's url, or an Image for a video's.
    property string _url: ""
    property string _type: "image"
    property bool _animatable: false

    function _applySource() {
        // Switching kinds (e.g. image -> video): unload the old item
        // first, so it never sees the new url before it is replaced.
        if (type !== _type || animatable !== _animatable)
            _url = ""

        _type = type
        _animatable = animatable
        _url = url
    }

    onUrlChanged: Qt.callLater(_applySource)
    onTypeChanged: Qt.callLater(_applySource)
    onAnimatableChanged: Qt.callLater(_applySource)
    Component.onCompleted: _applySource()

    readonly property bool isPlayer: _type === "video" || _type === "audio"
    readonly property bool isVideo: _type === "video"

    // The QtMultimedia player, for videos and audio (null otherwise).
    // While the loader is switching components, loader.item can briefly
    // be the previous Image, which has no player: normalize to null.
    readonly property var player:
        isPlayer && loader.item && loader.item.player ? loader.item.player : null

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

    // Emitted when a player has loaded its media (a good moment to seek).
    signal mediaLoaded()


    Loader {
        id: loader

        anchors.fill: parent

        // Don't try to load a file we already know is missing.
        active: !view.missing && view._url !== ""

        sourceComponent: view.isPlayer ? playerComponent
                         : view._animatable ? animatedComponent
                         : stillComponent
    }

    Component {
        id: stillComponent

        Image {
            source: view._url

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
            source: view._url

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

                source: view._url

                // Audio (including a video used only for its sound) gets
                // no video output, so its picture is never decoded.
                videoOutput: view._type === "audio" ? null : videoOutput
                audioOutput: AudioOutput {
                    muted: view.muted
                    volume: view.volume
                }

                loops: view.loop ? MediaPlayer.Infinite : 1

                playbackRate: view.speed
                pitchCompensation: view.preservePitch

                onErrorOccurred: playerItem.failed = true

                onMediaStatusChanged: {
                    if (mediaPlayer.mediaStatus === MediaPlayer.LoadedMedia)
                        view.mediaLoaded()
                }

                // A-B loop: jump back to A on reaching B (or if playback
                // has got past it, e.g. B was just moved earlier). The
                // seek is deferred: seeking from inside positionChanged
                // is ignored by the FFmpeg backend.
                property bool abJumpPending: false

                onPositionChanged: {
                    if (!view.abLooping || abJumpPending || mediaPlayer.position < view.loopB)
                        return
                    abJumpPending = true
                    Qt.callLater(function() {
                        mediaPlayer.setPosition(view.loopA)
                        mediaPlayer.abJumpPending = false
                    })
                }

                // A new source resets the player to StoppedState, which
                // would drop the play() requested for the previous one.
                onSourceChanged: {
                    playerItem.failed = false
                    playerItem.sync()
                }
            }

            VideoOutput {
                id: videoOutput

                anchors.fill: parent

                fillMode: VideoOutput.PreserveAspectFit

                // sourceRect is the frame size as stored; phone videos are
                // often stored sideways with a rotation flag, which the
                // player applies when drawing. contentRect is what's
                // actually drawn, so report the stored size in the drawn
                // orientation (portrait videos come out portrait).
                function reportSize() {
                    var w = sourceRect.width
                    var h = sourceRect.height
                    if (w <= 0 || h <= 0 || contentRect.width <= 0 || contentRect.height <= 0)
                        return
                    if ((contentRect.width > contentRect.height) !== (w > h)) {
                        var t = w
                        w = h
                        h = t
                    }
                    view.ready(w, h)
                }

                // Report once the drawn shape has settled: right after
                // loading, contentRect can briefly show the stored
                // (sideways) shape before the rotation is applied.
                Timer {
                    id: reportTimer
                    interval: 150
                    onTriggered: videoOutput.reportSize()
                }

                onSourceRectChanged: reportTimer.restart()
                onContentRectChanged: reportTimer.restart()
            }

            // Audio files have nothing to show; say what's playing.
            Rectangle {
                anchors.fill: parent

                visible: view._type === "audio"

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
