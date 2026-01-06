# VisionOS - Control Robotic Hand with Webcam

[中文](README_CN.md) | English

<p align="center">
  <img src="docs/assets/cover.jpeg" alt="VISION_OS cover" width="100%" />
</p>

Track hand movements with a regular webcam, optionally control a WujiHand robotic hand in real-time.

## Demo (Real Hardware)

- Click the thumbnail to watch:

[![VISION_OS hardware demo](docs/assets/cover.jpeg)](https://youtu.be/onrclXu-o68)

- Direct file in repo (download/open): `docs/assets/demo1.mp4`

<details>
  <summary>10s GIF preview (high quality)</summary>
  <br/>
  <img src="docs/assets/demo1_10s.gif" alt="VISION_OS hardware demo (10s GIF)" width="100%" />
</details>

## Demo (Web UI)

- UI-only demo recording (download/open): `docs/assets/demo2.mp4`

<details>
  <summary>10s GIF preview (high quality)</summary>
  <br/>
  <img src="docs/assets/demo2_10s.gif" alt="VISION_OS web UI demo (10s GIF)" width="100%" />
</details>

## Technical Architecture

```text
Browser (MediaPipe + Three.js)
  - Hand tracking + finger extensions (0-100)
  - UI / telemetry rendering
        |
        | WebSocket (default ws://localhost:8765)
        v
Python Bridge (wuji_bridge.py)
  - Extension -> joint target mapping
  - Safety: ARM, reset/unjam, watchdog
        |
        | USB (via wujihandpy)
        v
WujiHand hardware
```

- **Frontend**: `index.html` + `app.js` (+ `src/fingerExtension.js`)
- **Backend bridge**: `wuji_bridge.py` (WebSocket server)
- **Mapping/config**: `config/wuji_mapping.json` (optional override)
- **Docs**: `docs/TECHNICAL_DETAILS.md`, `docs/WUJI_INTEGRATION.md`

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

## Safety Notice (Hardware)

This project can drive real hardware. **Use at your own risk.** Keep fingers, hair, cables, and objects away from moving parts. Start with low speed/current limits and be ready to unplug power/USB. The authors are not responsible for any injury or hardware damage.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Start Bridge (optional; auto-scans for device)
python wuji_bridge.py --max-speed 2.0

# Start frontend
npm run dev:8080

# Open http://localhost:8080, click ARM to start
```

## Hardware (Optional)

- The hardware bridge depends on **`wujihandpy`** (see `requirements.txt`). If you don't have the device, you can still run the dashboard.
- On Windows, you may need to switch the device driver to **WinUSB** (Zadig). See `docs/WUJI_INTEGRATION.md`.

## Project Structure

```
├── app.js, index.html     # Frontend
├── wuji_bridge.py         # Backend WebSocket + hardware control
├── config/                # Config files (wuji_mapping.json)
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
- `THIRD_PARTY_NOTICES.md` - Third-party licenses and notices

## License

MIT - see `LICENSE`.
