#!/usr/bin/env python3
"""
測試每個關節的移動 - 診斷哪個關節沒有動
"""

import wujihandpy
import numpy as np
import time

def main():
    print("連接 WujiHand...")
    h = wujihandpy.Hand(usb_vid=0x0483, usb_pid=-1)
    
    # 讀取限制
    lower = np.array(h.read_joint_lower_limit(), dtype=np.float64)
    upper = np.array(h.read_joint_upper_limit(), dtype=np.float64)
    actual = np.array(h.read_joint_actual_position(), dtype=np.float64)
    
    finger_names = ["THUMB", "INDEX", "MIDDLE", "RING", "PINKY"]
    joint_names = ["J0(MCP/底)", "J1(側向)", "J2(PIP/中)", "J3(DIP/尖)"]
    
    print("\n=== 關節範圍 ===")
    for fi, fname in enumerate(finger_names):
        print(f"\n{fname}:")
        for ji, jname in enumerate(joint_names):
            range_val = abs(upper[fi, ji] - lower[fi, ji])
            print(f"  {jname}: lower={lower[fi,ji]:.3f}, upper={upper[fi,ji]:.3f}, range={range_val:.3f}")
    
    # 啟用關節
    print("\n啟用關節...")
    h.write_joint_enabled(True, 2.0)
    time.sleep(0.5)
    
    # 測試食指的每個關節
    print("\n=== 測試食指 (INDEX) 每個關節 ===")
    fi = 1  # INDEX finger
    
    for ji in range(4):
        jname = joint_names[ji]
        print(f"\n測試 {jname}...")
        
        # 讀取當前位置
        actual = np.array(h.read_joint_actual_position(), dtype=np.float64)
        start_pos = actual[fi, ji]
        
        # 計算目標 (往 lower 方向移動 50%)
        target_val = lower[fi, ji] + 0.5 * (upper[fi, ji] - lower[fi, ji])
        
        print(f"  當前: {start_pos:.3f}")
        print(f"  目標: {target_val:.3f}")
        
        # 漸進移動
        target = actual.copy()
        for step in range(10):
            alpha = (step + 1) / 10.0
            target[fi, ji] = start_pos + alpha * (target_val - start_pos)
            h.write_joint_target_position(target, 2.0)
            time.sleep(0.1)
        
        # 讀取最終位置
        final = np.array(h.read_joint_actual_position(), dtype=np.float64)
        end_pos = final[fi, ji]
        moved = abs(end_pos - start_pos)
        
        if moved > 0.05:
            print(f"  ✅ 移動了 {moved:.3f} rad")
        else:
            print(f"  ⚠️  幾乎沒動 (只移動 {moved:.3f} rad)")
        
        # 回到原位
        target[fi, ji] = start_pos
        h.write_joint_target_position(target, 2.0)
        time.sleep(0.3)
    
    print("\n完成!")

if __name__ == "__main__":
    main()
