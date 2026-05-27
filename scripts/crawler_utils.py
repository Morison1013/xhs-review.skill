# -*- coding: utf-8 -*-
"""
crawler_utils.py — 多平台爬虫共享工具函数
"""
import asyncio
import json
import os
import random
import re
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================
# 通用工具
# ============================================================

def parse_cookie_string(cookie_str, domain='.example.com'):
    """将 'key1=val1; key2=val2' 格式的 Cookie 字符串转为 Playwright cookies 列表"""
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
    """通过拦截网络请求捕获视频 URL"""
    video_urls = []

    async def on_response(response):
        try:
            url = response.url
            if platform == 'xiaohongshu':
                if any(ext in url for ext in ['.mp4', '.m3u8', 'video', 'sns-video']):
                    if response.status == 200:
                        video_urls.append(url)
            elif platform == 'bilibili':
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
    """通过浏览器上下文下载资源文件"""
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


def make_note_dir(output_dir, platform, index):
    """创建笔记输出目录"""
    note_dir = os.path.join(output_dir, f'{platform}_note_{index}')
    os.makedirs(note_dir, exist_ok=True)
    return note_dir


def save_crawl_result(result, output_dir):
    """保存爬取结果到 JSON"""
    output_path = os.path.join(output_dir, 'crawled_notes.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    return output_path
