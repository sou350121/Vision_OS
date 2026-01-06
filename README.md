# VISION_OS - Control Robotic Hand with Webcam

[中文](README_CN.md) | English

Track hand movements with a regular webcam, optionally control a WujiHand robotic hand in real-time.

## Why This Project?

Started out wanting to build a cool-looking hand tracking dashboard with a cyberpunk aesthetic. Later got a WujiHand and added hardware control. Made some optimizations along the way, got latency down to ~50ms.

## Features

**Hand Tracking (No Hardware Needed)**
- Dual-hand tracking + gesture recognition (OPEN, PEACE, OK, etc.)
- 3D visualization with cyberpunk style

**Robotic Hand Control (With Hardware)**
- 5-finger curl + thumb spread, ~50ms latency
- Auto USB device scanning, plug and play
- Safety: ARM switch, Reset sequence, grip limits

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Start (auto-scans for device)
python wuji_bridge.py --max-speed 2.0
npx http-server -p 8080

# Open http://localhost:8080, click ARM to start
```

## Project Structure

```
├── app.js, index.html     # Frontend
├── wuji_bridge.py         # Backend WebSocket + hardware control
├── wuji_mapping.json      # Config
├── src/                   # Frontend modules
├── tools/                 # Debug tools (unjam, diagnostics, etc.)
├── docs/                  # Documentation
└── tests/                 # Tests
```

## Debug Tools

```bash
python tools/unjam_now.py      # Unjam
python tools/goto_zero.py      # Go to zero position
python tools/wuji_diag.py      # Hardware diagnostics
```

## Documentation

- `docs/PROJECT_SUMMARY.md` - Full project summary (Chinese)
- `docs/WUJI_INTEGRATION.md` - Integration guide

## License

MIT
