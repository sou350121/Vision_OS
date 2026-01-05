"""
解卡無名指 (Ring Finger - finger index 3)
Unjam ring finger
"""

import time
import numpy as np
import wujihandpy

def main():
    print("連接 WujiHand...")
    hand = wujihandpy.Hand(usb_vid=0x0483, usb_pid=-1)
    
    # Read limits
    lower = np.array(hand.read_joint_lower_limit(), dtype=np.float64)
    upper = np.array(hand.read_joint_upper_limit(), dtype=np.float64)
    actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
    error = hand.read_joint_error_code()
    
    ring_idx = 3  # Ring finger
    
    print(f"\n=== 無名指狀態 (finger {ring_idx}) ===")
    print(f"Position: {actual[ring_idx]}")
    print(f"Error:    {error[ring_idx]}")
    print(f"Lower:    {lower[ring_idx]}")
    print(f"Upper:    {upper[ring_idx]}")
    
    # Clear errors
    print("\n清除錯誤...")
    try:
        hand.write_joint_reset_error(1, 2.0)
    except:
        pass
    
    # Disable then enable
    print("重置關節...")
    hand.write_joint_enabled(False, 2.0)
    time.sleep(1.0)
    hand.write_joint_enabled(True, 2.0)
    time.sleep(0.5)
    
    # Move ring finger to OPEN (LOWER for this right hand)
    print("\n移動無名指到 OPEN (LOWER)...")
    target = np.array(actual, dtype=np.float64)
    
    # Gradually move to lower limit
    for step in range(20):
        t = (step + 1) / 20.0
        target[ring_idx, :] = actual[ring_idx, :] + t * (lower[ring_idx, :] - actual[ring_idx, :])
        # Add small margin from limit
        target[ring_idx, :] = target[ring_idx, :] + 0.05 * (upper[ring_idx, :] - lower[ring_idx, :])
        hand.write_joint_target_position(target, 2.0)
        time.sleep(0.15)
        
        now = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        print(f"  Step {step+1}: Ring = {now[ring_idx, :2]}")
    
    print("\n完成!")

if __name__ == "__main__":
    main()
