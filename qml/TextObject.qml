import QtQuick
import QtQuick.Controls
import "Zoom.js" as Zoom

// A text object on the canvas ("WordArt"; readme section 5.4): one line
// of styled text that fills its box, or (wrap) lines as wide as the box.
// Moved, resized, and rotated like a free image. Its words are typed on
// the canvas (double-click it) or in the Text tab of the Wall Features
// panel, where its style is set (right-click > Edit Text).

Item {
    id: root

    // ---- Model roles ----
    required property string objectId
    required property real posX
    required property real posY
    required property real objWidth
    required property real objHeight
    required property real objRotation
    required property int objZ
    required property string objText
    required property var textStyle

    // The scene item (Main.qml), for coordinate mapping.
    property Item sceneItem

    // Shared right-click menu (ObjectContextMenu in Main.qml).
    property var contextMenu

    // Present mode: view-only, never shown as selected. Disabled items
    // let clicks through to the canvas.
    readonly property bool presenting: sceneItem ? sceneItem.presenting : false
    enabled: !presenting

    readonly property bool selected:
        !presenting && sceneModel.selectedId === objectId

    // Used by the context menu and the Text tab.
    readonly property bool isText: true
    readonly property bool wrap: textStyle && textStyle.wrap === true
    readonly property bool stretch: textStyle && textStyle.stretch === true && !wrap

    x: posX
    y: posY
    width: objWidth
    height: objHeight
    rotation: objRotation
    z: objZ


    // -------------------------------------------------
    // Model sync (as in MediaObject.qml)
    // -------------------------------------------------

    function commit() {
        // Wrapping, the height follows the lines at the new width.
        if (wrap && objText !== "")
            fitHeight(art.wrappedHeight)
        sceneModel.commitGeometry(objectId, x, y, width, height, rotation)
        rebind()
    }

    // A new height keeping the top edge where it is (rotated or not).
    function fitHeight(h) {
        var dh = h - height
        var r = rotation * Math.PI / 180
        var cx = x + width / 2 - Math.sin(r) * dh / 2
        var cy = y + height / 2 + Math.cos(r) * dh / 2
        height = h
        x = cx - width / 2
        y = cy - h / 2
    }

    function rebind() {
        x = Qt.binding(function() { return root.posX })
        y = Qt.binding(function() { return root.posY })
        width = Qt.binding(function() { return root.objWidth })
        height = Qt.binding(function() { return root.objHeight })
        rotation = Qt.binding(function() { return root.objRotation })
    }

    function scaleAround(px, py, f) {
        sceneModel.setMergeKey("scale:" + objectId)
        sceneModel.scaleObject(objectId, px, py, f)
    }

    // The letters' size on the canvas (the Text tab's Size). Wrapping,
    // it's the style's size; otherwise the box scales around its center.
    readonly property real letterSize: art.scaleY * art.basePixelSize

    function setLetterSize(s) {
        if (wrap)
            sceneModel.setTextStyle(objectId, { size: s })
        else if (letterSize > 0)
            scaleAround(x + width / 2, y + height / 2, s / letterSize)
    }


    // -------------------------------------------------
    // The box follows the text's proportions after an edit (new words,
    // font, outline, depth...), unless the style stretches it; wrapping,
    // its height follows the lines. Only after the user's edits: undo
    // and loading never resize anything.
    // -------------------------------------------------

    Connections {
        target: sceneModel
        function onTextEdited(id) {
            if (id === root.objectId)
                fitTimer.restart()
        }
    }

    // Wrap on or off (Text tab), keeping the letters' size on screen.
    // Turning it off, the box then fits the one line at that size.
    property real unwrapSize: 0

    function setWrap(on) {
        if (on) {
            unwrapSize = 0
            sceneModel.setTextStyle(objectId, { wrap: true, size: art.scaleY * art.basePixelSize })
        } else {
            unwrapSize = textStyle.size
            sceneModel.setTextStyle(objectId, { wrap: false })
        }
    }

    Timer {
        id: fitTimer
        interval: 30
        onTriggered: {
            if (!root.wrap && root.unwrapSize > 0 && root.objText !== "") {
                var h = art.naturalHeight * root.unwrapSize / art.basePixelSize
                root.unwrapSize = 0
                sceneModel.fitTextHeight(root.objectId, h)
                sceneModel.fitTextWidth(root.objectId, h * art.naturalAspect)
                return
            }
            root.unwrapSize = 0
            if (root.stretch || root.objText === "")
                return
            if (root.wrap) {
                if (Math.abs(art.wrappedHeight - root.objHeight) > 0.5)
                    sceneModel.fitTextHeight(root.objectId, art.wrappedHeight)
                return
            }
            var w = root.objHeight * art.naturalAspect
            if (Math.abs(w - root.objWidth) > 0.5)
                sceneModel.fitTextWidth(root.objectId, w)
        }
    }


    // -------------------------------------------------
    // The text
    // -------------------------------------------------

    TextArt {
        id: art
        anchors.fill: parent
        text: root.objText
        style: root.textStyle
    }

    // -------------------------------------------------
    // Typing on the canvas: a field under the box (double-click, or a
    // new text object). The words change as you type; Enter, Esc, or
    // clicking elsewhere finishes. A run of typing is one undo step.
    // -------------------------------------------------

    property bool typing: false

    function startTyping() {
        typing = true
        Qt.callLater(function() {
            typeField.forceActiveFocus()
            typeField.selectAll()
        })
    }

    Connections {
        target: root.sceneItem
        function onTextTypeRequested(id) {
            if (id === root.objectId)
                root.startTyping()
        }
    }

    onSelectedChanged: if (!selected) typing = false

    TextField {
        id: typeField
        objectName: "canvasTextField"

        visible: root.typing
        z: 10
        anchors.top: parent.bottom
        anchors.topMargin: 8
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(240, Math.min(root.width, 640))
        placeholderText: "Type the text"

        text: root.objText
        onTextEdited: sceneModel.setText(root.objectId, text)
        onAccepted: root.typing = false
        Keys.onEscapePressed: root.typing = false
        onActiveFocusChanged: if (!activeFocus) root.typing = false
    }

    // Empty text: a faint placeholder, so the box can still be found.
    Text {
        anchors.centerIn: parent
        visible: root.objText === "" && !root.presenting
        text: "(empty text)"
        color: "#80ffffff"
        font.pixelSize: 14
    }


    // -------------------------------------------------
    // Selection outline
    // -------------------------------------------------

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: "#5da9ff"
        border.width: 1
        visible: root.selected
        z: 5
    }


    // -------------------------------------------------
    // Move; double-click edits
    // -------------------------------------------------

    MouseArea {
        id: moveArea

        anchors.fill: parent
        z: 2

        acceptedButtons: Qt.LeftButton | Qt.RightButton

        property bool dragging: false
        property bool moved: false
        property point startMouse
        property point startPos

        onPressed: function(mouse) {
            sceneModel.select(root.objectId)

            if (mouse.button === Qt.RightButton) {
                dragging = false
                if (root.contextMenu)
                    root.contextMenu.openFor(root)
                return
            }

            dragging = true
            moved = false
            startMouse = moveArea.mapToItem(root.sceneItem, mouse.x, mouse.y)
            startPos = Qt.point(root.x, root.y)
        }

        onPositionChanged: function(mouse) {
            if (!pressed || !dragging)
                return

            var p = moveArea.mapToItem(root.sceneItem, mouse.x, mouse.y)
            var dx = p.x - startMouse.x
            var dy = p.y - startMouse.y

            if (!moved && Math.abs(dx) + Math.abs(dy) < 6)
                return
            moved = true

            root.x = startPos.x + dx
            root.y = startPos.y + dy
        }

        onReleased: {
            if (dragging && moved)
                root.commit()
            dragging = false
        }

        onDoubleClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton && root.sceneItem)
                root.sceneItem.textTypeRequested(root.objectId)
        }

        // Mouse wheel over selected text scales it around the pointer.
        onWheel: function(wheel) {
            if (!root.selected || wheel.angleDelta.y === 0) {
                wheel.accepted = false
                return
            }
            var p = moveArea.mapToItem(root.sceneItem, wheel.x, wheel.y)
            root.scaleAround(p.x, p.y, Zoom.wheelFactor(wheel.angleDelta.y, appSettings.zoomStep))
        }

        onCanceled: {
            dragging = false
            root.rebind()
        }
    }


    // -------------------------------------------------
    // Resize (proportions kept unless stretching or wrapping) and rotate
    // -------------------------------------------------

    ResizeHandles {
        visible: root.selected

        target: root
        sceneItem: root.sceneItem

        keepAspect: !root.stretch && !root.wrap && root.objText !== ""
        aspectRatio: art.naturalAspect

        minWidth: 30
        minHeight: 16

        color: "#5da9ff"

        onFinished: root.commit()
    }

    RotationHandle {
        visible: root.selected

        target: root
        sceneItem: root.sceneItem

        pivot: function() {
            return root.mapToItem(root.sceneItem, root.width / 2, root.height / 2)
        }
        currentRotation: function() { return root.rotation }
        applyRotation: function(r) { root.rotation = r }

        onFinished: root.commit()
    }
}
