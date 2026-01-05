"""
Wuji Bridge: Vision_OS (browser) <-> wujihandpy (hardware)

- Runs a WebSocket server (default ws://localhost:8765)
- Receives finger extensions (0-100) from Vision_OS
- Maps extensions to joint target positions using the hardware joint limits
- Sends telemetry back to Vision_OS (input voltage + joint actual positions)

Safety:
- Motion is OFF by default. Use the ARM button in Vision_OS (or send {"type":"arm","enabled":true}).
- Includes a simple watchdog: if no command arrives for a while, it opens the hand.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, Optional, Set

import numpy as np
import websockets
import wujihandpy

FINGER_INDEX: Dict[str, int] = {
    "thumb": 0,
    "index": 1,
    "middle": 2,
    "ring": 3,
    "pinky": 4,
}

# Weights for mapping a single "curl" value into 4 joints per finger
# J4 is kept near open by default (weight=0) until we know the exact mechanism for that joint.
DEFAULT_FINGER_WEIGHTS = np.array([0.70, 1.00, 0.80, 0.00], dtype=np.float64)
DEFAULT_THUMB_WEIGHTS = np.array([1.00, 0.90, 0.60, 0.00], dtype=np.float64)


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    usb_vid: int
    usb_pid: int
    serial_number: Optional[str]
    telemetry_hz: float
    smoothing: float
    max_speed_rad_s: float
    unjam_max_speed_rad_s: float
    max_curl: float
    open_margin: float
    arm_reset_s: float
    reset_open_s: float
    normal_current_limit_ma: int
    unjam_current_limit_ma: int
    auto_unjam_on_error: bool
    arm_reset_threshold_rad: float
    watchdog_s: float
    dry_run: bool
    mapping_path: Optional[str]
    write_mode: str
    write_timeout_s: float


class WujiBridge:
    def __init__(self, cfg: Config):
        self.cfg = cfg

        self.clients: Set[Any] = set()

        self.hand: Optional[wujihandpy.Hand] = None
        self.rt_controller: Optional[Any] = None  # Realtime controller for smooth motion
        self.has_hardware: bool = False
        self.armed: bool = False
        self.last_hw_error: Optional[str] = None
        self.firmware_version: Optional[Any] = None
        self.handedness: Optional[Any] = None

        self._connect_backoff_s: float = 3.0
        self._next_connect_try: float = 0.0
        self._windows_driver_hint_done: bool = False
        self._windows_driver_hint: Optional[str] = None

        # Mapping / calibration settings (overridable via JSON)
        # NOTE: This Wuji hand (right palm) boots into a stable OPEN pose. Default OPEN to "upper" and CLOSED to "lower".
        # You can override via `wuji_mapping.json` (`open_pose` / `closed_pose`) if your hardware is inverted.
        # open_pose_mode / closed_pose_mode: "lower" | "upper" | "auto"
        self.open_pose_mode: str = "upper"
        self.closed_pose_mode: str = "lower"
        # Limit how closed the hand is allowed to get (0=open, 1=fully closed). This avoids "perfect fist"
        # which can jam some hardware batches and make it hard to open again.
        self.max_curl: float = float(self.cfg.max_curl)
        self.finger_weights: Dict[str, np.ndarray] = {
            "thumb": DEFAULT_THUMB_WEIGHTS.copy(),
            "index": DEFAULT_FINGER_WEIGHTS.copy(),
            "middle": DEFAULT_FINGER_WEIGHTS.copy(),
            "ring": DEFAULT_FINGER_WEIGHTS.copy(),
            "pinky": DEFAULT_FINGER_WEIGHTS.copy(),
        }

        self.lower: Optional[np.ndarray] = None
        self.upper: Optional[np.ndarray] = None
        self.min_lim: Optional[np.ndarray] = None
        self.max_lim: Optional[np.ndarray] = None
        self.open_pose: Optional[np.ndarray] = None
        self.closed_pose: Optional[np.ndarray] = None
        self._open_margin: float = float(self.cfg.open_margin)

        self.last_target: Optional[np.ndarray] = None
        self._last_target_monotonic: float = time.monotonic()
        # Desired (unfiltered) target that the control loop will chase at a safe rate
        self.desired_target: Optional[np.ndarray] = None
        # When ARM turns on, we first force the hand to OPEN (reset) before accepting tracking commands.
        self._reset_active: bool = False
        # Reset phases:
        # 0=none, 1=IDX, 2=MID, 3=RNG, 4=PNK, 5=THM
        # We open one finger at a time to reduce mechanical interference/jams.
        self._reset_phase: int = 0
        self._reset_start_monotonic: float = 0.0
        self._reset_phase_start_monotonic: float = 0.0
        self._reset_deadline_monotonic: float = 0.0
        self._reset_reason: str = ""
        # Temporarily pause telemetry/control traffic during aggressive disable/enable windows to reduce bus contention.
        self._hw_quiet_until_monotonic: float = 0.0
        # When errors keep re-latching during reset, we can "pulse" enable to re-release mechanics.
        self._reset_pulse_pending_enable: bool = False
        self._reset_pulse_disable_until: float = 0.0
        self._reset_next_pulse_monotonic: float = 0.0
        self._last_reset_error_monotonic: float = 0.0
        self._reset_error_clear_count: int = 0
        self._reset_current_limit_applied: bool = False
        self.last_recv_monotonic: float = 0.0
        self.cmd_times = deque(maxlen=200)
        self.last_cmd_ts_ms: Optional[int] = None
        self._last_rx_log_monotonic: float = 0.0

        # MOCK state (lets you validate end-to-end even when hardware is powered off)
        self.mock_position: np.ndarray = np.zeros((5, 4), dtype=np.float64)

        # Provide a default calibration so mapping works in MOCK mode.
        # When hardware connects, we replace these with real joint limits.
        self._set_mock_calibration()

        # Optional JSON mapping config (weights + open/closed mode)
        self._load_mapping(self.cfg.mapping_path)
        # Clamp mapping-driven safety limits.
        try:
            self.max_curl = float(self.max_curl)
        except Exception:
            self.max_curl = float(self.cfg.max_curl)
        self.max_curl = max(0.0, min(1.0, float(self.max_curl)))
        self._set_open_closed_from_limits(reset_state=True)
        # Default desired target is OPEN (safe idle). Control loop will chase this when armed.
        self.desired_target = None if self.open_pose is None else np.array(self._safe_open_pose(), dtype=np.float64)

    def _safe_open_pose(self, margin: Optional[float] = None) -> np.ndarray:
        """
        Return an OPEN target slightly inside the limit (margin towards CLOSED) to avoid pushing into hard stops.
        margin: 0 -> exact OPEN pose; 0.1 -> 10% towards CLOSED.
        """
        if self.open_pose is None or self.closed_pose is None:
            return np.array(self.open_pose if self.open_pose is not None else np.zeros((5, 4)), dtype=np.float64)
        m = float(self._open_margin if margin is None else margin)
        if not (0.0 <= m <= 0.5):
            m = 0.1
        open_p = np.asarray(self.open_pose, dtype=np.float64)
        closed_p = np.asarray(self.closed_pose, dtype=np.float64)
        tgt = open_p + (m * (closed_p - open_p))
        if self.min_lim is not None and self.max_lim is not None:
            tgt = np.clip(tgt, self.min_lim, self.max_lim)
        return np.asarray(tgt, dtype=np.float64)

    @staticmethod
    def _reset_phase_label(phase: int) -> str:
        return {1: "IDX", 2: "MID", 3: "RNG", 4: "PNK", 5: "THM"}.get(int(phase), "")

    @staticmethod
    def _reset_phase_finger_index(phase: int) -> Optional[int]:
        return {1: 1, 2: 2, 3: 3, 4: 4, 5: 0}.get(int(phase))

    def _set_mock_calibration(self) -> None:
        self.lower = np.zeros((5, 4), dtype=np.float64)
        self.upper = np.array(
            [
                [1.2, 1.0, 0.8, 0.0],  # thumb
                [1.1, 1.2, 1.0, 0.0],  # index
                [1.1, 1.2, 1.0, 0.0],  # middle
                [1.1, 1.2, 1.0, 0.0],  # ring
                [1.1, 1.2, 1.0, 0.0],  # pinky
            ],
            dtype=np.float64,
        )
        self.min_lim = np.minimum(self.lower, self.upper)
        self.max_lim = np.maximum(self.lower, self.upper)
        self.open_pose = np.array(self.lower, dtype=np.float64)
        self.closed_pose = np.array(self.upper, dtype=np.float64)
        self.last_target = np.array(self.open_pose, dtype=np.float64)
        self.mock_position = np.array(self.open_pose, dtype=np.float64)
        self._last_target_monotonic = time.monotonic()

    def _set_open_closed_from_limits(self, reset_state: bool, actual: Optional[np.ndarray] = None) -> None:
        if self.lower is None or self.upper is None:
            return

        lower = np.asarray(self.lower, dtype=np.float64)
        upper = np.asarray(self.upper, dtype=np.float64)

        # Determine (per-joint) which side is "open".
        if self.open_pose_mode == "lower":
            open_is_lower = np.ones_like(lower, dtype=bool)
        elif self.open_pose_mode == "upper":
            open_is_lower = np.zeros_like(lower, dtype=bool)
        else:
            # "auto": choose whichever limit is closer to the current actual joint position.
            if actual is None:
                open_is_lower = np.ones_like(lower, dtype=bool)
            else:
                act = np.asarray(actual, dtype=np.float64)
                open_is_lower = np.abs(act - lower) <= np.abs(act - upper)

        open_src = np.where(open_is_lower, lower, upper)

        # Determine which side is "closed".
        if self.closed_pose_mode == "lower":
            closed_src = lower
        elif self.closed_pose_mode == "upper":
            closed_src = upper
        else:
            # "auto": closed is the opposite limit from open (per joint).
            closed_src = np.where(open_is_lower, upper, lower)

        self.open_pose = np.array(open_src, dtype=np.float64)
        self.closed_pose = np.array(closed_src, dtype=np.float64)

        if reset_state:
            self.last_target = np.array(self.open_pose, dtype=np.float64)
            self.mock_position = np.array(self.open_pose, dtype=np.float64)
            self._last_target_monotonic = time.monotonic()

    def _load_mapping(self, mapping_path: Optional[str]) -> None:
        # Default to `wuji_mapping.json` next to this script if present.
        path: Optional[Path] = None
        if mapping_path:
            path = Path(mapping_path)
        else:
            candidate = Path(__file__).with_name("wuji_mapping.json")
            if candidate.exists():
                path = candidate

        if not path or not path.exists():
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[BRIDGE] Mapping load failed ({path}): {e}", flush=True)
            return

        open_mode = str(data.get("open_pose", self.open_pose_mode)).lower().strip()
        closed_mode = str(data.get("closed_pose", self.closed_pose_mode)).lower().strip()
        if open_mode in ("lower", "upper", "auto"):
            self.open_pose_mode = open_mode
        if closed_mode in ("lower", "upper", "auto"):
            self.closed_pose_mode = closed_mode

        mc = data.get("max_curl", None)
        if isinstance(mc, (int, float)):
            try:
                self.max_curl = float(mc)
            except Exception:
                pass

        fw = data.get("finger_weights") or {}
        if isinstance(fw, dict):
            for name in ("thumb", "index", "middle", "ring", "pinky"):
                arr = fw.get(name)
                if isinstance(arr, (list, tuple)) and len(arr) == 4:
                    try:
                        self.finger_weights[name] = np.array([float(x) for x in arr], dtype=np.float64)
                    except Exception:
                        pass

        print(f"[BRIDGE] Mapping loaded: {path}", flush=True)

    def connect_hardware(self, force: bool = False) -> None:
        now = time.monotonic()
        if (not force) and (now < self._next_connect_try):
            return

        try:
            self.hand = wujihandpy.Hand(
                serial_number=self.cfg.serial_number,
                usb_pid=self.cfg.usb_pid,
                usb_vid=self.cfg.usb_vid,
            )

            # One-time device info
            try:
                self.firmware_version = self.hand.read_firmware_version()
            except Exception:
                self.firmware_version = None

            try:
                self.handedness = self.hand.read_handedness()
            except Exception:
                self.handedness = None

            self.lower = np.array(self.hand.read_joint_lower_limit(), dtype=np.float64)
            self.upper = np.array(self.hand.read_joint_upper_limit(), dtype=np.float64)
            self.min_lim = np.minimum(self.lower, self.upper)
            self.max_lim = np.maximum(self.lower, self.upper)

            # Apply open/closed pose selection (supports inverted devices) using current actual position if possible.
            actual0 = None
            try:
                actual0 = np.array(self.hand.read_joint_actual_position(), dtype=np.float64)
            except Exception:
                actual0 = None
            self._set_open_closed_from_limits(reset_state=True, actual=actual0)

            self.has_hardware = True
            self.last_hw_error = None
            self._windows_driver_hint = None
            self._windows_driver_hint_done = False
            self._connect_backoff_s = 3.0
            self._next_connect_try = now

            # Initialize realtime controller with LowPass filter for smooth motion
            # Higher cutoff = faster response, lower cutoff = smoother but slower
            try:
                lowpass = wujihandpy.filter.LowPass(cutoff_freq=5.0)  # 5 Hz for faster response
                self.rt_controller = self.hand.realtime_controller(enable_upstream=True, filter=lowpass)
                print("[BRIDGE] Realtime controller initialized with LowPass filter (5Hz)", flush=True)
            except Exception as e:
                self.rt_controller = None
                print(f"[BRIDGE] Realtime controller init failed (using fallback): {e}", flush=True)

            # If UI is already armed when hardware comes online, ensure joints are enabled.
            if self.armed:
                try:
                    self.hand.write_joint_enabled_unchecked(True, float(self.cfg.write_timeout_s))
                except Exception as e:
                    self.last_hw_error = f"write_joint_enabled failed: {e}"

            pid_disp = (self.cfg.usb_pid & 0xFFFF) if isinstance(self.cfg.usb_pid, int) else self.cfg.usb_pid
            print(
                f"[BRIDGE] Hardware connected. vid=0x{self.cfg.usb_vid:04x} pid=0x{pid_disp:04x} serial={self.cfg.serial_number or '-'}"
            , flush=True)
        except Exception as e:
            self.hand = None
            self.has_hardware = False
            # If we already know this is a Windows driver binding issue, keep the actionable hint.
            if self._windows_driver_hint:
                self.last_hw_error = self._windows_driver_hint
            else:
                self.last_hw_error = str(e)

            # If Windows bound the device to a serial driver (usbser), libusb/WinUSB open will fail with NOT_SUPPORTED.
            # Add a one-time actionable hint for the UI.
            if not self._windows_driver_hint_done:
                self._windows_driver_hint_done = True
                self._maybe_add_windows_driver_hint()

            # Backoff to avoid spamming attempts/logs when hardware is off.
            delay = float(self._connect_backoff_s)
            self._next_connect_try = now + delay
            self._connect_backoff_s = min(delay * 1.5, 30.0)
            print(f"[BRIDGE] Hardware connect failed: {e} (retry in {delay:.1f}s)", flush=True)

    def _maybe_add_windows_driver_hint(self) -> None:
        try:
            if sys.platform != "win32":
                return

            out = subprocess.check_output(["pnputil", "/enum-devices", "/connected"], text=True, errors="ignore")

            vid_hex = f"{int(self.cfg.usb_vid) & 0xFFFF:04X}"

            if int(self.cfg.usb_pid) != -1:
                pid_hex = f"{int(self.cfg.usb_pid) & 0xFFFF:04X}"
                pat = rf"USB\\VID_{vid_hex}&PID_{pid_hex}\\[0-9A-Za-z]+"
            else:
                pat = rf"USB\\VID_{vid_hex}&PID_[0-9A-Fa-f]{{4}}\\[0-9A-Za-z]+"

            instance_ids = sorted(set(re.findall(pat, out)))
            if not instance_ids:
                return

            for instance_id in instance_ids[:5]:
                try:
                    detail = subprocess.check_output(
                        ["pnputil", "/enum-devices", "/instanceid", instance_id],
                        text=True,
                        errors="ignore",
                    )
                except Exception:
                    continue

                lower = detail.lower()
                if "usbser.inf" in lower:
                    m = re.search(r"\(COM\d+\)", detail, flags=re.IGNORECASE)
                    com = f" {m.group(0)}" if m else ""
                    self._windows_driver_hint = (
                        f"Device uses usbser.inf{com}; wujihandpy needs WinUSB (use Zadig to replace driver) for {instance_id}"
                    )
                    self.last_hw_error = self._windows_driver_hint
                    return
        except Exception:
            # Never break the bridge due to best-effort diagnostics
            return

    def _compute_target_from_extensions(self, extensions: Dict[str, Any]) -> np.ndarray:
        if self.open_pose is None or self.closed_pose is None:
            raise RuntimeError("Hardware not calibrated (joint limits missing).")

        tgt = np.array(self.open_pose, dtype=np.float64)
        max_curl = float(self.max_curl)
        if not (0.0 <= max_curl <= 1.0):
            max_curl = 1.0

        for name, finger_idx in FINGER_INDEX.items():
            raw = extensions.get(name, 0.0)
            try:
                ext = float(raw)
            except Exception:
                ext = 0.0
            ext = max(0.0, min(100.0, ext))

            curl = 1.0 - (ext / 100.0)  # 0=open, 1=closed
            curl = min(curl, max_curl)
            weights = self.finger_weights.get(name, DEFAULT_FINGER_WEIGHTS)

            tgt[finger_idx, :] = self.open_pose[finger_idx, :] + (curl * weights) * (
                self.closed_pose[finger_idx, :] - self.open_pose[finger_idx, :]
            )

        return tgt

    def _filter_target(self, desired: np.ndarray) -> np.ndarray:
        """Apply speed limiting only (smoothing handled by hardware LowPass filter)."""
        tgt = np.asarray(desired, dtype=np.float64)

        if self.min_lim is not None and self.max_lim is not None:
            tgt = np.clip(tgt, self.min_lim, self.max_lim)

        prev = None if self.last_target is None else np.asarray(self.last_target, dtype=np.float64)

        now = time.monotonic()
        dt = now - float(self._last_target_monotonic)
        dt = max(0.0, min(dt, 0.2))  # Clamp dt to avoid jumps

        # Speed limiting only (smoothing is done by hardware LowPass filter)
        max_speed = float(self.cfg.unjam_max_speed_rad_s) if self._reset_active else float(self.cfg.max_speed_rad_s)
        if prev is not None and max_speed > 0.0 and dt > 0.0:
            max_step = max_speed * dt
            if max_step > 0.0:
                delta = np.clip(tgt - prev, -max_step, max_step)
                tgt = prev + delta

        self._last_target_monotonic = now
        self.last_target = np.asarray(tgt, dtype=np.float64)
        return self.last_target

    def _apply_target(self, desired: np.ndarray) -> None:
        """Drive the target slowly/safely towards desired (hardware or MOCK)."""
        tgt = self._filter_target(desired)
        if self.has_hardware and self.hand and (not self.cfg.dry_run):
            self._write_raw(tgt)
        else:
            self.mock_position = np.asarray(tgt, dtype=np.float64)

    def _write_raw(self, target: np.ndarray) -> None:
        if not self.hand or not self.has_hardware:
            return
        if self.cfg.dry_run:
            return

        arr = np.asarray(target, dtype=np.float64)
        
        # Prefer realtime controller for smoother motion (hardware-level filtering)
        if self.rt_controller is not None:
            try:
                self.rt_controller.set_joint_target_position(arr)
                return
            except Exception:
                # Fall back to direct write if realtime controller fails
                pass
        
        # Fallback: direct write
        timeout = float(self.cfg.write_timeout_s)
        if self.cfg.write_mode == "unchecked":
            self.hand.write_joint_target_position_unchecked(arr, timeout)
        else:
            self.hand.write_joint_target_position(arr, timeout)

    @staticmethod
    def _json_default(obj: Any) -> Any:
        # Make pybind/numpy scalar types JSON serializable.
        try:
            if isinstance(obj, np.generic):
                return obj.item()
        except Exception:
            pass

        # Try common numeric casts (pybind scalars often work with int()/float()).
        try:
            return int(obj)
        except Exception:
            pass
        try:
            return float(obj)
        except Exception:
            pass

        return str(obj)

    def _dumps(self, payload: Dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, default=self._json_default)

    def _cmd_hz_1s(self) -> float:
        try:
            now = time.monotonic()
            return float(sum(1 for t in self.cmd_times if (now - t) <= 1.0))
        except Exception:
            return 0.0

    def _cmd_age_ms(self) -> Optional[int]:
        if self.last_cmd_ts_ms is None:
            return None
        try:
            return int(time.time() * 1000) - int(self.last_cmd_ts_ms)
        except Exception:
            return None

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        if not self.clients:
            return
        try:
            msg = self._dumps(payload)
        except Exception as e:
            # Never crash background tasks because of serialization edge cases.
            msg = json.dumps({"type": "error", "error": f"json_serialize_failed: {e}"}, ensure_ascii=False)
        dead = []
        # Iterate on a snapshot to avoid "set changed size during iteration" when clients connect/disconnect mid-send.
        for ws in list(self.clients):
            try:
                await ws.send(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def _send_status(self) -> None:
        await self._broadcast(
            {
                "type": "status",
                "has_hardware": self.has_hardware,
                "armed": self.armed,
                "usb_vid": self.cfg.usb_vid,
                "usb_pid": self.cfg.usb_pid,
                "serial_number": self.cfg.serial_number,
                "last_hw_error": self.last_hw_error,
                "firmware_version": self.firmware_version,
                "handedness": self.handedness,
            }
        )

    async def handle_client(self, websocket) -> None:
        self.clients.add(websocket)
        print(f"[BRIDGE] Client connected: {getattr(websocket, 'remote_address', None)}", flush=True)

        # Initial status
        await websocket.send(
            self._dumps(
                {
                    "type": "status",
                    "has_hardware": self.has_hardware,
                    "armed": self.armed,
                    "usb_vid": self.cfg.usb_vid,
                    "usb_pid": self.cfg.usb_pid,
                    "serial_number": self.cfg.serial_number,
                    "last_hw_error": self.last_hw_error,
                    "firmware_version": self.firmware_version,
                    "handedness": self.handedness,
                },
            )
        )

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except Exception:
                    continue

                mtype = data.get("type")
                if mtype in ("reset_open", "hard_unjam"):
                    print(f"[BRIDGE] RX {mtype}", flush=True)

                if mtype == "hello":
                    await websocket.send(
                        self._dumps(
                            {
                                "type": "status",
                                "has_hardware": self.has_hardware,
                                "armed": self.armed,
                                "usb_vid": self.cfg.usb_vid,
                                "usb_pid": self.cfg.usb_pid,
                                "serial_number": self.cfg.serial_number,
                                "last_hw_error": self.last_hw_error,
                                "firmware_version": self.firmware_version,
                                "handedness": self.handedness,
                            },
                        )
                    )
                    continue

                if mtype == "arm":
                    self.armed = bool(data.get("enabled"))
                    print(f"[BRIDGE] ARM={self.armed}", flush=True)
                    if self.armed and not self.has_hardware:
                        self.connect_hardware(force=True)

                    # On ARM enable: first reset to OPEN for safety, then accept tracking commands.
                    if self.armed:
                        self._reset_active = float(self.cfg.arm_reset_s) > 0.0
                        self._reset_phase = 1 if self._reset_active else 0
                        self._reset_start_monotonic = time.monotonic()
                        self._reset_phase_start_monotonic = self._reset_start_monotonic
                        self._reset_deadline_monotonic = time.monotonic() + float(self.cfg.arm_reset_s)
                        self._reset_reason = "arm" if self._reset_active else ""
                        if self.open_pose is not None:
                            self.desired_target = np.array(self._safe_open_pose(), dtype=np.float64)
                    else:
                        self._reset_active = False
                        self._reset_phase = 0
                        self._reset_start_monotonic = 0.0
                        self._reset_phase_start_monotonic = 0.0
                        self._reset_deadline_monotonic = 0.0
                        self._reset_reason = ""

                    # Enable/disable joints on ARM toggle (required on some devices to actually move)
                    if self.has_hardware and self.hand:
                        try:
                            # Quiet the bus briefly during enable/disable operations.
                            now_m = time.monotonic()
                            self._hw_quiet_until_monotonic = max(float(self._hw_quiet_until_monotonic), now_m + 1.0)

                            # Clear joint errors once, then set enabled state.
                            # Use blocking writes here to avoid protocol framing issues seen on Windows.
                            try:
                                self.hand.write_joint_reset_error(1, float(self.cfg.write_timeout_s))
                            except Exception:
                                pass
                            self.hand.write_joint_enabled(bool(self.armed), float(self.cfg.write_timeout_s))
                        except Exception as e:
                            self.last_hw_error = f"write_joint_enabled failed: {e}"
                    await self._send_status()
                    continue

                if mtype == "connect":
                    if not self.has_hardware:
                        self.connect_hardware(force=True)
                    await self._send_status()
                    continue

                if mtype == "reset_open":
                    # Recovery from a jammed/gripped state:
                    # - briefly disable joints (release torque)
                    # - reset/clear joint errors
                    # - re-enable joints
                    # - force OPEN reset sequence (4 fingers then thumb)
                    now_m = time.monotonic()
                    if self.has_hardware and self.hand:
                        try:
                            # Quiet the bus while we do disable/enable + parameter writes.
                            self._hw_quiet_until_monotonic = max(float(self._hw_quiet_until_monotonic), now_m + 3.2)
                            # Clear errors first (some devices refuse to move while error flags are set).
                            try:
                                self.hand.write_joint_reset_error(1, float(self.cfg.write_timeout_s))
                            except Exception:
                                pass
                            self.hand.write_joint_enabled(False, float(self.cfg.write_timeout_s))
                            # Give mechanics time to relax; too short often fails to unjam.
                            await asyncio.sleep(2.5)
                            self.hand.write_joint_enabled(True, float(self.cfg.write_timeout_s))
                            # Reduce current limit during unjam (mA) to avoid forcing into a jam.
                            try:
                                self.hand.write_joint_current_limit(int(self.cfg.unjam_current_limit_ma), float(self.cfg.write_timeout_s))
                            except Exception:
                                pass
                            # Clear errors again after re-enable.
                            try:
                                self.hand.write_joint_reset_error(1, float(self.cfg.write_timeout_s))
                            except Exception:
                                pass
                        except Exception as e:
                            self.last_hw_error = f"reset enable cycle failed: {e}"
                            await self._send_status()
                            continue

                    self._reset_active = True
                    self._reset_phase = 1
                    self._reset_start_monotonic = now_m
                    self._reset_phase_start_monotonic = now_m
                    self._reset_deadline_monotonic = now_m + float(self.cfg.reset_open_s)
                    self._reset_pulse_pending_enable = False
                    self._reset_pulse_disable_until = 0.0
                    self._reset_next_pulse_monotonic = now_m + 2.0
                    self._last_reset_error_monotonic = 0.0
                    self._reset_error_clear_count = 0
                    self._reset_current_limit_applied = True
                    self._reset_reason = "reset"
                    if self.open_pose is not None:
                        self.desired_target = np.array(self._safe_open_pose(), dtype=np.float64)
                    # keep armed state; user explicitly requested recovery
                    await self._send_status()
                    continue

                if mtype == "hard_unjam":
                    # HARD UNJAM (aggressive recovery):
                    # - optionally set joint_control_mode (write-only; value depends on firmware; default None)
                    # - set lower current limit (mA) during recovery
                    # - disable joints longer (release torque), then enable
                    # - force OPEN reset sequence (4 fingers then thumb)
                    now_m = time.monotonic()
                    mode = data.get("control_mode", None)
                    current_ma = data.get("current_ma", None)
                    disable_s = data.get("disable_s", None)

                    try:
                        mode = None if mode is None else int(mode)
                    except Exception:
                        mode = None
                    try:
                        current_ma = int(current_ma) if current_ma is not None else int(self.cfg.unjam_current_limit_ma)
                    except Exception:
                        current_ma = int(self.cfg.unjam_current_limit_ma)
                    current_ma = max(0, min(3000, int(current_ma)))
                    try:
                        disable_s = float(disable_s) if disable_s is not None else 4.0
                    except Exception:
                        disable_s = 4.0
                    disable_s = max(0.5, min(10.0, float(disable_s)))

                    if self.has_hardware and self.hand:
                        try:
                            # Quiet the bus during aggressive disable/enable window to reduce protocol framing issues.
                            self._hw_quiet_until_monotonic = max(
                                float(self._hw_quiet_until_monotonic), now_m + float(disable_s) + 1.0
                            )
                            # Optional: set control mode if provided (vendor warns not to change under normal circumstances).
                            if mode is not None:
                                try:
                                    self.hand.write_joint_control_mode_unchecked(mode, float(self.cfg.write_timeout_s))
                                except Exception:
                                    pass

                            # Lower current limit during unjam.
                            try:
                                self.hand.write_joint_current_limit(current_ma, float(self.cfg.write_timeout_s))
                            except Exception:
                                pass

                            # Clear errors once before releasing torque.
                            try:
                                self.hand.write_joint_reset_error(1, float(self.cfg.write_timeout_s))
                            except Exception:
                                pass

                            # Longer relax window.
                            self.hand.write_joint_enabled(False, float(self.cfg.write_timeout_s))
                            await asyncio.sleep(disable_s)
                            self.hand.write_joint_enabled(True, float(self.cfg.write_timeout_s))

                            # Clear errors again after enable.
                            try:
                                self.hand.write_joint_reset_error(1, float(self.cfg.write_timeout_s))
                            except Exception:
                                pass
                        except Exception as e:
                            self.last_hw_error = f"hard_unjam prep failed: {e}"
                            await self._send_status()
                            continue

                    self._reset_active = True
                    self._reset_phase = 1
                    self._reset_start_monotonic = now_m
                    self._reset_phase_start_monotonic = now_m
                    # HARD UNJAM may need more time than normal reset (still limited by max speed + low current).
                    self._reset_deadline_monotonic = now_m + max(float(self.cfg.reset_open_s), 90.0)
                    self._reset_pulse_pending_enable = False
                    self._reset_pulse_disable_until = 0.0
                    # Pulse sooner for hard unjam.
                    self._reset_next_pulse_monotonic = now_m + 0.8
                    self._last_reset_error_monotonic = 0.0
                    self._reset_error_clear_count = 0
                    self._reset_current_limit_applied = True
                    self._reset_reason = "hard"
                    if self.open_pose is not None:
                        self.desired_target = np.array(self._safe_open_pose(0.25), dtype=np.float64)
                    await self._send_status()
                    continue

                if mtype == "hand_data":
                    now_m = time.monotonic()
                    self.last_recv_monotonic = now_m
                    self.last_cmd_ts_ms = int(time.time() * 1000)
                    self.cmd_times.append(now_m)

                    # Lightweight debug: log at most once per second
                    if (now_m - self._last_rx_log_monotonic) > 1.0:
                        self._last_rx_log_monotonic = now_m
                        print("[BRIDGE] RX hand_data", flush=True)
                    if not self.armed:
                        continue
                    # During reset window, ignore tracking commands; we are forcing OPEN.
                    if self._reset_active:
                        continue

                    extensions = data.get("extensions") or {}
                    try:
                        target = self._compute_target_from_extensions(extensions)
                        self.desired_target = np.asarray(target, dtype=np.float64)
                    except Exception as e:
                        self.last_hw_error = str(e)
                        print(f"[BRIDGE] write error: {e}", flush=True)
                        await self._send_status()
                    continue

        finally:
            self.clients.discard(websocket)
            print("[BRIDGE] Client disconnected", flush=True)

    async def telemetry_loop(self) -> None:
        interval = 1.0 / max(1.0, float(self.cfg.telemetry_hz))
        while True:
            now_m = time.monotonic()

            # During aggressive disable/enable windows, avoid issuing extra reads/writes.
            if now_m < float(self._hw_quiet_until_monotonic):
                # Still broadcast status/telemetry using cached/mock position if clients are connected.
                if self.clients:
                    await self._broadcast(
                        {
                            "type": "telemetry",
                            "ts": int(time.time() * 1000),
                            "input_voltage": None,
                            "joint_actual_position": (np.asarray(self.mock_position, dtype=np.float64).tolist() if not self.has_hardware else None),
                            "joint_error_code": None,
                            "cmd_hz": self._cmd_hz_1s(),
                            "cmd_age_ms": self._cmd_age_ms(),
                            "reset_active": bool(self._reset_active),
                            "reset_phase": int(self._reset_phase),
                            "reset_label": self._reset_phase_label(int(self._reset_phase)) if self._reset_active else "",
                            "reset_reason": str(self._reset_reason) if self._reset_active else "",
                        }
                    )
                await asyncio.sleep(interval)
                continue

            # Read telemetry (and support reset completion + error-aware recovery)
            vin: Optional[float] = None
            pos_arr: Optional[np.ndarray] = None
            pos_list: Any = None
            err_list: Any = None
            err_has_any: bool = False

            need_hw_read = bool(self.has_hardware and self.hand and (self.clients or self._reset_active))
            if need_hw_read:
                try:
                    vin_raw = self.hand.read_input_voltage()
                    try:
                        vin = float(vin_raw)
                    except Exception:
                        vin = None

                    pos_arr = np.asarray(self.hand.read_joint_actual_position(), dtype=np.float64)
                    pos_list = pos_arr.tolist()
                    try:
                        err_list = np.asarray(self.hand.read_joint_error_code(), dtype=np.int64).tolist()
                        try:
                            err_has_any = any(int(x) != 0 for row in err_list for x in (row if isinstance(row, list) else []))
                        except Exception:
                            err_has_any = False
                    except Exception:
                        err_list = None
                except Exception as e:
                    self.last_hw_error = str(e)
                    await self._send_status()

            # During reset, keep clearing joint errors (some devices re-latch errors while moving)
            if self._reset_active and self.has_hardware and self.hand:
                # NOTE: vendor docs warn not to abuse reset_error in a tight loop. Throttle to <= 1Hz and only when errors exist.
                if err_has_any and self._reset_error_clear_count < 20 and (now_m - float(self._last_reset_error_monotonic)) >= 2.0:
                    try:
                        self.hand.write_joint_reset_error(
                            np.ones((5, 4), dtype=np.uint16), float(self.cfg.write_timeout_s)
                        )
                        self._last_reset_error_monotonic = now_m
                        self._reset_error_clear_count += 1
                    except Exception:
                        pass
                # If errors persist, pulse enable OFF briefly then ON again to help unjam.
                if err_has_any and (now_m >= float(self._reset_next_pulse_monotonic)) and (now_m > float(self._reset_start_monotonic) + 2.0):
                    try:
                        self.hand.write_joint_enabled(False, float(self.cfg.write_timeout_s))
                        self._reset_pulse_pending_enable = True
                        self._reset_pulse_disable_until = now_m + 0.6
                        self._reset_next_pulse_monotonic = now_m + 3.5
                    except Exception:
                        pass
                if self._reset_pulse_pending_enable and (now_m >= float(self._reset_pulse_disable_until)):
                    try:
                        self.hand.write_joint_enabled(True, float(self.cfg.write_timeout_s))
                    except Exception:
                        pass
                    self._reset_pulse_pending_enable = False

            # Auto-unjam: if we are armed, errors present, and not already resetting, enter reset state.
            if (
                (not self._reset_active)
                and bool(self.cfg.auto_unjam_on_error)
                and bool(self.armed)
                and bool(self.has_hardware and self.hand)
                and bool(err_has_any)
            ):
                self._reset_active = True
                self._reset_phase = 1
                self._reset_start_monotonic = now_m
                self._reset_phase_start_monotonic = now_m
                self._reset_deadline_monotonic = now_m + float(self.cfg.reset_open_s)
                self._reset_pulse_pending_enable = False
                self._reset_pulse_disable_until = 0.0
                self._reset_next_pulse_monotonic = now_m + 1.0
                self._last_reset_error_monotonic = 0.0
                self._reset_error_clear_count = 0
                self._reset_current_limit_applied = True
                self._reset_reason = "auto"
                try:
                    self.hand.write_joint_current_limit(int(self.cfg.unjam_current_limit_ma), float(self.cfg.write_timeout_s))
                except Exception:
                    pass
                if self.open_pose is not None:
                    self.desired_target = np.array(self._safe_open_pose(0.25), dtype=np.float64)

            # Control loop: always chase desired_target at a safe rate.
            if self.armed:
                desired: Optional[np.ndarray] = None
                if self.open_pose is not None and self._reset_active:
                    # If any joint reports error during reset, back off further from OPEN hard stops.
                    dyn_margin = 0.25 if err_has_any else None
                    # Reset sequence: open one finger at a time (IDX->MID->RNG->PNK), then THM.
                    desired = np.array(self._safe_open_pose(dyn_margin), dtype=np.float64)
                    active_fi = self._reset_phase_finger_index(self._reset_phase)
                    if active_fi is not None and pos_arr is not None:
                        # Hold all non-active fingers at current positions to avoid interference/jams.
                        hold = np.asarray(pos_arr, dtype=np.float64)
                        for fi in range(5):
                            if fi != active_fi:
                                desired[fi, :] = hold[fi, :]
                    elif active_fi is not None and self.last_target is not None:
                        hold = np.asarray(self.last_target, dtype=np.float64)
                        for fi in range(5):
                            if fi != active_fi:
                                desired[fi, :] = hold[fi, :]
                else:
                    # Watchdog: if armed but no command recently, open the hand (safe default).
                    if self.open_pose is not None and self.cfg.watchdog_s > 0 and (
                        (now_m - self.last_recv_monotonic) > float(self.cfg.watchdog_s)
                    ):
                        desired = self._safe_open_pose()
                    elif self.desired_target is not None:
                        desired = self.desired_target

                if desired is not None:
                    try:
                        self._apply_target(desired)
                    except Exception as e:
                        self.last_hw_error = str(e)
                        await self._send_status()

            # Reset completion: stop forcing OPEN once we are close enough (or timeout).
            if self._reset_active:
                done = False
                if now_m >= float(self._reset_deadline_monotonic):
                    done = True
                elif pos_arr is not None and self.open_pose is not None:
                    try:
                        dyn_margin = 0.25 if err_has_any else None
                        open_pose_arr = np.asarray(self._safe_open_pose(dyn_margin), dtype=np.float64)
                        reset_window_s = max(0.0, float(self._reset_deadline_monotonic) - float(self._reset_start_monotonic))
                        # Per-finger sequencing: advance when the active finger is close enough (or per-finger timeout).
                        if str(self._reset_reason) == "hard":
                            per_finger_timeout_s = 18.0
                        elif str(self._reset_reason) == "arm":
                            per_finger_timeout_s = 10.0
                        else:
                            per_finger_timeout_s = 12.0
                        if 1 <= int(self._reset_phase) <= 4:
                            fi = self._reset_phase_finger_index(self._reset_phase)
                            if fi is not None:
                                err_one = float(np.max(np.abs(pos_arr[fi, :] - open_pose_arr[fi, :])))
                                if err_one <= float(self.cfg.arm_reset_threshold_rad):
                                    self._reset_phase = int(self._reset_phase) + 1
                                    self._reset_phase_start_monotonic = now_m
                                else:
                                    # Failsafe: don't wait too long on one finger.
                                    remaining_s = max(0.0, float(self._reset_deadline_monotonic) - now_m)
                                    failsafe_s = min(per_finger_timeout_s, max(2.0, remaining_s))
                                    if (now_m - float(self._reset_phase_start_monotonic)) >= failsafe_s:
                                        self._reset_phase = int(self._reset_phase) + 1
                                        self._reset_phase_start_monotonic = now_m

                        # Final phase (THM): complete when all joints are close enough to OPEN.
                        if int(self._reset_phase) >= 5:
                            err_all = float(np.max(np.abs(pos_arr - open_pose_arr)))
                            if err_all <= float(self.cfg.arm_reset_threshold_rad):
                                done = True
                    except Exception:
                        pass
                if done:
                    self._reset_active = False
                    self._reset_phase = 0
                    self._reset_start_monotonic = 0.0
                    self._reset_phase_start_monotonic = 0.0
                    self._reset_reason = ""
                    # Restore current limit to normal after recovery.
                    if self._reset_current_limit_applied and self.has_hardware and self.hand:
                        try:
                            self.hand.write_joint_current_limit(int(self.cfg.normal_current_limit_ma), float(self.cfg.write_timeout_s))
                        except Exception:
                            pass
                    self._reset_current_limit_applied = False

            # Broadcast telemetry (UI)
            if self.clients:
                if pos_list is None:
                    if self.has_hardware:
                        pos_list = None
                    else:
                        pos_list = np.asarray(self.mock_position, dtype=np.float64).tolist()

                await self._broadcast(
                    {
                        "type": "telemetry",
                        "ts": int(time.time() * 1000),
                        "input_voltage": vin if self.has_hardware else None,
                        "joint_actual_position": pos_list,
                        "joint_error_code": err_list if self.has_hardware else None,
                        "cmd_hz": self._cmd_hz_1s(),
                        "cmd_age_ms": self._cmd_age_ms(),
                        "reset_active": bool(self._reset_active),
                        "reset_phase": int(self._reset_phase),
                        "reset_label": self._reset_phase_label(int(self._reset_phase)) if self._reset_active else "",
                        "reset_reason": str(self._reset_reason) if self._reset_active else "",
                    }
                )

            await asyncio.sleep(interval)

    async def hardware_monitor_loop(self) -> None:
        while True:
            if not self.has_hardware:
                self.connect_hardware()
                await self._send_status()
            await asyncio.sleep(3.0)

    async def start(self) -> None:
        print(f"[BRIDGE] WebSocket server: ws://{self.cfg.host}:{self.cfg.port}", flush=True)
        print(
            f"[BRIDGE] wujihandpy.Hand(serial_number={self.cfg.serial_number}, usb_pid={self.cfg.usb_pid}, usb_vid={self.cfg.usb_vid})"
        , flush=True)

        if not self.has_hardware:
            self.connect_hardware()

        async with websockets.serve(self.handle_client, self.cfg.host, self.cfg.port):
            await self._send_status()
            asyncio.create_task(self.telemetry_loop())
            asyncio.create_task(self.hardware_monitor_loop())
            await asyncio.Future()  # run forever


def _parse_args() -> Config:
    p = argparse.ArgumentParser(description="Vision_OS <-> Wuji hand bridge (WebSocket)")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--serial", default=None, help="USB serial number (optional)")
    p.add_argument("--usb-vid", default="0x0483", help="USB vendor id (default 0x0483)")
    p.add_argument("--usb-pid", default="-1", help="USB product id (-1 means any)")
    p.add_argument("--telemetry-hz", type=float, default=30.0)
    p.add_argument("--smoothing", type=float, default=3.0, help="Time constant for smoothing (higher = smoother)")
    p.add_argument("--max-speed", type=float, default=2.0, help="Max joint target speed (rad/s). 0 disables limiting.")
    p.add_argument(
        "--unjam-max-speed",
        type=float,
        default=0.12,
        help="Max joint target speed (rad/s) during RESET/HARD UNJAM. Keep conservative; current limit is reduced during unjam.",
    )
    p.add_argument("--max-curl", type=float, default=0.85, help="Max curl (0=open, 1=full close). Prevents 'perfect fist'.")
    p.add_argument("--open-margin", type=float, default=0.10, help="OPEN safety margin (0..0.5): move OPEN target slightly towards CLOSED to avoid hard stops.")
    p.add_argument("--arm-reset-s", type=float, default=0.0, help="Seconds after ARM to force OPEN (reset) before taking tracking commands.")
    p.add_argument("--reset-open-s", type=float, default=60.0, help="Seconds for RESET recovery (UNJAM) before giving up.")
    p.add_argument(
        "--normal-current-ma",
        type=int,
        default=1000,
        help="Normal joint current limit (mA). Docs default is 1000, valid range 0..3000.",
    )
    p.add_argument(
        "--unjam-current-ma",
        type=int,
        default=500,
        help="Current limit (mA) during RESET/unjam to avoid forcing into jams. Valid range 0..3000.",
    )
    p.add_argument(
        "--auto-unjam-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Automatically enter RESET when joint_error_code is non-zero while armed.",
    )
    p.add_argument("--arm-reset-threshold", type=float, default=0.15, help="Reset completion threshold (rad) vs OPEN pose.")
    p.add_argument("--watchdog-s", type=float, default=1.0, help="seconds without command to open hand")
    p.add_argument("--dry-run", action="store_true", help="Do not write commands to hardware")
    p.add_argument("--mapping", default=None, help="JSON mapping file (weights + open/closed mode)")
    p.add_argument("--write-mode", default="unchecked", choices=["unchecked", "blocking"], help="Write mode for joint targets")
    p.add_argument("--write-timeout", type=float, default=2.0, help="Seconds for SDK write timeout (blocking or unchecked API parameter)")

    a = p.parse_args()
    mc = float(a.max_curl)
    if not (0.0 <= mc <= 1.0):
        mc = max(0.0, min(1.0, mc))
    return Config(
        host=a.host,
        port=a.port,
        usb_vid=int(str(a.usb_vid), 0),
        usb_pid=int(str(a.usb_pid), 0),
        serial_number=a.serial,
        telemetry_hz=float(a.telemetry_hz),
        smoothing=float(a.smoothing),
        max_speed_rad_s=float(a.max_speed),
        unjam_max_speed_rad_s=float(a.unjam_max_speed),
        max_curl=mc,
        open_margin=float(a.open_margin),
        arm_reset_s=float(a.arm_reset_s),
        reset_open_s=float(a.reset_open_s),
        normal_current_limit_ma=int(a.normal_current_ma),
        unjam_current_limit_ma=int(a.unjam_current_ma),
        auto_unjam_on_error=bool(a.auto_unjam_on_error),
        arm_reset_threshold_rad=float(a.arm_reset_threshold),
        watchdog_s=float(a.watchdog_s),
        dry_run=bool(a.dry_run),
        mapping_path=a.mapping,
        write_mode=str(a.write_mode),
        write_timeout_s=float(a.write_timeout),
    )


if __name__ == "__main__":
    cfg = _parse_args()
    bridge = WujiBridge(cfg)
    asyncio.run(bridge.start())

