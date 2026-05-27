# -*- coding: utf-8 -*-
"""
crawl_xiaohongshu.py — 小红书笔记爬虫（独立模块）

关键发现：
- web_session 是跟随每个笔记链接动态变化的，不能用固定 cookie 爬所有笔记
- headless 模式会被 XHS 风控拦截（"IP存在风险"）
- 必须使用 visible Chrome + Chrome profile 才能正常加载

用法（独立）：
    python crawl_xiaohongshu.py urls.txt --output ./output [--headed] [--max-comments 200]

用法（被 crawl_notes.py 调用）：
    from crawl_xiaohongshu import crawl_xhs_notes
    result = await crawl_xhs_notes(urls, output_dir, max_comments=200, headless=False)
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
)

logger = logging.getLogger(__name__)


# ============================================================
# 笔记信息提取
# ============================================================

async def extract_xhs_note_info(page, url, note_dir):
    """从小红书笔记页面提取结构化信息"""
    try:
        note_id = extract_note_id_from_url(url, 'xiaohongshu')

        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await human_delay(2, 4)
        await simulate_scroll(page)
        await human_delay(1, 2)

        current_url = page.url
        if 'login' in current_url.lower() or '404' in current_url:
            logger.warning(f'  页面不可访问: {current_url}')
            return None
        if 'error' in current_url.lower():
            logger.warning(f'  页面错误: {current_url}')
            return None

        # 标题
        title = ''
        try:
            title_el = await page.query_selector('h1, .title, [class*="title"]')
            if title_el:
                title = (await title_el.inner_text()).strip()
        except Exception:
            pass

        # 正文内容
        content_text = ''
        try:
            selectors = ['[class*="desc"]', '[class*="content"]', '[class*="note-detail"]',
                         'article', '[class*="note-content"]']
            for sel in selectors:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if len(text) > 20:
                        content_text = text
                        break
        except Exception:
            pass

        # 如果 DOM 提取不到，尝试从页面文本中提取
        if not content_text:
            try:
                body_text = await page.inner_text('body')
                # 尝试匹配正文（标题之后、#标签 之前）
                if title:
                    idx = body_text.find(title)
                    if idx >= 0:
                        rest = body_text[idx + len(title):]
                        # 找到第一个 # 标签位置
                        hash_idx = rest.find('#')
                        if hash_idx > 0:
                            content_text = rest[:hash_idx].strip()
            except Exception:
                pass

        # 图片 URL
        image_urls = []
        try:
            img_els = await page.query_selector_all(
                'img[class*="image"], img[class*="photo"], img[src*="sns-video"], img[src*="xhscdn"]'
            )
            for img in img_els:
                src = await img.get_attribute('src') or ''
                if src and ('sns-web' in src or 'xhscdn' in src) and src not in image_urls:
                    image_urls.append(src)
        except Exception:
            pass

        # 视频信息
        video_info = {'has_video': False, 'video_url': '', 'duration_sec': 0}
        try:
            video_el = await page.query_selector('video')
            if video_el:
                video_src = await video_el.get_attribute('src') or ''
                if not video_src:
                    src_el = await video_el.query_selector('source')
                    if src_el:
                        video_src = await src_el.get_attribute('src') or ''
                if video_src:
                    video_info['has_video'] = True
                    video_info['video_url'] = video_src
                    try:
                        duration = await video_el.evaluate('el => el.duration')
                        video_info['duration_sec'] = int(duration) if duration else 0
                    except Exception:
                        pass
        except Exception:
            pass

        # 互动数据（从页面文本正则提取）
        stats = {'likes': 0, 'favorites': 0, 'comments_count': 0, 'shares': 0}
        try:
            text = await page.inner_text('body')
            like_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*[点赞]', text)
            fav_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*收藏', text)
            comment_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*评论', text)
            if like_match:
                stats['likes'] = parse_num(like_match.group(1))
            if fav_match:
                stats['favorites'] = parse_num(fav_match.group(1))
            if comment_match:
                stats['comments_count'] = parse_num(comment_match.group(1))
        except Exception:
            pass

        # 作者
        author = {'name': '', 'fans_count': 0}
        try:
            author_el = await page.query_selector('[class*="author"], [class*="user-name"]')
            if author_el:
                author['name'] = (await author_el.inner_text()).strip()
        except Exception:
            pass

        # 下载图片
        image_paths = []
        for i, img_url in enumerate(image_urls[:10]):
            img_path = os.path.join(note_dir, f'img_{i}.jpg')
            try:
                resp = await page.context.request.get(img_url)
                if resp.status == 200:
                    img_bytes = await resp.body()
                    with open(img_path, 'wb') as f:
                        f.write(img_bytes)
                    image_paths.append(img_path)
                await human_delay(0.3, 0.8)
            except Exception:
                pass

        # 下载视频（如果检测到）
        video_local_path = ''
        if video_info['has_video'] and video_info['video_url']:
            video_path = os.path.join(note_dir, 'video.mp4')
            ok = await download_resource(page.context, video_info['video_url'], video_path)
            if ok:
                video_local_path = video_path
                logger.info(f'  视频下载成功: {video_path}')

        return {
            'note_id': note_id,
            'note_url': url,
            'title': title,
            'content_text': content_text,
            'note_type': 'video' if video_info['has_video'] else 'text',
            'images': image_paths,
            'video': {
                'has_video': video_info['has_video'],
                'video_url': video_info['video_url'],
                'local_path': video_local_path,
                'duration_sec': video_info['duration_sec'],
            },
            'author': author,
            'stats': stats,
            'comments': [],
        }
    except Exception as e:
        logger.error(f'  XHS 页面提取失败: {e}')
        return None


# ============================================================
# 评论加载
# ============================================================

async def load_xhs_comments(page, max_comments=200):
    """滚动加载小红书评论区"""
    comments = []
    seen_texts = set()

    try:
        await human_delay(1, 2)
        await simulate_scroll(page)
        await human_delay(1, 2)

        # 尝试展开评论
        expand_selectors = ['text=查看更多评论', 'text=查看全部', '[class*="expand"]',
                            '[class*="load-more"]', 'text=展开']
        for sel in expand_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await human_delay(1, 2)
                    break
            except Exception:
                pass

        for scroll_round in range(max_comments // 10 + 5):
            await page.mouse.wheel(0, 400)
            await human_delay(1.5, 3.0)

            comment_selectors = ['[class*="comment"]', '[class*="comment-item"]',
                                 '[data-type="comment"]', '.comment-content']
            comment_els = []
            for sel in comment_selectors:
                els = await page.query_selector_all(sel)
                if els:
                    comment_els = els
                    break

            if not comment_els:
                break

            new_count = 0
            for el in comment_els:
                try:
                    text = (await el.inner_text()).strip()
                    short_text = text[:50]
                    if not text or short_text in seen_texts or len(text) < 2:
                        continue
                    seen_texts.add(short_text)

                    likes = 0
                    author = ''
                    try:
                        like_el = await el.query_selector('[class*="like"], [class*="count"]')
                        if like_el:
                            like_text = await like_el.inner_text()
                            likes = parse_num(like_text)
                        author_el = await el.query_selector('[class*="user"], [class*="name"], [class*="author"]')
                        if author_el:
                            author = (await author_el.inner_text()).strip()
                    except Exception:
                        pass

                    comments.append({
                        'text': text, 'likes': likes,
                        'timestamp': '', 'author': author, 'replies': [],
                    })
                    new_count += 1
                    if len(comments) >= max_comments:
                        break
                except Exception:
                    continue

            if new_count == 0 or len(comments) >= max_comments:
                break
            if scroll_round % 3 == 0:
                await human_delay(2, 4)
    except Exception as e:
        logger.warning(f'  XHS 评论加载异常: {e}')

    return comments[:max_comments]


# ============================================================
# 单个笔记爬取
# ============================================================

async def crawl_xhs_note(page, url, note_dir, max_comments=200):
    """爬取单个小红书笔记"""
    logger.info(f'正在爬取(小红书): {url}')

    # 设置拦截器
    video_urls = await intercept_video_url(page, 'xiaohongshu')

    # 提取笔记信息
    note_data = await extract_xhs_note_info(page, url, note_dir)
    if note_data is None:
        return None

    # 检查拦截到的视频 URL
    if not note_data['video']['has_video'] and video_urls:
        for vu in video_urls:
            if 'mp4' in vu or 'video' in vu:
                note_data['video']['has_video'] = True
                note_data['video']['video_url'] = vu
                note_data['note_type'] = 'video'
                break

    # 加载评论
    if note_data['stats'].get('comments_count', 0) > 0:
        logger.info(f'  正在加载评论 (预计 {note_data["stats"]["comments_count"]} 条)...')
        note_data['comments'] = await load_xhs_comments(page, max_comments)
        logger.info(f'  实际获取 {len(note_data["comments"])} 条评论')

    # 视频封面
    if note_data['video']['local_path']:
        cover_path = os.path.join(note_dir, 'cover.jpg')
        await save_first_frame_as_cover(note_data['video']['local_path'], cover_path)
        if os.path.exists(cover_path):
            note_data['video']['cover_path'] = cover_path

    return note_data


# ============================================================
# 批量爬取
# ============================================================

async def crawl_xhs_notes(urls, output_dir, max_comments=200, headless=False,
                           cookie_str='', user_data_dir=None):
    """
    批量爬取小红书笔记

    Args:
        urls: URL 列表
        output_dir: 输出目录
        max_comments: 每篇最大评论数
        headless: 是否无头模式（XHS 建议 False）
        cookie_str: Cookie 字符串（可选，XHS 需要登录态）
        user_data_dir: Chrome 用户数据目录（用于自动加载登录态）
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
            'platforms': {'xiaohongshu': len(urls)},
        },
        'notes': [],
    }

    async with async_playwright() as p:
        if user_data_dir:
            # 使用 Chrome 用户数据目录，自动加载登录态
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
            )
        else:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                locale='zh-CN',
            )

        page = await context.new_page()

        # 如果提供了 cookie 字符串，注入
        if cookie_str:
            try:
                from crawler_utils import parse_cookie_string
                cookies = parse_cookie_string(cookie_str, domain='.xiaohongshu.com')
                await context.add_cookies(cookies)
            except Exception as e:
                logger.warning(f'  Cookie 注入失败: {e}')

        for i, url in enumerate(urls):
            note_dir = make_note_dir(output_dir, 'xiaohongshu', i + 1)

            success = False
            for retry in range(3):
                try:
                    note_data = await crawl_xhs_note(page, url, note_dir, max_comments)
                    if note_data:
                        note_data['platform'] = 'xiaohongshu'
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

                if (i + 1) % 10 == 0:
                    logger.info('  大休息 30 秒...')
                    await asyncio.sleep(30)

        await context.close()

    output_path = save_crawl_result(result, output_dir)
    logger.info(f'小红书爬取完成！成功 {result["crawl_metadata"]["successful"]}/{result["crawl_metadata"]["total_urls"]}')
    logger.info(f'结果已保存: {output_path}')
    return result


# ============================================================
# CLI 入口
# ============================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='小红书笔记爬虫')
    parser.add_argument('url_file', help='URL 列表文件')
    parser.add_argument('--output', default='./crawl_output', help='输出目录')
    parser.add_argument('--max-comments', type=int, default=200, help='每篇最大评论数')
    parser.add_argument('--cookie', default='', help='Cookie 字符串')
    parser.add_argument('--user-data-dir', default=None, help='Chrome 用户数据目录')
    parser.add_argument('--headed', action='store_true', help='显示浏览器窗口')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    with open(args.url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    if not urls:
        logger.error('URL 文件为空')
        sys.exit(1)

    asyncio.run(crawl_xhs_notes(
        urls=urls,
        output_dir=args.output,
        max_comments=args.max_comments,
        headless=not args.headed,
        cookie_str=args.cookie,
        user_data_dir=args.user_data_dir,
    ))
