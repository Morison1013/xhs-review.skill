# xhs-review.skill

新媒体行业小红书投放数据复盘

自动根据 Excel 投放数据生成带图表的 Word 复盘报告，支持小红书蒲公英标准格式和多平台达人合作表（视频号/抖音/小红书）。

使用方式：
1. 直接把 github 链接 https://github.com/Morison1013/xhs-review.skill 告诉你的 agent（Claude Code / Codex / Openclaw / Trae）
2. 下载文件放入你的 agent 的 skill 文件夹中

## 功能亮点

- 自动识别列名（曝光、互动、成本、粉丝量、SPU 名称等 180+ 字段）
- 生成完整 Word 报告：封面、目录、16+ 核心图表（环形图、柱状图、散点图、漏斗图等）
- 智能异常数据过滤（CPM/CPE 离群值自动排除）
- 跨平台指标统一（曝光 ⇄ 播放），支持多平台对比分析
- 输出包括：流量结构、内容形式对比、SPU 效率矩阵、成本 TOP 分析、粉丝梯队 CPE 趋势、转化漏斗、组件 CTR、TOP 笔记盘点及复盘建议

## 快速开始

### 模式1：Excel 数据文件

```bash
# 蒲公英格式（单 sheet 标准导出）
python scripts/run_pipeline.py <Excel数据文件> <品牌名称> [输出目录]

# 分步执行
python scripts/analyze_data.py <Excel文件> <输出JSON>
python scripts/generate_charts.py <分析JSON> <图表目录>
python scripts/build_report.py <分析JSON> <图表目录> <输出docx> [品牌名]
```

### 模式2：爬虫模式（v2.1 新增）

从笔记 URL 列表自动爬取内容，分析评论区舆情和视频内容。

```bash
python scripts/run_pipeline.py crawl <URL文件> \
  --cookie "a1=xxx; webId=yyy; web_session=zzz" \
  --brand 品牌名 \
  [--llm-config config/llm_config.json] \
  [--max-comments 200] \
  [--headed]
```

URL 文件格式：每行一个小红书笔记 URL，`#` 开头为注释。

### Cookie 获取

1. 浏览器打开小红书网页版并登录
2. F12 → Application → Cookies → `.xiaohongshu.com`
3. 复制 `a1`、`webId`、`web_session` 的值，用 `; ` 拼接

## 新增特性（v2.1）

| 模块 | 说明 |
|------|------|
| **Playwright 爬虫** | 注入 Cookie 登录态，自动提取标题、正文、图片、视频、评论 |
| **评论舆情分析** | 规则情感分类（正面/负面/中性）、7 种子类别、jieba TF-IDF 热词 |
| **视频内容分析** | OpenCV 抽帧 + Claude Vision API，分析主题/风格/叙事/切角 |
| **自动化 Pipeline** | crawl → comment → video → merge → charts → Word 报告 |

## 依赖安装

### 基础依赖
```bash
pip install python-docx openpyxl matplotlib pandas numpy
```

### 爬虫模式（可选）
```bash
pip install playwright opencv-python jieba anthropic
playwright install chromium
```

## 报告内容

Word 报告自动包含：
- 数据概览（总笔记数、异常数）
- 核心效果总览（曝光/互动/CPM/CPE/CPC）
- 流量来源结构 + 自然流量渠道分布
- 图文 vs 视频效率对比
- SPU 维度散点图（成本 × 互动率）
- 合作项目成本 TOP 横向柱状图
- 粉丝梯队 CPE 双轴图
- 健康 vs 异常笔记对比
- 转化漏斗（活跃 → 成交）
- 组件效果 CTR 对比
- TOP 笔记盘点（阅读量 TOP3 + 成本 TOP3）
- 复盘总结（成功经验/问题诊断/策略建议）
- **评论舆情**：情感分布、子类别、热门关键词、代表性评论
- **视频分析**：内容主题、视觉风格、叙事模式、切入角度、核心卖点

## 输入格式

- 文件：.xlsx
- 类型一：小红书蒲公英导出（第 3 行为列名，第 4 行起数据）
- 类型二：多平台达人合作表（含 sheet：视频号、抖音、小红书，20 列左右）

## 核心计算逻辑

- CPM = 总成本 / 总曝光 × 1000（聚合总量计算，不采用行级平均值）
- CPE = 总成本 / 总互动
- 异常自动过滤：CPM > 中位数 × 10 且 >5000 元；CPE > 中位数 × 20 且 >500 元；曝光 <5 但有成本

## 适用场景

- 小红书品牌商单复盘
- 多平台投放对比（视频号/抖音/小红书）
- 月度/季度/活动投放总结
- 达人策略评估与周度跟踪
- **竞品笔记内容分析**（爬虫模式）
- **评论舆情监控**（爬虫模式）
- **视频内容切角分析**（爬虫模式 + LLM）

## 项目结构

```
xhs-review/
├── scripts/
│   ├── run_pipeline.py       # Pipeline 编排
│   ├── analyze_data.py       # Excel 数据分析
│   ├── generate_charts.py    # matplotlib 图表生成
│   ├── build_report.py       # Word 报告组装
│   ├── crawl_notes.py        # Playwright 小红书爬虫
│   ├── analyze_comments.py   # 评论舆情分析
│   └── analyze_video.py      # 视频内容分析
├── config/
│   └── llm_config.json       # LLM API 配置
├── Skill.md                  # 完整文档
└── README.md
```

## 注意事项

- 确保系统已安装中文字体（SimHei / Microsoft YaHei）
- 大数据量（3000+ 行 × 180+ 列）自动使用 pandas 处理
- JSON 序列化时会自动转换 numpy 数值类型
- 爬虫模式内置人体行为模拟，不建议修改为更快速度
- Cookie 有效期通常 1-7 天，过期需重新获取
