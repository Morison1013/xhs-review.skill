# -*- coding: utf-8 -*-
"""
build_video_number_report.py — 视频号 Word 报告组装
导入 build_report.py 的样式工具函数，生成视频号专属报告
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

# Import utilities from build_report.py
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
from build_report import (
    add_styled_table, add_heading_styled, add_insight,
    add_centered_image, set_cell_shading
)


def fmt(n):
    if n >= 1e8: return f'{n/1e8:.2f}亿'
    elif n >= 1e4: return f'{n/1e4:.1f}万'
    return f'{n:,.0f}'


def to_num(v):
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

    # Normalize values
    data['meta'] = {k: to_num(v) for k, v in data['meta'].items()}
    data['core_metrics'] = {k: to_num(v) for k, v in data['core_metrics'].items()}
    data['engagement_detail'] = {k: to_num(v) for k, v in data.get('engagement_detail', {}).items()}
    data['completion_rate_stats'] = {k: to_num(v) for k, v in data.get('completion_rate_stats', {}).items()}
    data['mention_rate_stats'] = {k: to_num(v) for k, v in data.get('mention_rate_stats', {}).items()}
    data['predicted_vs_actual'] = {k: {kk: to_num(vv) for kk, vv in v.items()} for k, v in data.get('predicted_vs_actual', {}).items()}

    if 'pred_actual_rows' in data:
        data['pred_actual_rows'] = [{kk: to_num(vv) for kk, vv in item.items()} for item in data['pred_actual_rows']]

    for section in ['content_types', 'cooperation_formats', 'influencer_tiers', 'content_angles']:
        if section in data:
            for k, v in data[section].items():
                if isinstance(v, dict):
                    data[section][k] = {kk: to_num(vv) for kk, vv in v.items()}

    if 'date_trend' in data:
        for k, v in data['date_trend'].items():
            if isinstance(v, dict):
                data['date_trend'][k] = {kk: to_num(vv) for kk, vv in v.items()}

    if 'top_engagement' in data:
        data['top_engagement'] = [{kk: to_num(vv) for kk, vv in item.items()} for item in data['top_engagement']]

    core = data['core_metrics']
    engagement = data.get('engagement_detail', {})
    content_types = data.get('content_types', {})
    coop_formats = data.get('cooperation_formats', {})
    influencer_tiers = data.get('influencer_tiers', {})
    content_angles = data.get('content_angles', {})
    date_trend = data.get('date_trend', {})
    pred_vs_actual = data.get('predicted_vs_actual', {})
    completion_stats = data.get('completion_rate_stats', {})
    mention_stats = data.get('mention_rate_stats', {})
    top_engagement = data.get('top_engagement', [])
    meta = data['meta']

    brand = brand_name or '品牌'

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

    # ========== COVER ==========
    for _ in range(6): doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'{brand}视频号投放复盘SOP')
    run.font.size = Pt(28); run.font.bold = True; run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    for text, size, color in [
        (f'品牌：{brand}', 14, (0x55, 0x55, 0x55)),
        (f'样本量：{int(meta["total_notes"]):,}篇笔记', 12, (0x55, 0x55, 0x55)),
        (f'日期范围：{meta.get("date_range", "未知")}', 12, (0x55, 0x55, 0x55)),
        (f'生成日期：{datetime.date.today().strftime("%Y年%m月%d日")}', 11, (0x88, 0x88, 0x88)),
    ]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text); run.font.size = Pt(size); run.font.color.rgb = RGBColor(*color)
        run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_page_break()

    # ========== TOC ==========
    add_heading_styled(doc, '目录', level=1)
    toc = ['一、数据概览', '二、核心效果总览', '三、达人类型对比', '四、合作形式对比',
           '五、达人量级效果', '六、切角方向效果', '七、预估 vs 实际达成评价',
           '八、预估 vs 实际 CPM/CPE', '九、时间趋势', '十、完播率与提及率',
           '十一、TOP达人盘点', '十二、复盘总结 & 行动建议']
    for item in toc:
        p = doc.add_paragraph(item)
        for run in p.runs: run.font.size = Pt(11); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_page_break()

    # ========== 一、数据概览 ==========
    add_heading_styled(doc, '一、数据概览', level=1)
    add_styled_table(doc, ['指标', '数值'], [
        ['品牌', brand],
        ['平台', meta.get('platform', '视频号')],
        ['总笔记数', f'{int(meta["total_notes"]):,}篇'],
        ['日期范围', meta.get('date_range', '未知')],
        ['总成本', f'{meta.get("total_cost", 0):,.0f}元'],
    ], col_widths=[4, 10])
    doc.add_paragraph()

    # ========== 二、核心效果总览 ==========
    add_heading_styled(doc, '二、核心效果总览', level=1)

    add_styled_table(doc, ['指标', '数值'], [
        ['总曝光量', fmt(core['total_exposure'])],
        ['均曝光', f'{core["avg_exposure"]:,.0f}/篇'],
        ['总互动量', fmt(core['total_interaction'])],
        ['均互动', f'{core["avg_interaction"]:,.0f}/篇'],
        ['— 赞', fmt(engagement.get('total_likes', 0))],
        ['— 评论', fmt(engagement.get('total_comments', 0))],
        ['— 分享', fmt(engagement.get('total_shares', 0))],
        ['— 私密赞', fmt(engagement.get('total_private_likes', 0))],
        ['CPM', f'{core["cpm"]:.2f}元'],
        ['CPE', f'{core["cpe"]:.2f}元'],
    ], col_widths=[4, 10])
    doc.add_paragraph()

    # Chart 1: Engagement
    chart1 = os.path.join(chart_dir, '01_engagement_pie.png')
    if os.path.exists(chart1):
        add_centered_image(doc, chart1, 5.0, '图1：互动构成拆解')
    doc.add_paragraph()

    # Engagement detail table
    add_styled_table(doc, ['互动类型', '数量', '占比'], [
        ['赞', fmt(engagement.get('total_likes', 0)), f'{engagement.get("likes_pct", 0):.1f}%'],
        ['评论', fmt(engagement.get('total_comments', 0)), f'{engagement.get("comments_pct", 0):.1f}%'],
        ['分享', fmt(engagement.get('total_shares', 0)), f'{engagement.get("shares_pct", 0):.1f}%'],
        ['私密赞', fmt(engagement.get('total_private_likes', 0)), f'{engagement.get("private_likes_pct", 0):.1f}%'],
    ], col_widths=[3, 5, 5])
    doc.add_paragraph()

    # Engagement analysis summary
    eng_parts = []
    if engagement.get('shares_pct', 0) > 30:
        eng_parts.append(f'分享占比{engagement["shares_pct"]:.1f}%，为第一大互动来源，说明内容具有较强的社交传播属性，用户愿意将内容扩散给更多好友')
    if engagement.get('private_likes_pct', 0) > engagement.get('likes_pct', 0):
        eng_parts.append(f'私密赞占比{engagement["private_likes_pct"]:.1f}%高于公开赞{engagement.get("likes_pct", 0):.1f}%，视频号社交关系链中的"半熟人点赞"现象明显')
    if engagement.get('comments_pct', 0) < 5:
        eng_parts.append(f'评论仅占{engagement.get("comments_pct", 0):.1f}%，用户互动深度不足，建议在视频结尾增加引导评论的话术')
    for s in eng_parts:
        p = doc.add_paragraph()
        run = p.add_run(s)
        run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if eng_parts:
        doc.add_paragraph()

    # ========== 三、达人类型对比 ==========
    add_heading_styled(doc, '三、达人类型对比', level=1)

    chart2 = os.path.join(chart_dir, '02_content_type_comparison.png')
    if os.path.exists(chart2):
        add_centered_image(doc, chart2, 5.0, '图2：达人类型 CPE/CPM 对比')
    doc.add_paragraph()

    if content_types:
        ct_rows = []
        for t, d in sorted(content_types.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999):
            ct_rows.append([t, d['count'], f"{d['exposure']:,.0f}", f"{d['interaction']:,.0f}",
                f"{d['cost']:.0f}元", f"{d['cpm']:.2f}", f"{d['cpe']:.2f}"])
        add_styled_table(doc, ['达人类型', '笔记数', '总曝光', '总互动', '总成本', 'CPM', 'CPE'], ct_rows)
    doc.add_paragraph()

    # Auto insight
    if len(content_types) >= 2:
        items = list(content_types.items())
        best_ct = min(items, key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        worst_ct = max(items, key=lambda x: x[1].get('cpe', 0))
        add_insight(doc, f'{best_ct[0]}类型CPE最优（{best_ct[1]["cpe"]:.2f}元），{worst_ct[0]}类型CPE最高（{worst_ct[1]["cpe"]:.2f}元），相差{worst_ct[1]["cpe"]/best_ct[1]["cpe"]:.1f}倍。')
    doc.add_paragraph()

    # ========== 四、合作形式对比 ==========
    add_heading_styled(doc, '四、合作形式对比', level=1)

    if len(coop_formats) >= 2:
        chart3 = os.path.join(chart_dir, '03_coop_format_comparison.png')
        if os.path.exists(chart3):
            add_centered_image(doc, chart3, 5.0, '图3：合作形式 CPE/CPM 对比')
        doc.add_paragraph()

        cf_rows = []
        for cf, d in coop_formats.items():
            cf_rows.append([cf, d['count'], f"{d['exposure']:,.0f}", f"{d['interaction']:,.0f}",
                f"{d['cost']:.0f}元", f"{d['cpm']:.2f}", f"{d['cpe']:.2f}"])
        add_styled_table(doc, ['合作形式', '笔记数', '总曝光', '总互动', '总成本', 'CPM', 'CPE'], cf_rows)
    elif coop_formats:
        cf_rows = []
        for cf, d in coop_formats.items():
            cf_rows.append([cf, d['count'], f"{d['exposure']:,.0f}", f"{d['interaction']:,.0f}",
                f"{d['cost']:.0f}元", f"{d['cpm']:.2f}", f"{d['cpe']:.2f}"])
        add_styled_table(doc, ['合作形式', '笔记数', '总曝光', '总互动', '总成本', 'CPM', 'CPE'], cf_rows)
    doc.add_paragraph()

    # ========== 五、达人量级效果 ==========
    add_heading_styled(doc, '五、达人量级效果', level=1)

    chart4 = os.path.join(chart_dir, '04_tier_comparison.png')
    if os.path.exists(chart4):
        add_centered_image(doc, chart4, 5.0, '图4：达人量级 CPE/CPM 对比')
    doc.add_paragraph()

    if influencer_tiers:
        tier_rows = []
        # Sort by CPE
        sorted_tiers = sorted(influencer_tiers.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        for t_name, t_data in sorted_tiers:
            tier_rows.append([t_name, t_data['count'], f"{t_data['exposure']:,.0f}",
                f"{t_data['interaction']:,.0f}", f"{t_data['cost']:.0f}元",
                f"{t_data['cpm']:.2f}", f"{t_data['cpe']:.2f}",
                f"{t_data.get('avg_completion_rate', 0):.1f}%",
                f"{t_data.get('avg_mention_rate', 0):.1f}%"])
        add_styled_table(doc, ['达人量级', '笔记数', '总曝光', '总互动', '总成本', 'CPM', 'CPE', '均完播率', '均提及率'],
            tier_rows, col_widths=[1.5, 1, 1.5, 1.5, 1.5, 1.2, 1.2, 1.5, 1.5])
    doc.add_paragraph()

    if influencer_tiers:
        best_t = min(influencer_tiers.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        worst_t = max(influencer_tiers.items(), key=lambda x: x[1].get('cpe', 0))
        add_insight(doc, f'{best_t[0]}量级CPE最优（{best_t[1]["cpe"]:.2f}元），{worst_t[0]}量级CPE最高（{worst_t[1]["cpe"]:.2f}元）。')
    doc.add_paragraph()

    # ========== 六、切角方向效果 ==========
    add_heading_styled(doc, '六、切角方向效果', level=1)

    chart5 = os.path.join(chart_dir, '05_content_angle_ranking.png')
    if os.path.exists(chart5):
        add_centered_image(doc, chart5, 5.5, '图5：切角方向 CPE 排行')
    doc.add_paragraph()

    if content_angles:
        sorted_angles = sorted(content_angles.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        angle_rows = []
        for a_name, a_data in sorted_angles[:10]:
            angle_rows.append([a_name, a_data['count'], f"{a_data['exposure']:,.0f}",
                f"{a_data['interaction']:,.0f}", f"{a_data['cost']:.0f}元",
                f"{a_data['cpm']:.2f}", f"{a_data['cpe']:.2f}",
                f"{a_data.get('avg_mention_rate', 0):.1f}%"])
        add_styled_table(doc, ['切角方向', '笔记数', '总曝光', '总互动', '总成本', 'CPM', 'CPE', '均提及率'],
            angle_rows, col_widths=[2.5, 1, 1.5, 1.5, 1.5, 1.2, 1.2, 1.5])
    doc.add_paragraph()

    # 切角方向 analysis summary
    if content_angles:
        sorted_a = sorted(content_angles.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        best_a = sorted_a[0]
        worst_a = sorted_a[-1]
        p = doc.add_paragraph()
        run = p.add_run(f'切角方向分析：')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        run2 = p.add_run(
            f'"{best_a[0]}"方向CPE最低（{best_a[1]["cpe"]:.2f}元），为最高效的内容切入点；'
            f'"{worst_a[0]}"方向CPE最高（{worst_a[1]["cpe"]:.2f}元），投入产出比偏低。'
            f'建议加大"{best_a[0]}"方向的内容占比，减少低效切角的投放。'
        )
        run2.font.size = Pt(10); run2.font.name = '微软雅黑'; run2._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        doc.add_paragraph()

        # Mention rate insight
        high_mention = sorted(content_angles.items(), key=lambda x: x[1].get('avg_mention_rate', 0), reverse=True)[:3]
        if high_mention:
            p2 = doc.add_paragraph()
            run3 = p2.add_run(f'评论区提及率最高的3个切角为：'
                f'"{high_mention[0][0]}"（{high_mention[0][1].get("avg_mention_rate", 0):.1f}%）、'
                f'"{high_mention[1][0]}"（{high_mention[1][1].get("avg_mention_rate", 0):.1f}%）、'
                f'"{high_mention[2][0]}"（{high_mention[2][1].get("avg_mention_rate", 0):.1f}%），'
                f'说明这些方向更容易引发用户讨论和品牌联想。')
            run3.font.size = Pt(10); run3.font.name = '微软雅黑'; run3._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            doc.add_paragraph()

    # ========== 七、预估 vs 实际达成评价 ==========
    add_heading_styled(doc, '七、预估 vs 实际达成评价', level=1)

    pred_actual_rows = data.get('pred_actual_rows', [])

    if pred_actual_rows:
        # Summary stats
        exceed_count = sum(1 for r in pred_actual_rows if r['status'] == '超预期')
        achieve_count = sum(1 for r in pred_actual_rows if r['status'] == '综合达成')
        below_count = sum(1 for r in pred_actual_rows if r['status'] == '不及预期')
        avg_ach = sum(r['avg_achievement'] for r in pred_actual_rows) / len(pred_actual_rows) if pred_actual_rows else 0
        avg_exp_ach = sum(r['exp_achievement'] for r in pred_actual_rows) / len(pred_actual_rows) if pred_actual_rows else 0
        avg_int_ach = sum(r['int_achievement'] for r in pred_actual_rows) / len(pred_actual_rows) if pred_actual_rows else 0

        # Status summary table
        add_styled_table(doc, ['评价', '笔记数', '占比'], [
            ['超预期', exceed_count, f'{exceed_count/len(pred_actual_rows)*100:.1f}%'],
            ['综合达成', achieve_count, f'{achieve_count/len(pred_actual_rows)*100:.1f}%'],
            ['不及预期', below_count, f'{below_count/len(pred_actual_rows)*100:.1f}%'],
        ], col_widths=[3, 4, 4])
        doc.add_paragraph()

        # Achievement charts
        chart9 = os.path.join(chart_dir, '09_achievement_status.png')
        if os.path.exists(chart9):
            add_centered_image(doc, chart9, 5.0, '图9：预估vs实际达成评价分布')
        doc.add_paragraph()

        chart10 = os.path.join(chart_dir, '10_achievement_rate.png')
        if os.path.exists(chart10):
            add_centered_image(doc, chart10, 5.5, '图10：达人综合达成率排行')
        doc.add_paragraph()

        # Per-row comparison table
        add_styled_table(doc, ['达人昵称', '达人类型', '量级',
            '预估曝光', '实际曝光', '曝光达成',
            '预估互动', '实际互动', '互动达成',
            '预估CPM', '实际CPM', '预估CPE', '实际CPE', '综合达成', '评价'],
            [[r['nickname'][:8], r['content_type'], r['influencer_tier'],
                f"{r['pred_exposure']:,.0f}", f"{r['actual_exposure']:,.0f}",
                f"{r['exp_achievement']:.0f}%",
                f"{r['pred_interaction']:,.0f}", f"{r['actual_interaction']:,.0f}",
                f"{r['int_achievement']:.0f}%",
                f"{r['pred_cpm']:.1f}", f"{r['actual_cpm']:.1f}",
                f"{r['pred_cpe']:.2f}", f"{r['actual_cpe']:.2f}",
                f"{r['avg_achievement']:.0f}%", r['status']]
             for r in sorted(pred_actual_rows, key=lambda x: x['avg_achievement'], reverse=True)],
            col_widths=[1.5, 1.2, 0.8, 1.2, 1.2, 1, 1.2, 1.2, 1, 0.9, 0.9, 0.9, 0.9, 1, 1])
        doc.add_paragraph()

        # Achievement analysis summary
        p = doc.add_paragraph()
        run = p.add_run(f'综合达成分析：')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        run2 = p.add_run(
            f'本次投放{len(pred_actual_rows)}篇笔记，'
            f'综合平均达成率{avg_ach:.0f}%。'
            f'其中{exceed_count}篇超预期（占比{exceed_count/len(pred_actual_rows)*100:.0f}%），'
            f'{achieve_count}篇综合达成，{below_count}篇不及预期。'
            f'曝光平均达成{avg_exp_ach:.0f}%，互动平均达成{avg_int_ach:.0f}%。'
        )
        run2.font.size = Pt(10); run2.font.name = '微软雅黑'; run2._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        doc.add_paragraph()

        # Highlight top exceed performers
        exceed_rows = [r for r in pred_actual_rows if r['status'] == '超预期']
        if exceed_rows:
            top_exceed = sorted(exceed_rows, key=lambda x: x['avg_achievement'], reverse=True)[:3]
            p2 = doc.add_paragraph()
            run3 = p2.add_run(f'超预期达人中达成率最高的3位为：'
                f'{top_exceed[0]["nickname"]}（{top_exceed[0]["avg_achievement"]:.0f}%）、'
                f'{top_exceed[1]["nickname"]}（{top_exceed[1]["avg_achievement"]:.0f}%）、'
                f'{top_exceed[2]["nickname"]}（{top_exceed[2]["avg_achievement"]:.0f}%）。')
            run3.font.size = Pt(10); run3.font.name = '微软雅黑'; run3._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            doc.add_paragraph()

        # Highlight below-expect performers
        if below_count > 0:
            below_rows = sorted([r for r in pred_actual_rows if r['status'] == '不及预期'], key=lambda x: x['avg_achievement'])
            p3 = doc.add_paragraph()
            run4 = p3.add_run(f'不及预期达人共{below_count}位，'
                f'达成率最低的为{below_rows[0]["nickname"]}（{below_rows[0]["avg_achievement"]:.0f}%），'
                f'建议复盘曝光/互动未达标的原因（如发布时间、内容质量、达人粉丝活跃度等）。')
            run4.font.size = Pt(10); run4.font.name = '微软雅黑'; run4._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            doc.add_paragraph()

    # ========== 八、预估 vs 实际 CPM/CPE ==========
    add_heading_styled(doc, '八、预估 vs 实际 CPM/CPE', level=1)

    chart6 = os.path.join(chart_dir, '06_pred_vs_actual_cpm.png')
    if os.path.exists(chart6):
        add_centered_image(doc, chart6, 5.5, '图6：预估 vs 实际 CPM')
    doc.add_paragraph()

    chart7 = os.path.join(chart_dir, '07_pred_vs_actual_cpe.png')
    if os.path.exists(chart7):
        add_centered_image(doc, chart7, 5.5, '图7：预估 vs 实际 CPE')
    doc.add_paragraph()

    if pred_vs_actual:
        pva = pred_vs_actual
        add_styled_table(doc, ['指标', '预估值', '实际值', '差异%'], [
            ['CPM (元)', f'{pva["cpm"]["pred_avg"]:.2f}', f'{pva["cpm"]["actual_avg"]:.2f}', f'{pva["cpm"]["diff_pct"]:+.1f}%'],
            ['CPE (元)', f'{pva["cpe"]["pred_avg"]:.2f}', f'{pva["cpe"]["actual_avg"]:.2f}', f'{pva["cpe"]["diff_pct"]:+.1f}%'],
        ], col_widths=[3, 4, 4, 4])
    doc.add_paragraph()

    if pred_vs_actual:
        pva = pred_vs_actual
        cpm_ok = pva['cpm']['actual_avg'] <= pva['cpm']['pred_avg']
        cpe_ok = pva['cpe']['actual_avg'] <= pva['cpe']['pred_avg']
        insight_parts = []
        if cpm_ok:
            insight_parts.append(f'实际CPM比预估低{abs(pva["cpm"]["diff_pct"]):.1f}%，投放效率超预期')
        else:
            insight_parts.append(f'实际CPM比预估高{abs(pva["cpm"]["diff_pct"]):.1f}%，需优化曝光质量')
        if cpe_ok:
            insight_parts.append(f'实际CPE比预估低{abs(pva["cpe"]["diff_pct"]):.1f}%，互动成本控制良好')
        else:
            insight_parts.append(f'实际CPE比预估高{abs(pva["cpe"]["diff_pct"]):.1f}%，需提升互动表现')
        add_insight(doc, '；'.join(insight_parts) + '。')
    doc.add_paragraph()

    # ========== 九、时间趋势 ==========
    add_heading_styled(doc, '九、时间趋势', level=1)

    chart8 = os.path.join(chart_dir, '08_date_trend.png')
    if os.path.exists(chart8):
        add_centered_image(doc, chart8, 5.5, '图8：发布时间趋势')
    doc.add_paragraph()

    if date_trend:
        date_rows = []
        for d_str, d_data in date_trend.items():
            date_rows.append([d_str, d_data['count'], f"{d_data['exposure']:,.0f}",
                f"{d_data['interaction']:,.0f}", f"{d_data['cost']:.0f}元"])
        add_styled_table(doc, ['日期', '笔记数', '曝光量', '互动量', '成本'], date_rows)
    doc.add_paragraph()

    # 时间趋势 analysis summary
    if date_trend:
        dates_list = list(date_trend.items())
        first_date = dates_list[0][0]
        last_date = dates_list[-1][0]
        total_days = (datetime.datetime.strptime(last_date, '%Y-%m-%d') - datetime.datetime.strptime(first_date, '%Y-%m-%d')).days + 1
        avg_per_day = len(date_trend) / total_days * 100 if total_days > 0 else 0

        # Find peak day
        peak_date = max(date_trend.items(), key=lambda x: x[1]['interaction'])
        peak_date_str = peak_date[0]
        peak_interact = int(peak_date[1]['interaction'])

        p = doc.add_paragraph()
        run = p.add_run(f'投放节奏分析：')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        run2 = p.add_run(
            f'本轮投放从{first_date}持续至{last_date}，共{total_days}天，'
            f'覆盖{len(date_trend)}个发布日。'
            f'{peak_date_str}互动量最高（{peak_interact:,}），建议复盘该日发布内容的创意特点和发布时段，'
            f'提炼可复用的成功要素。'
        )
        run2.font.size = Pt(10); run2.font.name = '微软雅黑'; run2._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        doc.add_paragraph()

        # Check for early vs late performance
        mid = len(dates_list) // 2
        if mid > 0:
            early_interact = sum(d['interaction'] for _, d in dates_list[:mid])
            late_interact = sum(d['interaction'] for _, d in dates_list[mid:])
            if late_interact > early_interact:
                p2 = doc.add_paragraph()
                run3 = p2.add_run(f'投放后期（{dates_list[mid][0]}之后）互动量高于前期，说明内容策略在投放过程中持续优化，效果逐步提升。')
                run3.font.size = Pt(10); run3.font.name = '微软雅黑'; run3._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
                doc.add_paragraph()

    # ========== 十、完播率与提及率 ==========
    add_heading_styled(doc, '十、完播率与提及率', level=1)

    add_styled_table(doc, ['指标', '平均值', '中位数', '最高', '最低'], [
        ['完播率', f'{completion_stats.get("avg", 0):.1f}%', f'{completion_stats.get("median", 0):.1f}%',
         f'{completion_stats.get("max", 0):.1f}%', f'{completion_stats.get("min", 0):.1f}%'],
        ['评论区提及率', f'{mention_stats.get("avg", 0):.1f}%', f'{mention_stats.get("median", 0):.1f}%',
         f'{mention_stats.get("max", 0):.1f}%', f'{mention_stats.get("min", 0):.1f}%'],
    ], col_widths=[3, 2.5, 2.5, 2.5, 2.5])
    doc.add_paragraph()

    if completion_stats.get('avg', 0) < 20:
        add_insight(doc, f'平均完播率仅{completion_stats.get("avg", 0):.1f}%，建议优化视频前3秒的吸引力，提升用户停留。')
    elif completion_stats.get('avg', 0) > 25:
        add_insight(doc, f'平均完播率{completion_stats.get("avg", 0):.1f}%表现良好，说明内容质量较高。')
    doc.add_paragraph()

    # 完播率与提及率 analysis summary
    p = doc.add_paragraph()
    run = p.add_run(f'完播率与提及率综合分析：')
    run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    cr_val = completion_stats.get('avg', 0)
    mr_val = mention_stats.get('avg', 0)
    run2 = p.add_run(
        f'平均完播率{cr_val:.1f}%（中位数{completion_stats.get("median", 0):.1f}%），'
        f'平均评论区提及率{mr_val:.1f}%（中位数{mention_stats.get("median", 0):.1f}%）。'
    )
    run2.font.size = Pt(10); run2.font.name = '微软雅黑'; run2._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_paragraph()

    if top_engagement:
        # Find correlation between completion rate and engagement
        high_cr = [t for t in top_engagement if t.get('completion_rate', 0) > completion_stats.get('avg', 0)]
        high_mr = [t for t in top_engagement if t.get('mention_rate', 0) > mention_stats.get('avg', 0)]
        if high_cr:
            p2 = doc.add_paragraph()
            run3 = p2.add_run(f'完播率高于均值的{len(high_cr)}位达人中，互动表现普遍较好，建议后续筛选达人时将完播率作为重要参考指标。')
            run3.font.size = Pt(10); run3.font.name = '微软雅黑'; run3._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            doc.add_paragraph()

    # ========== 十一、TOP达人盘点 ==========
    add_heading_styled(doc, '十一、TOP达人盘点', level=1)
    add_heading_styled(doc, '互动量 TOP5 达人', level=2)

    if top_engagement:
        top5 = top_engagement[:5]
        top_rows = []
        for i, t in enumerate(top5, 1):
            top_rows.append([i, t.get('nickname', ''), t.get('content_type', ''), t.get('influencer_tier', ''),
                f"{t.get('exposure', 0):,.0f}", f"{t.get('interaction', 0):,.0f}",
                f"{t.get('cost', 0):.0f}元", f"{t.get('cpm', 0):.2f}", f"{t.get('cpe', 0):.2f}",
                f"{t.get('completion_rate', 0):.1f}%", f"{t.get('mention_rate', 0):.1f}%"])
        add_styled_table(doc, ['排名', '达人昵称', '达人类型', '量级', '曝光量', '互动量', '成本', 'CPM', 'CPE', '完播率', '提及率'],
            top_rows, col_widths=[0.8, 1.8, 1.5, 1, 1.3, 1.3, 1.2, 1, 1, 1.2, 1.2])
    doc.add_paragraph()

    # TOP达人 analysis summary
    if top_engagement:
        top1 = top_engagement[0]
        p = doc.add_paragraph()
        run = p.add_run(f'TOP达人分析：')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        run2 = p.add_run(
            f'{top1["nickname"]}以{int(top1["interaction"]):,}互动量位居榜首（{top1["content_type"]}类型，{top1["influencer_tier"]}量级），'
            f'CPE仅{top1["cpe"]:.2f}元。'
            f'TOP5达人均CPE为{sum(t["cpe"] for t in top_engagement[:5])/5:.2f}元，'
            f'低于整体CPE {core["cpe"]:.2f}元，说明高互动达人的投放效率也更高，'
            f'建议后续优先与这些达人保持长期合作。'
        )
        run2.font.size = Pt(10); run2.font.name = '微软雅黑'; run2._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        doc.add_paragraph()

    # ========== 十二、复盘总结 & 行动建议 ==========
    add_heading_styled(doc, '十二、复盘总结 & 行动建议', level=1)

    # 12.1 成功经验
    add_heading_styled(doc, '12.1 成功经验', level=2)
    successes = []
    if influencer_tiers:
        best_t = min(influencer_tiers.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        successes.append(f'{best_t[0]}量级达人CPE最优（{best_t[1]["cpe"]:.2f}元），是该预算区间的高性价比选择')
    if content_angles:
        best_a = min(content_angles.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        successes.append(f'"{best_a[0]}"切角方向CPE最低（{best_a[1]["cpe"]:.2f}元），说明该话题与目标受众匹配度高')
    if completion_stats.get('avg', 0) > 20:
        successes.append(f'平均完播率{completion_stats.get("avg", 0):.1f}%，内容质量整体达标')
    if engagement.get('shares_pct', 0) > 30:
        successes.append(f'分享占比{engagement["shares_pct"]:.1f}%，内容具有较强的社交传播性')
    for s in successes:
        p = doc.add_paragraph(s, style='List Bullet')
        for run in p.runs: run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_paragraph()

    # 12.2 问题与改进方向
    add_heading_styled(doc, '12.2 问题与改进方向', level=2)
    issues = []
    if influencer_tiers:
        worst_t = max(influencer_tiers.items(), key=lambda x: x[1].get('cpe', 0))
        best_t = min(influencer_tiers.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        if best_t[1].get('cpe', 0) > 0 and worst_t[1]['cpe'] > best_t[1]['cpe'] * 2:
            issues.append([f'{worst_t[0]}量级CPE达{worst_t[1]["cpe"]:.2f}元',
                f'是{best_t[0]}量级的{worst_t[1]["cpe"]/best_t[1]["cpe"]:.1f}倍',
                f'缩减{worst_t[0]}量级投放，预算转移至高效区间'])
    if completion_stats.get('avg', 0) < 15:
        issues.append([f'平均完播率仅{completion_stats.get("avg", 0):.1f}%',
            '视频内容前3秒吸引力不足', '优化开场画面，增加痛点引入'])
    if mention_stats.get('avg', 0) < 15:
        issues.append([f'平均评论区提及率仅{mention_stats.get("avg", 0):.1f}%',
            '品牌/产品心智渗透不足', '加强评论区运营引导和关键词植入'])
    if pred_vs_actual:
        pva = pred_vs_actual
        if pva['cpe']['diff_pct'] > 30:
            issues.append([f'实际CPE超预估{pva["cpe"]["diff_pct"]:.1f}%',
                'SIPAC定价模型偏差较大', '修正SIPAC定价模型，基于历史数据调整'])
    if issues:
        add_styled_table(doc, ['问题', '影响', '改进建议'], issues, col_widths=[4.5, 4, 5.5])
    doc.add_paragraph()

    # 12.3 下期策略建议
    add_heading_styled(doc, '12.3 下期策略建议', level=2)
    strategies = []
    if influencer_tiers:
        best_t = min(influencer_tiers.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        strategies.append(('达人量级', f'优先投放{best_t[0]}量级达人（CPE {best_t[1]["cpe"]:.2f}元）'))
    if content_angles:
        best_a = min(content_angles.items(), key=lambda x: x[1].get('cpe', 999) if x[1].get('cpe', 0) > 0 else 999999)
        strategies.append(('切角方向', f'加大"{best_a[0]}"方向的内容占比'))
    if completion_stats.get('avg', 0) > 0:
        strategies.append(('完播率', f'当前平均{completion_stats.get("avg", 0):.1f}%，目标提升至{min(completion_stats.get("avg", 0) + 5, 35):.0f}%，优化前3秒钩子'))
    if engagement.get('shares_pct', 0) > 25:
        strategies.append(('传播策略', f'分享占比已达{engagement["shares_pct"]:.1f}%，可加大社交裂变激励'))
    for title, desc in strategies:
        p = doc.add_paragraph()
        run = p.add_run(title + '：')
        run.font.bold = True; run.font.size = Pt(10); run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        run2 = p.add_run(desc)
        run2.font.size = Pt(10); run2.font.name = '微软雅黑'; run2._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.add_paragraph()

    # Footer
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('— 文档结束 —')
    run.font.size = Pt(10); run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'基于《视频号投放复盘SOP》模板 | 生成时间：{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}')
    run.font.size = Pt(8); run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
    run.font.name = '微软雅黑'; run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    doc.save(output_path)
    print(f'报告已保存: {output_path}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(f"用法: python build_video_number_report.py <分析JSON> <图表目录> <输出docx路径> [品牌名]")
        sys.exit(1)
    brand = sys.argv[4] if len(sys.argv) > 4 else ''
    build_report(sys.argv[1], sys.argv[2], sys.argv[3], brand)
