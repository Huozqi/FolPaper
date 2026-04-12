import urllib.request
import urllib.parse
import json
import ssl
import time

class OpenAlexService:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://api.openalex.org"
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def get_source_id(self, journal_name):
        """支持传入逗号分隔的多个期刊名，返回匹配的 (source_ids, display_names) 列表"""
        journal_names = [name.strip() for name in journal_name.split(',') if name.strip()]
        matched_sources = []
        
        for name in journal_names:
            encoded_name = urllib.parse.quote(name)
            url = f"{self.base_url}/sources?search={encoded_name}"
            if self.api_key:
                url += f"&api_key={self.api_key}"
            
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=20) as response:
                    data = json.loads(response.read())
                    if data.get('results'):
                        # 返回最匹配的 source id 和 display_name
                        matched_sources.append({
                            'id': data['results'][0]['id'].split('/')[-1],
                            'display_name': data['results'][0]['display_name']
                        })
            except Exception as e:
                print(f"Error fetching source ID for {name}: {e}")
                
        return matched_sources

    def fetch_works(self, source_ids, start_date, end_date, max_results=500):
        works = []
        
        # 将所有的 source_id 用管道符(|)连接，代表 OR 查询
        source_id_str = "|".join(source_ids)
        
        page = 1
        per_page = 200
        
        while len(works) < max_results:
            url = f"{self.base_url}/works?filter=primary_location.source.id:{source_id_str},from_publication_date:{start_date},to_publication_date:{end_date}&per-page={per_page}&page={page}"
            if self.api_key:
                url += f"&api_key={self.api_key}"
                
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=30) as response:
                    data = json.loads(response.read())
                    results = data.get('results', [])
                    if not results:
                        break
                    
                    for item in results:
                        # 提取摘要
                        abstract = ""
                        abstract_inverted = item.get('abstract_inverted_index')
                        if abstract_inverted:
                            words = []
                            for word, positions in abstract_inverted.items():
                                for pos in positions:
                                    words.append((pos, word))
                            words.sort(key=lambda x: x[0])
                            abstract = " ".join([w[1] for w in words])
                        
                        # 提取 DOI
                        doi = item.get('doi', '')
                        if doi:
                            doi = doi.replace('https://doi.org/', '')
                            
                        # 提取作者
                        authors = ", ".join([a.get('author', {}).get('display_name', '') for a in item.get('authorships', []) if a.get('author')])
                        
                        journal_display = item.get('primary_location', {}).get('source', {}).get('display_name', '')
                        
                        works.append({
                            'id': item.get('id', ''),
                            'title': item.get('title', '') or 'Untitled',
                            'abstract': abstract,
                            'doi': doi,
                            'publication_date': item.get('publication_date', ''),
                            'publication_year': item.get('publication_year', ''),
                            'journal': journal_display,
                            'authors': authors,
                            'is_related': '',
                            'llm_reason': ''
                        })
                        if len(works) >= max_results:
                            break
                            
                    total = data.get('meta', {}).get('count', 0)
                    if page * per_page >= total or len(works) >= total:
                        break
                    page += 1
                    time.sleep(0.1) # 遵守 API 礼貌池策略
            except Exception as e:
                print(f"Error fetching works page {page}: {e}")
                break
        return works

    def clean_and_group_data(self, works):
        """数据清洗：去重、按年份/期刊规整"""
        seen = set()
        cleaned = []
        for w in works:
            # 去重：优先用 DOI，没有则用小写标题
            key = w['doi'] if w['doi'] else w['title'].lower()
            if key and key not in seen:
                seen.add(key)
                cleaned.append(w)
                
        # 按年份降序、期刊字母序排序
        cleaned.sort(key=lambda x: (x['publication_year'] or 0, x['journal']), reverse=True)
        return cleaned

    def generate_stats(self, works):
        """生成可视化所需的统计信息"""
        stats = {
            'years': {},
            'journals': {}
        }
        for w in works:
            year = str(w['publication_year']) if w['publication_year'] else 'Unknown'
            journal = w['journal'] or 'Unknown'
            
            stats['years'][year] = stats['years'].get(year, 0) + 1
            stats['journals'][journal] = stats['journals'].get(journal, 0) + 1
            
        # 按年份排序
        sorted_years = dict(sorted(stats['years'].items(), reverse=True))
        stats['years'] = sorted_years
        
        # 期刊按数量降序排序
        sorted_journals = dict(sorted(stats['journals'].items(), key=lambda item: item[1], reverse=True))
        stats['journals'] = sorted_journals
        
        return stats
