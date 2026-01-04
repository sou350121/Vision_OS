# Vision_OS ↔ WujiHand（wujihandpy）整合說明

本文件說明如何把 **Vision_OS（MediaPipe 手部追蹤）** 與 **WujiHand（wujihandpy 控制硬體）** 串起來，做到：
- Vision_OS 即時追蹤你的手指伸展度（0–100）
- 透過 WebSocket 傳到 Python Bridge
- Python Bridge 依硬體關節限位做映射並寫入目標角度
- Bridge 回傳硬體遙測（電壓 / 關節實際角度）到 Vision_OS 顯示

---

## 1) 目前整合做了什麼？

### 前端（Vision_OS）
- 檔案：`Vision_OS/app.js`
- 新增：WebSocket 連線（預設 `ws://localhost:8765`）
- 新增：Header 上的 **WUJI 狀態列 + ARM 按鈕 + LEFT/RIGHT 控制手選擇**
- 行為：
  - 當你在畫面中看到左右手追蹤資料時，會把選定的那隻手（LEFT/RIGHT）的五指伸展度送到 Bridge
  - 預設 **不會驅動硬體**，必須按 **ARM** 才會開始送控制命令（安全機制）
  - 解卡/復位：
    - `RESET`：一般復位（disable→enable→逐指開：IDX→MID→RNG→PNK→THM）
    - `HARD UNJAM`：更強復位（**降電流限制 + 更長鬆力 + 逐指開**），用在「卡死握拳打不開」時

### 後端（Python Bridge）
- 檔案：`Vision_OS/wuji_bridge.py`
- 行為：
  - 啟動 WebSocket server（預設 `ws://localhost:8765`）
  - 連線硬體成功後，會讀取 `read_joint_lower_limit / read_joint_upper_limit`
  - 將「伸展度 0–100」映射成「關節角度（radians）」並寫入 `write_joint_target_position`
  - 週期性回傳遙測：
    - `read_input_voltage`
    - `read_joint_actual_position`
  - Watchdog：若 ARM 開啟但一段時間沒有收到手勢資料，會自動把手打開（避免卡死）
  - Auto-Unjam：若 ARM 開啟且讀到 `joint_error_code != 0`（例如 8192），會自動進入解卡流程（可用參數關閉）

---

## 2) 一鍵跑起來（推薦流程）

### A. 先啟動 Python Bridge

在 `Vision_OS` 目錄下：

```bash
python wuji_bridge.py
```

或使用 npm script（Windows）：

```bash
npm run bridge
```

> 目前預設 bridge 使用 `--write-mode unchecked`（避免高頻控制時出現 write timeout），如需改回阻塞模式可自行啟動：
>
> ```bash
> python wuji_bridge.py --write-mode blocking --write-timeout 2.0
> ```

可選參數（當你的硬體不是預設 VID / PID 時會用到）：

```bash
python wuji_bridge.py --usb-vid 0x0483 --usb-pid -1
```

### A.1 映射/反向（重要）

不同批次硬體的「開手/握拳」方向有機會相反，你可以用 JSON 設定調整映射：

- 複製範例：`wuji_mapping.example.json` → `wuji_mapping.json`
- 可調項目：
  - `open_pose`: `"auto"` / `"lower"` / `"upper"`
  - `closed_pose`: `"auto"` / `"lower"` / `"upper"`
  - `finger_weights`: 每指 4 關節的權重（0~1）

> **建議**：如果你的 Wuji 手「上電穩態就是五指打開」（右手掌常見），通常 `OPEN = upper`、`CLOSED = lower`。  
> 需要自動判斷時再用 `"auto"`（它會以「當下實際關節角」來猜 OPEN，所以**請在穩態 OPEN 時啟動 bridge**，避免反向）。

啟動 bridge 時指定：

```bash
python wuji_bridge.py --mapping wuji_mapping.json
```

### A.2 速度（更安全）

如果你覺得 Wuji 手動作太快，可以調低最大速度（單位 rad/s）：

```bash
python wuji_bridge.py --max-speed 0.10
```

### A.3 復位（重要）

為了避免「上一個姿態太緊」導致卡住、或上電狀態不一致，bridge 在你按下 **ARM** 後會先做 **復位到 OPEN**：

- 會先強制追到 OPEN（最多 `--arm-reset-s` 秒，或已接近 OPEN 就提前結束）
- 復位期間會 **忽略追蹤 hand_data**（確保先回到穩態開手）

可調參數：

```bash
python wuji_bridge.py --arm-reset-s 8 --arm-reset-threshold 0.15
```

### A.4 不要「完美握拳」（避免握死打不開）

你提到這批 Wuji 手 **不能完全 fist 起來**，否則可能打不開，所以 bridge 預設會限制最大握拳程度：

- `--max-curl 0.70`：0=open，1=完全握死（預設 0.70）

```bash
python wuji_bridge.py --max-curl 0.70
```

### A.5 HARD UNJAM / 電流限制（卡拳必看）

官方文件：`joint_current_limit` 單位是 **mA**，範圍 **0~3000**，預設 **1000**。  
我們在復位/解卡時會把電流限制降下來，避免「越推越卡」。

可調參數（建議保守）：

```bash
python wuji_bridge.py --unjam-current-ma 500 --normal-current-ma 1000 --unjam-max-speed 0.12
```

另外可關閉自動解卡（除非你很確定不需要）：

```bash
python wuji_bridge.py --no-auto-unjam-on-error
```

### A.6 如果還是打不開：用官方上位機（Wuji Hand HMI）

如果你已經「握死卡住」且 bridge 的 `RESET/HARD UNJAM` 仍然無法打開，建議改用官方上位機先把手打回穩態 OPEN：

1) **先關掉 bridge**（避免同時搶 USB）
2) 下載並啟動官方 Wuji Hand HMI（wujihand-qt）
3) 在 HMI 裡連上裝置後，使用它的「OPEN/復位/解卡」功能把手打開

參考：`https://github.com/wuji-technology/wujihand-qt`

> `wujihandpy.Hand()` 的預設 `usb_vid=0x0483`（十進位 1155）。  
> 你也可以指定 `--serial <SERIAL_NUMBER>` 來綁定某一隻手。

---

### B. 再啟動 Vision_OS（Vite）

```bash
npm install
npm run dev -- --port 8080
```

或使用預設腳本：

```bash
npm run dev:8080
```

打開：
- `http://localhost:8080/`

Header 會看到：
- `WUJI CONNECTED (MOCK)`：表示 WebSocket 連上了，但 Bridge 沒偵測到硬體
- `WUJI CONNECTED` + `HW:ON`：表示 Bridge 已連到硬體（可開始控制）

---

## 3) 硬體偵測失敗（最常見）怎麼排查？

如果 `wuji_bridge.py` 一直看到：
`No device found with specified vendor id (0x0483)`

代表 **Windows 目前沒有枚舉到該 USB 裝置**（或 SDK 找不到符合的 VID/PID）。

### 3.1 先確認 Windows 有沒有看到 USB 裝置（VID/PID）

請在 PowerShell 執行：

```powershell
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_' } | Select-Object Status,Class,FriendlyName,InstanceId | Format-Table -AutoSize
```

你應該會看到類似：
- `USB\VID_0483&PID_....\...`

若完全沒有出現 `VID_0483`：
- **換一條可傳資料的 USB 線**（很多線只能充電）
- **換 USB 口**（避免 HUB / 前面板）
- 確認硬體 **有上電/已開機**

你也可以先跑一次診斷腳本（同樣會嘗試初始化硬體）：

```bash
python wuji_diag.py
```

### 3.2 若 VID/PID 不是 0x0483

把 Device Manager（裝置管理員）裡該裝置的 Hardware IDs（硬體識別碼）找出來，例如：
`USB\VID_1234&PID_ABCD\...`

然後用：

```bash
python wuji_bridge.py --usb-vid 0x1234 --usb-pid 0xABCD
```

### 3.3 Windows 已枚舉到（COM 口）但 Bridge 顯示 `ERROR_NOT_SUPPORTED`

如果你看到類似錯誤：
- `Device ... could not be opened: ERROR_NOT_SUPPORTED`
- 裝置在 Device Manager 里顯示為 **Ports / USB 串行設備 (COMx)**，而且 driver 是 `usbser.inf`

這代表裝置目前被 Windows 綁定成 **USB Serial (usbser)**，但 `wujihandpy` 需要用 **WinUSB / libusb** 方式打開裝置，所以會失敗。

你可以用這個命令確認 driver：

```powershell
pnputil /enum-devices /instanceid "USB\VID_0483&PID_2000\3479387A3433"
```

解法（推薦）：
- 用 **Zadig** 把該裝置的 driver 換成 **WinUSB**
  - 下載：`https://zadig.akeo.ie/`
  - Options → **List All Devices**
  - 找到 `USB\VID_0483&PID_2000\...`（或顯示為 USB Serial Device / COMx）
  - Driver 選 **WinUSB**
  - 點 **Replace Driver**

完成後：
- 裝置通常 **不會再以 COM 口出現**（正常）
- 重新拔插硬體
- 重新啟動 `wuji_bridge.py`，應該就會變成 `HW:ON`

---

## 4) 安全建議（很重要）

- **先確認硬體周圍無障礙物**、不要夾到手/線材
- 先讓 Vision_OS 能穩定追蹤到手（HANDS > 0）
- Bridge 顯示 `HW:ON` 後再按 **ARM**
- Vision_OS 每次載入都會預設 **DISARM**（需要你手動按 ARM 才會送控制命令）
- 如需測試但不想動硬體，可加 `--dry-run`：

```bash
python wuji_bridge.py --dry-run
```

---

## 5) 協議（給後續擴充用）

Vision_OS → Bridge：
- `{"type":"hello", ...}`
- `{"type":"arm","enabled":true}`
- `{"type":"hand_data","side":"right","extensions":{"thumb":..,"index":..,...}}`

Bridge → Vision_OS：
- `{"type":"status","has_hardware":true/false,"armed":true/false,"last_hw_error":...}`
- `{"type":"telemetry","input_voltage":...,"joint_actual_position":[[...],[...],...], "cmd_hz":..., "cmd_age_ms":... }`

## 6) 快速排錯（你的情況：手有追蹤但硬體不動）

先看右側 `WUJI_TELEMETRY`：
- **ARM**：一定要 `ON`
- **CMD**：
  - **RX**：應該 > 0/s（代表 Vision_OS 的控制命令有到 bridge）
  - **AGE**：應該很小（< 500ms）

再按 `TEST`：
- **OPEN / FIST**：不用攝像頭追蹤也會直接下控制命令到硬體，用來確認「bridge→硬體」的鏈路是否 OK。


