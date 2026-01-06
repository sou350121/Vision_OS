# AGENT_CONTEXT - VISION_OS

This document provides technical context and design rationales for the **VISION_OS - Neural Interface Terminal** project to assist future development and AI collaboration.

## 🏗️ Architecture Architecture

The application is a single-page terminal designed for real-time telemetry from MediaPipe hand tracking.

### Core Logic (`app.js`)
- **Dual Hand Processing**: The `onHandResults` loop iterates through `multiHandLandmarks` and maps data to specific UI blocks (`left` vs `right`) based on the handedness label.
- **Gesture Detection**: Use the `classifyGesture(landmarks)` function. It employs a **Hysteresis** pattern (via `check` helper) with dual thresholds (Straight > 65, Tucked < 35) to stabilize pose detection.
- **Finger Extension**: calculated via `getFingerExtension` using bone joint angles rather than simple Euclidean distances. This provides robust tracking regardless of hand distance from the camera.
- **3D Mode**: A Three.js implementation. The scene is updated via `update3DHand(landmarks, side)` which maps normalized MP coordinates to a 3D world space.

### CSS Architecture (`style.css`)
- Use a **Cyberpunk Design System**:
  - Primary colors: `#00ff66` (Neon Green), `#00ffff` (Cyan).
  - Background: `#0a0a0a` (OLED Black).
  - Borders: Semi-transparent gradients with subtle glow effects.
- **Layout**: Employs a fixed-column Grid system to maintain dashboard stability during heavy data updates.

## 🧠 Key Design Decisions

1. **Wait-Based Hysteresis**: To prevent "flickering" between similar gestures (like PEACE and THREE), we use a loosened threshold (70 -> 65) and a validation buffer.
2. **Normalized 3D Mapping**: Mediapipe's Z-coordinate is relative. We apply a `scale` factor and Z-boost in `update3DHand` to make depth more visible in the 3D viewport.
3. **Glassmorphism**: HUD elements use `backdrop-filter: blur()` and low-opacity backgrounds to layer data over the live video/3D feeds without obscuring them.

## 🛠️ Internal Tooling & Scripts
- Local development: `npx http-server -p 8080 --cors`.
- Verification: Browser subagent tests ensure 3D scene integrity and dual-hand parity.

## 🤖 WujiHand Integration (Vision_OS ↔ wujihandpy)

This repo includes an optional hardware bridge:
- **Bridge server**: `wuji_bridge.py` (WebSocket, default `ws://localhost:8765`)
- **Diagnostics**: `wuji_diag.py`
- **Runbook**: `WUJI_INTEGRATION.md`

High-level flow:
- Vision_OS (browser) computes finger extension (0–100) per finger.
- It sends selected-hand extension data over WebSocket.
- `wuji_bridge.py` maps extension → joint target angles using the device joint limits and writes via `wujihandpy`.
- The bridge also broadcasts telemetry (VIN + joint actual positions) back to Vision_OS.

## 🚀 Future Roadmap Suggestions
- **Gesture Persistence**: Implement a "Hold Task" mechanism where holding a gesture for 2 seconds triggers a specific terminal command.
- **Bone Smoothing**: Implement a simple EMA (Exponential Moving Average) filter on 3D joint positions to eliminate jitter.
- **VR/AR Pass-through**: Adapt the CSS for transparent backgrounds to support AR headsets.
