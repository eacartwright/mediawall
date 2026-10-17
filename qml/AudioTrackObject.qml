import QtQuick

// An audio track: a player with no place on the canvas. It is a row of
// sceneModel like every other object (so saving, undo, and deleting
// work the same), but draws nothing; it is controlled from the
// sidebar's Playback tab (readme section 14).
//
// A speech track (readme 14.6) has no file: its words and settings are
// its source, and speechEngine makes its clip (temporary, for this
// session) when it's about to play: when it's loaded playing, or at its
// first Play.

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
    required property var objSpeech

    property Item sceneItem
    property var contextMenu

    visible: false
    width: 0
    height: 0

    readonly property bool isSpeech: root.objSpeech !== undefined && root.objSpeech !== null
                                     && root.objSpeech.text !== undefined
    // The speech track's clip, once made ("" until then).
    readonly property string speechUrl: {
        speechEngine.clipsVersion          // re-read when clips are made
        return isSpeech ? speechEngine.clipUrl(root.objSpeech) : ""
    }

    function needClip() {
        // (Asks the engine, not speechUrl, which may not be re-read yet.)
        if (isSpeech && objPlaying && speechEngine.clipUrl(objSpeech) === "")
            speechEngine.request(objSpeech)
    }
    onObjPlayingChanged: needClip()
    onObjSpeechChanged: needClip()
    Component.onCompleted: needClip()
    // Piper or the voices were just set up: try again.
    Connections {
        target: speechEngine
        function onVoicesChanged() { root.needClip() }
    }

    MediaView {
        id: view

        url: root.isSpeech ? root.speechUrl : root.sourceUrl
        type: "audio"
        missing: root.isSpeech ? false : root.sourceMissing
        playing: root.objPlaying
        muted: root.objMuted
        volume: root.objVolume * (root.sceneItem ? root.sceneItem.masterVolume : 1)
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
