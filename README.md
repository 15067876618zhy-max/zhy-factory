# A 股集合竞价屏幕观察助手

这是一个本地运行的通达信集合竞价观察工具。它会在固定竞价节点截取通达信界面，通过 Windows OCR 解析封单、加单和股票名称，再结合本地概念库生成竞价属性报告。

> 仅用于个人看盘研究和复盘记录，不构成投资建议。

## 功能

- 自动观察集合竞价节点：`09:15:01`、`09:19:30`、`09:20:00`、`09:23:00`、`09:24:00`、`09:24:50`、`09:25:00`
- 生成 `09:20` 竞价初判报告
- 生成 `09:24` 及时交易判断报告
- 生成 `09:25` 最终竞价属性映射报告
- 识别封单、9:20 后加单、9:23 后冲刺加单
- 结合本地股票概念库输出潜在扩散方向
- 支持交易日自动启动任务
- 支持开盘 9:30-9:33 涨速观察脚本

## 主要文件

```text
screen_observer.py                 通达信屏幕截图、OCR、竞价节点采样
auction_attribute_assistant.py     竞价属性、封单、加单、扩散方向分析
opening_momentum_observer.py       开盘前几分钟涨速观察
windows_ocr.ps1                    Windows OCR 调用脚本
run_screen_observer.ps1            屏幕观察入口
run_opening_momentum.ps1           开盘涨速观察入口
install_trading_day_task.ps1       安装交易日自动任务
start_trading_day_watch.ps1        自动任务启动脚本
stock_profile.csv                  股票概念、事件、业绩、本地记忆库
market_heat.csv                    市场热点热度配置
review_framework.md                复盘和短线策略框架
limitup_structure_*.md             每日涨停结构记忆
```

## 第一次使用

打开通达信，切到要观察的竞价列表界面，并固定窗口、字体和列宽。

然后运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_screen_observer.ps1 --calibrate
```

框选通达信表格区域后，会在本地保存校准配置。

## 测试截图

```powershell
powershell -ExecutionPolicy Bypass -File .\run_screen_observer.ps1 --capture-now
```

## 竞价自动观察

竞价前打开通达信并保持区域不被遮挡：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_screen_observer.ps1 --watch
```

运行后会生成：

```text
auction_report_0920.txt
auction_report_0924.txt
auction_report_observed.txt
```

这些报告属于本地运行输出，默认不会提交到 GitHub。

## 交易日自动运行

安装 Windows 计划任务：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_trading_day_task.ps1
```

卸载计划任务：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_trading_day_task.ps1
```

## 使用注意

- 通达信界面不能被遮挡。
- 表格列宽和字体尽量固定。
- OCR 可能识别错代码或名称，需要结合截图人工校验。
- `stock_profile.csv` 是本地概念记忆库，效果取决于维护质量。
- 截图、OCR 原文、报告和本机校准配置默认被 `.gitignore` 排除。

