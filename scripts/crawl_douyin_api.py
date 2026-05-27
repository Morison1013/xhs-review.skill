#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
抖音评论 API 爬取 - 基于 MediaCrawler 方案
核心思路：
1. 用 Playwright + 用户 Cookie 完成登录
2. 用浏览器内的 fetch 调用抖音内部评论 API
3. 利用浏览器自动处理 a_bogus 签名
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from playwright.async_api import async_playwright

COOKIE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'douyin_cookie.txt'))
OUTPUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'douyin_api_result.json'))
AWEME_ID = '7632534891883810082'
VIDEO_URL = f'https://www.douyin.com/video/{AWEME_ID}'

def parse_cookie_string(cookie_str, domain='.douyin.com'):
    cookies = []
    for pair in cookie_str.split(';'):
        pair = pair.strip()
        if '=' not in pair: continue
        key, _, value = pair.partition('=')
        cookies.append({'name': key.strip(), 'value': value.strip(), 'domain': domain, 'path': '/'})
    return cookies

async def main():
    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookie_str = f.read().strip()
    cookies = parse_cookie_string(cookie_str, domain='.douyin.com')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
            locale='zh-CN',
        )
        await context.add_cookies(cookies)
        page = await context.new_page()

        # 1. 先访问首页初始化
        print('步骤1: 访问抖音首页...')
        await page.goto('https://www.douyin.com', wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(5000)

        # 2. 访问视频页，让浏览器建立完整会话
        print('步骤2: 访问视频页...')
        await page.goto(VIDEO_URL, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(10000)

        # 检查 localStorage 中是否有 xmst (msToken 来源)
        local_storage = await page.evaluate('() => window.localStorage')
        ms_token = local_storage.get('xmst', '')
        print(f'  xmst (msToken): {ms_token[:30]}...' if ms_token else '  无 xmst')

        # 3. 用浏览器内的 fetch 直接调用评论 API
        # 浏览器会自动处理 Cookie、签名等所有验证
        print('\n步骤3: 调用评论 API...')

        api_result = await page.evaluate(f'''() => {{
            return new Promise((resolve, reject) => {{
                const url = '/aweme/v1/web/comment/list/?aweme_id={AWEME_ID}&cursor=0&count=20&item_type=0';
                fetch(url, {{
                    method: 'GET',
                    credentials: 'include',
                }})
                .then(r => r.json())
                .then(data => resolve(data))
                .catch(err => reject(err.toString()));
            }});
        }}''')

        print(f'API 返回状态: {json.dumps(api_result, ensure_ascii=False)[:200]}...')

        # 检查返回结果
        if isinstance(api_result, dict):
            status_code = api_result.get('status_code', -1)
            has_more = api_result.get('has_more', 0)
            comments = api_result.get('comments', [])
            cursor = api_result.get('cursor', 0)

            print(f'  status_code: {status_code}')
            print(f'  has_more: {has_more}')
            print(f'  cursor: {cursor}')
            print(f'  评论数: {len(comments)}')

            if comments:
                print(f'\n前5条评论:')
                for i, c in enumerate(comments[:5]):
                    text = c.get('text', '')
                    user = c.get('user', {})
                    nickname = user.get('nickname', '未知')
                    likes = c.get('digg_count', 0)
                    ip = c.get('ip_label', '')
                    print(f'  [{i+1}] {nickname} ({ip}): {text[:80]} ({likes}赞)')

                # 继续加载更多评论
                if has_more and len(comments) < 200:
                    print(f'\n继续加载更多评论...')
                    all_comments = list(comments)
                    current_cursor = cursor
                    max_pages = 20  # 最多再加载20页

                    for page_num in range(max_pages):
                        await page.wait_for_timeout(2000)  # 间隔2秒

                        next_page = await page.evaluate(f'''() => {{
                            return new Promise((resolve, reject) => {{
                                const url = '/aweme/v1/web/comment/list/?aweme_id={AWEME_ID}&cursor={current_cursor}&count=20&item_type=0';
                                fetch(url, {{
                                    method: 'GET',
                                    credentials: 'include',
                                }})
                                .then(r => r.json())
                                .then(data => resolve(data))
                                .catch(err => reject(err.toString()));
                            }});
                        }}''')

                        batch_comments = next_page.get('comments', [])
                        current_cursor = next_page.get('cursor', 0)
                        has_more = next_page.get('has_more', 0)

                        all_comments.extend(batch_comments)
                        print(f'  第{page_num+2}批: 获取 {len(batch_comments)} 条, 累计 {len(all_comments)} 条, has_more={has_more}')

                        if not has_more or len(all_comments) >= 200:
                            break

                    comments = all_comments[:200]

            # 4. 获取视频详情
            print('\n步骤4: 获取视频详情...')
            detail_result = await page.evaluate(f'''() => {{
                return new Promise((resolve, reject) => {{
                    const url = '/aweme/v1/web/aweme/detail/?aweme_id={AWEME_ID}';
                    fetch(url, {{
                        method: 'GET',
                        credentials: 'include',
                    }})
                    .then(r => r.json())
                    .then(data => resolve(data))
                    .catch(err => reject(err.toString()));
                }});
            }}''')

            aweme_detail = detail_result.get('aweme_detail', {}) if isinstance(detail_result, dict) else {}
            if aweme_detail:
                desc = aweme_detail.get('desc', '')
                author = aweme_detail.get('author', {})
                stats = aweme_detail.get('statistics', {})
                video = aweme_detail.get('video', {})
                duration = video.get('duration', 0)

                print(f'  标题: {desc[:80]}')
                print(f'  作者: {author.get("nickname", "")}')
                print(f'  点赞: {stats.get("digg_count", 0)}')
                print(f'  评论: {stats.get("comment_count", 0)}')
                print(f'  收藏: {stats.get("collect_count", 0)}')
                print(f'  分享: {stats.get("share_count", 0)}')
                print(f'  时长: {duration}ms')

            # 5. 保存结果
            result = {
                'platform': 'douyin',
                'note_id': AWEME_ID,
                'note_url': VIDEO_URL,
                'crawl_time': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'title': aweme_detail.get('desc', '') if aweme_detail else '',
                'author': {
                    'name': author.get('nickname', '') if author else '',
                    'sec_uid': author.get('sec_uid', '') if author else '',
                },
                'stats': {
                    'plays': stats.get('play_count', 0) if stats else 0,
                    'likes': stats.get('digg_count', 0) if stats else 0,
                    'comments_count': stats.get('comment_count', 0) if stats else 0,
                    'favorites': stats.get('collect_count', 0) if stats else 0,
                    'shares': stats.get('share_count', 0) if stats else 0,
                },
                'video': {
                    'duration_sec': round(duration / 1000) if duration else 0,
                },
                'comments': [],
            }

            # 标准化评论格式
            for c in comments:
                user = c.get('user', {})
                result['comments'].append({
                    'text': c.get('text', ''),
                    'author': user.get('nickname', ''),
                    'likes': c.get('digg_count', 0),
                    'ip': c.get('ip_label', ''),
                    'timestamp': c.get('create_time', 0),
                    'reply_count': c.get('reply_comment_total', 0),
                })

            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f'\n===== 最终结果 =====')
            print(f'标题: {result["title"][:60]}')
            print(f'作者: {result["author"]["name"]}')
            print(f'播放: {result["stats"]["plays"]}')
            print(f'点赞: {result["stats"]["likes"]}')
            print(f'评论: {result["stats"]["comments_count"]}')
            print(f'收藏: {result["stats"]["favorites"]}')
            print(f'时长: {result["video"]["duration_sec"]}秒')
            print(f'爬取评论: {len(result["comments"])} 条')

            if result['comments']:
                print(f'\n前3条评论:')
                for i, c in enumerate(result['comments'][:3]):
                    print(f'  [{i+1}] {c["author"]}: {c["text"][:60]} ({c["likes"]}赞, {c["ip"]})')

            print(f'\n结果已保存: {OUTPUT_FILE}')
        else:
            print(f'API 返回异常: {api_result}')

        await browser.close()

asyncio.run(main())
