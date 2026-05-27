# -*- coding: utf-8 -*-
"""
小红书笔记爬虫（Playwright）
支持多平台 URL 自动识别：小红书 / B站 / 抖音
"""
import asyncio
import json
import os
import time
import random
import re
import logging
import base64

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================
# 工具函数
# ============================================================

def parse_cookie_string(cookie_str, domain='.xiaohongshu.com'):
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
            'domain': domain,
            'path': '/',
        })
    return cookies


async def human_delay(lo=1.0, hi=3.0):
    await asyncio.sleep(random.uniform(lo, hi))


async def simulate_scroll(page, times=None):
    if times is None:
        times = random.randint(2, 5)
    for _ in range(times):
        await page.mouse.wheel(0, random.randint(200, 500))
        await asyncio.sleep(random.uniform(0.3, 0.8))


def parse_num(s):
    s = str(s).strip()
    if '万' in s or 'w' in s.lower():
        s = s.replace('万', '').replace('w', '').replace('W', '')
        try:
            return int(float(s) * 10000)
        except ValueError:
            return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def detect_platform(url):
    """根据 URL 识别平台"""
    if 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return 'xiaohongshu'
    elif 'bilibili.com' in url or 'b23.tv' in url:
        return 'bilibili'
    elif 'douyin.com' in url or 'iesdouyin.com' in url:
        return 'douyin'
    else:
        return 'unknown'


def extract_note_id_from_url(url, platform):
    """从 URL 提取笔记 ID"""
    if platform == 'xiaohongshu':
        m = re.search(r'(?:explore|discovery/item)/([a-f0-9]{24})', url)
        if m:
            return m.group(1)
    elif platform == 'bilibili':
        m = re.search(r'(?:video/)?((?:av\d+)|(?:BV[A-Za-z0-9]+))', url)
        if m:
            return m.group(1)
    elif platform == 'douyin':
        m = re.search(r'video/(\d+)', url)
        if m:
            return m.group(1)
    return f'unknown_{int(time.time())}_{random.randint(1000,9999)}'


async def intercept_video_url(page, platform):
    """
    通过拦截网络请求捕获视频 URL。
    在页面加载前调用。
    """
    video_urls = []

    async def on_response(response):
        try:
            url = response.url
            if platform == 'xiaohongshu':
                if any(ext in url for ext in ['.mp4', '.m3u8', 'video', 'sns-video']):
                    if response.status == 200:
                        video_urls.append(url)
            elif platform == 'bilibili':
                # B站视频通过 DASH 或 flv 获取
                if any(kw in url for kw in ['bilivideo', 'upos-sz', 'aliyuncs.com', 'qn=']):
                    if response.status == 200:
                        video_urls.append(url)
            elif platform == 'douyin':
                if any(kw in url for kw in ['douyinvod', 'douyincdn', 'byteimg', 'douyinpic', '.mp4']):
                    if response.status == 200:
                        video_urls.append(url)
        except Exception:
            pass

    page.on('response', on_response)
    return video_urls


async def download_resource(page_or_context, url, save_path, timeout=60000):
    """通过浏览器上下文下载视频文件"""
    try:
        if hasattr(page_or_context, 'request'):
            resp = await page_or_context.request.get(url, timeout=timeout)
        else:
            resp = await page_or_context.get(url, timeout=timeout)
        if resp.status == 200:
            data = await resp.body()
            with open(save_path, 'wb') as f:
                f.write(data)
            return True
    except Exception as e:
        logger.debug(f'  资源下载失败: {e}')
    return False


async def save_first_frame_as_cover(video_path, cover_path):
    """从视频第一帧提取封面图"""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(cover_path, frame)
            return True
        cap.release()
    except Exception:
        pass
    return False


# ============================================================
# 小红书爬虫
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
        if 'login' in current_url.lower():
            logger.warning(f'  页面跳转登录页，Cookie 可能已过期: {url}')
            return None

        title = ''
        try:
            title_el = await page.query_selector('h1, .title, [class*="title"]')
            if title_el:
                title = (await title_el.inner_text()).strip()
        except Exception:
            pass

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

        image_urls = []
        try:
            img_els = await page.query_selector_all('img[class*="image"], img[class*="photo"], img[src*="sns-web-note"]')
            for img in img_els:
                src = await img.get_attribute('src') or ''
                if src and ('sns-web' in src or 'xhscdn' in src) and src not in image_urls:
                    image_urls.append(src)
        except Exception:
            pass

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

        author = {'name': '', 'fans_count': 0}
        try:
            author_el = await page.query_selector('[class*="author"], [class*="user-name"]')
            if author_el:
                author['name'] = (await author_el.inner_text()).strip()
        except Exception:
            pass

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
        logger.error(f'  XHS 页面提取失败: {e}')
        return None


async def load_xhs_comments(page, max_comments=200):
    """滚动加载小红书评论区"""
    comments = []
    seen_texts = set()

    try:
        await human_delay(1, 2)
        await simulate_scroll(page)
        await human_delay(1, 2)

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


async def crawl_xhs_note(page, url, note_dir, cookie, max_comments=200):
    """爬取单个小红书笔记"""
    logger.info(f'正在爬取(小红书): {url}')

    try:
        await page.context.add_cookies(parse_cookie_string(cookie))
    except Exception as e:
        logger.warning(f'  Cookie 注入失败: {e}')

    video_urls = await intercept_video_url(page, 'xiaohongshu')
    note_data = await extract_xhs_note_info(page, url, note_dir)
    if note_data is None:
        return None

    if not note_data['video']['has_video'] and video_urls:
        for vu in video_urls:
            if 'mp4' in vu or 'video' in vu:
                note_data['video']['has_video'] = True
                note_data['video']['video_url'] = vu
                note_data['note_type'] = 'video'
                break

    if note_data['stats'].get('comments_count', 0) > 0:
        logger.info(f'  正在加载评论 (预计 {note_data["stats"]["comments_count"]} 条)...')
        note_data['comments'] = await load_xhs_comments(page, max_comments)
        logger.info(f'  实际获取 {len(note_data["comments"])} 条评论')

    if note_data['video']['local_path']:
        cover_path = os.path.join(note_dir, 'cover.jpg')
        await save_first_frame_as_cover(note_data['video']['local_path'], cover_path)
        if os.path.exists(cover_path):
            note_data['video']['cover_path'] = cover_path

    return note_data


# ============================================================
# B站爬虫
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

        # 简介/描述
        content_text = ''
        try:
            desc_el = await page.query_selector('[class*="desc-info"], .desc-info-text, .desc, [class*="description"]')
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
            coin_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*投硬币', text)
            danmu_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*弹幕', text)
            play_match = re.search(r'(\d+(?:\.\d+)?[w万]?)\s*播放', text)
            if like_match:
                stats['likes'] = parse_num(like_match.group(1))
            if fav_match:
                stats['favorites'] = parse_num(fav_match.group(1))
            if coin_match:
                stats['shares'] = parse_num(coin_match.group(1))  # 用 shares 表示投币
            if danmu_match:
                stats['comments_count'] = parse_num(danmu_match.group(1))  # 弹幕数
            if play_match:
                stats['views'] = parse_num(play_match.group(1))
        except Exception:
            pass

        # 作者
        author = {'name': '', 'fans_count': 0}
        try:
            author_el = await page.query_selector('[class*="up-name"], [class*="author"], .up-name, [class*="user-name"]')
            if author_el:
                author['name'] = (await author_el.inner_text()).strip()
        except Exception:
            pass

        # 封面图
        image_paths = []
        try:
            cover_el = await page.query_selector('.bpx-player-poster-shadow img, .video-page-card img, img.cover')
            if cover_el:
                cover_url = await cover_el.get_attribute('src') or await cover_el.get_attribute('data-src') or ''
                if cover_url:
                    cover_path = os.path.join(note_dir, 'cover.jpg')
                    resp = await page.context.request.get(cover_url)
                    if resp.status == 200:
                        with open(cover_path, 'wb') as f:
                            f.write(await resp.body())
                        image_paths.append(cover_path)
        except Exception:
            pass

        # B站始终有视频
        video_info = {'has_video': True, 'video_url': '', 'duration_sec': 0, 'local_path': ''}

        # 尝试从 <video> 标签获取
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


async def load_bilibili_comments(page, max_comments=200):
    """
    加载B站评论。
    B站评论区在右侧，需要等待加载完成。
    也支持调用 API 获取。
    """
    comments = []
    seen_texts = set()

    try:
        await human_delay(2, 4)
        # 滚动到评论区域
        await page.mouse.wheel(0, 300)
        await human_delay(2, 3)

        # 尝试从页面提取
        comment_selectors = [
            '[class*="reply-item"]', '.reply-item',
            '[class*="comment-item"]', '.reply-content',
        ]
        for sel in comment_selectors:
            comment_els = await page.query_selector_all(sel)
            if comment_els:
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
                        if len(comments) >= max_comments:
                            break
                    except Exception:
                        continue

        # 如果页面提取不到，尝试调用 API
        if not comments:
            try:
                # 从 URL 提取 aid
                note_id_match = re.search(r'(?:video/)?((?:av\d+)|(?:BV[A-Za-z0-9]+))', page.url)
                if note_id_match:
                    aid_or_bvid = note_id_match.group(1)
                    api_url = f'https://api.bilibili.com/x/v2/reply?type=1&oid={aid_or_bvid}&sort=0&pn=1&ps={min(max_comments, 50)}'
                    resp = await page.context.request.get(api_url)
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('code') == 0:
                            replies = data.get('data', {}).get('replies', [])
                            for r in replies:
                                text = r.get('content', {}).get('message', '')
                                likes = r.get('like', 0)
                                author = r.get('member', {}).get('uname', '')
                                if text:
                                    comments.append({
                                        'text': text.strip(),
                                        'likes': likes,
                                        'timestamp': '',
                                        'author': author,
                                        'replies': [],
                                    })
                                    seen_texts.add(text[:50])
                                    if len(comments) >= max_comments:
                                        break
            except Exception as e:
                logger.debug(f'  B站 API 评论获取失败: {e}')

    except Exception as e:
        logger.warning(f'  B站 评论加载异常: {e}')

    return comments[:max_comments]


async def download_bilibili_video(page, url, note_id, note_dir, intercepted_urls):
    """
    下载B站视频。
    B站视频是 DASH 分片格式，直接下载 mp4 比较困难。
    优先使用拦截到的视频流 URL。
    """
    video_path = os.path.join(note_dir, 'video.mp4')

    # 尝试从拦截的 URL 中下载
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


async def crawl_bilibili_note(page, url, note_dir, cookie, max_comments=200):
    """爬取单个B站笔记"""
    logger.info(f'正在爬取(B站): {url}')

    if cookie:
        try:
            await page.context.add_cookies(parse_cookie_string(cookie, domain='.bilibili.com'))
        except Exception as e:
            logger.warning(f'  Cookie 注入失败: {e}')

    video_urls = await intercept_video_url(page, 'bilibili')
    note_data = await extract_bilibili_note_info(page, url, note_dir)
    if note_data is None:
        return None

    # 下载视频
    video_local = await download_bilibili_video(page, url, note_data['note_id'], note_dir, video_urls)
    if video_local:
        note_data['video']['local_path'] = video_local
        logger.info(f'  B站视频下载成功: {video_local}')
    else:
        logger.warning(f'  B站视频下载失败，跳过视频分析')
        note_data['video']['has_video'] = False

    # 加载评论
    logger.info(f'  正在加载B站评论...')
    note_data['comments'] = await load_bilibili_comments(page, max_comments)
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
# 抖音爬虫
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

        # 标题 — 从 meta 标签或页面标题
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


async def crawl_douyin_note(page, url, note_dir, cookie, max_comments=200):
    """爬取单个抖音笔记"""
    logger.info(f'正在爬取(抖音): {url}')

    if cookie:
        try:
            await page.context.add_cookies(parse_cookie_string(cookie, domain='.douyin.com'))
        except Exception as e:
            logger.warning(f'  Cookie 注入失败: {e}')

    video_urls = await intercept_video_url(page, 'douyin')
    note_data = await extract_douyin_note_info(page, url, note_dir)
    if note_data is None:
        return None

    # 下载视频
    if note_data['video'].get('video_url'):
        video_path = os.path.join(note_dir, 'video.mp4')
        ok = await download_resource(page.context, note_data['video']['video_url'], video_path, timeout=60000)
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
# 主调度器
# ============================================================

PLATFORM_MAP = {
    'xiaohongshu': {
        'crawl_fn': crawl_xhs_note,
        'cookie_domain': '.xiaohongshu.com',
    },
    'bilibili': {
        'crawl_fn': crawl_bilibili_note,
        'cookie_domain': '.bilibili.com',
    },
    'douyin': {
        'crawl_fn': crawl_douyin_note,
        'cookie_domain': '.douyin.com',
    },
}


def crawl_notes(url_file, cookie, output_dir, max_comments=200, max_notes=0, headless=True):
    """
    主入口函数。自动识别平台并分发到对应爬虫。
    """
    with open(url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    if not urls:
        logger.error('URL 文件为空')
        return None

    if max_notes > 0:
        urls = urls[:max_notes]

    # 统计平台分布
    platform_counts = {}
    for u in urls:
        p = detect_platform(u)
        platform_counts[p] = platform_counts.get(p, 0) + 1

    logger.info(f'共 {len(urls)} 个链接待爬取: {platform_counts}')

    result = {
        'crawl_metadata': {
            'crawl_time': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'total_urls': len(urls),
            'successful': 0,
            'failed': 0,
            'cookie_valid': True,
            'max_comments': max_comments,
            'platforms': platform_counts,
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
                platform = detect_platform(url)
                if platform == 'unknown':
                    logger.warning(f'  未知平台，跳过: {url}')
                    result['crawl_metadata']['failed'] += 1
                    continue

                platform_cfg = PLATFORM_MAP[platform]
                note_dir = os.path.join(output_dir, f'{platform}_note_{i+1}')
                os.makedirs(note_dir, exist_ok=True)

                success = False
                for retry in range(3):
                    try:
                        note_data = await platform_cfg['crawl_fn'](
                            page, url, note_dir, cookie, max_comments
                        )
                        if note_data:
                            note_data['platform'] = platform
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

            await browser.close()

    asyncio.run(_run())

    output_path = os.path.join(output_dir, 'crawled_notes.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f'爬取完成！成功 {result["crawl_metadata"]["successful"]}/{result["crawl_metadata"]["total_urls"]}')
    logger.info(f'结果已保存: {output_path}')

    return result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='多平台笔记爬虫（小红书/B站/抖音）')
    parser.add_argument('url_file', help='URL 列表文件（每行一个 URL）')
    parser.add_argument('--cookie', required=False, default=None, help='Cookie 字符串（key1=val1; key2=val2 格式）')
    parser.add_argument('--output', default='./crawl_output', help='输出目录（默认 ./crawl_output）')
    parser.add_argument('--max-comments', type=int, default=200, help='每篇笔记最大评论数（默认 200）')
    parser.add_argument('--max-notes', type=int, default=0, help='最大爬取笔记数（0=不限制）')
    parser.add_argument('--headed', action='store_true', help='显示浏览器窗口（默认无头模式）')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    crawl_notes(
        url_file=args.url_file,
        cookie=args.cookie or '',
        output_dir=args.output,
        max_comments=args.max_comments,
        max_notes=args.max_notes,
        headless=not args.headed,
    )
