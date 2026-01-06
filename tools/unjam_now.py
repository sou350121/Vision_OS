"""
Emergency Unjam Script for WujiHand - 直接執行版本
"""

import time
import sys
import numpy as np

try:
    import wujihandpy
except ImportError:
    print("❌ 請先安裝 wujihandpy: pip install wujihandpy")
    sys.exit(1)


def unjam_hand():
    print("=" * 50)
    print("🔧 WujiHand 緊急解卡程序")
    print("=" * 50)
    
    # Step 1: 連接
    print("\n[1/6] 連接手...")
    try:
        hand = wujihandpy.Hand(usb_vid=0x0483)
        print("✅ 連接成功!")
    except Exception as e:
        print(f"❌ 連接失敗: {e}")
        return False
    
    # 讀取關節限制
    try:
        lower = np.array(hand.read_joint_lower_limit(), dtype=np.float64)
        upper = np.array(hand.read_joint_upper_limit(), dtype=np.float64)
        print(f"  關節下限 (thumb): {lower[0]}")
        print(f"  關節上限 (thumb): {upper[0]}")
    except Exception as e:
        print(f"⚠️ 讀取關節限制失敗: {e}")
        lower = np.zeros((5, 4))
        upper = np.ones((5, 4))
    
    # 決定 OPEN 位置 (通常是 upper)
    open_pose = np.array(upper, dtype=np.float64)
    
    # Step 2: 降低電流
    print("\n[2/6] 降低電流限制到 500mA...")
    try:
        hand.write_joint_current_limit(500, 2.0)
        print("✅ 電流已降低")
    except Exception as e:
        print(f"⚠️ 設定電流失敗: {e}")
    
    # Step 3: Disable (鬆力)
    print("\n[3/6] Disable joints (鬆力 4 秒)...")
    try:
        hand.write_joint_enabled(False, 2.0)
        print("  等待 4 秒讓機構鬆開...")
        for i in range(4):
            time.sleep(1.0)
            print(f"  {i+1}/4 秒...")
        print("✅ 鬆力完成")
    except Exception as e:
        print(f"❌ Disable 失敗: {e}")
        return False
    
    # Step 4: Clear errors
    print("\n[4/6] 清除錯誤...")
    try:
        hand.write_joint_reset_error(1, 2.0)
        print("✅ 錯誤已清除")
    except Exception as e:
        print(f"⚠️ 清除錯誤失敗: {e}")
    
    # Step 5: Enable
    print("\n[5/6] Enable joints...")
    try:
        hand.write_joint_enabled(True, 2.0)
        print("✅ Joints 已啟用")
    except Exception as e:
        print(f"❌ Enable 失敗: {e}")
        return False
    
    # Step 6: 順序打開手指
    print("\n[6/6] 順序打開手指...")
    finger_names = ["INDEX", "MIDDLE", "RING", "PINKY", "THUMB"]
    finger_order = [1, 2, 3, 4, 0]  # IDX→MID→RNG→PNK→THM
    
    # 先讀取當前位置
    try:
        current_pos = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        print(f"  當前位置 (thumb): {current_pos[0]}")
    except:
        current_pos = np.zeros((5, 4))
    
    for fi in finger_order:
        name = finger_names[finger_order.index(fi)]
        print(f"\n  打開 {name}...")
        
        # 目標是這根手指的 OPEN 位置
        target = np.array(current_pos, dtype=np.float64)
        target[fi, :] = open_pose[fi, :]
        
        # 慢慢移動 (10 步，每步 0.2 秒)
        for step in range(10):
            try:
                actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
                alpha = (step + 1) / 10.0
                step_target = actual.copy()
                step_target[fi, :] = actual[fi, :] + alpha * (open_pose[fi, :] - actual[fi, :])
                
                hand.write_joint_target_position(step_target, 2.0)
                time.sleep(0.2)
                print(f"    步驟 {step+1}/10", end="\r")
                
            except Exception as e:
                print(f"\n    ⚠️ 錯誤: {e}")
                try:
                    hand.write_joint_reset_error(1, 2.0)
                except:
                    pass
                time.sleep(0.3)
        
        # 更新 current_pos
        try:
            current_pos = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        except:
            pass
        
        print(f"\n  ✅ {name} 完成")
        time.sleep(0.3)
    
    # 恢復正常電流
    print("\n恢復正常電流限制 (1000mA)...")
    try:
        hand.write_joint_current_limit(1000, 2.0)
        print("✅ 電流已恢復")
    except Exception as e:
        print(f"⚠️ 恢復電流失敗: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 解卡完成!")
    print("=" * 50)
    return True


if __name__ == "__main__":
    success = unjam_hand()
    sys.exit(0 if success else 1)
