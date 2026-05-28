# -*- coding: utf-8 -*-
"""
analyze_video_number.py — 视频号 Excel 数据分析
使用 column_matcher 模块实现灵活的列名同义词识别
支持不同 Excel 文件的列名变体和平台差异
"""
import pandas as pd
import numpy as np
import json
import sys
import os
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from column_matcher import (
    detect_platform, detect_all_columns, detect_header_row, clean_name,
    match_column, UNIVERSAL_SYNONYMS
)


def excel_date_to_str(serial):
    """Excel serial date to ISO string"""
    try:
        base = datetime(1899, 12, 30)
        dt = base + timedelta(days=int(float(serial)))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return str(serial)


def parse_num_series(s):
    """Convert series to float"""
    def convert(val):
        if pd.isna(val) or val == '-' or val == '':
            return 0.0
        try:
            return float(val)
        except Exception:
            return 0.0
    return s.apply(convert)


def parse_pct_series(s):
    """Convert percentage series to float (handles both decimal and percent forms)"""
    def convert(val):
        if pd.isna(val) or val == '-' or val == '':
            return 0.0
        try:
            s_val = str(val).replace('%', '').strip()
            v = float(s_val)
            if v > 1:
                return v / 100.0
            return v
        except Exception:
            return 0.0
    return s.apply(convert)


def analyze(data_path, output_path):
    """Main analysis function"""
    print(f"读取视频号Excel: {data_path}")

    # Detect header row dynamically
    header_row = detect_header_row(data_path)
    print(f"检测到 header 行: {header_row}")

    df = pd.read_excel(data_path, header=header_row - 1)
    print(f"数据维度: {df.shape[0]} 行 × {df.shape[1]} 列")

    col_names = list(df.columns)
    # Use shared column matcher with platform-aware detection
    col_map = detect_all_columns(col_names, platform='video_number')

    print(f"成功映射 {len(col_map)} 个指标")
    for k, v in col_map.items():
        print(f"  {k} -> Col {v}: {col_names[v]}")

    def gs(metric, default=0):
        """Get series safely"""
        if metric in col_map:
            return df.iloc[:, col_map[metric]].fillna(default)
        return pd.Series([default] * len(df))

    # Core numeric columns
    exposure = parse_num_series(gs('col_exposure'))
    interaction = parse_num_series(gs('col_interaction'))
    cost = parse_num_series(gs('col_cost'))
    fans = parse_num_series(gs('col_fans'))

    # Engagement breakdown
    likes = parse_num_series(gs('col_likes'))
    comments = parse_num_series(gs('col_comments'))
    shares = parse_num_series(gs('col_shares'))
    private_likes = parse_num_series(gs('col_private_likes'))

    # Rates
    completion_rate = parse_pct_series(gs('col_completion_rate'))
    mention_rate = parse_pct_series(gs('col_mention_rate'))

    # Predicted vs actual
    pred_cpm = parse_num_series(gs('col_pred_cpm'))
    pred_cpe = parse_num_series(gs('col_pred_cpe'))
    actual_cpm = parse_num_series(gs('col_cpm'))
    actual_cpe = parse_num_series(gs('col_cpe'))

    # Avg predicted (平均曝光量, 平均互动量)
    avg_exposure_pred = parse_num_series(gs('col_avg_exposure'))
    avg_interaction_pred = parse_num_series(gs('col_avg_interaction'))

    # String columns
    content_type = gs('col_content_type', '').astype(str).str.strip()
    nickname = gs('col_nickname', '').astype(str).str.strip()
    coop_format = gs('cooperation_format', '').astype(str).str.strip()
    influencer_tier = gs('col_tier', '').astype(str).str.strip()
    content_angle = gs('col_content_angle', '').astype(str).str.strip()
    platform_val = gs('col_platform', '').astype(str).str.strip()

    # Date column
    date_raw = gs('col_date', '')
    dates = []
    for v in date_raw:
        if pd.isna(v):
            dates.append('')
        else:
            dates.append(excel_date_to_str(v))

    n = len(df)
    valid_mask = (exposure > 0) | (interaction > 0)
    n_valid = int(valid_mask.sum())
    total_cost = float(cost.sum())
    total_exposure = float(exposure.sum())
    total_interaction = float(interaction.sum())

    # ========== Meta ==========
    date_vals = [d for d in dates if d]
    date_range = f"{min(date_vals)} ~ {max(date_vals)}" if date_vals else '未知'

    meta = {
        'total_notes': n_valid,
        'platform': '视频号',
        'date_range': date_range,
        'total_cost': total_cost,
    }

    # ========== Core Metrics ==========
    cpm = total_cost / total_exposure * 1000 if total_exposure > 0 else 0
    cpe = total_cost / total_interaction if total_interaction > 0 else 0

    core = {
        'total_exposure': total_exposure,
        'avg_exposure': total_exposure / n_valid if n_valid > 0 else 0,
        'total_interaction': total_interaction,
        'avg_interaction': total_interaction / n_valid if n_valid > 0 else 0,
        'total_likes': float(likes.sum()),
        'total_comments': float(comments.sum()),
        'total_shares': float(shares.sum()),
        'total_private_likes': float(private_likes.sum()),
        'total_cost': total_cost,
        'cpm': cpm,
        'cpe': cpe,
    }

    # ========== Engagement Detail ==========
    total_eng = likes.sum() + comments.sum() + shares.sum() + private_likes.sum()
    engagement = {
        'total_likes': float(likes.sum()),
        'total_comments': float(comments.sum()),
        'total_shares': float(shares.sum()),
        'total_private_likes': float(private_likes.sum()),
        'likes_pct': float(likes.sum() / total_eng * 100) if total_eng > 0 else 0,
        'comments_pct': float(comments.sum() / total_eng * 100) if total_eng > 0 else 0,
        'shares_pct': float(shares.sum() / total_eng * 100) if total_eng > 0 else 0,
        'private_likes_pct': float(private_likes.sum() / total_eng * 100) if total_eng > 0 else 0,
    }

    # ========== Content Types (达人类型) ==========
    content_types = {}
    for t in content_type.unique():
        if not t or t == 'nan':
            continue
        mask = content_type == t
        d = {
            'count': int(mask.sum()),
            'exposure': float(exposure[mask].sum()),
            'interaction': float(interaction[mask].sum()),
            'cost': float(cost[mask].sum()),
        }
        d['cpm'] = d['cost'] / d['exposure'] * 1000 if d['exposure'] > 0 else 0
        d['cpe'] = d['cost'] / d['interaction'] if d['interaction'] > 0 else 0
        content_types[t] = d

    # ========== Cooperation Formats (合作形式) ==========
    coop_formats = {}
    for cf in coop_format.unique():
        if not cf or cf == 'nan':
            continue
        mask = coop_format == cf
        d = {
            'count': int(mask.sum()),
            'exposure': float(exposure[mask].sum()),
            'interaction': float(interaction[mask].sum()),
            'cost': float(cost[mask].sum()),
        }
        d['cpm'] = d['cost'] / d['exposure'] * 1000 if d['exposure'] > 0 else 0
        d['cpe'] = d['cost'] / d['interaction'] if d['interaction'] > 0 else 0
        coop_formats[cf] = d

    # ========== Influencer Tiers (达人量级) ==========
    influencer_tiers = {}
    for tier in influencer_tier.unique():
        if not tier or tier == 'nan':
            continue
        mask = influencer_tier == tier
        d = {
            'count': int(mask.sum()),
            'exposure': float(exposure[mask].sum()),
            'interaction': float(interaction[mask].sum()),
            'cost': float(cost[mask].sum()),
        }
        d['cpm'] = d['cost'] / d['exposure'] * 1000 if d['exposure'] > 0 else 0
        d['cpe'] = d['cost'] / d['interaction'] if d['interaction'] > 0 else 0
        valid_cr = completion_rate[mask]
        d['avg_completion_rate'] = float(valid_cr.mean() * 100) if valid_cr.sum() > 0 else 0
        valid_mr = mention_rate[mask]
        d['avg_mention_rate'] = float(valid_mr.mean() * 100) if valid_mr.sum() > 0 else 0
        influencer_tiers[tier] = d

    # ========== Content Angles (切角方向) ==========
    content_angles = {}
    for angle in content_angle.unique():
        if not angle or angle == 'nan':
            continue
        mask = content_angle == angle
        d = {
            'count': int(mask.sum()),
            'exposure': float(exposure[mask].sum()),
            'interaction': float(interaction[mask].sum()),
            'cost': float(cost[mask].sum()),
        }
        d['cpm'] = d['cost'] / d['exposure'] * 1000 if d['exposure'] > 0 else 0
        d['cpe'] = d['cost'] / d['interaction'] if d['interaction'] > 0 else 0
        valid_cr = completion_rate[mask]
        d['avg_completion_rate'] = float(valid_cr.mean() * 100) if valid_cr.sum() > 0 else 0
        valid_mr = mention_rate[mask]
        d['avg_mention_rate'] = float(valid_mr.mean() * 100) if valid_mr.sum() > 0 else 0
        content_angles[angle] = d

    # ========== Date Trend ==========
    date_trend = {}
    for i, d_str in enumerate(dates):
        if not d_str:
            continue
        if d_str not in date_trend:
            date_trend[d_str] = {'exposure': 0.0, 'interaction': 0.0, 'count': 0, 'cost': 0.0}
        date_trend[d_str]['exposure'] += float(exposure.iloc[i])
        date_trend[d_str]['interaction'] += float(interaction.iloc[i])
        date_trend[d_str]['count'] += 1
        date_trend[d_str]['cost'] += float(cost.iloc[i])
    date_trend = dict(sorted(date_trend.items()))

    # ========== Predicted vs Actual ==========
    valid_pred_cpm = pred_cpm[pred_cpm > 0]
    valid_actual_cpm = actual_cpm[actual_cpm > 0]
    valid_pred_cpe = pred_cpe[pred_cpe > 0]
    valid_actual_cpe = actual_cpe[actual_cpe > 0]

    pred_vs_actual = {
        'cpm': {
            'pred_avg': float(valid_pred_cpm.mean()) if len(valid_pred_cpm) > 0 else 0,
            'actual_avg': float(valid_actual_cpm.mean()) if len(valid_actual_cpm) > 0 else 0,
        },
        'cpe': {
            'pred_avg': float(valid_pred_cpe.mean()) if len(valid_pred_cpe) > 0 else 0,
            'actual_avg': float(valid_actual_cpe.mean()) if len(valid_actual_cpe) > 0 else 0,
        },
    }
    for metric in ['cpm', 'cpe']:
        pred = pred_vs_actual[metric]['pred_avg']
        actual = pred_vs_actual[metric]['actual_avg']
        if pred > 0:
            pred_vs_actual[metric]['diff_pct'] = (actual - pred) / pred * 100
        else:
            pred_vs_actual[metric]['diff_pct'] = 0

    # ========== Completion Rate Stats ==========
    valid_cr_all = completion_rate[completion_rate > 0]
    completion_rate_stats = {
        'avg': float(valid_cr_all.mean() * 100) if len(valid_cr_all) > 0 else 0,
        'median': float(valid_cr_all.median() * 100) if len(valid_cr_all) > 0 else 0,
        'max': float(completion_rate.max() * 100),
        'min': float(completion_rate[completion_rate > 0].min() * 100) if (completion_rate > 0).any() else 0,
    }

    # ========== Mention Rate Stats ==========
    valid_mr_all = mention_rate[mention_rate > 0]
    mention_rate_stats = {
        'avg': float(valid_mr_all.mean() * 100) if len(valid_mr_all) > 0 else 0,
        'median': float(valid_mr_all.median() * 100) if len(valid_mr_all) > 0 else 0,
        'max': float(mention_rate.max() * 100),
        'min': float(mention_rate[mention_rate > 0].min() * 100) if (mention_rate > 0).any() else 0,
    }

    # ========== Top Engagement ==========
    top_engagement = []
    sort_idx = interaction.argsort()[::-1]
    for i in sort_idx[:10]:
        if interaction.iloc[i] > 0:
            top_engagement.append({
                'nickname': str(nickname.iloc[i]),
                'content_type': str(content_type.iloc[i]),
                'influencer_tier': str(influencer_tier.iloc[i]),
                'cooperation_format': str(coop_format.iloc[i]),
                'content_angle': str(content_angle.iloc[i]),
                'exposure': float(exposure.iloc[i]),
                'interaction': float(interaction.iloc[i]),
                'likes': float(likes.iloc[i]),
                'comments': float(comments.iloc[i]),
                'shares': float(shares.iloc[i]),
                'private_likes': float(private_likes.iloc[i]),
                'completion_rate': float(completion_rate.iloc[i] * 100),
                'mention_rate': float(mention_rate.iloc[i] * 100),
                'cost': float(cost.iloc[i]),
                'cpm': float(actual_cpm.iloc[i]) if actual_cpm.iloc[i] > 0 else float(cost.iloc[i] / exposure.iloc[i] * 1000) if exposure.iloc[i] > 0 else 0,
                'cpe': float(actual_cpe.iloc[i]) if actual_cpe.iloc[i] > 0 else float(cost.iloc[i] / interaction.iloc[i]) if interaction.iloc[i] > 0 else 0,
                'pred_cpm': float(pred_cpm.iloc[i]),
                'pred_cpe': float(pred_cpe.iloc[i]),
                'pub_date': dates[i],
            })

    # ========== Predicted vs Actual Per-Row Comparison ==========
    pred_actual_rows = []
    for i in range(n):
        pred_exp = float(avg_exposure_pred.iloc[i])
        pred_int = float(avg_interaction_pred.iloc[i])
        pred_cpm_val = float(pred_cpm.iloc[i])
        pred_cpe_val = float(pred_cpe.iloc[i])
        actual_exp = float(exposure.iloc[i])
        actual_int = float(interaction.iloc[i])
        actual_cpm_val = float(actual_cpm.iloc[i])
        actual_cpe_val = float(actual_cpe.iloc[i])
        cost_val = float(cost.iloc[i])

        exp_rate = actual_exp / pred_exp * 100 if pred_exp > 0 else 0
        int_rate = actual_int / pred_int * 100 if pred_int > 0 else 0
        cpm_rate = pred_cpm_val / actual_cpm_val * 100 if actual_cpm_val > 0 and pred_cpm_val > 0 else 0
        cpe_rate = pred_cpe_val / actual_cpe_val * 100 if actual_cpe_val > 0 and pred_cpe_val > 0 else 0
        avg_achievement = (exp_rate + int_rate + cpm_rate + cpe_rate) / 4 if (exp_rate + int_rate + cpm_rate + cpe_rate) > 0 else 0

        if avg_achievement >= 100:
            status = '超预期'
        elif avg_achievement >= 80:
            status = '综合达成'
        else:
            status = '不及预期'

        pred_actual_rows.append({
            'nickname': str(nickname.iloc[i]),
            'content_type': str(content_type.iloc[i]),
            'influencer_tier': str(influencer_tier.iloc[i]),
            'content_angle': str(content_angle.iloc[i]),
            'pred_exposure': pred_exp,
            'actual_exposure': actual_exp,
            'exp_achievement': round(exp_rate, 1),
            'pred_interaction': pred_int,
            'actual_interaction': actual_int,
            'int_achievement': round(int_rate, 1),
            'pred_cpm': pred_cpm_val,
            'actual_cpm': actual_cpm_val,
            'cpm_rate': round(cpm_rate, 1),
            'pred_cpe': pred_cpe_val,
            'actual_cpe': actual_cpe_val,
            'cpe_rate': round(cpe_rate, 1),
            'avg_achievement': round(avg_achievement, 1),
            'status': status,
            'cost': cost_val,
            'pub_date': dates[i],
        })

    result = {
        'meta': meta,
        'core_metrics': core,
        'engagement_detail': engagement,
        'content_types': content_types,
        'cooperation_formats': coop_formats,
        'influencer_tiers': influencer_tiers,
        'content_angles': content_angles,
        'date_trend': date_trend,
        'predicted_vs_actual': pred_vs_actual,
        'pred_actual_rows': pred_actual_rows,
        'completion_rate_stats': completion_rate_stats,
        'mention_rate_stats': mention_rate_stats,
        'top_engagement': top_engagement,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n分析完成！结果已保存至: {output_path}")
    print(f"总笔记数: {n_valid}")
    print(f"总曝光: {total_exposure:,.0f}")
    print(f"总互动: {total_interaction:,.0f}")
    print(f"CPE: {cpe:.2f}")
    print(f"CPM: {cpm:.2f}")

    return result


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"用法: python analyze_video_number.py <Excel文件路径> <输出JSON路径>")
        sys.exit(1)
    analyze(sys.argv[1], sys.argv[2])
