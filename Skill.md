---
name: xhs-review
description: 小红书/多平台投放数据复盘 — 输入Excel数据文件或笔记URL，自动生成带图表的Word复盘报告。支持蒲公英格式、多平台达人合作表、以及基于爬虫的内容分析（评论舆情+视频内容）
---

# 小红书/多平台投放复盘 Skill

## 功能

根据投放数据Excel文件**或**笔记URL列表，自动完成数据分析、图表生成和Word报告组装，产出可直接汇报的复盘文档。

**新增（v2.1）**：支持通过 Playwright 爬取小红书笔记页面，自动分析评论区舆情和视频内容。

## 用法

### 模式1：Excel 数据文件（原有模式）
```bash
python ~/.claude/skills/xhs-review/scripts/run_pipeline.py <Excel数据文件> <品牌名称> [输出目录]
```

### 模式2：爬虫模式（新增）
```bash
python ~/.claude/skills/xhs-review/scripts/run_pipeline.py crawl <URL文件> \
  --cookie "a1=xxx; webId=yyy; web_session=zzz" \
  --brand 品牌名 \
  [--output 输出目录] \
  [--llm-config config/llm_config.json] \
  [--max-comments 200] \
  [--max-notes 0] \
  [--headed]
```

URL 文件格式：每行一个笔记 URL，空行和 `#` 开头的注释行自动跳过。
```
# 竞品笔记
https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6
https://www.xiaohongshu.com/explore/64b2c3d4e5f6a7
```

### Cookie 获取方式
1. 浏览器打开小红书网页版 → 登录
2. F12 → Application → Cookies → `.xiaohongshu.com`
3. 复制 `a1`、`webId`、`web_session` 等 key 的值，用 `; ` 拼接

### 分步执行
```bash
# 1. 爬取笔记
python ~/.claude/skills/xhs-review/scripts/crawl_notes.py urls.txt --cookie "xxx" --output ./output

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

## 输入要求

- **数据文件**：.xlsx格式，支持蒲公英标准导出或多sheet达人合作表
- **URL文件**：每行一个小红书笔记 URL
- **Cookie**：小红书登录态 Cookie 字符串
- **品牌名称**：用于报告标题和命名
- **输出目录**：可选，默认与数据文件同目录

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

使用前需设置环境变量：`export ANTHROPIC_API_KEY=sk-ant-xxx`

评论分析不依赖 LLM，使用本地规则+关键词即可完成。

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

即使列名略有差异，只要包含上述关键词即可自动识别。

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

多平台周复盘版本还包含：平台对比、切角分析、周对比、异常数据排查。

## 核心计算规则

### CPM/CPE 计算
- **CPM = 总成本 / 总播放 × 1000**（用聚合总量计算，不用每行CPM的平均值）
- **CPE = 总成本 / 总互动**（用聚合总量计算）
- Excel表格中的CPM/CPE/CTR总计行通常已是预计算平均值，但报告中应重新用总量计算以获得更准确的平台/品类级效率

### 跨平台指标统一
- 小红书的「曝光量」等价于视频号/抖音的「播放量」，在分析中统一映射为 `plays` 字段
- 这样可以统一比较不同平台的内容传播规模

## 异常数据处理

自动检测并排除以下异常数据行，不参与CPM/CPE等指标计算：

1. **CPM异常**：CPM > 中位数×10倍 且 > 5000元绝对值（通常是数据未沉淀）
2. **CPE异常**：CPE > 中位数×20倍 且 > 500元绝对值
3. **数据未沉淀**：播放/曝光 < 5次 但有成本

被排除的数据在报告中「数据概览」部分单独列出，说明排除原因。

## 适用场景

- 小红书蒲公英商单数据复盘（任意品牌）
- 多平台投放数据对比（视频号/抖音/小红书）
- 品牌月度/季度/活动投放总结
- 品类投放效率分析
- 达人投放策略评估与周度跟踪
- **竞品笔记内容分析**（爬虫模式）
- **评论舆情监控**（爬虫模式）
- **视频内容切角分析**（爬虫模式 + LLM）

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
- 如列名行位置不同，可修改 `analyze_data.py` 中的 `header_row` 参数
- 图表使用SimHei/Microsoft YaHei字体，确保系统中已安装中文字体
- 多平台数据文件中，小红书sheet的第一列通常为"红书"或"小红书"，视频号/抖音同理
- 大数据量（3000+行×180+列）使用pandas处理，避免openpyxl逐行遍历
- JSON序列化时注意numpy类型转换，需要先将 numpy.int64/numpy.float64 转为Python原生类型

### 爬虫模式注意事项
- 爬取频率已内置人体行为模拟（3~8秒随机间隔），不建议修改为更快速度
- Cookie 有效期通常 1-7 天，过期需重新获取
- 视频分析需要 ANTHROPIC_API_KEY，无 API Key 时跳过视频分析继续执行
- 评论分析为本地规则+关键词，不依赖外部 API
- 单篇笔记最多抓取 200 条评论（可通过 --max-comments 调整）
- 小红书反爬策略可能更新，如遇封禁请降低爬取频率
