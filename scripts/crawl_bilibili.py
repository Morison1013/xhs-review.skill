# -*- coding: utf-8 -*-
"""
crawl_bilibili.py — B站笔记爬虫（独立模块）

关键发现：
- headless 模式可用，不被风控拦截
- 评论通过 API 获取比 DOM 解析更可靠：
  1. 先用 bvid 获取 aid: https://api.bilibili.com/x/web-interface/view?bvid={bvid}
  2. 再用 aid 获取评论: https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&sort=2&pn={n}&ps=20
- 不登录只能获取前几条热评，登录后可获取完整评论
- 视频为 DASH 分片格式，下载后需合并

用法（独立）：
    python crawl_bilibili.py urls.txt --output ./output [--headed] [--max-comments 200] [--cookie "SESSDATA=xxx; bili_jct=yyy"]
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
# 辅助函数
# ============================================================

async def get_aid_from_bvid(page, bvid):
    """通过 B站 API 将 BV 号转换为 aid"""
    try:
        api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
        resp = await page.context.request.get(api_url)
        if resp.status == 200:
            data = await resp.json()
            if data.get('code') == 0:
                return data['data'].get('aid', '')
    except Exception as e:
        logger.debug(f'  获取 aid 失败: {e}')
    return ''


# ============================================================
# 笔记信息提取
# ============================================================

async def extract_bilibili_note_info(page, url, note_dir):
    """从B站视频页面提取结构化信息"""
    try:
        note_id = extract_note_id_from_url(url, 'bilibili')

        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await human_delay(3, 5)
        await simulate_scroll(page, 3)
        await human_delay(1, 2)

        # 标题
        title = ''
        try:
            title_el = await page.query_selector('h1.video-title, [class*="video-title"], .tit, [data-title]')
            if title_el:
                title = (await title_el.inner_text()).strip()
            if not title:
                title = await page.title()
        except Exception:
            title = await page.title()
        # 清理标题中的 " - 哔哩哔哩" 后缀
        title = re.sub(r'\s*[-–—]\s*哔哩哔哩.*$', '', title).strip()

        # 简介/描述
        content_text = ''
        try:
            desc_el = await page.query_selector('.desc-info-text, .desc, [class*="description"]')
            if desc_el:
                content_text = (await desc_el.inner_text()).strip()
        except Exception:
            pass

        # 互动数据（从页面文本正则提取）
        stats = {'likes': 0, 'favorites': 0, 'comments_count': 0, 'shares': 0, 'views': 0}
        try:
            text = await page.inner_text('body')
            like_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*点赞', text)
            fav_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*收藏', text)
            coin_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*投硬币', text)
            danmu_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*弹幕', text)
            play_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*播放', text)
            if like_match:
                stats['likes'] = parse_num(like_match.group(1))
            if fav_match:
                stats['favorites'] = parse_num(fav_match.group(1))
            if coin_match:
                stats['shares'] = parse_num(coin_match.group(1))
            if danmu_match:
                stats['comments_count'] = parse_num(danmu_match.group(1))
            if play_match:
                stats['views'] = parse_num(play_match.group(1))
        except Exception:
            pass

        # 作者
        author = {'name': '', 'fans_count': 0}
        try:
            author_el = await page.query_selector('.up-name, [class*="up-name"], [class*="author"]')
            if author_el:
                author['name'] = (await author_el.inner_text()).strip()
            # 粉丝数
            fans_el = await page.query_selector('[class*="fans"], [class*="follower"]')
            if fans_el:
                fans_text = await fans_el.inner_text()
                author['fans_count'] = parse_num(fans_text)
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

        # 视频信息
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
        logger.error(f'  B站 页面提取失败: {e}')
        return None


# ============================================================
# 评论加载（API 方式）
# ============================================================

async def load_bilibili_comments(page, note_id, max_comments=200):
    """
    通过 B站 API 加载评论（比 DOM 解析更可靠）。

    排序方式：
      sort=0 按热度排序
      sort=1 按时间排序
      sort=2 按热度+时间混合
    """
    comments = []
    seen_texts = set()

    # 尝试获取 aid（如果是 BV 号）
    aid = ''
    if note_id.startswith('BV'):
        aid = await get_aid_from_bvid(page, note_id)

    target = aid if aid else note_id

    if not target:
        logger.warning('  无法获取评论参数，跳过评论加载')
        return []

    # 分页获取评论
    max_pages = max(max_comments // 20, 1) + 1
    for pn in range(1, max_pages + 1):
        api_url = f'https://api.bilibili.com/x/v2/reply?type=1&oid={target}&sort=2&pn={pn}&ps=20'
        try:
            resp = await page.context.request.get(api_url)
            if resp.status != 200:
                break

            data = await resp.json()
            if data.get('code') != 0:
                # ps out of bounds 等错误
                if 'out of bounds' in str(data.get('message', '')):
                    break
                break

            replies = data.get('data', {}).get('replies', [])
            if not replies:
                break

            for r in replies:
                text = r.get('content', {}).get('message', '').strip()
                if not text or text[:50] in seen_texts:
                    continue
                seen_texts.add(text[:50])

                likes = r.get('like', 0)
                author = r.get('member', {}).get('uname', '')
                timestamp = r.get('ctime', '')

                # 子回复
                reply_replies = []
                if r.get('replies'):
                    for sub in r.get('replies', [])[:5]:
                        sub_text = sub.get('content', {}).get('message', '').strip()
                        if sub_text:
                            reply_replies.append({
                                'text': sub_text,
                                'likes': sub.get('like', 0),
                                'author': sub.get('member', {}).get('uname', ''),
                            })

                comments.append({
                    'text': text,
                    'likes': likes,
                    'timestamp': str(timestamp),
                    'author': author,
                    'replies': reply_replies,
                })

                if len(comments) >= max_comments:
                    break

            if len(comments) >= max_comments:
                break

            # 检查是否有更多
            page_info = data.get('data', {}).get('page', {})
            if pn >= page_info.get('count', 0):
                break

        except Exception as e:
            logger.debug(f'  B站 API 评论获取失败 (page {pn}): {e}')
            break

        # 频率控制
        await human_delay(1.0, 2.0)

    logger.info(f'  通过 API 获取 {len(comments)} 条评论')
    return comments[:max_comments]


# ============================================================
# 视频下载
# ============================================================

async def download_bilibili_video(page, note_id, note_dir, intercepted_urls):
    """下载B站视频（DASH 格式处理）"""
    video_path = os.path.join(note_dir, 'video.mp4')

    # 优先尝试拦截到的视频流 URL
    for vurl in intercepted_urls:
        if any(kw in vurl for kw in ['bilivideo', 'upos-sz', 'aliyuncs.com']):
            ok = await download_resource(page.context, vurl, video_path, timeout=120000)
            if ok:
                return video_path

    # 尝试从 <video> 标签
    try:
        video_el = await page.query_selector('video')
        if video_el:
            video_src = await video_el.get_attribute('src') or ''
            if video_src and video_src.startswith('http'):
                ok = await download_resource(page.context, video_src, video_path, timeout=120000)
                if ok:
                    return video_path
    except Exception:
        pass

    return ''


# ============================================================
# 单个笔记爬取
# ============================================================

async def crawl_bilibili_note(page, url, note_dir, cookie_str='', max_comments=200):
    """爬取单个B站笔记"""
    logger.info(f'正在爬取(B站): {url}')

    # 注入 Cookie（用于获取更多评论）
    if cookie_str:
        try:
            cookies = parse_cookie_string(cookie_str, domain='.bilibili.com')
            await page.context.add_cookies(cookies)
        except Exception as e:
            logger.warning(f'  Cookie 注入失败: {e}')

    # 设置拦截器
    video_urls = await intercept_video_url(page, 'bilibili')

    # 提取笔记信息
    note_data = await extract_bilibili_note_info(page, url, note_dir)
    if note_data is None:
        return None

    # 下载视频
    video_local = await download_bilibili_video(
        page, note_data['note_id'], note_dir, video_urls
    )
    if video_local:
        note_data['video']['local_path'] = video_local
        logger.info(f'  B站视频下载成功: {video_local}')
    else:
        logger.warning(f'  B站视频下载失败，跳过视频分析')
        note_data['video']['has_video'] = False

    # 加载评论（API 方式）
    logger.info(f'  正在加载B站评论...')
    note_data['comments'] = await load_bilibili_comments(
        page, note_data['note_id'], max_comments
    )
    note_data['stats']['comments_count'] = len(note_data['comments'])
    logger.info(f'  实际获取 {len(note_data["comments"])} 条评论')

    # 封面
    if video_local:
        cover_path = os.path.join(note_dir, 'cover.jpg')
        await save_first_frame_as_cover(video_local, cover_path)
        if os.path.exists(cover_path):
            note_data['video']['cover_path'] = cover_path

    return note_data


# ============================================================
# 批量爬取
# ============================================================

async def crawl_bilibili_notes(urls, output_dir, max_comments=200, headless=True,
                                cookie_str=''):
    """
    批量爬取B站笔记

    Args:
        urls: URL 列表
        output_dir: 输出目录
        max_comments: 每篇最大评论数
        headless: 是否无头模式（B站 headless 可用）
        cookie_str: Cookie 字符串（SESSDATA + bili_jct，用于获取更多评论）
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
            'platforms': {'bilibili': len(urls)},
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
            note_dir = make_note_dir(output_dir, 'bilibili', i + 1)

            success = False
            for retry in range(3):
                try:
                    note_data = await crawl_bilibili_note(
                        page, url, note_dir, cookie_str, max_comments
                    )
                    if note_data:
                        note_data['platform'] = 'bilibili'
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
    logger.info(f'B站爬取完成！成功 {result["crawl_metadata"]["successful"]}/{result["crawl_metadata"]["total_urls"]}')
    logger.info(f'结果已保存: {output_path}')
    return result


# ============================================================
# CLI 入口
# ============================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='B站笔记爬虫')
    parser.add_argument('url_file', help='URL 列表文件')
    parser.add_argument('--output', default='./crawl_output', help='输出目录')
    parser.add_argument('--max-comments', type=int, default=200, help='每篇最大评论数')
    parser.add_argument('--cookie', default='', help='Cookie 字符串 (SESSDATA + bili_jct)')
    parser.add_argument('--headed', action='store_true', help='显示浏览器窗口')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    with open(args.url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    if not urls:
        logger.error('URL 文件为空')
        sys.exit(1)

    asyncio.run(crawl_bilibili_notes(
        urls=urls,
        output_dir=args.output,
        max_comments=args.max_comments,
        headless=not args.headed,
        cookie_str=args.cookie,
    ))
