# -*- coding: utf-8 -*-
"""
crawl_douyin.py — 抖音笔记爬虫（API 方案，基于 MediaCrawler）

v2.4: 重构为 API 方案。不再用 DOM 滚动抓取，改为调用抖音内部 API：
- 视频详情: GET /aweme/v1/web/aweme/detail/
- 评论列表: GET /aweme/v1/web/comment/list/
- 子评论: GET /aweme/v1/web/comment/list/reply/

用法（独立）：
    python crawl_douyin.py urls.txt --output ./output [--headed] [--cookie "xxx"]
"""
import asyncio
import json
import os
import re
import random
import logging
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from crawler_utils import (
    extract_note_id_from_url, human_delay, simulate_scroll,
    parse_num, intercept_video_url, download_resource,
    save_first_frame_as_cover, make_note_dir, save_crawl_result,
    parse_cookie_string,
)

logger = logging.getLogger(__name__)


# ============================================================
# API 调用（通过浏览器 fetch）
# ============================================================

async def call_douyin_api(page, uri, params=None):
    """通过浏览器内 fetch 调用抖音内部 API"""
    if params:
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        url = f'{uri}?{query}'
    else:
        url = uri
    return await page.evaluate(f'''() => {{
        return new Promise((resolve, reject) => {{
            fetch('{url}', {{ method: 'GET', credentials: 'include' }})
                .then(r => r.json())
                .then(d => resolve(d))
                .catch(e => reject(e.toString()));
        }});
    }}''')


async def get_video_detail(page, aweme_id):
    """获取视频详情"""
    result = await call_douyin_api(page, '/aweme/v1/web/aweme/detail/', {'aweme_id': aweme_id})
    return result.get('aweme_detail', {})


async def get_all_comments(page, aweme_id, max_comments=200):
    """分页获取所有评论"""
    comments = []
    cursor = 0
    has_more = 1
    max_pages = max_comments // 20 + 5

    for _ in range(max_pages):
        if len(comments) >= max_comments:
            break
        res = await call_douyin_api(page, '/aweme/v1/web/comment/list/', {
            'aweme_id': aweme_id,
            'cursor': cursor,
            'count': 20,
            'item_type': 0,
        })
        batch = res.get('comments', [])
        cursor = res.get('cursor', 0)
        has_more = res.get('has_more', 0)
        comments.extend(batch)
        await asyncio.sleep(1.5)
        if not has_more or not batch:
            break

    return comments[:max_comments]


# ============================================================
# 笔记信息提取
# ============================================================

async def extract_douyin_note_info(page, url, note_dir):
    """从抖音 API 提取结构化信息"""
    try:
        note_id = extract_note_id_from_url(url, 'douyin')
        logger.info(f'正在爬取(抖音): {url}')

        # 通过 API 获取视频详情
        logger.info(f'  获取视频详情...')
        detail = await get_video_detail(page, note_id)
        if not detail:
            logger.warning(f'  视频详情为空: {url}')
            return None

        # 解析详情
        author_info = detail.get('author', {})
        stats = detail.get('statistics', {})
        video_info = detail.get('video', {})

        note_data = {
            'note_id': note_id,
            'note_url': url,
            'title': detail.get('desc', ''),
            'content_text': detail.get('desc', ''),
            'note_type': 'video',
            'images': [],
            'video': {
                'has_video': True,
                'video_url': '',
                'duration_sec': round(video_info.get('duration', 0) / 1000),
                'local_path': '',
            },
            'author': {
                'name': author_info.get('nickname', ''),
                'fans_count': author_info.get('follower_count', 0),
            },
            'stats': {
                'plays': stats.get('play_count', 0),
                'likes': stats.get('digg_count', 0),
                'comments_count': stats.get('comment_count', 0),
                'favorites': stats.get('collect_count', 0),
                'shares': stats.get('share_count', 0),
            },
            'comments': [],
        }

        logger.info(f'  标题: {note_data["title"][:50]}')
        logger.info(f'  作者: {note_data["author"]["name"]}')
        logger.info(f'  数据: 播放={note_data["stats"]["plays"]}, 点赞={note_data["stats"]["likes"]}, '
                    f'评论={note_data["stats"]["comments_count"]}, 收藏={note_data["stats"]["favorites"]}')

        return note_data
    except Exception as e:
        logger.error(f'  抖音 页面提取失败: {e}')
        return None


# ============================================================
# 单个笔记爬取
# ============================================================

async def crawl_douyin_note(page, url, note_dir, cookie_str='', max_comments=200):
    """爬取单个抖音笔记"""
    logger.info(f'正在爬取(抖音): {url}')

    # 注入 Cookie 并初始化
    if cookie_str:
        try:
            cookies = parse_cookie_string(cookie_str, domain='.douyin.com')
            await page.context.add_cookies(cookies)
            logger.info(f'  Cookie 已注入，访问主页初始化...')
            await page.goto('https://www.douyin.com', wait_until='domcontentloaded', timeout=15000)
            await human_delay(2, 4)
            title = await page.title()
            logger.info(f'  抖音首页: {title}')
        except Exception as e:
            logger.warning(f'  Cookie 注入失败: {e}')

    # 视频拦截（用于下载）
    video_urls = await intercept_video_url(page, 'douyin')

    # API 提取信息
    note_data = await extract_douyin_note_info(page, url, note_dir)
    if note_data is None:
        return None

    # 下载视频
    if note_data['video'].get('video_url'):
        video_path = os.path.join(note_dir, 'video.mp4')
        ok = await download_resource(page.context, note_data['video']['video_url'],
                                     video_path, timeout=60000)
        if ok:
            note_data['video']['local_path'] = video_path
            logger.info(f'  抖音视频下载成功: {video_path}')
        else:
            for vurl in video_urls:
                if '.mp4' in vurl or 'douyinvod' in vurl:
                    video_path = os.path.join(note_dir, 'video.mp4')
                    ok = await download_resource(page.context, vurl, video_path, timeout=60000)
                    if ok:
                        note_data['video']['local_path'] = video_path
                        note_data['video']['video_url'] = vurl
                        logger.info(f'  抖音视频下载成功(拦截): {video_path}')
                        break
    else:
        for vurl in video_urls:
            if '.mp4' in vurl or 'douyinvod' in vurl:
                video_path = os.path.join(note_dir, 'video.mp4')
                ok = await download_resource(page.context, vurl, video_path, timeout=60000)
                if ok:
                    note_data['video']['local_path'] = video_path
                    note_data['video']['video_url'] = vurl
                    logger.info(f'  抖音视频下载成功(拦截): {video_path}')
                    break

    if not note_data['video']['local_path']:
        logger.warning(f'  抖音视频下载失败，跳过视频分析')
        note_data['video']['has_video'] = False

    # API 获取评论
    if note_data['stats'].get('comments_count', 0) > 0:
        logger.info(f'  正在加载抖音评论...')
        raw_comments = await get_all_comments(page, note_data['note_id'], max_comments)
        note_data['comments'] = []
        for c in raw_comments:
            user = c.get('user', {})
            note_data['comments'].append({
                'text': c.get('text', ''),
                'likes': c.get('digg_count', 0),
                'timestamp': c.get('create_time', 0),
                'author': user.get('nickname', ''),
                'replies': [],
                'ip': c.get('ip_label', ''),
            })
        logger.info(f'  实际获取 {len(note_data["comments"])} 条评论')

    # 封面
    if note_data['video']['local_path']:
        cover_path = os.path.join(note_dir, 'cover.jpg')
        await save_first_frame_as_cover(note_data['video']['local_path'], cover_path)
        if os.path.exists(cover_path):
            note_data['video']['cover_path'] = cover_path

    return note_data


# ============================================================
# 批量爬取
# ============================================================

async def crawl_douyin_notes(urls, output_dir, max_comments=200, headless=True,
                              cookie_str=''):
    """
    批量爬取抖音笔记

    Args:
        urls: URL 列表
        output_dir: 输出目录
        max_comments: 每篇最大评论数
        headless: 是否无头模式
        cookie_str: Cookie 字符串（可选，部分页面需要登录）
    """
    from playwright.async_api import async_playwright

    result = {
        'crawl_metadata': {
            'crawl_time': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'total_urls': len(urls),
            'successful': 0,
            'failed': 0,
            'cookie_valid': True,
            'max_comments': max_comments,
            'platforms': {'douyin': len(urls)},
        },
        'notes': [],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
            locale='zh-CN',
        )
        page = await context.new_page()

        for i, url in enumerate(urls):
            note_dir = make_note_dir(output_dir, 'douyin', i + 1)

            success = False
            for retry in range(3):
                try:
                    note_data = await crawl_douyin_note(
                        page, url, note_dir, cookie_str, max_comments
                    )
                    if note_data:
                        note_data['platform'] = 'douyin'
                        note_data['crawl_index'] = i + 1
                        result['notes'].append(note_data)
                        result['crawl_metadata']['successful'] += 1
                        success = True
                    break
                except Exception as e:
                    logger.warning(f'  第 {retry + 1} 次重试失败: {e}')
                    await asyncio.sleep(random.uniform(3, 6) * (retry + 1))

            if not success:
                result['crawl_metadata']['failed'] += 1
                logger.error(f'爬取失败: {url}')

            # 频率控制
            if i < len(urls) - 1:
                delay = random.uniform(3, 8)
                logger.info(f'  等待 {delay:.1f} 秒...')
                await asyncio.sleep(delay)

        await browser.close()

    output_path = save_crawl_result(result, output_dir)
    logger.info(f'抖音爬取完成！成功 {result["crawl_metadata"]["successful"]}/{result["crawl_metadata"]["total_urls"]}')
    logger.info(f'结果已保存: {output_path}')
    return result


# ============================================================
# CLI 入口
# ============================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='抖音笔记爬虫 (API 方案)')
    parser.add_argument('url_file', help='URL 列表文件')
    parser.add_argument('--output', default='./crawl_output', help='输出目录')
    parser.add_argument('--max-comments', type=int, default=200, help='每篇最大评论数')
    parser.add_argument('--cookie', default='', help='Cookie 字符串')
    parser.add_argument('--headed', action='store_true', help='显示浏览器窗口')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    with open(args.url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    if not urls:
        logger.error('URL 文件为空')
        sys.exit(1)

    asyncio.run(crawl_douyin_notes(
        urls=urls,
        output_dir=args.output,
        max_comments=args.max_comments,
        headless=not args.headed,
        cookie_str=args.cookie,
    ))
