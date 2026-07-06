import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


def _first_text(value):
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    if value:
        return str(value).strip()
    return ''


def _date_parts_to_iso(date_parts):
    if not date_parts:
        return ''
    parts = date_parts[0] if isinstance(date_parts[0], list) else date_parts
    if not parts:
        return ''
    year = str(parts[0]).zfill(4)
    month = str(parts[1]).zfill(2) if len(parts) > 1 else '01'
    day = str(parts[2]).zfill(2) if len(parts) > 2 else '01'
    return f'{year}-{month}-{day}T00:00:00Z'


class CrossrefService:
    BASE_URL = 'https://api.crossref.org/works'
    _request_lock = threading.Lock()
    _last_request_at = 0.0
    MIN_INTERVAL_SECONDS = 1.2
    MAX_RETRIES = 4

    def __init__(self, mailto='developer@example.com'):
        self.mailto = mailto

    def _wait_for_rate_limit(self):
        with self._request_lock:
            now = time.monotonic()
            wait_seconds = self.MIN_INTERVAL_SECONDS - (now - self.__class__._last_request_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self.__class__._last_request_at = time.monotonic()

    def _request_json(self, url, timeout=30):
        for attempt in range(self.MAX_RETRIES):
            self._wait_for_rate_limit()
            req = urllib.request.Request(url, headers={'User-Agent': f'FolPaper/1.0 (mailto:{self.mailto})'})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as error:
                if error.code not in (429, 503) or attempt == self.MAX_RETRIES - 1:
                    raise
                retry_after = error.headers.get('Retry-After') if error.headers else None
                try:
                    sleep_seconds = float(retry_after) if retry_after else self.MIN_INTERVAL_SECONDS * (2 ** (attempt + 1))
                except ValueError:
                    sleep_seconds = self.MIN_INTERVAL_SECONDS * (2 ** (attempt + 1))
                time.sleep(min(max(sleep_seconds, self.MIN_INTERVAL_SECONDS), 60.0))

    def _build_filters(self, issn, start_date, end_date):
        filters = ['type:journal-article']
        if issn:
            filters.append(f'issn:{issn}')
        if start_date:
            filters.append(f'from-pub-date:{start_date.strftime("%Y-%m-%d")}')
        if end_date:
            filters.append(f'until-pub-date:{end_date.strftime("%Y-%m-%d")}')
        return ','.join(filters)

    def _build_url(self, query, issn, start_date, end_date, rows):
        params = {
            'filter': self._build_filters(issn, start_date, end_date),
            'rows': str(rows),
            'sort': 'published',
            'order': 'desc',
            'select': 'DOI,title,author,abstract,URL,published-print,published-online,published,container-title,ISSN',
            'mailto': self.mailto,
        }
        if query and not issn:
            params['query.container-title'] = query
        return self.BASE_URL + '?' + urllib.parse.urlencode(params)

    def _clean_abstract(self, abstract):
        if not abstract:
            return ''
        text = re.sub(r'<[^>]+>', '', abstract)
        return re.sub(r'\s+', ' ', text).strip()

    def _authors(self, item):
        names = []
        for author in item.get('author') or []:
            given = author.get('given', '')
            family = author.get('family', '')
            name = ' '.join(part for part in [given, family] if part).strip()
            if name:
                names.append(name)
        return ', '.join(names)

    def _published(self, item):
        for key in ['published-online', 'published-print', 'published']:
            date = _date_parts_to_iso((item.get(key) or {}).get('date-parts') or [])
            if date:
                return date
        return ''

    def _matches_journal(self, item, query, issn):
        if issn:
            item_issns = {str(value).lower() for value in item.get('ISSN') or []}
            return issn.lower() in item_issns
        if not query:
            return True
        query_norm = re.sub(r'[^a-z0-9]+', ' ', query.lower()).strip()
        titles = item.get('container-title') or []
        for title in titles:
            title_norm = re.sub(r'[^a-z0-9]+', ' ', str(title).lower()).strip()
            if query_norm == title_norm:
                return True
        return False

    def search_journal(self, journal_name='', issn='', start_date=None, end_date=None, rows=200):
        if not journal_name and not issn:
            return []
        url = self._build_url(journal_name, issn, start_date, end_date, rows)
        try:
            data = self._request_json(url)
        except Exception as error:
            print(f'Crossref search failed for {journal_name or issn}: {error}')
            return []

        items = data.get('message', {}).get('items', [])
        results = []
        for item in items:
            doi = (item.get('DOI') or '').strip().lower()
            title = _first_text(item.get('title'))
            if not doi or not title:
                continue
            if not self._matches_journal(item, journal_name, issn):
                continue
            journal = _first_text(item.get('container-title'))
            results.append({
                'article_id': f'crossref:{doi}',
                'title': title,
                'authors': self._authors(item),
                'summary': self._clean_abstract(item.get('abstract', '')),
                'link': item.get('URL') or f'https://doi.org/{doi}',
                'published': self._published(item),
                'source': journal or journal_name,
                'journal': journal,
                'doi': doi,
            })
        return results
