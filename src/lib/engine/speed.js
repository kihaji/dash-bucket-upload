/**
 * Exponentially-weighted moving average of transfer speed.
 *
 * Samples arrive as (totalLoadedBytes, timestampMs); the estimator converts
 * deltas to an instantaneous rate and blends it with the running average using
 * a weight derived from the sample spacing, so bursty progress events and slow
 * stalls both converge over roughly `halfLifeMs`.
 */
export function createSpeedEstimator(halfLifeMs = 3000, now = () => Date.now()) {
    let lastLoaded = null;
    let lastTime = null;
    let ewmaBps = 0;

    return {
        /** Feed a new cumulative byte count; returns the current estimate in bytes/sec. */
        update(loadedBytes, timeMs = now()) {
            if (lastTime === null) {
                lastLoaded = loadedBytes;
                lastTime = timeMs;
                return 0;
            }
            const dt = timeMs - lastTime;
            if (dt <= 0) {
                return ewmaBps;
            }
            // Progress can move backwards when a part fails and its in-flight
            // bytes are rolled back; skip the sample but keep the clock current.
            const dBytes = loadedBytes - lastLoaded;
            lastLoaded = loadedBytes;
            lastTime = timeMs;
            if (dBytes < 0) {
                return ewmaBps;
            }
            const instBps = (dBytes / dt) * 1000;
            const alpha = 1 - Math.exp(-dt / halfLifeMs);
            ewmaBps = ewmaBps === 0 ? instBps : ewmaBps + alpha * (instBps - ewmaBps);
            return ewmaBps;
        },
        current() {
            return ewmaBps;
        },
    };
}
