# GitHub 发布建议

## 公开仓库

建议只发布：

```text
*.py
*.ps1
README.md
README_SCREEN.md
PUBLISHING.md
examples/
.gitignore
```

不建议公开发布：

```text
stock_profile.csv
market_heat.csv
review_framework.md
rotation_watchlist.csv
limitup_structure_*.md
screen_observer_config.json
screen_captures/
auction_report*.txt
screen_ocr_raw.csv
auction_snapshot_observed.csv
logs/
```

这些文件包含个人交易体系、本地看盘记忆、截图/OCR 数据或机器配置。

## 私有仓库

如果仓库设为 private，可以按需加入：

```text
stock_profile.csv
market_heat.csv
review_framework.md
rotation_watchlist.csv
limitup_structure_*.md
```

本机运行输出和截图仍不建议提交。

