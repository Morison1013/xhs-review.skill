# -*- coding: utf-8 -*-
"""
crawl_notes.py — 小红书笔记爬虫（Playwright）

用法:
    python crawl_notes.py <URL文件> --cookie "cookie字符串" --output <输出目录>
    python crawl_notes.py <URL文件> --cookie "cookie字符串" --output <输出目录> --max-comments 200

URL文件格式：每行一个笔记URL，空行和#注释行自动跳过
"""
import asyncio
import json
import os
import sys
import time
import random
import re
import argparse
import logging
import base64

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_cookie_string(cookie_str):
    """将 'key1=val1; key2=val2' 格式的 Cookie 字符串转为列表"""
    cookies = []
    for pair in cookie_str.split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, _, value = pair.partition('=')
        cookies.append({
            'name': key.strip(),
            'value': value.strip(),
            'domain': '.xiaohongshu.com',
            'path': '/',
        })
    return cookies


async def human_delay(lo=1.0, hi=3.0):
    """随机延迟，模拟人类行为"""
    await asyncio.sleep(random.uniform(lo, hi))


async def simulate_scroll(page):
    """模拟滚动行为"""
    for _ in range(random.randint(2, 5)):
        await page.mouse.wheel(0, random.randint(200, 500))
        await asyncio.sleep(random.uniform(0.3, 0.8))


async def extract_note_info(page, url, note_dir):
    """
    从笔记页面提取结构化信息。
    返回 dict 或 None（页面无法访问）
    """
    try:
        # 提取 note_id
        note_id_match = re.search(r'explore/([a-f0-9]{24})', url)
        if not note_id_match:
            note_id_match = re.search(r'discovery/item/([a-f0-9]{24})', url)
        note_id = note_id_match.group(1) if note_id_match else f'unknown_{int(time.time())}'

        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await human_delay(2, 4)
        await simulate_scroll(page)
        await human_delay(1, 2)

        # 检测是否跳转到登录页
        current_url = page.url
        if 'login' in current_url.lower():
            logger.warning(f'  页面跳转登录页，Cookie 可能已过期: {url}')
            return None

        # 提取标题
        title = ''
        try:
            title_el = await page.query_selector('h1, .title, [class*="title"]')
            if title_el:
                title = (await title_el.inner_text()).strip()
        except Exception:
            pass

        # 提取正文文案
        content_text = ''
        try:
            # 多种方式尝试
            selectors = [
                '[class*="desc"]', '[class*="content"]', '[class*="note-detail"]',
                'article', '[class*="note-content"]'
            ]
            for sel in selectors:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if len(text) > 20:
                        content_text = text
                        break
        except Exception:
            pass

        # 提取图片 URL
        image_urls = []
        try:
            img_els = await page.query_selector_all('img[class*="image"], img[class*="photo"], img[src*="sns-web-note"]')
            for img in img_els:
                src = await img.get_attribute('src') or ''
                if src and ('sns-web' in src or 'xhscdn' in src) and src not in image_urls:
                    image_urls.append(src)
        except Exception:
            pass

        # 提取视频 URL（如果有）
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

        # 提取互动数据
        stats = {'likes': 0, 'favorites': 0, 'comments_count': 0, 'shares': 0}
        try:
            # 小红书的互动数据通常在页面某处
            text = await page.inner_text('body')
            # 尝试提取数字
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

        # 提取作者信息
        author = {'name': '', 'fans_count': 0}
        try:
            author_el = await page.query_selector('[class*="author"], [class*="user-name"]')
            if author_el:
                author['name'] = (await author_el.inner_text()).strip()
        except Exception:
            pass

        # 下载图片
        image_paths = []
        for i, img_url in enumerate(image_urls[:10]):  # 最多10张
            img_path = os.path.join(note_dir, f'img_{i}.jpg')
            try:
                resp = await page.context.request.get(img_url)
                if resp.status == 200:
                    img_bytes = await resp.body()
                    with open(img_path, 'wb') as f:
                        f.write(img_bytes)
                    image_paths.append(img_path)
                await human_delay(0.3, 0.8)
            except Exception as e:
                logger.debug(f'  图片下载失败: {e}')

        # 下载视频
        video_local_path = ''
        if video_info['has_video'] and video_info['video_url']:
            video_path = os.path.join(note_dir, 'video.mp4')
            try:
                resp = await page.context.request.get(video_info['video_url'])
                if resp.status == 200:
                    video_bytes = await resp.body()
                    with open(video_path, 'wb') as f:
                        f.write(video_bytes)
                    video_local_path = video_path
                    logger.info(f'  视频下载成功: {video_path}')
            except Exception as e:
                logger.warning(f'  视频下载失败: {e}')

        return {
            'note_id': note_id,
            'note_url': url,
            'title': title,
            'content_text': content_text,
            'note_type': 'video' if video_info['has_video'] else 'image',
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
        logger.error(f'  页面提取失败: {e}')
        return None


def parse_num(s):
    """将 '1.2万' 转为 12000，'1234' 转为 1234"""
    s = s.strip()
    if '万' in s or 'w' in s.lower():
        s = s.replace('万', '').replace('w', '').replace('W', '')
        return int(float(s) * 10000)
    try:
        return int(float(s))
    except ValueError:
        return 0


async def load_comments(page, max_comments=200):
    """
    滚动加载评论区。
    返回评论列表 [{text, likes, timestamp, author, replies}]
    """
    comments = []
    seen_texts = set()

    try:
        # 尝试点击"查看全部评论"或滚动到评论区
        await human_delay(1, 2)
        await simulate_scroll(page)
        await human_delay(1, 2)

        # 尝试点击展开评论按钮
        expand_selectors = [
            'text=查看更多评论', 'text=查看全部', '[class*="expand"]',
            '[class*="load-more"]', 'text=展开'
        ]
        for sel in expand_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await human_delay(1, 2)
                    break
            except Exception:
                pass

        # 滚动加载评论
        for scroll_round in range(max_comments // 10 + 5):
            await page.mouse.wheel(0, 400)
            await human_delay(1.5, 3.0)

            # 提取可见评论
            comment_selectors = [
                '[class*="comment"]', '[class*="comment-item"]',
                '[data-type="comment"]', '.comment-content'
            ]
            comment_els = []
            for sel in comment_selectors:
                els = await page.query_selector_all(sel)
                if els:
                    comment_els = els
                    break

            if not comment_els:
                # 尝试从页面文本中提取
                body_text = await page.inner_text('body')
                # 如果页面没有明显评论区，跳过
                if len(body_text) < 500:
                    break
                # 尝试用 JSON 方式提取（备用方案）
                break

            new_count = 0
            for el in comment_els:
                try:
                    text = (await el.inner_text()).strip()
                    # 去重
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
                        'text': text,
                        'likes': likes,
                        'timestamp': '',
                        'author': author,
                        'replies': [],
                    })
                    new_count += 1

                    if len(comments) >= max_comments:
                        break
                except Exception:
                    continue

            if new_count == 0 or len(comments) >= max_comments:
                # 没有新评论了
                break

            if scroll_round % 3 == 0:
                await human_delay(2, 4)

    except Exception as e:
        logger.warning(f'  评论加载异常: {e}')

    return comments[:max_comments]


async def intercept_video_url(page):
    """
    通过拦截网络请求捕获视频 URL。
    在页面加载前调用。
    """
    video_urls = []

    async def on_response(response):
        try:
            url = response.url
            if any(ext in url for ext in ['.mp4', '.m3u8', 'video', 'sns-video']):
                if response.status == 200:
                    video_urls.append(url)
        except Exception:
            pass

    page.on('response', on_response)
    return video_urls


async def crawl_note(page, url, note_dir, cookie, max_comments=200):
    """爬取单个笔记，含评论加载和视频拦截"""
    logger.info(f'正在爬取: {url}')

    # 注入 Cookie
    try:
        await page.context.add_cookies(parse_cookie_string(cookie))
    except Exception as e:
        logger.warning(f'  Cookie 注入失败: {e}')

    # 设置网络拦截器捕获视频 URL
    video_urls = await intercept_video_url(page)

    # 提取页面信息
    note_data = await extract_note_info(page, url, note_dir)
    if note_data is None:
        return None

    # 如果之前没抓到视频 URL，从拦截器拿
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
        note_data['comments'] = await load_comments(page, max_comments)
        logger.info(f'  实际获取 {len(note_data["comments"])} 条评论')

    # 保存封面帧（从视频第一帧）
    if note_data['video']['local_path']:
        try:
            import cv2
            cap = cv2.VideoCapture(note_data['video']['local_path'])
            ret, frame = cap.read()
            if ret:
                cover_path = os.path.join(note_dir, 'cover.jpg')
                cv2.imwrite(cover_path, frame)
                note_data['video']['cover_path'] = cover_path
            cap.release()
        except Exception:
            pass

    return note_data


def crawl_notes(url_file, cookie, output_dir, max_comments=200, max_notes=0, headless=True):
    """
    主入口函数。
    url_file: URL 列表文件路径
    cookie: Cookie 字符串
    output_dir: 输出目录
    max_comments: 每篇笔记最大评论数
    max_notes: 最大爬取笔记数（0=不限制）
    headless: 是否无头模式
    """
    # 读取 URL 列表
    with open(url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    if not urls:
        logger.error('URL 文件为空')
        return None

    if max_notes > 0:
        urls = urls[:max_notes]

    logger.info(f'共 {len(urls)} 个笔记待爬取')

    result = {
        'crawl_metadata': {
            'crawl_time': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'total_urls': len(urls),
            'successful': 0,
            'failed': 0,
            'cookie_valid': True,
            'max_comments': max_comments,
        },
        'notes': [],
    }

    async def _run():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='zh-CN',
            )

            page = await context.new_page()

            for i, url in enumerate(urls):
                note_dir = os.path.join(output_dir, f'note_{i+1}')
                os.makedirs(note_dir, exist_ok=True)

                success = False
                for retry in range(3):
                    try:
                        note_data = await crawl_note(page, url, note_dir, cookie, max_comments)
                        if note_data:
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

                # 频率控制：每篇笔记间隔 + 每 10 篇大休息
                if i < len(urls) - 1:
                    delay = random.uniform(3, 8)
                    logger.info(f'  等待 {delay:.1f} 秒...')
                    await asyncio.sleep(delay)

                    if (i + 1) % 10 == 0:
                        logger.info('  大休息 30 秒...')
                        await asyncio.sleep(30)

            await browser.close()

    asyncio.run(_run())

    # 保存结果
    output_path = os.path.join(output_dir, 'crawled_notes.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f'爬取完成！成功 {result["crawl_metadata"]["successful"]}/{result["crawl_metadata"]["total_urls"]}')
    logger.info(f'结果已保存: {output_path}')

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='小红书笔记爬虫')
    parser.add_argument('url_file', help='URL 列表文件（每行一个 URL）')
    parser.add_argument('--cookie', required=True, help='Cookie 字符串（key1=val1; key2=val2 格式）')
    parser.add_argument('--output', default='./xhs_crawl_output', help='输出目录（默认 ./xhs_crawl_output）')
    parser.add_argument('--max-comments', type=int, default=200, help='每篇笔记最大评论数（默认 200）')
    parser.add_argument('--max-notes', type=int, default=0, help='最大爬取笔记数（0=不限制）')
    parser.add_argument('--headed', action='store_true', help='显示浏览器窗口（默认无头模式）')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    crawl_notes(
        url_file=args.url_file,
        cookie=args.cookie,
        output_dir=args.output,
        max_comments=args.max_comments,
        max_notes=args.max_notes,
        headless=not args.headed,
    )
