# -*- coding: utf-8 -*-
"""
generate_charts.py — 基于分析结果JSON生成8张PNG图表
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import json
import sys
import os
from collections import Counter

# Set Chinese font
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# Color palette
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
    """格式化大数字"""
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

    # ========== CHART 1: Traffic Source Donut ==========
    print('Chart 1: Traffic Source Donut...')
    fig, ax = plt.subplots(figsize=(7, 6))
    promo_pct = traffic['promo_exposure_pct']
    nat_pct = traffic['nat_exposure_pct']
    heat_pct = (traffic['heat_exposure'] / (traffic['promo_exposure'] + traffic['nat_exposure'] + traffic['heat_exposure']) * 100) if (traffic['promo_exposure'] + traffic['nat_exposure'] + traffic['heat_exposure']) > 0 else 0

    if heat_pct < 0.1:
        sizes_vis = [promo_pct, nat_pct]
        labels = [f'推广流量 {promo_pct:.1f}%', f'自然流量 {nat_pct:.1f}%']
        colors = [DARK_BLUE, LIGHT_BLUE]
    else:
        sizes_vis = [promo_pct, nat_pct, heat_pct]
        labels = [f'推广流量 {promo_pct:.1f}%', f'自然流量 {nat_pct:.1f}%', f'加热流量 {heat_pct:.1f}%']
        colors = [DARK_BLUE, LIGHT_BLUE, YELLOW]

    wedges, texts, autotexts = ax.pie(sizes_vis, labels=labels, colors=colors,
        autopct='%1.1f%%', startangle=90,
        textprops={'fontsize': 11, 'fontweight': 'bold'},
        pctdistance=0.75, wedgeprops=dict(width=0.55, edgecolor='white', linewidth=2))
    for t in autotexts:
        t.set_color('white')
        t.set_fontsize(13)
        t.set_fontweight('bold')

    ax.text(0, -1.25, f'加热流量: {heat_pct:.1f}% ({'未启用' if heat_pct < 0.1 else '已启用'})',
        fontsize=10, ha='center', color=RED, fontweight='bold')
    ax.set_title('流量来源结构', fontsize=16, fontweight='bold', pad=20, color=BLUE)
    plt.tight_layout()
    plt.savefig(os.path.join(chart_dir, '01_traffic_source_donut.png'), dpi=150, bbox_inches='tight')
    plt.close()

    # ========== CHART 2: Natural Traffic Channel Bar ==========
    print('Chart 2: Natural Traffic Channel Bar...')
    fig, ax = plt.subplots(figsize=(8, 5))
    exp_src = sources['exp']
    read_src = sources['read']
    channels = ['发现页', '搜索页', '个人页', '关注页', '附近页', '其他']
    exp_vals = [exp_src.get(c, 0) for c in channels]
    read_vals = [read_src.get(c, 0) for c in channels]

    x = np.arange(len(channels))
    width = 0.35
    bars1 = ax.barh(x - width/2, exp_vals, height=width, label='曝光占比',
        color=DARK_BLUE, edgecolor='white')
    bars2 = ax.barh(x + width/2, read_vals, height=width, label='阅读占比',
        color=LIGHT_BLUE, edgecolor='white')

    ax.set_yticks(x)
    ax.set_yticklabels(channels, fontsize=11)
    ax.set_xlabel('占比 (%)', fontsize=10)
    ax.legend(fontsize=10, loc='lower right')
    ax.set_title('自然流量渠道分布', fontsize=16, fontweight='bold', pad=15, color=BLUE)

    for bars in [bars1, bars2]:
        for bar in bars:
            w = bar.get_width()
            if w > 0.3:
                ax.text(w + 0.3, bar.get_y() + bar.get_height()/2,
                    f'{w:.1f}%', va='center', fontsize=9, fontweight='bold')

    ax.invert_yaxis()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(chart_dir, '02_natural_channel_bar.png'), dpi=150, bbox_inches='tight')
    plt.close()

    # ========== CHART 3: Interaction Breakdown ==========
    print('Chart 3: Interaction Breakdown...')
    fig, ax = plt.subplots(figsize=(8, 5))
    items = ['点赞', '收藏', '分享', '关注', '评论']
    values = [core['total_likes'], core['total_favorites'], core['total_shares'],
              core['total_follows'], core['total_comments']]
    values_wan = [v / 1e4 for v in values]
    colors_bar = ['#1F4E79', '#2E75B6', '#5B9BD5', '#85C1E9', '#AED6F1']

    bars = ax.barh(items[::-1], values_wan[::-1], color=colors_bar[::-1],
        edgecolor='white', height=0.55)
    ax.set_xlabel('互动量 (万)', fontsize=10)
    ax.set_title('互动量构成拆解', fontsize=16, fontweight='bold', pad=15, color=BLUE)

    for bar, val in zip(bars, values_wan[::-1]):
        ax.text(bar.get_width() + max(values_wan)*0.01, bar.get_y() + bar.get_height()/2,
            f'{val:.1f}万', va='center', fontsize=10, fontweight='bold', color=DARK_BLUE)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    total_wan = sum(values) / 1e4
    ax.text(0.02, 0.95, f'总互动: {total_wan:.1f}万', transform=ax.transAxes,
        fontsize=11, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.3', facecolor=ACCENT_BLUE, edgecolor=DARK_BLUE))
    plt.tight_layout()
    plt.savefig(os.path.join(chart_dir, '03_interaction_breakdown.png'), dpi=150, bbox_inches='tight')
    plt.close()

    # ========== CHART 4: Image vs Video Grouped Bar ==========
    print('Chart 4: Image vs Video Grouped Bar...')
    fig, ax = plt.subplots(figsize=(8, 5))

    type_names = list(content.keys())
    if len(type_names) >= 2:
        type1, type2 = type_names[0], type_names[1]
    else:
        type1, type2 = type_names[0] if type_names else '图文', '视频'

    t1 = content.get(type1, {})
    t2 = content.get(type2, {})

    metrics = ['均阅读\n(篇)', '互动率\n(%)', 'CPE\n(元)']
    v1 = [t1.get('avg_reads', 0)/1000 if t1.get('avg_reads',0)/1000 < 100 else t1.get('avg_reads',0)/1000,
          t1.get('irate', 0), t1.get('cpe', 0)]
    v2 = [t2.get('avg_reads', 0)/1000 if t2.get('avg_reads',0)/1000 < 100 else t2.get('avg_reads',0)/1000,
          t2.get('irate', 0), t2.get('cpe', 0)]
    l1 = [f"{t1.get('avg_reads',0):,.0f}", f"{t1.get('irate',0):.2f}%", f"{t1.get('cpe',0):.2f}元"]
    l2 = [f"{t2.get('avg_reads',0):,.0f}", f"{t2.get('irate',0):.2f}%", f"{t2.get('cpe',0):.2f}元"]

    x = np.arange(len(metrics))
    w = 0.35
    bars1 = ax.bar(x - w/2, v1, width=w, label=type1, color=GRAY, edgecolor='white')
    bars2 = ax.bar(x + w/2, v2, width=w, label=type2, color=DARK_BLUE, edgecolor='white')

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylabel('数值', fontsize=10)
    ax.legend(fontsize=11)
    ax.set_title(f'{type1} vs {type2} 核心指标对比', fontsize=16, fontweight='bold', pad=15, color=BLUE)

    for bars, labels in [(bars1, l1), (bars2, l2)]:
        for bar, label in zip(bars, labels):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(max(v1),max(v2))*0.02,
                label, ha='center', fontsize=9, fontweight='bold')

    ratio_reads = t2.get('avg_reads',0) / t1.get('avg_reads',1) if t1.get('avg_reads',0) > 0 else 0
    ratio_cpe = (1 - t2.get('cpe',0) / t1.get('cpe',1)) * 100 if t1.get('cpe',0) > 0 else 0

    ax.text(0.02, 0.92, f'{type2}均阅读是{type1}的 {ratio_reads:.1f} 倍', transform=ax.transAxes,
        fontsize=10, color=DARK_BLUE, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.3', facecolor=ACCENT_BLUE, edgecolor=DARK_BLUE))
    ax.text(0.02, 0.84, f'{type2}CPE比{type1}低 {ratio_cpe:.1f}%', transform=ax.transAxes,
        fontsize=10, color=GREEN, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(chart_dir, '04_type_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()

    # ========== CHART 5: SPU Scatter ==========
    print('Chart 5: SPU Scatter...')
    if spu_top:
        fig, ax = plt.subplots(figsize=(10, 6))
        names = [s['name'][:25].replace('\t', ' ').replace('\n', ' ') for s in spu_top]
        costs = [s['cost'] for s in spu_top]
        irates = [s['irate'] for s in spu_top]
        reads = [s['reads'] for s in spu_top]

        bubble_sizes = [max(r * 0.05, 50) for r in reads]
        color_scatter = [RED if c > 500 else (ORANGE if c > 100 else (GREEN if i > 5 else DARK_BLUE))
                        for c, i in zip(costs, irates)]

        scatter = ax.scatter(costs, irates, s=bubble_sizes, c=color_scatter,
            alpha=0.7, edgecolors='white', linewidth=1.5, zorder=3)

        for i, name in enumerate(names):
            ax.annotate(name, (costs[i], irates[i]), fontsize=8, ha='center', va='center',
                zorder=4, bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                edgecolor=color_scatter[i], alpha=0.9))

        median_cost = np.median([c for c in costs if c > 0]) if any(c > 0 for c in costs) else 100
        median_ir = np.median(irates) if irates else 5
        ax.axhline(y=median_ir, color=GRAY, linestyle='--', alpha=0.5)
        ax.axvline(x=median_cost, color=GRAY, linestyle='--', alpha=0.5)

        ax.text(median_cost * 1.1, max(irates) * 0.95, '低效区\n(高成本/低互动)',
            fontsize=9, color=RED, fontweight='bold')
        ax.text(median_cost * 0.1, min(irates) * 1.1, '高效区\n(低成本/高互动)',
            fontsize=9, color=GREEN, fontweight='bold')

        ax.set_xlabel('成本 (万元)', fontsize=10)
        ax.set_ylabel('互动率 (%)', fontsize=10)
        ax.set_title('SPU维度: 成本 vs 互动率 (气泡大小=阅读量)',
            fontsize=14, fontweight='bold', pad=15, color=BLUE)

        for r in [1000, 5000, 10000]:
            ax.scatter([], [], s=r*0.05, c='none', edgecolors=GRAY, alpha=0.5,
                label=f'{fmt_num(r)}阅读')
        ax.legend(scatterpoints=1, frameon=False, labelspacing=1.5,
            fontsize=8, loc='upper right')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '05_spu_scatter.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 6: Project Cost TOP10 ==========
    print('Chart 6: Project Cost TOP10...')
    if proj_top:
        fig, ax = plt.subplots(figsize=(10, 6))
        projects = [p['name'][:40].replace('\t', ' ').replace('\n', ' ') for p in proj_top[:10][::-1]]
        costs_p = [p['cost'] for p in proj_top[:10]][::-1]
        cpes_p = [p['cpe'] for p in proj_top[:10]][::-1]

        y = np.arange(len(projects))
        cpe_colors = []
        for c in cpes_p:
            if c > 40: cpe_colors.append(RED)
            elif c > 20: cpe_colors.append(ORANGE)
            elif c > 10: cpe_colors.append(YELLOW)
            else: cpe_colors.append(GREEN)

        bars = ax.barh(y, costs_p, color=cpe_colors, edgecolor='white',
            height=0.6, alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(projects, fontsize=8)
        ax.set_xlabel('成本 (万元)', fontsize=10)
        ax.set_title('合作项目成本TOP10 (颜色=CPE效率)', fontsize=14,
            fontweight='bold', pad=15, color=BLUE)

        for i, (bar, cost, cpe) in enumerate(zip(bars, costs_p, cpes_p)):
            ax.text(bar.get_width() + max(costs_p)*0.01, bar.get_y() + bar.get_height()/2,
                f'{cost/1e4:.1f}万 | CPE:{cpe:.1f}元',
                va='center', fontsize=8, fontweight='bold')

        legend_elements = [
            mpatches.Patch(facecolor=GREEN, alpha=0.85, label='CPE<10 (高效)'),
            mpatches.Patch(facecolor=YELLOW, alpha=0.85, label='CPE 10-20'),
            mpatches.Patch(facecolor=ORANGE, alpha=0.85, label='CPE 20-40'),
            mpatches.Patch(facecolor=RED, alpha=0.85, label='CPE>40 (低效)'),
        ]
        ax.legend(handles=legend_elements, fontsize=8, loc='lower right')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '06_project_cost_top10.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 7: CPE by Fan Tier ==========
    print('Chart 7: CPE by Fan Tier...')
    if tiers:
        fig, ax1 = plt.subplots(figsize=(8, 5))
        tier_names = list(tiers.keys())
        cpes_t = [tiers[t]['cpe'] for t in tier_names]
        cost_shares = [tiers[t]['cost_pct'] for t in tier_names]

        x = np.arange(len(tier_names))
        ax1.plot(x, cpes_t, 'o-', color=DARK_BLUE, linewidth=2.5, markersize=8,
            markerfacecolor='white', markeredgewidth=2.5, zorder=3, label='CPE (元)')

        for i, v in enumerate(cpes_t):
            ax1.annotate(f'{v:.2f}元', (i, v), textcoords='offset points',
                xytext=(0, 12), ha='center', fontsize=9, fontweight='bold', color=DARK_BLUE)

        ax1.set_ylabel('CPE (元)', fontsize=11, fontweight='bold', color=DARK_BLUE)
        ax1.set_xticks(x)
        short_names = [t.replace('（', '\n(').replace('）', ')') for t in tier_names]
        ax1.set_xticklabels(short_names, fontsize=9)
        ax1.set_title('粉丝梯队 CPE 趋势', fontsize=16, fontweight='bold', pad=15, color=BLUE)

        ax2 = ax1.twinx()
        bars = ax2.bar(x, cost_shares, width=0.4, color=LIGHT_BLUE, alpha=0.5,
            edgecolor='white', label='成本占比 (%)', zorder=1)
        ax2.set_ylabel('成本占比 (%)', fontsize=11, fontweight='bold', color=DARK_GRAY)
        for i, v in enumerate(cost_shares):
            ax2.text(i, v + 0.5, f'{v:.1f}%', ha='center', fontsize=8,
                fontweight='bold', color=DARK_GRAY)

        max_cpe = max(cpes_t) if cpes_t else 0
        min_cpe = min(cpes_t) if cpes_t else 0
        if max_cpe > 0 and min_cpe > 0:
            ratio = max_cpe / min_cpe
            ax1.annotate(f'尾部CPE是头部的{ratio:.1f}倍',
                xy=(0, max_cpe), xytext=(1.5, max_cpe * 0.8),
                fontsize=9, fontweight='bold', color=RED,
                arrowprops=dict(arrowstyle='->', color=RED, lw=1.5))

        lines1, labels1 = ax1.get_legend_handles_labels()
        bars2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + bars2, labels1 + labels2, fontsize=9,
            loc='upper right')
        ax1.spines['top'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '07_cpe_fan_tier.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 8: Conversion Funnel ==========
    print('Chart 8: Conversion Funnel...')
    if conv and conv.get('count', 0) > 0:
        fig, ax = plt.subplots(figsize=(8, 6))
        stages = ['站外活跃行为', '新访客', '搜索进店', '加购', '收藏商品', '成交']
        values_f = [conv.get('active_uv',0), conv.get('new_visitor_uv',0),
                   conv.get('search_uv',0), conv.get('cart_uv',0),
                   conv.get('fav_product_uv',0), conv.get('deal_uv',0)]
        max_val = values_f[0] if values_f[0] > 0 else 1
        n_stages = len(stages)
        bar_h = 0.7
        y_pos = np.arange(n_stages)[::-1]
        colors_f = [DARK_BLUE, '#2E75B6', '#5B9BD5', '#85C1E9', '#AED6F1', '#D6EAF8']

        for i, (stage, val, color) in enumerate(zip(stages, values_f, colors_f)):
            width_ratio = val / max_val
            left = (1 - width_ratio) / 2
            bar = ax.barh(y_pos[i], width_ratio, height=bar_h,
                left=left, color=color, edgecolor='white', linewidth=1.5, zorder=3)
            ax.text(0.5, y_pos[i], f'{stage}\n{val:,}人',
                ha='center', va='center', fontsize=9, fontweight='bold',
                color='white', zorder=4)
            if i < n_stages - 1:
                rate = values_f[i+1] / values_f[i] * 100 if values_f[i] > 0 else 0
                ax.text(1.02, y_pos[i], f'→ {rate:.1f}%',
                    ha='left', va='center', fontsize=9, fontweight='bold', color=RED, zorder=4)

        ax.set_xlim(0, 1.15)
        ax.set_title(f'站外转化漏斗 (有数据笔记: {conv.get("count",0)}篇)',
            fontsize=16, fontweight='bold', pad=15, color=BLUE)
        ax.set_yticks(y_pos)
        ax.set_yticklabels([''] * n_stages)
        ax.axis('off')

        avg_pur = conv.get('avg_purchase_rate', 0)
        avg_cart = conv.get('avg_cart_rate', 0)
        cart_deal = conv.get('cart_to_deal_pct', 0)
        ax.text(0.5, -0.7, f'平均购买率: {avg_pur:.2f}%  |  平均加购率: {avg_cart:.2f}%  |  加购→成交: {cart_deal:.2f}%',
            ha='center', fontsize=10, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=ACCENT_BLUE, edgecolor=DARK_BLUE),
            color=DARK_BLUE)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '08_conversion_funnel.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 9: Component CTR ==========
    print('Chart 9: Component CTR...')
    if comps:
        fig, ax = plt.subplots(figsize=(8, 4))
        comp_names = list(comps.keys())
        ctrs = [comps[c]['ctr'] for c in comp_names]
        usages = []
        # Count usage by checking original data is not available here, use relative indicator
        for c in comp_names:
            usages.append(comps[c].get('usage', 0))

        colors_ctr = []
        for ctr in ctrs:
            if ctr > 10: colors_ctr.append(GREEN)
            elif ctr > 1: colors_ctr.append(DARK_BLUE)
            else: colors_ctr.append(GRAY)

        bars = ax.bar(comp_names, ctrs, color=colors_ctr, edgecolor='white',
            width=0.55, alpha=0.85)
        ax.set_ylabel('CTR (%)', fontsize=11)
        ax.set_title('各组件CTR对比', fontsize=16, fontweight='bold', pad=15, color=BLUE)

        max_ctr = max(ctrs) if ctrs else 1
        for bar, ctr in zip(bars, ctrs):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max_ctr*0.02,
                f'{ctr:.2f}%', ha='center', fontsize=12, fontweight='bold')
            if ctr > 5:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 0.4,
                    f'CTR最高', ha='center', fontsize=9, color='white', fontweight='bold')

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        if max_ctr > 0 and len(ctrs) >= 2:
            min_ctr = min([c for c in ctrs if c > 0]) if any(c > 0 for c in ctrs) else 0.01
            ratio_comp = max_ctr / min_ctr
            max_idx = ctrs.index(max(ctrs))
            ax.text(0.02, 0.92, f'{comp_names[max_idx]}CTR是最低组件的{ratio_comp:.0f}倍',
                transform=ax.transAxes, fontsize=10, fontweight='bold', color=RED,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FADBD8', edgecolor=RED))

        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '09_component_ctr.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 10: Sentiment Distribution Pie ==========
    if 'comment_analysis' in data and data['comment_analysis'].get('sentiment_distribution'):
        print('Chart 10: Sentiment Distribution...')
        sd = data['comment_analysis']['sentiment_distribution']
        fig, ax = plt.subplots(figsize=(7, 6))
        labels = []
        sizes = []
        colors_pie = []
        for key, label_text, color in [('positive', '正面', GREEN), ('neutral', '中性', LIGHT_BLUE), ('negative', '负面', RED)]:
            if key in sd:
                pct = sd[key].get('pct', 0)
                if pct > 0:
                    labels.append(f'{label_text} {pct:.1f}%')
                    sizes.append(pct)
                    colors_pie.append(color)

        if sizes:
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors_pie,
                autopct='%1.1f%%', startangle=90,
                textprops={'fontsize': 12, 'fontweight': 'bold'},
                pctdistance=0.75, wedgeprops=dict(width=0.55, edgecolor='white', linewidth=2))
            for t in autotexts:
                t.set_color('white')
                t.set_fontsize(13)
                t.set_fontweight('bold')

            total_c = data['comment_analysis'].get('overall', {}).get('total_comments', 0)
            ax.text(0, -1.3, f'总评论数: {total_c:,}', fontsize=11, ha='center',
                color=DARK_BLUE, fontweight='bold')
            ax.set_title('评论情感分布', fontsize=16, fontweight='bold', pad=20, color=BLUE)
            plt.tight_layout()
            plt.savefig(os.path.join(chart_dir, '10_sentiment_pie.png'), dpi=150, bbox_inches='tight')
            plt.close()

    # ========== CHART 11: Comment Sub-category Bar ==========
    if 'comment_analysis' in data and data['comment_analysis'].get('sub_categories'):
        print('Chart 11: Comment Sub-categories...')
        cats = data['comment_analysis']['sub_categories']
        sorted_cats = sorted(cats.items(), key=lambda x: x[1]['count'], reverse=True)
        cat_names = [c[0] for c in sorted_cats]
        cat_counts = [c[1]['count'] for c in sorted_cats]
        cat_pcts = [c[1]['pct'] for c in sorted_cats]

        fig, ax = plt.subplots(figsize=(9, max(4, len(cat_names) * 0.5)))
        y = np.arange(len(cat_names))
        bars = ax.barh(y, cat_counts, color=DARK_BLUE, edgecolor='white', height=0.6)
        ax.set_yticks(y)
        ax.set_yticklabels(cat_names, fontsize=11)
        ax.set_xlabel('评论数', fontsize=10)
        ax.set_title('评论子类别分布', fontsize=16, fontweight='bold', pad=15, color=BLUE)

        for bar, count, pct in zip(bars, cat_counts, cat_pcts):
            ax.text(bar.get_width() + max(cat_counts) * 0.01, bar.get_y() + bar.get_height() / 2,
                f'{count} ({pct:.1f}%)', va='center', fontsize=9, fontweight='bold', color=DARK_BLUE)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(chart_dir, '11_comment_categories_bar.png'), dpi=150, bbox_inches='tight')
        plt.close()

    # ========== CHART 12: Video Content Themes ==========
    if 'video_analysis' in data and data['video_analysis'].get('video_notes'):
        print('Chart 12: Video Content Themes...')
        vn_list = data['video_analysis']['video_notes']

        # Collect all themes across videos
        all_themes = []
        all_styles = []
        theme_counts = Counter()
        for vn in vn_list:
            llm = vn.get('llm_analysis', {})
            for t in llm.get('content_themes', []):
                theme_counts[t] += 1
                all_themes.append(t)
            for s in llm.get('visual_style', []):
                all_styles.append(s)

        if theme_counts:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

            # Left: content themes
            top_themes = theme_counts.most_common(10)
            t_names = [t[0] for t in top_themes]
            t_vals = [t[1] for t in top_themes]
            y = np.arange(len(t_names))
            ax1.barh(y, t_vals, color=DARK_BLUE, edgecolor='white', height=0.5)
            ax1.set_yticks(y)
            ax1.set_yticklabels(t_names, fontsize=10)
            ax1.set_xlabel('出现次数', fontsize=10)
            ax1.set_title('视频内容主题', fontsize=14, fontweight='bold', pad=10, color=BLUE)
            for bar, val in zip(ax1.patches, t_vals):
                ax1.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                    str(val), va='center', fontsize=9, fontweight='bold', color=DARK_BLUE)
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)

            # Right: visual styles
            style_counts = Counter(all_styles)
            top_styles = style_counts.most_common(8)
            s_names = [s[0] for s in top_styles]
            s_vals = [s[1] for s in top_styles]
            y2 = np.arange(len(s_names))
            ax2.barh(y2, s_vals, color=LIGHT_BLUE, edgecolor='white', height=0.5)
            ax2.set_yticks(y2)
            ax2.set_yticklabels(s_names, fontsize=10)
            ax2.set_xlabel('出现次数', fontsize=10)
            ax2.set_title('视觉风格', fontsize=14, fontweight='bold', pad=10, color=BLUE)
            for bar, val in zip(ax2.patches, s_vals):
                ax2.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                    str(val), va='center', fontsize=9, fontweight='bold', color=DARK_BLUE)
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)

            plt.suptitle(f'视频内容分析 (共 {len(vn_list)} 篇)', fontsize=16, fontweight='bold', color=BLUE)
            plt.tight_layout()
            plt.savefig(os.path.join(chart_dir, '12_video_themes.png'), dpi=150, bbox_inches='tight')
            plt.close()

    # Return chart file list
    charts = []
    for f in sorted(os.listdir(chart_dir)):
        if f.endswith('.png'):
            charts.append(os.path.join(chart_dir, f))
    return charts

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"用法: python generate_charts.py <分析结果JSON> <图表输出目录>")
        sys.exit(1)
    generate(sys.argv[1], sys.argv[2])
