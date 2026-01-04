# Design Document: WujiHand Integration

## Overview

This design describes the architecture for integrating VisionOS (a browser-based hand tracking dashboard) with WujiHand dexterous robotic hand hardware. The system enables real-time teleoperation where a human operator's hand movements, captured via webcam, are mapped to control a physical robotic hand.

The architecture follows a client-server model with three main components:
1. **VisionOS (Browser)**: Captures hand tracking data via MediaPipe, computes finger extensions, and provides the operator UI
2. **Bridge (Python)**: WebSocket server that translates finger extensions to joint commands and manages hardware communication
3. **WujiHand (Hardware)**: The physical dexterous hand controlled via the `wujihandpy` SDK

```
┌─────────────────┐     WebSocket      ┌─────────────────┐      USB       ┌─────────────────┐
│    VisionOS     │◄──────────────────►│     Bridge      │◄──────────────►│    WujiHand     │
│    (Browser)    │   JSON messages    │    (Python)     │   wujihandpy   │   (Hardware)    │
│                 │                    │                 │                │                 │
│ - MediaPipe     │                    │ - Mapping       │                │ - 5 fingers     │
│ - Three.js      │                    │ - Safety        │                │ - 4 joints each │
│ - UI/HUD        │                    │ - Telemetry     │                │ - 20 DOF total  │
└─────────────────┘                    └─────────────────┘                └─────────────────┘
```

## Architecture

### System Flow

1. **Tracking Loop** (30 Hz):
   - MediaPipe detects hand landmarks from webcam
   - VisionOS computes finger extension values (0-100) using joint angle calculations
   - Extension data is sent to Bridge via WebSocket

2. **Control Loop** (Bridge):
   - Receives extension data from VisionOS
   - Maps extensions to joint target positions using hardware calibration
   - Applies safety filters (smoothing, speed limiting, curl limiting)
   - Writes target positions to hardware via `wujihandpy`

3. **Telemetry Loop** (10 Hz):
   - Bridge reads hardware state (voltage, joint positions, errors)
   - Broadcasts telemetry to all connected VisionOS clients

### State Machine

```
                    ┌──────────────┐
                    │  DISARMED    │◄─────────────────┐
                    │  (Safe Idle) │                  │
                    └──────┬───────┘                  │
                           │ ARM button              │ DISARM button
                           ▼                         │
                    ┌──────────────┐                  │
                    │   RESETTING  │                  │
                    │ (Open Hand)  │                  │
                    └──────┬───────┘                  │
                           │ Reset complete          │
                           ▼                         │
                    ┌──────────────┐                  │
                    │    ARMED     │──────────────────┘
                    │ (Tracking)   │
                    └──────┬───────┘
                           │ Error detected
                           ▼
                    ┌──────────────┐
                    │   UNJAMMING  │
                    │ (Recovery)   │
                    └──────────────┘
```

## Components and Interfaces

### VisionOS (Browser) - `app.js`

**Responsibilities:**
- Webcam capture and MediaPipe hand detection
- Finger extension calculation using joint angles
- WebSocket communication with Bridge
- Operator UI (ARM button, hand selection, telemetry display)

**Key Functions:**
- `getFingerExtension(landmarks, fingerIndices)`: Computes 0-100 extension using bone angles
- `classifyGesture(landmarks)`: Identifies gestures using hysteresis thresholds
- `sendHandData(side, extensions)`: Sends extension data to Bridge

**WebSocket Messages Sent:**
```javascript
// Hello (on connect)
{ "type": "hello" }

// Arm control
{ "type": "arm", "enabled": true|false }

// Hand tracking data
{ "type": "hand_data", "side": "left"|"right", "extensions": {
    "thumb": 0-100,
    "index": 0-100,
    "middle": 0-100,
    "ring": 0-100,
    "pinky": 0-100
}}

// Recovery commands
{ "type": "reset_open" }
{ "type": "hard_unjam" }

// Test commands
{ "type": "test_open" }
{ "type": "test_fist" }
```

### Bridge (Python) - `wuji_bridge.py`

**Responsibilities:**
- WebSocket server for VisionOS clients
- Hardware connection management via `wujihandpy`
- Extension-to-joint mapping with calibration
- Safety enforcement (speed limits, curl limits, watchdog)
- Telemetry broadcasting

**Key Classes:**

```python
@dataclass(frozen=True)
class Config:
    host: str                    # WebSocket host (default: "0.0.0.0")
    port: int                    # WebSocket port (default: 8765)
    usb_vid: int                 # USB Vendor ID (default: 0x0483)
    usb_pid: int                 # USB Product ID (default: -1 = any)
    serial_number: Optional[str] # Specific device serial
    telemetry_hz: float          # Telemetry broadcast rate
    smoothing: float             # EMA smoothing factor (0-1)
    max_speed_rad_s: float       # Maximum joint speed
    max_curl: float              # Maximum curl (0=open, 1=closed)
    watchdog_s: float            # Watchdog timeout
    dry_run: bool                # Simulate without hardware

class WujiBridge:
    # State
    hand: Optional[wujihandpy.Hand]  # Hardware handle
    has_hardware: bool               # Hardware connected
    armed: bool                      # Motion enabled
    
    # Calibration
    lower: np.ndarray               # Joint lower limits (5x4)
    upper: np.ndarray               # Joint upper limits (5x4)
    open_pose: np.ndarray           # Open position (5x4)
    closed_pose: np.ndarray         # Closed position (5x4)
    finger_weights: Dict[str, np.ndarray]  # Per-finger joint weights
    
    # Methods
    def connect_hardware(self, force: bool) -> None
    def _compute_target_from_extensions(self, extensions: Dict) -> np.ndarray
    def _filter_target(self, desired: np.ndarray) -> np.ndarray
    def _apply_target(self, desired: np.ndarray) -> None
```

**WebSocket Messages Received:**
```python
# Status response
{ "type": "status", "has_hardware": bool, "armed": bool, 
  "last_hw_error": str|None, "firmware_version": str, "handedness": str }

# Telemetry broadcast
{ "type": "telemetry", "input_voltage": float, 
  "joint_actual_position": [[float]*4]*5, "cmd_hz": float, "cmd_age_ms": int }
```

### Hardware Interface - `wujihandpy`

**Key SDK Methods Used:**
```python
# Connection
Hand(usb_vid, usb_pid, serial_number)

# Calibration reads
read_joint_lower_limit() -> List[List[float]]  # 5x4 radians
read_joint_upper_limit() -> List[List[float]]  # 5x4 radians
read_firmware_version() -> str
read_handedness() -> str  # "left" | "right"

# Control writes
write_joint_enabled(enabled: bool, timeout: float)
write_joint_target_position(positions: np.ndarray, timeout: float)
write_joint_target_position_unchecked(positions: np.ndarray, timeout: float)
write_joint_current_limit(limit_ma: int, timeout: float)
write_joint_reset_error(value: int, timeout: float)

# Telemetry reads
read_input_voltage() -> float
read_joint_actual_position() -> List[List[float]]
read_joint_error_code() -> List[List[int]]
```

## Data Models

### Finger Extension (VisionOS → Bridge)

```typescript
interface HandData {
    type: "hand_data";
    side: "left" | "right";
    timestamp_ms: number;
    extensions: {
        thumb: number;   // 0-100, 100 = fully extended
        index: number;
        middle: number;
        ring: number;
        pinky: number;
    };
}
```

### Joint Target Position (Bridge → Hardware)

```python
# 5 fingers × 4 joints = 20 DOF
# Values in radians, within [lower_limit, upper_limit]
target_position: np.ndarray  # shape (5, 4), dtype float64

# Finger indices
FINGER_INDEX = {
    "thumb": 0,
    "index": 1,
    "middle": 2,
    "ring": 3,
    "pinky": 4,
}
```

### Mapping Configuration

```json
{
    "open_pose": "upper" | "lower" | "auto",
    "closed_pose": "upper" | "lower" | "auto",
    "max_curl": 0.70,
    "finger_weights": {
        "thumb": [1.0, 0.9, 0.6, 0.0],
        "index": [0.7, 1.0, 0.8, 0.0],
        "middle": [0.7, 1.0, 0.8, 0.0],
        "ring": [0.7, 1.0, 0.8, 0.0],
        "pinky": [0.7, 1.0, 0.8, 0.0]
    }
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Extension Value Range Invariant

*For any* hand detected by MediaPipe, the computed extension value for each finger SHALL be in the range [0, 100].

**Validates: Requirements 3.1**

### Property 2: Joint Position Clamping Invariant

*For any* extension input (even invalid values outside 0-100), the computed joint target position SHALL always be within the hardware joint limits [min_lim, max_lim].

**Validates: Requirements 3.5**

### Property 3: Extension Mapping Correctness

*For any* valid extension value E (0-100) and valid calibration (open_pose, closed_pose, finger_weights), the mapping function SHALL produce:
- E=100 (fully open) → position near open_pose
- E=0 (fully closed) → position at open_pose + max_curl * (closed_pose - open_pose)
- Intermediate values → linear interpolation weighted by finger_weights

**Validates: Requirements 3.3, 3.4, 3.6**

### Property 4: Speed Limiting Invariant

*For any* sequence of target positions over time, the rate of change between consecutive targets SHALL NOT exceed max_speed_rad_s × dt for any joint.

**Validates: Requirements 5.1**

### Property 5: Curl Limiting Invariant

*For any* extension input, the effective curl value (1 - extension/100) applied to the mapping SHALL NOT exceed max_curl.

**Validates: Requirements 5.3**

### Property 6: Smoothing Filter Correctness

*For any* sequence of desired targets D[t], the filtered output F[t] SHALL follow the EMA formula:
F[t] = smoothing × D[t] + (1 - smoothing) × F[t-1]

**Validates: Requirements 5.2**

### Property 7: Hand Selection Filtering

*For any* hand selection state (LEFT or RIGHT), the Bridge SHALL only receive hand_data messages for the selected side.

**Validates: Requirements 8.2, 8.3**

### Property 8: Status Broadcast to All Clients

*For any* status change (hardware connect/disconnect, arm state change), ALL connected WebSocket clients SHALL receive the status update.

**Validates: Requirements 2.5**

### Property 9: Exponential Backoff Timing

*For any* sequence of N consecutive hardware connection failures, the delay before retry N SHALL be min(3.0 × 1.5^(N-1), 30.0) seconds.

**Validates: Requirements 2.4**

### Property 10: Hello-Status Round Trip

*For any* hello message received by the Bridge, a status response SHALL be sent containing the current hardware state.

**Validates: Requirements 1.3**

## Error Handling

### Hardware Connection Errors

| Error | Detection | Recovery |
|-------|-----------|----------|
| Device not found | `wujihandpy.Hand()` raises exception | Retry with exponential backoff |
| Wrong USB driver (Windows) | `ERROR_NOT_SUPPORTED` | Display Zadig hint |
| USB disconnect | Read/write timeout | Set `has_hardware=false`, retry |

### Joint Errors

| Error Code | Meaning | Recovery |
|------------|---------|----------|
| 0 | No error | Normal operation |
| 8192 | Overcurrent/jam | Auto-unjam sequence |
| Other | Unknown | Log and continue |

### WebSocket Errors

| Error | Detection | Recovery |
|-------|-----------|----------|
| Connection refused | `onerror` event | Display disconnected, retry |
| Connection lost | `onclose` event | Display disconnected, auto-reconnect |
| Invalid message | JSON parse error | Log and ignore |

## Testing Strategy

### Unit Tests

Unit tests verify specific examples and edge cases:

1. **Extension Calculation**: Test `getFingerExtension` with known landmark positions
2. **Mapping Edge Cases**: Test extension values at boundaries (0, 50, 100)
3. **Config Loading**: Test JSON parsing with valid/invalid configs
4. **CLI Argument Parsing**: Test all command-line options

### Property-Based Tests

Property tests verify universal properties across many generated inputs using a property-based testing library (e.g., Hypothesis for Python, fast-check for JavaScript).

Each property test should:
- Run minimum 100 iterations
- Generate random but valid inputs
- Verify the property holds for all generated cases
- Tag with: **Feature: wujihand-integration, Property N: [property text]**

**Python (Bridge) - using Hypothesis:**
```python
from hypothesis import given, strategies as st

@given(st.floats(min_value=-1000, max_value=1000))
def test_joint_clamping_invariant(extension):
    """Property 2: Joint positions always within limits"""
    # ... test implementation
```

**JavaScript (VisionOS) - using fast-check:**
```javascript
import fc from 'fast-check';

test('Property 1: Extension values in range', () => {
    fc.assert(fc.property(
        fc.array(fc.record({ x: fc.float(), y: fc.float(), z: fc.float() }), { minLength: 21, maxLength: 21 }),
        (landmarks) => {
            const ext = getFingerExtension(landmarks, [5,6,7,8]);
            return ext >= 0 && ext <= 100;
        }
    ), { numRuns: 100 });
});
```

### Integration Tests

1. **WebSocket Protocol**: Test message exchange between mock VisionOS and Bridge
2. **End-to-End (Dry Run)**: Test full flow with `--dry-run` flag
3. **Hardware Mock**: Test Bridge with mocked `wujihandpy.Hand`
