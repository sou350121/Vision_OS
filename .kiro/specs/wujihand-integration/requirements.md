# Requirements Document

## Introduction

This document specifies the requirements for integrating VisionOS (a MediaPipe-based hand tracking dashboard) with the WujiHand dexterous robotic hand hardware. The system enables real-time teleoperation of a physical robotic hand by tracking a human operator's hand movements via webcam.

## Glossary

- **VisionOS**: The browser-based hand tracking dashboard using MediaPipe and Three.js
- **WujiHand**: A dexterous robotic hand hardware controlled via the `wujihandpy` SDK
- **Bridge**: The Python WebSocket server (`wuji_bridge.py`) that connects VisionOS to WujiHand hardware
- **Extension_Value**: A 0-100 percentage representing how extended a finger is (100 = fully open, 0 = fully closed)
- **Joint_Target_Position**: The target angle (in radians) for a hardware joint
- **ARM_State**: Boolean flag indicating whether the system is allowed to send motion commands to hardware
- **Telemetry**: Real-time data from the hardware (voltage, joint positions, error codes)
- **Unjam_Sequence**: A recovery procedure to release a mechanically stuck hand

## Requirements

### Requirement 1: WebSocket Communication

**User Story:** As a developer, I want VisionOS and the Bridge to communicate via WebSocket, so that hand tracking data can flow to hardware in real-time.

#### Acceptance Criteria

1. WHEN VisionOS loads, THE VisionOS SHALL attempt to connect to the Bridge WebSocket server at `ws://localhost:8765`
2. WHEN the WebSocket connection is established, THE VisionOS SHALL send a `{"type":"hello"}` message
3. WHEN the Bridge receives a `hello` message, THE Bridge SHALL respond with a `status` message containing hardware state
4. WHEN the WebSocket connection is lost, THE VisionOS SHALL display a disconnected status and attempt reconnection
5. IF the Bridge is not running, THEN THE VisionOS SHALL display "WUJI DISCONNECTED" status

### Requirement 2: Hardware Connection Management

**User Story:** As an operator, I want the Bridge to automatically detect and connect to WujiHand hardware, so that I don't need to manually configure USB connections.

#### Acceptance Criteria

1. WHEN the Bridge starts, THE Bridge SHALL attempt to connect to WujiHand hardware using default USB VID (0x0483)
2. WHEN hardware connection succeeds, THE Bridge SHALL read joint limits (`read_joint_lower_limit`, `read_joint_upper_limit`)
3. WHEN hardware connection succeeds, THE Bridge SHALL read device info (firmware version, handedness)
4. IF hardware connection fails, THEN THE Bridge SHALL retry with exponential backoff (starting at 3s, max 30s)
5. WHEN hardware is connected, THE Bridge SHALL broadcast `{"type":"status","has_hardware":true}` to all clients
6. IF Windows driver is incompatible (usbser.inf), THEN THE Bridge SHALL provide an actionable error message suggesting Zadig

### Requirement 3: Finger Extension Mapping

**User Story:** As an operator, I want my finger movements to be accurately mapped to the robotic hand, so that the robot mimics my hand pose.

#### Acceptance Criteria

1. WHEN VisionOS detects a hand, THE VisionOS SHALL compute Extension_Value (0-100) for each of the 5 fingers using joint angle calculations
2. WHEN VisionOS computes finger extensions, THE VisionOS SHALL send `{"type":"hand_data","side":"left|right","extensions":{...}}` to the Bridge
3. WHEN the Bridge receives hand_data and ARM_State is true, THE Bridge SHALL map Extension_Value to Joint_Target_Position using hardware joint limits
4. THE Bridge SHALL apply configurable finger weights to distribute curl across 4 joints per finger
5. THE Bridge SHALL clamp Joint_Target_Position within hardware min/max limits
6. THE Bridge SHALL support configurable `open_pose` and `closed_pose` modes ("lower", "upper", "auto") for inverted hardware

### Requirement 4: Safety - ARM/DISARM Control

**User Story:** As an operator, I want explicit control over when the robot moves, so that I can prevent accidental motion and ensure safety.

#### Acceptance Criteria

1. WHEN VisionOS loads, THE VisionOS SHALL initialize with ARM_State = false (DISARMED)
2. WHEN the operator clicks the ARM button, THE VisionOS SHALL send `{"type":"arm","enabled":true}` to the Bridge
3. WHEN the Bridge receives arm=true, THE Bridge SHALL enable hardware joints and begin accepting motion commands
4. WHEN the Bridge receives arm=false, THE Bridge SHALL disable hardware joints and stop motion
5. WHEN ARM_State transitions to true, THE Bridge SHALL first execute a reset-to-OPEN sequence before accepting tracking commands
6. THE VisionOS SHALL display current ARM_State prominently in the UI header

### Requirement 5: Safety - Motion Limiting

**User Story:** As an operator, I want the system to limit motion speed and grip strength, so that the hardware doesn't damage itself or surroundings.

#### Acceptance Criteria

1. THE Bridge SHALL apply a configurable maximum speed limit (default 0.15 rad/s) to all joint movements
2. THE Bridge SHALL apply smoothing (EMA filter) to target positions to reduce jitter
3. THE Bridge SHALL enforce a configurable `max_curl` limit (default 0.70) to prevent full fist closure
4. WHEN no hand_data is received for `watchdog_s` seconds while armed, THE Bridge SHALL automatically open the hand
5. THE Bridge SHALL support configurable current limits (normal: 1000mA, unjam: 500mA)

### Requirement 6: Safety - Unjam Recovery

**User Story:** As an operator, I want recovery mechanisms when the hand gets mechanically stuck, so that I can restore normal operation without manual intervention.

#### Acceptance Criteria

1. WHEN the operator triggers RESET, THE Bridge SHALL execute: disable joints → wait → enable joints → open fingers sequentially (IDX→MID→RNG→PNK→THM)
2. WHEN the operator triggers HARD UNJAM, THE Bridge SHALL reduce current limit before executing the reset sequence
3. IF joint_error_code is non-zero while armed, THEN THE Bridge SHALL automatically trigger an unjam sequence (configurable)
4. THE Bridge SHALL clear joint errors (`write_joint_reset_error`) before and after enable cycles
5. WHEN unjam is active, THE Bridge SHALL use a slower max speed (`unjam_max_speed_rad_s`)

### Requirement 7: Telemetry Display

**User Story:** As an operator, I want to see real-time hardware status, so that I can monitor system health and diagnose issues.

#### Acceptance Criteria

1. THE Bridge SHALL periodically read and broadcast telemetry: input voltage, joint actual positions
2. THE Bridge SHALL include command rate (cmd_hz) and command age (cmd_age_ms) in telemetry
3. THE VisionOS SHALL display telemetry data in a dedicated UI panel
4. THE VisionOS SHALL display connection status (CONNECTED/DISCONNECTED, HW:ON/OFF)
5. THE VisionOS SHALL display any hardware errors from `last_hw_error`

### Requirement 8: Hand Selection

**User Story:** As an operator, I want to choose which tracked hand controls the robot, so that I can use either hand for teleoperation.

#### Acceptance Criteria

1. THE VisionOS SHALL provide LEFT/RIGHT toggle buttons in the UI
2. WHEN LEFT is selected, THE VisionOS SHALL send only left-hand extension data to the Bridge
3. WHEN RIGHT is selected, THE VisionOS SHALL send only right-hand extension data to the Bridge
4. THE VisionOS SHALL persist the hand selection across page reloads (optional)

### Requirement 9: Configuration and Calibration

**User Story:** As a developer, I want to configure mapping parameters via JSON, so that I can adapt the system to different hardware batches.

#### Acceptance Criteria

1. THE Bridge SHALL load configuration from `config/wuji_mapping.json` if present
2. THE configuration SHALL support: `open_pose`, `closed_pose`, `max_curl`, `finger_weights`
3. THE Bridge SHALL support command-line arguments for: `--usb-vid`, `--usb-pid`, `--serial`, `--max-speed`, `--max-curl`, `--dry-run`
4. WHEN `--dry-run` is specified, THE Bridge SHALL simulate hardware without sending actual commands

### Requirement 10: Test Mode

**User Story:** As an operator, I want to test hardware motion without camera tracking, so that I can verify the Bridge-to-hardware link independently.

#### Acceptance Criteria

1. THE VisionOS SHALL provide TEST buttons (OPEN, FIST) that send direct pose commands
2. WHEN OPEN is pressed, THE Bridge SHALL command all fingers to open position
3. WHEN FIST is pressed, THE Bridge SHALL command all fingers to closed position (respecting max_curl)
4. TEST commands SHALL work regardless of camera tracking status
