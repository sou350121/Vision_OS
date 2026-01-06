import argparse

import numpy as np
import wujihandpy


def main() -> int:
    p = argparse.ArgumentParser(description="WujiHand quick diagnostic (wujihandpy)")
    p.add_argument("--serial", default=None, help="USB serial number (optional)")
    p.add_argument("--usb-vid", default="0x0483", help="USB vendor id (default 0x0483)")
    p.add_argument("--usb-pid", default="-1", help="USB product id (-1 means any)")
    args = p.parse_args()

    print("wujihandpy version:", getattr(wujihandpy, "__version__", "unknown"))
    vid = int(str(args.usb_vid), 0)
    pid = int(str(args.usb_pid), 0)

    try:
        hand = wujihandpy.Hand(serial_number=args.serial, usb_pid=pid, usb_vid=vid)
        print("Hand init OK")

        fw = hand.read_firmware_version()
        print("firmware_version:", fw)

        vin = hand.read_input_voltage()
        print("input_voltage:", vin)

        lo = np.asarray(hand.read_joint_lower_limit(), dtype=np.float64)
        hi = np.asarray(hand.read_joint_upper_limit(), dtype=np.float64)
        pos = np.asarray(hand.read_joint_actual_position(), dtype=np.float64)
        print("joint_lower_limit shape:", lo.shape)
        print("joint_upper_limit shape:", hi.shape)
        print("joint_actual_position shape:", pos.shape)
        return 0
    except Exception as e:
        print("Hand init failed:", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

