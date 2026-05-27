# -*- coding: utf-8 -*-
"""
crawl_douyin.py — 抖音笔记爬虫（独立模块）

TODO: 抖音尚未实际测试，以下为基础框架。
- 可能需要登录态（Cookie）才能查看完整内容
- 视频下载需处理时效性 URL
- 评论加载可能需要 API 或 DOM 滚动

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

sys.path.insert(0, os.path.dirname(__file__))
from crawler_utils import (
    extract_note_id_from_url, human_delay, simulate_scroll,
    parse_num, intercept_video_url, download_resource,
    save_first_frame_as_cover, make_note_dir, save_crawl_result,
    parse_cookie_string,
)

logger = logging.getLogger(__name__)


# ============================================================
# 笔记信息提取
# ============================================================

async def extract_douyin_note_info(page, url, note_dir):
    """从抖音网页版提取结构化信息"""
    try:
        note_id = extract_note_id_from_url(url, 'douyin')

        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await human_delay(3, 6)
        await simulate_scroll(page, 2)
        await human_delay(1, 2)

        # 检测登录拦截
        current_url = page.url
        if 'login' in current_url.lower():
            logger.warning(f'  页面需要登录: {url}')
            return None

        # 标题 — 从 meta 标签
        title = ''
        try:
            title_el = await page.query_selector('meta[property="og:title"]')
            if title_el:
                title = (await title_el.get_attribute('content') or '').strip()
            if not title:
                title_el = await page.query_selector('h1, [class*="title"], .title, [class*="desc"]')
                if title_el:
                    title = (await title_el.inner_text()).strip()
            if not title:
                title = await page.title()
        except Exception:
            title = await page.title()

        # 描述
        content_text = ''
        try:
            desc_el = await page.query_selector('[class*="desc"], .desc, [class*="content"], .content')
            if desc_el:
                content_text = (await desc_el.inner_text()).strip()
        except Exception:
            pass

        # 互动数据
        stats = {'likes': 0, 'favorites': 0, 'comments_count': 0, 'shares': 0}
        try:
            text = await page.inner_text('body')
            like_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*点赞', text)
            fav_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*收藏', text)
            comment_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*评论', text)
            share_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*分享', text)
            if like_match:
                stats['likes'] = parse_num(like_match.group(1))
            if fav_match:
                stats['favorites'] = parse_num(fav_match.group(1))
            if comment_match:
                stats['comments_count'] = parse_num(comment_match.group(1))
            if share_match:
                stats['shares'] = parse_num(share_match.group(1))
        except Exception:
            pass

        # 作者
        author = {'name': '', 'fans_count': 0}
        try:
            author_el = await page.query_selector('[class*="author"], .author, [class*="user-name"], .user-name')
            if author_el:
                author['name'] = (await author_el.inner_text()).strip()
        except Exception:
            pass

        # 封面图
        image_paths = []
        try:
            cover_el = await page.query_selector('meta[property="og:image"]')
            if cover_el:
                cover_url = (await cover_el.get_attribute('content') or '').strip()
                if cover_url:
                    cover_path = os.path.join(note_dir, 'cover.jpg')
                    resp = await page.context.request.get(cover_url)
                    if resp.status == 200:
                        with open(cover_path, 'wb') as f:
                            f.write(await resp.body())
                        image_paths.append(cover_path)
        except Exception:
            pass

        # 视频
        video_info = {'has_video': True, 'video_url': '', 'duration_sec': 0, 'local_path': ''}
        try:
            video_el = await page.query_selector('video')
            if video_el:
                video_src = await video_el.get_attribute('src') or ''
                if not video_src:
                    src_el = await video_el.query_selector('source')
                    if src_el:
                        video_src = await src_el.get_attribute('src') or ''
                if video_src:
                    video_info['video_url'] = video_src
                    try:
                        duration = await video_el.evaluate('el => el.duration')
                        video_info['duration_sec'] = int(duration) if duration else 0
                    except Exception:
                        pass
        except Exception:
            pass

        return {
            'note_id': note_id,
            'note_url': url,
            'title': title,
            'content_text': content_text,
            'note_type': 'video',
            'images': image_paths,
            'video': video_info,
            'author': author,
            'stats': stats,
            'comments': [],
        }
    except Exception as e:
        logger.error(f'  抖音 页面提取失败: {e}')
        return None


# ============================================================
# 评论加载
# ============================================================

async def load_douyin_comments(page, max_comments=200):
    """加载抖音评论（滚动触发）"""
    comments = []
    seen_texts = set()

    try:
        await human_delay(2, 4)
        await simulate_scroll(page, 5)
        await human_delay(2, 3)

        # 尝试点击"查看更多评论"
        expand_selectors = ['text=查看更多', 'text=展开', '[class*="expand"]', '[class*="load-more"]']
        for sel in expand_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await human_delay(1, 2)
            except Exception:
                pass

        # 多次滚动加载
        for _ in range(max_comments // 20 + 3):
            await page.mouse.wheel(0, 400)
            await human_delay(1.5, 3.0)

            comment_els = await page.query_selector_all(
                '[class*="comment"], .comment, [class*="reply"], [data-e2e="comment-item"]'
            )

            new_count = 0
            for el in comment_els:
                try:
                    text = (await el.inner_text()).strip()
                    short_text = text[:50]
                    if not text or short_text in seen_texts or len(text) < 2:
                        continue
                    seen_texts.add(short_text)

                    comments.append({
                        'text': text, 'likes': 0,
                        'timestamp': '', 'author': '', 'replies': [],
                    })
                    new_count += 1
                    if len(comments) >= max_comments:
                        break
                except Exception:
                    continue

            if new_count == 0 or len(comments) >= max_comments:
                break

    except Exception as e:
        logger.warning(f'  抖音 评论加载异常: {e}')

    return comments[:max_comments]


# ============================================================
# 单个笔记爬取
# ============================================================

async def crawl_douyin_note(page, url, note_dir, cookie_str='', max_comments=200):
    """爬取单个抖音笔记"""
    logger.info(f'正在爬取(抖音): {url}')

    if cookie_str:
        try:
            cookies = parse_cookie_string(cookie_str, domain='.douyin.com')
            await page.context.add_cookies(cookies)
        except Exception as e:
            logger.warning(f'  Cookie 注入失败: {e}')

    video_urls = await intercept_video_url(page, 'douyin')
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
            # 尝试拦截的 URL
            for vurl in video_urls:
                if '.mp4' in vurl or 'douyinvod' in vurl:
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

    # 加载评论
    if note_data['stats'].get('comments_count', 0) > 0:
        logger.info(f'  正在加载抖音评论...')
        note_data['comments'] = await load_douyin_comments(page, max_comments)
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
            'crawl_time': __import__('time').strftime('%Y-%m-%dT%H:%M:%S'),
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
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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

    parser = argparse.ArgumentParser(description='抖音笔记爬虫')
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
