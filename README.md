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

## 🤖 WujiHand Integration

This project can stream tracked finger extension data to a **Wuji dexterous hand** via the `wujihandpy` SDK using a local WebSocket bridge.

### Features
- Real-time finger tracking → robotic hand control (~50ms latency)
- 5-finger curl tracking + independent thumb spread control
- Hardware LowPass filtering for smooth motion
- Safety mechanisms: ARM switch, Reset sequence, max_curl limit
- **Auto device scanning**: Automatically detects WujiHand USB devices
- **Relative motion enhancement**: Velocity coherence detection to filter hand shake

### Quick Start

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the bridge (auto-scans for device):
   ```bash
   python wuji_bridge.py --max-speed 2.0
   ```

3. Start Vision_OS:
   ```bash
   npx http-server -p 8080
   ```

4. Open `http://localhost:8080/`, wait for WUJI to show `CONNECTED`, then press **ARM** to enable motion.

### Device Scanning

The bridge automatically scans for WujiHand devices on startup. You can also scan manually:
```bash
python scan_wuji.py           # Scan and print device info
python scan_wuji.py --json    # Output as JSON
python scan_wuji.py --wait    # Wait until device is found
python scan_wuji.py --all     # Show all found devices
```

### Configuration

Copy `wuji_mapping.example.json` → `wuji_mapping.json` to customize:
- `open_pose` / `closed_pose`: Direction mapping (lower/upper)
- `max_curl`: Maximum grip strength (0-1, default 0.85)
- `finger_weights`: Per-joint weight tuning

### Documentation
- **Integration Guide**: `docs/WUJI_INTEGRATION.md`
- **Technical Details**: `docs/TECHNICAL_DETAILS.md`
- **Project Summary**: `docs/PROJECT_SUMMARY.md`

## 📁 Project Structure

```
Vision_OS/
├── app.js                    # Frontend: MediaPipe + WebSocket client
├── index.html                # UI interface
├── style.css                 # Styles
├── wuji_bridge.py            # Backend: WebSocket server + hardware control
├── scan_wuji.py              # USB device auto-scanner
├── wuji_mapping.json         # Config: joint weights and direction
├── wuji_mapping.example.json # Example config template
│
├── src/                      # Frontend modules
│   ├── fingerExtension.js    # Finger extension calculation
│   ├── fingerExtension.test.js
│   ├── handSelection.js      # Hand selection logic
│   ├── handSelection.test.js
│   └── oneEuroFilter.js      # One Euro filter (backup)
│
├── tests/                    # Python tests
│   └── test_bridge.py        # Bridge unit tests
│
├── tools/                    # Hardware debug tools
│   ├── diagnose_and_open.py  # Diagnose and open hand
│   ├── goto_zero.py          # Move to zero position
│   ├── unjam_*.py            # Unjam utilities
│   ├── fix_*.py              # Joint fix utilities
│   └── wuji_diag.py          # Hardware diagnostics
│
├── docs/                     # Documentation
│   ├── PROJECT_SUMMARY.md    # Full project summary (中文)
│   ├── TECHNICAL_DETAILS.md  # Technical implementation details
│   ├── WUJI_INTEGRATION.md   # WujiHand integration guide
│   └── AGENT.md              # AI agent instructions
│
├── backups/                  # Version backups
│   ├── backup_old_with_smoothing/
│   ├── backup_new_hardware_lowpass/
│   └── backup_before_relative_motion/
│
└── v2_dev/                   # V2 development (VLA integration)
    └── README.md
```

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
