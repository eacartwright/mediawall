import QtQuick

// Steps a browser or browsing container through its folder's files
// (readme section 26): holding a back/forward thumb button steps once,
// pauses, then keeps stepping until released; a horizontal wheel (tilt,
// or a sideways trackpad swipe) steps once per notch.
//
// The owner sets `step` to its function(delta), delta -1 or +1.

QtObject {
    id: stepper

    property var step

    property int delta: 0

    // Two timers with fixed intervals: changing a running Timer's
    // interval (400 ms first, then 150 ms) made it stop repeating.
    property Timer firstDelay: Timer {
        interval: 400                   // ms before repeating
        onTriggered: {
            stepper.step(stepper.delta)
            stepper.repeater.start()
        }
    }

    property Timer repeater: Timer {
        interval: 150                   // ms between repeats
        repeat: true
        onTriggered: stepper.step(stepper.delta)
    }

    function begin(d) {
        end()
        delta = d
        step(d)
        firstDelay.start()
    }

    function end() {
        firstDelay.stop()
        repeater.stop()
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
