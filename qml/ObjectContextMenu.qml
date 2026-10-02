import QtQuick
import QtQuick.Controls

// Right-click menu shared by every scene object.
// One instance lives in Main.qml; objects call openFor(item).
// Items that don't apply to the clicked object are hidden.

Menu {
    id: menu

    // The object item that was right-clicked.
    property Item target: null

    // Shared commands (AppActions.qml), set in Main.qml.
    property var actions

    readonly property string targetId: target ? target.objectId : ""

    // Media with more than one frame (a free GIF, or one in a container)
    readonly property bool targetAnimated:
        target !== null && target.isAnimated === true

    // A free video, or a container holding one
    readonly property bool targetVideo:
        target !== null && target.isVideo === true

    // A non-looping video that has played to the end
    readonly property bool targetEnded:
        targetVideo && target.mediaView !== undefined &&
        target.mediaView !== null && target.mediaView.ended

    readonly property bool isContainer:
        target !== null && target.isContainer === true

    readonly property bool isBrowser:
        target !== null && target.isBrowser === true

    // Objects that step through a folder, and so can filter it.
    readonly property bool filtersFiles:
        isBrowser || (isContainer && target.browseMode === true)

    readonly property bool containerHasContent:
        isContainer && target.hasContent === true

    readonly property bool isFreeMedia:
        target !== null && target.isFreeMedia === true

    // A free image, or a container's content, whose file can't be found
    readonly property bool targetMissing:
        target !== null &&
        (target.sourceMissing === true ||
         (isContainer && target.hasContent === true &&
          target.contentSourceMissing === true))

    function isRotated(degrees) {
        var r = ((degrees % 360) + 360) % 360
        return r > 0.01 && r < 359.99
    }

    readonly property bool targetRotated:
        target !== null && isRotated(target.rotation)

    readonly property bool contentRotated:
        containerHasContent && isRotated(target.contentRotation)

    function openFor(item) {
        target = item
        popup()   // opens at the mouse cursor
    }


    // ---- Missing file ----

    MenuItem {
        text: "Locate Missing File…"

        visible: menu.targetMissing
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.locateMissing(menu.targetId)
    }

    MenuSeparator {
        visible: menu.targetMissing
        height: visible ? implicitHeight : 0
    }


    // ---- Playback (animated images and video) ----

    MenuItem {
        text: {
            if (menu.targetEnded)
                return "Replay Video"
            var what = menu.targetVideo ? "Video" : "Animation"
            return (menu.target && menu.target.objPlaying ? "Pause " : "Play ") + what
        }

        visible: menu.targetAnimated || menu.targetVideo
        height: visible ? implicitHeight : 0

        onTriggered: {
            if (menu.targetEnded) {
                if (!menu.target.objPlaying)
                    sceneModel.setPlaying(menu.target.playbackId, true)
                menu.target.mediaView.replay()
            } else {
                sceneModel.setPlaying(
                    menu.target.playbackId, !menu.target.objPlaying
                )
            }
        }
    }

    MenuItem {
        text: menu.target && menu.target.mediaMuted ? "Unmute" : "Mute"

        visible: menu.targetVideo
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.setMuted(
            menu.target.playbackId, !menu.target.mediaMuted
        )
    }

    MenuItem {
        id: loopItem

        text: "Loop"

        checkable: true
        checked: menu.target !== null && menu.target.mediaLoop === true

        visible: menu.targetVideo
        height: visible ? implicitHeight : 0

        onTriggered: {
            sceneModel.setLoop(menu.target.playbackId, !menu.target.mediaLoop)
            loopItem.checked = Qt.binding(function() {
                return menu.target !== null && menu.target.mediaLoop === true
            })
        }
    }

    // ---- A-B loop (video): points are set at the current position ----

    readonly property bool targetHasLoopPoints:
        targetVideo && (target.mediaLoopA >= 0 || target.mediaLoopB >= 0)

    function formatMs(ms) {
        var t = Math.max(0, ms) / 1000
        var m = Math.floor(t / 60)
        var sec = (t - m * 60).toFixed(1)
        return m + ":" + (sec < 10 ? "0" : "") + sec
    }

    MenuItem {
        text: "Set Loop Start (A) Here"
              + (menu.targetVideo && menu.target.mediaLoopA >= 0
                 ? "   [" + menu.formatMs(menu.target.mediaLoopA) + "]" : "")

        visible: menu.targetVideo
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.setLoopA(menu.target.playbackId,
                                         menu.target.mediaView.position)
    }

    MenuItem {
        text: "Set Loop End (B) Here"
              + (menu.targetVideo && menu.target.mediaLoopB >= 0
                 ? "   [" + menu.formatMs(menu.target.mediaLoopB) + "]" : "")

        visible: menu.targetVideo
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.setLoopB(menu.target.playbackId,
                                         menu.target.mediaView.position)
    }

    // Video as audio: the video leaves the canvas and its sound goes on
    // as a track in the Playback tab, from the same position (undoable).
    MenuItem {
        text: "Convert to Audio Track"

        visible: menu.targetVideo
        height: visible ? implicitHeight : 0

        onTriggered: {
            // Read everything first: a free video's item is destroyed
            // by the conversion.
            var scene = menu.target.sceneItem
            var position = menu.target.mediaView ? menu.target.mediaView.position : 0
            var trackId = sceneModel.convertToAudioTrack(menu.target.playbackId)
            if (trackId !== "" && scene)
                scene.setPendingSeek(trackId, position)
        }
    }

    MenuItem {
        text: "Clear A–B Loop"

        visible: menu.targetHasLoopPoints
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.clearLoop(menu.target.playbackId)
    }

    MenuSeparator {
        visible: menu.targetAnimated || menu.targetVideo
        height: visible ? implicitHeight : 0
    }


    // ---- Free media ----

    MenuItem {
        text: "Crop / Zoom Inside…"

        visible: menu.isFreeMedia
        height: visible ? implicitHeight : 0

        onTriggered: {
            var id = menu.targetId
            // The image's delegate is replaced by a container, so run
            // this after the menu has finished with it.
            Qt.callLater(function() { sceneModel.wrapInContainer(id) })
        }
    }

    MenuSeparator {
        visible: menu.isFreeMedia
        height: visible ? implicitHeight : 0
    }


    // ---- Container ----

    MenuItem {
        text: "Adjust Content…"

        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: menu.target.adjusting = true
    }

    MenuItem {
        text: "Fit Content (show whole image)"

        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.fitContent(menu.targetId, false)
    }

    MenuItem {
        text: "Fill Container"

        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.fitContent(menu.targetId, true)
    }

    // ---- Browsing (containers) ----

    MenuItem {
        text: "Browse This Folder"
        visible: menu.isContainer && !menu.target.browseMode && menu.target.hasContent
        height: visible ? implicitHeight : 0
        onTriggered: sceneModel.startBrowsing(menu.targetId)
    }

    // Any container, filled or not: pick a folder to browse.
    MenuItem {
        text: "Browse Folder…"
        visible: menu.isContainer
        height: visible ? implicitHeight : 0
        onTriggered: sceneModel.chooseBrowseFolder(menu.targetId)
    }

    MenuItem {
        text: "Stop Browsing"
        visible: menu.isContainer && menu.target.browseMode === true
        height: visible ? implicitHeight : 0
        onTriggered: sceneModel.stopBrowsing(menu.targetId)
    }

    MenuItem {
        id: browseSubfoldersItem
        text: "Browse Subfolders Too"
        checkable: true
        checked: menu.isContainer && menu.target.browseSubfolders === true
        visible: menu.isContainer && menu.target.browseMode === true
        height: visible ? implicitHeight : 0
        onTriggered: {
            sceneModel.setContainerBrowseSubfolders(menu.targetId, !menu.target.browseSubfolders)
            browseSubfoldersItem.checked = Qt.binding(function() {
                return menu.isContainer && menu.target.browseSubfolders === true
            })
        }
    }

    // Which files a browser or browsing container steps through (one
    // is checked). Containers show no audio.
    Repeater {
        model: [
            { text: "Show All Media", value: "all" },
            { text: "Show Images Only", value: "image" },
            { text: "Show Videos Only", value: "video" },
            { text: "Show Audio Only", value: "audio" },
        ]

        MenuItem {
            required property var modelData

            text: modelData.value === "all" && menu.isContainer
                  ? "Show Images and Videos" : modelData.text
            checkable: true
            checked: menu.filtersFiles && menu.target.mediaFilter === modelData.value
            visible: menu.filtersFiles && (modelData.value !== "audio" || menu.isBrowser)
            height: visible ? implicitHeight : 0
            onTriggered: {
                sceneModel.setMediaFilter(menu.targetId, modelData.value)
                checked = Qt.binding(function() {
                    return menu.filtersFiles && menu.target.mediaFilter === modelData.value
                })
            }
        }
    }

    MenuItem {
        id: lockItem

        text: "Scale Content with Container"

        checkable: true
        checked: menu.target !== null && menu.target.lockContent === true

        visible: menu.isContainer
        height: visible ? implicitHeight : 0

        onTriggered: {
            sceneModel.setLockContent(menu.targetId, !menu.target.lockContent)

            // Clicking toggles `checked` itself; restore the binding.
            lockItem.checked = Qt.binding(function() {
                return menu.target !== null && menu.target.lockContent === true
            })
        }
    }

    MenuItem {
        text: "Release Content"

        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.releaseContent(menu.targetId)
    }

    MenuItem {
        text: "Remove Content"

        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.removeContent(menu.targetId)
    }

    MenuSeparator {
        visible: menu.isContainer
        height: visible ? implicitHeight : 0
    }


    // ---- Mirror (the picture: a free image/video, or a container's) ----

    MenuItem {
        id: mirrorItem

        text: "Flip Horizontally"

        checkable: true
        checked: menu.target !== null && menu.target.mediaMirrored === true

        visible: menu.isFreeMedia || menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: {
            sceneModel.setMirrored(menu.target.playbackId, !menu.target.mediaMirrored)
            mirrorItem.checked = Qt.binding(function() {
                return menu.target !== null && menu.target.mediaMirrored === true
            })
        }
    }

    // ---- Rotation (also: double-click the orange knob) ----

    MenuItem {
        text: "Reset Rotation"

        visible: menu.targetRotated
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.commitGeometry(
            menu.targetId, menu.target.x, menu.target.y,
            menu.target.width, menu.target.height, 0
        )
    }

    MenuItem {
        text: "Reset Content Rotation"

        visible: menu.contentRotated
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.commitContent(
            menu.targetId, menu.target.contentX, menu.target.contentY,
            menu.target.contentWidth, menu.target.contentHeight, 0
        )
    }

    MenuSeparator {
        visible: menu.targetRotated || menu.contentRotated
        height: visible ? implicitHeight : 0
    }


    // ---- Z-order ----

    // Shared commands (AppActions.qml). They act on the selection, and
    // the right-clicked object is always the selected one.

    MenuItem { action: menu.actions.bringToFront }
    MenuItem { action: menu.actions.bringForward }
    MenuItem { action: menu.actions.sendBackward }
    MenuItem { action: menu.actions.sendToBack }

    MenuSeparator {}

    MenuItem { action: menu.actions.duplicate }
    MenuItem { action: menu.actions.deleteSelected }
}
