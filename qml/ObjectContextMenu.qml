import QtQuick
import QtQuick.Controls

// Right-click menu shared by every scene object.
// One instance lives in Main.qml; objects call openFor(item).
// Items that don't apply to the clicked object are hidden.

Menu {
    id: menu

    // The object item that was right-clicked.
    property Item target: null

    readonly property string targetId: target ? target.objectId : ""
    readonly property int targetZ: target ? target.z : 0

    readonly property bool atFront: targetZ >= sceneModel.count
    readonly property bool atBack: targetZ <= 1

    // Media with more than one frame (a free GIF, or one in a container)
    readonly property bool targetAnimated:
        target !== null && target.isAnimated === true

    // A free video, or a container holding one
    readonly property bool targetVideo:
        target !== null && target.isVideo === true

    readonly property bool isContainer:
        target !== null && target.isContainer === true

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
            var what = menu.targetVideo ? "Video" : "Animation"
            return (menu.target && menu.target.objPlaying ? "Pause " : "Play ") + what
        }

        visible: menu.targetAnimated || menu.targetVideo
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.setPlaying(
            menu.target.playbackId, !menu.target.objPlaying
        )
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

    MenuItem {
        text: "Bring to Front"
        enabled: !menu.atFront
        onTriggered: sceneModel.bringToFront(menu.targetId)
    }

    MenuItem {
        text: "Bring Forward"
        enabled: !menu.atFront
        onTriggered: sceneModel.bringForward(menu.targetId)
    }

    MenuItem {
        text: "Send Backward"
        enabled: !menu.atBack
        onTriggered: sceneModel.sendBackward(menu.targetId)
    }

    MenuItem {
        text: "Send to Back"
        enabled: !menu.atBack
        onTriggered: sceneModel.sendToBack(menu.targetId)
    }

    MenuSeparator {}

    MenuItem {
        text: "Duplicate"
        onTriggered: sceneModel.duplicate(menu.targetId)
    }

    MenuItem {
        text: "Delete"
        onTriggered: sceneModel.removeObject(menu.targetId)
    }
}
