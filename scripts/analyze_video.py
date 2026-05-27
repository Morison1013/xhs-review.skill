# -*- coding: utf-8 -*-
"""
analyze_video.py — 小红书视频内容分析

功能:
- OpenCV 提取视频关键帧
- 将帧图片送入 Claude Vision API 分析内容
- 结合笔记标题/正文/评论热词做上下文
- 输出结构化分析：内容主题、视觉风格、叙事模式、切角、核心卖点

用法:
    python analyze_video.py <crawled_notes.json> <llm_config.json> <输出目录>
"""
import json
import sys
import os
import time
import logging
import base64
from io import BytesIO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================
# 视频帧提取
# ============================================================

def extract_frames(video_path, output_dir, interval_sec=3, max_frames=12, max_size=(800, 600)):
    """
    使用 OpenCV 从视频中提取关键帧。
    返回提取的帧文件路径列表。
    """
    try:
        import cv2
    except ImportError:
        logger.error('需要安装 opencv-python: pip install opencv-python')
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f'无法打开视频: {video_path}')
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    logger.info(f'视频信息: {duration:.1f}s, {fps:.1f}fps, {total_frames}帧')

    # 计算采样间隔
    if interval_sec <= 0:
        interval_sec = max(duration / max_frames, 2)

    frame_paths = []
    frame_idx = 0
    timestamps = []

    # 按时间间隔采样
    t = 0
    while t < duration and len(frame_paths) < max_frames:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if ret:
            # 缩放图片
            h, w = frame.shape[:2]
            target_w, target_h = max_size
            if w > target_w or h > target_h:
                scale = min(target_w / w, target_h / h)
                new_w = int(w * scale)
                new_h = int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # 保存为 JPEG
            frame_filename = f'frame_{len(frame_paths):03d}.jpg'
            frame_path = os.path.join(output_dir, frame_filename)
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_paths.append(frame_path)
            timestamps.append(t)
            frame_idx += 1

        t += interval_sec

    cap.release()
    logger.info(f'提取 {len(frame_paths)} 帧')
    return frame_paths, timestamps


def frame_to_base64(image_path):
    """将图片文件转为 base64 编码"""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


# ============================================================
# Claude Vision 分析
# ============================================================

def build_analysis_prompt(note_info):
    """构建给 Claude Vision 的分析 Prompt"""
    title = note_info.get('title', '')
    content = note_info.get('content_text', '')
    comment_keywords = note_info.get('comment_keywords', [])

    prompt = f"""你是一名专业的小红书内容分析师。请分析以下笔记的视频内容和文案，输出结构化分析结果。

笔记标题: {title}
笔记正文: {content[:500] if content else '（无正文）'}
评论热词: {', '.join(comment_keywords[:10]) if comment_keywords else '（无数据）'}

请分析视频帧画面，按以下 JSON 格式输出（不要输出其他内容，只输出 JSON）：

{{
  "content_themes": ["主题1", "主题2", "主题3"],
  "visual_style": ["风格1", "风格2", "风格3"],
  "narrative_pattern": "叙事模式描述",
  "cutting_angle": "内容切入角度",
  "key_selling_points": ["卖点1", "卖点2", "卖点3"],
  "target_audience": "目标受众描述",
  "tone": "语气和风格描述",
  "opening_hook": "前3秒抓人手法",
  "scene_count": 5,
  "visual_elements": ["元素1", "元素2", "元素3"],
  "confidence": 0.8
}}

要求:
- content_themes: 内容主题标签（如 "产品测评", "使用教程", "成分科普", "开箱体验"）
- visual_style: 视觉风格（如 "清新自然", "生活化", "近距离特写", "电影感"）
- narrative_pattern: 叙事结构（如 "问题引入→产品展示→效果对比→购买引导"）
- cutting_angle: 切入点/差异化角度
- key_selling_points: 核心卖点
- target_audience: 目标受众画像
- tone: 语气风格
- opening_hook: 前3秒如何抓住注意力
- scene_count: 大约有多少个场景切换
- visual_elements: 画面中的主要视觉元素
- confidence: 分析置信度 0-1"""

    return prompt


def analyze_with_claude(frame_paths, prompt, config):
    """使用 Claude Vision API 分析视频帧"""
    try:
        from anthropic import Anthropic
    except ImportError:
        logger.error('需要安装 anthropic: pip install anthropic')
        return None

    api_key = os.environ.get(config.get('api_key_env', 'ANTHROPIC_API_KEY'), '')
    if not api_key:
        logger.error(f'未设置 API Key 环境变量: {config.get("api_key_env", "ANTHROPIC_API_KEY")}')
        return None

    client = Anthropic(api_key=api_key)
    model = config.get('model', 'claude-sonnet-4-20250514')
    max_tokens = config.get('max_tokens', 4096)

    # 构建消息内容：帧图片 + 文本 prompt
    content_parts = []
    for fp in frame_paths:
        b64 = frame_to_base64(fp)
        content_parts.append({
            'type': 'image',
            'source': {
                'type': 'base64',
                'media_type': 'image/jpeg',
                'data': b64,
            }
        })

    content_parts.append({
        'type': 'text',
        'text': prompt,
    })

    try:
        logger.info(f'正在调用 Claude Vision API (model={model}, frames={len(frame_paths)})...')
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=config.get('temperature', 0.3),
            messages=[{
                'role': 'user',
                'content': content_parts,
            }],
        )

        response_text = message.content[0].text if message.content else ''
        logger.info(f'Claude 响应: {len(response_text)} 字符')

        # 尝试解析 JSON
        return _extract_json(response_text)

    except Exception as e:
        logger.error(f'Claude API 调用失败: {e}')
        return None


def _extract_json(text):
    """从响应文本中提取 JSON"""
    import re

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从代码块中提取
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找到 JSON 对象
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # 回退：返回原始文本
    logger.warning('无法从响应中提取 JSON，返回原始文本')
    return {'raw_response': text}


def analyze_video(crawled_path, config_path, output_dir, comment_analysis_path=None):
    """
    主分析函数。
    crawled_path: crawled_notes.json
    config_path: llm_config.json
    output_dir: 输出目录
    comment_analysis_path: 评论分析 JSON 路径（可选，用于获取评论热词）
    """
    with open(crawled_path, 'r', encoding='utf-8') as f:
        crawled_data = json.load(f)

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 加载评论热词（如果可用）
    comment_keywords_map = {}
    if comment_analysis_path and os.path.exists(comment_analysis_path):
        try:
            with open(comment_analysis_path, 'r', encoding='utf-8') as f:
                comment_data = json.load(f)
            for note_id, note_info in comment_data.get('per_note', {}).items():
                kws = note_info.get('top_keywords', [])
                comment_keywords_map[note_id] = [kw['word'] for kw in kws]
        except Exception:
            pass

    notes = crawled_data.get('notes', [])
    video_notes = [n for n in notes if n.get('video', {}).get('local_path')]

    if not video_notes:
        logger.info('没有视频笔记需要分析')
        result = {'video_notes': []}
        output_path = os.path.join(output_dir, 'video_analysis.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result

    logger.info(f'发现 {len(video_notes)} 篇视频笔记需要分析')

    result = {'video_notes': []}

    for i, note in enumerate(video_notes):
        note_id = note.get('note_id', f'unknown_{i}')
        title = note.get('title', '')
        video_path = note['video']['local_path']
        note_dir = os.path.join(output_dir, f'video_{note_id}')
        os.makedirs(note_dir, exist_ok=True)

        logger.info(f'\n[{i+1}/{len(video_notes)}] 分析视频: {title or note_id}')

        # 1. 提取帧
        interval = config.get('frame_interval_sec', 3)
        max_frames = config.get('max_frames_per_video', 8)
        max_size = tuple(config.get('frame_max_size', [800, 600]))

        frame_paths, timestamps = extract_frames(
            video_path, note_dir,
            interval_sec=interval,
            max_frames=max_frames,
            max_size=max_size,
        )

        if not frame_paths:
            logger.warning(f'无法提取帧: {video_path}')
            continue

        # 2. 构建笔记信息（含评论热词）
        note_info = {
            'title': title,
            'content_text': note.get('content_text', ''),
            'comment_keywords': comment_keywords_map.get(note_id, []),
        }

        # 3. Claude Vision 分析
        prompt = build_analysis_prompt(note_info)
        llm_result = analyze_with_claude(frame_paths, prompt, config)

        if llm_result is None:
            logger.warning(f'LLM 分析失败: {note_id}')
            continue

        video_result = {
            'note_id': note_id,
            'note_title': title,
            'note_url': note.get('note_url', ''),
            'video_duration_sec': note.get('video', {}).get('duration_sec', 0),
            'frame_analysis': {
                'total_frames_extracted': len(frame_paths),
                'frame_paths': frame_paths,
                'frame_timestamps': timestamps,
                'visual_elements': llm_result.get('visual_elements', []),
                'scene_count': llm_result.get('scene_count', 0),
            },
            'llm_analysis': {
                'content_themes': llm_result.get('content_themes', []),
                'visual_style': llm_result.get('visual_style', []),
                'narrative_pattern': llm_result.get('narrative_pattern', ''),
                'cutting_angle': llm_result.get('cutting_angle', ''),
                'key_selling_points': llm_result.get('key_selling_points', []),
                'target_audience': llm_result.get('target_audience', ''),
                'tone': llm_result.get('tone', ''),
                'opening_hook': llm_result.get('opening_hook', ''),
                'confidence': llm_result.get('confidence', 0),
            },
        }

        result['video_notes'].append(video_result)
        logger.info(f'  主题: {llm_result.get("content_themes", [])}')
        logger.info(f'  切角: {llm_result.get("cutting_angle", "")}')

    # 保存
    output_path = os.path.join(output_dir, 'video_analysis.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f'\n视频分析完成！共分析 {len(result["video_notes"])} 篇')
    logger.info(f'结果已保存: {output_path}')

    return result


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(f'用法: python analyze_video.py <crawled_notes.json> <llm_config.json> <输出目录>')
        print(f'可选: python analyze_video.py <crawled_notes.json> <llm_config.json> <输出目录> <comment_analysis.json>')
        sys.exit(1)

    comment_path = sys.argv[4] if len(sys.argv) > 4 else None
    analyze_video(sys.argv[1], sys.argv[2], sys.argv[3], comment_path)
