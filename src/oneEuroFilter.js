/**
 * One Euro Filter - Adaptive Low-Pass Filter for Human-Computer Interaction
 * 
 * Paper: "1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Interactive Systems"
 * by Géry Casiez, Nicolas Roussel, Daniel Vogel (CHI 2012)
 * 
 * Key insight: Use speed to adapt filter cutoff
 * - Low speed = low cutoff = more smoothing (reduce jitter)
 * - High speed = high cutoff = less smoothing (reduce lag)
 */

class LowPassFilter {
    constructor(alpha = 0.5) {
        this.alpha = alpha;
        this.y = null;
        this.s = null;
    }

    setAlpha(alpha) {
        this.alpha = Math.max(0, Math.min(1, alpha));
    }

    filter(value, timestamp) {
        if (this.y === null) {
            this.y = value;
            this.s = value;
        } else {
            this.s = this.alpha * value + (1 - this.alpha) * this.s;
            this.y = this.s;
        }
        return this.y;
    }

    lastValue() {
        return this.y;
    }

    reset() {
        this.y = null;
        this.s = null;
    }
}

export class OneEuroFilter {
    /**
     * @param {number} freq - Data frequency (Hz), e.g., 30 for 30fps
     * @param {number} minCutoff - Minimum cutoff frequency (Hz), lower = more smoothing at low speed
     * @param {number} beta - Speed coefficient, higher = less lag at high speed
     * @param {number} dCutoff - Cutoff frequency for derivative (Hz)
     */
    constructor(freq = 30, minCutoff = 1.0, beta = 0.007, dCutoff = 1.0) {
        this.freq = freq;
        this.minCutoff = minCutoff;
        this.beta = beta;
        this.dCutoff = dCutoff;
        
        this.x = new LowPassFilter(this._alpha(this.minCutoff));
        this.dx = new LowPassFilter(this._alpha(this.dCutoff));
        this.lastTime = null;
    }

    _alpha(cutoff) {
        const te = 1.0 / this.freq;
        const tau = 1.0 / (2 * Math.PI * cutoff);
        return 1.0 / (1.0 + tau / te);
    }

    filter(value, timestamp = null) {
        // Update frequency estimate if timestamp provided
        if (timestamp !== null && this.lastTime !== null) {
            const dt = (timestamp - this.lastTime) / 1000; // Convert to seconds
            if (dt > 0) {
                this.freq = 1.0 / dt;
            }
        }
        this.lastTime = timestamp;

        // Estimate derivative (speed)
        const prevX = this.x.lastValue();
        let dx = 0;
        if (prevX !== null) {
            dx = (value - prevX) * this.freq;
        }

        // Filter the derivative
        const edx = this.dx.filter(dx, timestamp);

        // Adaptive cutoff based on speed
        const cutoff = this.minCutoff + this.beta * Math.abs(edx);

        // Filter the value with adaptive alpha
        this.x.setAlpha(this._alpha(cutoff));
        return this.x.filter(value, timestamp);
    }

    reset() {
        this.x.reset();
        this.dx.reset();
        this.lastTime = null;
    }
}

/**
 * Multi-channel One Euro Filter for filtering multiple values (e.g., 5 fingers)
 */
export class MultiOneEuroFilter {
    /**
     * @param {string[]} channels - Array of channel names
     * @param {number} freq - Data frequency (Hz)
     * @param {number} minCutoff - Minimum cutoff frequency
     * @param {number} beta - Speed coefficient
     * @param {number} dCutoff - Derivative cutoff
     */
    constructor(channels, freq = 30, minCutoff = 1.0, beta = 0.007, dCutoff = 1.0) {
        this.filters = {};
        for (const ch of channels) {
            this.filters[ch] = new OneEuroFilter(freq, minCutoff, beta, dCutoff);
        }
    }

    filter(values, timestamp = null) {
        const result = {};
        for (const [ch, value] of Object.entries(values)) {
            if (this.filters[ch]) {
                result[ch] = this.filters[ch].filter(value, timestamp);
            } else {
                result[ch] = value;
            }
        }
        return result;
    }

    reset() {
        for (const filter of Object.values(this.filters)) {
            filter.reset();
        }
    }
}

export default OneEuroFilter;
