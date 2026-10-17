import QtQuick
import QtQuick.Effects
import QtQuick.Shapes

// Draws text in a text object's style ("WordArt"; readme section 5.4).
// One line scaled to fill this item, keeping its proportions (centered)
// unless the style says stretch; or, with wrap, lines as wide as this
// item at the style's letter size, from the top. The letters' outlines
// come from textShaper (bridge/text_shaper.py), which also bends them
// onto an arc and tilts them; drawn as vector shapes, they stay sharp
// at any size. Used for text objects on the canvas and for the style
// previews in the Text tab.

Item {
    id: art

    property string text: ""

    // A text style (core/scene.py TEXT_STYLE_DEFAULTS). The model's are
    // always complete; previews may give only some values.
    property var style: ({})

    function value(key, fallback) {
        var v = style ? style[key] : undefined
        return v === undefined ? fallback : v
    }

    readonly property string fontFamily: value("font", "") || Qt.application.font.family
    readonly property bool bold: value("bold", true)
    readonly property bool italic: value("italic", false)
    readonly property color fill: value("fill", "#ffffff")
    readonly property string fill2: value("fill2", "")
    readonly property color outline: value("outline", "#000000")
    readonly property real outlineWidth: value("outline_width", 3)
    readonly property int depth: value("depth", 0)
    readonly property color depthColor: value("depth_color", "#404040")
    readonly property bool stretch: value("stretch", false) && !wrap
    readonly property bool wrap: value("wrap", false)
    readonly property real size: value("size", 60)
    readonly property string align: value("align", "center")
    readonly property real arc: value("arc", 0)
    readonly property real tilt: value("tilt", 0)
    readonly property real glow: value("glow", 0)
    readonly property color glowColor: value("glow_color", "#40c0ff")

    // Drawn at this size, then scaled; style sizes are in these units.
    readonly property int basePixelSize: 100

    readonly property real pad: outlineWidth / 2

    // Wrapping: the line length (in base units) that fits this item's
    // width at the style's letter size.
    readonly property real wrapScale: size / basePixelSize
    readonly property real wrapWidth: Math.max(basePixelSize, width / wrapScale - 2 * pad - depth)

    // The letters' outline (SVG path data) and bounds.
    readonly property var shaped: textShaper.shape(text, fontFamily, bold, italic,
                                                   wrap ? wrapWidth : 0, align, arc, tilt)
    readonly property rect glyphs: Qt.rect(shaped.x, shaped.y, shaped.width, shaped.height)

    // The natural size with outline and depth. Wrapping, the width is
    // the line length (so alignment is within the item).
    readonly property real naturalWidth: Math.max(1, (wrap ? wrapWidth : glyphs.width) + 2 * pad + depth)
    readonly property real naturalHeight: Math.max(1, glyphs.height + 2 * pad + depth)
    readonly property real naturalAspect: naturalWidth / naturalHeight

    readonly property real scaleX: wrap ? wrapScale
                                 : stretch ? width / naturalWidth
                                 : Math.min(width / naturalWidth, height / naturalHeight)
    readonly property real scaleY: wrap || !stretch ? scaleX : height / naturalHeight

    // Wrapping: the height the lines take on the canvas.
    readonly property real wrappedHeight: naturalHeight * wrapScale

    Item {
        id: body

        width: art.naturalWidth
        height: art.naturalHeight

        // Centered when keeping proportions; from the top-left wrapping.
        x: art.wrap ? 0 : (art.width - width * art.scaleX) / 2
        y: art.wrap ? 0 : (art.height - height * art.scaleY) / 2

        transform: Scale { xScale: art.scaleX; yScale: art.scaleY }

        // Where the outline's (0, 0) goes, so its bounds start at the
        // padding. (Wrapping, x = 0 is the line's start instead.)
        readonly property real originX: art.wrap ? art.pad : art.pad - art.glyphs.x
        readonly property real originY: art.pad - art.glyphs.y

        // Glow: the letters, thickened and blurred, behind everything.
        // Drawn into a layer with room around it for the blur. Built only
        // while there is a glow: an effect whose source's layer is turned
        // on later never shows it.
        Loader {
            id: glowLoader
            objectName: "glowLoader"         // found by tests/app
            active: art.glow > 0 && !rebuilding

            // The effect keeps its first size when the outline changes
            // (arc, tilt, new words), so it is built again instead.
            property bool rebuilding: false
            readonly property var outline: art.shaped

            onOutlineChanged: {
                if (!active)
                    return
                rebuilding = true
                Qt.callLater(function() { glowLoader.rebuilding = false })
            }

            sourceComponent: Item {
                readonly property real margin: 2 * art.glow + art.pad + 4

                x: -margin
                y: -margin
                width: body.width + 2 * margin
                height: body.height + 2 * margin

                Item {
                    id: glowSource

                    anchors.fill: parent
                    visible: false
                    layer.enabled: true

                    Shape {
                        x: body.originX + parent.parent.margin
                        y: body.originY + parent.parent.margin
                        preferredRendererType: Shape.CurveRenderer

                        ShapePath {
                            fillColor: art.glowColor
                            strokeColor: art.glowColor
                            strokeWidth: art.outlineWidth + art.glow
                            joinStyle: ShapePath.RoundJoin
                            PathSvg { path: art.shaped.path }
                        }
                    }
                }

                MultiEffect {
                    source: glowSource
                    anchors.fill: parent
                    blurEnabled: true
                    blurMax: 64
                    blur: Math.min(1, art.glow / 16)
                    // Brighter than a plain blur, so it reads as light.
                    brightness: 0.15
                }
            }
        }

        // 3D extrusion: copies of the text stepping down and right, the
        // farthest drawn first, a little darker the farther back.
        Repeater {
            model: art.depth

            Shape {
                id: slice

                required property int index
                readonly property int step: art.depth - index

                x: body.originX + step
                y: body.originY + step
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    fillColor: Qt.darker(art.depthColor, 1 + 0.4 * slice.step / art.depth)
                    strokeColor: art.outlineWidth > 0 ? fillColor : "transparent"
                    strokeWidth: art.outlineWidth
                    joinStyle: ShapePath.RoundJoin
                    PathSvg { path: art.shaped.path }
                }
            }
        }

        // The letters' face. The curve renderer doesn't always redraw
        // when a gradient's colours change (a new preset's outline and
        // depth showed, but the old fill stayed), so the face is built
        // again whenever the fill or its span changes: the Repeater's
        // one-item model is that key. Swapped in the same frame, so it
        // doesn't flicker.
        Repeater {
            objectName: "textFace"               // found by tests/app
            model: [art.fill + "|" + art.fill2 + "|" + art.glyphs.y + "|" + art.glyphs.height]

            Shape {
                id: front

                x: body.originX
                y: body.originY
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    // Always the gradient (a plain fill is two equal stops).
                    fillGradient: front.fillGrad
                    strokeColor: art.outlineWidth > 0 ? art.outline : "transparent"
                    strokeWidth: art.outlineWidth
                    joinStyle: ShapePath.RoundJoin
                    PathSvg { path: art.shaped.path }
                }

                // Top to bottom across the glyphs.
                property LinearGradient fillGrad: LinearGradient {
                    x1: 0
                    y1: art.glyphs.y
                    x2: 0
                    y2: art.glyphs.y + art.glyphs.height
                    GradientStop { position: 0; color: art.fill }
                    GradientStop { position: 1; color: art.fill2 !== "" ? art.fill2 : art.fill }
                }
            }
        }

        // Emoji, in colour: not part of the outline (textShaper gives
        // each one's centre, size, and angle), so they take no fill,
        // outline, depth, or glow.
        Repeater {
            objectName: "emojiRepeater"      // found by tests/app
            model: art.shaped.emoji || []

            Text {
                required property var modelData

                text: modelData.text
                // Shown only where no emoji font has the picture (e.g.
                // flags on Windows come out as two letters).
                color: art.fill
                font.pixelSize: Math.max(1, modelData.size)
                x: body.originX + modelData.x - width / 2
                y: body.originY + modelData.y - height / 2
                rotation: modelData.angle
            }
        }
    }
}
