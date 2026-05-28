# -*- coding: utf-8 -*-
"""
generate_video_number_charts.py — 视频号分析图表生成
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json
import sys
import os

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BLUE = '#1F4E79'
DARK_BLUE = '#2E75B6'
LIGHT_BLUE = '#5B9BD5'
ACCENT_BLUE = '#DEEAF6'
RED = '#C0392B'
ORANGE = '#E67E22'
GREEN = '#27AE60'
YELLOW = '#F39C12'
GRAY = '#95A5A6'
DARK_GRAY = '#7F8C8D'

def fmt_num(n):
    if n >= 1e8:
        return f'{n/1e8:.2f}亿'
    elif n >= 1e4:
        return f'{n/1e4:.1f}万'
    else:
        return f'{n:,.0f}'


def generate(json_path, chart_dir):
    os.makedirs(chart_dir, exist_ok=True)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    core = data['core_metrics']
    engagement = data.get('engagement_detail', {})
    content_types = data.get('content_types', {})
    coop_formats = data.get('cooperation_formats', {})
    influencer_tiers = data.get('influencer_tiers', {})
    content_angles = data.get('content_angles', {})
    date_trend = data.get('date_trend', {})
    pred_vs_actual = data.get('predicted_vs_actual', {})
    pred_actual_rows = data.get('pred_actual_rows', [])
    top_engagement = data.get('top_engagement', [])

    # ========== CHART 1: Engagement Donut ==========
    print('Chart 1: Engagement Donut...')
    fig, ax = plt.subplots(figsize=(6, 5))
    items_eng = ['赞', '评论', '分享', '私密赞']
    vals_eng = [engagement.get('total_likes', 0), engagement.get('total_comments', 0),
                engagement.get('total_shares', 0), engagement.get('total_private_likes', 0)]
    pcts_eng = [engagement.get('likes_pct', 0), engagement.get('comments_pct', 0),
                engagement.get('shares_pct', 0), engagement.get('private_likes_pct', 0)]
    colors_eng = [DARK_BLUE, LIGHT_BLUE, GREEN, ORANGE]
    valid = [(items_eng[i], vals_eng[i], pcts_eng[i], colors_eng[i]) for i in range(4) if vals_eng[i] > 0]

    if valid:
        labels = [f'{v[0]} {v[2]:.1f}%' for v in valid]
        sizes = [v[1] for v in valid]
        colors = [v[3] for v in valid]
    else:
        labels = ['互动']
        sizes = [1]
        colors = [DARK_BLUE]

    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors,
        autopct='%1.1f%%', startangle=90,
        textprops={'fontsize': 10, 'fontweight': 'bold'},
        pctdistance=0.75, wedgeprops=dict(width=0.55, edgecolor='white', linewidth=2))
    for t in autotexts:
        t.set_color('white')
        t.set_fontsize(11)
        t.set_fontweight('bold')

    ax.text(0, -1.15, f'总互动: {fmt_num(sum(vals_eng))}',
        fontsize=9, ha='center', color=DARK_BLUE, fontweight='bold')
    ax.set_title('互动构成拆解', fontsize=13, fontweight='bold', pad=12, color=BLUE)
    plt.tight_layout()
    plt.savefig(os.path.join(chart_dir, '01_engagement_pie.png'), dpi=150, bbox_inches='tight')
    plt.close()

    # ========== CHART 2: Content Type CPE/CPM ==========
    print('Chart 2: Content Type Comparison...')
    if len(content_types) >= 1:
        n_ct = len(content_types)
        fig_h = 4 + n_ct * 0.3
        fig, ax = plt.subplots(figsize=(max(7, n_ct * 1.2), fig_h))
        ct_names = list(content_types.keys())
        cpes = [content_types[n]['cpe'] for n in ct_names]
        cpms = [content_types[n]['cpm'] for n in ct_names]

        x = np.arange(len(ct_names))
        w = 0.3
        bars1 = ax.bar(x - w/2, cpes, width=w, label='CPE (元)',
            color=DARK_BLUE, edgecolor='white')
        ax2 = ax.twinx()
        bars2 = ax2.bar(x + w/2, cpms, width=w, label='CPM (元)',
            color=LIGHT_BLUE, edgecolor='white')

        ax.set_xticks(x)
        ax.set_xticklabels(ct_names, fontsize=9)
        ax.set_ylabel('CPE (元)', fontsize=9, color=DARK_BLUE)
        ax2.set_ylabel('CPM (元)', fontsize=9, color=LIGHT_BLUE)

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='upper right')
        ax.set_title('达人类型 CPE/CPM 对比', fontsize=13, fontweight='bold', pad=12, color=BLUE)

        ax.spines['top'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '02_content_type_comparison.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 3: Coop Format Comparison ==========
    print('Chart 3: Cooperation Format Comparison...')
    if len(coop_formats) >= 2:
        fig, ax = plt.subplots(figsize=(7, 4))
        cf_names = list(coop_formats.keys())
        cpes_cf = [coop_formats[n]['cpe'] for n in cf_names]
        cpms_cf = [coop_formats[n]['cpm'] for n in cf_names]

        x = np.arange(len(cf_names))
        w = 0.3
        bars1 = ax.bar(x - w/2, cpes_cf, width=w, label='CPE (元)',
            color=DARK_BLUE, edgecolor='white')
        ax2 = ax.twinx()
        bars2 = ax2.bar(x + w/2, cpms_cf, width=w, label='CPM (元)',
            color=LIGHT_BLUE, edgecolor='white')

        ax.set_xticks(x)
        ax.set_xticklabels(cf_names, fontsize=9)
        ax.set_ylabel('CPE (元)', fontsize=9, color=DARK_BLUE)
        ax2.set_ylabel('CPM (元)', fontsize=9, color=LIGHT_BLUE)

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='upper right')
        ax.set_title('合作形式 CPE/CPM 对比', fontsize=13, fontweight='bold', pad=12, color=BLUE)

        ax.spines['top'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '03_coop_format_comparison.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 4: Influencer Tier Comparison ==========
    print('Chart 4: Tier Comparison...')
    if influencer_tiers:
        n_t = len(influencer_tiers)
        fig, ax = plt.subplots(figsize=(max(7, n_t * 1.5), 4))
        tier_names = list(influencer_tiers.keys())
        cpes_t = [influencer_tiers[n]['cpe'] for n in tier_names]
        cpms_t = [influencer_tiers[n]['cpm'] for n in tier_names]

        x = np.arange(len(tier_names))
        w = 0.3
        bars1 = ax.bar(x - w/2, cpes_t, width=w, label='CPE (元)',
            color=DARK_BLUE, edgecolor='white')
        ax2 = ax.twinx()
        bars2 = ax2.bar(x + w/2, cpms_t, width=w, label='CPM (元)',
            color=LIGHT_BLUE, edgecolor='white')

        ax.set_xticks(x)
        ax.set_xticklabels(tier_names, fontsize=9)
        ax.set_ylabel('CPE (元)', fontsize=9, color=DARK_BLUE)
        ax2.set_ylabel('CPM (元)', fontsize=9, color=LIGHT_BLUE)

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='upper right')
        ax.set_title('达人量级 CPE/CPM 对比', fontsize=13, fontweight='bold', pad=12, color=BLUE)

        ax.spines['top'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '04_tier_comparison.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 5: Content Angle CPE Ranking ==========
    print('Chart 5: Content Angle CPE Ranking...')
    if content_angles:
        sorted_angles = sorted(content_angles.items(), key=lambda x: x[1]['cpe'] if x[1]['cpe'] > 0 else 999999)
        sorted_angles = sorted_angles[:10]
        n_a = len(sorted_angles)
        fig_h = 3 + n_a * 0.35
        fig, ax = plt.subplots(figsize=(8, fig_h))
        angle_names = [a[0][:20] for a in sorted_angles]
        cpes_a = [a[1]['cpe'] for a in sorted_angles]

        bar_colors = []
        for c in cpes_a:
            if c < 1: bar_colors.append(GREEN)
            elif c < 3: bar_colors.append(DARK_BLUE)
            elif c < 5: bar_colors.append(ORANGE)
            else: bar_colors.append(RED)

        y = np.arange(len(angle_names))
        bars = ax.barh(y[::-1], [c for c in cpes_a[::-1]], color=bar_colors[::-1],
            edgecolor='white', height=0.55)
        ax.set_yticks(y)
        ax.set_yticklabels(angle_names[::-1], fontsize=8)
        ax.set_xlabel('CPE (元)', fontsize=9)
        ax.set_title('切角方向 CPE 排行 (越低越优)', fontsize=13, fontweight='bold', pad=12, color=BLUE)

        max_cpe = max(cpes_a) if cpes_a else 1
        for bar, val in zip(bars, cpes_a[::-1]):
            ax.text(bar.get_width() + max_cpe*0.03, bar.get_y() + bar.get_height()/2,
                f'{val:.2f}', va='center', fontsize=7, fontweight='bold')

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '05_content_angle_ranking.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 6: Predicted vs Actual CPM ==========
    print('Chart 6: Predicted vs Actual CPM...')
    if pred_vs_actual and pred_vs_actual.get('cpm', {}).get('pred_avg', 0) > 0:
        fig, ax = plt.subplots(figsize=(5, 4))
        p_cpm = pred_vs_actual['cpm']['pred_avg']
        a_cpm = pred_vs_actual['cpm']['actual_avg']
        diff = pred_vs_actual['cpm']['diff_pct']

        labels = ['预估CPM', '实际CPM']
        values = [p_cpm, a_cpm]
        colors_cpm = [GRAY, DARK_BLUE]

        bars = ax.bar(labels, values, color=colors_cpm, edgecolor='white', width=0.4)
        ax.set_ylabel('CPM (元)', fontsize=10)
        ax.set_title(f'预估 vs 实际 CPM (差异: {diff:+.1f}%)', fontsize=13, fontweight='bold', pad=12, color=BLUE)

        max_val = max(values) if values else 1
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max_val*0.02,
                f'{val:.2f}', ha='center', fontsize=10, fontweight='bold')

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '06_pred_vs_actual_cpm.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 7: Predicted vs Actual CPE ==========
    print('Chart 7: Predicted vs Actual CPE...')
    if pred_vs_actual and pred_vs_actual.get('cpe', {}).get('pred_avg', 0) > 0:
        fig, ax = plt.subplots(figsize=(5, 4))
        p_cpe = pred_vs_actual['cpe']['pred_avg']
        a_cpe = pred_vs_actual['cpe']['actual_avg']
        diff = pred_vs_actual['cpe']['diff_pct']

        labels = ['预估CPE', '实际CPE']
        values = [p_cpe, a_cpe]
        colors_cpe = [GRAY, DARK_BLUE]

        bars = ax.bar(labels, values, color=colors_cpe, edgecolor='white', width=0.4)
        ax.set_ylabel('CPE (元)', fontsize=10)
        ax.set_title(f'预估 vs 实际 CPE (差异: {diff:+.1f}%)', fontsize=13, fontweight='bold', pad=12, color=BLUE)

        max_val = max(values) if values else 1
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max_val*0.02,
                f'{val:.2f}', ha='center', fontsize=10, fontweight='bold')

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '07_pred_vs_actual_cpe.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 8: Date Trend ==========
    print('Chart 8: Date Trend...')
    if date_trend:
        n_d = len(date_trend)
        fig_w = max(8, n_d * 0.6)
        fig, ax = plt.subplots(figsize=(fig_w, 4))
        dates_list = list(date_trend.keys())
        exposures = [date_trend[d]['exposure'] for d in dates_list]
        interactions = [date_trend[d]['interaction'] for d in dates_list]

        x = np.arange(len(dates_list))
        w = 0.5
        bars = ax.bar(x, exposures, width=w, color=DARK_BLUE, edgecolor='white',
            alpha=0.7, label='曝光量')
        ax2 = ax.twinx()
        ax2.plot(x, interactions, 'o-', color=ORANGE, linewidth=2,
            markersize=6, markerfacecolor='white', markeredgewidth=2, label='互动量')

        ax.set_xticks(x)
        ax.set_xticklabels([d[5:] for d in dates_list], fontsize=8, rotation=45, ha='right')
        ax.set_ylabel('曝光量', fontsize=9, color=DARK_BLUE)
        ax2.set_ylabel('互动量', fontsize=9, color=ORANGE)

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='upper right')
        ax.set_title('发布时间趋势 (曝光量 & 互动量)', fontsize=13, fontweight='bold', pad=12, color=BLUE)

        ax.spines['top'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '08_date_trend.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 9: Achievement Status Donut ==========
    print('Chart 9: Achievement Status Donut...')
    if pred_actual_rows:
        fig, ax = plt.subplots(figsize=(6, 5))
        status_counts = {}
        for r in pred_actual_rows:
            s = r['status']
            status_counts[s] = status_counts.get(s, 0) + 1

        labels = [f'{k} ({v}篇)' for k, v in status_counts.items()]
        sizes = list(status_counts.values())
        colors_map = {'超预期': GREEN, '综合达成': DARK_BLUE, '不及预期': RED}
        colors = [colors_map.get(k, GRAY) for k in status_counts.keys()]

        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors,
            autopct='%1.1f%%', startangle=90,
            textprops={'fontsize': 10, 'fontweight': 'bold'},
            pctdistance=0.75, wedgeprops=dict(width=0.55, edgecolor='white', linewidth=2))
        for t in autotexts:
            t.set_color('white')
            t.set_fontsize(11)
            t.set_fontweight('bold')

        ax.set_title('预估 vs 实际达成评价', fontsize=13, fontweight='bold', pad=12, color=BLUE)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '09_achievement_status.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 10: Achievement Rate Bar ==========
    print('Chart 10: Achievement Rate Bar...')
    if pred_actual_rows and len(pred_actual_rows) <= 20:
        fig_h = 3 + len(pred_actual_rows) * 0.3
        fig, ax = plt.subplots(figsize=(9, fig_h))
        sorted_rows = sorted(pred_actual_rows, key=lambda x: x['avg_achievement'], reverse=True)
        names = [r['nickname'][:8] for r in sorted_rows]
        ach_rates = [r['avg_achievement'] for r in sorted_rows]

        bar_colors = []
        for r in ach_rates:
            if r >= 100: bar_colors.append(GREEN)
            elif r >= 80: bar_colors.append(DARK_BLUE)
            else: bar_colors.append(RED)

        y = np.arange(len(names))
        bars = ax.barh(y[::-1], [a for a in ach_rates[::-1]], color=bar_colors[::-1],
            edgecolor='white', height=0.55)
        ax.set_yticks(y)
        ax.set_yticklabels(names[::-1], fontsize=8)
        ax.set_xlabel('综合达成率 (%)', fontsize=9)
        ax.axvline(x=100, color=GREEN, linestyle='--', alpha=0.5, linewidth=1)
        ax.axvline(x=80, color=ORANGE, linestyle='--', alpha=0.5, linewidth=1)
        ax.set_title('达人综合达成率排行 (虚线=超预期/综合达成阈值)', fontsize=13, fontweight='bold', pad=12, color=BLUE)

        max_ach = max(ach_rates) if ach_rates else 100
        for bar, val in zip(bars, ach_rates[::-1]):
            ax.text(bar.get_width() + max_ach*0.02, bar.get_y() + bar.get_height()/2,
                f'{val:.0f}%', va='center', fontsize=7, fontweight='bold')

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '10_achievement_rate.png'), dpi=150, bbox_inches='tight')
        plt.close()

    charts = []
    for f in sorted(os.listdir(chart_dir)):
        if f.endswith('.png'):
            charts.append(os.path.join(chart_dir, f))
    return charts


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"用法: python generate_video_number_charts.py <分析结果JSON> <图表输出目录>")
        sys.exit(1)
    generate(sys.argv[1], sys.argv[2])
