import feedparser
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import json
import os
from datetime import datetime, timezone, timedelta
import time
from email.utils import parsedate_to_datetime
import re
import logging
import concurrent.futures

# 拉取日志：记录每次抓取的详细过程到 fetch.log
_fetch_log = logging.getLogger('folpaper.fetch')
_fetch_log.setLevel(logging.DEBUG)
if not _fetch_log.handlers:
    _fh = logging.FileHandler(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fetch.log'),
        encoding='utf-8'
    )
    _fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    _fetch_log.addHandler(_fh)
    _fetch_log.propagate = False

SECURITY_CHALLENGE_MARKERS = (
    # Cloudflare
    'checking your browser',
    'just a moment',
    'cf-browser-verification',
    'cloudflare',
    # Akamai
    'akamai',
    # Imperva / Incapsula
    'incap_ses',
    '_incap_',
    'incapsula',
    # AWS WAF / CloudFront
    'request blocked',
    'aws-waf',
    # Fastly
    'fastly',
    # Generic
    'enable javascript',
    'access denied',
    'captcha',
    'challenge-platform',
)

SUPPLEMENT_MIN_THRESHOLD = 3  # 补源至少收到此数量才视为有效，避免只拉到1-2篇就短路
SUPPLEMENT_TIMEOUT = 45  # 单个补源操作超时秒数

def _is_security_page(content_bytes_or_text):
    """统一的安全页面检测，供 HTTP 响应体和 feed 内容两处复用。"""
    if isinstance(content_bytes_or_text, bytes):
        raw = content_bytes_or_text[:8192]
        text = raw.decode('utf-8', errors='ignore').lower()
    else:
        raw = None
        text = str(content_bytes_or_text)[:8192].lower()
    if any(marker in text for marker in SECURITY_CHALLENGE_MARKERS):
        return True
    # HTML 页面且不含任何 RSS/Atom/RDF 标记，认定为安全拦截页面
    if ('<html' in text or '<!doctype html' in text) and not any(
        tag in text for tag in ('<rss', '<feed', '<rdf')
    ):
        return True
    # 二进制/加密响应：合法 HTTP 响应不可能以控制字符（非空白）开头
    if raw is not None and len(raw) > 0:
        first = raw[0]
        if first < 32 and first not in (9, 10, 13):
            return True
    return False

RSS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Upgrade-Insecure-Requests': '1',
    'Connection': 'keep-alive',
}

JOURNAL_LIBRARY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'builtin_journals.json')

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
                return normalize_doi(match.group(1))
    return None

def normalize_doi(value):
    if not value:
        return None
    doi = str(value).strip().lower()
    doi = doi.replace('https://doi.org/', '').replace('http://doi.org/', '').replace('http://dx.doi.org/', '')
    if doi.startswith('doi:'):
        doi = doi[4:]
    doi = re.sub(r'\s+', '', doi)
    doi = re.sub(r'[\.\;\,\:]$', '', doi)
    return doi or None

class LiteratureFetcher:
    def __init__(self, db_manager):
        self.db = db_manager
        self.journal_library = self._load_journal_library()
        # Cookie 会话：复用同一个 CookieJar 跨请求保持 CDN 下发的 clearance cookie
        self._cookie_jar = http.cookiejar.CookieJar()
        self._cookie_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie_jar)
        )

    def _get_flaresolverr_url(self):
        """读取 FlareSolverr 地址，未配置返回空表示禁用。"""
        url = (self.db.get_config('flaresolverr_url', '') or '').strip()
        return url if url else None

    def _fetch_via_patchright(self, rss_url, timeout=60):
        """使用 Patchright（Playwright 反检测硬分叉）绕过 Cloudflare。

        Patchright 抹除了 CDP 痕迹和数十个自动化指纹，能通过 CF JS Challenge。
        安装：pip install patchright && patchright install chromium

        返回 (data, error_message, is_security)。
        """
        try:
            from patchright.sync_api import sync_playwright
        except ImportError:
            return None, 'Patchright 未安装', False

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=['--no-sandbox'],
                )
                try:
                    page = browser.new_page()
                    page.goto(rss_url, wait_until='load', timeout=30000)

                    # 等待 Cloudflare 挑战自动完成（或超时）
                    deadline = time.time() + timeout
                    while time.time() < deadline:
                        time.sleep(1)
                        content_lower = page.content().lower()
                        if '<rss' in content_lower or '<feed' in content_lower:
                            break

                    content = page.content()
                finally:
                    browser.close()

            # Chromium XML viewer 会包装 RSS，从隐藏层提取原始 XML
            if 'webkit-xml-viewer-source-xml' in content:
                import re
                m = re.search(
                    r'<div\s+id="webkit-xml-viewer-source-xml"\s+style="[^"]*">(.*?)</div>',
                    content, re.DOTALL
                )
                if m:
                    content = m.group(1)

            data = content.encode('utf-8')
            if _is_security_page(data):
                return None, 'Patchright 未能绕过安全验证', True
            return data, None, False
        except Exception as e:
            return None, f'Patchright 请求失败: {e}', False

    def _load_journal_library(self):
        if not os.path.exists(JOURNAL_LIBRARY_FILE):
            return []
        try:
            with open(JOURNAL_LIBRARY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load journal library: {e}")
            return []

    def _extract_subscription_code(self, sub_value):
        if not sub_value:
            return ''
        parsed = urllib.parse.urlparse(sub_value)
        query = urllib.parse.parse_qs(parsed.query)
        if query.get('jc'):
            return query['jc'][0].strip().lower()
        path = parsed.path.strip('/').split('/')
        if path:
            last = path[-1]
            if last.endswith('.rss') or last.endswith('.xml'):
                last = last.rsplit('.', 1)[0]
            return last.strip().lower()
        return ''

    def _resolve_journal_metadata(self, sub):
        sub_value = (sub.get('sub_value') or '').strip()
        source_name = (sub.get('source_name') or '').strip().lower()
        openalex_query = (sub.get('openalex_query') or '').strip().lower()
        code = self._extract_subscription_code(sub_value)
        normalized_url = sub_value.lower()

        for journal in self.journal_library:
            journal_url = (journal.get('url') or '').strip().lower()
            journal_code = (journal.get('code') or '').strip().lower()
            names = {
                (journal.get('name') or '').strip().lower(),
                (journal.get('full_name') or '').strip().lower(),
                (journal.get('openalex_query') or '').strip().lower(),
            }
            if journal_url and journal_url == normalized_url:
                return journal
            if code and journal_code and code == journal_code:
                return journal
            if openalex_query and openalex_query in names:
                return journal
            if source_name and source_name in names:
                return journal
        return None

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

    def _new_result(self, source_name, sub_type):
        return {
            'source': source_name,
            'type': sub_type,
            'fetched': 0,
            'inserted': 0,
            'duplicates': 0,
            'errors': [],
            'warnings': [],
            'supplements': []
        }

    def _record_article(self, article_data, result):
        status = self.db.add_article(article_data, return_status=True)
        if status == 'inserted':
            result['inserted'] += 1
            return True
        if status and status.startswith('duplicate'):
            result['duplicates'] += 1
        return False

    def _fetch_feed_data(self, url):
        """返回 (data, error_message, is_security)。

        is_security 为 True 表示被安全验证拦截（如 Cloudflare/Akamai），
        后续补源逻辑会据此决定是否启动 API 补源。
        """
        req = urllib.request.Request(url, headers=RSS_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                data = response.read()
                # Cloudflare JS Challenge 等返回 200 但内容是验证页
                if _is_security_page(data):
                    return None, 'HTTP 200 但返回安全验证页面，RSS 需要浏览器验证', True
                return data, None, False
        except urllib.error.HTTPError as e:
            body_bytes = b''
            try:
                body_bytes = e.read(8192)
            except Exception:
                pass
            is_security = e.code in (401, 403, 429, 503) and _is_security_page(body_bytes)
            if is_security:
                return None, f'安全验证拦截 HTTP {e.code}，RSS 需要浏览器验证，已尝试使用 OpenAlex 补源', True
            # 虽然状态码异常但不像安全页面，可能是临时故障
            return None, f'HTTP {e.code}: {e.reason}', False
        except Exception as e:
            return None, str(e), False

    def _looks_like_security_challenge(self, feed_data):
        return _is_security_page(feed_data)

    def _guess_journal_homepage(self, rss_url):
        """从 RSS URL 反推期刊首页，供 Cookie 预取使用。"""
        parsed = urllib.parse.urlparse(rss_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path_parts = [p for p in parsed.path.split('/') if p]
        # 常见 RSS 路径模式：/rss/xxx, /feed/xxx, /action/showFeed, /toc/xxx
        rss_segments = {'rss', 'feed', 'action', 'toc', 'loi', 'pb-assets'}
        filtered = [p for p in path_parts if p.lower() not in rss_segments]
        if filtered:
            return f"{base}/{'/'.join(filtered[:2])}"
        return base

    def _fetch_with_cookie_session(self, url, timeout=20):
        """Cookie 预取策略：先访问期刊首页拿 CDN clearance cookie，再用同一会话拉 RSS。

        返回 (data, error_message, is_security)，与 _fetch_feed_data 签名一致。
        """
        try:
            homepage = self._guess_journal_homepage(url)
            req = urllib.request.Request(homepage, headers=RSS_HEADERS)
            try:
                self._cookie_opener.open(req, timeout=10)
            except Exception:
                pass  # 首页也可能被拦截，不阻塞，cookie jar 里有什么用什么
        except Exception:
            pass  # 首页 URL 推导失败或请求异常，跳过预取，直接用 cookie jar 现有会话

        # 用同一 cookie jar 拉 RSS
        req = urllib.request.Request(url, headers=RSS_HEADERS)
        try:
            with self._cookie_opener.open(req, timeout=timeout) as response:
                data = response.read()
                if _is_security_page(data):
                    return None, 'Cookie 会话返回安全验证页面', True
                return data, None, False
        except urllib.error.HTTPError as e:
            body_bytes = b''
            try:
                body_bytes = e.read(8192)
            except Exception:
                pass
            is_security = e.code in (401, 403, 429, 503) and _is_security_page(body_bytes)
            if is_security:
                return None, f'Cookie 预取仍被拦截 HTTP {e.code}', True
            return None, f'Cookie 会话 HTTP {e.code}: {e.reason}', False
        except Exception as e:
            return None, str(e), False

    def _fetch_via_flaresolverr(self, rss_url, timeout=60):
        """通过 FlareSolverr 代理获取受 Cloudflare 保护的 RSS 内容。

        FlareSolverr 是一个开源中间件，用 headless 浏览器自动通过 JS Challenge/Turnstile。
        部署：docker run -d --name flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest

        返回 (data, error_message, is_security)，与 _fetch_feed_data 签名一致。
        """
        fs_url = self._get_flaresolverr_url()
        if not fs_url:
            return None, 'FlareSolverr 未配置', False
        try:
            payload = json.dumps({
                "cmd": "request.get",
                "url": rss_url,
                "maxTimeout": timeout * 1000,
            }).encode('utf-8')
            req = urllib.request.Request(
                fs_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=timeout + 15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            if result.get('status') != 'ok':
                return None, f"FlareSolverr 返回异常: {result.get('message', 'unknown')}", False
            solution = result.get('solution', {})
            if solution.get('status') != 200:
                return None, f"FlareSolverr 目标返回 HTTP {solution.get('status')}", True
            data = solution.get('response', '').encode('utf-8')
            # FlareSolverr 可能返回 HTML 验证页（如 Turnstile 失败），再次检测
            if _is_security_page(data):
                return None, 'FlareSolverr 返回仍为安全验证页面', True
            return data, None, False
        except urllib.error.HTTPError as e:
            return None, f'FlareSolverr 服务 HTTP {e.code}', False
        except Exception as e:
            return None, f'FlareSolverr 请求失败: {e}', False

    def _save_openalex_works_into_result(self, works, source_name, fallback_date, result):
        for w in works:
            article_data = {
                'article_id': w['id'],
                'title': w['title'],
                'authors': w['authors'],
                'summary': w['abstract'],
                'link': f"https://doi.org/{w['doi']}" if w['doi'] else w['id'],
                'published': w['publication_date'] + "T00:00:00Z" if w['publication_date'] else fallback_date + "T00:00:00Z",
                'source': source_name,
                'doi': normalize_doi(w['doi']),
                'journal': w.get('journal')
            }
            self._record_article(article_data, result)

    def _save_article_list_into_result(self, articles, source_name, result):
        for article in articles:
            article_data = dict(article)
            article_data['source'] = source_name
            self._record_article(article_data, result)

    def _filter_articles_by_date(self, articles, start_date, end_date):
        filtered = []
        for article in articles:
            published = article.get('published') or ''
            date_part = published[:10]
            try:
                pub_date = datetime.strptime(date_part, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                if start_date <= pub_date <= end_date:
                    filtered.append(article)
            except Exception:
                filtered.append(article)
        return filtered

    def _fill_missing_abstracts_from_pubmed(self, articles, max_lookups=20):
        missing = [article for article in articles if not article.get('summary') and article.get('doi')]
        if not missing:
            return 0
        try:
            from pubmed_service import PubMedService
            service = PubMedService()
            filled_count = 0
            for article in missing[:max_lookups]:
                pubmed_article = service.search_by_doi(article.get('doi'))
                if pubmed_article and pubmed_article.get('summary'):
                    article['summary'] = pubmed_article['summary']
                    filled_count += 1
            return filled_count
        except Exception as e:
            print(f'PubMed DOI 摘要补全失败: {e}')
            return 0

    def _supplement_query(self, sub, metadata, source_name):
        query = sub.get('openalex_query') or (metadata or {}).get('openalex_query') or source_name
        if query and (query.startswith('RSS:') or query.startswith('Imported:')) and not metadata:
            return ''
        return query

    def _openalex_supplement(self, query_name, source_name, start_date, end_date, result, max_results=1000, metadata=None):
        if not query_name and not metadata:
            return
        if query_name and (query_name.startswith('RSS:') or query_name.startswith('Imported:')) and not metadata:
            return
        try:
            from openalex_service import OpenAlexService
            api_key = self.db.get_config('openalex_api_key', '')
            openalex_service = OpenAlexService(api_key=api_key)
            matched_sources = openalex_service.get_source_id(
                query_name,
                issn=(metadata or {}).get('issn'),
                source_id=(metadata or {}).get('openalex_source_id'),
            )
            if not matched_sources:
                identifiers = []
                if (metadata or {}).get('issn'):
                    identifiers.append(f"ISSN {(metadata or {}).get('issn')}")
                if (metadata or {}).get('openalex_source_id'):
                    identifiers.append(f"Source ID {(metadata or {}).get('openalex_source_id')}")
                suffix = f" ({'，'.join(identifiers)})" if identifiers else ''
                result['warnings'].append(f'OpenAlex 未匹配到来源: {query_name}{suffix}')
                return
            source_ids = [src['id'] for src in matched_sources]
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            works = openalex_service.fetch_works(source_ids, start_str, end_str, max_results=max_results)
            cleaned_works = openalex_service.clean_and_group_data(works)
            before_inserted = result['inserted']
            before_duplicates = result['duplicates']
            self._save_openalex_works_into_result(cleaned_works, source_name, end_str, result)
            result['supplements'].append({
                'source': 'OpenAlex',
                'matched': ', '.join(src['display_name'] for src in matched_sources),
                'fetched': len(cleaned_works),
                'inserted': result['inserted'] - before_inserted,
                'duplicates': result['duplicates'] - before_duplicates,
            })
        except Exception as e:
            result['errors'].append(f'OpenAlex 补源失败: {e}')

    def _crossref_supplement(self, query_name, source_name, start_date, end_date, result, metadata=None, max_results=200):
        issn = (metadata or {}).get('issn', '')
        if not query_name and not issn:
            return
        try:
            from crossref_service import CrossrefService
            mailto = self.db.get_config('crossref_mailto', '') or 'researcher@example.com'
            service = CrossrefService(mailto=mailto)
            articles = service.search_journal(
                journal_name=query_name,
                issn=issn,
                start_date=start_date,
                end_date=end_date,
                rows=max_results,
            )
            articles = self._filter_articles_by_date(articles, start_date, end_date)
            abstract_filled = self._fill_missing_abstracts_from_pubmed(articles)
            before_inserted = result['inserted']
            before_duplicates = result['duplicates']
            self._save_article_list_into_result(articles, source_name, result)
            result['supplements'].append({
                'source': 'Crossref',
                'matched': issn or query_name,
                'fetched': len(articles),
                'inserted': result['inserted'] - before_inserted,
                'duplicates': result['duplicates'] - before_duplicates,
                'abstract_filled': abstract_filled,
            })
        except Exception as e:
            result['errors'].append(f'Crossref 补源失败: {e}')

    def _pubmed_supplement(self, query_name, source_name, start_date, end_date, result, metadata=None, max_results=200):
        issn = (metadata or {}).get('issn', '')
        if not query_name and not issn:
            return
        try:
            from pubmed_service import PubMedService
            service = PubMedService()
            articles = service.search_journal(
                journal_name=query_name,
                issn=issn,
                retmax=max_results,
                start_date=start_date,
                end_date=end_date,
            )
            articles = self._filter_articles_by_date(articles, start_date, end_date)
            before_inserted = result['inserted']
            before_duplicates = result['duplicates']
            self._save_article_list_into_result(articles, source_name, result)
            result['supplements'].append({
                'source': 'PubMed',
                'matched': issn or query_name,
                'fetched': len(articles),
                'inserted': result['inserted'] - before_inserted,
                'duplicates': result['duplicates'] - before_duplicates,
            })
        except Exception as e:
            result['errors'].append(f'PubMed 补源失败: {e}')

    def _supplement_fetched_since(self, result, start_index):
        return any(
            item.get('fetched', 0) >= SUPPLEMENT_MIN_THRESHOLD
            for item in result.get('supplements', [])[start_index:]
        )

    def supplement_subscription(self, sub, source_name, start_date, end_date, base_result=None, mode='full'):
        """API 补源。mode: 'full'=三级全量(安全拦截时), 'light'=仅PubMed(成功时补齐最新)。

        base_result 应携带 'security_blocked': True 表示确实被安全拦截，
        而非 RSS 可访问但 0 更新的情况。
        """
        result = base_result or self._new_result(source_name, 'supplement')
        if sub.get('sub_type') != 'rss':
            return result
        journal_metadata = self._resolve_journal_metadata(sub)
        supplement_query = self._supplement_query(sub, journal_metadata, source_name)
        _fetch_log.info('补源开始 %s (mode=%s query=%s)', source_name, mode, supplement_query or source_name)

        if mode == 'light':
            # RSS 成功后轻量补源：仅 PubMed 补齐最新文章（force 跳过生物医学门控）
            self._pubmed_supplement(supplement_query, source_name, start_date, end_date,
                                     result, metadata=journal_metadata, max_results=50)
            _fetch_log.info('补源结束 %s (light): supplements=%d', source_name, len(result.get('supplements', [])))
            return result

        # mode == 'full': 安全拦截时全量补源
        deadline = time.time() + SUPPLEMENT_TIMEOUT
        # 补源顺序：Crossref → PubMed → OpenAlex（按时效性排序）
        supplement_start = len(result.get('supplements', []))
        if time.time() < deadline:
            self._crossref_supplement(supplement_query, source_name, start_date, end_date, result, metadata=journal_metadata)
        if self._supplement_fetched_since(result, supplement_start):
            _fetch_log.info('补源完成 %s: Crossref 满足阈值', source_name)
            return result
        supplement_start = len(result.get('supplements', []))
        if time.time() < deadline:
            self._pubmed_supplement(supplement_query, source_name, start_date, end_date, result, metadata=journal_metadata)
        if self._supplement_fetched_since(result, supplement_start):
            _fetch_log.info('补源完成 %s: PubMed 满足阈值', source_name)
            return result
        supplement_start = len(result.get('supplements', []))
        if time.time() < deadline:
            self._openalex_supplement(supplement_query, source_name, start_date, end_date, result, metadata=journal_metadata)
        else:
            result['errors'].append(f'补源超时（{SUPPLEMENT_TIMEOUT}秒），跳过 OpenAlex')
        if self._supplement_fetched_since(result, supplement_start):
            _fetch_log.info('补源完成 %s: OpenAlex 满足阈值', source_name)
            return result
        _fetch_log.info('补源结束 %s: supplements=%d', source_name, len(result.get('supplements', [])))
        return result

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

    def fetch_subscription(self, sub, default_start_date=None, default_end_date=None, return_details=False, include_supplements=True):
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
            result = self.fetch_arxiv(sub['sub_value'], current_start_date, default_end_date, max_results=1000, source_name=source_name, return_details=True)
            return result if return_details else result['inserted']
        if sub['sub_type'] == 'rss':
            if 'biorxiv.org' in (sub.get('sub_value') or '').lower():
                result = self.fetch_biorxiv_api(
                    sub['sub_value'], current_start_date, default_end_date,
                    max_results=1000, source_name=source_name
                )
                if result.get('api_success'):
                    return result if return_details else result['inserted']
            result = self.fetch_rss(sub['sub_value'], current_start_date, default_end_date, source_name=source_name, return_details=True)
            if include_supplements:
                self.supplement_subscription(sub, source_name, current_start_date, default_end_date, base_result=result)
            return result if return_details else result['inserted']
        if sub['sub_type'] == 'pubmed':
            from pubmed_service import PubMedService
            pubmed_service = PubMedService()
            result = self._new_result(source_name, 'pubmed')
            results = pubmed_service.search(sub['sub_value'], retmax=1000, start_date=current_start_date, end_date=default_end_date)
            result['fetched'] = len(results)
            for res in results:
                res['source'] = source_name
                self._record_article(res, result)
            return result if return_details else result['inserted']
        if sub['sub_type'] == 'openalex':
            from openalex_service import OpenAlexService
            result = self._new_result(source_name, 'openalex')
            api_key = self.db.get_config('openalex_api_key', '')
            openalex_service = OpenAlexService(api_key=api_key)
            matched_sources = openalex_service.get_source_id(sub['sub_value'])
            if not matched_sources:
                result['warnings'].append(f"OpenAlex 未匹配到来源: {sub['sub_value']}")
                return result if return_details else 0
            source_ids = [src['id'] for src in matched_sources]
            start_str = current_start_date.strftime("%Y-%m-%d")
            end_str = default_end_date.strftime("%Y-%m-%d")
            works = openalex_service.fetch_works(source_ids, start_str, end_str, max_results=1000)
            cleaned_works = openalex_service.clean_and_group_data(works)
            result['fetched'] = len(cleaned_works)
            self._save_openalex_works_into_result(cleaned_works, source_name, end_str, result)
            return result if return_details else result['inserted']
        if sub['sub_type'] == 'conference':
            from openalex_service import OpenAlexService
            result = self._new_result(source_name, 'conference')
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
                max_results=1000,
                matched_sources=matched_sources,
            )
            cleaned_works = openalex_service.clean_and_group_data(works)
            result['fetched'] = len(cleaned_works)
            self._save_openalex_works_into_result(cleaned_works, source_name, end_str, result)
            return result if return_details else result['inserted']
        result = self.fetch_rss(sub['sub_value'], current_start_date, default_end_date, source_name=source_name, return_details=True)
        return result if return_details else result['inserted']

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

    def fetch_biorxiv_api(self, feed_url, start_date, end_date, max_results=1000, source_name='bioRxiv'):
        """通过 bioRxiv 分页 API 获取指定日期和学科范围内的预印本。"""
        result = self._new_result(source_name, 'biorxiv')
        result['api_success'] = False
        raw_subject = next((part.split('=', 1)[1] for part in
                            urllib.parse.urlparse(feed_url).query.split('&')
                            if part.startswith('subject=')), '')
        subjects = {
            urllib.parse.unquote(item).replace('_', ' ').strip().lower()
            for item in raw_subject.split('+') if item.strip()
        }

        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        def fetch_page(cursor):
            url = f'https://api.biorxiv.org/details/biorxiv/{start_str}/{end_str}/{cursor}'
            req = urllib.request.Request(url, headers=RSS_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))

        def record_collection(collection):
            for item in collection:
                category = (item.get('category') or '').replace('_', ' ').strip().lower()
                if subjects and category not in subjects:
                    continue
                doi = normalize_doi(item.get('doi'))
                article_data = {
                    'article_id': doi or item.get('jatsxml') or item.get('title'),
                    'title': item.get('title') or 'Unknown Title',
                    'authors': item.get('authors') or 'Unknown',
                    'summary': item.get('abstract') or 'No summary provided.',
                    'link': f'https://doi.org/{doi}' if doi else (item.get('jatsxml') or ''),
                    'published': f"{item.get('date')}T00:00:00Z" if item.get('date') else '',
                    'source': source_name,
                    'doi': doi,
                    'journal': 'bioRxiv'
                }
                result['fetched'] += 1
                self._record_article(article_data, result)
                if result['fetched'] >= max_results:
                    break

        try:
            first_page = fetch_page(0)
            first_collection = first_page.get('collection') or []
            messages = first_page.get('messages') or []
            meta = messages[0] if messages else {}
            page_size = int(meta.get('count') or len(first_collection) or 100)
            total = int(meta.get('total') or len(first_collection))
            scan_limit = min(total, max(max_results * 5, 1000))
            record_collection(first_collection)

            cursors = range(page_size, scan_limit, page_size)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_cursor = {executor.submit(fetch_page, cursor): cursor for cursor in cursors}
                pages = []
                for future in concurrent.futures.as_completed(future_to_cursor):
                    cursor = future_to_cursor[future]
                    try:
                        pages.append((cursor, future.result()))
                    except Exception as e:
                        result['warnings'].append(f'bioRxiv API 分页 {cursor} 获取失败: {e}')
                for _, payload in sorted(pages):
                    if result['fetched'] >= max_results:
                        break
                    record_collection(payload.get('collection') or [])

            if scan_limit < total:
                result['warnings'].append(
                    f'bioRxiv 区间内共有 {total} 条记录，本次为控制耗时扫描前 {scan_limit} 条'
                )

            result['api_success'] = True
            _fetch_log.info('bioRxiv API 抓取完成 %s: fetched=%d inserted=%d dup=%d',
                            source_name, result['fetched'], result['inserted'], result['duplicates'])
        except Exception as e:
            result['errors'].append(f'bioRxiv API 请求失败，回退 RSS: {e}')
            _fetch_log.warning('bioRxiv API 失败 %s: %s', source_name, e)
        return result

    def fetch_arxiv(self, category="cs.AI", start_date=None, end_date=None, max_results=20, source_name=None, return_details=False):
        # 订阅指定预印本类别，例如 cs.AI (人工智能)
        base_url = 'http://export.arxiv.org/api/query?'
        # arxiv 支持按照提交时间排序
        query = f'search_query=cat:{category}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=desc'
        url = base_url + query
        
        if not source_name:
            source_name = f"arXiv: {category}"
            
        result = self._parse_arxiv_feed(url, source=source_name, start_date=start_date, end_date=end_date, return_details=True)
        return result if return_details else result['inserted']

    @staticmethod
    def _parse_sciencedirect_summary(summary_html):
        """从 ScienceDirect RSS 的 HTML summary 中提取元数据。

        ScienceDirect/Elsevier RSS feed 仅返回极少字段（标题、链接、HTML摘要），
        DOI、日期、作者全部嵌在 <p> 标签中。此方法解析这些隐藏字段。

        返回 (published_date_str, author_str, journal_str)。
        """
        import re as _re
        date_str = ''
        author_str = ''
        journal_str = ''

        if not summary_html:
            return date_str, author_str, journal_str

        text = _re.sub(r'<[^>]+>', ' ', str(summary_html))
        text = _re.sub(r'\s+', ' ', text).strip()

        # Publication date: stop before "Source:" or "Author(s):" or end
        m = _re.search(r'Publication\s+date:\s*(.+?)(?=\s*(?:Source:|Author\s*\(s\):)|$)', text, _re.I)
        if m:
            date_str = m.group(1).strip()

        # Author(s): stop before "Source:" or end
        m = _re.search(r'Author\s*\(s\):\s*(.+?)(?=\s*(?:Source:)|$)', text, _re.I)
        if m:
            author_str = m.group(1).strip()

        # Source: stop before "Author(s):" or end
        m = _re.search(r'Source:\s*(.+?)(?=\s*(?:Author\s*\(s\):)|$)', text, _re.I)
        if m:
            journal_str = m.group(1).strip()

        return date_str, author_str, journal_str

    @staticmethod
    def _resolve_sciencedirect_doi(entry_id, title, timeout=5):
        """通过 Crossref API 按标题搜索 ScienceDirect 论文的 DOI。

        ScienceDirect RSS 的 entry id 是 PII URL（不含DOI），
        通过 Crossref 标题搜索可以找回真实 DOI。
        每批次最多查询 10 篇以防止 Crossref 限流。

        返回 DOI 字符串或 None。
        """
        if not hasattr(LiteratureFetcher, '_sd_doi_cache'):
            LiteratureFetcher._sd_doi_cache = {}
        if not hasattr(LiteratureFetcher, '_sd_doi_count'):
            LiteratureFetcher._sd_doi_count = 0

        cache = LiteratureFetcher._sd_doi_cache
        # 每个 fetch_rss 调用最多查 10 次 Crossref
        if LiteratureFetcher._sd_doi_count >= 10:
            return None
        # 仅命中正向缓存时直接返回（不缓存 None，允许重试）
        if entry_id in cache and cache[entry_id] is not None:
            return cache[entry_id]

        import json as _json
        import urllib.parse as _up
        import urllib.request as _ur
        if not title:
            return None
        safe_title = title[:300]
        try:
            q = _up.quote(safe_title)
            url = f'https://api.crossref.org/works?query.title={q}&rows=1'
            req = _ur.Request(url, headers={
                'User-Agent': 'FolPaper/1.0 (mailto:folpaper@example.com)'
            })
            with _ur.urlopen(req, timeout=timeout) as resp:
                data = _json.loads(resp.read().decode('utf-8'))
            items = (data.get('message') or {}).get('items') or []
            LiteratureFetcher._sd_doi_count += 1
            doi = None
            if items:
                doi = normalize_doi(items[0].get('DOI'))
            # 只缓存成功结果，失败不缓存以便重试
            if doi:
                cache[entry_id] = doi
            return doi
        except Exception:
            return None

    def fetch_rss(self, feed_url, start_date=None, end_date=None, source_name=None, return_details=False):
        if not source_name:
            source_name = f"RSS: {feed_url}"
        result = self._new_result(source_name, 'rss')
        result['security_blocked'] = False
        # 每次抓取重置 Crossref DOI 查询计数器（每批上限 10 次）
        LiteratureFetcher._sd_doi_count = 0
        _fetch_log.info('开始抓取 %s (%d级)', source_name, 2 + (1 if self._get_flaresolverr_url() else 1))

        # ── 三级 RSS 抓取：直连 → Cookie 预取 → Patchright/FlareSolverr ──
        # 每级失败（且是安全拦截）时自动降级到下一级，全失败才标记 security_blocked
        feed_data = None
        seen_security = False
        attempts = [
            ('direct', lambda: self._fetch_feed_data(feed_url)),
            ('cookie', lambda: self._fetch_with_cookie_session(feed_url)),
        ]
        if self._get_flaresolverr_url():
            attempts.append(('flaresolverr', lambda: self._fetch_via_flaresolverr(feed_url)))
        else:
            attempts.append(('patchright', lambda: self._fetch_via_patchright(feed_url)))
        last_idx = len(attempts) - 1

        for attempt, (label, fetcher_fn) in enumerate(attempts):
            data, error, is_security = fetcher_fn()
            if error is None:
                _fetch_log.info('%s 成功 (attempt %d/%d)', label, attempt + 1, last_idx + 1)
                feed_data = data
                break
            if is_security:
                seen_security = True
                if attempt < last_idx:
                    _fetch_log.warning('%s 安全拦截 → 降级下一级', label)
                    result['warnings'].append(f'{label} 被安全拦截，尝试下一级')
                else:
                    _fetch_log.error('%s 安全拦截 → 全部失败，触发补源', label)
                    result['errors'].append(error)
                    result['security_blocked'] = True
            else:
                # 非安全错误（网络故障等），但若前级已确认是安全拦截，仍标记 blocked
                _fetch_log.warning('%s 非安全错误: %s (seen_security=%s)', label, error, seen_security)
                if seen_security:
                    result['errors'].append(error)
                    result['security_blocked'] = True
                else:
                    result['errors'].append(error)
                break
        else:
            # 所有尝试都被安全拦截
            if not result.get('errors'):
                result['errors'].append('RSS 所有抓取方式均失败')
            _fetch_log.error('全部抓取失败: %s', '; '.join(result['errors']))
            print(f"Failed to fetch RSS {feed_url}: {'; '.join(result['errors'])}")
            return result if return_details else 0

        if feed_data is None:
            if not result.get('errors'):
                result['errors'].append('RSS 抓取返回空数据')
            return result if return_details else 0

        # 兜底检测：HTTP 200 但内容是安全页面（如 Cookie/FlareSolverr 未能完全绕过）
        if self._looks_like_security_challenge(feed_data):
            result['errors'].append('RSS 返回安全验证页面，无法直接解析，已尝试使用 OpenAlex 补源')
            result['security_blocked'] = True
            return result if return_details else 0

        feed = feedparser.parse(feed_data)
        if getattr(feed, 'bozo', False):
            result['warnings'].append(f"RSS 解析告警: {getattr(feed, 'bozo_exception', '')}")
        result['fetched'] = len(feed.entries)
        
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

                # ScienceDirect/Elsevier RSS 的所有元数据藏在 HTML summary 中
                sd_date, sd_authors, sd_journal = self._parse_sciencedirect_summary(summary)
                if not published and sd_date:
                    published = sd_date

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
                if author_str == 'Unknown' and sd_authors:
                    author_str = sd_authors

                # 从 ScienceDirect summary 提取期刊名
                journal_name = sd_journal or ''

                
                # 尝试直接从 RSS 节点获取 DOI（如 prism:doi 或 dc:identifier）
                doi = normalize_doi(entry.get('prism_doi') or entry.get('dc_identifier'))
                if not doi:
                    doi = extract_doi(link, article_id, summary)
                # ScienceDirect RSS 不含 DOI（PII URL），尝试 Crossref 标题搜索
                if not doi and ('sciencedirect' in str(link).lower() or 'sciencedirect' in str(article_id).lower()):
                    doi = self._resolve_sciencedirect_doi(article_id, title)
                
                article_data = {
                    'article_id': str(article_id),
                    'title': str(title),
                    'authors': str(author_str),
                    'summary': str(summary),
                    'link': str(link),
                    'published': parse_to_iso(str(published)), # 转换为 ISO 格式保证排序准确
                    'source': source_name,
                    'doi': doi, # 提取 DOI 供归档使用
                    'journal': journal_name, # 从 summary 或 RSS 元数据提取的期刊名
                }
                
                # 以增量形式添加，利用数据库 UNIQUE 约束去重
                self._record_article(article_data, result)
            except Exception as e:
                # 遇到解析异常时打印错误，防止阻断其他正常节点的拉取
                result['errors'].append(f"解析 RSS 条目失败: {e}")
                print(f"解析 RSS 条目时发生异常，已跳过该条目: {e}")
                continue

        _fetch_log.info('抓取完成 %s: fetched=%d inserted=%d dup=%d blocked=%s',
                        source_name, result['fetched'], result['inserted'],
                        result['duplicates'], result['security_blocked'])
        return result if return_details else result['inserted']

    def fetch_manual_arxiv(self, arxiv_id):
        # 独立功能：手动提交文献需求（通过 arXiv ID）
        base_url = 'http://export.arxiv.org/api/query?'
        query = f'id_list={arxiv_id}'
        url = base_url + query
        return self._parse_arxiv_feed(url, source="Manual Entry")

    def _parse_arxiv_feed(self, url, source, start_date=None, end_date=None, return_details=False):
        result = self._new_result(source, 'arxiv')
        # 解析 arXiv XML 数据流
        feed_data, error, _ = self._fetch_feed_data(url)
        if error:
            result['errors'].append(error)
            print(f"Failed to fetch arXiv {url}: {error}")
            return result if return_details else 0
        feed = feedparser.parse(feed_data)
        
        result['fetched'] = len(feed.entries)
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
                
                self._record_article(article_data, result)
            except Exception as e:
                result['errors'].append(f"解析 arXiv 条目失败: {e}")
                print(f"解析 arXiv 条目时发生异常，已跳过该条目: {e}")
                continue
                
        return result if return_details else result['inserted']
