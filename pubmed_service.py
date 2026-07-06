import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import time

class PubMedService:
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    # NCBI E-utilities: 无 API key 时限 3 req/s，留余量 2 req/s
    _MIN_INTERVAL = 0.5
    _last_request = 0

    def __init__(self, tool_name="FolPaper", email="researcher@example.com"):
        self.tool_name = tool_name
        self.email = email

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self._MIN_INTERVAL:
            time.sleep(self._MIN_INTERVAL - elapsed)
        self._last_request = time.time()

    def search_journal(self, journal_name='', issn='', retmax=200, start_date=None, end_date=None):
        terms = []
        if issn:
            terms.append(f'{issn}[ISSN]')
        if journal_name:
            terms.append(f'"{journal_name}"[Journal]')
        if not terms:
            return []
        term = ' OR '.join(terms)
        if len(terms) > 1:
            term = f'({term})'
        return self.search(term, retmax=retmax, start_date=start_date, end_date=end_date, sort="pub+date")

    def search_by_doi(self, doi):
        doi = (doi or '').strip()
        if not doi:
            return None
        results = self.search(f'{doi}[AID]', retmax=1, sort='relevance')
        return results[0] if results else None

    def search(self, term, retmax=20, start_date=None, end_date=None, sort="pub+date"):
        # 严格依从 E-utilities 规范：
        # https://www.ncbi.nlm.nih.gov/books/NBK25497/
        # 添加 tool 和 email 参数
        query = urllib.parse.quote(term)
        
        # 处理日期限制 (格式: YYYY/MM/DD)
        date_filter = ""
        if start_date and end_date:
            mindate = start_date.strftime("%Y/%m/%d")
            maxdate = end_date.strftime("%Y/%m/%d")
            # 注意：PubMed API 中，只有在没有其他 [Filter] 或明确时间限制时，
            # 追加 datetype 等参数才不会产生冲突。对于基于流的后台订阅抓取，
            # 如果原始 query 里自带了 2023[PDAT]，追加 mindate 会导致搜索失败。
            # 另外为了避免大跨度拉取时经常触发 PubMed 返回空数据，
            # 这里如果 start_date 和 end_date 的跨度极大（比如超过 1000 天）且用户搜索词比较短，
            # 不追加明确的时间段限制，让其自然拉取最新。
            delta_days = (end_date - start_date).days
            if delta_days < 1000:
                date_filter_str = f" AND ({mindate}:{maxdate}[PDAT])"
                query = urllib.parse.quote(term + date_filter_str)
            else:
                query = urllib.parse.quote(term)
        else:
            query = urllib.parse.quote(term)
            
        # 1. esearch
        search_url = f"{self.BASE_URL}esearch.fcgi?db=pubmed&term={query}&retmode=json&retmax={retmax}&sort={sort}&tool={self.tool_name}&email={self.email}"
        self._rate_limit()
        try:
            req = urllib.request.Request(search_url)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"PubMed search failed: {e}")
            return []

        id_list = data.get('esearchresult', {}).get('idlist', [])
        if not id_list:
            print(f"PubMed search returned empty for: {search_url}")
            return []

        # 2. esummary (获取基本信息) - 分批 POST 请求
        results = []
        batch_size = 200
        for i in range(0, len(id_list), batch_size):
            batch_ids = id_list[i:i + batch_size]
            ids = ",".join(batch_ids)

            summary_params = {
                'db': 'pubmed',
                'id': ids,
                'retmode': 'json',
                'tool': self.tool_name,
                'email': self.email
            }

            self._rate_limit()
            try:
                data_encoded = urllib.parse.urlencode(summary_params).encode('utf-8')
                req2 = urllib.request.Request(f"{self.BASE_URL}esummary.fcgi", data=data_encoded)
                with urllib.request.urlopen(req2, timeout=30) as response2:
                    summary_data = json.loads(response2.read().decode('utf-8'))
            except Exception as e:
                print(f"PubMed summary failed for batch {i}: {e}")
                continue

            batch_results = []
            result_dict = summary_data.get('result', {})
            for uid in batch_ids:
                item = result_dict.get(uid)
                if item:
                    title = item.get('title', '')
                    pubdate = item.get('pubdate', '')
                    source = item.get('source', '')
                    authors = ", ".join([a.get('name', '') for a in item.get('authors', [])])
                    doi = ''
                    for articleid in item.get('articleids', []):
                        if articleid.get('idtype') == 'doi':
                            doi = articleid.get('value')
                    
                    # 转换 pubdate 到标准 ISO 格式
                    iso_pubdate = pubdate
                    try:
                        # 尝试解析类似于 "2023 Oct 12" 或 "2023" 的日期
                        # 为了简单，直接使用提取的年份或返回原字符串，因为日期格式多变
                        parts = pubdate.split()
                        if len(parts) >= 1 and parts[0].isdigit():
                            year = parts[0]
                            month = "01"
                            day = "01"
                            
                            # 尝试映射月份
                            if len(parts) >= 2:
                                month_map = {
                                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                                }
                                month_str = parts[1][:3]
                                if month_str in month_map:
                                    month = month_map[month_str]
                                    
                            # 尝试获取日期
                            if len(parts) >= 3 and parts[2].isdigit():
                                day = parts[2].zfill(2)
                                
                            iso_pubdate = f"{year}-{month}-{day}"
                        elif pubdate:
                            # Fallback for unexpected formats, ensure it's not empty and resembles a date
                            # Try to find a 4 digit year
                            import re
                            match = re.search(r'\b(19|20)\d{2}\b', pubdate)
                            if match:
                                iso_pubdate = f"{match.group(0)}-01-01"
                    except:
                        pass
                        
                    # 极端情况下如果无法解析出任何日期，默认给一个当天的日期，防止入库被 prune 清理掉
                    if not iso_pubdate or not iso_pubdate[0].isdigit():
                        iso_pubdate = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    
                    # 如果是按时间截断（如只有日期），确保能进行正常的字符串比较
                    if len(iso_pubdate) == 10:
                        iso_pubdate += "T00:00:00"
                    
                    # 注意：如果 PubMed API 返回的时间是将来的时间（比如 2026-12-31）
                    # 为了不让它们在列表里显得很奇怪或者永远排在最前面，如果年份超过当前年份，修正为当前时间
                    try:
                        current_year = datetime.now(timezone.utc).year
                        parsed_year = int(iso_pubdate[:4])
                        if parsed_year > current_year:
                            iso_pubdate = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
                    except:
                        pass

                    # 注意：SQLite 里 prune 语句用的是 substr(published, 1, 10) < cutoff_date
                    # 对于某些直接带有奇怪字符的，强制修正前10位为标准日期
                    if len(iso_pubdate) >= 10 and not iso_pubdate[:4].isdigit():
                        iso_pubdate = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
                    elif len(iso_pubdate) > 10 and iso_pubdate[4] != '-':
                        # 防御：有些可能解析出 20260326T10:00:00 这种格式，强制变成 YYYY-MM-DD
                        iso_pubdate = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")

                    batch_results.append({
                        'article_id': f"pubmed:{uid}",
                        'title': title,
                        'authors': authors,
                        'published': iso_pubdate, # 供数据库排序
                        'source': f"PubMed",
                        'journal': source, # 原有 source 为期刊名
                        'doi': doi,
                        'link': f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                        'summary': '' # 稍后通过 efetch 获取
                    })
            
            # 3. efetch (获取摘要) - POST 请求
            fetch_params = {
                'db': 'pubmed',
                'id': ids,
                'retmode': 'xml',
                'tool': self.tool_name,
                'email': self.email
            }
            try:
                data_encoded = urllib.parse.urlencode(fetch_params).encode('utf-8')
                req3 = urllib.request.Request(f"{self.BASE_URL}efetch.fcgi", data=data_encoded)
                with urllib.request.urlopen(req3, timeout=60) as response3:
                    xml_data = response3.read()
                    root = ET.fromstring(xml_data)
                    for article in root.findall('.//PubmedArticle'):
                        pmid = article.findtext('.//PMID')
                        abstract_texts = article.findall('.//AbstractText')
                        abstract = " ".join([a.text for a in abstract_texts if a.text])
                        for r in batch_results:
                            if r['article_id'] == f"pubmed:{pmid}":
                                r['summary'] = abstract
            except Exception as e:
                print(f"PubMed fetch abstract failed for batch {i}:", e)
                
            results.extend(batch_results)
            
        return results
