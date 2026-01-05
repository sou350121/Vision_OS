/**
 * Tests for Hand Selection Filtering
 * 
 * Feature: wujihand-integration
 * 
 * Property-based tests use fast-check to verify correctness properties.
 * Each property test runs minimum 100 iterations.
 */

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { shouldSendHandData, filterHandsBySelection } from './handSelection.js';

// =============================================================================
// Unit Tests for Hand Selection Filtering
// Requirements: 8.2, 8.3
// =============================================================================

describe('shouldSendHandData', () => {
    it('should return true for left hand when LEFT is selected', () => {
        expect(shouldSendHandData('left', 'left')).toBe(true);
    });

    it('should return false for right hand when LEFT is selected', () => {
        expect(shouldSendHandData('left', 'right')).toBe(false);
    });

    it('should return true for right hand when RIGHT is selected', () => {
        expect(shouldSendHandData('right', 'right')).toBe(true);
    });

    it('should return false for left hand when RIGHT is selected', () => {
        expect(shouldSendHandData('right', 'left')).toBe(false);
    });

    it('should return true for any hand when AUTO is selected', () => {
        expect(shouldSendHandData('auto', 'left')).toBe(true);
        expect(shouldSendHandData('auto', 'right')).toBe(true);
    });
});

describe('filterHandsBySelection', () => {
    it('should filter to only left hands when LEFT is selected', () => {
        const hands = [
            { side: 'left', extensions: {} },
            { side: 'right', extensions: {} }
        ];
        const filtered = filterHandsBySelection('left', hands);
        expect(filtered).toHaveLength(1);
        expect(filtered[0].side).toBe('left');
    });

    it('should filter to only right hands when RIGHT is selected', () => {
        const hands = [
            { side: 'left', extensions: {} },
            { side: 'right', extensions: {} }
        ];
        const filtered = filterHandsBySelection('right', hands);
        expect(filtered).toHaveLength(1);
        expect(filtered[0].side).toBe('right');
    });

    it('should return all hands when AUTO is selected', () => {
        const hands = [
            { side: 'left', extensions: {} },
            { side: 'right', extensions: {} }
        ];
        const filtered = filterHandsBySelection('auto', hands);
        expect(filtered).toHaveLength(2);
    });

    it('should return empty array when no matching hands', () => {
        const hands = [{ side: 'right', extensions: {} }];
        const filtered = filterHandsBySelection('left', hands);
        expect(filtered).toHaveLength(0);
    });
});

// =============================================================================
// Property Test: Hand Selection Filtering
// Feature: wujihand-integration, Property 7: Hand Selection Filtering
// Validates: Requirements 8.2, 8.3
// =============================================================================

describe('Property 7: Hand Selection Filtering', () => {
    // Arbitrary for hand side
    const handSideArb = fc.constantFrom('left', 'right');
    
    // Arbitrary for selection
    const selectionArb = fc.constantFrom('left', 'right', 'auto');
    
    // Arbitrary for hand object
    const handArb = fc.record({
        side: handSideArb,
        extensions: fc.record({
            thumb: fc.float({ min: 0, max: 100, noNaN: true }),
            index: fc.float({ min: 0, max: 100, noNaN: true }),
            middle: fc.float({ min: 0, max: 100, noNaN: true }),
            ring: fc.float({ min: 0, max: 100, noNaN: true }),
            pinky: fc.float({ min: 0, max: 100, noNaN: true })
        })
    });
    
    // Arbitrary for array of hands
    const handsArb = fc.array(handArb, { minLength: 0, maxLength: 5 });

    it('*For any* selection state, only selected hand data SHALL be sent', () => {
        fc.assert(
            fc.property(selectionArb, handsArb, (selection, hands) => {
                const filtered = filterHandsBySelection(selection, hands);
                
                // All filtered hands must match the selection (unless auto)
                for (const hand of filtered) {
                    if (selection !== 'auto' && hand.side !== selection) {
                        return false;
                    }
                }
                
                // If selection is specific (not auto), no wrong-side hands should be included
                if (selection !== 'auto') {
                    const wrongSide = selection === 'left' ? 'right' : 'left';
                    if (filtered.some(h => h.side === wrongSide)) {
                        return false;
                    }
                }
                
                // If selection is auto, all hands should be included
                if (selection === 'auto') {
                    if (filtered.length !== hands.length) {
                        return false;
                    }
                }
                
                return true;
            }),
            { numRuns: 100 }
        );
    });

    it('LEFT selection sends only left-hand data', () => {
        fc.assert(
            fc.property(handsArb, (hands) => {
                const filtered = filterHandsBySelection('left', hands);
                
                // All filtered hands must be left
                return filtered.every(h => h.side === 'left');
            }),
            { numRuns: 100 }
        );
    });

    it('RIGHT selection sends only right-hand data', () => {
        fc.assert(
            fc.property(handsArb, (hands) => {
                const filtered = filterHandsBySelection('right', hands);
                
                // All filtered hands must be right
                return filtered.every(h => h.side === 'right');
            }),
            { numRuns: 100 }
        );
    });
});
