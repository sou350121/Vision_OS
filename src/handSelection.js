/**
 * Hand Selection Module
 * 
 * Handles filtering of hand data based on user selection (LEFT/RIGHT).
 */

/**
 * Filter hand data based on selection.
 * 
 * @param {string} selection - Current selection: 'left', 'right', or 'auto'
 * @param {string} handSide - Side of the detected hand: 'left' or 'right'
 * @returns {boolean} True if this hand should be sent to the bridge
 */
export function shouldSendHandData(selection, handSide) {
    if (selection === 'auto') {
        return true;
    }
    return selection === handSide;
}

/**
 * Filter multiple hands based on selection.
 * 
 * @param {string} selection - Current selection: 'left', 'right', or 'auto'
 * @param {Array} hands - Array of hand objects with 'side' property
 * @returns {Array} Filtered array of hands that should be sent
 */
export function filterHandsBySelection(selection, hands) {
    if (selection === 'auto') {
        return hands;
    }
    return hands.filter(hand => hand.side === selection);
}
