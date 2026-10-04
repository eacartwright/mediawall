import QtQuick

// Steps a browser or browsing container through its folder's files
// (readme section 26): holding Left/Right or a back/forward thumb
// button steps once, pauses, then keeps stepping until released; a
// horizontal wheel (tilt, or a sideways trackpad swipe) steps once per
// notch. The pause and the pace are in Settings (appSettings
// stepRepeatDelay / stepRepeatInterval).
//
// The owner sets `step` to its function(delta), delta -1 or +1.

QtObject {
    id: stepper

    property var step

    property int delta: 0

    // Two timers with fixed intervals: changing a running Timer's
    // interval (delay first, then the pace) made it stop repeating.
    property Timer firstDelay: Timer {
        interval: appSettings.stepRepeatDelay       // ms before repeating
        onTriggered: {
            stepper.step(stepper.delta)
            stepper.repeater.start()
        }
    }

    property Timer repeater: Timer {
        interval: appSettings.stepRepeatInterval    // ms between repeats
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
    //
    // A held tilt arrives as a stream of whole notches at the mouse
    // driver's pace; those are paced like a held button instead (the
    // first steps at once, then the Settings delay, then the interval),
    // so the driver can't step faster than the setting. Trackpad swipes
    // are left alone.

    property real wheelSum: 0

    property int tiltDelta: 0
    property int tiltSteps: 0           // steps in the current hold
    property double tiltLastEvent: 0    // ms timestamps
    property double tiltLastStep: 0

    // Returns true if the event was a sideways one (and so handled).
    function wheel(angleDelta) {
        if (Math.abs(angleDelta.x) <= Math.abs(angleDelta.y))
            return false

        if (Math.abs(angleDelta.x) >= 120) {
            tilt(angleDelta.x > 0 ? -1 : 1)
            return true
        }

        wheelSum += angleDelta.x
        while (Math.abs(wheelSum) >= 120) {
            step(wheelSum > 0 ? -1 : 1)
            wheelSum -= wheelSum > 0 ? 120 : -120
        }
        return true
    }

    function tilt(d) {
        var now = Date.now()
        // Still the same hold: same direction, and the next notch came
        // sooner than a separate tilt would (drivers pause before they
        // repeat, so allow at least the setting's delay plus slack).
        var gap = Math.max(600, appSettings.stepRepeatDelay + 250)
        var held = d === tiltDelta && now - tiltLastEvent < gap
        tiltLastEvent = now

        if (!held) {
            tiltDelta = d
            tiltSteps = 0
        } else {
            var wait = tiltSteps === 1 ? appSettings.stepRepeatDelay
                                       : appSettings.stepRepeatInterval
            if (now - tiltLastStep < wait)
                return
        }
        tiltSteps++
        tiltLastStep = now
        step(d)
    }
}
