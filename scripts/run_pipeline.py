# -*- coding: utf-8 -*-
"""
run_pipeline.py — 小红书投放复盘全流程
用法: python run_pipeline.py <Excel数据文件> <品牌名称> [输出目录]
"""
import sys
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_pipeline(data_file, brand, output_dir=None):
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
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print('\n' + '=' * 60)
    print(f'完成！报告已保存: {output_path}')
    print('=' * 60)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f'用法: python run_pipeline.py <Excel数据文件> <品牌名称> [输出目录]')
        print(f'示例: python run_pipeline.py 0310.xlsx 钙尔奇')
        sys.exit(1)

    data_file = sys.argv[1]
    brand = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else None
    run_pipeline(data_file, brand, output_dir)
