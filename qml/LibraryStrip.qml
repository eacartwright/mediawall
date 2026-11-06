import QtQuick
import QtQuick.Controls
import "Zoom.js" as Zoom

// The Library's Strip view (readme section 44.1): one large file above a
// single row of the others. It shares the file list and selection with the
// grid. Only the large file plays (section 44.4), and it's in a player of
// its own, gone when this view is hidden: so with the grid's, there is
// still at most one file decoding.
//
// By mouse: thumb buttons step through the files, anywhere in this view. Over the
// large file a click plays or pauses, the wheel zooms around the pointer, a drag
// pans, a double-click resets the zoom, and a tilt skips 10% of a video or audio
// file (of anything else, it steps). Over the row, the wheel scrolls it and a tilt
// steps.

Rectangle {
    id: strip

    color: "#1b1b1b"

    required property var files

    signal focusReturned()
    signal dragStarted(int row)
    signal fileMenuRequested()

    required property Item dragProxy

    // Before a file is deleted: Windows won't move a file that's open.
    // showCurrent() opens it again, if it stays.
    function releaseFile() {
        openDelay.stop()
        openFile = null
        fileReady = false
    }

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

    // The large file's zoom, from 1 (all of it, fitted) up. Each file starts at 1.
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    readonly property real maxZoom: 20

    function resetZoom() {
        zoom = 1
        panX = 0
        panY = 0
    }

    // Zoom by factor f around (px, py) on the stage: the point under the
    // pointer stays there (as in a browser's preview).
    function zoomAt(px, py, f) {
        var newZoom = Math.max(1, Math.min(maxZoom, zoom * f))
        if (newZoom === 1) {
            resetZoom()
            return
        }
        var k = newZoom / zoom
        var baseX = stage.width / 2
        var baseY = stage.height / 2
        panX = px + (baseX + panX - px) * k - baseX
        panY = py + (baseY + panY - py) * k - baseY
        zoom = newZoom
    }

    FileStepper {
        id: fileStepper
        step: function(delta) { tagLibrary.stepFile(delta) }
    }

    function showCurrent() {
        openFile = null
        fileReady = false
        paused = false
        resetZoom()
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

    // Thumb buttons, anywhere in this view: what lies above takes only the left.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.BackButton | Qt.ForwardButton
        onPressed: function(mouse) {
            fileStepper.begin(mouse.button === Qt.BackButton ? -1 : 1)
        }
        onReleased: fileStepper.end()
        onCanceled: fileStepper.end()
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

        // What zooms: the stage's size times the zoom, its center moved by the pan.
        Item {
            objectName: "libraryStripZoomed"             // found by tests/app

            width: stage.width * strip.zoom
            height: stage.height * strip.zoom
            x: stage.width / 2 + strip.panX - width / 2
            y: stage.height / 2 + strip.panY - height / 2

            Image {
                anchors.fill: parent
                visible: !strip.fileReady && !strip.isAudio
                source: strip.file.thumb || ""
                asynchronous: true
                fillMode: Image.PreserveAspectFit
            }

            Loader {
                id: viewLoader
                objectName: "libraryStripView"           // found by tests/app

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
        }

        MouseArea {
            objectName: "libraryStripStage"              // found by tests/app

            anchors.fill: parent

            property point startMouse
            property point startPan
            property bool moved: false

            // What the first click of a double-click did, for it to take back.
            property var pausedBeforeClick: null

            onPressed: function(mouse) {
                startMouse = Qt.point(mouse.x, mouse.y)
                startPan = Qt.point(strip.panX, strip.panY)
                moved = false
            }

            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                if (Math.abs(mouse.x - startMouse.x) + Math.abs(mouse.y - startMouse.y) >= 6)
                    moved = true
                if (moved && strip.zoom !== 1) {
                    strip.panX = startPan.x + (mouse.x - startMouse.x)
                    strip.panY = startPan.y + (mouse.y - startMouse.y)
                }
            }

            onClicked: {
                pausedBeforeClick = null
                strip.focusReturned()
                if (moved || !strip.view || !strip.view.canPause)
                    return
                pausedBeforeClick = strip.paused
                strip.paused = !strip.paused
            }

            onDoubleClicked: {
                if (pausedBeforeClick !== null) {
                    strip.paused = pausedBeforeClick
                    pausedBeforeClick = null
                }
                strip.resetZoom()
                strip.focusReturned()
            }

            // Audio has nothing to zoom: it stays as it is.
            onWheel: function(wheel) {
                if (strip.view && strip.view.skipWheel(wheel.angleDelta))
                    return
                if (fileStepper.wheel(wheel.angleDelta))
                    return
                if (wheel.angleDelta.y !== 0 && !strip.isAudio && strip.file.path !== undefined)
                    strip.zoomAt(wheel.x, wheel.y,
                                 Zoom.wheelFactor(wheel.angleDelta.y, appSettings.zoomStep))
            }
        }

        // Seek and sound, for a video or audio.
        VideoControls {
            objectName: "libraryStripControls"           // found by tests/app

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 8
            controlsFocusPolicy: Qt.NoFocus

            visible: strip.view !== null && strip.view.isPlayer
            view: strip.view
            muted: !strip.isAudio && !strip.soundOn
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
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    preventStealing: true        // a drag here is a file drag, not a scroll
                    drag.target: cell.missing ? null : strip.dragProxy
                    drag.threshold: 12
                    drag.onActiveChanged: {
                        if (drag.active)
                            strip.dragStarted(cell.index)
                    }
                    onClicked: function(mouse) {
                        // The menu acts on the selection if this is among it, else on this alone.
                        if (mouse.button === Qt.RightButton) {
                            if (!cell.selected)
                                tagLibrary.clickFile(cell.index, false, false)
                            strip.fileMenuRequested()
                            return
                        }
                        strip.focusReturned()
                        tagLibrary.clickFile(cell.index,
                                             (mouse.modifiers & Qt.ControlModifier) !== 0,
                                             (mouse.modifiers & Qt.ShiftModifier) !== 0)
                    }
                }
            }

            ScrollBar.horizontal: ScrollBar {}
        }

        // The wheel moves the row, which by itself takes only a sideways wheel;
        // a sideways one here steps through the files, even if a video is showing.
        MouseArea {
            anchors.fill: carousel
            acceptedButtons: Qt.NoButton
            onWheel: function(wheel) {
                if (fileStepper.wheel(wheel.angleDelta))
                    return
                var furthest = Math.max(carousel.originX,
                                        carousel.originX + carousel.contentWidth - carousel.width)
                // Two files to a notch.
                carousel.contentX = Math.max(carousel.originX, Math.min(furthest,
                    carousel.contentX - wheel.angleDelta.y / 120 * 2 * (130 + carousel.spacing)))
            }
        }
    }
}
