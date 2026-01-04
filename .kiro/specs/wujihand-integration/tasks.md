# Implementation Plan: WujiHand Integration

## Overview

This implementation plan covers verification, testing, and refinement of the existing VisionOS + WujiHand integration. The core functionality is already implemented in `app.js` (VisionOS) and `wuji_bridge.py` (Bridge). Tasks focus on adding property-based tests to verify correctness properties and ensuring robust error handling.

## Tasks

- [ ] 1. Set up testing infrastructure
  - [ ] 1.1 Add Python testing dependencies (pytest, hypothesis) to requirements.txt
    - Add pytest and hypothesis for property-based testing
    - _Requirements: Testing Strategy_
  - [ ] 1.2 Create test directory structure
    - Create `tests/` directory with `__init__.py`
    - Create `tests/test_bridge.py` for Bridge tests
    - _Requirements: Testing Strategy_

- [ ] 2. Implement Bridge mapping tests
  - [ ] 2.1 Write unit tests for extension-to-joint mapping
    - Test `_compute_target_from_extensions` with known inputs
    - Test boundary values (0, 50, 100)
    - _Requirements: 3.3, 3.4_
  - [ ] 2.2 Write property test for joint clamping invariant
    - **Property 2: Joint Position Clamping Invariant**
    - *For any* extension input, output SHALL be within [min_lim, max_lim]
    - **Validates: Requirements 3.5**
  - [ ] 2.3 Write property test for curl limiting invariant
    - **Property 5: Curl Limiting Invariant**
    - *For any* extension input, effective curl SHALL NOT exceed max_curl
    - **Validates: Requirements 5.3**
  - [ ] 2.4 Write property test for extension mapping correctness
    - **Property 3: Extension Mapping Correctness**
    - *For any* valid extension and calibration, mapping produces correct interpolation
    - **Validates: Requirements 3.3, 3.4, 3.6**

- [ ] 3. Implement Bridge safety filter tests
  - [ ] 3.1 Write unit tests for speed limiting
    - Test `_filter_target` with rapid position changes
    - Verify output rate never exceeds max_speed_rad_s
    - _Requirements: 5.1_
  - [ ] 3.2 Write property test for speed limiting invariant
    - **Property 4: Speed Limiting Invariant**
    - *For any* sequence of targets, rate of change SHALL NOT exceed max_speed × dt
    - **Validates: Requirements 5.1**
  - [ ] 3.3 Write property test for smoothing filter correctness
    - **Property 6: Smoothing Filter Correctness**
    - *For any* sequence of desired targets, output SHALL follow EMA formula
    - **Validates: Requirements 5.2**

- [ ] 4. Checkpoint - Verify Bridge tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Bridge connection tests
  - [ ] 5.1 Write unit tests for exponential backoff
    - Test retry timing after consecutive failures
    - Verify backoff formula: min(3.0 × 1.5^(N-1), 30.0)
    - _Requirements: 2.4_
  - [ ] 5.2 Write property test for exponential backoff timing
    - **Property 9: Exponential Backoff Timing**
    - *For any* N consecutive failures, delay SHALL follow backoff formula
    - **Validates: Requirements 2.4**

- [ ] 6. Implement WebSocket protocol tests
  - [ ] 6.1 Write unit tests for hello-status exchange
    - Test that hello message triggers status response
    - Verify status contains required fields
    - _Requirements: 1.3_
  - [ ] 6.2 Write property test for hello-status round trip
    - **Property 10: Hello-Status Round Trip**
    - *For any* hello message, a status response SHALL be sent
    - **Validates: Requirements 1.3**
  - [ ] 6.3 Write property test for status broadcast
    - **Property 8: Status Broadcast to All Clients**
    - *For any* status change, ALL connected clients SHALL receive update
    - **Validates: Requirements 2.5**

- [ ] 7. Checkpoint - Verify all Bridge tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement VisionOS extension calculation tests
  - [ ] 8.1 Create JavaScript test setup (vitest or jest)
    - Add test runner to package.json
    - Configure for ES modules
    - _Requirements: Testing Strategy_
  - [ ] 8.2 Write unit tests for finger extension calculation
    - Test `getFingerExtension` with mock landmarks
    - Test all 5 fingers
    - _Requirements: 3.1_
  - [ ] 8.3 Write property test for extension value range
    - **Property 1: Extension Value Range Invariant**
    - *For any* valid landmarks, extension SHALL be in [0, 100]
    - **Validates: Requirements 3.1**

- [ ] 9. Implement VisionOS hand selection tests
  - [ ] 9.1 Write unit tests for hand selection filtering
    - Test LEFT selection sends only left-hand data
    - Test RIGHT selection sends only right-hand data
    - _Requirements: 8.2, 8.3_
  - [ ] 9.2 Write property test for hand selection filtering
    - **Property 7: Hand Selection Filtering**
    - *For any* selection state, only selected hand data SHALL be sent
    - **Validates: Requirements 8.2, 8.3**

- [ ] 10. Final checkpoint - Verify all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Run full test suite: `pytest tests/` and `npm test`

## Notes

- All property-based tests are required for comprehensive coverage
- The core implementation already exists in `app.js` and `wuji_bridge.py`
- Property tests use Hypothesis (Python) and fast-check (JavaScript)
- Each property test should run minimum 100 iterations
- Tests should be tagged with: **Feature: wujihand-integration, Property N: [property text]**
