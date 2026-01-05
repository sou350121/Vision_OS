"""
直接測試 WujiHand 控制 - 不經過 bridge
"""

import time
import sys
import numpy as np

try:
    import wujihandpy
except ImportError:
    print("❌ 請先安裝 wujihandpy: pip install wujihandpy")
    sys.exit(1)


def main():
    print("=" * 60)
    print("🎮 WujiHand 直接控制測試")
    print("=" * 60)
    
    # 連接
    print("\n[1] 連接手...")
    try:
        hand = wujihandpy.Hand(usb_vid=0x0483)
        print("✅ 連接成功!")
    except Exception as e:
        print(f"❌ 連接失敗: {e}")
        return
    
    # 讀取限制
    print("\n[2] 讀取關節限制...")
    lower = np.array(hand.read_joint_lower_limit(), dtype=np.float64)
    upper = np.array(hand.read_joint_upper_limit(), dtype=np.float64)
    actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
    
    print(f"  LOWER (OPEN): {lower[0][:2]}...")
    print(f"  UPPER (CLOSED): {upper[0][:2]}...")
    print(f"  ACTUAL: {actual[0][:2]}...")
    
    # 設定 OPEN = LOWER, CLOSED = UPPER (根據之前的診斷)
    open_pose = lower.copy()
    closed_pose = upper.copy()
    
    # Enable
    print("\n[3] Enable joints...")
    hand.write_joint_enabled(True, 2.0)
    
    # 設定電流
    print("  設定電流 800mA...")
    hand.write_joint_current_limit(800, 2.0)
    
    # 測試：握拳 (往 UPPER/CLOSED)
    print("\n[4] 測試握拳 (70% closed)...")
    max_curl = 0.7
    target = open_pose + max_curl * (closed_pose - open_pose)
    
    for step in range(30):
        actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        alpha = (step + 1) / 30.0
        interp = actual + alpha * (target - actual)
        hand.write_joint_target_position(interp, 2.0)
        time.sleep(0.05)
        print(f"  Step {step+1}/30", end="\r")
    
    print("\n  ✅ 握拳完成")
    time.sleep(1)
    
    # 測試：張開 (往 LOWER/OPEN)
    print("\n[5] 測試張開...")
    target = open_pose.copy()
    
    for step in range(30):
        actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        alpha = (step + 1) / 30.0
        interp = actual + alpha * (target - actual)
        hand.write_joint_target_position(interp, 2.0)
        time.sleep(0.05)
        print(f"  Step {step+1}/30", end="\r")
    
    print("\n  ✅ 張開完成")
    
    # 恢復電流
    print("\n[6] 恢復電流 1000mA...")
    hand.write_joint_current_limit(1000, 2.0)
    
    print("\n" + "=" * 60)
    print("🎮 測試完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
