# 通达信屏幕观察版

这个版本用于你打开通达信界面后，程序在固定时间节点自动截取竞价表格区域，并调用 Windows 内置 OCR 尝试读取表格文字。

## 第一次使用

先打开通达信，切到你要观察的竞价列表界面，并把窗口、列宽、字体固定好。

然后在本目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_screen_observer.ps1 --calibrate
```

屏幕会变暗，用鼠标框选通达信表格区域，松开后保存配置。

## 测试截图

```powershell
powershell -ExecutionPolicy Bypass -File .\run_screen_observer.ps1 --capture-now
```

截图、OCR 原文和解析结果会保存在：

```text
screen_captures
screen_ocr_raw.csv
auction_snapshot_observed.csv
```

## 竞价时自动观察

竞价前打开通达信并保持界面不被遮挡，然后运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_screen_observer.ps1 --watch
```

默认采样时间：

```text
09:15:01
09:19:30
09:20:00
09:23:00
09:24:50
09:25:00
```

其中 `09:15:01` 属于可撤单阶段，主要用于观察最早竞价封单和后续撤单/留存变化；真正可信度更高的是 `09:20:00` 之后。

## 重要说明

如果 OCR 成功解析出结构化数据，程序会自动生成：

```text
auction_report_observed.txt
```

为了提高识别率，通达信表格最好固定显示这些列，并保持顺序：

```text
代码
名称
最新价
涨停价
买一价
买一量
涨幅
成交额
```

纯 OCR 的识别率取决于表格清晰度。建议：

```text
字体调大
不要遮挡表格
不要频繁移动窗口
列宽固定
屏幕缩放固定
表格背景尽量干净
```

如果 OCR 对数字识别不稳定，下一步应改成“自动复制通达信表格文本”或“读取通达信导出文件”，可靠性会明显高于纯图片识别。
