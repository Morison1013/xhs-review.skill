# -*- coding: utf-8 -*-
"""
build_report.py — 组装Word报告，嵌入图表和表格
"""
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.enum.table import WD_TABLE_ALIGNMENT
import json
import sys
import os
import datetime
import glob

def set_cell_shading(cell, color):
    shading_elm = cell._tc.get_or_add_tcPr()
    shading = shading_elm.makeelement(qn('w:shd'), {
        qn('w:val'): 'clear', qn('w:color'): 'auto', qn('w:fill'): color
    })
    shading_elm.append(shading)

def add_styled_table(doc, headers, rows, col_widths=None, header_color='1F4E79'):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(headers):
        cell = table.rows[0].cells[j]
        cell.text = str(h)
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.size = Pt(10)
                run.font.bold = True
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                run.font.name = '微软雅黑'
                run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        set_cell_shading(cell, header_color)
    for i, row_data in enumerate(rows):
        for j, val in enumerate(row_data):
            cell = table.rows[i + 1].cells[j]
            cell.text = str(val)
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9)
                    run.font.name = '微软雅黑'
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            if i % 2 == 1:
                set_cell_shading(cell, 'E8F0FE')
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Cm(w)

def add_heading_styled(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = '微软雅黑'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        if level == 1:
            run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        elif level == 2:
            run.font.color.rgb = RGBColor(0x2E, 0x75, 0xB6)

def add_insight(doc, text, prefix='关键洞察：'):
    p = doc.add_paragraph()
    run1 = p.add_run(prefix)
    run1.font.bold = True
    run1.font.size = Pt(10)
    run1.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
    run1.font.name = '微软雅黑'
    run1._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    run2 = p.add_run(text)
    run2.font.size = Pt(10)
    run2.font.name = '微软雅黑'
    run2._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    p.paragraph_format.left_indent = Cm(0.5)

def add_centered_image(doc, image_path, width_inch=6.0, caption=''):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(image_path, width=Inches(width_inch))
    if caption:
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_cap = p_cap.add_run(caption)
        run_cap.font.size = Pt(9)
        run_cap.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        run_cap.font.italic = True
        run_cap.font.name = '微软雅黑'
        run_cap._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

def fmt(n):
    if n >= 1e8: return f'{n/1e8:.2f}亿'
    elif n >= 1e4: return f'{n/1e4:.1f}万'
    return f'{n:,.0f}'

def to_num(v):
    """Convert JSON-loaded value to proper numeric type"""
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return v
    return v

def build_report(json_path, chart_dir, output_path, brand_name=''):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Normalize all JSON values to proper types
    data['meta'] = {k: to_num(v) for k, v in data['meta'].items()}
    data['core_metrics'] = {k: to_num(v) for k, v in data['core_metrics'].items()}
    data['traffic_structure'] = {k: to_num(v) for k, v in data['traffic_structure'].items()}
    data['conversion'] = {k: to_num(v) for k, v in data['conversion'].items()}
    # Nested dicts
    for section in ['content_types', 'traffic_sources', 'components']:
        if section in data:
            for k, v in data[section].items():
                if isinstance(v, dict):
                    data[section][k] = {kk: to_num(vv) for kk, vv in v.items()}
                else:
                    data[section][k] = to_num(v)
    # List items
    for section in ['spu_top', 'proj_top', 'top_reads', 'top_cost']:
        if section in data:
            data[section] = [{kk: to_num(vv) for kk, vv in item.items()} for item in data[section]]
    # Fan tiers (nested dict)
    if 'fan_tiers' in data:
        for k, v in data['fan_tiers'].items():
            if isinstance(v, dict):
                data['fan_tiers'][k] = {kk: to_num(vv) for kk, vv in v.items()}
    # Health (nested dict)
    if 'health' in data:
        for k, v in data['health'].items():
            if isinstance(v, dict):
                data['health'][k] = {kk: to_num(vv) for kk, vv in v.items()}

    doc = Document()
    style = doc.styles['Normal']
    style.font.name = '微软雅黑'
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    for section in doc.sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.18)
        section.right_margin = Cm(3.18)

    core = data['core_metrics']
    traffic = data['traffic_structure']
    sources = data['traffic_sources']
    content = data['content_types']
    spu_top = data['spu_top']
    proj_top = data['proj_top']
    tiers = data['fan_tiers']
    health = data['health']
    conv = data['conversion']
    comps = data['components']
    meta = data['meta']
    top_reads = data['top_reads']
    top_cost = data['top_cost']

    brand = brand_name or '品牌'

    # ========== COVER ==========
    for _ in range(6): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'{brand}小红书投放复盘SOP')
    run.font.size = Pt(28); run.font.bold = True; run.font.color.rgb = RGBColor(0x1F,0x4E,0x79)
    run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    for text, size, color in [
        (f'品牌：{brand}', 14, (0x55,0x55,0x55)),
        (f'样本量：{int(meta["total_notes"]):,}篇笔记 | {int(meta["video_count"])+int(meta["image_count"])}篇有效数据', 12, (0x55,0x55,0x55)),
        (f'生成日期：{datetime.date.today().strftime("%Y年%m月%d日")}', 11, (0x88,0x88,0x88)),
    ]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text); run.font.size = Pt(size); run.font.color.rgb = RGBColor(*color)
        run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_page_break()

    # ========== TOC ==========
    add_heading_styled(doc, '目录', level=1)
    toc = ['一、数据概览', '二、核心效果总览', '  2.1 曝光&阅读&互动', '  2.2 流量来源结构',
           '  2.3 自然流量渠道分布', '三、多维度拆解分析', '  3.1 内容形式对比',
           '  3.2 SPU维度表现', '  3.3 合作项目成本TOP', '  3.4 粉丝梯队效率',
           '  3.5 健康vs异常笔记', '四、转化漏斗分析', '五、组件效果分析',
           '六、TOP笔记盘点', '七、复盘总结&行动建议']
    # Add crawl-mode sections if data exists
    has_comment = 'comment_analysis' in data
    has_video = 'video_analysis' in data
    has_crawl_data = 'crawled_data_summary' in data
    if has_crawl_data:
        toc.insert(1, '  平台分布')
    if has_comment:
        toc.extend(['八、评论舆情分析', '  8.1 情感分布', '  8.2 评论子类别', '  8.3 热门关键词'])
    if has_video:
        toc.extend(['九、视频内容深度分析'])
    for item in toc:
        p = doc.add_paragraph(item)
        for run in p.runs: run.font.size = Pt(11); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_page_break()

    # ========== SEC 1 ==========
    add_heading_styled(doc, '一、数据概览', level=1)

    # Platform distribution (crawl mode)
    platform_info = data.get('crawled_data_summary', {}).get('platforms', {})
    if platform_info:
        platform_rows = []
        platform_names = {'xiaohongshu': '小红书', 'bilibili': 'B站', 'douyin': '抖音'}
        for p, count in platform_info.items():
            platform_rows.append([platform_names.get(p, p), count])
        add_styled_table(doc, ['平台', '笔记数'], platform_rows, col_widths=[4, 10])
        doc.add_paragraph()

    add_styled_table(doc, ['指标', '数值'], [
        ['品牌', brand],
        ['总笔记数', f'{int(meta["total_notes"]):,}篇（图文{int(meta["image_count"]):,}篇 / 视频{int(meta["video_count"]):,}篇）'],
        ['异常笔记', f'{int(meta["abnormal_count"]):,}篇'],
        ['明星合作', f'{int(meta["star_count"]):,}篇'],
    ], col_widths=[4, 10])
    doc.add_paragraph()

    # ========== SEC 2 ==========
    add_heading_styled(doc, '二、核心效果总览', level=1)
    add_heading_styled(doc, '2.1 曝光 & 阅读 & 互动', level=2)
    add_styled_table(doc, ['指标', '数值'], [
        ['总曝光量', fmt(core['total_exposure'])],
        ['总阅读量', fmt(core['total_reads'])],
        ['均阅读', f'{core["avg_reads"]:,.0f}/篇'],
        ['总互动量', fmt(core['total_interactions'])],
        ['— 点赞', fmt(core['total_likes'])],
        ['— 收藏', fmt(core['total_favorites'])],
        ['— 评论', fmt(core['total_comments'])],
        ['— 分享', fmt(core['total_shares'])],
        ['— 关注', fmt(core['total_follows'])],
        ['均互动率', f'{core["avg_interact_rate"]*100:.2f}%'],
        ['CPE', f'{core["cpe"]:.2f}元'],
        ['CPM', f'{core["cpm"]:.2f}元'],
        ['CPC', f'{core["cpc"]:.2f}元'],
    ], col_widths=[4, 10])
    doc.add_paragraph()

    add_heading_styled(doc, '2.2 流量来源结构', level=2)
    chart1 = os.path.join(chart_dir, '01_traffic_source_donut.png')
    if os.path.exists(chart1):
        add_centered_image(doc, chart1, 6.0, '图1：流量来源结构')
    doc.add_paragraph()
    add_styled_table(doc, ['来源类型', '曝光占比', '阅读占比'], [
        ['推广流量', f'{traffic["promo_exposure_pct"]:.1f}%', f'{traffic["promo_reads_pct"]:.1f}%'],
        ['自然流量', f'{traffic["nat_exposure_pct"]:.1f}%', f'{traffic["nat_reads_pct"]:.1f}%'],
        ['加热流量', f'{traffic["heat_exposure"]/traffic["promo_exposure"]*100 if traffic["promo_exposure"]>0 else 0:.1f}%',
         f'{traffic["heat_reads"]/traffic["promo_reads"]*100 if traffic["promo_reads"]>0 else 0:.1f}%'],
    ], col_widths=[4, 5, 5])
    doc.add_paragraph()
    add_insight(doc, f'推广曝光占比{traffic["promo_exposure_pct"]:.1f}%，加热流量{"未启用" if traffic["heat_exposure"] < 100 else "已启用"}。')
    doc.add_paragraph()

    add_heading_styled(doc, '2.3 自然流量渠道分布', level=2)
    chart2 = os.path.join(chart_dir, '02_natural_channel_bar.png')
    if os.path.exists(chart2):
        add_centered_image(doc, chart2, 6.0, '图2：自然流量渠道分布')
    doc.add_paragraph()
    exp_s = sources['exp']
    read_s = sources['read']
    add_styled_table(doc, ['渠道'] + [f'{k}占比' for k in ['曝光', '阅读']],
        [[ch, f'{exp_s.get(ch,0):.1f}%', f'{read_s.get(ch,0):.1f}%']
         for ch in ['发现页','搜索页','个人页','关注页','附近页','其他']],
        col_widths=[3, 5, 5])
    doc.add_paragraph()
    top_channel = max(exp_s.items(), key=lambda x:x[1])
    add_insight(doc, f'{top_channel[0]}是核心自然流量入口（曝光{top_channel[1]:.1f}%），搜索页仅占{exp_s.get("搜索页",0):.1f}%。')
    doc.add_paragraph()

    # ========== SEC 3 ==========
    add_heading_styled(doc, '三、多维度拆解分析', level=1)

    add_heading_styled(doc, '3.1 内容形式对比', level=2)
    chart4 = os.path.join(chart_dir, '04_type_comparison.png')
    if os.path.exists(chart4):
        add_centered_image(doc, chart4, 6.5, '图3：内容形式核心指标对比')
    doc.add_paragraph()
    type_rows = []
    for t, d in content.items():
        type_rows.append([t, f'{int(d["count"]):,}篇', f'{d["avg_reads"]:,.0f}',
            f'{d["irate"]:.2f}%', f'{d["cpm"]:.1f}元', f'{d["cpe"]:.2f}元'])
    if type_rows:
        add_styled_table(doc, ['类型', '笔记数', '均阅读', '互动率', 'CPM', 'CPE'], type_rows)
    doc.add_paragraph()
    if len(content) >= 2:
        items = list(content.items())
        t1n, t1d = items[0]; t2n, t2d = items[1]
        ratio = t2d['avg_reads'] / t1d['avg_reads'] if t1d['avg_reads'] > 0 else 0
        add_insight(doc, f'{t2n}均阅读是{t1n}的{ratio:.1f}倍，CPE{"更低" if t2d["cpe"] < t1d["cpe"] else "更高"}。')
    doc.add_paragraph()

    add_heading_styled(doc, '3.2 SPU维度表现', level=2)
    chart5 = os.path.join(chart_dir, '05_spu_scatter.png')
    if os.path.exists(chart5):
        add_centered_image(doc, chart5, 7.0, '图4：SPU成本vs互动率散点图')
    doc.add_paragraph()
    if spu_top:
        add_styled_table(doc, ['SPU', '笔记数', '阅读量(万)', '互动率', '成本(万)'],
            [[s['name'][:30].replace('\t',' '), s['count'], f'{s["reads"]/1e4:.1f}', f'{s["irate"]:.2f}%', f'{s["cost"]/1e4:.1f}']
             for s in spu_top[:5]], col_widths=[5, 2, 2.5, 2, 2.5])
    doc.add_paragraph()
    if spu_top and len(spu_top) > 1:
        best = min(spu_top[1:], key=lambda x: x['cost']/x['irate'] if x['irate']>0 else 999)
        worst = max(spu_top[1:], key=lambda x: x['cost'])
        add_insight(doc, f'{worst["name"][:20]}投入最大但互动率偏低，{best["name"][:20]}性价比最优。')
    doc.add_paragraph()

    add_heading_styled(doc, '3.3 合作项目成本TOP', level=2)
    chart6 = os.path.join(chart_dir, '06_project_cost_top10.png')
    if os.path.exists(chart6):
        add_centered_image(doc, chart6, 7.0, '图5：项目成本TOP10')
    doc.add_paragraph()
    if proj_top:
        add_styled_table(doc, ['项目', '笔记数', '成本(万)', 'CPM', 'CPE', '互动率'],
            [[p['name'][:35].replace('\t',' '), p['count'], f'{p["cost"]/1e4:.1f}', f'{p["cpm"]:.1f}', f'{p["cpe"]:.1f}', f'{p["irate"]:.2f}%']
             for p in proj_top[:5]], col_widths=[5, 1.5, 1.8, 1.5, 1.5, 1.5])
    doc.add_paragraph()
    if proj_top:
        worst_proj = proj_top[0]
        add_insight(doc, f'{worst_proj["name"][:30]}成本最高（{worst_proj["cost"]/1e4:.1f}万），CPE达{worst_proj["cpe"]:.1f}元。')
    doc.add_paragraph()

    add_heading_styled(doc, '3.4 粉丝梯队效率', level=2)
    chart7 = os.path.join(chart_dir, '07_cpe_fan_tier.png')
    if os.path.exists(chart7):
        add_centered_image(doc, chart7, 6.5, '图6：粉丝梯队CPE趋势')
    doc.add_paragraph()
    if tiers:
        tier_rows = []
        for t, d in tiers.items():
            tier_rows.append([t, d['count'], f'{d["avg_reads"]:,.0f}',
                f'{d["irate"]:.2f}%', f'{d["cpe"]:.2f}', f'{d["cost_pct"]:.1f}%'])
        add_styled_table(doc, ['粉丝区间', '笔记数', '均阅读', '互动率', 'CPE', '成本占比'], tier_rows)
    doc.add_paragraph()
    if tiers:
        tier_list = list(tiers.items())
        best_tier = min(tier_list, key=lambda x: x[1]['cpe'] if x[1]['cpe'] > 0 else 999)
        worst_tier = max(tier_list, key=lambda x: x[1]['cpe'])
        add_insight(doc, f'{best_tier[0]}区间CPE最优（{best_tier[1]["cpe"]:.2f}元），{worst_tier[0]}区间CPE最高（{worst_tier[1]["cpe"]:.2f}元）。')
    doc.add_paragraph()

    add_heading_styled(doc, '3.5 健康 vs 异常笔记', level=2)
    if health:
        health_rows = []
        for h, d in health.items():
            health_rows.append([h, d['count'], f'{d["avg_reads"]:,.0f}', fmt(d['total_reads']), f'{d["pct"]:.1f}%'])
        add_styled_table(doc, ['状态', '笔记数', '均阅读', '总阅读', '占比'], health_rows)
        doc.add_paragraph()
        if '异常' in health and '健康' in health:
            ratio_h = health['异常']['avg_reads'] / health['健康']['avg_reads'] if health['健康']['avg_reads'] > 0 else 0
            add_insight(doc, f'异常笔记均阅读仅为健康笔记的{ratio_h*100:.0f}%。')
    doc.add_paragraph()

    # ========== SEC 4 ==========
    add_heading_styled(doc, '四、转化漏斗分析', level=1)
    if conv and conv.get('count', 0) > 0:
        p = doc.add_paragraph()
        run = p.add_run(f'有归因数据笔记数：{conv["count"]}篇（占总笔记{conv["count"]/meta["total_notes"]*100:.1f}%）')
        run.font.size = Pt(10); run.font.italic = True; run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        doc.add_paragraph()
        chart8 = os.path.join(chart_dir, '08_conversion_funnel.png')
        if os.path.exists(chart8):
            add_centered_image(doc, chart8, 7.0, '图7：站外转化漏斗')
        doc.add_paragraph()
        add_styled_table(doc, ['环节', 'UV', '转化率'], [
            ['站外活跃行为', f'{conv["active_uv"]:,.0f}', '—'],
            ['→ 新访客', f'{conv["new_visitor_uv"]:,.0f}', f'{conv["new_visitor_uv"]/conv["active_uv"]*100:.1f}%' if conv["active_uv"]>0 else '—'],
            ['→ 搜索进店', f'{conv["search_uv"]:,.0f}', f'{conv["search_uv"]/conv["active_uv"]*100:.1f}%' if conv["active_uv"]>0 else '—'],
            ['→ 加购', f'{conv["cart_uv"]:,.0f}', f'{conv["cart_uv"]/conv["active_uv"]*100:.1f}%' if conv["active_uv"]>0 else '—'],
            ['→ 收藏商品', f'{conv["fav_product_uv"]:,.0f}', f'{conv["fav_product_uv"]/conv["active_uv"]*100:.1f}%' if conv["active_uv"]>0 else '—'],
            ['→ 成交', f'{conv["deal_uv"]:,.0f}', f'{conv["deal_uv"]/conv["active_uv"]*100:.2f}%' if conv["active_uv"]>0 else '—'],
        ], col_widths=[5, 4, 4])
        doc.add_paragraph()
        p = doc.add_paragraph()
        run = p.add_run(f'平均购买率：{conv["avg_purchase_rate"]:.2f}% | 平均加购率：{conv["avg_cart_rate"]:.2f}% | 加购→成交：{conv["cart_to_deal_pct"]:.2f}%')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        doc.add_paragraph()
        add_insight(doc, f'归因覆盖率仅{conv["count"]/meta["total_notes"]*100:.1f}%，大部分笔记无法衡量转化效果。')
    doc.add_paragraph()

    # ========== SEC 5 ==========
    add_heading_styled(doc, '五、组件效果分析', level=1)
    chart9 = os.path.join(chart_dir, '09_component_ctr.png')
    if os.path.exists(chart9):
        add_centered_image(doc, chart9, 6.0, '图8：各组件CTR对比')
    doc.add_paragraph()
    if comps:
        comp_rows = []
        for c, d in comps.items():
            comp_rows.append([c, fmt(d['exp']), fmt(d['click']), f'{d["ctr"]:.2f}%'])
        add_styled_table(doc, ['组件类型', '曝光', '点击', 'CTR'], comp_rows)
    doc.add_paragraph()
    if comps:
        best_comp = max(comps.items(), key=lambda x: x[1]['ctr'])
        add_insight(doc, f'{best_comp[0]}CTR最高（{best_comp[1]["ctr"]:.2f}%），应扩大使用范围。')
    doc.add_paragraph()

    # ========== SEC 6 ==========
    add_heading_styled(doc, '六、TOP笔记盘点', level=1)
    add_heading_styled(doc, '6.1 阅读量TOP3', level=2)
    for note in top_reads[:3]:
        p = doc.add_paragraph()
        run = p.add_run(f'【{note["title"]}】')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        p2 = doc.add_paragraph(f'阅读{fmt(note["reads"])} | 互动{note["interact"]:.0f} | 互动率{note["irate"]:.1f}% | {note["type"]} | 粉丝{fmt(note["fans"])} | 成本{note["cost"]:.0f}')
        for run in p2.runs: run.font.size = Pt(9); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_paragraph()

    add_heading_styled(doc, '6.2 成本TOP3', level=2)
    for note in top_cost[:3]:
        p = doc.add_paragraph()
        run = p.add_run(f'【{note["title"]}】')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        p2 = doc.add_paragraph(f'成本{note["cost"]:,.0f} | CPE {note["cpe"]:.2f}元 | {note["type"]}')
        for run in p2.runs: run.font.size = Pt(9); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_paragraph()
    if top_cost and top_cost[0]['cpe'] > core['cpe'] * 5:
        add_insight(doc, f'成本TOP笔记CPE高达{top_cost[0]["cpe"]:.2f}元，远超均值{core["cpe"]:.2f}元，需排查。')
    doc.add_paragraph()

    # ========== SEC 7 ==========
    add_heading_styled(doc, '七、复盘总结 & 行动建议', level=1)

    add_heading_styled(doc, '7.1 成功经验', level=2)
    # Auto-generate success points from data
    successes = []
    if len(content) >= 2:
        items = list(content.items())
        better = max(items, key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe',0) > 0 else -999, default=items[0])
        worse = min(items, key=lambda x: x[1].get('cpe', 0) if x[1].get('cpe',0) > 0 else 999)
        successes.append(f'{worse[0]}内容效率更优（CPE {worse[1]["cpe"]:.2f}元 vs {better[0]} {better[1]["cpe"]:.2f}元）')
    if tiers:
        best_t = min(tiers.items(), key=lambda x: x[1]['cpe'] if x[1]['cpe'] > 0 else 999)
        successes.append(f'{best_t[0]}粉丝区间达人CPE最优（{best_t[1]["cpe"]:.2f}元）')
    if spu_top and len(spu_top) > 1:
        efficient = min(spu_top[1:], key=lambda x: x['cost']/x['irate'] if x['irate'] > 0 else 999)
        successes.append(f'{efficient["name"][:20]}互动率{efficient["irate"]:.2f}%，性价比突出')
    if comps:
        best_c = max(comps.items(), key=lambda x: x[1]['ctr'])
        successes.append(f'{best_c[0]}CTR达{best_c[1]["ctr"]:.2f}%，转化驱动效果好')
    for s in successes:
        p = doc.add_paragraph(s, style='List Bullet')
        for run in p.runs: run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_paragraph()

    add_heading_styled(doc, '7.2 问题 & 改进方向', level=2)
    issues = []
    if tiers:
        worst_t = max(tiers.items(), key=lambda x: x[1]['cpe'])
        if worst_t[1]['cpe'] > core['cpe'] * 3:
            issues.append([f'{worst_t[0]}达人CPE过高（{worst_t[1]["cpe"]:.2f}元）',
                f'互动率仅{worst_t[1]["irate"]:.2f}%',
                f'缩减{worst_t[0]}达人投放，预算转移至高效区间'])
    if traffic['heat_exposure'] < 100:
        issues.append(['加热流量为0%', '无加热放大优质笔记', '启用聚光加热，对TOP20%笔记加热放大'])
    if exp_s.get('搜索页', 0) < 15:
        issues.append([f'搜索流量占比仅{exp_s.get("搜索页",0):.1f}%', 'SEO搜索心智不足', '优化笔记标题/标签/正文关键词'])
    if conv and conv.get('count', 0) / meta['total_notes'] < 0.3:
        issues.append([f'归因覆盖率仅{conv["count"]/meta["total_notes"]*100:.1f}%', '大部分笔记无法衡量转化', '推动全量笔记绑定店铺归因'])
    if meta['abnormal_count'] > meta['total_notes'] * 0.03:
        issues.append([f'异常笔记{meta["abnormal_count"]}篇({meta["abnormal_count"]/meta["total_notes"]*100:.1f}%)', '影响整体效果', '建立异常监控日报，24h内预警'])
    if len(content) >= 2:
        items = list(content.items())
        low_eff = max(items, key=lambda x: x[1].get('cpe', 0))
        high_eff = min(items, key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe',0) > 0 else 999)
        if low_eff[1]['cpe'] > high_eff[1]['cpe'] * 2:
            issues.append([f'{low_eff[0]}占比{low_eff[1]["count"]/meta["total_notes"]*100:.1f}%但效率低',
                f'CPE {low_eff[1]["cpe"]:.2f}元远高于{high_eff[0]}',
                f'逐步将{low_eff[0]}占比降低'])
    if issues:
        add_styled_table(doc, ['问题', '影响', '改进建议'], issues, col_widths=[4.5, 4, 5.5])
    doc.add_paragraph()

    add_heading_styled(doc, '7.3 下期策略建议', level=2)
    strategies = []
    if tiers:
        best_tier = min(tiers.items(), key=lambda x: x[1]['cpe'] if x[1]['cpe'] > 0 else 999)
        strategies.append(('预算分配', f'优先{best_tier[0]}区间达人（CPE {best_tier[1]["cpe"]:.2f}元）'))
    if len(content) >= 2:
        items = list(content.items())
        best_type = min(items, key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe',0) > 0 else 999)
        strategies.append(('内容形式', f'加大{best_type[0]}投入占比'))
    if spu_top:
        efficient_spu = min(spu_top[1:], key=lambda x: x['cost']/x['irate'] if x['irate'] > 0 else 999)
        strategies.append(('SPU优先级', efficient_spu['name'][:30]))
    if comps:
        best_comp = max(comps.items(), key=lambda x: x[1]['ctr'])
        strategies.append(('组件策略', f'{best_comp[0]}全覆盖（目标使用率>80%）'))
    if traffic['heat_exposure'] < 100:
        strategies.append(('加热策略', '启用聚光加热，目标自然/推广阅读比优化至55/45'))
    for title, desc in strategies:
        p = doc.add_paragraph()
        run = p.add_run(title + '：')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        run2 = p.add_run(desc)
        run2.font.size = Pt(10); run2.font.name = '微软雅黑'; run2._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_paragraph()

    # ========== SEC 8: Comment Analysis ==========
    if 'comment_analysis' in data:
        ca = data['comment_analysis']
        add_heading_styled(doc, '八、评论舆情分析', level=1)

        # 8.1 Sentiment
        add_heading_styled(doc, '8.1 情感分布', level=2)
        chart10 = os.path.join(chart_dir, '10_sentiment_pie.png')
        if os.path.exists(chart10):
            add_centered_image(doc, chart10, 5.5, '图10：评论情感分布')
        doc.add_paragraph()

        if 'sentiment_distribution' in ca:
            sd = ca['sentiment_distribution']
            add_styled_table(doc, ['情感', '评论数', '占比'], [
                ['正面', sd.get('positive', {}).get('count', 0), f'{sd.get("positive", {}).get("pct", 0):.1f}%'],
                ['中性', sd.get('neutral', {}).get('count', 0), f'{sd.get("neutral", {}).get("pct", 0):.1f}%'],
                ['负面', sd.get('negative', {}).get('count', 0), f'{sd.get("negative", {}).get("pct", 0):.1f}%'],
            ], col_widths=[3, 4, 4])
        doc.add_paragraph()

        # Representative comments
        rep = ca.get('representative_comments', {})
        if rep.get('positive'):
            add_heading_styled(doc, '代表性正面评论', level=3)
            for rc in rep['positive'][:3]:
                p = doc.add_paragraph()
                run = p.add_run(f'「{rc["text"]}」')
                run.font.size = Pt(9); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
                run2 = p.add_run(f'  👍 {rc.get("likes", 0)}')
                run2.font.size = Pt(8); run2.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        if rep.get('negative'):
            add_heading_styled(doc, '代表性负面评论', level=3)
            for rc in rep['negative'][:3]:
                p = doc.add_paragraph()
                run = p.add_run(f'「{rc["text"]}」')
                run.font.size = Pt(9); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
                run.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
        if rep.get('questions'):
            add_heading_styled(doc, '用户高频问题', level=3)
            for rc in rep['questions'][:3]:
                p = doc.add_paragraph()
                run = p.add_run(f'❓ {rc["text"]}')
                run.font.size = Pt(9); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        doc.add_paragraph()

        # 8.2 Sub-categories
        add_heading_styled(doc, '8.2 评论子类别', level=2)
        chart11 = os.path.join(chart_dir, '11_comment_categories_bar.png')
        if os.path.exists(chart11):
            add_centered_image(doc, chart11, 6.5, '图11：评论子类别分布')
        doc.add_paragraph()

        if 'sub_categories' in ca:
            cat_rows = []
            for cat_name, cat_data in sorted(ca['sub_categories'].items(), key=lambda x: x[1]['count'], reverse=True):
                cat_rows.append([cat_name, cat_data['count'], f'{cat_data["pct"]:.1f}%'])
            add_styled_table(doc, ['子类别', '评论数', '占比'], cat_rows, col_widths=[4, 3, 3])
        doc.add_paragraph()

        # Key insight
        if ca.get('sub_categories'):
            top_cat = max(ca['sub_categories'].items(), key=lambda x: x[1]['count'])
            add_insight(doc, f'用户最关注"{top_cat[0]}"（{top_cat[1]["count"]}条，{top_cat[1]["pct"]:.1f}%），这是内容切入的关键方向。')
        doc.add_paragraph()

        # 8.3 Keywords
        add_heading_styled(doc, '8.3 热门关键词', level=2)
        if 'keywords' in ca:
            kws = ca['keywords']
            if kws.get('tfidf_top'):
                kw_rows = []
                for kw in kws['tfidf_top'][:15]:
                    kw_rows.append([kw['word'], kw['count'], f'{kw["weight"]:.4f}'])
                add_styled_table(doc, ['关键词', '出现次数', 'TF-IDF权重'], kw_rows, col_widths=[3, 3, 4])
                doc.add_paragraph()
            if kws.get('ngram_top'):
                ng_rows = []
                for ng in kws['ngram_top'][:10]:
                    ng_rows.append([ng['phrase'], ng['count']])
                add_styled_table(doc, ['高频短语', '出现次数'], ng_rows, col_widths=[6, 4])
        doc.add_paragraph()

    # ========== SEC 9: Video Analysis ==========
    if 'video_analysis' in data:
        va = data['video_analysis']
        add_heading_styled(doc, '九、视频内容深度分析', level=1)

        if va.get('video_notes'):
            for idx, vn in enumerate(va['video_notes'], 1):
                add_heading_styled(doc, f'9.{idx} {vn.get("note_title", "视频笔记")}', level=2)

                # Content themes
                llm = vn.get('llm_analysis', {})
                if llm:
                    add_styled_table(doc, ['维度', '分析结果'], [
                        ['内容主题', ', '.join(llm.get('content_themes', []))],
                        ['视觉风格', ', '.join(llm.get('visual_style', []))],
                        ['叙事模式', llm.get('narrative_pattern', '')],
                        ['切入角度', llm.get('cutting_angle', '')],
                        ['核心卖点', ', '.join(llm.get('key_selling_points', []))],
                        ['目标受众', llm.get('target_audience', '')],
                        ['语气风格', llm.get('tone', '')],
                        ['开场抓人', llm.get('opening_hook', '')],
                    ], col_widths=[3, 11])
                    doc.add_paragraph()

                    if llm.get('cutting_angle'):
                        add_insight(doc, f'该笔记以"{llm["cutting_angle"]}"为切入点，目标受众为{llm.get("target_audience", "")}。')
                    doc.add_paragraph()

        # Summary across videos
        if len(va.get('video_notes', [])) > 1:
            add_heading_styled(doc, '9.0 视频内容总览', level=2)
            chart12 = os.path.join(chart_dir, '12_video_themes.png')
            if os.path.exists(chart12):
                add_centered_image(doc, chart12, 7.0, '图12：视频内容主题与视觉风格')
            doc.add_paragraph()

    # Footer
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('— 文档结束 —')
    run.font.size = Pt(10); run.font.color.rgb = RGBColor(0x99,0x99,0x99)
    run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'基于《小红书AI复盘新人SOP》模板 | SOP版本：v2.0（可复用版）')
    run.font.size = Pt(8); run.font.color.rgb = RGBColor(0xAA,0xAA,0xAA)
    run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    doc.save(output_path)
    print(f'报告已保存: {output_path}')

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(f"用法: python build_report.py <分析JSON> <图表目录> <输出docx路径> [品牌名]")
        sys.exit(1)
    brand = sys.argv[4] if len(sys.argv) > 4 else ''
    build_report(sys.argv[1], sys.argv[2], sys.argv[3], brand)
