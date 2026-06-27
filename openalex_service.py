import json
import re
import time
import urllib.parse
import urllib.request


class OpenAlexService:
    CONFERENCE_RULES = (
        {
            'rule_id': 'neurips',
            'aliases': ['neurips', 'neural information processing systems', 'advances in neural information processing systems'],
            'search_terms': ['Neural Information Processing Systems'],
            'include_terms': ['neural information processing systems', 'advances in neural information processing systems'],
            'exclude_terms': ['workshop', 'companion'],
            'doi_prefixes': [],
            'doi_exclude_prefixes': []
        },
        {
            'rule_id': 'icml',
            'aliases': ['icml', 'international conference on machine learning'],
            'search_terms': ['International Conference on Machine Learning'],
            'include_terms': ['international conference on machine learning'],
            'exclude_terms': ['applications', 'cybernetics', 'big data', 'intelligent systems engineering', 'applied machine learning'],
            'doi_prefixes': [],
            'doi_exclude_prefixes': []
        },
        {
            'rule_id': 'iclr',
            'aliases': ['iclr', 'international conference on learning representations'],
            'search_terms': ['International Conference on Learning Representations'],
            'include_terms': ['international conference on learning representations'],
            'exclude_terms': ['workshop', 'companion'],
            'doi_prefixes': [],
            'doi_exclude_prefixes': []
        },
        {
            'rule_id': 'aaai',
            'aliases': ['aaai', 'aaai conference on artificial intelligence', 'proceedings of the aaai conference on artificial intelligence'],
            'search_terms': ['AAAI Conference on Artificial Intelligence'],
            'include_terms': ['proceedings of the aaai conference on artificial intelligence', 'aaai conference on artificial intelligence'],
            'exclude_terms': ['interactive digital entertainment', 'web and social media', 'workshop', 'companion'],
            'doi_prefixes': [],
            'doi_exclude_prefixes': []
        },
        {
            'rule_id': 'ijcai',
            'aliases': ['ijcai', 'international joint conference on artificial intelligence'],
            'search_terms': ['International Joint Conference on Artificial Intelligence', 'Proceedings of the Thirty-Third International Joint Conference on Artificial Intelligence', 'Proceedings of the Thirty-Fourth International Joint Conference on Artificial Intelligence'],
            'include_terms': ['international joint conference on artificial intelligence'],
            'exclude_terms': ['workshop', 'companion'],
            'doi_prefixes': ['10.24963/ijcai.2024/', '10.24963/ijcai.2025/'],
            'doi_exclude_prefixes': []
        },
        {
            'rule_id': 'cvpr',
            'aliases': ['cvpr', 'computer vision and pattern recognition', 'ieee cvf conference on computer vision and pattern recognition'],
            'search_terms': ['IEEE/CVF Conference on Computer Vision and Pattern Recognition', 'CVPR 2024', 'CVPR 2025'],
            'include_terms': ['conference on computer vision and pattern recognition'],
            'exclude_terms': ['workshop', 'cvprw', 'energy minimization methods'],
            'doi_prefixes': ['10.1109/cvpr52733.2024.', '10.1109/cvpr59857.2025.', '10.1109/cvpr52729.2023.']
        },
        {
            'rule_id': 'iccv',
            'aliases': ['iccv', 'international conference on computer vision'],
            'search_terms': ['International Conference on Computer Vision'],
            'include_terms': ['international conference on computer vision'],
            'exclude_terms': ['workshop', 'companion'],
            'doi_prefixes': [],
            'doi_exclude_prefixes': []
        },
        {
            'rule_id': 'eccv',
            'aliases': ['eccv', 'european conference on computer vision'],
            'search_terms': ['European Conference on Computer Vision'],
            'include_terms': ['european conference on computer vision'],
            'exclude_terms': ['workshop', 'companion'],
            'doi_prefixes': [],
            'doi_exclude_prefixes': []
        },
        {
            'rule_id': 'acl',
            'aliases': ['acl', 'annual meeting of the association for computational linguistics'],
            'search_terms': ['Annual Meeting of the Association for Computational Linguistics', 'Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics', 'Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics'],
            'include_terms': ['annual meeting of the association for computational linguistics', 'meeting of the association for computational linguistics'],
            'exclude_terms': ['transactions of the association for computational linguistics', 'findings of the association for computational linguistics', 'north american chapter', 'european chapter', 'student research workshop', 'system demonstrations', 'tutorial'],
            'doi_prefixes': ['10.18653/v1/2024.acl-long.', '10.18653/v1/2024.acl-short.', '10.18653/v1/2025.acl-long.', '10.18653/v1/2025.acl-short.'],
            'doi_exclude_prefixes': ['10.18653/v1/2024.naacl-', '10.18653/v1/2025.naacl-', '10.18653/v1/2024.findings-acl.', '10.18653/v1/2025.findings-acl.']
        },
        {
            'rule_id': 'emnlp',
            'aliases': ['emnlp', 'conference on empirical methods in natural language processing'],
            'search_terms': ['Conference on Empirical Methods in Natural Language Processing', 'Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing'],
            'include_terms': ['conference on empirical methods in natural language processing'],
            'exclude_terms': ['findings', 'workshop', 'tutorial'],
            'doi_prefixes': ['10.18653/v1/2024.emnlp-main.', '10.18653/v1/2024.emnlp-short.'],
            'doi_exclude_prefixes': ['10.18653/v1/2024.findings-emnlp.']
        },
        {
            'rule_id': 'naacl',
            'aliases': ['naacl', 'north american chapter of the association for computational linguistics'],
            'search_terms': ['North American Chapter of the Association for Computational Linguistics', 'Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics'],
            'include_terms': ['north american chapter of the association for computational linguistics'],
            'exclude_terms': ['findings', 'workshop', 'tutorial'],
            'doi_prefixes': ['10.18653/v1/2024.naacl-long.', '10.18653/v1/2024.naacl-short.'],
            'doi_exclude_prefixes': ['10.18653/v1/2024.acl-', '10.18653/v1/2025.acl-', '10.18653/v1/2024.findings-naacl.']
        },
        {
            'rule_id': 'kdd',
            'aliases': ['kdd', 'knowledge discovery and data mining', 'acm sigkdd conference on knowledge discovery and data mining'],
            'search_terms': ['ACM SIGKDD Conference on Knowledge Discovery and Data Mining', 'Proceedings of the 30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining', 'Proceedings of the 31st ACM SIGKDD Conference on Knowledge Discovery and Data Mining'],
            'include_terms': ['acm sigkdd conference on knowledge discovery and data mining', 'knowledge discovery and data mining'],
            'exclude_terms': ['workshop', 'pacific asia conference', 'principles of data mining', 'biological knowledge discovery', 'cryptography'],
            'doi_prefixes': ['10.1145/3637528.', '10.1145/3690624.', '10.1145/3711896.'],
            'doi_exclude_prefixes': []
        },
        {
            'rule_id': 'www',
            'aliases': ['www', 'the web conference', 'acm web conference', 'world wide web conference'],
            'search_terms': ['The Web Conference', 'Proceedings of the ACM Web Conference 2024', 'Proceedings of the ACM Web Conference 2025'],
            'include_terms': ['the web conference', 'acm web conference'],
            'exclude_terms': ['companion', 'web and social media', 'web intelligence', 'web search and data mining', 'www alt'],
            'doi_prefixes': ['10.1145/3589334.', '10.1145/3696410.'],
            'doi_exclude_prefixes': ['10.1145/3589335.', '10.1145/3701716.']
        },
        {
            'rule_id': 'sigir',
            'aliases': ['sigir', 'international acm sigir conference on research and development in information retrieval', 'research and development in information retrieval'],
            'search_terms': ['International ACM SIGIR Conference on Research and Development in Information Retrieval', 'Proceedings of the 47th International ACM SIGIR Conference on Research and Development in Information Retrieval', 'Proceedings of the 48th International ACM SIGIR Conference on Research and Development in Information Retrieval'],
            'include_terms': ['international acm sigir conference on research and development in information retrieval', 'sigir conference on research and development in information retrieval'],
            'exclude_terms': ['forum', 'workshop', 'companion'],
            'doi_prefixes': ['10.1145/3626772.', '10.1145/3726302.'],
            'doi_exclude_prefixes': ['10.1145/3673791.', '10.1145/3767695.']
        },
    )
    ALLOWED_CONFERENCE_WORK_TYPES = {'article', 'preprint', 'review'}
    MAX_CONFERENCE_SEARCH_PAGES = 5

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://api.openalex.org"

    def _normalize_text(self, value):
        return re.sub(r'[^a-z0-9]+', ' ', (value or '').lower()).strip()

    def _append_api_key(self, url):
        if self.api_key:
            return f"{url}&api_key={self.api_key}"
        return url

    def _request_json(self, url, timeout=30):
        req = urllib.request.Request(self._append_api_key(url))
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read())

    def _extract_source_id(self, source):
        source_id = source.get('id', '')
        return source_id.split('/')[-1] if source_id else ''

    def _resolve_conference_rule(self, conference):
        candidates = [
            self._normalize_text(conference.get('key', '')),
            self._normalize_text(conference.get('name', '')),
            self._normalize_text(conference.get('query', '')),
        ]
        candidates = [candidate for candidate in candidates if candidate]

        exact_matches = []
        partial_matches = []
        for rule in self.CONFERENCE_RULES:
            aliases = [self._normalize_text(alias) for alias in rule['aliases']]
            if any(candidate == alias for candidate in candidates for alias in aliases):
                exact_matches.append(rule)
                continue
            if any(candidate in alias or alias in candidate for candidate in candidates for alias in aliases):
                partial_matches.append(rule)

        if exact_matches:
            return exact_matches[0]
        if partial_matches:
            return partial_matches[0]
        return None

    def _conference_spec(self, conference):
        rule = self._resolve_conference_rule(conference)
        base_name = conference.get('name') or conference.get('query') or conference.get('key') or ''
        query = conference.get('query') or base_name
        if not rule:
            normalized_query = self._normalize_text(query)
            return {
                'rule_id': self._normalize_text(conference.get('key') or base_name),
                'name': base_name,
                'search_terms': [query],
                'include_terms': [normalized_query] if normalized_query else [],
                'exclude_terms': [],
                'doi_prefixes': [],
                'doi_exclude_prefixes': [],
                'allowed_source_types': {'conference'},
            }

        return {
            'rule_id': rule['rule_id'],
            'name': base_name,
            'search_terms': rule['search_terms'],
            'include_terms': [self._normalize_text(term) for term in rule['include_terms']],
            'exclude_terms': [self._normalize_text(term) for term in rule['exclude_terms']],
            'doi_prefixes': [prefix.lower() for prefix in rule.get('doi_prefixes', [])],
            'doi_exclude_prefixes': [prefix.lower() for prefix in rule.get('doi_exclude_prefixes', [])],
            'allowed_source_types': {'conference'},
        }

    def _source_matches_conference(self, source, conf_spec):
        source_name = self._normalize_text(source.get('display_name', ''))
        if not source_name:
            return False

        source_type = (source.get('type') or '').lower()
        if source_type and source_type not in conf_spec['allowed_source_types']:
            return False
        if any(term in source_name for term in conf_spec['exclude_terms']):
            return False
        return any(term in source_name for term in conf_spec['include_terms'])

    def _item_sources(self, item):
        sources = []
        seen = set()

        for raw_source in [
            (item.get('primary_location') or {}).get('source'),
            *[(location.get('source') or None) for location in item.get('locations', [])],
        ]:
            if not raw_source:
                continue
            source_id = self._extract_source_id(raw_source)
            source_name = raw_source.get('display_name', '')
            source_type = raw_source.get('type', '')
            source_key = (source_id, source_name)
            if source_key in seen or not source_name:
                continue
            seen.add(source_key)
            sources.append({
                'id': source_id,
                'display_name': source_name,
                'type': source_type,
            })
        return sources

    def _matches_conference_doi(self, item, conf_spec):
        doi = self._canonical_doi(item.get('doi'))
        if not doi:
            return False
        if any(doi.startswith(prefix) for prefix in conf_spec.get('doi_exclude_prefixes', [])):
            return False
        return any(doi.startswith(prefix) for prefix in conf_spec.get('doi_prefixes', []))

    def _match_conference_source_in_item(self, item, conf_spec):
        matched_source = None
        for source in self._item_sources(item):
            if self._source_matches_conference(source, conf_spec):
                matched_source = source
                break

        if matched_source:
            return matched_source

        if self._matches_conference_doi(item, conf_spec):
            return {
                'id': '',
                'display_name': conf_spec['name'],
                'type': 'conference',
            }

        return None

    def _canonical_doi(self, value):
        doi = (value or '').strip().lower()
        return doi.replace('https://doi.org/', '').replace('http://dx.doi.org/', '').replace('http://doi.org/', '')

    def _extract_abstract(self, item):
        abstract_inverted = item.get('abstract_inverted_index')
        if not abstract_inverted:
            return ""

        words = []
        for word, positions in abstract_inverted.items():
            for pos in positions:
                words.append((pos, word))
        words.sort(key=lambda x: x[0])
        return " ".join(word for _, word in words)

    def _extract_work(self, item, venue_name):
        doi = item.get('doi', '')
        if doi:
            doi = doi.replace('https://doi.org/', '')

        authors = ", ".join([
            authorship.get('author', {}).get('display_name', '')
            for authorship in item.get('authorships', [])
            if authorship.get('author')
        ])

        return {
            'id': item.get('id', ''),
            'title': item.get('title', '') or 'Untitled',
            'abstract': self._extract_abstract(item),
            'doi': doi,
            'publication_date': item.get('publication_date', ''),
            'publication_year': item.get('publication_year', ''),
            'journal': venue_name,
            'authors': authors,
            'is_related': '',
            'llm_reason': ''
        }

    def _work_key(self, item):
        doi = (item.get('doi') or '').strip().lower()
        if doi:
            return doi
        item_id = (item.get('id') or '').strip().lower()
        if item_id:
            return item_id
        return (item.get('title') or '').strip().lower()

    def get_source_id(self, journal_name):
        return self.search_sources(journal_name)

    def search_sources(self, source_name):
        source_names = [name.strip() for name in source_name.split(',') if name.strip()]
        matched_sources = []
        seen_ids = set()

        for name in source_names:
            encoded_name = urllib.parse.quote(name)
            url = f"{self.base_url}/sources?search={encoded_name}"
            try:
                data = self._request_json(url, timeout=20)
                if data.get('results'):
                    source = data['results'][0]
                    source_id = self._extract_source_id(source)
                    if source_id not in seen_ids:
                        seen_ids.add(source_id)
                        matched_sources.append({
                            'id': source_id,
                            'display_name': source['display_name']
                        })
            except Exception as e:
                print(f"Error fetching source ID for {name}: {e}")

        return matched_sources

    def search_conference_sources(self, conferences):
        matched_sources = []
        seen_pairs = set()

        for conf in conferences:
            conf_spec = self._conference_spec(conf)
            # Also search with year suffixes to find year-specific proceedings
            current_year = int(time.strftime('%Y'))
            search_terms = list(conf_spec['search_terms'])
            for year in range(current_year - 3, current_year + 1):
                search_terms.append(f"{conf_spec['name']} {year}")

            for term in search_terms:
                page = 1
                while True:
                    encoded_term = urllib.parse.quote(term)
                    url = f"{self.base_url}/sources?search={encoded_term}&filter=type:conference&per-page=50&page={page}"
                    try:
                        data = self._request_json(url, timeout=20)
                        results = data.get('results', [])
                        if not results:
                            break

                        for source in results:
                            if not self._source_matches_conference(source, conf_spec):
                                continue
                            source_id = self._extract_source_id(source)
                            pair_key = (conf_spec['rule_id'], source_id)
                            if pair_key in seen_pairs:
                                continue
                            seen_pairs.add(pair_key)
                            matched_sources.append({
                                'id': source_id,
                                'display_name': source['display_name'],
                                'conference_key': conf.get('key'),
                                'conference_name': conf.get('name'),
                                'conference_rule_id': conf_spec['rule_id'],
                            })

                        if len(results) < 50:
                            break
                        page += 1
                        time.sleep(0.15)
                    except Exception as e:
                        print(f"Error fetching conference sources for {conf.get('name') or term} page {page}: {e}")
                        break

        return matched_sources

    def fetch_works(self, source_ids, start_date, end_date, max_results=500):
        works = []
        source_id_str = "|".join(source_ids)
        page = 1
        per_page = 200

        while len(works) < max_results:
            url = f"{self.base_url}/works?filter=primary_location.source.id:{source_id_str},from_publication_date:{start_date},to_publication_date:{end_date}&per-page={per_page}&page={page}"
            try:
                data = self._request_json(url, timeout=30)
                results = data.get('results', [])
                if not results:
                    break

                for item in results:
                    journal_display = item.get('primary_location', {}).get('source', {}).get('display_name', '')
                    works.append(self._extract_work(item, journal_display))
                    if len(works) >= max_results:
                        break

                total = data.get('meta', {}).get('count', 0)
                if page * per_page >= total or len(works) >= total:
                    break
                page += 1
                time.sleep(0.1)
            except Exception as e:
                print(f"Error fetching works page {page}: {e}")
                break
        return works

    def _fetch_conference_works_by_source_ids(self, source_ids, conf_spec, start_date, end_date, max_results, seen_work_keys):
        if not source_ids or max_results <= 0:
            return []

        works = []
        source_id_str = "|".join(source_ids[:25])
        page = 1
        per_page = min(200, max(max_results, 25))

        while len(works) < max_results:
            url = (
                f"{self.base_url}/works?filter=locations.source.id:{source_id_str},"
                f"from_publication_date:{start_date},to_publication_date:{end_date}"
                f"&sort=publication_date:desc&per-page={per_page}&page={page}"
            )
            try:
                data = self._request_json(url, timeout=30)
                results = data.get('results', [])
                if not results:
                    break

                for item in results:
                    if item.get('type') not in self.ALLOWED_CONFERENCE_WORK_TYPES:
                        continue
                    matched_source = self._match_conference_source_in_item(item, conf_spec)
                    if not matched_source:
                        continue
                    work_key = self._work_key(item)
                    if work_key in seen_work_keys:
                        continue
                    seen_work_keys.add(work_key)
                    works.append(self._extract_work(item, matched_source['display_name']))
                    if len(works) >= max_results:
                        break

                total = data.get('meta', {}).get('count', 0)
                if page * per_page >= total:
                    break
                page += 1
                time.sleep(0.1)
            except Exception as e:
                print(f"Error fetching conference works by source for {conf_spec['name']} page {page}: {e}")
                break

        return works

    def _fetch_conference_works_by_doi(self, conf_spec, start_date, end_date, max_results, seen_work_keys):
        """Fetch works by DOI prefix matching - most accurate for conferences with known DOI patterns."""
        if max_results <= 0:
            return []

        works = []
        doi_prefixes = conf_spec.get('doi_prefixes', [])
        if not doi_prefixes:
            return works

        for prefix in doi_prefixes:
            if len(works) >= max_results:
                break
            url = (
                f"{self.base_url}/works?filter=doi:{urllib.parse.quote(prefix + '*')},"
                f"from_publication_date:{start_date},to_publication_date:{end_date}"
                f"&sort=publication_date:desc&per-page=50&page=1"
            )
            try:
                data = self._request_json(url, timeout=20)
                for item in data.get('results', []):
                    if item.get('type') not in self.ALLOWED_CONFERENCE_WORK_TYPES:
                        continue
                    matched_source = self._match_conference_source_in_item(item, conf_spec)
                    source_name = matched_source['display_name'] if matched_source else conf_spec['name']
                    work_key = self._work_key(item)
                    if work_key in seen_work_keys:
                        continue
                    seen_work_keys.add(work_key)
                    works.append(self._extract_work(item, source_name))
                    if len(works) >= max_results:
                        break
            except Exception as e:
                print(f"Error fetching by DOI for {conf_spec['name']}: {e}")

        return works

    def _fetch_conference_works_by_search(self, conf_spec, start_date, end_date, max_results, seen_work_keys):
        if max_results <= 0:
            return []

        works = []
        per_page = 50

        for term in conf_spec['search_terms']:
            if len(works) >= max_results:
                break
            url = (
                f"{self.base_url}/works?search={urllib.parse.quote(term)}"
                f"&filter=from_publication_date:{start_date},to_publication_date:{end_date}"
                f"&sort=relevance_score:desc&per-page={per_page}&page=1"
            )
            try:
                data = self._request_json(url, timeout=20)
                results = data.get('results', [])

                for item in results:
                    if item.get('type') not in self.ALLOWED_CONFERENCE_WORK_TYPES:
                        continue
                    matched_source = self._match_conference_source_in_item(item, conf_spec)
                    if not matched_source:
                        continue
                    doi = self._canonical_doi(item.get('doi'))
                    if conf_spec.get('doi_prefixes') and any(excluded in doi for excluded in ['cvprw', 'workshop']):
                        continue
                    work_key = self._work_key(item)
                    if work_key in seen_work_keys:
                        continue
                    seen_work_keys.add(work_key)
                    works.append(self._extract_work(item, matched_source['display_name']))
                    if len(works) >= max_results:
                        break
            except Exception as e:
                print(f"Error searching conference works for {conf_spec['name']}: {e}")

        return works

    def fetch_conference_works(self, conferences, start_date, end_date, max_results=300, matched_sources=None):
        works = []
        seen_work_keys = set()
        per_conf_limit = max(max_results // max(len(conferences), 1), 1)

        if matched_sources is None:
            matched_sources = self.search_conference_sources(conferences)

        for conf in conferences:
            if len(works) >= max_results:
                break

            conf_spec = self._conference_spec(conf)
            remaining = min(per_conf_limit, max_results - len(works))
            conf_source_ids = [
                source['id']
                for source in matched_sources
                if source.get('conference_key') == conf.get('key') or source.get('conference_rule_id') == conf_spec['rule_id']
            ]

            # Try DOI-based first (most accurate)
            conf_works = self._fetch_conference_works_by_doi(
                conf_spec,
                start_date,
                end_date,
                remaining,
                seen_work_keys,
            )

            # Then try search-based
            if len(conf_works) < remaining:
                search_works = self._fetch_conference_works_by_search(
                conf_spec,
                start_date,
                end_date,
                remaining,
                seen_work_keys,
            )

            # Fall back to source-based if search didn't get enough
            if len(conf_works) < remaining and conf_source_ids:
                source_works = self._fetch_conference_works_by_source_ids(
                    conf_source_ids,
                    conf_spec,
                    start_date,
                    end_date,
                    remaining - len(conf_works),
                    seen_work_keys,
                )
                conf_works.extend(source_works)

            works.extend(conf_works[:remaining])

        return works

    def clean_and_group_data(self, works):
        seen = set()
        cleaned = []
        for work in works:
            key = work['doi'] if work['doi'] else work['title'].lower()
            if key and key not in seen:
                seen.add(key)
                cleaned.append(work)

        cleaned.sort(key=lambda item: (item['publication_year'] or 0, item['journal']), reverse=True)
        return cleaned

    def generate_stats(self, works):
        stats = {
            'years': {},
            'journals': {}
        }
        for work in works:
            year = str(work['publication_year']) if work['publication_year'] else 'Unknown'
            journal = work['journal'] or 'Unknown'

            stats['years'][year] = stats['years'].get(year, 0) + 1
            stats['journals'][journal] = stats['journals'].get(journal, 0) + 1

        stats['years'] = dict(sorted(stats['years'].items(), reverse=True))
        stats['journals'] = dict(sorted(stats['journals'].items(), key=lambda item: item[1], reverse=True))
        return stats
