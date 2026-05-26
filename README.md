# xhs-review.skill
新媒体行业小红书投放数据复盘
自动根据 Excel 投放数据生成带图表的 Word 复盘报告，支持小红书蒲公英标准格式和多平台达人合作表（视频号/抖音/小红书）。
使用方式：
1. 直接把github链接告诉你的agent（claude code/codex/openclaw/trae）
2. 下载文件放入你的agent的skill文件夹中
🎯 功能亮点
自动识别列名（曝光、互动、成本、粉丝量、SPU 名称等 180+ 字段）

生成完整 Word 报告：封面、目录、16+ 核心图表（环形图、柱状图、散点图、漏斗图等）

智能异常数据过滤（CPM/CPE 离群值自动排除）

跨平台指标统一（曝光⇄播放），支持多平台对比分析

输出包括：流量结构、内容形式对比、SPU 效率矩阵、成本 TOP 分析、粉丝梯队 CPE 趋势、转化漏斗、组件 CTR、TOP 笔记盘点及复盘建议

📦 依赖
python-docx, openpyxl, matplotlib, pandas, numpy

🚀 快速开始
蒲公英格式（单 sheet 标准导出）
bash
python run_pipeline.py <Excel数据文件> <品牌名称> [输出目录]
多平台周复盘（视频号/抖音/小红书）
需单独处理多 sheet 数据，调用 generate_charts.py 和 build_weekly_report.py 生成报告。

分步执行
bash
# 1. 数据分析 → JSON
python analyze_data.py <Excel文件> <输出JSON>

# 2. 生成图表目录
python generate_charts.py <分析JSON> <图表目录>

# 3. 组装 Word 报告
python build_report.py <分析JSON> <图表目录> <输出docx> [品牌名]
📥 输入格式
文件：.xlsx

类型一：小红书蒲公英导出（第 3 行为列名，第 4 行起数据）

类型二：多平台达人合作表（含 sheet：视频号、抖音、小红书，20 列左右）

📤 输出内容
Word 报告包含（自动排版带图表）：

数据概览（总笔记数、异常数）

核心效果总览（曝光/互动/CPM/CPE/CPC）

流量来源结构 + 自然流量渠道分布

图文 vs 视频效率对比

SPU 维度散点图（成本×互动率）

合作项目成本 TOP 横向柱状图

粉丝梯队 CPE 双轴图

健康 vs 异常笔记对比

转化漏斗（活跃→成交）

组件效果 CTR 对比

TOP 笔记盘点（阅读量 TOP3 + 成本 TOP3）

复盘总结（成功经验/问题诊断/策略建议）

⚙️ 核心计算逻辑
CPM = 总成本 / 总曝光 × 1000（聚合总量计算，不采用行级平均值）

CPE = 总成本 / 总互动

异常自动过滤：CPM > 中位数×10 且 >5000 元；CPE > 中位数×20 且 >500 元；曝光<5 但有成本

📌 适用场景
小红书品牌商单复盘

多平台投放对比（视频号/抖音/小红书）

月度/季度/活动投放总结

达人策略评估与周度跟踪

⚠️ 注意事项
确保系统已安装中文字体（SimHei / Microsoft YaHei）

大数据量（3000+ 行 × 180+ 列）自动使用 pandas 处理

JSON 序列化时会自动转换 numpy 数值类型
