#!/usr/bin/env python3
"""
修復中指位置
"""
import time
import numpy as np
import wujihandpy

MIDDLE_IDX = 2  # 中指索引

def main():
    print("=" * 50)
    print("🔧 修復中指")
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
    
    print(f"  中指 LOWER: {lower[MIDDLE_IDX]}")
    print(f"  中指 UPPER: {upper[MIDDLE_IDX]}")
    print(f"  中指 ACTUAL: {actual[MIDDLE_IDX]}")
    
    # 計算 OPEN 位置 (LOWER)
    open_pos = lower[MIDDLE_IDX].copy()
    print(f"\n  OPEN 位置 (LOWER): {open_pos}")
    
    print("\n[3] 設定電流 600mA (安全)...")
    hand.write_joint_current_limit(600)
    hand.write_joint_enabled(True)
    time.sleep(0.3)
    
    print("\n[4] 移動中指到 OPEN 位置...")
    target = actual.copy()
    target[MIDDLE_IDX] = open_pos
    
    # 緩慢移動
    steps = 30
    for i in range(steps + 1):
        t = i / steps
        interp = actual + t * (target - actual)
        hand.write_joint_target_position(interp)
        time.sleep(0.05)
        
        if i % 10 == 0:
            pct = int(t * 100)
            print(f"  進度: {pct}%")
    
    print("\n[5] 最終位置:")
    final = np.array(hand.read_joint_actual_position())
    print(f"  中指: {final[MIDDLE_IDX]}")
    print(f"  目標: {open_pos}")
    
    print("\n[6] 恢復電流 1000mA...")
    hand.write_joint_current_limit(1000)
    
    print("\n" + "=" * 50)
    print("✅ 中指修復完成!")
    print("=" * 50)

if __name__ == "__main__":
    main()
