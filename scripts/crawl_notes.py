# -*- coding: utf-8 -*-
"""
crawl_notes.py — 多平台笔记爬虫调度器

URL 自动识别平台并分发到对应爬虫模块：
  - crawl_xiaohongshu.py  → 小红书（需 visible Chrome + 登录态）
  - crawl_bilibili.py     → B站（headless 可用，API 获取评论）
  - crawl_douyin.py       → 抖音（预留，待测试）

用法：
  # 混合平台 URL 文件
  python crawl_notes.py urls.txt --output ./output [--cookie "xxx"] [--headed]

  # 单平台独立调用（推荐用于复杂场景）
  python crawl_xiaohongshu.py xhs_urls.txt --output ./xhs_output --headed
  python crawl_bilibili.py bili_urls.txt --output ./bili_output --cookie "SESSDATA=xxx"
"""
import asyncio
import json
import os
import time
import random
import logging
import sys

sys.path.insert(0, os.path.dirname(__file__))
from crawler_utils import detect_platform, save_crawl_result

logger = logging.getLogger(__name__)


# ============================================================
# 平台爬虫注册表
# ============================================================

CRAWLERS = {}


def _load_crawler(platform):
    """延迟加载爬虫模块"""
    if platform in CRAWLERS:
        return CRAWLERS[platform]

    module_map = {
        'xiaohongshu': 'crawl_xiaohongshu',
        'bilibili': 'crawl_bilibili',
        'douyin': 'crawl_douyin',
    }

    if platform not in module_map:
        return None

    try:
        mod = __import__(module_map[platform], fromlist=['crawl_notes'])
        CRAWLERS[platform] = mod
        return mod
    except ImportError as e:
        logger.error(f'  无法加载 {platform} 爬虫模块: {e}')
        return None


# ============================================================
# 混合平台爬取
# ============================================================

def crawl_notes(url_file, cookie, output_dir, max_comments=200, max_notes=0,
                headless=True, xhs_user_data_dir=None):
    """
    主入口函数。读取 URL 文件，按平台分组，分发到对应爬虫模块。

    Args:
        url_file: URL 列表文件路径
        cookie: Cookie 字符串
        output_dir: 输出目录
        max_comments: 每篇最大评论数
        max_notes: 最大爬取数（0=不限制）
        headless: 是否无头模式（XHS 建议 False）
        xhs_user_data_dir: Chrome 用户数据目录（XHS 自动加载登录态用）
    """
    # 读取 URL 文件
    with open(url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    if not urls:
        logger.error('URL 文件为空')
        return None

    if max_notes > 0:
        urls = urls[:max_notes]

    # 按平台分组
    platform_urls = {}
    for url in urls:
        platform = detect_platform(url)
        if platform == 'unknown':
            logger.warning(f'  未知平台，跳过: {url}')
            continue
        platform_urls.setdefault(platform, []).append(url)

    logger.info(f'共 {len(urls)} 个链接待爬取: {dict((k, len(v)) for k, v in platform_urls.items())}')

    # 合并结果
    merged_result = {
        'crawl_metadata': {
            'crawl_time': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'total_urls': len(urls),
            'successful': 0,
            'failed': 0,
            'cookie_valid': True,
            'max_comments': max_comments,
            'platforms': dict((k, len(v)) for k, v in platform_urls.items()),
        },
        'notes': [],
    }

    # 逐个平台执行
    crawl_index = 0
    for platform, urls in platform_urls.items():
        mod = _load_crawler(platform)
        if mod is None:
            logger.error(f'  跳过 {platform}（模块不可用）')
            merged_result['crawl_metadata']['failed'] += len(urls)
            continue

        # 调用对应爬虫模块
        crawl_fn = getattr(mod, 'crawl_{0}_notes'.format(platform), None)
        if crawl_fn is None:
            logger.error(f'  跳过 {platform}（函数不可用）')
            merged_result['crawl_metadata']['failed'] += len(urls)
            continue

        logger.info(f'\n===== 开始爬取 {platform} ({len(urls)} 个) =====')

        # 各平台参数不同
        kwargs = {
            'urls': urls,
            'output_dir': output_dir,
            'max_comments': max_comments,
            'cookie_str': cookie or '',
        }

        if platform == 'xiaohongshu':
            # XHS 默认 visible mode
            kwargs['headless'] = headless
            kwargs['user_data_dir'] = xhs_user_data_dir
        elif platform == 'bilibili':
            # B站 headless 可用
            kwargs['headless'] = headless
        elif platform == 'douyin':
            kwargs['headless'] = headless

        try:
            result = asyncio.run(crawl_fn(**kwargs))
            if result:
                # 更新全局索引
                for note in result.get('notes', []):
                    crawl_index += 1
                    note['crawl_index'] = crawl_index
                merged_result['notes'].extend(result.get('notes', []))
                merged_result['crawl_metadata']['successful'] += result.get('crawl_metadata', {}).get('successful', 0)
                merged_result['crawl_metadata']['failed'] += result.get('crawl_metadata', {}).get('failed', 0)
        except Exception as e:
            logger.error(f'  {platform} 爬取异常: {e}')
            merged_result['crawl_metadata']['failed'] += len(urls)

    # 保存合并结果
    output_path = save_crawl_result(merged_result, output_dir)
    logger.info(f'\n全部爬取完成！成功 {merged_result["crawl_metadata"]["successful"]}/{merged_result["crawl_metadata"]["total_urls"]}')
    logger.info(f'结果已保存: {output_path}')

    return merged_result


# ============================================================
# CLI 入口
# ============================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='多平台笔记爬虫（小红书/B站/抖音）— 自动识别平台并分发'
    )
    parser.add_argument('url_file', help='URL 列表文件（每行一个 URL）')
    parser.add_argument('--cookie', required=False, default=None,
                        help='Cookie 字符串（小红书需要登录态，B站/抖音可选）')
    parser.add_argument('--output', default='./crawl_output', help='输出目录')
    parser.add_argument('--max-comments', type=int, default=200,
                        help='每篇笔记最大评论数（默认 200）')
    parser.add_argument('--max-notes', type=int, default=0,
                        help='最大爬取笔记数（0=不限制）')
    parser.add_argument('--headed', action='store_true',
                        help='显示浏览器窗口（XHS 默认 visible，B站/抖音 默认 headless）')
    parser.add_argument('--xhs-user-data-dir', default=None,
                        help='Chrome 用户数据目录（用于 XHS 自动加载登录态）')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    crawl_notes(
        url_file=args.url_file,
        cookie=args.cookie or '',
        output_dir=args.output,
        max_comments=args.max_comments,
        max_notes=args.max_notes,
        headless=not args.headed,
        xhs_user_data_dir=args.xhs_user_data_dir,
    )
