# VISION_OS - Neural Interface Terminal

A premium, cyberpunk-inspired hand-tracking dashboard built with MediaPipe and Three.js. This application provide high-precision dual-hand tracking, gesture recognition, and real-time 3D spatial reconstruction.

## 🚀 Key Features

- **Dual-Hand Tracking**: Independent monitoring of Left (Green) and Right (Blue) hand data with real-time HUD (Position, Handedness).
- **High-Precision Sensing**: Angle-based finger extension calculation for 0-100% accuracy.
- **Robust Gesture Library**:
  - `OPEN` (🖐️), `PEACE` (✌️), `THREE` (3️⃣), `OK` (👌), `CALL / 666` (🤙), `THUMBS_UP` (👍).
  - Hysteresis-based stabilization to prevent visual flickering.
- **3D spatial Reconstruction**:
  - Holographic skeletal models with wireframe spheres and glowing cores.
  - Immersive cyberpunk environment with radial scanner grids and background particles.
  - Real-time coordinate mapping from 2D camera space to 3D world space.
- **Biometric Monitoring**:
  - `Neural Heatmap`: Visualizes spatial hand activity and data density.
  - `Analysis Open`: Real-time signal graphing of hand openness levels.
  - `Orientation Compass`: Dynamic heading tracking for hand rotation.

## 🛠️ Technology Stack

- **Core**: HTML5, Vanilla CSS, JavaScript (ES6+).
- **Computer Vision**: [MediaPipe Hands](https://google.github.io/mediapipe/solutions/hands).
- **3D Engine**: [Three.js](https://threejs.org/) (WebGL).
- **Typography**: [JetBrains Mono](https://www.jetbrains.com/lp/mono/) via Google Fonts.

## 🏁 Getting Started

### Prerequisites

- A modern web browser (Chrome/Edge recommended for MediaPipe performance).
- An active webcam.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/vision-os-dashboard.git
   ```
2. Navigate to the project directory:
   ```bash
   cd vision-os-dashboard
   ```
3. Run with a local server (required for MediaPipe assets):
   ```bash
   npx http-server -p 8080 --cors
   ```
4. Open your browser to `http://localhost:8080`.

## 🎮 Usage

- **2D/3D Toggle**: Use the selector in the upper header to switch between the camera overlay and the immersive 3D view.
- **Hand Positioning**: Hold your hands 0.5m - 1.5m from the webcam for optimal tracking.
- **Gestures**: Perform standard gestures to trigger status changes on the dashboard.

## 📜 License

Created by **Antigravity**. Designed for experimental neural interface prototyping.
