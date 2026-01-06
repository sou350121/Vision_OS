# VISION_OS - 用摄像头控制机械手

[English](README.md) | 简体中文

用普通摄像头追踪手部动作，实时控制 WujiHand 机械手。

## 为什么做这个项目？

WujiHand 官方的示例代码延迟太高（200-500ms），手动完了机械手才开始动。我花了几天时间优化，把延迟降到了 ~50ms，现在基本是实时的。

## 和官方示例的对比

| | 官方示例 | 本项目 |
|---|---|---|
| **延迟** | 200-500ms | ~50ms |
| **滤波** | 软件多层叠加，越滤越慢 | 硬件 LowPass，不增加延迟 |
| **USB 写入** | 同步阻塞等确认 | 非阻塞，发完就走 |
| **设备连接** | 手动指定 VID/PID | 自动扫描 |
| **安全机制** | 基本 | ARM 开关 + Reset 序列 + 握力限制 |
| **调试工具** | 无 | 15 个脚本，解卡/诊断/测试 |

### 延迟优化的关键

官方示例的问题：软件滤波（One Euro Filter + 速度限制 + 指数平滑）三层叠加，每层都在"拖慢"数据。

我的做法：
1. 删掉所有软件滤波，改用硬件 LowPass（8Hz）
2. USB 写入改成 `_unchecked` 非阻塞模式
3. 速度限制只在 Reset 时启用，正常操作不限速

结果：延迟从 200-500ms 降到 ~50ms。

## 硬件需求

- 普通 USB 摄像头（笔记本内置的也行）
- WujiHand 机械手
- Windows/Mac/Linux 电脑

## 快速开始

```bash
# 1. 装依赖
pip install -r requirements.txt
npm install

# 2. 启动 bridge（自动扫描设备）
python wuji_bridge.py --max-speed 2.0

# 3. 启动前端
npx http-server -p 8080

# 4. 打开浏览器 http://localhost:8080
# 5. 等 WUJI 显示 CONNECTED，点 ARM 开始控制
```

## 配置

复制 `wuji_mapping.example.json` → `wuji_mapping.json`：

```json
{
    "max_curl": 0.85,        // 最大握力，别设太高会卡住
    "open_pose": "lower",    // 张开对应 lower limit
    "closed_pose": "upper",  // 握拳对应 upper limit
    "finger_weights": {
        "thumb": [1.4, 1.0, 1.0, 0.8],
        "index": [1.0, 0.0, 1.0, 0.8],
        // ...
    }
}
```

## 项目结构

```
Vision_OS/
├── app.js              # 前端，MediaPipe 手部追踪
├── wuji_bridge.py      # 后端，WebSocket + 硬件控制
├── scan_wuji.py        # USB 设备自动扫描
├── wuji_mapping.json   # 配置文件
│
├── src/                # 前端模块
├── tests/              # 测试
├── tools/              # 调试工具（解卡、诊断、测试关节）
├── docs/               # 文档
└── backups/            # 历史版本备份
```

## 调试工具

机械手卡住了？用这些脚本：

```bash
python tools/unjam_now.py      # 快速解卡
python tools/goto_zero.py      # 回零位
python tools/wuji_diag.py      # 硬件诊断
python tools/fix_middle.py     # 修复中指
```

## 已知问题

- MediaPipe 对手指侧向张开（spread）检测不准，所以四指的 J1 关节禁用了，只有拇指的 spread 能用
- Windows 可能需要用 Zadig 换 USB 驱动（WinUSB）

## 文档

- `docs/PROJECT_SUMMARY.md` - 完整项目总结，包括优化细节
- `docs/TECHNICAL_DETAILS.md` - 技术实现
- `docs/WUJI_INTEGRATION.md` - 集成指南

## License

MIT
