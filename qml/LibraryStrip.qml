import QtQuick
import QtQuick.Controls

// The Library's Strip view (readme section 44.1): one large file above a
// single row of the others. It shares the file list and selection with the
// grid. Only the large file plays (section 44.4), and it's in a player of
// its own, gone when this view is hidden: so with the grid's, there is
// still at most one file decoding.

Rectangle {
    id: strip

    color: "#1b1b1b"

    required property var files

    signal focusReturned()
    signal dragStarted(int row)

    required property Item dragProxy

    // The current file, at once. Its thumbnail shows straight away, and the
    // real thing a moment later, so holding an arrow key through a folder
    // doesn't open every file on the way.
    property var file: ({})
    property var openFile: null
    property bool paused: false
    property bool soundOn: false         // a video's sound (kept from file to file)
    property bool fileReady: false

    readonly property var view: viewLoader.item
    readonly property bool isAudio: file.type === "audio"
    readonly property bool isStill: file.type === "image" && !file.animatable
    readonly property bool isMissing: file.missing === true

    function showCurrent() {
        openFile = null
        fileReady = false
        paused = false
        file = visible ? tagLibrary.fileAt(tagLibrary.currentRow) : {}
        if (file.path)
            openDelay.restart()
        else
            openDelay.stop()
        if (tagLibrary.currentRow >= 0)
            carousel.positionViewAtIndex(tagLibrary.currentRow, ListView.Center)
    }

    // Ctrl+Space: the first press brings up the sound, the next pause and resume.
    function togglePlay() {
        if (isStill || isMissing || !openFile)
            return
        var hasSound = file.type === "video"
        if (hasSound && !soundOn && !paused)
            soundOn = true
        else
            paused = !paused
    }

    onVisibleChanged: showCurrent()

    Connections {
        target: tagLibrary
        function onCurrentRowChanged(row) {
            if (strip.visible)
                strip.showCurrent()
        }
    }

    Timer {
        id: openDelay
        interval: 120
        onTriggered: strip.openFile = strip.file
    }

    // ---- The large file ----

    Item {
        id: stage

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: carouselPane.top
        anchors.margins: 6
        clip: true

        Image {
            anchors.fill: parent
            visible: !strip.fileReady && !strip.isAudio
            source: strip.file.thumb || ""
            asynchronous: true
            fillMode: Image.PreserveAspectFit
        }

        Loader {
            id: viewLoader
            objectName: "libraryStripView"               // found by tests/app

            anchors.fill: parent
            active: strip.openFile !== null

            sourceComponent: MediaView {
                url: strip.openFile.url
                missing: strip.openFile.missing === true
                type: strip.openFile.type
                animatable: strip.openFile.animatable
                name: strip.openFile.name
                path: strip.openFile.path
                playing: !strip.paused
                muted: type !== "audio" && !strip.soundOn
                loop: true
                memoryPlace: "library"
                onReady: strip.fileReady = true
            }
        }

        // Play, seek, and sound, for a video or audio.
        VideoControls {
            objectName: "libraryStripControls"           // found by tests/app

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 8
            controlsFocusPolicy: Qt.NoFocus

            visible: strip.view !== null && strip.view.isPlayer
            view: strip.view
            playing: !strip.paused
            muted: !strip.isAudio && !strip.soundOn
            onTogglePlay: strip.paused = !strip.paused
            onToggleMute: if (!strip.isAudio) strip.soundOn = !strip.soundOn
        }

        Text {
            anchors.centerIn: parent
            visible: strip.file.path === undefined
            color: "#888888"
            text: tagLibrary.scanning ? "Scanning…"
                  : tagLibrary.findMode ? "No files match"
                  : "No media in this folder"
        }
    }

    // ---- The row of files ----

    Rectangle {
        id: carouselPane

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 124
        color: "#242424"

        ListView {
            id: carousel
            objectName: "libraryCarousel"                // found by tests/app

            anchors.fill: parent
            anchors.margins: 4
            orientation: ListView.Horizontal
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            reuseItems: true
            cacheBuffer: 300
            spacing: 3

            model: strip.files

            delegate: Rectangle {
                id: cell

                required property int index
                required property string name
                required property string mediaType
                required property string thumb
                required property bool failed
                required property bool selected
                required property bool current
                required property bool tagged
                required property bool missing

                width: 130
                height: ListView.view.height
                radius: 3
                color: cell.selected ? "#2f4a66" : "#2a2a2a"
                border.width: cell.current ? 2 : cell.selected ? 1 : 0
                border.color: "#6aa6e8"

                Image {
                    anchors.fill: parent
                    anchors.margins: 4
                    anchors.bottomMargin: 18
                    source: cell.thumb
                    asynchronous: true
                    fillMode: Image.PreserveAspectFit
                }

                Text {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -7
                    readonly property bool sayingWhy: cell.missing || cell.failed
                    visible: cell.mediaType === "audio" || sayingWhy
                    text: cell.missing ? "Missing file" : cell.failed ? "Can't display" : "♪"
                    color: cell.missing ? "#e07070" : cell.failed ? "#888888" : "#9fb4d8"
                    font.pixelSize: sayingWhy ? 11 : 28
                }

                Text {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 3
                    text: cell.name
                    color: "#dddddd"
                    font.pixelSize: 10
                    elide: Text.ElideMiddle
                    horizontalAlignment: Text.AlignHCenter
                }

                Rectangle {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 5
                    width: 10
                    height: 10
                    radius: 5
                    visible: cell.tagged
                    color: "#4caf50"
                    border.color: "#1b1b1b"
                }

                MouseArea {
                    anchors.fill: parent
                    preventStealing: true        // a drag here is a file drag, not a scroll
                    drag.target: cell.missing ? null : strip.dragProxy
                    drag.threshold: 12
                    drag.onActiveChanged: {
                        if (drag.active)
                            strip.dragStarted(cell.index)
                    }
                    onClicked: function(mouse) {
                        strip.focusReturned()
                        tagLibrary.clickFile(cell.index,
                                             (mouse.modifiers & Qt.ControlModifier) !== 0,
                                             (mouse.modifiers & Qt.ShiftModifier) !== 0)
                    }
                }
            }

            ScrollBar.horizontal: ScrollBar {}
        }
    }
}
