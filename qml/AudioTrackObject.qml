import QtQuick

// An audio track: a player with no place on the canvas. It is a row of
// sceneModel like every other object (so saving, undo, and deleting
// work the same), but draws nothing; it is controlled from the
// sidebar's Audio tab (readme section 14).

Item {
    id: root

    // ---- Model roles ----
    required property string objectId
    required property bool objPlaying
    required property bool objMuted
    required property real objVolume
    required property bool objLoop
    required property real objSpeed
    required property bool objPreservePitch
    required property real objLoopA
    required property real objLoopB
    required property string sourceUrl
    required property string sourcePath
    required property string sourceName
    required property bool sourceMissing

    property Item sceneItem
    property var contextMenu

    visible: false
    width: 0
    height: 0

    MediaView {
        id: view

        url: root.sourceUrl
        type: "audio"
        missing: root.sourceMissing
        playing: root.objPlaying
        muted: root.objMuted
        volume: root.objVolume
        loop: root.objLoop
        speed: root.objSpeed
        preservePitch: root.objPreservePitch
        loopA: root.objLoopA
        loopB: root.objLoopB
        name: root.sourceName
        path: root.sourcePath

        // Continue from a position handed over (e.g. by Convert to
        // Audio Track).
        onMediaLoaded: {
            var ms = root.sceneItem ? root.sceneItem.takePendingSeek(root.objectId) : -1
            if (ms > 0)
                view.seek(ms)
        }

        Component.onCompleted: if (root.sceneItem) root.sceneItem.registerView(root.objectId, view)
        Component.onDestruction: if (root.sceneItem) root.sceneItem.unregisterView(root.objectId, view)
    }
}
