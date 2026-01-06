"""
WujiHand 回零點 - 把手移動到中間位置
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
    print("🎯 WujiHand 回零點")
    print("=" * 60)
    
    # 連接
    print("\n[1] 連接手...")
    try:
        hand = wujihandpy.Hand(usb_vid=0x0483)
        print("✅ 連接成功!")
    except Exception as e:
        print(f"❌ 連接失敗: {e}")
        return
    
    # 讀取當前位置和限制
    print("\n[2] 讀取當前狀態...")
    try:
        lower = np.array(hand.read_joint_lower_limit(), dtype=np.float64)
        upper = np.array(hand.read_joint_upper_limit(), dtype=np.float64)
        actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        
        # 零點 = 中間位置
        zero_pose = (lower + upper) / 2.0
        
        print(f"  當前位置: 已讀取")
        print(f"  目標零點: (LOWER + UPPER) / 2")
        
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return
    
    # 設定電流
    print("\n[3] 設定電流 800mA...")
    try:
        hand.write_joint_current_limit(800, 2.0)
    except Exception as e:
        print(f"  ⚠️ {e}")
    
    # 確保 Enable
    print("  Enable joints...")
    try:
        hand.write_joint_enabled(True, 2.0)
    except Exception as e:
        print(f"  ⚠️ {e}")
    
    # 平滑移動到零點
    print("\n[4] 移動到零點...")
    
    steps = 30
    for step in range(steps):
        try:
            actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
            
            # 線性插值
            alpha = (step + 1) / steps
            target = actual + alpha * (zero_pose - actual)
            
            hand.write_joint_target_position(target, 2.0)
            time.sleep(0.08)
            
            # 顯示進度
            progress = "█" * (step + 1) + "░" * (steps - step - 1)
            pct = int((step + 1) / steps * 100)
            print(f"  [{progress}] {pct}%", end="\r")
            
        except Exception as e:
            print(f"\n  ⚠️ 錯誤: {e}")
            try:
                hand.write_joint_reset_error(1, 2.0)
            except:
                pass
            time.sleep(0.1)
    
    print(f"\n  ✅ 移動完成")
    
    # 恢復正常電流
    print("\n[5] 恢復正常電流 (1000mA)...")
    try:
        hand.write_joint_current_limit(1000, 2.0)
    except:
        pass
    
    # 最終位置
    print("\n[6] 最終位置:")
    try:
        final = np.array(hand.read_joint_actual_position(), dtype=np.float64)
        finger_names = ["THUMB ", "INDEX ", "MIDDLE", "RING  ", "PINKY "]
        for i, name in enumerate(finger_names):
            print(f"  {name}: {final[i]}")
            print(f"          零點: {zero_pose[i]}")
    except:
        pass
    
    print("\n" + "=" * 60)
    print("🎯 回零完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
