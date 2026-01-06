# Vision_OS v2 - VLA 整合開發計劃

## 核心目標：融合大模型做 VLA (Vision-Language-Action)

將當前的手勢追蹤系統升級為 VLA 架構，實現：
- **語言指令** → **視覺理解** → **機械手動作**

## 架構設計

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Language      │     │   Vision        │     │   Action        │
│   (LLM/VLM)     │────▶│   (Camera +     │────▶│   (WujiHand)    │
│   指令理解       │     │   場景理解)      │     │   動作執行       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## 技術路線

### 1. Vision-Language Model (VLM)
- **GPT-4V / Claude Vision** - 場景理解 + 任務規劃
- **LLaVA / Qwen-VL** - 開源替代，可本地部署
- **輸入**: 攝像頭畫面 + 語言指令
- **輸出**: 高層動作描述 (如 "抓取紅色方塊")

### 2. Action Policy
- **方案 A**: VLM 直接輸出關節角度 (端到端)
- **方案 B**: VLM 輸出高層指令 → 低層控制器執行
- **方案 C**: 模仿學習 (Imitation Learning) 從示範中學習

### 3. Tactile Feedback (觸覺反饋)
- 讀取 WujiHand 關節電流 → 估算接觸力
- 力反饋作為 VLA 的額外輸入模態
- 實現精細操作 (如 "輕輕拿起雞蛋")

## 實現階段

### Phase 1: 基礎 VLM 整合
- [ ] 接入 GPT-4V API
- [ ] 實現場景描述功能
- [ ] 語言指令 → 預定義動作映射

### Phase 2: 動作生成
- [ ] 收集示範數據 (手勢追蹤 + 機械手動作)
- [ ] 訓練動作策略網絡
- [ ] VLM → Action Policy → WujiHand

### Phase 3: 觸覺整合
- [ ] 讀取關節電流/力矩
- [ ] 力反饋閉環控制
- [ ] 多模態 VLA (視覺 + 語言 + 觸覺)

## 參考資源

### 開源 VLA 項目
- **RT-2** (Google): Vision-Language-Action Model
- **OpenVLA** (Stanford): 開源 VLA 實現
- **RoboFlamingo**: 基於 Flamingo 的機器人控制

### 相關論文
- "RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control"
- "Open X-Embodiment: Robotic Learning Datasets and RT-X Models"
- "Tactile-VLA: Integrating Tactile Sensing into Vision-Language-Action Models"

## 硬件需求

- **GPU**: RTX 3090+ (本地 VLM 推理)
- **攝像頭**: 深度攝像頭 (RealSense) 或多視角 RGB
- **機械手**: WujiHand (已有)
- **觸覺傳感器**: 可選 (或用電流估算)

## v1 基礎
- 手勢追蹤 → 機械手控制 (已完成)
- 延遲 ~50ms (可接受)
- 文檔: `PROJECT_SUMMARY.md`

---
*Created: 2026-01-06*
*目標: 從手勢模仿升級到語言指令控制*
