#!/usr/bin/env python3
"""
WujiHand Device Scanner

Automatically scans for WujiHand devices and returns connection info.
Can be used standalone or imported by wuji_bridge.py.

Usage:
    python scan_wuji.py           # Scan and print device info
    python scan_wuji.py --wait    # Wait until device is found
    python scan_wuji.py --json    # Output as JSON
"""

import argparse
import json
import subprocess
import sys
import time
import re
from typing import Optional, Dict, List, Any

# WujiHand USB Vendor ID (STMicroelectronics)
WUJI_VID = 0x0483

# Known WujiHand Product IDs
KNOWN_PIDS = [0x2000, 0xFFFF, 0x5740]


def scan_windows() -> List[Dict[str, Any]]:
    """Scan for WujiHand devices on Windows using pnputil."""
    devices = []
    
    try:
        # Get all connected USB devices
        out = subprocess.check_output(
            ["pnputil", "/enum-devices", "/connected"],
            text=True,
            errors="ignore",
            timeout=10
        )
        
        # Find devices with WujiHand VID
        vid_hex = f"{WUJI_VID:04X}"
        pattern = rf"USB\\VID_{vid_hex}&PID_([0-9A-Fa-f]{{4}})\\([^\s]+)"
        
        for match in re.finditer(pattern, out):
            pid_hex = match.group(1)
            serial = match.group(2)
            instance_id = match.group(0)
            
            # Get device details
            try:
                detail = subprocess.check_output(
                    ["pnputil", "/enum-devices", "/instanceid", instance_id],
                    text=True,
                    errors="ignore",
                    timeout=5
                )
                
                # Check if it's actually a WujiHand
                is_wuji = "WUJIHAND" in detail.upper() or "WUJI" in detail.upper()
                
                # Check driver status
                driver_ok = "usbser.inf" not in detail.lower()
                
                devices.append({
                    "vid": WUJI_VID,
                    "pid": int(pid_hex, 16),
                    "serial": serial,
                    "instance_id": instance_id,
                    "is_wuji": is_wuji,
                    "driver_ok": driver_ok,
                    "platform": "windows"
                })
            except Exception:
                pass
                
    except Exception as e:
        print(f"[SCAN] Windows scan error: {e}", file=sys.stderr)
    
    return devices


def scan_linux() -> List[Dict[str, Any]]:
    """Scan for WujiHand devices on Linux using lsusb."""
    devices = []
    
    try:
        out = subprocess.check_output(
            ["lsusb"],
            text=True,
            errors="ignore",
            timeout=10
        )
        
        vid_hex = f"{WUJI_VID:04x}"
        pattern = rf"Bus (\d+) Device (\d+): ID {vid_hex}:([0-9a-f]{{4}})"
        
        for match in re.finditer(pattern, out, re.IGNORECASE):
            bus = match.group(1)
            device = match.group(2)
            pid_hex = match.group(3)
            
            devices.append({
                "vid": WUJI_VID,
                "pid": int(pid_hex, 16),
                "serial": None,
                "bus": bus,
                "device": device,
                "is_wuji": True,  # Assume true if VID matches
                "driver_ok": True,
                "platform": "linux"
            })
            
    except FileNotFoundError:
        print("[SCAN] lsusb not found, trying /sys/bus/usb", file=sys.stderr)
        # Fallback to sysfs
        try:
            import os
            usb_path = "/sys/bus/usb/devices"
            if os.path.exists(usb_path):
                for dev in os.listdir(usb_path):
                    vendor_file = os.path.join(usb_path, dev, "idVendor")
                    product_file = os.path.join(usb_path, dev, "idProduct")
                    if os.path.exists(vendor_file) and os.path.exists(product_file):
                        with open(vendor_file) as f:
                            vid = int(f.read().strip(), 16)
                        with open(product_file) as f:
                            pid = int(f.read().strip(), 16)
                        if vid == WUJI_VID:
                            devices.append({
                                "vid": vid,
                                "pid": pid,
                                "serial": None,
                                "sysfs_path": dev,
                                "is_wuji": True,
                                "driver_ok": True,
                                "platform": "linux"
                            })
        except Exception as e:
            print(f"[SCAN] Linux sysfs scan error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[SCAN] Linux scan error: {e}", file=sys.stderr)
    
    return devices


def scan_macos() -> List[Dict[str, Any]]:
    """Scan for WujiHand devices on macOS using system_profiler."""
    devices = []
    
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPUSBDataType", "-json"],
            text=True,
            errors="ignore",
            timeout=15
        )
        
        data = json.loads(out)
        
        def search_usb(items):
            for item in items:
                if isinstance(item, dict):
                    vid = item.get("vendor_id", "")
                    if isinstance(vid, str) and f"0x{WUJI_VID:04x}" in vid.lower():
                        pid_str = item.get("product_id", "0x0000")
                        pid = int(pid_str.replace("0x", ""), 16) if isinstance(pid_str, str) else 0
                        devices.append({
                            "vid": WUJI_VID,
                            "pid": pid,
                            "serial": item.get("serial_num"),
                            "name": item.get("_name"),
                            "is_wuji": True,
                            "driver_ok": True,
                            "platform": "macos"
                        })
                    # Recurse into nested items
                    for key in ["_items", "Media"]:
                        if key in item:
                            search_usb(item[key])
        
        if "SPUSBDataType" in data:
            search_usb(data["SPUSBDataType"])
            
    except Exception as e:
        print(f"[SCAN] macOS scan error: {e}", file=sys.stderr)
    
    return devices


def scan_devices() -> List[Dict[str, Any]]:
    """Scan for WujiHand devices on the current platform."""
    if sys.platform == "win32":
        return scan_windows()
    elif sys.platform == "darwin":
        return scan_macos()
    else:
        return scan_linux()


def find_best_device(devices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the best WujiHand device from the scan results."""
    # Filter to valid devices
    valid = [d for d in devices if d.get("driver_ok", True)]
    
    if not valid:
        return None
    
    # Prefer devices with known PIDs
    for d in valid:
        if d["pid"] in KNOWN_PIDS:
            return d
    
    # Return first valid device
    return valid[0]


def wait_for_device(timeout: float = 60.0, interval: float = 2.0) -> Optional[Dict[str, Any]]:
    """Wait for a WujiHand device to be connected."""
    start = time.time()
    
    while (time.time() - start) < timeout:
        devices = scan_devices()
        best = find_best_device(devices)
        if best:
            return best
        
        print(f"[SCAN] No WujiHand found, waiting... ({int(timeout - (time.time() - start))}s remaining)", 
              file=sys.stderr)
        time.sleep(interval)
    
    return None


def get_connection_params(device: Dict[str, Any]) -> Dict[str, Any]:
    """Get wujihandpy connection parameters from device info."""
    return {
        "usb_vid": device["vid"],
        "usb_pid": device["pid"],
        "serial_number": device.get("serial")
    }


def main():
    parser = argparse.ArgumentParser(description="Scan for WujiHand devices")
    parser.add_argument("--wait", action="store_true", help="Wait until device is found")
    parser.add_argument("--timeout", type=float, default=60.0, help="Wait timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--all", action="store_true", help="Show all found devices")
    args = parser.parse_args()
    
    if args.wait:
        device = wait_for_device(timeout=args.timeout)
    else:
        devices = scan_devices()
        if args.all:
            if args.json:
                print(json.dumps(devices, indent=2))
            else:
                print(f"Found {len(devices)} device(s):")
                for d in devices:
                    print(f"  VID=0x{d['vid']:04X} PID=0x{d['pid']:04X} Serial={d.get('serial', 'N/A')}")
            return
        device = find_best_device(devices)
    
    if device:
        if args.json:
            print(json.dumps({
                "found": True,
                "device": device,
                "connection": get_connection_params(device)
            }, indent=2))
        else:
            print(f"[SCAN] Found WujiHand: VID=0x{device['vid']:04X} PID=0x{device['pid']:04X}")
            if device.get("serial"):
                print(f"[SCAN] Serial: {device['serial']}")
            if not device.get("driver_ok", True):
                print("[SCAN] WARNING: Device may need driver update (Zadig)")
    else:
        if args.json:
            print(json.dumps({"found": False, "device": None}, indent=2))
        else:
            print("[SCAN] No WujiHand device found")
        sys.exit(1)


if __name__ == "__main__":
    main()
