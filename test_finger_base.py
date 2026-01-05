"""
測試手指底端關節 (J0 - MCP flexion)
Test finger base joints (J0 - MCP flexion)

This script tests if the base joint (J0) of each finger is responding.
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
    
    finger_names = ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']
    joint_names = ['J0 (MCP/Base)', 'J1 (Spread)', 'J2 (PIP)', 'J3 (DIP)']
    
    print("\n=== 關節限位 (Joint Limits) ===")
    for i, name in enumerate(finger_names):
        print(f"\n{name}:")
        for j in range(4):
            print(f"  {joint_names[j]}: Lower={lower[i,j]:.3f}, Upper={upper[i,j]:.3f}, Actual={actual[i,j]:.3f}")
    
    # Enable joints
    print("\n啟用關節...")
    hand.write_joint_enabled(True, 2.0)
    time.sleep(0.5)
    
    # Test each finger's J0 (base joint)
    print("\n=== 測試各手指底端關節 (J0) ===")
    print("OPEN = LOWER, CLOSED = UPPER (for this right hand)")
    
    # Start from current position
    target = np.array(actual, dtype=np.float64)
    
    for finger_idx in range(5):
        finger_name = finger_names[finger_idx]
        j0_lower = lower[finger_idx, 0]
        j0_upper = upper[finger_idx, 0]
        j0_range = abs(j0_upper - j0_lower)
        
        print(f"\n--- {finger_name} J0 ---")
        print(f"  Range: {j0_lower:.3f} (OPEN) to {j0_upper:.3f} (CLOSED)")
        print(f"  Total range: {j0_range:.3f} rad")
        
        # Move to OPEN (lower)
        print(f"  Moving to OPEN (lower)...")
        target[finger_idx, 0] = j0_lower + 0.05  # Small margin from limit
        hand.write_joint_target_position(target, 2.0)
        time.sleep(1.5)
        
        actual_now = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        print(f"  Actual J0: {actual_now[finger_idx, 0]:.3f}")
        
        # Move to 50% closed
        print(f"  Moving to 50% closed...")
        target[finger_idx, 0] = j0_lower + 0.5 * (j0_upper - j0_lower)
        hand.write_joint_target_position(target, 2.0)
        time.sleep(1.5)
        
        actual_now = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        print(f"  Actual J0: {actual_now[finger_idx, 0]:.3f}")
        
        # Move back to OPEN
        print(f"  Moving back to OPEN...")
        target[finger_idx, 0] = j0_lower + 0.05
        hand.write_joint_target_position(target, 2.0)
        time.sleep(1.0)
    
    print("\n=== 測試完成 ===")
    print("如果某個手指的 J0 沒有動，可能是硬體問題或需要調整 finger_weights")

if __name__ == "__main__":
    main()
