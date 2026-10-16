import QtQuick
import QtQuick.Shapes

// Draws a line of text in a text object's style ("WordArt"; readme
// section 5.4), scaled to fill this item: keeping its proportions
// (centered) unless the style says stretch. The glyphs are vector
// shapes, so they stay sharp at any size. Used for text objects on the
// canvas and for the style previews in the Text tab.

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
    readonly property bool stretch: value("stretch", false)

    // Drawn at this size, then scaled; style sizes are in these units.
    readonly property int basePixelSize: 100

    // The glyphs' bounds, and the natural size with outline and depth.
    // (Copied when the shape reports a change, not bound: reading the
    // bounds inside a binding the shape itself depends on is a loop.)
    property rect glyphs
    readonly property real pad: outlineWidth / 2
    readonly property real naturalWidth: Math.max(1, glyphs.width + 2 * pad + depth)
    readonly property real naturalHeight: Math.max(1, glyphs.height + 2 * pad + depth)
    readonly property real naturalAspect: naturalWidth / naturalHeight

    readonly property real scaleX: stretch ? width / naturalWidth
                                           : Math.min(width / naturalWidth, height / naturalHeight)
    readonly property real scaleY: stretch ? height / naturalHeight : scaleX

    Item {
        id: body

        width: art.naturalWidth
        height: art.naturalHeight

        // Centered when keeping proportions.
        x: (art.width - width * art.scaleX) / 2
        y: (art.height - height * art.scaleY) / 2

        transform: Scale { xScale: art.scaleX; yScale: art.scaleY }

        // 3D extrusion: copies of the text stepping down and right, the
        // farthest drawn first, a little darker the farther back.
        Repeater {
            model: art.depth

            Shape {
                id: slice

                required property int index
                readonly property int step: art.depth - index

                x: front.x + step
                y: front.y + step
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    fillColor: Qt.darker(art.depthColor, 1 + 0.4 * slice.step / art.depth)
                    strokeColor: art.outlineWidth > 0 ? fillColor : "transparent"
                    strokeWidth: art.outlineWidth
                    joinStyle: ShapePath.RoundJoin

                    PathText {
                        text: art.text
                        font.family: art.fontFamily
                        font.pixelSize: art.basePixelSize
                        font.bold: art.bold
                        font.italic: art.italic
                    }
                }
            }
        }

        Shape {
            id: front

            onBoundingRectChanged: art.glyphs = boundingRect
            Component.onCompleted: art.glyphs = boundingRect

            x: art.pad - art.glyphs.x
            y: art.pad - art.glyphs.y
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                fillColor: art.fill
                fillGradient: art.fill2 !== "" ? front.fillGrad : null
                strokeColor: art.outlineWidth > 0 ? art.outline : "transparent"
                strokeWidth: art.outlineWidth
                joinStyle: ShapePath.RoundJoin

                PathText {
                    text: art.text
                    font.family: art.fontFamily
                    font.pixelSize: art.basePixelSize
                    font.bold: art.bold
                    font.italic: art.italic
                }
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
}
