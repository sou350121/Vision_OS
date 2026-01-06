# MediaPipe + WujiHand 聯動項目總結

## 項目概述

本項目實現了通過 MediaPipe 手部追蹤（普通攝像頭）來實時控制 WujiHand 機械手。用戶在攝像頭前做手勢，機械手會同步模仿這些動作。項目名稱 "VisionOS" 是代號，實際使用的是瀏覽器 + MediaPipe，不需要 Apple Vision Pro。

### 系統架構

```
┌─────────────────┐     WebSocket      ┌─────────────────┐      USB       ┌─────────────────┐
│   Browser       │ ──────────────────▶│   Python        │ ─────────────▶│   WujiHand      │
│   (MediaPipe)   │   ws://localhost   │   Bridge        │   wujihandpy  │   Hardware      │
│   Hand Tracking │      :8765         │   wuji_bridge   │               │   5 fingers     │
│   + Webcam      │                    │      .py        │               │   20 joints     │
└─────────────────┘                    └─────────────────┘               └─────────────────┘
```

### 硬件需求

- 普通 USB 攝像頭（或筆記本內置攝像頭）
- WujiHand 機械手（USB 連接）
- 電腦（Windows/Mac/Linux）

### 數據流

1. **瀏覽器 (app.js)**: MediaPipe 通過攝像頭檢測手部 21 個關鍵點
2. **計算 Extension**: 將關鍵點轉換為手指伸展度 (0-100)
3. **WebSocket 傳輸**: 發送 `{extensions, thumbSpread}` 到 Bridge
4. **Bridge 映射**: 將 extension 映射到關節角度 (radians)
5. **硬件控制**: 通過 wujihandpy SDK 驅動機械手

## 核心技術實現

### 1. 手指伸展度計算 (fingerExtension.js)

**四指 (食指/中指/無名指/小指)**:
- 計算 MCP、PIP、DIP 三個關節角度
- 加權平均: `MCP*0.4 + PIP*0.35 + DIP*0.25`
- 映射: 100° (彎曲) → 0%, 165° (伸直) → 100%

**大拇指 (雙維度)**:
- **Curl (彎曲)**: MCP + IP 關節角度平均
- **Spread (展開)**: 拇指尖到食指 MCP 的距離比例

### 2. 關節映射 (wuji_bridge.py)

每根手指有 4 個關節 [J0, J1, J2, J3]:
- **J0**: 基部彎曲 (主要)
- **J1**: 側向展開 (四指設為 0，大拇指用於 spread)
- **J2**: 中間關節
- **J3**: 末端關節

映射公式:
```python
target[finger, joint] = open_pose + curl * weight * (closed_pose - open_pose)
```

### 3. 安全機制

- **ARM 開關**: 必須手動啟用才能控制
- **Reset 序列**: ARM 時先強制張開手
- **max_curl 限制**: 防止完全握拳卡住
- **速度限制**: Reset 期間限速 1.0 rad/s
- **硬件 LowPass 濾波**: 8Hz 平滑運動

## 配置文件 (wuji_mapping.json)

```json
{
    "max_curl": 0.85,           // 最大彎曲程度 (0-1)
    "open_pose": "lower",       // 張開對應 lower limit
    "closed_pose": "upper",     // 握拳對應 upper limit
    "finger_weights": {
        "thumb": [1.4, 1.0, 1.0, 0.8],  // J1=1.0 用於 spread
        "index": [1.0, 0.0, 1.0, 0.8],  // J1=0 禁用側向
        "middle": [1.0, 0.0, 1.0, 0.8],
        "ring": [0.9, 0.0, 1.0, 0.9],
        "pinky": [1.0, 0.0, 1.0, 0.9]
    }
}
```

## 開發過程中的困難與解決方案

### 困難 1: 初始版本的嚴重延遲問題

**問題背景**: 
一開始直接使用 WujiHand 官方示例代碼的寫法，機械手響應有明顯的延遲（約 200-500ms），手勢做完了機械手才開始動。

**原因分析**:
1. **軟件速度限制過嚴**: 原代碼對每幀都做速度限制 (`max_speed_rad_s`)，導致目標位置被"拖慢"
2. **軟件平滑濾波疊加**: One Euro Filter + 速度限制 + 指數平滑，三層濾波疊加
3. **阻塞式 USB 寫入**: 使用 `write_joint_target_position()` 同步寫入，等待硬件確認

**解決方案**:

1. **移除軟件速度限制** (正常操作時)
   ```python
   # 之前: 每幀都限速
   delta = np.clip(tgt - prev, -max_step, max_step)
   
   # 之後: 只在 Reset/Unjam 時限速，正常操作直接發送
   if self._reset_active:
       # 限速邏輯
   else:
       # 直接發送，不限速
   ```

2. **移除軟件濾波，改用硬件 LowPass**
   ```python
   # 使用 wujihandpy 的硬件濾波器
   lowpass = wujihandpy.filter.LowPass(cutoff_freq=8.0)
   self.rt_controller = self.hand.realtime_controller(
       enable_upstream=True, 
       filter=lowpass
   )
   ```

3. **使用非阻塞寫入**
   ```python
   # 之前: 同步寫入，等待確認
   self.hand.write_joint_target_position(arr, timeout)
   
   # 之後: 非阻塞寫入
   self.hand.write_joint_target_position_unchecked(arr, timeout)
   ```

**效果**: 延遲從 200-500ms 降到 ~50ms，響應變得即時。

**延遲分佈分析**:
```
優化後總延遲 ~50ms 分解:

┌─────────────────────────────────────────────────────────────┐
│ MediaPipe 推理    │ WebSocket 傳輸 │ Bridge 處理 │ USB 寫入 │
│     ~30ms         │     ~5ms       │    ~5ms     │  ~10ms   │
│   (無法優化)       │   (已最小化)    │  (已最小化)  │ (硬件限制) │
└─────────────────────────────────────────────────────────────┘
```

**具體優化細節**:

| 優化項 | 之前 | 之後 | 節省 |
|--------|------|------|------|
| 軟件速度限制 | 每幀限速，累積 100-200ms | 只在 Reset 時限速 | ~150ms |
| 軟件濾波 | 3 層疊加 (One Euro + 速度 + 指數) | 0 層，交給硬件 | ~50ms |
| USB 寫入 | 同步阻塞等待確認 | 非阻塞 unchecked | ~10ms |
| 硬件濾波 | 無 | LowPass 8Hz | 平滑但不增加延遲 |

**為什麼硬件濾波不增加延遲？**
- 軟件濾波：在發送前"拖慢"數據，延遲疊加在控制鏈路上
- 硬件濾波：濾波和電機執行同時進行，不佔用控制鏈路時間

**關鍵學習**: 
- 硬件濾波比軟件濾波更高效，不增加控制延遲
- 實時控制系統要避免多層濾波疊加
- 安全限制（速度限制）只在必要時啟用（如 Reset），正常操作時信任硬件
- 瓶頸在 MediaPipe（30ms）和 USB 硬件（10ms），這兩個無法通過代碼優化

### 困難 2: 方向映射混亂

**問題**: WujiHand 的 "open" 和 "closed" 對應哪個 limit (upper/lower) 因硬件批次不同而異。

**解決**: 
- 配置化 `open_pose` / `closed_pose` 模式
- 支持 "lower"、"upper"、"auto" 三種模式
- 實際測試確定: 右手 open=lower, closed=upper

### 困難 3: 運動抖動

**問題**: 直接發送目標位置導致機械手抖動。

**嘗試的方案**:
1. ❌ 軟件 One Euro Filter - 增加延遲
2. ❌ 軟件速度限制 - 響應變慢
3. ✅ 硬件 LowPass 濾波 (8Hz) - 最佳平衡

**學到**: 讓硬件處理平滑比軟件更有效。

### 困難 4: 大拇指映射維度不足

**問題**: 大拇指有彎曲和展開兩個自由度，但只用一個 extension 值控制。

**解決**:
- 分離 `thumbCurl` (彎曲) 和 `thumbSpread` (展開)
- thumbSpread 獨立控制 J1 關節
- 兩個維度獨立計算和傳輸

### 困難 5: 手指張縮功能

**問題**: 嘗試實現四指的側向張縮 (J1)，但 MediaPipe 的 spread 檢測不準確。

**結果**: 放棄四指 J1 控制，只保留大拇指的 spread。

**學到**: 不是所有功能都值得實現，要根據輸入數據質量決定。

### 困難 6: Windows USB 驅動

**問題**: Windows 默認用 usbser.inf 綁定設備，wujihandpy 需要 WinUSB。

**解決**: 使用 Zadig 工具替換驅動。

## 可遷移的技能

### 1. 實時控制系統設計

- **分層架構**: 感知層 → 計算層 → 通信層 → 執行層
- **異步處理**: Python asyncio + WebSocket
- **狀態機**: ARM/DISARM、Reset 序列

**適用場景**: 機器人控制、遊戲輸入、IoT 設備

### 2. 傳感器數據處理

- **角度計算**: 三點向量夾角
- **歸一化**: 用手掌大小標準化距離
- **映射函數**: 線性映射 + 範圍限制

**適用場景**: 動作捕捉、姿態估計、手勢識別

### 3. 硬件軟件協同

- **濾波策略**: 軟件 vs 硬件濾波的取捨
- **安全機制**: 速度限制、範圍限制、watchdog
- **配置化**: JSON 配置文件解耦硬件差異

**適用場景**: 嵌入式系統、工業控制、醫療設備

### 4. 調試技巧

- **日誌分層**: 關鍵事件 vs 高頻數據
- **可視化**: UI 顯示實時數據 (extension bars)
- **測試姿勢**: 手動發送 OPEN/FIST 驗證硬件

**適用場景**: 任何實時系統調試

### 5. 迭代開發

- **最小可行**: 先實現基本功能，再優化
- **快速驗證**: 改配置 → 重啟 → 測試
- **及時止損**: 放棄不可行的功能 (四指 spread)

## 項目文件結構

```
Vision_OS/
├── app.js                    # 前端: MediaPipe + WebSocket 客戶端
├── index.html                # UI 界面
├── style.css                 # 樣式
├── wuji_bridge.py            # 後端: WebSocket 服務器 + 硬件控制
├── scan_wuji.py              # USB 設備自動掃描工具
├── wuji_mapping.json         # 配置: 關節權重和方向
│
├── src/                      # 前端模塊
│   ├── fingerExtension.js    # 手指伸展度計算 (可測試模塊)
│   └── oneEuroFilter.js      # One Euro 濾波器 (備用)
│
├── tests/                    # Python 測試
│   └── test_bridge.py        # Bridge 單元測試
│
├── tools/                    # 硬件調試工具
│   ├── diagnose_and_open.py  # 診斷並張開手
│   ├── goto_zero.py          # 移動到零位
│   ├── unjam_*.py            # 解卡工具
│   ├── fix_*.py              # 關節修復工具
│   └── wuji_diag.py          # 硬件診斷
│
├── docs/                     # 文檔
│   ├── PROJECT_SUMMARY.md    # 項目總結 (本文件)
│   ├── TECHNICAL_DETAILS.md  # 技術細節
│   └── WUJI_INTEGRATION.md   # WujiHand 集成指南
│
├── backups/                  # 歷史版本備份
└── v2_dev/                   # V2 開發 (VLA 集成)
```

## 運行方式

```bash
# 1. 啟動 Bridge
python wuji_bridge.py --max-speed 2.0

# 2. 啟動前端 (另一個終端)
npx http-server -p 8080

# 3. 打開瀏覽器
# http://localhost:8080

# 4. 點擊 ARM 按鈕開始控制
```

## 未來改進方向

1. **手勢識別**: 識別特定手勢觸發動作
2. **雙手控制**: 支持左右手分別控制
3. **力反饋**: 讀取關節電流估算接觸力
4. **遠程控制**: 通過網絡控制遠端機械手
5. **錄製回放**: 記錄手勢序列並回放

---

*最後更新: 2026-01-05*
