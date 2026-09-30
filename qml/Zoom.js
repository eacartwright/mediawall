.pragma library

// Shared wheel-zoom math, so every zoomable thing feels the same.
// The step comes from the Settings dialog (appSettings.zoomStep).

// Zoom factor for a wheel event's angleDelta.y, given the step in
// percent per wheel notch (angleDelta 120). Proportional to the delta,
// so trackpads (many small deltas) zoom smoothly too.
function wheelFactor(angleDeltaY, stepPercent) {
    return Math.pow(1 + stepPercent / 100, angleDeltaY / 120)
}
