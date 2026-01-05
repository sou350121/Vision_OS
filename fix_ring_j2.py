"""
修正無名指 J2 到中間位置
"""
import time
import numpy as np
import wujihandpy

hand = wujihandpy.Hand(usb_vid=0x0483)
print("連接成功")

# 讀取當前位置
actual = np.array(hand.read_joint_actual_position(), dtype=np.float64)
print(f"當前無名指: {actual[3]}")
print(f"當前 J2: {actual[3][1]}")

# 把 J2 移到 0 (中間)
target = actual.copy()
target[3][1] = 0.0  # Ring finger J2 = 0

print(f"目標無名指: {target[3]}")

# Enable
hand.write_joint_enabled(True, 2.0)
hand.write_joint_current_limit(800, 2.0)

# 移動
for i in range(20):
    current = np.array(hand.read_joint_actual_position(), dtype=np.float64)
    interp = current.copy()
    interp[3][1] = current[3][1] + (i+1)/20 * (0.0 - current[3][1])
    hand.write_joint_target_position(interp, 2.0)
    time.sleep(0.05)

print("完成！")
final = np.array(hand.read_joint_actual_position(), dtype=np.float64)
print(f"最終 J2: {final[3][1]}")
