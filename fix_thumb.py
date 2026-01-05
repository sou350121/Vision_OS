#!/usr/bin/env python3
"""診斷並修復大拇指"""

import wujihandpy
import numpy as np
import time

def main():
    print("連接 WujiHand...")
    h = wujihandpy.Hand(usb_vid=0x0483, usb_pid=-1)
    
    # 讀取大拇指狀態
    pos = np.array(h.read_joint_actual_position())
    err = np.array(h.read_joint_error_code())
    lower = np.array(h.read_joint_lower_limit())
    upper = np.array(h.read_joint_upper_limit())
    
    print("\n=== 大拇指狀態 (finger 0) ===")
    print(f"Position: {pos[0]}")
    print(f"Error:    {err[0]}")
    print(f"Lower:    {lower[0]}")
    print(f"Upper:    {upper[0]}")
    
    # 檢查是否有錯誤
    if np.any(err[0] != 0):
        print("\n⚠️  大拇指有錯誤! 清除錯誤...")
        h.write_joint_reset_error(1, 2.0)
        time.sleep(0.5)
        err2 = np.array(h.read_joint_error_code())
        print(f"清除後 Error: {err2[0]}")
    
    # 啟用關節
    print("\n啟用關節...")
    h.write_joint_enabled(True, 2.0)
    time.sleep(0.5)
    
    # 嘗試移動大拇指到 LOWER (OPEN)
    print("\n移動大拇指到 OPEN (LOWER)...")
    target = np.array(pos, dtype=np.float64)
    target[0] = lower[0]  # 大拇指移到 lower
    
    for i in range(20):
        # 漸進移動
        current = np.array(h.read_joint_actual_position())
        step = target - current
        step = np.clip(step, -0.05, 0.05)
        next_pos = current + step
        h.write_joint_target_position(next_pos, 2.0)
        time.sleep(0.1)
        
        new_pos = np.array(h.read_joint_actual_position())
        print(f"  Step {i+1}: Thumb = {new_pos[0][:2]}")
    
    print("\n完成!")
    final_pos = np.array(h.read_joint_actual_position())
    print(f"最終位置: {final_pos[0]}")

if __name__ == "__main__":
    main()
