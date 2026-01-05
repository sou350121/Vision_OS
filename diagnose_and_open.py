"""
診斷並打開 WujiHand - 先讀取狀態再決定方向
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
    print("🔧 WujiHand 診斷與解卡")
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
    try:
        lower = np.array(hand.read_joint_lower_limit(), dtype=np.float64)
        upper = np.array(hand.read_joint_upper_limit(), dtype=np.float64)
        actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        
        print("\n  === 關節數據 (5個手指 x 4個關節) ===")
        finger_names = ["THUMB ", "INDEX ", "MIDDLE", "RING  ", "PINKY "]
        for i, name in enumerate(finger_names):
            print(f"  {name}: lower={lower[i]}, upper={upper[i]}")
            print(f"          actual={actual[i]}")
        
        # 判斷當前位置更接近哪個極限
        dist_to_lower = np.sum(np.abs(actual - lower))
        dist_to_upper = np.sum(np.abs(actual - upper))
        
        print(f"\n  距離 LOWER 總和: {dist_to_lower:.3f}")
        print(f"  距離 UPPER 總和: {dist_to_upper:.3f}")
        
        if dist_to_lower < dist_to_upper:
            print("\n  📍 當前位置更接近 LOWER (可能已經是 OPEN)")
            print("     → 嘗試往 UPPER 方向移動")
            open_pose = upper
            direction = "UPPER"
        else:
            print("\n  📍 當前位置更接近 UPPER (可能是握拳)")
            print("     → 嘗試往 LOWER 方向移動")
            open_pose = lower
            direction = "LOWER"
            
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return
    
    # 詢問用戶
    print(f"\n[3] 準備往 {direction} 方向打開手指")
    print("    選項:")
    print("    1 = 往 LOWER 方向 (按 1)")
    print("    2 = 往 UPPER 方向 (按 2)")
    print("    Enter = 使用自動判斷的方向")
    print("    q = 退出")
    
    choice = input("\n    你的選擇: ").strip().lower()
    
    if choice == 'q':
        print("已退出")
        return
    elif choice == '1':
        open_pose = lower
        direction = "LOWER"
    elif choice == '2':
        open_pose = upper
        direction = "UPPER"
    # else: 使用自動判斷
    
    print(f"\n[4] 開始解卡 (往 {direction} 方向)...")
    
    # 降低電流
    print("\n  降低電流到 600mA...")
    try:
        hand.write_joint_current_limit(600, 2.0)
    except Exception as e:
        print(f"  ⚠️ {e}")
    
    # Disable
    print("  Disable joints (鬆力 3 秒)...")
    try:
        hand.write_joint_enabled(False, 2.0)
        time.sleep(3.0)
    except Exception as e:
        print(f"  ⚠️ {e}")
    
    # Clear errors
    print("  清除錯誤...")
    try:
        hand.write_joint_reset_error(1, 2.0)
    except Exception as e:
        print(f"  ⚠️ {e}")
    
    # Enable
    print("  Enable joints...")
    try:
        hand.write_joint_enabled(True, 2.0)
    except Exception as e:
        print(f"  ❌ {e}")
        return
    
    # 順序打開
    print(f"\n[5] 順序打開手指 (往 {direction})...")
    finger_order = [1, 2, 3, 4, 0]  # INDEX, MIDDLE, RING, PINKY, THUMB
    finger_names = ["INDEX", "MIDDLE", "RING", "PINKY", "THUMB"]
    
    for idx, fi in enumerate(finger_order):
        name = finger_names[idx]
        print(f"\n  === {name} ===")
        
        for step in range(20):
            try:
                actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
                
                # 只移動當前手指
                target = actual.copy()
                alpha = (step + 1) / 20.0
                target[fi, :] = actual[fi, :] + alpha * (open_pose[fi, :] - actual[fi, :])
                
                hand.write_joint_target_position(target, 2.0)
                time.sleep(0.1)
                
                # 顯示進度
                progress = "█" * (step + 1) + "░" * (19 - step)
                print(f"    [{progress}] {(step+1)*5}%", end="\r")
                
            except Exception as e:
                print(f"\n    ⚠️ 錯誤: {e}")
                try:
                    hand.write_joint_reset_error(1, 2.0)
                except:
                    pass
                time.sleep(0.2)
        
        print(f"\n    ✅ {name} 完成")
        time.sleep(0.2)
    
    # 恢復電流
    print("\n[6] 恢復正常電流 (1000mA)...")
    try:
        hand.write_joint_current_limit(1000, 2.0)
    except:
        pass
    
    # 最終位置
    print("\n[7] 最終位置:")
    try:
        final = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        for i, name in enumerate(["THUMB ", "INDEX ", "MIDDLE", "RING  ", "PINKY "]):
            print(f"  {name}: {final[i]}")
    except:
        pass
    
    print("\n" + "=" * 60)
    print("🎉 完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
