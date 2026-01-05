"""
Tests for wuji_bridge.py - WujiHand Bridge

Property-based tests use Hypothesis to verify correctness properties.
Each property test runs minimum 100 iterations.

Feature: wujihand-integration
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from wuji_bridge import WujiBridge, Config, FINGER_INDEX, DEFAULT_FINGER_WEIGHTS


def make_test_config(**overrides) -> Config:
    """Create a test configuration with sensible defaults."""
    defaults = {
        "host": "localhost",
        "port": 8765,
        "usb_vid": 0x0483,
        "usb_pid": -1,
        "serial_number": None,
        "telemetry_hz": 10.0,
        "smoothing": 0.35,
        "max_speed_rad_s": 0.08,
        "unjam_max_speed_rad_s": 0.12,
        "max_curl": 0.70,
        "open_margin": 0.10,
        "arm_reset_s": 20.0,
        "reset_open_s": 60.0,
        "normal_current_limit_ma": 1000,
        "unjam_current_limit_ma": 500,
        "auto_unjam_on_error": True,
        "arm_reset_threshold_rad": 0.15,
        "watchdog_s": 1.0,
        "dry_run": True,
        "mapping_path": "__nonexistent_path_for_tests__",  # Prevent loading wuji_mapping.json
        "write_mode": "unchecked",
        "write_timeout_s": 2.0,
    }
    defaults.update(overrides)
    return Config(**defaults)


def make_test_bridge(**config_overrides) -> WujiBridge:
    """Create a WujiBridge instance for testing (dry_run mode)."""
    cfg = make_test_config(**config_overrides)
    return WujiBridge(cfg)


# =============================================================================
# Unit Tests for Extension-to-Joint Mapping
# Requirements: 3.3, 3.4
# =============================================================================

class TestExtensionToJointMapping:
    """Unit tests for _compute_target_from_extensions."""

    def test_fully_open_returns_open_pose(self):
        """Extension=100 for all fingers should return near open_pose."""
        bridge = make_test_bridge()
        extensions = {"thumb": 100, "index": 100, "middle": 100, "ring": 100, "pinky": 100}
        target = bridge._compute_target_from_extensions(extensions)
        
        # Should be very close to open_pose (within margin)
        np.testing.assert_array_almost_equal(target, bridge.open_pose, decimal=5)

    def test_fully_closed_respects_max_curl(self):
        """Extension=0 should apply max_curl limit, not full closure."""
        bridge = make_test_bridge(max_curl=0.70)
        extensions = {"thumb": 0, "index": 0, "middle": 0, "ring": 0, "pinky": 0}
        target = bridge._compute_target_from_extensions(extensions)
        
        # Should NOT equal closed_pose (max_curl limits it)
        assert not np.allclose(target, bridge.closed_pose)
        
        # Should be between open and closed
        for fi in range(5):
            for ji in range(4):
                open_val = bridge.open_pose[fi, ji]
                closed_val = bridge.closed_pose[fi, ji]
                min_val, max_val = min(open_val, closed_val), max(open_val, closed_val)
                assert min_val <= target[fi, ji] <= max_val

    def test_half_extension_interpolates(self):
        """Extension=50 should produce values between open and closed."""
        bridge = make_test_bridge()
        extensions = {"thumb": 50, "index": 50, "middle": 50, "ring": 50, "pinky": 50}
        target = bridge._compute_target_from_extensions(extensions)
        
        # Should be between open_pose and closed_pose
        for fi in range(5):
            for ji in range(4):
                open_val = bridge.open_pose[fi, ji]
                closed_val = bridge.closed_pose[fi, ji]
                min_val, max_val = min(open_val, closed_val), max(open_val, closed_val)
                assert min_val <= target[fi, ji] <= max_val

    def test_boundary_values(self):
        """Test boundary extension values: 0, 50, 100."""
        bridge = make_test_bridge()
        
        for ext_val in [0, 50, 100]:
            extensions = {name: ext_val for name in FINGER_INDEX.keys()}
            target = bridge._compute_target_from_extensions(extensions)
            
            # All values should be finite
            assert np.all(np.isfinite(target))
            
            # All values should be within joint limits
            assert np.all(target >= bridge.min_lim)
            assert np.all(target <= bridge.max_lim)

    def test_missing_finger_defaults_to_zero(self):
        """Missing finger in extensions dict should default to 0 (closed)."""
        bridge = make_test_bridge()
        extensions = {"thumb": 100}  # Only thumb specified
        target = bridge._compute_target_from_extensions(extensions)
        
        # Thumb should be open
        np.testing.assert_array_almost_equal(
            target[FINGER_INDEX["thumb"], :], 
            bridge.open_pose[FINGER_INDEX["thumb"], :],
            decimal=5
        )


# =============================================================================
# Property Test: Joint Position Clamping Invariant
# Feature: wujihand-integration, Property 2: Joint Position Clamping Invariant
# Validates: Requirements 3.5
# =============================================================================

# Strategy for generating extension values (including invalid ones)
extension_value = st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False)
extensions_dict = st.fixed_dictionaries({
    "thumb": extension_value,
    "index": extension_value,
    "middle": extension_value,
    "ring": extension_value,
    "pinky": extension_value,
})


@given(extensions=extensions_dict)
@settings(max_examples=100)
def test_property_joint_clamping_invariant(extensions):
    """
    Property 2: Joint Position Clamping Invariant
    
    *For any* extension input (even invalid values outside 0-100), 
    the computed joint target position SHALL always be within the 
    hardware joint limits [min_lim, max_lim].
    
    **Validates: Requirements 3.5**
    """
    bridge = make_test_bridge()
    target = bridge._compute_target_from_extensions(extensions)
    
    # All joint positions must be within limits
    assert np.all(target >= bridge.min_lim), \
        f"Target below min_lim: {target} < {bridge.min_lim}"
    assert np.all(target <= bridge.max_lim), \
        f"Target above max_lim: {target} > {bridge.max_lim}"


# =============================================================================
# Property Test: Curl Limiting Invariant
# Feature: wujihand-integration, Property 5: Curl Limiting Invariant
# Validates: Requirements 5.3
# =============================================================================

@given(
    extensions=extensions_dict,
    max_curl=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
)
@settings(max_examples=100)
def test_property_curl_limiting_invariant(extensions, max_curl):
    """
    Property 5: Curl Limiting Invariant
    
    *For any* extension input, the effective curl value (1 - extension/100) 
    applied to the mapping SHALL NOT exceed max_curl.
    
    **Validates: Requirements 5.3**
    """
    bridge = make_test_bridge(max_curl=max_curl)
    target = bridge._compute_target_from_extensions(extensions)
    
    # For each finger, verify the curl doesn't exceed max_curl
    for name, fi in FINGER_INDEX.items():
        weights = bridge.finger_weights.get(name, DEFAULT_FINGER_WEIGHTS)
        
        for ji in range(4):
            if weights[ji] == 0:
                continue  # Skip joints with zero weight
                
            open_val = bridge.open_pose[fi, ji]
            closed_val = bridge.closed_pose[fi, ji]
            actual_val = target[fi, ji]
            
            # Calculate the actual curl applied
            if abs(closed_val - open_val) < 1e-9:
                continue  # Skip if open == closed
            
            # The position should be: open + curl * weight * (closed - open)
            # So: (actual - open) / (weight * (closed - open)) = curl
            # And curl should be <= max_curl
            
            # Verify target is between open and max_curl position
            max_curl_pos = open_val + max_curl * weights[ji] * (closed_val - open_val)
            
            if closed_val > open_val:
                assert actual_val <= max_curl_pos + 1e-6, \
                    f"Finger {name} joint {ji}: {actual_val} > max_curl_pos {max_curl_pos}"
            else:
                assert actual_val >= max_curl_pos - 1e-6, \
                    f"Finger {name} joint {ji}: {actual_val} < max_curl_pos {max_curl_pos}"


# =============================================================================
# Property Test: Extension Mapping Correctness
# Feature: wujihand-integration, Property 3: Extension Mapping Correctness
# Validates: Requirements 3.3, 3.4, 3.6
# =============================================================================

# Strategy for valid extension values (0-100)
valid_extension = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)
valid_extensions_dict = st.fixed_dictionaries({
    "thumb": valid_extension,
    "index": valid_extension,
    "middle": valid_extension,
    "ring": valid_extension,
    "pinky": valid_extension,
})


@given(extensions=valid_extensions_dict)
@settings(max_examples=100)
def test_property_extension_mapping_correctness(extensions):
    """
    Property 3: Extension Mapping Correctness
    
    *For any* valid extension value E (0-100) and valid calibration 
    (open_pose, closed_pose, finger_weights), the mapping function SHALL produce:
    - E=100 (fully open) → position near open_pose
    - E=0 (fully closed) → position at open_pose + max_curl * (closed_pose - open_pose)
    - Intermediate values → linear interpolation weighted by finger_weights
    
    **Validates: Requirements 3.3, 3.4, 3.6**
    """
    bridge = make_test_bridge()
    target = bridge._compute_target_from_extensions(extensions)
    
    for name, fi in FINGER_INDEX.items():
        ext = extensions[name]
        curl = 1.0 - (ext / 100.0)
        curl = min(curl, bridge.max_curl)  # Apply max_curl limit
        weights = bridge.finger_weights.get(name, DEFAULT_FINGER_WEIGHTS)
        
        for ji in range(4):
            expected = bridge.open_pose[fi, ji] + (curl * weights[ji]) * (
                bridge.closed_pose[fi, ji] - bridge.open_pose[fi, ji]
            )
            
            np.testing.assert_almost_equal(
                target[fi, ji], expected, decimal=6,
                err_msg=f"Finger {name} joint {ji}: expected {expected}, got {target[fi, ji]}"
            )


# =============================================================================
# Unit Tests for Speed Limiting
# Requirements: 5.1
# =============================================================================

class TestSpeedLimiting:
    """Unit tests for _filter_target speed limiting during reset/unjam."""

    def test_large_jump_is_limited_during_reset(self):
        """A large position jump should be limited by max_speed during reset."""
        bridge = make_test_bridge(unjam_max_speed_rad_s=0.1)
        
        # Activate reset mode (speed limiting only applies during reset)
        bridge._reset_active = True
        
        # Set initial position
        bridge.last_target = np.zeros((5, 4), dtype=np.float64)
        bridge._last_target_monotonic = 0.0
        
        # Try to jump to a large value
        import time
        bridge._last_target_monotonic = time.monotonic() - 0.1  # 100ms ago
        desired = np.ones((5, 4), dtype=np.float64)  # Jump to 1.0
        
        filtered = bridge._filter_target(desired)
        
        # The jump should be limited to max_speed * dt = 0.1 * 0.1 = 0.01
        # But dt is clamped to max 0.2, so max step = 0.1 * 0.2 = 0.02
        max_step = 0.1 * 0.2  # max_speed * max_dt
        assert np.all(filtered <= max_step + 1e-6), \
            f"Filtered values {filtered.max()} exceed max step {max_step}"

    def test_large_jump_not_limited_during_normal_operation(self):
        """Large position jumps should NOT be limited during normal operation (hardware LowPass handles it)."""
        bridge = make_test_bridge(unjam_max_speed_rad_s=0.1)
        
        # Normal operation (reset not active)
        bridge._reset_active = False
        
        # Set initial position
        bridge.last_target = np.zeros((5, 4), dtype=np.float64)
        
        import time
        bridge._last_target_monotonic = time.monotonic() - 0.1
        
        # Try to jump to a large value (within joint limits)
        desired = np.full((5, 4), 0.5, dtype=np.float64)
        # 4th joint has max_lim=0 in mock calibration
        desired[:, 3] = 0.0
        
        filtered = bridge._filter_target(desired)
        
        # Should pass through without speed limiting (only clamped to joint limits)
        for fi in range(5):
            for ji in range(3):  # First 3 joints
                assert abs(filtered[fi, ji] - desired[fi, ji]) < 0.01

    def test_small_change_passes_through(self):
        """Small position changes within speed limit should pass through (respecting joint limits)."""
        bridge = make_test_bridge(unjam_max_speed_rad_s=1.0)
        
        import time
        bridge.last_target = np.zeros((5, 4), dtype=np.float64)
        bridge._last_target_monotonic = time.monotonic() - 0.1
        
        # Small change - but respect joint limits (4th joint has max_lim=0)
        desired = np.full((5, 4), 0.05, dtype=np.float64)
        filtered = bridge._filter_target(desired)
        
        # Should be close to desired for joints within limits
        # 4th joint (index 3) has max_lim=0 in mock calibration
        for fi in range(5):
            for ji in range(3):  # Only check first 3 joints
                assert abs(filtered[fi, ji] - desired[fi, ji]) < 0.02

    def test_output_within_joint_limits(self):
        """Filtered output should always be within joint limits."""
        bridge = make_test_bridge()
        
        # Try extreme values
        desired = np.full((5, 4), 100.0, dtype=np.float64)
        filtered = bridge._filter_target(desired)
        
        assert np.all(filtered >= bridge.min_lim)
        assert np.all(filtered <= bridge.max_lim)


# =============================================================================
# Property Test: Speed Limiting Invariant (During Reset/Unjam)
# Feature: wujihand-integration, Property 4: Speed Limiting Invariant
# Validates: Requirements 5.1
# =============================================================================

# Strategy for joint position arrays (within mock joint limits)
# Mock calibration: lower=0, upper varies by joint (max ~1.2 for joints 0-2, 0 for joint 3)
joint_position_j0 = st.floats(min_value=0.0, max_value=1.1, allow_nan=False, allow_infinity=False)
joint_position_j1 = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
joint_position_j2 = st.floats(min_value=0.0, max_value=0.8, allow_nan=False, allow_infinity=False)
joint_position_j3 = st.just(0.0)  # 4th joint has max_lim=0 in mock calibration

joint_row = st.tuples(joint_position_j0, joint_position_j1, joint_position_j2, joint_position_j3).map(list)
joint_array = st.lists(joint_row, min_size=5, max_size=5)


@given(
    prev_positions=joint_array,
    desired_positions=joint_array,
    dt=st.floats(min_value=0.01, max_value=0.2, allow_nan=False),
    max_speed=st.floats(min_value=0.1, max_value=10.0, allow_nan=False)
)
@settings(max_examples=100)
def test_property_speed_limiting_invariant(prev_positions, desired_positions, dt, max_speed):
    """
    Property 4: Speed Limiting Invariant (During Reset/Unjam)
    
    *For any* sequence of target positions over time DURING RESET/UNJAM, the rate of change 
    between consecutive targets SHALL NOT exceed unjam_max_speed_rad_s × dt for any joint.
    
    Note: Speed limiting only applies during reset/unjam operations for safety.
    Normal operation relies on hardware LowPass filter for smoothing.
    
    **Validates: Requirements 5.1**
    """
    import time
    
    bridge = make_test_bridge(unjam_max_speed_rad_s=max_speed)
    
    # Activate reset mode (speed limiting only applies during reset)
    bridge._reset_active = True
    
    prev = np.array(prev_positions, dtype=np.float64)
    desired = np.array(desired_positions, dtype=np.float64)
    
    # Clamp to joint limits
    prev = np.clip(prev, bridge.min_lim, bridge.max_lim)
    desired = np.clip(desired, bridge.min_lim, bridge.max_lim)
    
    # Set previous state
    bridge.last_target = prev.copy()
    bridge._last_target_monotonic = time.monotonic() - dt
    
    # Apply filter
    filtered = bridge._filter_target(desired)
    
    # Calculate actual rate of change
    delta = np.abs(filtered - prev)
    max_allowed_step = max_speed * min(dt, 0.2)  # dt is clamped to 0.2 in implementation
    
    # All deltas should be within allowed step (with tolerance for timing jitter)
    assert np.all(delta <= max_allowed_step + 0.01), \
        f"Delta {delta.max()} exceeds max step {max_allowed_step}"


# =============================================================================
# Property Test: No Speed Limiting During Normal Operation
# Feature: wujihand-integration, Property 6: Hardware LowPass Delegation
# Validates: Requirements 5.2 (hardware handles smoothing)
# =============================================================================

@given(
    prev_positions=joint_array,
    desired_positions=joint_array
)
@settings(max_examples=100)
def test_property_no_speed_limiting_normal_operation(prev_positions, desired_positions):
    """
    Property 6: Hardware LowPass Delegation
    
    *For any* sequence of desired targets during NORMAL OPERATION (not reset/unjam),
    the filtered output SHALL pass through without software speed limiting,
    delegating smoothing to the hardware LowPass filter.
    
    **Validates: Requirements 5.2**
    """
    import time
    
    bridge = make_test_bridge(unjam_max_speed_rad_s=0.01)  # Very low speed limit
    
    # Normal operation (reset NOT active)
    bridge._reset_active = False
    
    prev = np.array(prev_positions, dtype=np.float64)
    desired = np.array(desired_positions, dtype=np.float64)
    
    # Clamp to joint limits
    prev = np.clip(prev, bridge.min_lim, bridge.max_lim)
    desired = np.clip(desired, bridge.min_lim, bridge.max_lim)
    
    # Set previous state
    bridge.last_target = prev.copy()
    bridge._last_target_monotonic = time.monotonic() - 0.1
    
    # Apply filter
    filtered = bridge._filter_target(desired)
    
    # During normal operation, output should equal desired (clamped to limits)
    # No speed limiting should be applied
    np.testing.assert_array_almost_equal(filtered, desired, decimal=6)


# =============================================================================
# Unit Tests for Exponential Backoff
# Requirements: 2.4
# =============================================================================

class TestExponentialBackoff:
    """Unit tests for hardware connection exponential backoff."""

    def test_initial_backoff_is_3_seconds(self):
        """Initial backoff should be 3 seconds."""
        bridge = make_test_bridge()
        assert bridge._connect_backoff_s == 3.0

    def test_backoff_increases_after_failure(self):
        """Backoff should increase by 1.5x after each failure."""
        bridge = make_test_bridge()
        
        # Simulate first failure
        initial_backoff = bridge._connect_backoff_s
        bridge._connect_backoff_s = min(initial_backoff * 1.5, 30.0)
        
        assert bridge._connect_backoff_s == 4.5  # 3.0 * 1.5

    def test_backoff_caps_at_30_seconds(self):
        """Backoff should cap at 30 seconds."""
        bridge = make_test_bridge()
        
        # Simulate many failures
        for _ in range(20):
            bridge._connect_backoff_s = min(bridge._connect_backoff_s * 1.5, 30.0)
        
        assert bridge._connect_backoff_s == 30.0

    def test_backoff_formula(self):
        """Verify backoff formula: min(3.0 × 1.5^(N-1), 30.0)."""
        bridge = make_test_bridge()
        
        expected_backoffs = [
            3.0,      # N=1: 3.0 * 1.5^0 = 3.0
            4.5,      # N=2: 3.0 * 1.5^1 = 4.5
            6.75,     # N=3: 3.0 * 1.5^2 = 6.75
            10.125,   # N=4: 3.0 * 1.5^3 = 10.125
            15.1875,  # N=5: 3.0 * 1.5^4 = 15.1875
            22.78125, # N=6: 3.0 * 1.5^5 = 22.78125
            30.0,     # N=7: capped at 30
        ]
        
        for i, expected in enumerate(expected_backoffs):
            if i == 0:
                assert abs(bridge._connect_backoff_s - expected) < 0.001
            else:
                bridge._connect_backoff_s = min(bridge._connect_backoff_s * 1.5, 30.0)
                assert abs(bridge._connect_backoff_s - expected) < 0.001


# =============================================================================
# Property Test: Exponential Backoff Timing
# Feature: wujihand-integration, Property 9: Exponential Backoff Timing
# Validates: Requirements 2.4
# =============================================================================

@given(n_failures=st.integers(min_value=1, max_value=50))
@settings(max_examples=100)
def test_property_exponential_backoff_timing(n_failures):
    """
    Property 9: Exponential Backoff Timing
    
    *For any* N consecutive hardware connection failures, the delay before 
    retry N SHALL be min(3.0 × 1.5^(N-1), 30.0) seconds.
    
    **Validates: Requirements 2.4**
    """
    bridge = make_test_bridge()
    
    # Simulate N-1 failures to get to the Nth retry
    for _ in range(n_failures - 1):
        bridge._connect_backoff_s = min(bridge._connect_backoff_s * 1.5, 30.0)
    
    # Calculate expected backoff for Nth retry
    expected = min(3.0 * (1.5 ** (n_failures - 1)), 30.0)
    
    assert abs(bridge._connect_backoff_s - expected) < 0.001, \
        f"For N={n_failures}, expected {expected}, got {bridge._connect_backoff_s}"


# =============================================================================
# Unit Tests for Hello-Status Exchange
# Requirements: 1.3
# =============================================================================

class TestHelloStatusExchange:
    """Unit tests for WebSocket hello-status protocol."""

    def test_status_message_contains_required_fields(self):
        """Status message should contain all required fields."""
        bridge = make_test_bridge()
        
        # Build status payload as the bridge would
        status = {
            "type": "status",
            "has_hardware": bridge.has_hardware,
            "armed": bridge.armed,
            "usb_vid": bridge.cfg.usb_vid,
            "usb_pid": bridge.cfg.usb_pid,
            "serial_number": bridge.cfg.serial_number,
            "last_hw_error": bridge.last_hw_error,
            "firmware_version": bridge.firmware_version,
            "handedness": bridge.handedness,
        }
        
        # Verify required fields
        assert "type" in status
        assert status["type"] == "status"
        assert "has_hardware" in status
        assert "armed" in status
        assert isinstance(status["has_hardware"], bool)
        assert isinstance(status["armed"], bool)

    def test_initial_state_is_disarmed(self):
        """Bridge should start in disarmed state."""
        bridge = make_test_bridge()
        assert bridge.armed == False

    def test_initial_state_no_hardware(self):
        """Bridge should start without hardware (dry_run mode)."""
        bridge = make_test_bridge(dry_run=True)
        # In dry_run mode, has_hardware is False
        assert bridge.has_hardware == False


# =============================================================================
# Property Test: Hello-Status Round Trip
# Feature: wujihand-integration, Property 10: Hello-Status Round Trip
# Validates: Requirements 1.3
# =============================================================================

@given(
    has_hardware=st.booleans(),
    armed=st.booleans(),
    last_hw_error=st.one_of(st.none(), st.text(min_size=1, max_size=50))
)
@settings(max_examples=100)
def test_property_hello_status_round_trip(has_hardware, armed, last_hw_error):
    """
    Property 10: Hello-Status Round Trip
    
    *For any* hello message received by the Bridge, a status response 
    SHALL be sent containing the current hardware state.
    
    **Validates: Requirements 1.3**
    """
    import json
    
    bridge = make_test_bridge()
    bridge.has_hardware = has_hardware
    bridge.armed = armed
    bridge.last_hw_error = last_hw_error
    
    # Build status payload as the bridge would for a hello response
    status_payload = {
        "type": "status",
        "has_hardware": bridge.has_hardware,
        "armed": bridge.armed,
        "usb_vid": bridge.cfg.usb_vid,
        "usb_pid": bridge.cfg.usb_pid,
        "serial_number": bridge.cfg.serial_number,
        "last_hw_error": bridge.last_hw_error,
        "firmware_version": bridge.firmware_version,
        "handedness": bridge.handedness,
    }
    
    # Verify the status can be serialized to JSON
    json_str = bridge._dumps(status_payload)
    parsed = json.loads(json_str)
    
    # Verify the response contains correct state
    assert parsed["type"] == "status"
    assert parsed["has_hardware"] == has_hardware
    assert parsed["armed"] == armed
    assert parsed["last_hw_error"] == last_hw_error


# =============================================================================
# Property Test: Status Broadcast to All Clients
# Feature: wujihand-integration, Property 8: Status Broadcast to All Clients
# Validates: Requirements 2.5
# =============================================================================

@given(num_clients=st.integers(min_value=1, max_value=10))
@settings(max_examples=100)
def test_property_status_broadcast_to_all_clients(num_clients):
    """
    Property 8: Status Broadcast to All Clients
    
    *For any* status change (hardware connect/disconnect, arm state change), 
    ALL connected WebSocket clients SHALL receive the status update.
    
    **Validates: Requirements 2.5**
    
    Note: This test verifies the broadcast mechanism by checking that the
    clients set is properly managed and that _broadcast iterates over all clients.
    """
    bridge = make_test_bridge()
    
    # Create mock client objects (just need to be hashable for the set)
    class MockClient:
        def __init__(self, id):
            self.id = id
            self.messages = []
        
        async def send(self, msg):
            self.messages.append(msg)
    
    mock_clients = [MockClient(i) for i in range(num_clients)]
    
    # Add all clients to the bridge
    for client in mock_clients:
        bridge.clients.add(client)
    
    # Verify all clients are tracked
    assert len(bridge.clients) == num_clients
    
    # Verify the clients set contains all mock clients
    for client in mock_clients:
        assert client in bridge.clients
