import QtQuick

// Steps a browser or browsing container through its folder's files
// (readme section 26): holding a back/forward thumb button steps once,
// pauses, then keeps stepping until released; a horizontal wheel (tilt,
// or a sideways trackpad swipe) steps once per notch.
//
// The owner sets `step` to its function(delta), delta -1 or +1.

Timer {
    id: stepper

    property var step

    readonly property int firstDelay: 400     // ms before repeating
    readonly property int repeatDelay: 150    // ms between repeats

    property int delta: 0

    function begin(d) {
        delta = d
        step(d)
        interval = firstDelay
        restart()
    }

    function end() {
        stop()
    }

    onTriggered: {
        interval = repeatDelay
        step(delta)
    }

    // ---- Horizontal wheel ----
    //
    // A wheel notch is 120; trackpads send many small deltas, so they
    // add up. Positive x is a tilt or swipe to the left: previous.

    property real wheelSum: 0

    // Returns true if the event was a sideways one (and so handled).
    function wheel(angleDelta) {
        if (Math.abs(angleDelta.x) <= Math.abs(angleDelta.y))
            return false
        wheelSum += angleDelta.x
        while (Math.abs(wheelSum) >= 120) {
            step(wheelSum > 0 ? -1 : 1)
            wheelSum -= wheelSum > 0 ? 120 : -120
        }
        return true
    }
}
