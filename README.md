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

### 模式2：爬虫模式（v2.4+，支持小红书/B站/抖音）

从笔记 URL 列表自动爬取内容，分析评论区舆情和视频内容。支持混合平台 URL。

```bash
# Pipeline 模式（推荐）
python scripts/run_pipeline.py crawl <URL文件> \
  [--cookie "cookie字符串"] \
  --brand 品牌名 \
  [--llm-config config/llm_config.json] \
  [--max-comments 200] \
  [--headed] \
  [--xhs-user-data-dir /path/to/chrome/profile]

# 独立调用（灵活控制）
python scripts/crawl_notes.py urls.txt --output ./output --headed
python scripts/analyze_comments.py ./output/crawled_notes.json ./output/comment_analysis.json
python scripts/analyze_video.py ./output/crawled_notes.json config/llm_config.json ./output
```

### 各平台独立调用

```bash
# 小红书（需要 visible Chrome，web_session 动态变化）
python scripts/crawl_xiaohongshu.py xhs_urls.txt --output ./xhs_output --headed

# B站（headless 可用，API 获取评论）
python scripts/crawl_bilibili.py bili_urls.txt --output ./bili_output --cookie "SESSDATA=xxx; bili_jct=yyy"

# 抖音（v2.4 API 方案，基于浏览器 fetch 调用内部 API）
python scripts/crawl_douyin.py douyin_urls.txt --output ./dy_output [--cookie "xxx"] [--headed]
```

URL 文件格式：每行一个 URL，`#` 开头为注释。支持混合平台：
```
# 小红书
https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6
# B站
https://www.bilibili.com/video/BV1xx4y1c7mN
# 抖音
https://www.douyin.com/video/7123456789012345678
```

### Cookie 获取

| 平台 | Cookie 是否必须 | 说明 |
|------|---------------|------|
| 小红书 | **是** | F12 → Cookies → `.xiaohongshu.com` → `a1`/`webId`/`web_session` |
| B站 | 否（可选） | 大部分内容不登录也可爬取，爬评论需要登录 |
| 抖音 | **是**（爬评论必须） | `ttwid` + `sessionid` 即可，详见下方抖音专项说明 |

**XHS 重要**：`web_session` 是跟随每个笔记链接动态变化的，推荐用 `--xhs-user-data-dir` 参数传入 Chrome 用户数据目录，让浏览器自动管理登录态。

## 抖音专项（v2.4 API 方案）

### 技术方案

抖音爬虫采用 **浏览器内 API 调用** 方案（参考 MediaCrawler），不再依赖 DOM 滚动抓取：

1. **登录态初始化**：注入 Cookie 后先访问抖音首页，建立完整会话
2. **视频详情 API**：`GET /aweme/v1/web/aweme/detail/?aweme_id=xxx`
3. **评论列表 API**：`GET /aweme/v1/web/comment/list/?aweme_id=xxx&cursor=N&count=20`
4. **子评论 API**：`GET /aweme/v1/web/comment/list/reply/?comment_id=xxx`

核心优势：浏览器内 `fetch()` 调用自动处理 `a_bogus` 签名，无需本地计算加密参数。

### Cookie 获取（抖音）

浏览器打开抖音视频页 → F12 → Console → 输入 `document.cookie` → 复制全部输出。

最关键的 Cookie 字段：`ttwid`（设备身份）+ `sessionid`（登录会话）。其他 Cookie 一并带上更稳妥。

### 抖音评论分析

抖音评论区与小红书/B站有明显差异：
- **评论风格**：以"知识认同/感谢分享"为主（约占 85%），购买意向远低于小红书
- **情感分布**：中性评论占 87%，正面 4%，负面 9%，舆情环境友好
- **热词特征**：围绕核心话题的知识性讨论，品牌提及较克制
- **互动结构**：评论 > 收藏 > 点赞，属于典型的"收藏型"内容

分析维度包括：
1. **情感分布**：正面/负面/中性比例
2. **子类别**：种草/质疑/比价/吐槽/求购/成分咨询/使用反馈/其他
3. **TF-IDF 热词**：jieba 分词 + 权重排序
4. **N-gram 短语**：2-3 词高频组合（如"中老年补钙""金钙尔奇k2"）
5. **代表性评论**：各情感类别 Top 评论（按点赞数排序）
6. **对比分析**：与小红书/B站评论区的横向对比

### 抖音视频内容分析

通过 OpenCV 提取视频关键帧，结合 Claude Vision API 进行：
- 内容主题识别
- 视觉风格分析
- 叙事模式判断
- 切入角度评估
- 核心卖点提取

## 爬虫模块架构（v2.4）

```
scripts/
├── crawl_notes.py         # 调度器：自动识别 URL 平台并分发
── crawl_xiaohongshu.py   # 小红书爬虫（DOM 滚动，visible Chrome）
├── crawl_bilibili.py      # B站爬虫（API 获取评论，headless 可用）
├── crawl_douyin.py        # 抖音爬虫（API 方案，浏览器 fetch 调用内部 API）
├── crawler_utils.py       # 共享工具函数
├── analyze_comments.py    # 评论舆情分析（规则情感分类+TF-IDF 热词）
├── analyze_video.py       # 视频内容分析（OpenCV 抽帧+Claude Vision API）
├── analyze_data.py        # Excel 数据分析 + 爬虫数据合并
├── generate_charts.py     # matplotlib 图表生成
├── build_report.py        # Word 报告组装
└── run_pipeline.py        # Pipeline 编排
```

### 各平台爬取策略对比

| 平台 | headless 模式 | 评论获取方式 | 视频下载 | Cookie 需求 |
|------|--------------|------------|---------|------------|
| 小红书 | **不可用**（风控拦截） | DOM 滚动加载 | 拦截 URL | 必须（web_session 动态变化） |
| B站 | 可用 | API（`/x/v2/reply`） | DASH 分片 | 可选（获取更多评论） |
| 抖音 | 推荐 visible | API（`/aweme/v1/web/comment/list/`） | CDN URL | **必须**（ttwid + sessionid） |

## 新增特性（v2.1-v2.4）

| 版本 | 模块 | 说明 |
|------|------|------|
| **v2.1** | Playwright 爬虫 | 支持小红书/B站/抖音三平台，自动识别 URL 分发 |
| **v2.1** | 评论舆情分析 | 规则情感分类（正面/负面/中性）、7 种子类别、jieba TF-IDF 热词 |
| **v2.1** | 视频内容分析 | OpenCV 抽帧 + Claude Vision API，分析主题/风格/叙事/切角 |
| **v2.1** | 自动化 Pipeline | crawl → comment → video → merge → charts → Word 报告 |
| **v2.3** | 模块化架构 | 爬虫拆分为独立模块，支持混合平台 URL 自动分发 |
| **v2.4** | **抖音 API 方案** | 基于浏览器 fetch 调用抖音内部 API，替代 DOM 滚动方案 |
| **v2.4** | 抖音评论分析 | 情感分布、子类别、TF-IDF 热词、N-gram 短语、跨平台对比 |

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
- **抖音科普内容复盘**（v2.4 新增）

## 注意事项

- 确保系统已安装中文字体（SimHei / Microsoft YaHei）
- 大数据量（3000+ 行 × 180+ 列）自动使用 pandas 处理
- JSON 序列化时会自动转换 numpy 数值类型
- 爬虫模式内置人体行为模拟，不建议修改为更快速度
- Cookie 有效期通常 1-7 天，过期需重新获取
- **小红书必须使用 visible Chrome**（headless 会被风控拦截为"IP存在风险"）
- **推荐方案**：`--xhs-user-data-dir` 传入 Chrome 用户数据目录，自动加载登录态
- **抖音评论爬取**：必须提供 Cookie（`ttwid` + `sessionid`），否则无法调用内部 API
- **抖音反爬**：单个视频爬取风险低；批量爬取需加大间隔（10-20秒/视频）
