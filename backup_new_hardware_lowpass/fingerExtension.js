/**
 * Finger Extension Calculation Module
 * 
 * Extracted from VisionOS app.js for testability.
 * Computes finger extension values (0-100) from MediaPipe hand landmarks.
 */

/**
 * Calculate angle between three points (in degrees).
 * @param {Object} a - First point {x, y, z}
 * @param {Object} b - Middle point (vertex) {x, y, z}
 * @param {Object} c - Third point {x, y, z}
 * @returns {number} Angle in degrees
 */
export function getAngle(a, b, c) {
    const ab = {
        x: a.x - b.x,
        y: a.y - b.y,
        z: a.z - b.z
    };
    const cb = {
        x: c.x - b.x,
        y: c.y - b.y,
        z: c.z - b.z
    };

    const dot = ab.x * cb.x + ab.y * cb.y + ab.z * cb.z;
    const magAB = Math.sqrt(ab.x * ab.x + ab.y * ab.y + ab.z * ab.z);
    const magCB = Math.sqrt(cb.x * cb.x + cb.y * cb.y + cb.z * cb.z);

    if (magAB === 0 || magCB === 0) return 180;

    const cosAngle = Math.max(-1, Math.min(1, dot / (magAB * magCB)));
    return Math.acos(cosAngle) * (180 / Math.PI);
}

/**
 * Calculate finger extension value (0-100) from landmarks.
 * 
 * @param {Array} landmarks - Array of 21 hand landmarks from MediaPipe
 * @param {Array} indices - Array of 4 landmark indices for the finger [base, pip, dip, tip]
 * @returns {number} Extension value 0-100 (100 = fully extended, 0 = fully curled)
 */
export function getFingerExtension(landmarks, indices) {
    // THUMB: Compound Logic (Structure + Position)
    if (indices[0] === 1) {
        const cmc = landmarks[1];
        const mcpThumb = landmarks[2];
        const ip = landmarks[3];
        const tipThumb = landmarks[4];
        const angleMCP = getAngle(cmc, mcpThumb, ip);
        const angleIP = getAngle(mcpThumb, ip, tipThumb);
        const avgAngle = (angleMCP + angleIP) / 2;
        // Map Angle: 142 (Bent) -> 0%, 175 (Straight) -> 100%
        const angleScore = Math.max(0, Math.min(100, (avgAngle - 142) * 3.0));
        const wrist = landmarks[0];
        const indexMCP = landmarks[5];
        const middleMCP = landmarks[9];
        const handScale = Math.sqrt(
            Math.pow(middleMCP.x - wrist.x, 2) + 
            Math.pow(middleMCP.y - wrist.y, 2) + 
            Math.pow(middleMCP.z - wrist.z, 2)
        );
        const zWeight = 4.0;
        const spread = Math.sqrt(
            Math.pow(tipThumb.x - indexMCP.x, 2) + 
            Math.pow(tipThumb.y - indexMCP.y, 2) + 
            Math.pow((tipThumb.z - indexMCP.z) * zWeight, 2)
        );
        const ratio = spread / (handScale || 1);
        // Map Spread: 0.30 (Tucked) -> 0%, 0.65 (Open) -> 100%
        const spreadScore = Math.max(0, Math.min(100, (ratio - 0.30) * 285));
        return Math.max(0, Math.min(100, Math.min(angleScore, spreadScore)));
    }

    // FINGERS: Robust Angle-Based Check (Straightness)
    // Include MCP (base) joint angle for better tracking
    const wrist = landmarks[0];
    const mcp = landmarks[indices[0]];
    const pip = landmarks[indices[1]];
    const dip = landmarks[indices[2]];
    const tip = landmarks[indices[3]];

    // MCP angle: wrist -> mcp -> pip (base joint flexion)
    const angleMCP = getAngle(wrist, mcp, pip);
    // PIP angle: mcp -> pip -> dip
    const anglePIP = getAngle(mcp, pip, dip);
    // DIP angle: pip -> dip -> tip
    const angleDIP = getAngle(pip, dip, tip);
    
    // Weighted average: MCP contributes more to overall extension
    // MCP (base) is the primary driver of finger curl
    const avgAngle = (angleMCP * 0.4 + anglePIP * 0.35 + angleDIP * 0.25);

    // Map Angle: 100 (Bent) -> 0% to 165 (Straight) -> 100%
    // Adjusted range to account for MCP joint
    return Math.max(0, Math.min(100, (avgAngle - 100) * 1.54));
}

/**
 * Finger landmark indices for MediaPipe hand model.
 */
export const FINGER_INDICES = {
    thumb: [1, 2, 3, 4],
    index: [5, 6, 7, 8],
    middle: [9, 10, 11, 12],
    ring: [13, 14, 15, 16],
    pinky: [17, 18, 19, 20]
};
