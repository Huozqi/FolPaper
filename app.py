from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for
import concurrent.futures
import csv
import io
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from database import DatabaseManager
from fetcher import LiteratureFetcher, extract_doi
from openalex_service import OpenAlexService
from translator import Translator


# 过滤掉频繁的轮询日志，防止终端刷屏让用户误以为任务一直在运行
log = logging.getLogger('werkzeug')


class NoHealthFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return 'api/task_status' not in msg and 'api/check_translation_status' not in msg


log.addFilter(NoHealthFilter())

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

app.secret_key = os.environ.get('FOLPAPER_SECRET', os.urandom(32).hex())

# 全局任务状态字典，用于跟踪后台抓取进度
task_status = {
    'is_running': False,
    'message': '',
    'progress': 0,
    'total': 0,
    'details': [],
    'errors': []
}
task_status_lock = threading.Lock()

# 补源状态追踪：记录哪些期刊因安全验证被拦截，用于判断是否继续补源
SUPPLEMENT_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'supplement_state.json')
_supplement_state_lock = threading.Lock()

def _load_supplement_state():
    """加载补源追踪状态。返回 {rss_url: {last_status, last_check, consecutive_blocks}}"""
    try:
        if os.path.exists(SUPPLEMENT_STATE_FILE):
            with open(SUPPLEMENT_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_supplement_state(state):
    with open(SUPPLEMENT_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def _update_supplement_tracking(sub_value, is_blocked):
    """更新单个期刊的补源追踪状态。is_blocked=True 表示本次被安全拦截。"""
    with _supplement_state_lock:
        state = _load_supplement_state()
        now = datetime.now().isoformat()
        entry = state.get(sub_value, {})
        if is_blocked:
            entry['last_status'] = 'blocked'
            entry['last_check'] = now
            entry['consecutive_blocks'] = entry.get('consecutive_blocks', 0) + 1
        else:
            # RSS 恢复正常，清除追踪记录
            if entry.get('last_status') == 'blocked':
                state.pop(sub_value, None)
                _save_supplement_state(state)
                return 'restored'
            entry['last_status'] = 'ok'
            entry['last_check'] = now
            entry['consecutive_blocks'] = 0
        state[sub_value] = entry
        _save_supplement_state(state)
        return entry['last_status']

def _was_previously_blocked(sub_value):
    """检查该期刊上次是否被安全拦截。"""
    state = _load_supplement_state()
    entry = state.get(sub_value, {})
    return entry.get('last_status') == 'blocked'

# 初始化全局后台组件
db = DatabaseManager()
# 重置可能因意外中断导致卡在 translating 状态的文献为 error，支持断点恢复
db.reset_translating_status()
fetcher = LiteratureFetcher(db)
translator = Translator(db)

ONE_DAY_ARXIV_CATEGORIES = ['cs.AI', 'cs.LG', 'stat.ML']

openalex_sessions = {}
download_tasks = {}
FETCH_RESULT_TTL_SECONDS = 60

# 加载内置期刊库
BUILTIN_JOURNALS = []
_BUILTIN_JOURNALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'builtin_journals.json')
if os.path.exists(_BUILTIN_JOURNALS_FILE):
    try:
        with open(_BUILTIN_JOURNALS_FILE, 'r', encoding='utf-8') as f:
            BUILTIN_JOURNALS = json.load(f)
    except Exception as e:
        print(f'Failed to load builtin journals: {e}')

TOP_CONFERENCE_GROUPS = {
    'AI/ML': [
        {'key': 'neurips', 'name': 'NeurIPS', 'query': 'Advances in Neural Information Processing Systems'},
        {'key': 'icml', 'name': 'ICML', 'query': 'International Conference on Machine Learning'},
        {'key': 'iclr', 'name': 'ICLR', 'query': 'International Conference on Learning Representations'},
        {'key': 'aaai', 'name': 'AAAI', 'query': 'AAAI Conference on Artificial Intelligence'},
        {'key': 'ijcai', 'name': 'IJCAI', 'query': 'International Joint Conference on Artificial Intelligence'},
    ],
    'CV': [
        {'key': 'cvpr', 'name': 'CVPR', 'query': 'IEEE/CVF Conference on Computer Vision and Pattern Recognition'},
        {'key': 'iccv', 'name': 'ICCV', 'query': 'International Conference on Computer Vision'},
        {'key': 'eccv', 'name': 'ECCV', 'query': 'European Conference on Computer Vision'},
    ],
    'NLP': [
        {'key': 'acl', 'name': 'ACL', 'query': 'Annual Meeting of the Association for Computational Linguistics'},
        {'key': 'emnlp', 'name': 'EMNLP', 'query': 'Conference on Empirical Methods in Natural Language Processing'},
        {'key': 'naacl', 'name': 'NAACL', 'query': 'North American Chapter of the Association for Computational Linguistics'},
    ],
    'Data/Web/IR': [
        {'key': 'kdd', 'name': 'KDD', 'query': 'ACM SIGKDD Conference on Knowledge Discovery and Data Mining'},
        {'key': 'www', 'name': 'WWW', 'query': 'The Web Conference'},
        {'key': 'sigir', 'name': 'SIGIR', 'query': 'International ACM SIGIR Conference on Research and Development in Information Retrieval'},
    ],
}
TOP_CONFERENCES = [conf for group in TOP_CONFERENCE_GROUPS.values() for conf in group]

def format_date(date_str):
    if not date_str: return "未知日期"
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y.%m.%d")
    except Exception:
        pass
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%Y.%m.%d")
    except Exception:
        pass
    m = re.search(r'\d{4}-\d{2}-\d{2}', date_str)
    if m:
        return m.group(0).replace('-', '.')
    return date_str[:10]

def remove_html_tags(text):
    if not text: return ""
    # 去除以 <> 包裹的任何 HTML 标签及不相干字符
    clean_text = re.sub(r'<[^>]+>', '', text)
    # 替换多个连续空格为一个空格，并去除两端空白
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    return clean_text

def format_cleanup_details(details, include_retention=False):
    if not details:
        return "0 篇"
    parts = []
    for item in details[:5]:
        source_name = item.get('source_name') or '未标记来源'
        count = item.get('count', 0)
        if include_retention:
            retention_days = item.get('retention_days')
            parts.append(f"{source_name} {count} 篇(保留 {retention_days} 天)")
        else:
            parts.append(f"{source_name} {count} 篇")
    if len(details) > 5:
        parts.append(f"其余 {len(details) - 5} 个来源")
    return "；".join(parts)

def summarize_fetch_result(result):
    supplements = result.get('supplements') or []
    supplement_text = ''
    if supplements:
        parts = [
            f"{item['source']} {item['inserted']}/{item['fetched']} 篇"
            for item in supplements
        ]
        supplement_text = f"；补源 {'，'.join(parts)}"
    security_text = ''
    if result.get('security_blocked'):
        security_text = '；[安全拦截]'
    error_text = ''
    if result.get('errors'):
        error_text = f"；错误 {len(result['errors'])} 条"
    return (
        f"{result.get('source')}: RSS/API 读取 {result.get('fetched', 0)} 篇，"
        f"新增 {result.get('inserted', 0)} 篇，重复 {result.get('duplicates', 0)} 篇"
        f"{security_text}{supplement_text}{error_text}"
    )

def update_task_status(**kwargs):
    with task_status_lock:
        if 'progress' not in kwargs:
            task_status['progress'] = task_status.get('progress', 0) + 1
        task_status.update(kwargs)
        return dict(task_status)

def resolve_subscription_info(sub_type, sub_value, source_name='', openalex_query=''):
    sub = {
        'sub_type': sub_type,
        'sub_value': sub_value,
        'source_name': source_name,
        'openalex_query': openalex_query,
    }
    metadata = fetcher._resolve_journal_metadata(sub) if sub_type == 'rss' else None
    resolved = {
        'source_name': source_name,
        'openalex_query': openalex_query,
        'issn': '',
        'doi_prefix': '',
        'openalex_source_id': '',
        'matched_by': ''
    }
    if metadata:
        resolved.update({
            'source_name': source_name or metadata.get('name', ''),
            'openalex_query': openalex_query or metadata.get('openalex_query', '') or metadata.get('full_name', '') or metadata.get('name', ''),
            'issn': metadata.get('issn', ''),
            'doi_prefix': metadata.get('doi_prefix', ''),
            'openalex_source_id': metadata.get('openalex_source_id', ''),
            'matched_by': 'journal_library'
        })
        return resolved

    query = (openalex_query or source_name or '').strip()
    if query and sub_type in ['rss', 'openalex']:
        try:
            service = OpenAlexService(api_key=db.get_config('openalex_api_key', ''))
            matched_sources = service.get_source_id(query)
            if matched_sources:
                resolved.update({
                    'source_name': source_name or matched_sources[0]['display_name'],
                    'openalex_query': openalex_query or matched_sources[0]['display_name'],
                    'openalex_source_id': matched_sources[0]['id'],
                    'matched_by': 'openalex'
                })
        except Exception as e:
            print(f"OpenAlex metadata lookup failed for {query}: {e}")
    return resolved

app.jinja_env.filters['format_date'] = format_date
app.jinja_env.filters['remove_html_tags'] = remove_html_tags

# 注入一个全局变量函数用于获取所有订阅以便渲染侧边栏树形菜单
@app.context_processor
def inject_sidebar_data():
    # 直接从 subscriptions 表获取用户订阅的所有期刊名称
    subs = db.get_subscriptions()
    all_sources = [sub['source_name'] for sub in subs if sub.get('source_name')]
    
    # 获取 pending 的所有不重复 source
    pending_sources = db.get_unique_sources_by_status('pending')
    
    # 获取各来源的未读数
    unread_counts = db.get_unread_counts_by_source()
    total_unread = sum(unread_counts.values())
    
    # 两者合并去重，以防有文章存在但订阅已被删除的情况
    display_sources = list(set(all_sources + pending_sources))
    display_sources.sort()
    
    return dict(display_sources=display_sources, unread_counts=unread_counts, total_unread=total_unread)

def process_articles(articles):
    for a in articles:
        a['author_list'] = [x.strip() for x in a.get('authors', '').split(',')] if a.get('authors') else ["未知作者"]

        doi = a.get('doi') or extract_doi(a.get('link'), a.get('article_id'), a.get('summary'))
        a['doi'] = doi
    return articles

@app.route('/')
def index():
    # 首页展示研究情报工作台
    return render_template('home.html')

@app.route('/library')
def library():
    # 我的文库 (状态为 saved 的文献)
    sort_by = request.args.get('sort_by', 'id_desc')
    source_filter = request.args.get('source', '')
    page = request.args.get('page', 1, type=int)
    page_size = 20

    sources = db.get_unique_sources_by_status('saved')

    articles, total_articles, total_pages, current_page = db.get_articles_by_status_paginated(
        'saved',
        source=source_filter,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )
    articles = process_articles(articles)
    return render_template(
        'index.html',
        articles=articles,
        view_type='saved',
        sources=sources,
        current_source=source_filter,
        sort_by=sort_by,
        current_page=current_page,
        total_pages=total_pages,
        total_articles=total_articles,
        page_size=page_size
    )

@app.route('/archive')
def archive():
    # 历史归档界面路由
    source_filter = request.args.get('source', '')
    page = request.args.get('page', 1, type=int)
    page_size = 50
    sources = db.get_unique_archive_sources()

    # 归档页改为分页读取，避免历史数据持续累积后一次性加载过多内容
    archives, total_archives, total_pages, current_page = db.get_archive_articles_paginated(
        source=source_filter,
        page=page,
        page_size=page_size
    )
    
    return render_template(
        'archive.html',
        archives=archives,
        sources=sources,
        current_source=source_filter,
        current_page=current_page,
        total_pages=total_pages,
        total_archives=total_archives,
        page_size=page_size
    )

@app.route('/pubmed', methods=['GET', 'POST'])
def pubmed_page():
    results = []
    query = ""
    retmax = 100
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        retmax = request.form.get('retmax', 100, type=int)
        if query:
            from pubmed_service import PubMedService
            service = PubMedService()
            # 解除限制，使用表单提交的 retmax，并设置按相关度排序
            results = service.search(query, retmax=retmax, sort="relevance")
            
    return render_template('pubmed.html', results=results, query=query, retmax=retmax)

@app.route('/api/pubmed/save', methods=['POST'])
def pubmed_save():
    article_id = request.form.get('article_id')
    title = request.form.get('title')
    authors = request.form.get('authors')
    summary = request.form.get('summary')
    link = request.form.get('link')
    published = request.form.get('published')
    doi = request.form.get('doi')
    
    article_data = {
        'article_id': article_id,
        'title': title,
        'authors': authors,
        'summary': summary,
        'link': link,
        'published': published,
        'source': 'PubMed Manual',
        'doi': doi,
        'status': 'saved'
    }
    
    if db.add_article(article_data):
        # 强制更新为 saved，因为 add_article 如果存在的话可能需要特殊处理，但这里 article_id 是唯一的
        # 为了确保其进入我的文库，我们可以执行一个 UPDATE
        db.update_article_status_by_article_id(article_id, 'saved')
        return jsonify({'success': True, 'message': '已保存到我的文库'})
    else:
        # 如果已经存在（比如因为之前通过订阅拉取过），更新状态即可
        db.update_article_status_by_article_id(article_id, 'saved')
        return jsonify({'success': True, 'message': '已保存到我的文库 (已存在)'})

@app.route('/api/pubmed/generate_query', methods=['POST'])
def pubmed_generate_query():
    user_input = request.form.get('user_input', '').strip()
    mode = request.form.get('mode', 'natural').strip()
    
    if not user_input:
        return jsonify({'success': False, 'message': '输入内容不能为空'})
        
    from translator import Translator
    t = Translator(db)
    
    if mode == 'keywords':
        prompt = f"请作为一位专业的 PubMed 检索专家，根据用户提供的一组以分号分隔的关键词，帮用户生成一个精准收束的 PubMed 检索式。\n\n" \
                 f"用户的关键词：{user_input}\n\n" \
                 f"要求：\n" \
                 f"1. 严格基于用户提供的关键词进行构建，不要随意添加大量外延同义词，以确保检索结果聚焦且精确。\n" \
                 f"2. 各个关键词组之间默认使用 AND 逻辑连接，如果某个词组内部包含明确的同义词可用 OR。\n" \
                 f"3. 优先使用 [Title/Abstract] 或合适的 MeSH 词汇标签进行限制，避免在全字段搜索导致结果过于泛滥。\n" \
                 f"4. 正确使用括号 ( ) 确保逻辑优先级正确。\n" \
                 f"5. 最终只需输出生成的检索式字符串本身，**不要有任何其他解释、前缀或代码块格式**。\n" \
                 f"6. 确保生成的检索式可以直接复制到 PubMed 的搜索框中使用。"
    else:
        prompt = f"请作为一位专业的 PubMed 检索专家，根据用户提供的一段自然语言描述，帮用户生成一个最合适、最准确的 PubMed 检索式。\n\n" \
                 f"用户的描述：{user_input}\n\n" \
                 f"要求：\n" \
                 f"1. 充分理解用户的意图，提取核心关键词。请注意**控制检索范围**，不要过度扩展同义词，以避免返回过多不相关的文献。\n" \
                 f"2. 优先使用 [Title/Abstract] 标签进行检索，以提高文献的相关性。\n" \
                 f"3. 正确使用布尔逻辑运算符 AND, OR, NOT，并使用括号 ( ) 确保逻辑优先级正确。\n" \
                 f"4. 最终只需输出生成的检索式字符串本身，**不要有任何其他解释、前缀或代码块格式**。\n" \
                 f"5. 确保生成的检索式可以直接复制到 PubMed 的搜索框中使用。"
             
    try:
        generated_query = t.call_llm(prompt, "你是一个专业的 PubMed 检索专家。只输出最终的检索式。", temperature=0.2, task='survey').strip()
        
        # 移除可能的 markdown 代码块标记
        if generated_query.startswith("```"):
            lines = generated_query.split('\n')
            if len(lines) > 1:
                # 移除第一行 (比如 ```pubmed) 和最后一行 (```)
                generated_query = '\n'.join(lines[1:-1]).strip()
                if generated_query.endswith("```"):
                    generated_query = generated_query[:-3].strip()
        
        return jsonify({'success': True, 'query': generated_query})
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成检索式失败: {str(e)}'})

@app.route('/api/pubmed/survey', methods=['POST'])
def pubmed_survey():
    query = request.form.get('query', '').strip()
    if not query:
        return jsonify({'success': False, 'message': '搜索词不能为空'})
        
    from pubmed_service import PubMedService
    service = PubMedService()
    # 扩大背景调研的基础样本池，一次性拉取所有匹配的文献（这里设置上限为 500 以防止极端超大数据量导致请求超时，绝大多数检索已经足够覆盖）
    results = service.search(query, retmax=500, sort="relevance")
    if not results:
        return jsonify({'success': False, 'message': '未找到相关文献，无法生成调研'})
        
    from translator import Translator
    t = Translator(db)
    
    # 1. 并发筛选相关性
    def check_relevance(article):
        # 如果摘要为空，可能无法判断，这里仍然传给大模型看看标题
        content = f"标题: {article['title']}\n摘要: {article['summary']}"
        prompt = f"请判断以下文献是否与查询主题“{query}”密切相关。请仅回复“是”或“否”。\n\n{content}"
        try:
            # 使用较小的 temperature 以获得确定性回答
            ans = t.call_llm(prompt, "你是一个严格的学术文献筛选助手。", temperature=0.1, task='recommend').strip()
            if ans.startswith("是"):
                return article
        except Exception as e:
            print(f"Relevance check failed for {article['article_id']}: {e}")
        return None

    relevant_results = []
    # 使用线程池并发对抓取到的每条文献进行相关性判断
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_relevance, r) for r in results]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                relevant_results.append(res)
                
    if not relevant_results:
        return jsonify({'success': False, 'message': '经过 AI 筛选后，未发现高度相关的文献，无法生成调研。'})
        
    # 2. 构建背景调研 Prompt (基于筛选后的文献)
    abstracts_text = ""
    for idx, r in enumerate(relevant_results):
        abstracts_text += f"[{idx+1}] Title: {r['title']}\nAbstract: {r['summary']}\n\n"
        
    prompt = f"请作为一位资深化学/生物学领域专家，基于以下 {len(relevant_results)} 篇最新/最相关的 PubMed 文献摘要，为我撰写一份关于“{query}”的背景调研报告。\n\n" \
             f"要求：\n" \
             f"1. 报告正文必须详实且有深度，分为多个小节详细论述该领域的研究现状、主要方法、具体应用场景及代表性成果。\n" \
             f"2. 深入剖析目前的学术共识，以及存在的争议、局限性或问题，避免泛泛而谈。\n" \
             f"3. 语言专业流畅，使用中文，确保正文篇幅充足，不要让参考文献列表显得比正文还长。\n" \
             f"4. 语言风格限制：禁止使用以下词汇（关键、核心、洞察、痛点、瓶颈、障碍、系统性、全栈、鸿沟、生态）；不得采用\"不是...而是...\"的句式结构进行表述。\n" \
             f"5. 在重要论述后必须使用 [1], [2] 标注引用的文献。\n" \
             f"6. 报告末尾必须单列“参考文献”章节，按顺序完整列出报告中引用的所有文献的标题。\n\n" \
             f"文献列表：\n{abstracts_text}"
             
    try:
        # 这里复用 Translator 的模型调用功能
        survey_result = t.call_llm(prompt, "你是一个专业的医学文献分析助手。", task='survey')
        
        # 在报告前面追加筛选信息，提升用户体验
        final_report = f"<div class='mb-4 p-3 bg-purple-100/50 rounded-lg text-sm text-purple-800 border border-purple-200'><strong>AI 筛选统计：</strong> 初始检索获得 {len(results)} 篇文献，经过 AI 逐条并发鉴别，确认 <strong>{len(relevant_results)}</strong> 篇高度相关文献参与最终调研总结。</div>\n\n" + survey_result
        
        # 提取筛选出的文献元数据供前端下载
        articles_data = []
        for r in relevant_results:
            articles_data.append({
                'title': r.get('title', ''),
                'authors': r.get('authors', ''),
                'published': r.get('published', ''),
                'link': r.get('link', ''),
                'doi': r.get('doi', ''),
                'summary': r.get('summary', '')
            })
        
        return jsonify({'success': True, 'survey': final_report, 'articles': articles_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成调研报告失败: {str(e)}'})

@app.route('/recommend')
def recommend_page():
    # 获取所有来源列表供下拉筛选
    sources = db.get_unique_sources()
    return render_template('recommend.html', sources=sources)

@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    criteria = request.form.get('criteria', '').strip()
    sources = request.form.getlist('source')
    read_status = request.form.get('read_status', 'unread')
    analysis_mode = request.form.get('analysis_mode', 'global')
    date_start = request.form.get('date_start', '').strip()
    date_end = request.form.get('date_end', '').strip()

    file = request.files.get('wos_file')
    
    if not criteria:
        return jsonify({'success': False, 'message': '请输入您的筛选要求'})
        
    is_wos_file = False
    articles = []
    
    if file and file.filename:
        is_wos_file = True
        try:
            import pandas as pd
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.filename.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
            else:
                return jsonify({'success': False, 'message': '仅支持 .xls, .xlsx 或 .csv 格式的文件'})
            
            required_cols = ['Article Title', 'Abstract', 'DOI']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                return jsonify({'success': False, 'message': f'上传的文件缺少必要的列: {", ".join(missing_cols)}'})
            
            # 仅保留这三列以减少内存/token开销
            df = df[required_cols]
            df = df.dropna(subset=['Article Title', 'Abstract'])
            
            for idx, row in df.iterrows():
                articles.append({
                    'id': f"WOS_{idx}",
                    'article_id': f"WOS_{idx}",
                    'title': str(row['Article Title']).strip(),
                    'summary': str(row['Abstract']).strip(),
                    'doi': str(row['DOI']).strip() if pd.notna(row['DOI']) else "",
                    'authors': "WOS 导出文献",
                    'source': "WOS Upload",
                    'published': "",
                    'status': 'pending',
                    'is_read': 0,
                    'trans_status': 'none',
                    'translated_title': '',
                    'translated_summary': ''
                })
                
            if not articles:
                return jsonify({'success': False, 'message': '上传的文件中没有有效的文献条目'})
                
        except Exception as e:
            return jsonify({'success': False, 'message': f'解析文件失败: {str(e)}'})
    else:
        # 过滤掉空字符串（代表“所有期刊”）
        sources = [s for s in sources if s.strip()]
        articles = db.get_articles_for_recommendation(sources=sources, read_status=read_status)
        if date_start or date_end:
            articles = [a for a in articles if
                (not date_start or (a.get('published','') or '')[:10] >= date_start) and
                (not date_end or (a.get('published','') or '')[:10] <= date_end)]
        if not articles:
            return jsonify({'success': False, 'message': '当前筛选条件下没有任何文献可供推荐'})
        
    from recommender import Recommender
    recommender = Recommender(db)
    
    # 根据前端选择的模式切换推荐策略，结果页面仍然复用原有卡片展示
    recommended_ids = recommender.get_recommendations(articles, criteria, mode=analysis_mode)
    if not recommended_ids:
        return jsonify({'success': True, 'message': '没有找到符合要求的文献', 'html': '<div class="py-12 text-center text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-200">没有找到符合要求的文献，请尝试调整筛选条件。</div>'})
        
    if is_wos_file:
        recommended_articles = [a for a in articles if a['article_id'] in recommended_ids]
    else:
        recommended_articles = db.get_articles_by_ids(recommended_ids)
        
    recommended_articles = process_articles(recommended_articles)
    total_found = len(recommended_articles)

    # ── 分类：将推荐结果按 criteria 相关类别分组 ──
    categories = {}
    if total_found > 2:
        try:
            categories = recommender.categorize_articles(recommended_articles, criteria)
        except Exception as e:
            print(f"推荐结果分类失败: {e}")

    # 渲染文献卡片
    if categories and len(categories) > 1:
        import html as _html
        html_parts = []
        all_cat_ids = set()
        for cat_name, cat_articles in categories.items():
            for a in cat_articles:
                all_cat_ids.add(a['id'])
            cat_html = render_template('components/article_cards.html',
                                       articles=cat_articles, view_type='pending', is_wos_file=is_wos_file)
            html_parts.append(f'''<div class="category-group mb-6 bg-white rounded-2xl border border-purple-100 overflow-hidden shadow-sm">
<div class="category-header flex items-center gap-3 px-5 py-3.5 bg-gradient-to-r from-purple-50 to-blue-50 cursor-pointer select-none" onclick="toggleCategory(this)">
<svg class="w-5 h-5 text-purple-400 category-chevron transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
<span class="font-bold text-gray-800 text-base">{_html.escape(cat_name)}</span>
<span class="ml-auto px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 text-purple-700">{len(cat_articles)} 篇</span>
</div>
<div class="category-body px-4 pb-4 pt-1 space-y-3">{cat_html}</div>
</div>''')
        # 未归类的文章
        uncategorized = [a for a in recommended_articles if a['id'] not in all_cat_ids]
        if uncategorized:
            uncat_html = render_template('components/article_cards.html',
                                         articles=uncategorized, view_type='pending', is_wos_file=is_wos_file)
            html_parts.append(f'''<div class="category-group mb-6 bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm">
<div class="category-header flex items-center gap-3 px-5 py-3.5 bg-gradient-to-r from-gray-50 to-slate-50 cursor-pointer select-none" onclick="toggleCategory(this)">
<svg class="w-5 h-5 text-gray-400 category-chevron transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
<span class="font-bold text-gray-700 text-base">其他</span>
<span class="ml-auto px-2.5 py-0.5 rounded-full text-xs font-bold bg-gray-100 text-gray-600">{len(uncategorized)} 篇</span>
</div>
<div class="category-body px-4 pb-4 pt-1 space-y-3">{uncat_html}</div>
</div>''')
        html = '\n'.join(html_parts)
    else:
        html = render_template('components/article_cards.html', articles=recommended_articles, view_type='pending', is_wos_file=is_wos_file)
    
    csv_data = []
    # 不管是不是 WOS，只要有推荐结果都可以导出为 CSV
    for a in recommended_articles:
        csv_data.append({
            'id': a.get('article_id', ''),
            'Article Title': a.get('title', ''),
            'Translated Title': '',
            'Abstract': a.get('summary', ''),
            'DOI': a.get('doi', '')
        })
            
    return jsonify({
        'success': True, 
        'html': html, 
        'is_wos_file': is_wos_file, 
        'csv_data': csv_data,
        'total_found': total_found,
        'total_analyzed': len(articles)
    })

@app.route('/inbox')
def inbox():
    # 获取来源筛选参数和排序参数，默认改为按阅读状态
    source_filter = request.args.get('source', '')
    sort_by = request.args.get('sort_by', 'id_desc')
    page = request.args.get('page', 1, type=int)
    page_size = 20
    
    # 获取所有不重复的来源供下拉框使用（不管 pending 还是 saved）
    sources = db.get_unique_sources()
    
    # 订阅收件箱现在展示该期刊下的所有文献 (包含 pending 和 saved)
    # 这样用户加入文库后，文章仍然可以在这里看到，但会带有标识
    articles, total_articles, total_pages, current_page = db.get_articles_by_source_paginated(
        source=source_filter,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )
    articles = process_articles(articles)
    return render_template(
        'index.html',
        articles=articles,
        view_type='pending',
        sources=sources,
        current_source=source_filter,
        sort_by=sort_by,
        current_page=current_page,
        total_pages=total_pages,
        total_articles=total_articles,
        page_size=page_size
    )

@app.route('/translate_titles', methods=['POST'])
def translate_titles():
    source_filter = request.form.get('source', '')
    
    if source_filter:
        articles = db.get_articles_by_source(source=source_filter)
    else:
        articles = db.get_articles_by_source()
        
    # 筛选出尚未翻译过标题的文章
    untranslated = [a for a in articles if not a.get('translated_title') and a.get('trans_status') != 'translating']
    
    if not untranslated:
        flash("当前列表没有需要翻译标题的文献。", "info")
        return redirect(url_for('inbox', source=source_filter))
        
    # 先将这些文章状态标记为 translating
    for article in untranslated:
        db.update_trans_status(article['article_id'], 'translating')
        
    def _translate_single(article):
        trans_title = translator.translate_title_only(article['title'])
        if trans_title and "翻译出错" not in trans_title:
            db.update_translation(article['article_id'], trans_title, article.get('translated_summary', ''))
        else:
            db.update_trans_status(article['article_id'], 'error')
            
    def run_batch_trans():
        # 提高并发数从 5 到 15 以加快批量翻译速度（需注意 API 的速率限制）
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            executor.map(_translate_single, untranslated)
                
    threading.Thread(target=run_batch_trans, daemon=True).start()
    flash(f"已提交 {len(untranslated)} 篇文献的标题翻译任务，请稍后刷新查看。", "success")
    return redirect(url_for('inbox', source=source_filter))

@app.route('/translate_single_title/<int:db_id>', methods=['POST'])
def translate_single_title(db_id):
    article = db.get_article_by_id(db_id)
    if article and not article.get('translated_title') and article.get('trans_status') != 'translating':
        db.update_trans_status(article['article_id'], 'translating')
        
        def run_trans():
            trans_title = translator.translate_title_only(article['title'])
            if trans_title and "翻译出错" not in trans_title:
                db.update_translation(article['article_id'], trans_title, article.get('translated_summary', ''))
            else:
                db.update_trans_status(article['article_id'], 'error')
                
        threading.Thread(target=run_trans, daemon=True).start()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': '已开始翻译'})
    return redirect(request.referrer or url_for('inbox'))

@app.route('/api/translate_text', methods=['POST'])
def api_translate_text():
    text = request.form.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'message': '翻译文本不能为空'})
        
    try:
        from translator import Translator
        translator = Translator(db)
        trans_text = translator.translate_title_only(text)
        if trans_text and "翻译出错" not in trans_text:
            return jsonify({'success': True, 'translated_text': trans_text})
        else:
            return jsonify({'success': False, 'message': '翻译失败或返回错误信息'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'请求出错: {str(e)}'})

@app.route('/clear_inbox', methods=['POST'])
def clear_inbox():
    source_filter = request.form.get('source', '')
    # 调整清空逻辑，因为现在收件箱里同时包含 saved 的文章，不应该一键把文库里的文章也删掉
    # 所以清空操作仍然只针对 pending 状态的文献
    db.clear_articles(status='pending', source=source_filter)
    flash("列表中未加入文库的待处理文献已清空。", "success")
    return redirect(url_for('inbox', source=source_filter))

@app.route('/test_api', methods=['POST'])
def test_api():
    # 简单的API连通性测试
    test_title = "Hello World"
    result = translator.translate_title_only(test_title)
    if result and "翻译出错" not in result:
        flash(f"API 测试成功！大模型返回: {result}", "success")
    else:
        flash(f"API 测试失败，请检查配置。错误信息或返回: {result}", "danger")
    return redirect(url_for('settings'))

@app.route('/article/<int:db_id>')
def article_detail(db_id):
    article = db.get_article_by_id(db_id)
    if not article:
        return "Article not found", 404
        
    # 获取返回链接，用于保持列表页状态
    return_url = request.args.get('return_url')
        
    # 如果处于未读状态且是 pending，点击查看详情时标记为已读
    if article.get('is_read') == 0 and article.get('status') == 'pending':
        db.update_article_read_status(db_id, 1)
        article['is_read'] = 1
        
    article = process_articles([article])[0]
    return render_template('article.html', article=article, return_url=return_url)

@app.route('/save_article/<int:db_id>', methods=['POST'])
def save_article(db_id):
    db.update_article_status(db_id, 'saved')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': '已加入文库'})
    flash("文献已成功添加到您的文库中！", "success")
    # 可以选择返回上一页
    next_url = request.referrer or url_for('inbox')
    return redirect(next_url)

@app.route('/api/download/<int:db_id>')
def api_download_paper(db_id):
    """通过 DOI 自动检索并下载 PDF 全文（异步，前端轮询状态）。"""
    article = db.get_article_by_id(db_id)
    if not article:
        return jsonify({'success': False, 'message': '文章不存在'}), 404

    doi = article.get('doi', '') or ''
    link = article.get('link', '') or ''
    aid = article.get('article_id', '') or ''

    query = doi or link or aid
    if not query:
        return jsonify({'success': False, 'message': '该文章无 DOI 或 PDF 链接，无法自动下载'}), 400

    import re as _re
    title = article.get('translated_title', '') or article.get('title', '') or 'paper'
    safe = _re.sub(r'[\\/:*?"<>|\r\n\t]+', '_', title)[:120].strip('. _') or 'paper'

    # arXiv 快速通道检测
    import re
    arxiv_match = re.search(r'(?:arxiv\.org/abs/|arXiv:|oai:arXiv\.org:)(\d{4}\.\d{4,5}(?:v\d+)?)', query, re.I)
    is_arxiv = bool(arxiv_match)

    task_id = str(uuid.uuid4())
    download_tasks[task_id] = {'status': 'downloading', 'message': '正在下载...', 'file': None}

    def _do_download():
        import time as _time
        try:
            if is_arxiv:
                import urllib.request
                dl_dir = db.get_config('download_dir', '') or os.path.join(os.path.expanduser('~'), 'Downloads')
                os.makedirs(dl_dir, exist_ok=True)
                dest = os.path.join(dl_dir, f'{safe}.pdf')
                base, ext = os.path.splitext(dest)
                counter = 2
                while os.path.exists(dest):
                    dest = f'{base}_{counter}{ext}'; counter += 1
                url = f'https://arxiv.org/pdf/{arxiv_match.group(1)}.pdf'

                # 最多重试 3 次，指数退避
                last_error = None
                for attempt in range(3):
                    try:
                        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            data = resp.read()
                        if len(data) < 1000:
                            last_error = 'PDF 文件异常（<1KB）'
                            _time.sleep(2 ** attempt)
                            continue
                        with open(dest, 'wb') as f:
                            f.write(data)
                        download_tasks[task_id] = {'status': 'success', 'message': f'已保存: {os.path.basename(dest)}', 'file': dest}
                        return
                    except Exception as e:
                        last_error = str(e)
                        if attempt < 2:
                            _time.sleep(2 ** attempt)
                download_tasks[task_id] = {'status': 'failed', 'message': f'arXiv 下载失败（重试3次）: {last_error}', 'file': None}
            else:
                pkg = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'paperdownload')
                if pkg not in sys.path:
                    sys.path.insert(0, pkg)
                from sync_download import download_by_query
                path = download_by_query(query)
                if path and path.exists():
                    import shutil
                    dl_dir = db.get_config('download_dir', '') or os.path.join(os.path.expanduser('~'), 'Downloads')
                    os.makedirs(dl_dir, exist_ok=True)
                    dest = os.path.join(dl_dir, f'{safe}.pdf')
                    base, ext = os.path.splitext(dest)
                    counter = 2
                    while os.path.exists(dest):
                        dest = f'{base}_{counter}{ext}'; counter += 1
                    shutil.copy2(str(path), dest)
                    download_tasks[task_id] = {'status': 'success', 'message': f'已保存: {os.path.basename(dest)}', 'file': dest}
                else:
                    download_tasks[task_id] = {'status': 'failed', 'message': '未找到可下载的 PDF（可能为闭源期刊或无开放获取版本）', 'file': None}
        except Exception as e:
            download_tasks[task_id] = {'status': 'failed', 'message': str(e), 'file': None}

    import threading
    t = threading.Thread(target=_do_download, daemon=True)
    t.start()
    return jsonify({'success': True, 'task_id': task_id, 'message': '开始下载...'})


@app.route('/api/download/status/<task_id>')
def api_download_status(task_id):
    """轮询下载任务状态。"""
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在或已过期'}), 404
    return jsonify({'success': True, **task})

@app.route('/remove_article/<int:db_id>', methods=['POST'])
def remove_article(db_id):
    # 此处选择一种“删除”逻辑：可以直接从数据库删，或者将其标记为 hidden。此处我们使用硬删除
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM articles WHERE id = ?', (db_id,))
    conn.commit()
    conn.close()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': '文献已从列表中移除'})
    flash("文献已从列表中移除。", "success")
    next_url = request.referrer or url_for('index')
    return redirect(next_url)

@app.route('/translate/<int:db_id>', methods=['POST'])
def translate(db_id):
    # 为兼容之前的路由，统一调用单条标题翻译
    article = db.get_article_by_id(db_id)
    if article and not article.get('translated_title'):
        db.update_trans_status(article['article_id'], 'translating')
        
        def bg_translate():
            trans_title = translator.translate_title_only(article['title'])
            if trans_title and "翻译出错" not in trans_title:
                db.update_translation(article['article_id'], trans_title, "")
            else:
                db.update_trans_status(article['article_id'], 'error')
                
        threading.Thread(target=bg_translate, daemon=True).start()
        
    return redirect(request.referrer or url_for('article_detail', db_id=db_id))

@app.route('/fetch_source', methods=['POST'])
def fetch_source():
    global task_status
    with task_status_lock:
        is_running = task_status['is_running']
    if is_running:
        flash("已有获取任务正在运行，请稍候...", "warning")
        return redirect(request.referrer or url_for('inbox'))

    source_name = request.form.get('source_name')
    subs = db.get_subscriptions()
    
    # 如果没有传 source_name，则表示获取所有订阅
    if not source_name:
        targets = subs
        initial_message = '正在准备获取所有订阅...'
    else:
        targets = [s for s in subs if s['source_name'] == source_name]
        if not targets:
            flash("找不到该订阅源配置，可能已被删除", "warning")
            return redirect(url_for('inbox', source=source_name))
        initial_message = f'正在准备获取 {source_name}...'

    rss_target_count = 0
    update_task_status(
        is_running=True,
        message=initial_message,
        progress=0,
        total=len(targets),
        details=[],
        errors=[]
    )

    def fetch_task(targets):
        global task_status
        total_inserted = 0
        total_duplicates = 0
        all_errors = []
        details = []
        try:
            update_task_status(message=f'正在并发抓取 {len(targets)} 个订阅，补源将在主抓取后串行执行...')
            max_workers = min(8, max(len(targets), 1))

            def fetch_one(target):
                end_date = datetime.now(timezone.utc)
                result = fetcher.fetch_subscription(
                    target,
                    default_end_date=end_date,
                    return_details=True,
                    include_supplements=False
                )
                return result, end_date

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(fetch_one, target): target for target in targets}
                rss_supplement_jobs = []
                for future in concurrent.futures.as_completed(future_map):
                    target = future_map[future]
                    name = target.get('source_name') or target.get('sub_value')
                    try:
                        result, end_date = future.result()
                    except Exception as e:
                        result = {
                            'source': name,
                            'type': target.get('sub_type'),
                            'fetched': 0,
                            'inserted': 0,
                            'duplicates': 0,
                            'errors': [str(e)],
                            'warnings': [],
                            'supplements': []
                        }
                        end_date = datetime.now(timezone.utc)
                        print(f"Fetch failed for {name}: {e}")

                    total_inserted += result.get('inserted', 0)
                    total_duplicates += result.get('duplicates', 0)
                    source_errors = result.get('errors') or []
                    for error in source_errors:
                        all_errors.append(f"{result.get('source')}: {error}")
                    details.append(summarize_fetch_result(result))

                    # ── 补源策略：安全拦截全量补源，RSS成功轻量PubMed兜底 ──
                    if target.get('sub_type') == 'rss':
                        sub_value = target.get('sub_value', '')
                        is_security_blocked = result.get('security_blocked', False)
                        has_errors = bool(result.get('errors'))

                        if is_security_blocked:
                            # 被安全验证拦截 → 全量补源
                            _update_supplement_tracking(sub_value, is_blocked=True)
                            fetch_days = target.get('fetch_days') or 7
                            start_date = max(
                                end_date - timedelta(days=fetch_days),
                                end_date - timedelta(days=30)
                            )
                            rss_supplement_jobs.append((target, name, start_date, end_date, 'full'))
                        elif has_errors:
                            # 非安全类错误（网络超时等），不补源
                            status = _update_supplement_tracking(sub_value, is_blocked=False)
                            if status == 'restored':
                                all_errors.append(f"{name}: RSS 安全验证已解除，恢复正常抓取")
                                details.append(f"{name}: RSS 已恢复，取消补源")
                        else:
                            # RSS 正常 → 轻量 PubMed 补齐最近 3 天
                            status = _update_supplement_tracking(sub_value, is_blocked=False)
                            if status == 'restored':
                                all_errors.append(f"{name}: RSS 安全验证已解除，恢复正常抓取")
                                details.append(f"{name}: RSS 已恢复，取消补源")
                            light_start = end_date - timedelta(days=3)
                            rss_supplement_jobs.append((target, name, light_start, end_date, 'light'))

                    update_task_status(
                        total=len(targets) + len(rss_supplement_jobs),
                        message=(
                            f"已完成: {name}，累计新增 {total_inserted} 篇，重复 {total_duplicates} 篇"
                        ),
                        details=details[-8:],
                        errors=all_errors[-8:]
                    )

            for target, name, start_date, end_date, mode in rss_supplement_jobs:
                label = '轻量PubMed' if mode == 'light' else '全量补源'
                update_task_status(message=f'正在{label} {name}...')
                result = fetcher._new_result(name, 'supplement')
                try:
                    fetcher.supplement_subscription(target, name, start_date, end_date, base_result=result, mode=mode)
                except Exception as e:
                    result['errors'].append(str(e))
                    print(f"Supplement failed for {name}: {e}")

                total_inserted += result.get('inserted', 0)
                total_duplicates += result.get('duplicates', 0)
                source_errors = result.get('errors') or []
                for error in source_errors:
                    all_errors.append(f"{result.get('source')}: {error}")
                details.append(summarize_fetch_result(result))

                update_task_status(
                    message=(
                        f"已完成补源 {name}，"
                        f"累计新增 {total_inserted} 篇，重复 {total_duplicates} 篇"
                    ),
                    details=details[-8:],
                    errors=all_errors[-8:]
                )

            # 抓取完成后统一清理主表中过期数据，保持主表基础近 30 天内容
            base_cleanup = db.prune_old_articles(days=30, return_details=True)
            # 再按各个源配置的保留天数清理
            rule_cleanup = db.prune_articles_by_subscription_retention(return_details=True)

            base_deleted_count = base_cleanup['deleted_count']
            sub_deleted_count = rule_cleanup['deleted_count']
            base_cleanup_text = format_cleanup_details(base_cleanup['details'])
            rule_cleanup_text = format_cleanup_details(rule_cleanup['details'], include_retention=True)

            update_task_status(
                is_running=False,
                progress=len(targets) + len(rss_supplement_jobs),
                message=(
                f'抓取完成！共新增 {total_inserted} 篇文章，重复跳过 {total_duplicates} 篇，'
                f'基础清理 {base_deleted_count} 篇（{base_cleanup_text}），'
                f'规则清理 {sub_deleted_count} 篇（{rule_cleanup_text}）。'
                ),
                details=details[-8:],
                errors=all_errors[-8:]
            )
        except Exception as e:
            update_task_status(is_running=False, message=f'抓取过程发生错误: {str(e)}', errors=[str(e)])
            print(f"Fetch failed: {e}")
        finally:
            # 延迟几秒后重置状态以便前端显示完成信息
            import time
            time.sleep(FETCH_RESULT_TTL_SECONDS)
            # 完全重置任务状态，防止后续提示“任务正在运行”
            update_task_status(message='', progress=0, total=0, details=[], errors=[])

    threading.Thread(target=fetch_task, args=(targets,), daemon=True).start()
    
    msg = f"后台正在拉取【{source_name}】的更新..." if source_name else "后台正在拉取【所有订阅】的更新..."
    flash(msg, "success")
    return redirect(request.referrer or url_for('inbox'))

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/search')
def search_page():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = db.search_articles(query, limit=50)
    return render_template('search.html', query=query, results=results)

@app.route('/api/task_status')
def api_task_status():
    """提供给前端轮询的任务状态接口"""
    with task_status_lock:
        status = dict(task_status)
    return jsonify(status)

@app.route('/api/check_translation_status')
def api_check_translation_status():
    """提供给前端轮询的翻译状态接口，返回当前正在翻译的文章状态和已完成的翻译结果"""
    # 获取所有状态为 translating 的文章 ID，用于前端停止轮询的判断
    translating_articles = db.get_articles_by_trans_status('translating')
    translating_ids = [a['id'] for a in translating_articles]
    
    # 接收前端传来的文章 ID 列表（可能刚提交翻译，或者之前处于翻译中）
    article_ids_str = request.args.get('ids', '')
    if not article_ids_str:
        return jsonify({'translating_ids': translating_ids, 'updates': {}})
        
    article_ids = [int(id_str) for id_str in article_ids_str.split(',') if id_str.isdigit()]
    
    updates = {}
    for aid in article_ids:
        article = db.get_article_by_id(aid)
        if article and article.get('trans_status') in ['done', 'error']:
            updates[aid] = {
                'status': article.get('trans_status'),
                'translated_title': article.get('translated_title', ''),
                'translated_summary': article.get('translated_summary', '')
            }
            
    return jsonify({
        'translating_ids': translating_ids,
        'updates': updates
    })

@app.route('/mark_all_read', methods=['POST'])
def mark_all_read():
    source_filter = request.form.get('source', '')
    articles = db.get_articles_by_source(source=source_filter)
    for a in articles:
        if a.get('is_read') == 0:
            db.update_article_read_status(a['id'], 1)
    flash("已全部标记为已读。", "success")
    return redirect(url_for('inbox', source=source_filter))

@app.route('/mark_read/<int:db_id>', methods=['POST'])
def mark_read(db_id):
    db.update_article_read_status(db_id, 1)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': '已标记为已读'})
    return redirect(request.referrer or url_for('inbox'))

@app.route('/api/toggle_follow/<int:db_id>', methods=['POST'])
def toggle_follow(db_id):
    new_status = db.toggle_follow(db_id)
    if new_status is not None:
        return jsonify({'success': True, 'is_followed': new_status})
    return jsonify({'success': False, 'message': '文章不存在'})

@app.route('/delete_source_inbox', methods=['POST'])
def delete_source_inbox():
    source_name = request.form.get('source', '')
    if source_name:
        db.delete_articles_by_source(source_name)
        flash(f"已清空【{source_name}】下的所有文献。", "success")
    return redirect(url_for('inbox'))

@app.route('/subscriptions', methods=['GET', 'POST'])
def subscriptions():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            # 从表单获取 sub_type，如果没传则默认为 rss（兼容原有的界面逻辑）
            sub_type = request.form.get('sub_type', 'rss')
            sub_value = request.form.get('sub_value')
            source_name = request.form.get('source_name', '').strip()
            fetch_days = int(request.form.get('fetch_days', 7))
            retention_days = int(request.form.get('retention_days', 30))
            openalex_query = request.form.get('openalex_query', '').strip()
            if sub_value:
                resolved_info = resolve_subscription_info(sub_type, sub_value.strip(), source_name, openalex_query)
                source_name = resolved_info['source_name'] or source_name
                openalex_query = resolved_info['openalex_query'] or openalex_query
                if db.add_subscription(sub_type, sub_value.strip(), source_name, fetch_days, retention_days, openalex_query):
                    flash("订阅添加成功", "success")
                else:
                    flash("该订阅已存在", "warning")
        elif action == 'update':
            sub_type = request.form.get('sub_type', 'rss')
            sub_value = request.form.get('sub_value')
            source_name = request.form.get('source_name', '').strip()
            fetch_days = int(request.form.get('fetch_days', 7))
            retention_days = int(request.form.get('retention_days', 30))
            openalex_query = request.form.get('openalex_query', '').strip()
            if sub_value:
                resolved_info = resolve_subscription_info(sub_type, sub_value.strip(), source_name, openalex_query)
                openalex_query = resolved_info['openalex_query'] or openalex_query
                db.update_subscription(sub_value, source_name, fetch_days, retention_days, openalex_query)
                flash("订阅配置已更新", "success")
        elif action == 'delete':
            sub_value = request.form.get('sub_value')
            sub_name = request.form.get('source_name', '')
            db.remove_subscription(sub_value)
            # 删除订阅时，顺便清空其在收件箱中遗留的关联文献
            if sub_name:
                db.delete_articles_by_source(sub_name, status='pending')
            flash("订阅及相关待处理文献已删除", "success")
        elif action == 'fetch_manual':
            arxiv_id = request.form.get('arxiv_id')
            if arxiv_id:
                def fetch_manual_task():
                    try:
                        count = fetcher.fetch_manual_arxiv(arxiv_id)
                        db.prune_old_articles(days=30)
                        db.prune_articles_by_subscription_retention()
                        print(f"Manual fetch complete: {count} new articles.")
                    except Exception as e:
                        print(f"Manual fetch failed: {e}")
                threading.Thread(target=fetch_manual_task, daemon=True).start()
                flash(f"正在后台获取 arXiv: {arxiv_id}，请稍后刷新列表查看。", "success")
        return redirect(url_for('subscriptions'))
        
    subs = db.get_subscriptions()
    default_end = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    return render_template(
        'subscriptions.html',
        subs=subs,
        default_start=default_start,
        default_end=default_end,
        conference_groups=TOP_CONFERENCE_GROUPS,
        builtin_journals=BUILTIN_JOURNALS
    )

@app.route('/api/subscriptions/resolve', methods=['POST'])
def api_resolve_subscription():
    sub_type = request.form.get('sub_type', 'rss').strip()
    sub_value = request.form.get('sub_value', '').strip()
    source_name = request.form.get('source_name', '').strip()
    openalex_query = request.form.get('openalex_query', '').strip()
    if not sub_value and not source_name and not openalex_query:
        return jsonify({'success': False, 'message': '请输入 RSS 链接、期刊名或 OpenAlex 补源名'})
    resolved = resolve_subscription_info(sub_type, sub_value, source_name, openalex_query)
    if not resolved.get('matched_by'):
        return jsonify({'success': False, 'message': '未自动识别到期刊信息', 'resolved': resolved})
    return jsonify({'success': True, 'resolved': resolved})

@app.route('/subscriptions/import', methods=['POST'])
def import_subscriptions():
    if 'file' not in request.files:
        flash('未上传文件', 'danger')
        return redirect(url_for('subscriptions'))
        
    file = request.files['file']
    if file.filename == '':
        flash('未选择文件', 'danger')
        return redirect(url_for('subscriptions'))
        
    filename = file.filename.lower()
    success_count = 0
    duplicate_count = 0
    
    try:
        content = file.read().decode('utf-8')
        
        if filename.endswith('.txt'):
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 解析 "名称:链接" 或纯链接
                parts = line.split(':', 1)
                if len(parts) == 2 and parts[0].strip() and parts[1].strip().startswith('http'):
                    title = parts[0].strip()
                    url = parts[1].strip()
                else:
                    title = f"Imported: {line[:20]}..."
                    url = line
                    
                if url.startswith('http'):
                    resolved_info = resolve_subscription_info('rss', url, title, '')
                    if db.add_subscription('rss', url, resolved_info['source_name'] or title, openalex_query=resolved_info['openalex_query']):
                        success_count += 1
                    else:
                        duplicate_count += 1
                        
        elif filename.endswith('.opml') or filename.endswith('.xml'):
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            for outline in root.findall('.//outline'):
                xml_url = outline.get('xmlUrl')
                if xml_url:
                    title = outline.get('title') or outline.get('text') or f"Imported RSS"
                    sub_type = 'rss'
                    # 尝试从 description 中提取 sub_type (之前导出的逻辑)
                    desc = outline.get('description', '')
                    if desc.startswith('Type: '):
                        sub_type = desc.replace('Type: ', '').strip()

                    resolved_info = resolve_subscription_info(sub_type, xml_url, title, '')
                    if db.add_subscription(sub_type, xml_url, resolved_info['source_name'] or title, openalex_query=resolved_info['openalex_query']):
                        success_count += 1
                    else:
                        duplicate_count += 1
                        
        else:
            flash('不支持的文件格式，请上传 .txt 或 .opml 文件', 'danger')
            return redirect(url_for('subscriptions'))
            
        flash(f'导入完成！成功导入 {success_count} 个订阅，{duplicate_count} 个已存在。', 'success')
        
    except Exception as e:
        flash(f'导入失败，文件格式可能有误: {str(e)}', 'danger')
        
    return redirect(url_for('subscriptions'))

@app.route('/subscriptions/export')
def export_subscriptions():
    format_type = request.args.get('format', 'opml')
    subs = db.get_subscriptions()
    
    if format_type == 'txt':
        lines = []
        for sub in subs:
            title = sub.get('source_name', 'Unnamed')
            xml_url = sub.get('sub_value', '')
            if xml_url:
                lines.append(f"{title}: {xml_url}")
                
        txt_content = '\n'.join(lines)
        return Response(
            txt_content.encode('utf-8'),
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment;filename=folpaper_subscriptions.txt"}
        )
    else:
        # 默认导出为 opml
        lines = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<opml version="1.0">')
        lines.append('    <head>')
        lines.append('        <title>FolPaper Subscriptions</title>')
        lines.append('    </head>')
        lines.append('    <body>')
        
        from xml.sax.saxutils import escape
        for sub in subs:
            title = escape(sub.get('source_name', 'Unnamed') or 'Unnamed', entities={'"': "&quot;", "'": "&apos;"})
            xml_url = escape(sub.get('sub_value', '') or '', entities={'"': "&quot;", "'": "&apos;"})
            sub_type = escape(sub.get('sub_type', 'rss') or 'rss', entities={'"': "&quot;", "'": "&apos;"})
            
            if xml_url:
                lines.append(f'        <outline text="{title}" title="{title}" type="rss" xmlUrl="{xml_url}" description="Type: {sub_type}"/>')
                
        lines.append('    </body>')
        lines.append('</opml>')
        
        opml_content = '\n'.join(lines)
        
        return Response(
            opml_content.encode('utf-8'),
            mimetype="application/xml",
            headers={"Content-Disposition": "attachment;filename=folpaper_subscriptions.opml"}
        )


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        for key in ['api_key', 'base_url', 'openalex_api_key', 'flaresolverr_url', 'crossref_mailto',
                     'model', 'translate_model', 'recommend_model', 'survey_model', 'extra_body', 'think_mode',
                     'temperature', 'translate_temperature', 'survey_temperature',
                     'timeout', 'recommend_concurrency', 'download_dir']:
            val = request.form.get(key, '').strip()
            if val:
                db.set_config(key, val)
        translator.client = None
        flash("设置已保存！", "success")
        return redirect(url_for('settings'))

    config = {
        'api_key': db.get_config('api_key', ''),
        'base_url': db.get_config('base_url', 'https://api.openai.com/v1'),
        'model': db.get_config('model', 'gpt-3.5-turbo'),
        'translate_model': db.get_config('translate_model', ''),
        'recommend_model': db.get_config('recommend_model', ''),
        'survey_model': db.get_config('survey_model', ''),
        'temperature': db.get_config('temperature', '0.3'),
        'translate_temperature': db.get_config('translate_temperature', '0.3'),
        'survey_temperature': db.get_config('survey_temperature', '0.5'),
        'timeout': db.get_config('timeout', '60'),
        'recommend_concurrency': db.get_config('recommend_concurrency', '20'),
        'extra_body': db.get_config('extra_body', ''),
        'think_mode': db.get_config('think_mode', 'off'),
        'openalex_api_key': db.get_config('openalex_api_key', ''),
        'flaresolverr_url': db.get_config('flaresolverr_url', ''),
        'crossref_mailto': db.get_config('crossref_mailto', ''),
        'download_dir': db.get_config('download_dir', ''),
    }
    return render_template('settings.html', config=config)


@app.route('/top-conferences')
def top_conferences_page():
    default_end = datetime.now().strftime('%Y-%m-%d')
    default_start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    return render_template(
        'top_conferences.html',
        conference_groups=TOP_CONFERENCE_GROUPS,
        default_start=default_start,
        default_end=default_end
    )


@app.route('/api/top-conferences/fetch', methods=['POST'])
def api_top_conferences_fetch():
    selected_keys = request.form.getlist('conference')
    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()
    api_key = request.form.get('api_key', '').strip()
    max_results = request.form.get('max_results', 300, type=int)

    if not selected_keys:
        return jsonify({'success': False, 'message': '请至少选择一个顶会'})
    if not start_date or not end_date:
        return jsonify({'success': False, 'message': '开始日期和结束日期不能为空'})

    selected = [conf for conf in TOP_CONFERENCES if conf['key'] in selected_keys]
    service = OpenAlexService(api_key=api_key)
    matched_sources = service.search_conference_sources(selected)
    display_names = ', '.join(src['display_name'] for src in matched_sources) or ', '.join(conf['name'] for conf in selected)
    works = service.fetch_conference_works(selected, start_date, end_date, max_results, matched_sources=matched_sources)
    if not works:
        return jsonify({'success': False, 'message': f'在所选顶会 {start_date} 至 {end_date} 范围内未找到可靠的会议来源文献。OpenAlex 对部分顶会的来源标注不稳定，请尝试扩大时间范围或更换会议。'})

    cleaned_works = service.clean_and_group_data(works)
    stats = service.generate_stats(cleaned_works)
    session_id = str(uuid.uuid4())
    openalex_sessions[session_id] = {
        'journal_query': ', '.join(conf['name'] for conf in selected),
        'journal_matched': display_names,
        'works': cleaned_works,
        'stats': stats,
        'filter_progress': 0,
        'filter_total': len(cleaned_works),
        'filter_status': 'idle'
    }

    return jsonify({
        'success': True,
        'session_id': session_id,
        'conference_matched': display_names,
        'total_fetched': len(works),
        'total_cleaned': len(cleaned_works),
        'stats': stats,
        'works': cleaned_works
    })


@app.route('/openalex')
def openalex_page():
    current_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('openalex.html', current_date=current_date)


@app.route('/api/openalex/fetch', methods=['POST'])
def api_openalex_fetch():
    journal_name = request.form.get('journal', '').strip()
    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()
    api_key = request.form.get('api_key', '').strip()
    max_results = request.form.get('max_results', 500, type=int)

    if not journal_name or not start_date or not end_date:
        return jsonify({'success': False, 'message': '期刊名称和日期范围不能为空'})

    service = OpenAlexService(api_key=api_key)
    matched_sources = service.get_source_id(journal_name)
    if not matched_sources:
        return jsonify({'success': False, 'message': f'未在 OpenAlex 中找到匹配的期刊: {journal_name}'})

    source_ids = [src['id'] for src in matched_sources]
    display_names = ", ".join([src['display_name'] for src in matched_sources])

    works = service.fetch_works(source_ids, start_date, end_date, max_results)
    if not works:
        return jsonify({'success': False, 'message': f'在期刊 {display_names} ({start_date} 至 {end_date}) 中未找到任何文献'})

    cleaned_works = service.clean_and_group_data(works)
    stats = service.generate_stats(cleaned_works)

    session_id = str(uuid.uuid4())
    openalex_sessions[session_id] = {
        'journal_query': journal_name,
        'journal_matched': display_names,
        'works': cleaned_works,
        'stats': stats,
        'filter_progress': 0,
        'filter_total': len(cleaned_works),
        'filter_status': 'idle'
    }

    return jsonify({
        'success': True, 
        'session_id': session_id,
        'journal_matched': display_names,
        'total_fetched': len(works),
        'total_cleaned': len(cleaned_works),
        'stats': stats,
        'works': cleaned_works
    })

@app.route('/api/openalex/filter', methods=['POST'])
def api_openalex_filter():
    session_id = request.form.get('session_id')
    topic = request.form.get('topic', '').strip()
    mode = request.form.get('mode', 'title_abstract')

    if not session_id or session_id not in openalex_sessions:
        return jsonify({'success': False, 'message': '无效的会话，请重新拉取'})

    if not topic:
        return jsonify({'success': False, 'message': '请输入筛选主题'})

    session_data = openalex_sessions[session_id]
    works = session_data['works']
    session_data['filter_status'] = 'running'
    session_data['filter_progress'] = 0

    def run_llm_filter():
        from translator import Translator
        t = Translator(db)
        
        def process_work(work):
            try:
                prompt = f"请判断以下文献是否与主题“{topic}”密切相关。\n\n"
                if mode == 'title_abstract' and work.get('abstract'):
                    prompt += f"标题: {work['title']}\n摘要: {work['abstract']}\n\n"
                else:
                    prompt += f"标题: {work['title']}\n\n"
                prompt += "要求：\n1. 第一行仅回复“是”或“否”。\n2. 第二行给出简要的判定理由（50字以内）。"
                
                ans = t.call_llm(prompt, "你是一个严谨的学术文献筛选助手。", temperature=0.1, task='recommend').strip()
                lines = [line.strip() for line in ans.split('\n') if line.strip()]
                if lines:
                    is_related = '是' in lines[0]
                    reason = lines[1] if len(lines) > 1 else '无判定理由'
                    work['is_related'] = '是' if is_related else '否'
                    work['llm_reason'] = reason
                else:
                    work['is_related'] = '未知'
                    work['llm_reason'] = '模型未返回有效结果'
            except Exception as e:
                print(f"LLM filter error for {work.get('title')}: {e}")
                work['is_related'] = '错误'
                work['llm_reason'] = str(e)
            finally:
                session_data['filter_progress'] += 1

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(process_work, works)
            
        session_data['filter_status'] = 'done'

    threading.Thread(target=run_llm_filter, daemon=True).start()
    return jsonify({'success': True, 'message': '开始后台智能筛选'})

@app.route('/api/openalex/progress/<session_id>')
def api_openalex_progress(session_id):
    if session_id not in openalex_sessions:
        return jsonify({'success': False, 'message': '无效的会话'})
    
    session_data = openalex_sessions[session_id]
    return jsonify({
        'success': True,
        'progress': session_data['filter_progress'],
        'total': session_data['filter_total'],
        'status': session_data['filter_status'],
        'works': session_data['works'] if session_data['filter_status'] == 'done' else []
    })

@app.route('/api/openalex/export/<session_id>')
def api_openalex_export(session_id):
    if session_id not in openalex_sessions:
        return "Invalid session", 400
        
    session_data = openalex_sessions[session_id]
    works = session_data['works']
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['标题', '作者', '期刊', '出版年份', 'DOI', '摘要', '主题相关', '判定理由'])
    
    for w in works:
        cw.writerow([
            w.get('title', ''),
            w.get('authors', ''),
            w.get('journal', ''),
            w.get('publication_year', ''),
            w.get('doi', ''),
            w.get('abstract', ''),
            w.get('is_related', ''),
            w.get('llm_reason', '')
        ])
        
    output = si.getvalue().encode('utf-8-sig') # 带有 BOM 方便 Excel 正确识别中文
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=openalex_export_{session_id[:8]}.csv"}
    )

@app.route('/api/dashboard/weekly')
def api_dashboard_weekly():
    days = []
    for i in range(7, 0, -1):
        d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles WHERE status='pending' AND published LIKE ?", (f'{d}%',))
        cnt = cursor.fetchone()[0]
        conn.close()
        days.append({'date': d[5:], 'count': cnt})
    return jsonify({'success': True, 'days': days})


@app.route('/api/dashboard/today')
def api_dashboard_today():
    dashboard = db.get_recent_dashboard(limit=200)
    return jsonify({
        'success': True,
        'stats': {
            'total': dashboard['total'],
            'by_source': dashboard['by_source'],
            'by_category': dashboard['by_category'],
        },
        'articles': dashboard['articles']
    })

@app.route('/api/dashboard/categorize', methods=['POST'])
def api_dashboard_categorize():
    articles = db.get_uncategorized_articles(limit=50)
    if not articles:
        return jsonify({'success': False, 'message': '今日无可分类文献'})

    api_key = db.get_config('api_key', '')
    if not api_key:
        return jsonify({'success': False, 'message': '请先在设置中配置 API Key'})

    # 构建批量分类 prompt
    titles = []
    for i, a in enumerate(articles):
        titles.append(f"[{i}] {a['title']}")

    titles_text = '\n'.join(titles)

    categories = [
        '分子性质预测', '分子生成与优化', '药物设计与发现',
        '蛋白质结构与功能', '合成规划与逆合成', '反应预测与机理',
        '材料设计与筛选', '生物信息与基因组学', '文献挖掘与NLP',
        '通用ML方法', '其他'
    ]

    prompt = f"""你是一个专业的科研文献分类助手。请分析以下论文标题，将每篇论文分配到最合适的类别中。

可选类别: {', '.join(categories)}

规则:
- 每篇论文只分配一个类别
- 输出格式: [编号] 类别名
- 如果无法判断，标记为"其他"
- 不要输出任何解释

论文列表:
{titles_text}"""

    try:
        from openai import OpenAI
        extra_str = db.get_config('extra_body', '')
        extra = {}
        if extra_str:
            try: extra = json.loads(extra_str)
            except: pass
        client = OpenAI(
            api_key=api_key,
            base_url=db.get_config('base_url', 'https://api.openai.com/v1')
        )
        model = db.get_config('recommend_model', '') or db.get_config('model', 'gpt-3.5-turbo')
        response_obj = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的科研文献分类助手。请严格按格式输出。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            extra_body=extra if extra else None,
        )
        response = response_obj.choices[0].message.content

        # 解析响应
        import re
        for line in response.strip().split('\n'):
            line = line.strip()
            match = re.match(r'\[(\d+)\]\s*(.+)', line)
            if match:
                idx = int(match.group(1))
                cat = match.group(2).strip()
                if 0 <= idx < len(articles) and cat in categories:
                    db.set_article_category(articles[idx]['id'], cat)

        stats = db.get_today_stats()
        return jsonify({
            'success': True,
            'message': f'已完成 {len(articles)} 篇文献分类',
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'分类失败: {str(e)}'})


if __name__ == '__main__':
    port = 5012

    # python app.py --web：浏览器模式（原行为）；默认：桌面窗口
    if '--web' in sys.argv:
        import webbrowser
        from threading import Timer
        def open_browser():
            webbrowser.open_new(f"http://127.0.0.1:{port}")
        if getattr(sys, 'frozen', False):
            Timer(1.5, open_browser).start()
            app.run(port=port)
        else:
            Timer(1.5, open_browser).start()
            app.run(debug=True, port=port)
    else:
        # 桌面窗口模式（pywebview）
        import threading
        t = threading.Thread(target=app.run, kwargs={'debug': False, 'port': port}, daemon=True)
        t.start()
        try:
            import webview
            import time
            while True:
                try:
                    import urllib.request
                    urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
                    break
                except Exception:
                    time.sleep(0.5)
            webview.create_window('FolPaper', f'http://127.0.0.1:{port}', width=1280, height=800)
            webview.start()
        except ImportError:
            print('pywebview 未安装，使用浏览器模式：pip install pywebview')
            print(f'浏览器打开 http://127.0.0.1:{port}')
            t.daemon = False
            app.run(debug=True, port=port)
