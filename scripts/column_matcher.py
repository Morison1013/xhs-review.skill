# -*- coding: utf-8 -*-
"""
column_matcher.py — 多平台 Excel 列名自动匹配
支持同义词识别和平台自适应
"""
import pandas as pd
import numpy as np
import re


def clean_name(name):
    """Normalize column name: remove whitespace, brackets, newlines"""
    s = str(name)
    s = re.sub(r'[\n\r\t]', '', s)
    s = s.replace('（', '(').replace('）', ')')
    s = s.replace('【', '(').replace('】', ')')
    s = s.strip()
    return s


def match_column(col_names, synonyms, priority=None):
    """
    Match Excel columns to metrics using synonym lists.

    Args:
        col_names: list of Excel column names
        synonyms: dict mapping metric_key -> list of synonym strings
        priority: list of metric_keys to try first (for disambiguation)

    Returns:
        dict mapping metric_key -> column_index
    """
    col_map = {}
    used = set()
    cleaned = [clean_name(n) for n in col_names]

    # Try high-priority metrics first
    order = list(synonyms.keys())
    if priority:
        order = sorted(order, key=lambda k: 0 if k in priority else 1)

    for key in order:
        if key in col_map:
            continue
        for syn in synonyms[key]:
            syn_lower = clean_name(syn).lower()
            for i, col in enumerate(cleaned):
                if i in used:
                    continue
                if syn_lower in col.lower():
                    col_map[key] = i
                    used.add(i)
                    break
            if key in col_map:
                break

    return col_map


# ========== 通用指标同义词字典 ==========
# 按 metric_key 组织，每个 key 对应一组可能的列名
UNIVERSAL_SYNONYMS = {
    # === 基础信息 ===
    'col_nickname': ['达人昵称', '博主昵称', '账号昵称', '创作者昵称', '达人名称', '博主名称', '昵称', '账号名称'],
    'col_platform': ['平台', '媒体平台', '发布平台'],
    'col_content_type': ['达人类型', '内容类型', '账号类型', '达人分类', '内容分类', '类目', '垂类', '赛道'],
    'cooperation_format': ['合作形式', '投放形式', '合作方式', '内容形式', '笔记形式', '视频形式'],
    'col_tier': ['达人量级', '达人级别', '粉丝量级', '达人梯队', '账号量级', 'KOL级别'],
    'col_fans': ['粉丝量', '粉丝数', '粉丝（万）', '粉丝(万)', '粉丝量（w）', '粉丝量(w)', '粉丝数(万)', '粉丝数（万）', '总粉丝', '账号粉丝'],
    'col_home_link': ['主页链接', '达人主页', '博主主页', '账号主页', '主页地址', '个人主页'],
    'col_date': ['发布日期', '发布时间', '上线日期', '上线时间', '数据日期', '日期', '投放日期', '发文日期'],
    'col_pub_link': ['发布链接', '链接', '笔记链接', '视频链接', '作品链接', '跳转链接', 'url'],
    'col_content_angle': ['切角方向', '内容方向', '创意方向', '选题方向', '内容主题', '主题', '选题', '痛点方向', '场景'],

    # === 成本 ===
    'col_cost': ['SIPAC价格', 'SIPAC报价', '合作费用', '达人报价', '报价', '金额', '总费用', '成本',
                  '合作金额', '投放金额', '单价', '达人费用', '执行费用', '达人合作费', '合作价',
                  '费用', '消耗', '总消耗'],
    'col_pred_cpm': ['预估cpm', '预估CPM', 'cpm预估', 'CPM预估', '预估千次曝光成本'],
    'col_pred_cpe': ['预估cpe', '预估CPE', 'cpe预估', 'CPE预估', '预估单次互动成本'],
    'col_cpm': ['CPM', 'cpm', '千次曝光成本', '实际cpm', '实际CPM'],
    'col_cpe': ['CPE', 'cpe', '单次互动成本', '实际cpe', '实际CPE'],

    # === 曝光/播放/阅读 ===
    'col_exposure': ['曝光量', '曝光', '播放量', '播放', '展现量', '展现', '覆盖人数', '触达人数', '阅读量'],
    'col_avg_exposure': ['平均曝光量', '平均曝光', '均曝光', '预估曝光', '预估曝光量', '均播放', '均播放量'],
    'col_reads': ['阅读量', '阅读数', '阅读', 'uv', '阅读uv'],
    'col_avg_reads': ['平均阅读量', '平均阅读', '均阅读', '预估阅读', '预估阅读量'],

    # === 互动 ===
    'col_interaction': ['互动量', '互动数', '互动', '总互动', '转评赞', '转评赞总数', '互动总数',
                         '综合互动', '互动总量', '行为总数'],
    'col_avg_interaction': ['平均互动量', '平均互动', '均互动', '预估互动', '预估互动量', '均互动量'],
    'col_interaction_rate': ['互动率', '互动率（%）', '互动率(%)', '综合互动率'],
    'col_likes': ['赞', '点赞量', '点赞数', '点赞', 'like', 'likes', '红心'],
    'col_comments': ['评论量', '评论数', '评论', 'comments'],
    'col_shares': ['分享量', '分享数', '分享', '转发量', '转发数', '转发', 'shares'],
    'col_favorites': ['收藏量', '收藏数', '收藏', 'favorites'],
    'col_follows': ['关注量', '关注数', '关注', '新增关注'],
    'col_private_likes': ['私密赞', '私密点赞', '密赞', '匿名赞', '私密喜欢'],

    # === 视频指标 ===
    'col_completion_rate': ['完播率', '视频完播率', '完成率', '完整播放率'],
    'col_mention_rate': ['评论区提及率', '提及率', '品牌提及率', '评论提及率'],
    'col_5s_play': ['5s播放率', '5s完播率', '5秒播放率'],
    'col_3s_read': ['3s阅读率', '3s完播率'],

    # === 流量来源 ===
    'col_nat_exposure': ['自然曝光', '自然流量曝光', '免费曝光'],
    'col_promo_exposure': ['推广曝光', '付费曝光', '广告曝光', '投放曝光'],
    'col_heat_exposure': ['加热曝光', '聚光曝光', 'DOU+曝光', '薯条曝光', '加热流量'],

    # === 达人合作信息 ===
    'col_coop_name': ['合作项目名称', '合作项目', '项目名称', '合作名称', 'campaign', '活动名称'],
    'col_spu': ['SPU', 'spu', '产品名称', '产品', '推广产品', '推广SPU', '商品名称'],
    'col_brand': ['品牌', '报备品牌', '推广品牌'],
    'col_service_fee': ['服务费', '平台服务费'],
    'col_pgy_cost': ['蒲公英金额', '蒲公英费用', '平台费用'],
    'col_ad_cost': ['广告金额', '广告费用', '投放费用', 'DOU+费用', '薯条费用', '聚光费用'],

    # === 用户画像 ===
    'col_female_pct': ['女性', '女', '女性占比', '女粉占比'],
    'col_male_pct': ['男性', '男', '男性占比', '男粉占比'],
    'col_age_18_24': ['18~24', '18-24', '18-24岁', '18~24岁'],
    'col_age_25_34': ['25~34', '25-34', '25-34岁', '25~34岁'],

    # === 转化漏斗 ===
    'col_active_uv_30d': ['站外活跃行为uv', '站外活跃UV', '活跃UV', '活跃用户'],
    'col_cart_uv_30d': ['加购UV', '加购uv', '购物车UV', '加购用户'],
    'col_deal_uv_30d': ['成交UV', '成交uv', '成交用户', '支付UV', '支付用户'],
    'col_purchase_rate_30d': ['购买率', '转化率', '站外购买率'],
    'col_cart_rate_30d': ['加购率', '加购率(%)'],

    # === 组件 ===
    'col_comp_text_exp': ['正文组件曝光', '正文曝光'],
    'col_comp_text_click': ['正文组件点击', '正文点击'],
    'col_comp_bottom_exp': ['底栏组件曝光', '笔记底栏组件曝光'],
    'col_comp_bottom_click': ['底栏组件点击', '笔记底栏组件点击'],
    'col_comp_interact_exp': ['互动组件曝光'],
    'col_comp_interact_click': ['互动组件参与', '互动组件点击'],
    'col_comp_comment_exp': ['评论区组件曝光'],
    'col_comp_comment_click': ['评论区组件点击'],
}


# ========== 平台专属同义词 ==========
# 每个平台的特殊列名
PLATFORM_SYNONYMS = {
    'xhs': {
        'col_note_type': ['笔记类型', '内容类型', '笔记形式', '笔记分类', '形式', '笔记分类'],
        'col_health': ['健康等级', '健康状态', '账号状态', '健康状态', '异常状态'],
        'col_note_title': ['笔记标题', '标题', '内容标题', '内容'],
        'col_source': ['笔记来源', '来源', '流量来源', '内容来源'],
        'col_exp_discover': ['发现页曝光', '发现页'],
        'col_exp_search': ['搜索页曝光', '搜索页'],
        'col_exp_profile': ['个人页曝光', '个人页', '个人主页曝光'],
        'col_exp_follow': ['关注页曝光', '关注页'],
        'col_exp_nearby': ['附近页曝光', '附近页'],
        'col_exp_other': ['其他曝光', '其他流量'],
        'col_read_discover': ['发现页阅读', '发现页阅读占比'],
        'col_read_search': ['搜索页阅读', '搜索页阅读占比'],
        'col_read_profile': ['个人页阅读', '个人页阅读占比'],
        'col_read_follow': ['关注页阅读', '关注页阅读占比'],
        'col_read_nearby': ['附近页阅读', '附近页阅读占比'],
        'col_read_other': ['其他阅读', '其他阅读占比'],
    },
    'video_number': {
        # 视频号特有列名 - 与 UNIVERSAL_SYNONYMS 合并使用
        'col_content_type': ['达人类型', '内容类型', '账号类型', '达人分类', '内容分类', '类目', '垂类', '赛道'],
        'cooperation_format': ['合作形式', '投放形式', '合作方式', '内容形式', '笔记形式', '视频形式'],
        'col_cost': ['SIPAC价格', 'SIPAC报价', '合作费用', '达人报价', '报价', '金额', '总费用', '成本',
                      '合作金额', '投放金额', '单价', '达人费用', '执行费用', '达人合作费', '合作价'],
    },
    'douyin': {
        'col_exposure': ['播放量', '播放', '曝光量', '曝光'],
        'col_avg_exposure': ['平均播放量', '平均播放', '预估播放'],
        'col_avg_interaction': ['平均互动量', '平均互动', '预估互动'],
    },
    'bilibili': {
        'col_exposure': ['播放量', '播放', '曝光量'],
        'col_views': ['浏览次数', '访问次数'],
        'col_danmaku': ['弹幕数', '弹幕'],
    },
}


def detect_platform(col_names):
    """
    Auto-detect platform from Excel column names.
    Returns: 'video_number', 'xhs', 'douyin', 'bilibili', or 'unknown'
    """
    cleaned = [clean_name(n).lower() for n in col_names]
    full_text = ' '.join(cleaned)

    # 视频号 indicators
    vn_signals = ['视频号', 'sipac', '切角', '私密赞', '评论区提及率', '完播率']
    vn_score = sum(1 for s in vn_signals if s in full_text)

    # 小红书 indicators
    xhs_signals = ['曝光量', '阅读量', '自然曝光', '推广曝光', '加热曝光',
                    '发现页', '搜索页', '蒲公英', '博主', '健康等级', '笔记']
    xhs_score = sum(1 for s in xhs_signals if s in full_text)

    # 抖音 indicators
    dy_signals = ['抖音', 'DOU+', '抖加', '千川', '巨量', '播放量', '抖音号']
    dy_score = sum(1 for s in dy_signals if s in full_text)

    # B站 indicators
    bili_signals = ['B站', 'bilibili', 'b站', '弹幕', 'BV', '哔哩哔哩']
    bili_score = sum(1 for s in bili_signals if s in full_text)

    scores = {
        'video_number': vn_score,
        'xhs': xhs_score,
        'douyin': dy_score,
        'bilibili': bili_score,
    }

    max_platform = max(scores, key=scores.get)
    if scores[max_platform] >= 2:
        return max_platform
    elif xhs_score >= 3:
        return 'xhs'
    elif vn_score >= 2:
        return 'video_number'
    return 'unknown'


def get_platform_synonyms(platform):
    """Get platform-specific synonym overrides"""
    return PLATFORM_SYNONYMS.get(platform, {})


def detect_all_columns(col_names, platform='unknown'):
    """
    Detect all columns using universal + platform-specific synonyms.

    Returns dict mapping metric_key -> column_index
    """
    # Start with universal synonyms
    all_synonyms = dict(UNIVERSAL_SYNONYMS)

    # Add platform-specific synonyms (these override universal ones)
    if platform != 'unknown':
        plat_syns = get_platform_synonyms(platform)
        for key, syns in plat_syns.items():
            if key in all_synonyms:
                # Prepend platform-specific synonyms for higher priority
                all_synonyms[key] = list(syns) + [s for s in all_synonyms[key] if s not in syns]
            else:
                all_synonyms[key] = list(syns)

    return match_column(col_names, all_synonyms)


def detect_header_row(data_path):
    """Scan Excel to find the header row (row with most non-empty string-like column names)"""
    import openpyxl
    wb = openpyxl.load_workbook(data_path, read_only=True, data_only=True)
    ws = wb.active
    best_row = 2  # default
    best_non_empty = 0
    for row_idx in range(1, min(ws.max_row + 1, 6)):
        non_empty = 0
        str_count = 0
        numeric_count = 0
        for cell in ws[row_idx]:
            if cell.value is not None:
                non_empty += 1
                val_str = str(cell.value).strip()
                has_chinese = any('一' <= c <= '鿿' for c in val_str)
                if has_chinese:
                    str_count += 1
                try:
                    float(val_str)
                    numeric_count += 1
                except ValueError:
                    pass
        # A header row has many non-empty cells that are mostly strings
        # Data rows have many numeric values
        if non_empty > best_non_empty and str_count >= non_empty * 0.5:
            best_non_empty = non_empty
            best_row = row_idx
    wb.close()
    return best_row
