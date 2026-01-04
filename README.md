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
   git clone https://github.com/sou350121/Vision_OS.git
   ```
2. Navigate to the project directory:
   ```bash
   cd Vision_OS
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Run development server:
   ```bash
   npm run dev
   ```

## 🤖 WujiHand Integration (Optional)

This project can stream tracked finger extension data to a **Wuji dexterous hand** via the `wujihandpy` SDK using a local WebSocket bridge.

- **Guide**: See `WUJI_INTEGRATION.md`
- **Mapping config**: copy `wuji_mapping.example.json` → `wuji_mapping.json` (optional)

Quick start (two terminals):

1. Install Python deps (Windows):

```bash
pip install -r requirements.txt
```

2. Start the bridge:

```bash
python wuji_bridge.py
```

Recommended (streaming-safe) mode:

```bash
python wuji_bridge.py --write-mode unchecked --write-timeout 2.0
```

3. Start Vision_OS (recommended port):

```bash
npm run dev:8080
```

4. Open `http://localhost:8080/`, wait for WUJI to show `CONNECTED`, then press **ARM** to enable motion.
   (Vision_OS always starts **DISARMED** for safety.)

### Production Build

To generate an optimized production bundle:
```bash
npm run build
```
The output will be in the `dist/` folder. To preview the build:
```bash
npm run preview
```

## 🎮 Usage

- **2D/3D Toggle**: Use the selector in the upper header to switch between the camera overlay and the immersive 3D view.
- **Hand Positioning**: Hold your hands 0.5m - 1.5m from the webcam for optimal tracking.
- **Gestures**: Perform standard gestures to trigger status changes on the dashboard.

## 📜 License

Created by **Antigravity**. Designed for experimental neural interface prototyping.
