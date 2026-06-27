import feedparser
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
import time
from email.utils import parsedate_to_datetime
import re

def parse_to_iso(date_str):
    """尝试将各种格式的日期字符串转换为标准 ISO 格式（UTC），以便数据库进行准确的字符串排序"""
    if not date_str: return ""
    try:
        dt = parsedate_to_datetime(date_str)
        # 转换为 UTC 并去除时区信息，方便字典序比较
        dt_utc = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt_utc.isoformat()
    except Exception:
        pass
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.isoformat()
    except Exception:
        pass
    m = re.search(r'\d{4}-\d{2}-\d{2}', date_str)
    if m:
        return m.group(0)
    return date_str

def extract_doi(link, article_id, summary):
    """提取 DOI 的通用逻辑"""
    for field in [link, article_id, summary]:
        if field:
            match = re.search(r'(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)', str(field))
            if match:
                return re.sub(r'[\.\;\,\:]$', '', match.group(1))
    return None

class LiteratureFetcher:
    def __init__(self, db_manager):
        self.db = db_manager

    def _is_within_date_range(self, published_parsed, start_date, end_date):
        if not published_parsed:
            return True # 如果没有时间信息，默认保留
        
        try:
            pub_date = datetime.fromtimestamp(time.mktime(published_parsed), tz=timezone.utc)
            # 确保 start_date 和 end_date 都是 aware datetime
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
                
            return start_date <= pub_date <= end_date
        except Exception:
            return True

    def fetch_all(self, start_date=None, end_date=None):
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        subs = self.db.get_subscriptions()
        total_new = 0
        for sub in subs:
            total_new += self.fetch_subscription(sub, default_start_date=start_date, default_end_date=end_date)
        return total_new

    def fetch_subscription(self, sub, default_start_date=None, default_end_date=None):
        if not default_end_date:
            default_end_date = datetime.now(timezone.utc)
        if not default_start_date:
            default_start_date = default_end_date - timedelta(days=30)

        source_name = sub.get('source_name')
        if not source_name:
            if sub['sub_type'] == 'arxiv':
                source_name = f"arXiv: {sub['sub_value']}"
            elif sub['sub_type'] == 'conference':
                source_name = f"Conference: {sub['sub_value']}"
            else:
                source_name = f"RSS: {sub['sub_value']}"

        fetch_days = sub.get('fetch_days') or 7
        current_start_date = default_end_date - timedelta(days=fetch_days)
        if current_start_date < default_start_date:
            current_start_date = default_start_date

        if sub['sub_type'] == 'arxiv':
            return self.fetch_arxiv(sub['sub_value'], current_start_date, default_end_date, max_results=1000, source_name=source_name)
        if sub['sub_type'] == 'rss':
            return self.fetch_rss(sub['sub_value'], current_start_date, default_end_date, source_name=source_name)
        if sub['sub_type'] == 'pubmed':
            from pubmed_service import PubMedService
            pubmed_service = PubMedService()
            results = pubmed_service.search(sub['sub_value'], retmax=200, start_date=current_start_date, end_date=default_end_date)
            count = 0
            for res in results:
                res['source'] = source_name
                if self.db.add_article(res):
                    count += 1
            return count
        if sub['sub_type'] == 'openalex':
            from openalex_service import OpenAlexService
            api_key = self.db.get_config('openalex_api_key', '')
            openalex_service = OpenAlexService(api_key=api_key)
            matched_sources = openalex_service.get_source_id(sub['sub_value'])
            if not matched_sources:
                return 0
            source_ids = [src['id'] for src in matched_sources]
            start_str = current_start_date.strftime("%Y-%m-%d")
            end_str = default_end_date.strftime("%Y-%m-%d")
            works = openalex_service.fetch_works(source_ids, start_str, end_str, max_results=200)
            cleaned_works = openalex_service.clean_and_group_data(works)
            return self._save_openalex_works(cleaned_works, source_name, end_str)
        if sub['sub_type'] == 'conference':
            from openalex_service import OpenAlexService
            api_key = self.db.get_config('openalex_api_key', '')
            openalex_service = OpenAlexService(api_key=api_key)
            start_str = current_start_date.strftime("%Y-%m-%d")
            end_str = default_end_date.strftime("%Y-%m-%d")
            conference = {'key': sub['sub_value'], 'name': source_name, 'query': sub['sub_value']}
            matched_sources = openalex_service.search_conference_sources([conference])
            works = openalex_service.fetch_conference_works(
                [conference],
                start_str,
                end_str,
                max_results=200,
                matched_sources=matched_sources,
            )
            cleaned_works = openalex_service.clean_and_group_data(works)
            return self._save_openalex_works(cleaned_works, source_name, end_str)
        return self.fetch_rss(sub['sub_value'], current_start_date, default_end_date, source_name=source_name)

    def _save_openalex_works(self, works, source_name, fallback_date):
        count = 0
        for w in works:
            article_data = {
                'article_id': w['id'],
                'title': w['title'],
                'authors': w['authors'],
                'summary': w['abstract'],
                'link': f"https://doi.org/{w['doi']}" if w['doi'] else w['id'],
                'published': w['publication_date'] + "T00:00:00Z" if w['publication_date'] else fallback_date + "T00:00:00Z",
                'source': source_name,
                'doi': w['doi'],
                'journal': w.get('journal')
            }
            if self.db.add_article(article_data):
                count += 1
        return count

    def fetch_arxiv(self, category="cs.AI", start_date=None, end_date=None, max_results=20, source_name=None):
        # 订阅指定预印本类别，例如 cs.AI (人工智能)
        base_url = 'http://export.arxiv.org/api/query?'
        # arxiv 支持按照提交时间排序
        query = f'search_query=cat:{category}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=desc'
        url = base_url + query
        
        if not source_name:
            source_name = f"arXiv: {category}"
            
        return self._parse_arxiv_feed(url, source=source_name, start_date=start_date, end_date=end_date)

    def fetch_rss(self, feed_url, start_date=None, end_date=None, source_name=None):
        if not source_name:
            source_name = f"RSS: {feed_url}"
            
        # 获取RSS期刊更新，添加 User-Agent 伪装浏览器，防止被部分学术网站（如 OUP）拦截返回 403 Forbidden
        try:
            req = urllib.request.Request(
                feed_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
            )
            response = urllib.request.urlopen(req, timeout=20)
            feed_data = response.read()
            feed = feedparser.parse(feed_data)
        except Exception as e:
            print(f"Failed to fetch RSS {feed_url}: {e}")
            return 0
            
        new_items_count = 0
        
        for entry in feed.entries:
            try:
                # 获取解析的时间元组，兼容多种时间字段格式
                parsed_date = entry.get('published_parsed') or entry.get('updated_parsed') or entry.get('created_parsed')
                
                if start_date and end_date:
                    if not self._is_within_date_range(parsed_date, start_date, end_date):
                        continue

                # 增强 ID 的获取逻辑：按优先级依次尝试 id, link, title，防止因缺失 id 导致后续去重和入库失败
                article_id = entry.get('id') or entry.get('link') or entry.get('title')
                if not article_id:
                    import uuid
                    article_id = f"urn:uuid:{uuid.uuid4()}"
                    
                title = entry.get('title') or entry.get('title_detail', {}).get('value') or 'Unknown Title'
                title = title.replace('\n', ' ').strip()
                
                # 增强摘要提取：兼容标准的 summary、description，或嵌入在 content 中的正文内容
                summary = entry.get('summary') or entry.get('description', '')
                if not summary and 'content' in entry and len(entry.content) > 0:
                    summary = entry.content[0].get('value', '')
                if not summary:
                    summary = 'No summary provided.'
                    
                link = entry.get('link', '')
                
                # 增强发布时间字符串的获取，适配不同规范的 RSS 源
                published = entry.get('published') or entry.get('updated') or entry.get('pubDate') or entry.get('dc_date') or ''
                
                # 提取作者，兼容常见的 authors 列表、单独的 author 字段以及 dc:creator 和 creator
                authors = []
                if 'authors' in entry:
                    authors = [author.get('name', '') for author in entry.authors if 'name' in author]
                elif 'author' in entry:
                    authors = [entry.author]
                elif 'dc_creator' in entry:
                    authors = [entry.dc_creator]
                elif 'creator' in entry:
                    authors = [entry.creator]
                author_str = ", ".join([a for a in authors if a]) if authors else "Unknown"
                
                # 尝试直接从 RSS 节点获取 DOI（如 prism:doi 或 dc:identifier）
                doi = entry.get('prism_doi') or entry.get('dc_identifier')
                if not doi:
                    doi = extract_doi(link, article_id, summary)
                elif doi.lower().startswith('doi:'):
                    doi = doi[4:]
                
                article_data = {
                    'article_id': str(article_id),
                    'title': str(title),
                    'authors': str(author_str),
                    'summary': str(summary),
                    'link': str(link),
                    'published': parse_to_iso(str(published)), # 转换为 ISO 格式保证排序准确
                    'source': source_name,
                    'doi': str(doi) if doi else None # 提取 DOI 供归档使用
                }
                
                # 以增量形式添加，利用数据库 UNIQUE 约束去重
                if self.db.add_article(article_data):
                    new_items_count += 1
            except Exception as e:
                # 遇到解析异常时打印错误，防止阻断其他正常节点的拉取
                print(f"解析 RSS 条目时发生异常，已跳过该条目: {e}")
                continue
                
        return new_items_count

    def fetch_manual_arxiv(self, arxiv_id):
        # 独立功能：手动提交文献需求（通过 arXiv ID）
        base_url = 'http://export.arxiv.org/api/query?'
        query = f'id_list={arxiv_id}'
        url = base_url + query
        return self._parse_arxiv_feed(url, source="Manual Entry")

    def _parse_arxiv_feed(self, url, source, start_date=None, end_date=None):
        # 解析 arXiv XML 数据流
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
            )
            response = urllib.request.urlopen(req, timeout=20)
            feed_data = response.read()
            feed = feedparser.parse(feed_data)
        except Exception as e:
            print(f"Failed to fetch arXiv {url}: {e}")
            return 0
        
        new_items_count = 0
        for entry in feed.entries:
            try:
                # 获取解析的时间元组
                parsed_date = entry.get('published_parsed') or entry.get('updated_parsed') or entry.get('created_parsed')
                
                if start_date and end_date:
                    if not self._is_within_date_range(parsed_date, start_date, end_date):
                        continue

                # 清理标题和摘要文本
                title = entry.get('title', '').replace('\n', ' ').strip()
                summary = entry.get('summary', '').replace('\n', ' ').strip()
                authors = ", ".join(author.get('name', '') for author in entry.get('authors', []))
                article_id = entry.get('id', '')
                
                article_data = {
                    'article_id': article_id,
                    'title': title,
                    'authors': authors,
                    'summary': summary,
                    'link': entry.get('link', ''),
                    'published': parse_to_iso(entry.get('published', '')), # 转换为 ISO 格式保证排序准确
                    'source': source,
                    'doi': extract_doi(entry.get('link', ''), article_id, summary)
                }
                
                if self.db.add_article(article_data):
                    new_items_count += 1
            except Exception as e:
                print(f"解析 arXiv 条目时发生异常，已跳过该条目: {e}")
                continue
                
        return new_items_count
