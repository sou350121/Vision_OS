#!/usr/bin/env python3
"""
打開手 - 往 UPPER 方向移動（張開）
"""
import time
import numpy as np
import wujihandpy

FINGER_NAMES = ["THUMB", "INDEX", "MIDDLE", "RING", "PINKY"]
FINGER_ORDER = [1, 2, 3, 4, 0]  # INDEX, MIDDLE, RING, PINKY, THUMB

def main():
    print("=" * 50)
    print("🖐️ 打開手 (往 UPPER 方向)")
    print("=" * 50)
    
    print("\n[1] 連接手...")
    try:
        hand = wujihandpy.Hand()
        print("✅ 連接成功!")
    except Exception as e:
        print(f"❌ 連接失敗: {e}")
        return
    
    print("\n[2] 讀取關節限位...")
    lower = np.array(hand.read_joint_lower_limit())
    upper = np.array(hand.read_joint_upper_limit())
    actual = np.array(hand.read_joint_actual_position())
    
    # OPEN = UPPER (張開)
    open_pose = upper.copy()
    print(f"  目標 OPEN 位置 (UPPER)")
    
    print("\n[3] 設定電流 600mA...")
    hand.write_joint_current_limit(600)
    
    print("\n[4] Enable joints...")
    hand.write_joint_enabled(True)
    time.sleep(0.3)
    
    print("\n[5] 順序打開手指...")
    current = actual.copy()
    
    for fi in FINGER_ORDER:
        name = FINGER_NAMES[fi]
        print(f"  打開 {name}...")
        
        target = current.copy()
        target[fi] = open_pose[fi]
        
        steps = 20
        for s in range(steps + 1):
            t = s / steps
            interp = current + t * (target - current)
            hand.write_joint_target_position(interp)
            time.sleep(0.04)
        
        current = target.copy()
        print(f"  ✅ {name} 完成")
        time.sleep(0.2)
    
    print("\n[6] 恢復電流 1000mA...")
    hand.write_joint_current_limit(1000)
    
    print("\n[7] 最終位置:")
    final = np.array(hand.read_joint_actual_position())
    for i, name in enumerate(FINGER_NAMES):
        print(f"  {name}: {final[i]}")
    
    print("\n" + "=" * 50)
    print("🖐️ 手已打開!")
    print("=" * 50)

if __name__ == "__main__":
    main()
