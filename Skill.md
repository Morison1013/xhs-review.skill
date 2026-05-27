---
name: xhs-review
description: 小红书/多平台投放数据复盘 — 输入Excel数据文件或笔记URL，自动生成带图表的Word复盘报告。支持蒲公英格式、多平台达人合作表、以及基于爬虫的内容分析（评论舆情+视频内容）
---

# 小红书/多平台投放复盘 Skill

## 功能

根据投放数据Excel文件**或**笔记URL列表，自动完成数据分析、图表生成和Word报告组装，产出可直接汇报的复盘文档。

**v2.4**：抖音爬虫升级为 API 方案（浏览器 fetch 调用内部 API），替代 DOM 滚动方案。支持完整评论分页拉取和结构化数据导出。

## 用法

### 模式1：Excel 数据文件（原有模式）
```bash
python ~/.claude/skills/xhs-review/scripts/run_pipeline.py <Excel数据文件> <品牌名称> [输出目录]
```

### 模式2：爬虫模式（v2.4，模块化架构）
```bash
python ~/.claude/skills/xhs-review/scripts/run_pipeline.py crawl <URL文件> \
  [--cookie "cookie字符串"] \
  --brand 品牌名 \
  [--output 输出目录] \
  [--llm-config config/llm_config.json] \
  [--max-comments 200] \
  [--max-notes 0] \
  [--headed] \
  [--xhs-user-data-dir /path/to/chrome/profile]
```

URL 文件格式：每行一个笔记 URL，空行和 `#` 开头的注释行自动跳过。支持混合平台：
```
# 小红书
https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6
# B站
https://www.bilibili.com/video/BV1xx4y1c7mN
# 抖音
https://www.douyin.com/video/7123456789012345678
```

### 独立调用（推荐用于复杂场景）

爬虫模块现已拆分为独立脚本，可直接调用：

```bash
# 小红书（需要 visible Chrome 或 Chrome profile）
python scripts/crawl_xiaohongshu.py xhs_urls.txt --output ./xhs_output --headed

# B站（headless 可用）
python scripts/crawl_bilibili.py bili_urls.txt --output ./bili_output --cookie "SESSDATA=xxx; bili_jct=yyy"

# 抖音（v2.4 API 方案）
python scripts/crawl_douyin.py douyin_urls.txt --output ./dy_output --cookie "ttwid=xxx; sessionid=yyy" --headed

# 混合模式（自动分发到各平台模块）
python scripts/crawl_notes.py urls.txt --output ./output --headed
```

### Cookie 获取方式

| 平台 | Cookie 是否必须 | 获取方式 |
|------|---------------|---------|
| 小红书 | **是** | 登录后 F12 → Cookies → `.xiaohongshu.com` → `a1`/`webId`/`web_session` |
| B站 | 否（可选） | 大部分内容不登录也可爬取，爬评论需要登录（SESSDATA + bili_jct） |
| 抖音 | **是**（爬评论必须） | 视频页 F12 → Console → 输入 `document.cookie` → 复制全部输出（核心字段：`ttwid` + `sessionid`） |

**XHS 重要**：`web_session` 是跟随每个笔记链接动态变化的，建议使用 `--xhs-user-data-dir` 参数传入 Chrome 用户数据目录，让浏览器自动管理登录态。

### 分步执行
```bash
# 1. 爬取笔记
python ~/.claude/skills/xhs-review/scripts/crawl_notes.py urls.txt --output ./output --headed

# 2. 分析评论
python ~/.claude/skills/xhs-review/scripts/analyze_comments.py ./output/crawled_notes.json ./output/comment_analysis.json

# 3. 分析视频（需要 LLM API）
python ~/.claude/skills/xhs-review/scripts/analyze_video.py ./output/crawled_notes.json config/llm_config.json ./output ./output/comment_analysis.json

# 4. 合并数据
python ~/.claude/skills/xhs-review/scripts/analyze_data.py --merge-crawl ./output/crawled_notes.json ./output/analysis_result.json --comments ./output/comment_analysis.json --videos ./output/video_analysis.json

# 5. 生成图表 + 报告
python ~/.claude/skills/xhs-review/scripts/generate_charts.py ./output/analysis_result.json ./output/charts
python ~/.claude/skills/xhs-review/scripts/build_report.py ./output/analysis_result.json ./output/charts ./output/report.docx 品牌名
```

## LLM 配置

视频内容分析需要调用 Claude Vision API。配置文件 `config/llm_config.json`：
```json
{
  "provider": "claude",
  "model": "claude-sonnet-4-20250514",
  "api_key_env": "ANTHROPIC_API_KEY",
  "max_tokens": 4096,
  "temperature": 0.3,
  "max_frames_per_video": 8,
  "frame_interval_sec": 3,
  "frame_max_size": [800, 600]
}
```

## 输入要求

- **数据文件**：.xlsx格式，支持蒲公英标准导出或多sheet达人合作表
- **URL文件**：每行一个笔记 URL，支持小红书/B站/抖音混合
- **Cookie**：小红书登录态 Cookie 字符串（或 --xhs-user-data-dir 指定 Chrome profile）；抖音需 `ttwid` + `sessionid`
- **品牌名称**：用于报告标题和命名
- **输出目录**：可选，默认与数据文件同目录

## 数据列自动识别

脚本自动通过关键词匹配识别Excel列，支持以下核心指标：
- 曝光量、阅读量、互动量（点赞/收藏/评论/分享/关注）
- 自然/推广/加热流量
- 博主粉丝量、笔记类型（图文/视频）、健康状态
- SPU名称、合作项目名称、品牌名称
- 成本数据（总金额/蒲公英费用/广告费用）
- 转化漏斗数据（站外活跃UV/加购UV/成交UV等）
- 组件数据（正文组件/评论区组件/互动组件等CTR）
- 达人量级（尾部KOL/腰部KOL/头部KOL/KOC）

## 输出内容

Word报告包含（Excel 模式）：
1. **封面**：品牌名、样本量、生成日期
2. **目录**
3. **数据概览**：总笔记数、异常数等
4. **核心效果总览**：曝光/阅读/互动/CPE/CPM/CPC
5. **流量来源结构**：推广vs自然vs加热（含环形图）
6. **自然流量渠道分布**：发现页/搜索页等（含柱状图）
7. **内容形式对比**：图文vs视频效率对比（含分组柱状图）
8. **SPU维度表现**：成本×互动率散点图
9. **合作项目成本TOP**：横向柱状图（颜色标注效率）
10. **粉丝梯队效率**：CPE趋势双轴图
11. **健康vs异常笔记**对比
12. **转化漏斗**：活跃→成交全流程（含漏斗图）
13. **组件效果分析**：各组件CTR对比（含柱状图）
14. **TOP笔记盘点**：阅读量TOP3 + 成本TOP3
15. **复盘总结**：自动生成的成功经验、问题诊断、策略建议

爬虫模式额外包含：
16. **评论舆情分析**：情感分布饼图、子类别柱状图、TF-IDF热词表、代表性评论
17. **视频内容深度分析**：内容主题、视觉风格、叙事模式、切入角度、核心卖点

## 核心计算规则

### CPM/CPE 计算
- **CPM = 总成本 / 总播放 × 1000**（用聚合总量计算，不用每行CPM的平均值）
- **CPE = 总成本 / 总互动**（用聚合总量计算）

### 跨平台指标统一
- 小红书的「曝光量」等价于视频号/抖音的「播放量」，在分析中统一映射为 `plays` 字段
- 这样可以统一比较不同平台的内容传播规模

## 异常数据处理

自动检测并排除以下异常数据行，不参与CPM/CPE等指标计算：

1. **CPM异常**：CPM > 中位数×10倍 且 > 5000元绝对值（通常是数据未沉淀）
2. **CPE异常**：CPE > 中位数×20倍 且 > 500元绝对值
3. **数据未沉淀**：播放/曝光 < 5次 但有成本

## 爬虫模块架构

### 独立模块结构
```
scripts/
├── crawl_notes.py         # 调度器：识别平台 URL，分发到对应模块
├── crawl_xiaohongshu.py   # 小红书爬虫（独立模块）
── crawl_bilibili.py      # B站爬虫（独立模块）
├── crawl_douyin.py        # 抖音爬虫（v2.4 API 方案）
├── crawler_utils.py       # 共享工具函数
├── analyze_comments.py    # 评论舆情分析
├── analyze_video.py       # 视频内容分析
├── analyze_data.py        # Excel 数据分析和爬虫数据合并
├── generate_charts.py     # matplotlib 图表生成
├── build_report.py        # Word 报告组装
└── run_pipeline.py        # Pipeline 编排
```

### 各平台爬取策略

| 平台 | headless | 评论获取方式 | 视频下载 | Cookie 需求 |
|------|----------|------------|---------|------------|
| 小红书 | **不可用**（会被风控拦截） | DOM 滚动加载 | 拦截 URL | 必须，web_session 动态变化 |
| B站 | **可用** | API（`/x/v2/reply`） | DASH 分片 | 可选（获取更多评论） |
| 抖音 | 推荐 visible | API（`/aweme/v1/web/comment/list/`） | CDN URL | **必须**（ttwid + sessionid） |

### 抖音 API 方案（v2.4）

抖音爬虫采用 **浏览器内 API 调用** 方案，核心思路：

1. **登录态初始化**：注入 Cookie 后先访问抖音首页，建立完整会话
2. **视频详情**：`GET /aweme/v1/web/aweme/detail/?aweme_id=xxx`
3. **评论列表**：`GET /aweme/v1/web/comment/list/?aweme_id=xxx&cursor=N&count=20`（分页拉取）
4. **子评论**：`GET /aweme/v1/web/comment/list/reply/?comment_id=xxx`

**优势**：浏览器内 `fetch()` 调用自动处理 `a_bogus` 签名，无需本地计算加密参数。结构化 JSON 返回，数据完整度高。

**注意事项**：
- 抖音 Cookie 有效期较短（通常 1-7 天），过期需重新获取
- 单个视频爬取风险低；批量爬取建议间隔 10-20 秒/视频
- 评论数超过 200 条时自动分页拉取

### 小红书特殊处理
- **web_session 动态变化**：每个笔记链接有对应的 web_session，不能用固定 cookie
- **推荐方案**：`--xhs-user-data-dir` 传入 Chrome 用户数据目录，浏览器自动管理登录态
- **备用方案**：visible 模式（`--headed`），手动登录后自动获取 cookie
- **风控拦截**：headless 模式会被识别为"IP存在风险"，必须使用 visible Chrome

## 技术依赖

### 原有依赖
- python-docx
- openpyxl
- matplotlib
- pandas
- numpy

### 新增依赖（爬虫模式）
- playwright（浏览器自动化）
- opencv-python（视频帧提取）
- jieba（中文分词+TF-IDF热词）
- anthropic（Claude Vision API，视频分析需要）

### 安装命令
```bash
# 原有依赖
pip install python-docx openpyxl matplotlib pandas numpy

# 爬虫模式新增
pip install playwright opencv-python jieba anthropic
playwright install chromium
```

## 注意事项

- Excel文件第3行为列名行，第4行起为数据行（与蒲公英标准导出格式一致）
- 图表使用SimHei/Microsoft YaHei字体，确保系统中已安装中文字体
- 大数据量（3000+行×180+列）使用pandas处理，避免openpyxl逐行遍历
- JSON序列化时注意numpy类型转换

### 爬虫模式注意事项
- **小红书必须使用 visible Chrome**（headless 会被风控拦截）
- **推荐**：使用 `--xhs-user-data-dir` 参数传入 Chrome profile 路径，自动加载登录态
- 小红书 Cookie 有效期通常 1-7 天，过期需重新获取
- 抖音爬评论必须提供 Cookie（`ttwid` + `sessionid`）
- 抖音视频 URL 有时效性，需在会话有效期内下载
- 视频分析需要 ANTHROPIC_API_KEY，无 API Key 时跳过视频分析继续执行
- 评论分析为本地规则+关键词，不依赖外部 API
- 单篇笔记最多抓取 200 条评论（可通过 --max-comments 调整）
- 各平台反爬策略可能更新，如遇封禁请降低爬取频率
- B站视频为 DASH 分片格式，下载可能较慢
