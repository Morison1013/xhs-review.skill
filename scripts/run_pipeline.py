# -*- coding: utf-8 -*-
"""
run_pipeline.py — 小红书投放复盘全流程

用法:
  # 现有模式（Excel 数据文件）
  python run_pipeline.py <Excel数据文件> <品牌名称> [输出目录]

  # 爬虫模式
  python run_pipeline.py --crawl <URL文件> --cookie "cookie字符串" --brand 品牌名 [输出目录] [--llm-config config文件]
"""
import sys
import os
import subprocess
import argparse
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'config')


def run_pipeline(data_file, brand, output_dir=None):
    """Existing Excel-only pipeline (unchanged)."""
    if not os.path.exists(data_file):
        print(f'错误: 文件不存在: {data_file}')
        sys.exit(1)

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(data_file))

    data_file = os.path.abspath(data_file)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    tmp_dir = os.path.join(output_dir, '.xhs_review_tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    json_path = os.path.join(tmp_dir, 'analysis_result.json')
    chart_dir = os.path.join(tmp_dir, 'charts')
    output_name = f'{brand}小红书投放复盘SOP.docx'
    output_path = os.path.join(output_dir, output_name)

    print('=' * 60)
    print(f'小红书投放复盘 Pipeline')
    print(f'数据文件: {data_file}')
    print(f'品牌名称: {brand}')
    print(f'输出目录: {output_dir}')
    print('=' * 60)

    # Step 1: Analyze
    print('\n[1/3] 数据分析中...')
    ret = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'analyze_data.py'),
                          data_file, json_path], capture_output=False)
    if ret.returncode != 0:
        print('分析失败!')
        sys.exit(1)

    # Step 2: Generate charts
    print('\n[2/3] 生成图表中...')
    ret = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'generate_charts.py'),
                          json_path, chart_dir], capture_output=False)
    if ret.returncode != 0:
        print('图表生成失败!')
        sys.exit(1)

    # Step 3: Build report
    print('\n[3/3] 组装Word报告中...')
    ret = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'build_report.py'),
                          json_path, chart_dir, output_path, brand], capture_output=False)
    if ret.returncode != 0:
        print('报告生成失败!')
        sys.exit(1)

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print('\n' + '=' * 60)
    print(f'完成！报告已保存: {output_path}')
    print('=' * 60)


def run_crawl_pipeline(url_file, cookie, brand, output_dir=None, llm_config=None, max_comments=200, max_notes=0, headed=False):
    """Crawl-driven pipeline: crawl → comment analysis → video analysis → merge → report."""
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(url_file))

    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    tmp_dir = os.path.join(output_dir, '.xhs_review_tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    crawled_path = os.path.join(tmp_dir, 'crawled_notes.json')
    comment_path = os.path.join(tmp_dir, 'comment_analysis.json')
    video_path = os.path.join(tmp_dir, 'video_analysis.json')
    json_path = os.path.join(tmp_dir, 'analysis_result.json')
    chart_dir = os.path.join(tmp_dir, 'charts')
    output_name = f'{brand}内容分析报告.docx'
    output_docx = os.path.join(output_dir, output_name)

    if llm_config is None:
        default_config = os.path.join(CONFIG_DIR, 'llm_config.json')
        if os.path.exists(default_config):
            llm_config = default_config

    print('=' * 60)
    print(f'多平台内容分析 Pipeline (爬虫模式)')
    print(f'URL 文件: {url_file}')
    print(f'品牌名称: {brand}')
    print(f'输出目录: {output_dir}')
    print('=' * 60)

    # Step 0: Crawl notes
    print('\n[Step 0/5] 爬取笔记中...')
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, 'crawl_notes.py'),
           url_file, '--output', tmp_dir,
           '--max-comments', str(max_comments)]
    if cookie:
        cmd.extend(['--cookie', cookie])
    if max_notes > 0:
        cmd.extend(['--max-notes', str(max_notes)])
    if headed:
        cmd.append('--headed')
    ret = subprocess.run(cmd, capture_output=False)
    if ret.returncode != 0 or not os.path.exists(crawled_path):
        print('爬取失败!')
        sys.exit(1)

    # Check crawl results
    with open(crawled_path, 'r', encoding='utf-8') as f:
        crawled_data = __import__('json').load(f)
    successful = crawled_data.get('crawl_metadata', {}).get('successful', 0)
    if successful == 0:
        print('没有成功爬取任何笔记!')
        sys.exit(1)
    print(f'成功爬取 {successful} 篇笔记')

    # Step 1: Comment analysis
    print('\n[Step 1/5] 分析评论舆情...')
    ret = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'analyze_comments.py'),
                          crawled_path, comment_path], capture_output=False)
    if ret.returncode != 0:
        print('评论分析失败（继续执行）')

    # Step 2: Video analysis (if LLM config available and video notes exist)
    has_video = any(
        n.get('video', {}).get('local_path')
        for n in crawled_data.get('notes', [])
    )
    if has_video and llm_config and os.path.exists(llm_config):
        print('\n[Step 2/5] 分析视频内容...')
        video_cmd = [sys.executable, os.path.join(SCRIPT_DIR, 'analyze_video.py'),
                     crawled_path, llm_config, tmp_dir]
        if os.path.exists(comment_path):
            video_cmd.append(comment_path)
        ret = subprocess.run(video_cmd, capture_output=False)
        if ret.returncode != 0:
            print('视频分析失败（继续执行）')
    elif has_video and not llm_config:
        print('\n[Step 2/5] 跳过视频分析（未提供 LLM 配置）')
    else:
        print('\n[Step 2/5] 跳过视频分析（无视频笔记）')

    # Step 3: Merge data
    print('\n[Step 3/5] 合并数据...')
    merge_cmd = [sys.executable, os.path.join(SCRIPT_DIR, 'analyze_data.py'),
                 '--merge-crawl', crawled_path, json_path]
    if os.path.exists(comment_path):
        merge_cmd.extend(['--comments', comment_path])
    if os.path.exists(video_path):
        merge_cmd.extend(['--videos', video_path])
    ret = subprocess.run(merge_cmd, capture_output=False)
    if ret.returncode != 0:
        print('数据合并失败!')
        sys.exit(1)

    # Step 4: Generate charts
    print('\n[Step 4/5] 生成图表...')
    ret = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'generate_charts.py'),
                          json_path, chart_dir], capture_output=False)
    if ret.returncode != 0:
        print('图表生成失败（继续执行）')

    # Step 5: Build report
    print('\n[Step 5/5] 组装Word报告...')
    ret = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'build_report.py'),
                          json_path, chart_dir, output_docx, brand], capture_output=False)
    if ret.returncode != 0:
        print('报告生成失败!')
        sys.exit(1)

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print('\n' + '=' * 60)
    print(f'完成！报告已保存: {output_docx}')
    print('=' * 60)


def main():
    parser = argparse.ArgumentParser(description='小红书投放复盘 Pipeline')
    subparsers = parser.add_subparsers(dest='mode')

    # Excel mode (default, positional args)
    # We handle this via fallback if no --crawl flag

    # Crawl mode
    crawl_parser = subparsers.add_parser('crawl', help='爬虫模式：从 URL 列表爬取笔记并分析')
    crawl_parser.add_argument('url_file', help='URL 列表文件（每行一个 URL）')
    crawl_parser.add_argument('--cookie', default=None, help='Cookie 字符串（小红书需要登录，B站/抖音可选）')
    crawl_parser.add_argument('--brand', required=True, help='品牌名称')
    crawl_parser.add_argument('--output', default=None, help='输出目录')
    crawl_parser.add_argument('--llm-config', default=None, help='LLM 配置文件路径')
    crawl_parser.add_argument('--max-comments', type=int, default=200, help='每篇最大评论数')
    crawl_parser.add_argument('--max-notes', type=int, default=0, help='最大爬取笔记数')
    crawl_parser.add_argument('--headed', action='store_true', help='显示浏览器窗口')

    # Also support --crawl as a flag for backward compatibility
    parser.add_argument('--crawl', nargs='?', const=True, help='URL 文件路径（爬虫模式）')
    parser.add_argument('--cookie', default=None, help='Cookie 字符串（小红书需要登录，B站/抖音可选）')
    parser.add_argument('--brand', default=None, help='品牌名称')
    parser.add_argument('--output', default=None, help='输出目录')
    parser.add_argument('--llm-config', default=None, help='LLM 配置文件')
    parser.add_argument('--max-comments', type=int, default=200, help='每篇最大评论数')
    parser.add_argument('--max-notes', type=int, default=0, help='最大爬取笔记数')
    parser.add_argument('--headed', action='store_true', help='显示浏览器窗口')

    args = parser.parse_args()

    # Determine mode
    if args.mode == 'crawl' or args.crawl:
        url_file = args.url_file if args.mode == 'crawl' else (args.crawl if isinstance(args.crawl, str) else None)
        if not url_file:
            parser.error('爬虫模式需要提供 URL 文件路径')

        run_crawl_pipeline(
            url_file=url_file,
            cookie=args.cookie or '',
            brand=args.brand,
            output_dir=args.output,
            llm_config=args.llm_config,
            max_comments=args.max_comments,
            max_notes=args.max_notes,
            headed=args.headed,
        )
    else:
        # Excel mode (fallback to positional args)
        if len(sys.argv) < 3:
            # Check if it's just --help
            if '--help' in sys.argv or '-h' in sys.argv:
                parser.print_help()
                sys.exit(0)
            print(f'用法:')
            print(f'  # Excel 模式:')
            print(f'  python run_pipeline.py <Excel数据文件> <品牌名称> [输出目录]')
            print(f'  # 爬虫模式:')
            print(f'  python run_pipeline.py crawl <URL文件> --cookie "xxx" --brand 品牌名 [输出目录]')
            sys.exit(1)

        data_file = sys.argv[1]
        brand = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else None
        run_pipeline(data_file, brand, output_dir)


if __name__ == '__main__':
    main()
