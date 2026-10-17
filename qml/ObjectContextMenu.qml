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

    // A locked container (Lock Container): the items that would change
    // it, or what it shows, are greyed out.
    readonly property bool targetLocked:
        isContainer && target.locked === true

    readonly property bool isFreeMedia:
        target !== null && target.isFreeMedia === true

    readonly property bool isText:
        target !== null && target.isText === true

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
        placeSpeedMenu()
        placeSortMenu()
        popup()   // opens at the mouse cursor
    }

    // ---- Speed submenu (animated images and video) ----
    // A submenu can't be hidden like an item, so it is put in after
    // the Play/Pause item when it applies and taken out otherwise.

    readonly property var speeds: [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4]

    function formatSpeed(s) {
        return (Math.round(s * 100) / 100) + "×"
    }

    function placeSpeedMenu() {
        for (var i = 0; i < count; i++) {
            if (itemAt(i).subMenu === speedMenu) {
                takeMenu(i)
                break
            }
        }
        if (!(targetAnimated || targetVideo))
            return
        for (var j = 0; j < count; j++) {
            if (itemAt(j) === playItem) {
                insertMenu(j + 1, speedMenu)
                return
            }
        }
    }

    // ---- Sort by submenu (browsers and browsing containers) ----
    // Put in just after the filter items, like the Speed submenu.

    function placeSortMenu() {
        for (var i = 0; i < count; i++) {
            if (itemAt(i).subMenu === sortMenu) {
                takeMenu(i)
                break
            }
        }
        if (!filtersFiles)
            return
        for (var j = 0; j < count; j++) {
            if (itemAt(j) === lockItem) {
                insertMenu(j, sortMenu)
                return
            }
        }
    }

    property Menu sortMenu: Menu {
        id: sortSub
        objectName: "sortMenu"       // found by tests/app
        title: "Sort by"

        readonly property var owner: menu
        readonly property string sortBy: owner.filtersFiles ? owner.target.sortBy : ""
        readonly property bool descending: owner.filtersFiles && owner.target.sortDescending === true

        function setSort(key, descending) {
            sceneModel.setSort(owner.targetId, key, descending)
        }

        // Checked state is re-bound after each click (a click toggles it).
        component SortItem: MenuItem {
            id: sortItem
            property bool current
            checkable: true
            checked: current
            onTriggered: checked = Qt.binding(function() { return sortItem.current })
        }

        SortItem {
            text: "Name"
            current: sortSub.sortBy === "name"
            onTriggered: sortSub.setSort("name", sortSub.descending)
        }
        SortItem {
            text: "Date Modified"
            current: sortSub.sortBy === "date"
            onTriggered: sortSub.setSort("date", sortSub.descending)
        }
        SortItem {
            text: "Type"
            current: sortSub.sortBy === "type"
            onTriggered: sortSub.setSort("type", sortSub.descending)
        }
        SortItem {
            text: "Random"
            current: sortSub.sortBy === "random"
            onTriggered: sortSub.setSort("random", sortSub.descending)
        }
        MenuSeparator {}
        SortItem {
            text: "Ascending"
            enabled: sortSub.sortBy !== "random"
            current: !sortSub.descending
            onTriggered: sortSub.setSort(sortSub.sortBy, false)
        }
        SortItem {
            text: "Descending"
            enabled: sortSub.sortBy !== "random"
            current: sortSub.descending
            onTriggered: sortSub.setSort(sortSub.sortBy, true)
        }
    }

    property Menu speedMenu: Menu {
        objectName: "speedMenu"      // found by tests/app
        title: "Speed" + (menu.target && menu.target.mediaSpeed !== undefined
                          && menu.target.mediaSpeed !== 1
                          ? "   (" + menu.formatSpeed(menu.target.mediaSpeed) + ")" : "")

        id: speedSub

        // Inside a MenuItem, `menu` is the item's own menu (this
        // submenu), so its items reach the context menu through here.
        readonly property var owner: menu

        Instantiator {
            model: menu.speeds

            MenuItem {
                id: speedItem
                required property real modelData

                function isCurrent() {
                    var t = speedSub.owner.target
                    return t !== null && t.mediaSpeed !== undefined
                           && Math.abs(t.mediaSpeed - modelData) < 0.001
                }

                text: speedSub.owner.formatSpeed(modelData) + (modelData === 1 ? "  (normal)" : "")
                checkable: true
                checked: isCurrent()
                onTriggered: {
                    sceneModel.setSpeed(speedSub.owner.target.playbackId, modelData)
                    speedItem.checked = Qt.binding(speedItem.isCurrent)
                }
            }

            onObjectAdded: function(index, object) { speedSub.insertItem(index, object) }
            onObjectRemoved: function(index, object) { speedSub.removeItem(object) }
        }
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


    // ---- Text: edited in the Wall Features panel's Text tab ----

    MenuItem {
        text: "Edit Text…"

        visible: menu.isText
        height: visible ? implicitHeight : 0

        onTriggered: menu.target.sceneItem.textEditRequested(menu.targetId)
    }

    MenuSeparator {
        visible: menu.isText
        height: visible ? implicitHeight : 0
    }


    // ---- Playback (animated images and video) ----

    MenuItem {
        id: playItem

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
        id: lockContainerItem
        objectName: "lockContainerItem"     // found by tests/app

        text: "Lock Container"

        checkable: true
        checked: menu.targetLocked

        visible: menu.isContainer
        height: visible ? implicitHeight : 0

        onTriggered: {
            sceneModel.setLocked(menu.targetId, !menu.targetLocked)
            lockContainerItem.checked = Qt.binding(function() { return menu.targetLocked })
        }
    }

    MenuItem {
        text: "Adjust Content…"

        enabled: !menu.targetLocked
        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: menu.target.adjusting = true
    }

    MenuItem {
        text: "Fit Content (show whole image)"
        enabled: !menu.targetLocked

        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.fitContent(menu.targetId, false)
    }

    MenuItem {
        text: "Fill Container"
        enabled: !menu.targetLocked

        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.fitContent(menu.targetId, true)
    }

    // ---- Browsing (containers) ----

    MenuItem {
        text: "Browse This Folder"
        enabled: !menu.targetLocked
        visible: menu.isContainer && !menu.target.browseMode && menu.target.hasContent
        height: visible ? implicitHeight : 0
        onTriggered: sceneModel.startBrowsing(menu.targetId)
    }

    // Any container, filled or not: pick a folder to browse.
    MenuItem {
        text: "Browse Folder…"
        enabled: !menu.targetLocked
        visible: menu.isContainer
        height: visible ? implicitHeight : 0
        onTriggered: sceneModel.chooseBrowseFolder(menu.targetId)
    }

    MenuItem {
        text: "Stop Browsing"
        enabled: !menu.targetLocked
        visible: menu.isContainer && menu.target.browseMode === true
        height: visible ? implicitHeight : 0
        onTriggered: sceneModel.stopBrowsing(menu.targetId)
    }

    MenuItem {
        id: browseSubfoldersItem
        text: "Browse Subfolders Too"
        enabled: !menu.targetLocked
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

    // A browsing container: mark the file shown as a favorite.
    MenuItem {
        id: favoriteItem
        text: "Favorite"
        checkable: true
        checked: menu.isContainer && menu.target.isFavorite === true
        visible: menu.isContainer && menu.target.browseMode === true && menu.target.hasContent
        height: visible ? implicitHeight : 0
        onTriggered: {
            menu.target.toggleFavorite()
            favoriteItem.checked = Qt.binding(function() {
                return menu.isContainer && menu.target.isFavorite === true
            })
        }
    }

    // A browsing container: files new to the folder are shown first.
    MenuItem {
        id: newFirstItem
        objectName: "newFirstItem"          // found by tests/app
        text: "Show New Files First"
        enabled: !menu.targetLocked
        checkable: true
        checked: menu.isContainer && menu.target.newFirst === true
        visible: menu.isContainer && menu.target.browseMode === true
        height: visible ? implicitHeight : 0
        onTriggered: {
            sceneModel.setNewFirst(menu.targetId, !menu.target.newFirst)
            newFirstItem.checked = Qt.binding(function() {
                return menu.isContainer && menu.target.newFirst === true
            })
        }
    }

    // A browsing container: at the end of a video, play the next one.
    MenuItem {
        id: continuePlayItem
        text: "Continue Play"
        enabled: !menu.targetLocked
        checkable: true
        checked: menu.isContainer && menu.target.continuePlay === true
        visible: menu.isContainer && menu.target.browseMode === true
        height: visible ? implicitHeight : 0
        onTriggered: {
            sceneModel.setContinuePlay(menu.targetId, !menu.target.continuePlay)
            continuePlayItem.checked = Qt.binding(function() {
                return menu.isContainer && menu.target.continuePlay === true
            })
        }
    }

    // Which files a browser or browsing container steps through (one
    // is checked). Containers show no audio.
    Repeater {
        model: [
            { text: "Show All Media", value: "all" },
            { text: "Show Images Only", value: "image" },
            { text: "Show Animated Only", value: "animated" },
            { text: "Show Videos Only", value: "video" },
            { text: "Show Audio Only", value: "audio" },
            { text: "Show Favorites Only", value: "favorites" },
        ]

        MenuItem {
            required property var modelData

            text: modelData.value === "all" && menu.isContainer
                  ? "Show Images and Videos" : modelData.text
            enabled: !menu.targetLocked
            checkable: true
            checked: menu.filtersFiles && menu.target.mediaFilter === modelData.value
            visible: menu.filtersFiles && (modelData.value !== "audio" || menu.isBrowser)
                     && (modelData.value !== "favorites" || menu.isContainer)
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
        enabled: !menu.targetLocked

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
        enabled: !menu.targetLocked

        visible: menu.containerHasContent
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.releaseContent(menu.targetId)
    }

    MenuItem {
        text: "Remove Content"
        enabled: !menu.targetLocked

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
        enabled: !menu.targetLocked

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
        enabled: !menu.targetLocked

        visible: menu.targetRotated
        height: visible ? implicitHeight : 0

        onTriggered: sceneModel.commitGeometry(
            menu.targetId, menu.target.x, menu.target.y,
            menu.target.width, menu.target.height, 0
        )
    }

    MenuItem {
        text: "Reset Content Rotation"
        enabled: !menu.targetLocked

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
