.pragma library

// Shared wheel-zoom step, so every zoomable thing feels the same.

// Scale per mouse-wheel notch (angleDelta 120).
var STEP = 1.05

// Zoom factor for a wheel event's angleDelta.y. Proportional to the
// delta, so trackpads (many small deltas) zoom smoothly too.
function wheelFactor(angleDeltaY) {
    return Math.pow(STEP, angleDeltaY / 120)
}
