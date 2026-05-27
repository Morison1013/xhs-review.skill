# -*- coding: utf-8 -*-
"""
analyze_comments.py — 小红书评论舆情分析

功能:
- 情感分类（正面/负面/中性）
- 子类别标签（种草/质疑/比价/吐槽/求购/成分咨询/使用反馈）
- 热词提取（jieba TF-IDF + n-gram）
- 聚合多笔记的评论数据

用法:
    python analyze_comments.py <crawled_notes.json> <输出JSON路径>
"""
import json
import sys
import os
import re
from collections import defaultdict, Counter

# ============================================================
# 关键词字典 — 用于规则分类
# ============================================================

# 情感正负面关键词
POSITIVE_WORDS = [
    '好用', '回购', '种草', '推荐', '喜欢', '效果不错', '值得', '爱了', '绝了',
    '太棒了', '真的', '好爱', '神仙', '宝藏', '牛', 'yyds', '绝绝子', '太可了',
    '效果好', '有效果', '明显改善', '改善', '很赞', 'nice', '棒', '好用哭',
    '已经回购', '空瓶', '无限回购', '好用到哭', '效果明显', '惊艳', '太爱了',
    '好喜欢', '种草了', '冲', '下单了', '已买', '好用好用', '太喜欢了',
    '超级好用', '效果很好', '满意', '良心产品', '靠谱', '可以闭眼入',
]

NEGATIVE_WORDS = [
    '没用', '坑', '智商税', '太贵', '过敏', '烂脸', '避雷', '不行', '差评',
    '失望', '后悔', '垃圾', '骗人', '夸大', '虚假', '不好用', '没用过',
    '刺痛', '泛红', '起痘', '爆痘', '闷痘', '搓泥', '没效果', '鸡肋',
    '别买', '快跑', '别被坑了', '踩雷', '拉胯', '翻车', '不建议', '难用',
    '没感觉', '一般般', '就那样', '不推荐', '拔草',
]

# 子类别关键词
SUB_CATEGORY_KEYWORDS = {
    '种草': [
        '想买', '种草', '已下单', '冲', '加购', '购物车', '求链接', '求淘口令',
        '哪里买', '链接', '怎么买', '蹲', '等优惠', '好心动', '被种草', '想要',
        '码住', '收藏了', '蹲一个', '求代购', '已加购', '坐等', '什么时候买',
        '想买想买', '必须买', '下单了', '已经下单',
    ],
    '质疑': [
        '真的假的', '智商税', '广告吧', '夸大', '真的吗', '有那么好吗',
        '是不是广告', '恰饭', '推广', '收钱了', '真的有用吗', '可信吗',
        '确定', '靠谱吗', '有依据吗', '成分安全吗', '真的还是', '有人用过吗',
    ],
    '比价': [
        '多少钱', '贵', '便宜', '平替', '有没有优惠', '打折', '活动',
        '优惠券', '满减', '好价', '价格', '优惠', '便宜点', '值不值',
        '划算', '性价比', '贵不贵', '价格怎么样', '活动价', '双十一',
        '大促', '有没有券', '领券', '折扣', '降价',
    ],
    '吐槽': [
        '难用', '失望', '后悔', '避雷', '垃圾', '太差', '太差了', '浪费时间',
        '被骗', '踩雷', '翻车', '踩坑', '拉胯', '无语', '服了', '绝了负面的',
        '太差劲', '什么鬼', '避雷避雷', '千万别买', '别买', '快跑',
    ],
    '求购': [
        '哪里买', '链接', '怎么买', '淘口令', '求代', '代购', '哪里有卖',
        '求链接', '求渠道', '正品在哪买', '靠谱渠道', '官方店', '旗舰店',
        '淘宝', '京东', '拼多多', '天猫', '有没有', '有卖吗',
    ],
    '成分咨询': [
        '成分', '安全', '孕妇', '敏感肌', '激素', '防腐剂', '酒精', '香精',
        '烟酰胺', '视黄醇', '水杨酸', '果酸', 'vc', '透明质酸', '神经酰胺',
        '耐受', '建立耐受', '浓度', 'pH值', '刺激性', '温和', '孕妇能用吗',
        '哺乳期', '敏感', '油皮', '干皮', '混油', '痘痘肌', '烂脸',
    ],
    '使用反馈': [
        '用了', '效果', '回购', '空瓶', '用完', '用了一个月', '用了两周',
        '坚持用', '用了一段时间', '用下来', '使用感受', '使用体验',
        '已经用了', '用了几次', '第二次买', '第三瓶', '回购了', '一直用',
        '用着', '使用感', '用后', '用了一周',
    ],
}

# jieba 停用词
STOP_WORDS = {
    '的', '了', '是', '我', '你', '他', '她', '它', '在', '有', '这', '那',
    '一个', '什么', '怎么', '为什么', '就', '都', '很', '太', '最', '更',
    '也', '还', '不', '没', '要', '会', '能', '可以', '吧', '啊', '呢',
    '吗', '哦', '嗯', '哈', '哎', '哇', '的', '和', '与', '及', '等',
    '我', '你', '他', '她', '我们', '你们', '他们', '这个', '那个',
    '真的', '真的吗', '一下', '一下下', '真的真的',
    '的', '了', '是', '在', '有', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
    '看', '好', '自己', '这',
}


def classify_sentiment(text):
    """
    判断单条评论的情感。
    返回 (sentiment, sub_category)
    sentiment: positive / negative / neutral
    sub_category: 种草 / 质疑 / 比价 / 吐槽 / 求购 / 成分咨询 / 使用反馈 / 其他
    """
    # 子类别判断（优先级：命中关键词数最多的）
    category_scores = {}
    for cat, keywords in SUB_CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            category_scores[cat] = score

    sub_category = max(category_scores, key=category_scores.get) if category_scores else '其他'

    # 情感判断
    pos_count = sum(1 for w in POSITIVE_WORDS if w in text)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in text)

    if pos_count > neg_count:
        sentiment = 'positive'
    elif neg_count > pos_count:
        sentiment = 'negative'
    else:
        # 中性或无法判断
        sentiment = 'neutral'

    return sentiment, sub_category


def extract_keywords(texts, top_k=20):
    """
    使用 jieba 提取 TF-IDF 关键词 + n-gram 短语。
    texts: 评论文本列表
    """
    try:
        import jieba.analyse
    except ImportError:
        # 回退方案：简单分词统计
        return _simple_keyword_fallback(texts, top_k)

    all_text = ' '.join(texts)

    # TF-IDF 关键词
    keywords = jieba.analyse.extract_tags(all_text, topK=top_k * 2, withWeight=True)

    # 过滤停用词和太短/太长的词
    filtered = []
    for word, weight in keywords:
        if word in STOP_WORDS or len(word) < 2 or len(word) > 6:
            continue
        filtered.append((word, weight))

    # 统计词频
    word_freq = Counter()
    for word, _ in filtered:
        word_freq[word] = texts.count(word) if isinstance(texts, list) else 0

    # 对于 jieba extract_tags 返回的词，统计真实出现次数
    text_joined = ''.join(texts)
    for word, weight in filtered:
        word_freq[word] = text_joined.count(word)

    # 按 TF-IDF 权重排序，取 top_k
    filtered.sort(key=lambda x: x[1], reverse=True)
    top_keywords = []
    for word, weight in filtered[:top_k]:
        top_keywords.append({
            'word': word,
            'weight': round(weight, 4),
            'count': word_freq.get(word, 0),
        })

    # N-gram (2-3 字短语)
    ngrams = _extract_ngrams(texts, top_k)

    return {
        'tfidf_top': top_keywords,
        'ngram_top': ngrams,
    }


def _extract_ngrams(texts, top_k=10):
    """提取 2-3 词组合的高频短语"""
    try:
        import jieba
    except ImportError:
        return []

    all_phrases = []
    for text in texts:
        words = [w for w in jieba.lcut(text) if len(w) >= 2 and w not in STOP_WORDS]
        # 2-gram
        for i in range(len(words) - 1):
            phrase = words[i] + words[i + 1]
            if 3 <= len(phrase) <= 8:
                all_phrases.append(phrase)
        # 3-gram
        for i in range(len(words) - 2):
            phrase = words[i] + words[i + 1] + words[i + 2]
            if 4 <= len(phrase) <= 10:
                all_phrases.append(phrase)

    phrase_counter = Counter(all_phrases)
    return [
        {'phrase': phrase, 'count': count}
        for phrase, count in phrase_counter.most_common(top_k)
    ]


def _simple_keyword_fallback(texts, top_k):
    """无 jieba 时的回退方案"""
    text_joined = ''.join(texts)
    # 用正则提取中文词（简单方案）
    words = re.findall(r'[一-龥]{2,4}', text_joined)
    counter = Counter(w for w in words if w not in STOP_WORDS)
    return {
        'tfidf_top': [
            {'word': w, 'weight': round(c / len(texts), 4), 'count': c}
            for w, c in counter.most_common(top_k)
        ],
        'ngram_top': [],
    }


def analyze_comments(crawled_path, output_path):
    """
    主分析函数。
    crawled_path: crawled_notes.json 路径
    output_path: 输出 comment_analysis.json 路径
    """
    with open(crawled_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    notes = data.get('notes', [])
    all_comments = []
    per_note = {}

    print(f'共 {len(notes)} 篇笔记')

    for note in notes:
        comments = note.get('comments', [])
        note_id = note.get('note_id', 'unknown')
        title = note.get('title', '')[:50]

        if not comments:
            continue

        # 单笔记分析
        note_sentiments = Counter()
        note_categories = Counter()
        note_texts = []

        for c in comments:
            text = c.get('text', '').strip()
            if not text:
                continue

            sentiment, sub_category = classify_sentiment(text)
            c['sentiment'] = sentiment
            c['sub_category'] = sub_category

            note_sentiments[sentiment] += 1
            note_categories[sub_category] += 1
            note_texts.append(text)
            all_comments.append(c)

        total = sum(note_sentiments.values())
        per_note[note_id] = {
            'title': title,
            'comment_count': total,
            'sentiment': {
                'positive': round(note_sentiments['positive'] / total, 4) if total > 0 else 0,
                'negative': round(note_sentiments['negative'] / total, 4) if total > 0 else 0,
                'neutral': round(note_sentiments['neutral'] / total, 4) if total > 0 else 0,
            },
            'top_keywords': extract_keywords(note_texts, top_k=10)['tfidf_top'][:5],
        }

    # 全局聚合
    total_comments = len(all_comments)
    if total_comments == 0:
        print('警告: 没有评论数据可分析')
        result = {
            'overall': {'total_comments': 0, 'total_notes_analyzed': 0},
            'sentiment_distribution': {},
            'sub_categories': {},
            'keywords': {'tfidf_top': [], 'ngram_top': []},
            'representative_comments': {},
            'per_note': {},
        }
    else:
        # 情感分布
        sentiment_counts = Counter(c['sentiment'] for c in all_comments)
        sentiment_dist = {
            'positive': {
                'count': sentiment_counts['positive'],
                'pct': round(sentiment_counts['positive'] / total_comments * 100, 1),
            },
            'negative': {
                'count': sentiment_counts['negative'],
                'pct': round(sentiment_counts['negative'] / total_comments * 100, 1),
            },
            'neutral': {
                'count': sentiment_counts['neutral'],
                'pct': round(sentiment_counts['neutral'] / total_comments * 100, 1),
            },
        }

        # 子类别分布
        cat_counts = Counter(c['sub_category'] for c in all_comments)
        sub_categories = {}
        for cat, count in cat_counts.most_common():
            sub_categories[cat] = {
                'count': count,
                'pct': round(count / total_comments * 100, 1),
            }

        # 热词
        all_texts = [c['text'] for c in all_comments]
        keywords = extract_keywords(all_texts, top_k=20)

        # 代表性评论
        representative = _pick_representative(all_comments)

        result = {
            'overall': {
                'total_comments': total_comments,
                'total_notes_analyzed': len([n for n in notes if n.get('comments')]),
                'avg_comments_per_note': round(total_comments / len([n for n in notes if n.get('comments')]), 1) if notes else 0,
            },
            'sentiment_distribution': sentiment_dist,
            'sub_categories': sub_categories,
            'keywords': keywords,
            'representative_comments': representative,
            'per_note': per_note,
        }

    # 保存
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    # 打印摘要
    print('\n=== 评论舆情分析摘要 ===')
    print(f'总评论数: {result["overall"]["total_comments"]}')
    print(f'笔记数: {result["overall"]["total_notes_analyzed"]}')

    if 'sentiment_distribution' in result:
        sd = result['sentiment_distribution']
        print(f'情感分布: 正面 {sd["positive"]["pct"]:.1f}% | 负面 {sd["negative"]["pct"]:.1f}% | 中性 {sd["neutral"]["pct"]:.1f}%')

    if 'sub_categories' in result:
        print('子类别 Top5:')
        for cat, d in list(result['sub_categories'].items())[:5]:
            print(f'  {cat}: {d["count"]}条 ({d["pct"]:.1f}%)')

    if 'keywords' in result and result['keywords']['tfidf_top']:
        print('TF-IDF 热词 Top5:')
        for kw in result['keywords']['tfidf_top'][:5]:
            print(f'  {kw["word"]} (权重 {kw["weight"]:.3f}, {kw["count"]}次)')

    print(f'\n结果已保存: {output_path}')
    return result


def _pick_representative(comments, max_per_category=3):
    """挑选每类情感的代表性评论（按点赞数排序）"""
    representative = {
        'positive': [],
        'negative': [],
        'neutral': [],
        'questions': [],
    }

    question_words = ['吗', '呢', '？', '?', '怎么', '什么', '哪里', '如何', '能不能']

    for cat in ['positive', 'negative', 'neutral']:
        cat_comments = [c for c in comments if c['sentiment'] == cat]
        cat_comments.sort(key=lambda x: x.get('likes', 0), reverse=True)
        representative[cat] = [
            {
                'text': c['text'][:100],
                'likes': c.get('likes', 0),
                'note_id': c.get('_note_id', ''),
                'sub_category': c.get('sub_category', ''),
            }
            for c in cat_comments[:max_per_category]
        ]

    # 问题类评论
    question_comments = [
        c for c in comments
        if any(w in c['text'] for w in question_words)
    ]
    question_comments.sort(key=lambda x: x.get('likes', 0), reverse=True)
    representative['questions'] = [
        {
            'text': c['text'][:100],
            'likes': c.get('likes', 0),
            'note_id': c.get('_note_id', ''),
        }
        for c in question_comments[:max_per_category]
    ]

    return representative


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f'用法: python analyze_comments.py <crawled_notes.json> <输出JSON路径>')
        sys.exit(1)
    analyze_comments(sys.argv[1], sys.argv[2])
