# -*- coding: utf-8 -*-
"""
analyze_data.py — 读取小红书Excel数据，自动识别列名，计算全量指标
使用pandas加速大数据量处理
输出：analysis_result.json
"""
import pandas as pd
import numpy as np
import json
import sys
import os
from collections import defaultdict

def parse_pct_series(s):
    """将百分比字符串Series转为float"""
    def convert(val):
        if pd.isna(val) or val == '-' or val == '':
            return 0.0
        try:
            s = str(val).replace('%', '').strip()
            return float(s) / 100.0
        except:
            return 0.0
    return s.apply(convert)

def parse_num_series(s):
    """将数值字符串Series转为float"""
    def convert(val):
        if pd.isna(val) or val == '-' or val == '':
            return 0.0
        try:
            return float(val)
        except:
            return 0.0
    return s.apply(convert)

def detect_columns(col_names):
    """通过 column_matcher 模块识别各指标对应的列名"""
    from column_matcher import detect_all_columns
    return detect_all_columns(col_names, platform='xhs')

def analyze(data_path, output_path):
    """主分析函数"""
    print(f"读取Excel: {data_path}")

    from column_matcher import detect_header_row
    header_row = detect_header_row(data_path)
    print(f"检测到 header 行: {header_row}")

    df = pd.read_excel(data_path, header=header_row - 1)
    print(f"数据维度: {df.shape[0]} 行 × {df.shape[1]} 列")

    col_names = list(df.columns)
    col_map = detect_columns(col_names)

    print(f"检测到 {len(col_names)} 个列")
    print(f"成功映射 {len(col_map)} 个指标")
    for k, v in col_map.items():
        print(f"  {k} -> Col {v}: {col_names[v]}")

    # Helper to get series safely
    def gs(metric, default=0):
        if metric in col_map:
            return df.iloc[:, col_map[metric]].fillna(default)
        return pd.Series([default] * len(df))

    # Parse numeric columns
    exposure = parse_num_series(gs('col_exposure'))
    reads = parse_num_series(gs('col_reads'))
    interaction = parse_num_series(gs('col_interaction'))
    likes = parse_num_series(gs('col_likes'))
    comments = parse_num_series(gs('col_comments'))
    favorites = parse_num_series(gs('col_favorites'))
    shares = parse_num_series(gs('col_shares'))
    follows = parse_num_series(gs('col_follows'))
    nat_exposure = parse_num_series(gs('col_nat_exposure'))
    nat_reads = parse_num_series(gs('col_nat_reads'))
    promo_exposure = parse_num_series(gs('col_promo_exposure'))
    promo_reads = parse_num_series(gs('col_promo_reads'))
    heat_exposure = parse_num_series(gs('col_heat_exposure'))
    heat_reads = parse_num_series(gs('col_heat_reads'))
    cost = parse_num_series(gs('col_total_cost'))
    pgy_cost = parse_num_series(gs('col_pgy_cost'))
    ad_cost = parse_num_series(gs('col_ad_cost'))
    fans = parse_num_series(gs('col_fans'))
    irate = parse_pct_series(gs('col_interaction_rate'))

    # String columns
    note_type = gs('col_note_type', '').astype(str).str.strip()
    health = gs('col_health', '').astype(str).str.strip()
    source = gs('col_source', '').astype(str).str.strip()
    spu = gs('col_spu', '未知').astype(str).str.strip()
    spu = spu.replace('-', '未知')
    coop = gs('col_coop_name', '未知').astype(str).str.strip()
    title = gs('col_note_title', '').astype(str)

    # Conversion columns
    active_uv = parse_num_series(gs('col_active_uv_30d'))
    new_visitor_uv = parse_num_series(gs('col_new_visitor_uv_30d'))
    search_uv = parse_num_series(gs('col_search_uv_30d'))
    cart_uv = parse_num_series(gs('col_cart_uv_30d'))
    fav_product_uv = parse_num_series(gs('col_fav_product_uv_30d'))
    deal_uv = parse_num_series(gs('col_deal_uv_30d'))
    follow_shop_uv = parse_num_series(gs('col_follow_shop_uv_30d'))
    purchase_rate = parse_pct_series(gs('col_purchase_rate_30d'))
    cart_rate = parse_pct_series(gs('col_cart_rate_30d'))

    # Component columns
    comp_text_exp = parse_num_series(gs('col_comp_text_exp'))
    comp_text_click = parse_num_series(gs('col_comp_text_click'))
    comp_bottom_exp = parse_num_series(gs('col_comp_bottom_exp'))
    comp_bottom_click = parse_num_series(gs('col_comp_bottom_click'))
    comp_interact_exp = parse_num_series(gs('col_comp_interact_exp'))
    comp_interact_click = parse_num_series(gs('col_comp_interact_click'))
    comp_comment_exp = parse_num_series(gs('col_comp_comment_exp'))
    comp_comment_click = parse_num_series(gs('col_comp_comment_click'))

    # Traffic source columns - detect by position relative to exposure column
    exp_col_idx = col_map.get('col_exposure', -1)
    # In the original data, traffic source % columns are at positions exp_col+21 to exp_col+32
    # But we use keyword matching instead
    ts_cols = {}
    ts_keywords = {
        'exp_discover': '发现页', 'exp_search': '搜索页', 'exp_profile': '个人页',
        'exp_follow': '关注页', 'exp_nearby': '附近页', 'exp_other': '其他',
        'read_discover': '发现页', 'read_search': '搜索页', 'read_profile': '个人页',
        'read_follow': '关注页', 'read_nearby': '附近页', 'read_other': '其他',
    }
    # Use position-based: after exposure column
    if exp_col_idx >= 0:
        ts_offsets = {
            'exp_discover': 21, 'exp_search': 22, 'exp_profile': 23,
            'exp_follow': 24, 'exp_nearby': 25, 'exp_other': 26,
            'read_discover': 27, 'read_search': 28, 'read_profile': 29,
            'read_follow': 30, 'read_nearby': 31, 'read_other': 32,
        }
        for key, offset in ts_offsets.items():
            idx = exp_col_idx + offset
            if idx < len(col_names):
                ts_cols[key] = parse_pct_series(df.iloc[:, idx])
            else:
                ts_cols[key] = pd.Series([0.0] * len(df))

    # ========== Aggregate metrics ==========
    n = len(df)
    valid_mask = (reads > 0) | (exposure > 0)
    n_valid = valid_mask.sum()

    core = {
        'total_exposure': float(exposure.sum()),
        'total_reads': float(reads.sum()),
        'avg_reads': float(reads.sum() / n_valid) if n_valid > 0 else 0,
        'total_interactions': float(interaction.sum()),
        'total_likes': float(likes.sum()),
        'total_favorites': float(favorites.sum()),
        'total_comments': float(comments.sum()),
        'total_shares': float(shares.sum()),
        'total_follows': float(follows.sum()),
        'avg_interact_rate': float(irate[irate > 0].mean()) if (irate > 0).any() else 0,
        'cpe': float(cost.sum() / interaction.sum()) if interaction.sum() > 0 else 0,
        'cpm': float(cost.sum() / exposure.sum() * 1000) if exposure.sum() > 0 else 0,
        'cpc': float(cost.sum() / reads.sum()) if reads.sum() > 0 else 0,
    }

    traffic = {
        'promo_exposure': float(promo_exposure.sum()),
        'promo_exposure_pct': float(promo_exposure.sum() / exposure.sum() * 100) if exposure.sum() > 0 else 0,
        'promo_reads': float(promo_reads.sum()),
        'promo_reads_pct': float(promo_reads.sum() / reads.sum() * 100) if reads.sum() > 0 else 0,
        'nat_exposure': float(nat_exposure.sum()),
        'nat_exposure_pct': float(nat_exposure.sum() / exposure.sum() * 100) if exposure.sum() > 0 else 0,
        'nat_reads': float(nat_reads.sum()),
        'nat_reads_pct': float(nat_reads.sum() / reads.sum() * 100) if reads.sum() > 0 else 0,
        'heat_exposure': float(heat_exposure.sum()),
        'heat_reads': float(heat_reads.sum()),
        'total_cost': float(cost.sum()),
        'pgy_cost': float(pgy_cost.sum()),
        'ad_cost': float(ad_cost.sum()),
    }

    # Traffic source weighted percentages
    total_exp_src = sum(ts_cols[f'exp_{k}'].sum() for k in ['discover','search','profile','follow','nearby','other'])
    total_read_src = sum(ts_cols[f'read_{k}'].sum() for k in ['discover','search','profile','follow','nearby','other'])

    traffic_sources = {'exp': {}, 'read': {}}
    for ch in ['discover', 'search', 'profile', 'follow', 'nearby', 'other']:
        cn_map = {'discover': '发现页', 'search': '搜索页', 'profile': '个人页',
                  'follow': '关注页', 'nearby': '附近页', 'other': '其他'}
        cn = cn_map[ch]
        traffic_sources['exp'][cn] = float(ts_cols[f'exp_{ch}'].sum() / total_exp_src * 100) if total_exp_src > 0 else 0
        traffic_sources['read'][cn] = float(ts_cols[f'read_{ch}'].sum() / total_read_src * 100) if total_read_src > 0 else 0

    # Meta
    meta = {
        'total_notes': n_valid,
        'video_count': int((note_type == '视频').sum()),
        'image_count': int((note_type == '图文').sum()),
        'abnormal_count': int((health.str.contains('异常', na=False)).sum()),
        'star_count': int((source.str.contains('明星', na=False)).sum()),
    }

    # Content type breakdown
    content_types = {}
    for t in note_type.unique():
        if not t or t == 'nan':
            continue
        mask = note_type == t
        d = {
            'count': int(mask.sum()),
            'reads': float(reads[mask].sum()),
            'exposure': float(exposure[mask].sum()),
            'interact': float(interaction[mask].sum()),
            'cost': float(cost[mask].sum()),
        }
        d['avg_reads'] = d['reads'] / d['count'] if d['count'] > 0 else 0
        d['irate'] = d['interact'] / d['reads'] * 100 if d['reads'] > 0 else 0
        d['cpe'] = d['cost'] / d['interact'] if d['interact'] > 0 else 0
        d['cpm'] = d['cost'] / d['exposure'] * 1000 if d['exposure'] > 0 else 0
        content_types[t] = d

    # SPU breakdown
    spu_groups = df.groupby(spu)
    spu_top = []
    for spu_name, group in spu_groups:
        mask = group.index
        r = reads[mask].sum()
        if r > 0 or len(group) > 10:
            d = {
                'name': spu_name,
                'count': len(group),
                'reads': float(r),
                'exposure': float(exposure[mask].sum()),
                'interact': float(interaction[mask].sum()),
                'cost': float(cost[mask].sum()),
            }
            d['irate'] = d['interact'] / d['reads'] * 100 if d['reads'] > 0 else 0
            spu_top.append(d)
    spu_top.sort(key=lambda x: x['reads'], reverse=True)
    spu_top = spu_top[:10]

    # Project breakdown
    proj_groups = df.groupby(coop)
    proj_top = []
    for proj_name, group in proj_groups:
        mask = group.index
        c = cost[mask].sum()
        if c > 0 or len(group) > 10:
            d = {
                'name': proj_name,
                'count': len(group),
                'reads': float(reads[mask].sum()),
                'cost': float(c),
                'exposure': float(exposure[mask].sum()),
                'interact': float(interaction[mask].sum()),
            }
            d['cpm'] = d['cost'] / d['exposure'] * 1000 if d['exposure'] > 0 else 0
            d['cpe'] = d['cost'] / d['interact'] if d['interact'] > 0 else 0
            d['irate'] = d['interact'] / d['reads'] * 100 if d['reads'] > 0 else 0
            proj_top.append(d)
    proj_top.sort(key=lambda x: x['cost'], reverse=True)
    proj_top = proj_top[:10]

    # Fan tiers
    tier_defs = [('<1万', 0, 10000), ('1-5万', 10000, 50000), ('5-10万', 50000, 100000),
                 ('10-50万', 100000, 500000), ('50-100万', 500000, 1000000), ('>100万', 1000000, 999999999)]
    fan_tiers = {}
    for name, lo, hi in tier_defs:
        mask = (fans >= lo) & (fans < hi)
        d = {
            'count': int(mask.sum()),
            'reads': float(reads[mask].sum()),
            'exposure': float(exposure[mask].sum()),
            'interact': float(interaction[mask].sum()),
            'cost': float(cost[mask].sum()),
        }
        d['avg_reads'] = d['reads'] / d['count'] if d['count'] > 0 else 0
        d['irate'] = d['interact'] / d['reads'] * 100 if d['reads'] > 0 else 0
        d['cpe'] = d['cost'] / d['interact'] if d['interact'] > 0 else 0
        d['cost_pct'] = d['cost'] / cost.sum() * 100 if cost.sum() > 0 else 0
        fan_tiers[name] = d

    # Health breakdown
    health_data = {}
    for h in health.unique():
        if not h or h == 'nan':
            continue
        mask = health == h
        d = {
            'count': int(mask.sum()),
            'avg_reads': float(reads[mask].mean()),
            'total_reads': float(reads[mask].sum()),
            'total_exposure': float(exposure[mask].sum()),
            'pct': float(mask.sum() / n_valid * 100) if n_valid > 0 else 0,
        }
        health_data[h] = d

    # Conversion
    conv_mask = active_uv > 0
    conv_count = int(conv_mask.sum())
    conversion = {}
    if conv_count > 0:
        valid_pr = purchase_rate[purchase_rate > 0]
        valid_cr = cart_rate[cart_rate > 0]
        conversion = {
            'count': conv_count,
            'active_uv': float(active_uv.sum()),
            'new_visitor_uv': float(new_visitor_uv.sum()),
            'search_uv': float(search_uv.sum()),
            'cart_uv': float(cart_uv.sum()),
            'fav_product_uv': float(fav_product_uv.sum()),
            'deal_uv': float(deal_uv.sum()),
            'follow_shop_uv': float(follow_shop_uv.sum()),
            'avg_purchase_rate': float(valid_pr.mean() * 100) if len(valid_pr) > 0 else 0,
            'avg_cart_rate': float(valid_cr.mean() * 100) if len(valid_cr) > 0 else 0,
            'active_to_deal_pct': float(deal_uv.sum() / active_uv.sum() * 100) if active_uv.sum() > 0 else 0,
            'active_to_cart_pct': float(cart_uv.sum() / active_uv.sum() * 100) if active_uv.sum() > 0 else 0,
            'cart_to_deal_pct': float(deal_uv.sum() / cart_uv.sum() * 100) if cart_uv.sum() > 0 else 0,
        }

    # Component CTR
    components = {}
    comp_defs = [
        ('正文组件', comp_text_exp, comp_text_click),
        ('笔记底栏组件', comp_bottom_exp, comp_bottom_click),
        ('互动组件', comp_interact_exp, comp_interact_click),
        ('评论区组件', comp_comment_exp, comp_comment_click),
    ]
    for name, exp_s, click_s in comp_defs:
        total_exp = float(exp_s.sum())
        total_click = float(click_s.sum())
        if total_exp > 0:
            components[name] = {
                'exp': total_exp,
                'click': total_click,
                'ctr': total_click / total_exp * 100,
                'usage': int((exp_s > 0).sum()),
            }

    # TOP notes by reads
    top_reads = []
    sort_idx = reads.argsort()[::-1]
    for i in sort_idx[:10]:
        if reads.iloc[i] > 0:
            top_reads.append({
                'title': str(title.iloc[i])[:60],
                'reads': float(reads.iloc[i]),
                'exposure': float(exposure.iloc[i]),
                'interact': float(interaction.iloc[i]),
                'irate': float(irate.iloc[i] * 100),
                'cost': float(cost.iloc[i]),
                'type': str(note_type.iloc[i]),
                'fans': float(fans.iloc[i]),
                'spu': str(spu.iloc[i])[:40],
            })

    # TOP notes by cost
    top_cost = []
    sort_idx_c = cost.argsort()[::-1]
    for i in sort_idx_c[:10]:
        if cost.iloc[i] > 0:
            top_cost.append({
                'title': str(title.iloc[i])[:60],
                'reads': float(reads.iloc[i]),
                'interact': float(interaction.iloc[i]),
                'cpe': float(cost.iloc[i] / interaction.iloc[i]) if interaction.iloc[i] > 0 else 0,
                'cost': float(cost.iloc[i]),
                'fans': float(fans.iloc[i]),
                'type': str(note_type.iloc[i]),
            })

    result = {
        'meta': meta,
        'core_metrics': core,
        'traffic_structure': traffic,
        'traffic_sources': traffic_sources,
        'content_types': content_types,
        'spu_top': spu_top,
        'proj_top': proj_top,
        'fan_tiers': fan_tiers,
        'health': health_data,
        'conversion': conversion,
        'components': components,
        'top_reads': top_reads,
        'top_cost': top_cost,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n分析完成！结果已保存至: {output_path}")
    print(f"总笔记数: {n_valid}")
    print(f"总曝光: {core['total_exposure']:,.0f}")
    print(f"总阅读: {core['total_reads']:,.0f}")
    print(f"总互动: {core['total_interactions']:,.0f}")
    print(f"CPE: {core['cpe']:.2f}")
    print(f"CPM: {core['cpm']:.2f}")

    return result

def merge_crawl_data(crawled_path, output_path, comment_path=None, video_path=None):
    """
    仅使用爬虫数据生成 analysis_result.json（无 Excel 时）。
    如果有 comment_path / video_path 则一并合并。
    """
    with open(crawled_path, 'r', encoding='utf-8') as f:
        crawled = json.load(f)

    notes = crawled.get('notes', [])
    meta = crawled.get('crawl_metadata', {})

    # 从爬取数据计算基础指标
    video_count = sum(1 for n in notes if n.get('note_type') == 'video')
    image_count = sum(1 for n in notes if n.get('note_type') == 'image')
    total_comments = sum(len(n.get('comments', [])) for n in notes)

    total_likes = sum(n.get('stats', {}).get('likes', 0) for n in notes)
    total_favorites = sum(n.get('stats', {}).get('favorites', 0) for n in notes)
    total_shares_val = sum(n.get('stats', {}).get('shares', 0) for n in notes)
    total_comments_count = sum(n.get('stats', {}).get('comments_count', 0) for n in notes)

    core = {
        'total_exposure': 0,
        'total_reads': 0,
        'avg_reads': 0,
        'total_interactions': total_likes + total_favorites + total_comments_count + total_shares_val,
        'total_likes': total_likes,
        'total_favorites': total_favorites,
        'total_comments': total_comments_count,
        'total_shares': total_shares_val,
        'total_follows': 0,
        'avg_interact_rate': 0,
        'cpe': 0,
        'cpm': 0,
        'cpc': 0,
    }

    # Crawled data summary
    crawl_summary = {
        'notes_crawled': len(notes),
        'video_notes': video_count,
        'image_notes': image_count,
        'total_comments_scraped': total_comments,
        'crawl_success_rate': round(meta.get('successful', 0) / max(meta.get('total_urls', 1), 1), 2),
    }

    result = {
        'meta': {
            'total_notes': len(notes),
            'video_count': video_count,
            'image_count': image_count,
            'abnormal_count': 0,
            'star_count': 0,
        },
        'core_metrics': core,
        'traffic_structure': {
            'promo_exposure': 0, 'promo_exposure_pct': 0,
            'promo_reads': 0, 'promo_reads_pct': 0,
            'nat_exposure': 0, 'nat_exposure_pct': 0,
            'nat_reads': 0, 'nat_reads_pct': 0,
            'heat_exposure': 0, 'heat_reads': 0,
            'total_cost': 0, 'pgy_cost': 0, 'ad_cost': 0,
        },
        'traffic_sources': {'exp': {}, 'read': {}},
        'content_types': {},
        'spu_top': [],
        'proj_top': [],
        'fan_tiers': {},
        'health': {},
        'conversion': {},
        'components': {},
        'top_reads': [],
        'top_cost': [],
        'crawled_data_summary': crawl_summary,
    }

    # Merge comment analysis
    if comment_path and os.path.exists(comment_path):
        with open(comment_path, 'r', encoding='utf-8') as f:
            result['comment_analysis'] = json.load(f)

    # Merge video analysis
    if video_path and os.path.exists(video_path):
        with open(video_path, 'r', encoding='utf-8') as f:
            result['video_analysis'] = json.load(f)

    # Write
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f'\n爬虫数据合并完成！')
    print(f'笔记数: {len(notes)} (视频 {video_count}, 图文 {image_count})')
    print(f'评论数: {total_comments}')
    print(f'结果已保存: {output_path}')

    return result


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"用法:")
        print(f"  python analyze_data.py <Excel文件路径> <输出JSON路径>")
        print(f"  python analyze_data.py --merge-crawl <crawled_notes.json> <输出JSON路径> [--comments comment.json] [--videos video.json]")
        sys.exit(1)

    # Check for --merge-crawl flag
    if sys.argv[1] == '--merge-crawl':
        crawled_path = sys.argv[2]
        output_path = sys.argv[3]
        comment_path = None
        video_path = None

        # Parse optional args
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == '--comments' and i + 1 < len(sys.argv):
                comment_path = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--videos' and i + 1 < len(sys.argv):
                video_path = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        merge_crawl_data(crawled_path, output_path, comment_path, video_path)
    else:
        analyze(sys.argv[1], sys.argv[2])
