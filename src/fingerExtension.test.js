/**
 * Tests for Finger Extension Calculation
 * 
 * Feature: wujihand-integration
 * 
 * Property-based tests use fast-check to verify correctness properties.
 * Each property test runs minimum 100 iterations.
 */

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { getFingerExtension, getAngle, FINGER_INDICES } from './fingerExtension.js';

// =============================================================================
// Helper: Generate valid landmark objects
// =============================================================================

/**
 * Generate a single landmark point with x, y, z coordinates.
 */
const landmarkArb = fc.record({
    x: fc.float({ min: 0, max: 1, noNaN: true }),
    y: fc.float({ min: 0, max: 1, noNaN: true }),
    z: fc.float({ min: -0.5, max: 0.5, noNaN: true })
});

/**
 * Generate an array of 21 landmarks (MediaPipe hand model).
 */
const landmarksArb = fc.array(landmarkArb, { minLength: 21, maxLength: 21 });

// =============================================================================
// Unit Tests for getAngle
// =============================================================================

describe('getAngle', () => {
    it('should return 180 for collinear points', () => {
        const a = { x: 0, y: 0, z: 0 };
        const b = { x: 1, y: 0, z: 0 };
        const c = { x: 2, y: 0, z: 0 };
        const angle = getAngle(a, b, c);
        expect(angle).toBeCloseTo(180, 1);
    });

    it('should return 90 for perpendicular points', () => {
        const a = { x: 0, y: 0, z: 0 };
        const b = { x: 1, y: 0, z: 0 };
        const c = { x: 1, y: 1, z: 0 };
        const angle = getAngle(a, b, c);
        expect(angle).toBeCloseTo(90, 1);
    });

    it('should handle zero-length vectors gracefully', () => {
        const a = { x: 1, y: 1, z: 1 };
        const b = { x: 1, y: 1, z: 1 };
        const c = { x: 2, y: 2, z: 2 };
        const angle = getAngle(a, b, c);
        expect(angle).toBe(180);
    });
});

// =============================================================================
// Unit Tests for getFingerExtension
// =============================================================================

describe('getFingerExtension', () => {
    it('should return value between 0 and 100 for index finger', () => {
        // Create landmarks with a moderately extended index finger
        const landmarks = createMockLandmarks();
        const ext = getFingerExtension(landmarks, FINGER_INDICES.index);
        expect(ext).toBeGreaterThanOrEqual(0);
        expect(ext).toBeLessThanOrEqual(100);
    });

    it('should return value between 0 and 100 for thumb', () => {
        const landmarks = createMockLandmarks();
        const ext = getFingerExtension(landmarks, FINGER_INDICES.thumb);
        expect(ext).toBeGreaterThanOrEqual(0);
        expect(ext).toBeLessThanOrEqual(100);
    });

    it('should return higher value for straight finger', () => {
        // Straight finger landmarks (angles near 180)
        const straightLandmarks = createStraightFingerLandmarks();
        const ext = getFingerExtension(straightLandmarks, FINGER_INDICES.index);
        expect(ext).toBeGreaterThan(50);
    });

    it('should return lower value for bent finger', () => {
        // Bent finger landmarks (angles near 90)
        const bentLandmarks = createBentFingerLandmarks();
        const ext = getFingerExtension(bentLandmarks, FINGER_INDICES.index);
        expect(ext).toBeLessThan(50);
    });
});

// =============================================================================
// Property Test: Extension Value Range Invariant
// Feature: wujihand-integration, Property 1: Extension Value Range Invariant
// Validates: Requirements 3.1
// =============================================================================

describe('Property 1: Extension Value Range Invariant', () => {
    it('*For any* valid landmarks, extension SHALL be in [0, 100]', () => {
        fc.assert(
            fc.property(landmarksArb, (landmarks) => {
                // Test all fingers
                for (const [name, indices] of Object.entries(FINGER_INDICES)) {
                    const ext = getFingerExtension(landmarks, indices);
                    
                    // Extension must be a finite number
                    if (!Number.isFinite(ext)) {
                        return false;
                    }
                    
                    // Extension must be in [0, 100]
                    if (ext < 0 || ext > 100) {
                        return false;
                    }
                }
                return true;
            }),
            { numRuns: 100 }
        );
    });
});

// =============================================================================
// Helper Functions for Creating Mock Landmarks
// =============================================================================

/**
 * Create mock landmarks with reasonable default positions.
 */
function createMockLandmarks() {
    // Basic hand shape with fingers pointing up
    return [
        { x: 0.5, y: 0.8, z: 0 },    // 0: wrist
        { x: 0.4, y: 0.7, z: 0 },    // 1: thumb_cmc
        { x: 0.35, y: 0.6, z: 0 },   // 2: thumb_mcp
        { x: 0.3, y: 0.5, z: 0 },    // 3: thumb_ip
        { x: 0.25, y: 0.4, z: 0 },   // 4: thumb_tip
        { x: 0.45, y: 0.6, z: 0 },   // 5: index_mcp
        { x: 0.45, y: 0.5, z: 0 },   // 6: index_pip
        { x: 0.45, y: 0.4, z: 0 },   // 7: index_dip
        { x: 0.45, y: 0.3, z: 0 },   // 8: index_tip
        { x: 0.5, y: 0.6, z: 0 },    // 9: middle_mcp
        { x: 0.5, y: 0.5, z: 0 },    // 10: middle_pip
        { x: 0.5, y: 0.4, z: 0 },    // 11: middle_dip
        { x: 0.5, y: 0.3, z: 0 },    // 12: middle_tip
        { x: 0.55, y: 0.6, z: 0 },   // 13: ring_mcp
        { x: 0.55, y: 0.5, z: 0 },   // 14: ring_pip
        { x: 0.55, y: 0.4, z: 0 },   // 15: ring_dip
        { x: 0.55, y: 0.3, z: 0 },   // 16: ring_tip
        { x: 0.6, y: 0.65, z: 0 },   // 17: pinky_mcp
        { x: 0.6, y: 0.55, z: 0 },   // 18: pinky_pip
        { x: 0.6, y: 0.45, z: 0 },   // 19: pinky_dip
        { x: 0.6, y: 0.35, z: 0 },   // 20: pinky_tip
    ];
}

/**
 * Create landmarks with straight (extended) index finger.
 */
function createStraightFingerLandmarks() {
    const landmarks = createMockLandmarks();
    // Make index finger straight (collinear points)
    landmarks[5] = { x: 0.45, y: 0.6, z: 0 };   // mcp
    landmarks[6] = { x: 0.45, y: 0.5, z: 0 };   // pip
    landmarks[7] = { x: 0.45, y: 0.4, z: 0 };   // dip
    landmarks[8] = { x: 0.45, y: 0.3, z: 0 };   // tip
    return landmarks;
}

/**
 * Create landmarks with bent (curled) index finger.
 */
function createBentFingerLandmarks() {
    const landmarks = createMockLandmarks();
    // Make index finger bent (90 degree angles)
    landmarks[5] = { x: 0.45, y: 0.6, z: 0 };   // mcp
    landmarks[6] = { x: 0.45, y: 0.5, z: 0 };   // pip
    landmarks[7] = { x: 0.5, y: 0.5, z: 0 };    // dip (bent)
    landmarks[8] = { x: 0.5, y: 0.55, z: 0 };   // tip (curled back)
    return landmarks;
}
