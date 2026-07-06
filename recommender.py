import json
import re
import concurrent.futures
from openai import OpenAI

class Recommender:
    def __init__(self, db_manager):
        self.db = db_manager
        self.api_key = self.db.get_config('api_key', '')
        self.base_url = self.db.get_config('base_url', 'https://api.openai.com/v1')
        self.model = self.db.get_config('recommend_model', '') or self.db.get_config('model', 'gpt-3.5-turbo')
        self.single_article_concurrency = int(self.db.get_config('recommend_concurrency', '20') or '20')

        if not self.api_key:
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _get_call_params(self):
        """读取 LLM 调用参数。"""
        temp = float(self.db.get_config('temperature', '0.3'))
        timeout = float(self.db.get_config('timeout', '60'))
        extra_str = self.db.get_config('extra_body', '')
        extra = {}
        if extra_str:
            try: extra = json.loads(extra_str)
            except json.JSONDecodeError: pass
        return temp, timeout, extra

    def _build_article_brief(self, article):
        # 优先使用中文字段，减少模型理解负担
        title = article.get('translated_title') if article.get('translated_title') else article.get('title')
        summary = article.get('translated_summary') if article.get('translated_summary') else article.get('summary', '')
        short_summary = summary[:200].replace('\n', ' ') + '...' if len(summary) > 200 else summary.replace('\n', ' ')
        return title, short_summary

    def _extract_json_array(self, content):
        # 兼容模型返回 Markdown 包裹或夹带说明文字的情况
        match = re.search(r'\[(.*?)\]', content, re.DOTALL)
        if not match:
            return []

        array_str = f"[{match.group(1)}]"
        try:
            ids = json.loads(array_str)
            return [int(id) if str(id).isdigit() else str(id) for id in ids if isinstance(id, (int, str)) and (str(id).isdigit() or str(id).startswith("WOS_"))]
        except json.JSONDecodeError:
            # Try to handle unquoted WOS_x strings manually if LLM fails to quote them
            if 'WOS_' in array_str:
                items = match.group(1).split(',')
                valid_ids = []
                for item in items:
                    item = item.strip().strip('"').strip("'")
                    if item.isdigit():
                        valid_ids.append(int(item))
                    elif item.startswith("WOS_"):
                        valid_ids.append(item)
                return valid_ids
            return []

    def _extract_json_object(self, content):
        """从模型返回中提取 recommend 字段，多重回退保证不遗漏。"""
        # 1. 标准 JSON
        match = re.search(r'\{.*?\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        # 2. 简单 true/false 文本
        low = content.lower()
        if 'true' in low and 'false' not in low:
            return {'recommend': True}
        if 'false' in low and 'true' not in low:
            return {'recommend': False}
        # 3. 中文关键词（先查否定，避免「不符合」含「符合」误判）
        neg = ('不符合', '不推荐', '不相关', '无关', '不匹配', '否')
        pos = ('符合要求', '推荐', '相关', '匹配', '是')
        if any(w in low for w in neg):
            return {'recommend': False}
        if any(w in low for w in pos):
            return {'recommend': True}
        return {}

    def _get_recommendations_global(self, articles, criteria):
        """
        全量拼接后交给大模型统一筛选
        返回符合条件的文献 ID 列表
        """
        article_text = ""
        for a in articles:
            title, short_summary = self._build_article_brief(a)
            article_text += f"ID: {a['id']} | 标题: {title} | 来源: {a.get('source')} | 摘要: {short_summary}\n"

        prompt = f"""你是一个专业的学术文献筛选助手。
用户需要筛选符合以下要求的文献：
"{criteria}"

下面是目前的待筛选文献列表（包含数据库ID、标题、来源和摘要片段）：
{article_text}

请你根据用户的要求，从上述文献中挑选出所有符合条件的文献，不要遗漏任何相关文献。
你只需要返回被选中文献的 ID 列表（注意保留原始 ID 类型，如果是字符串则必须带引号）。
返回格式必须是一个纯 JSON 数组，例如：[1, 5, 12, "WOS_3"]。
如果没有任何文献符合要求，请返回：[]。
不要返回任何其他文字说明！"""

        _, timeout, extra = self._get_call_params()
        if not extra:
            extra = {'enable_thinking': False}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个严谨的学术助手，严格按照要求的 JSON 格式输出结果。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            extra_body=extra, timeout=max(min(timeout, 60), 60)
        )

        content = response.choices[0].message.content.strip()
        return self._extract_json_array(content)

    def _is_article_recommended(self, article, criteria):
        title, short_summary = self._build_article_brief(article)

        prompt = f"""你是一个专业的学术文献筛选助手。
用户需要筛选符合以下要求的文献：
"{criteria}"

下面是一篇候选文献：
ID: {article['id']}
标题: {title}
来源: {article.get('source')}
摘要: {short_summary}

请判断这篇文献是否符合用户要求。
如果符合，请返回：{{"recommend": true}}
如果不符合，请返回：{{"recommend": false}}"""

        for attempt in range(3):
            try:
                _, timeout, extra = self._get_call_params()
                if not extra:
                    extra = {'enable_thinking': False}
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个严谨的学术助手，严格按照 JSON 格式输出。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    extra_body=extra, timeout=min(timeout, 60)
                )
                content = response.choices[0].message.content.strip()
                result = self._extract_json_object(content)
                rec = str(result.get('recommend')).lower()
                if rec in ('true', 'false'):
                    return rec == 'true'
                # 回退无结果 → 重试
                if attempt < 2:
                    import time; time.sleep(1)
            except Exception as e:
                if attempt < 2:
                    import time; time.sleep(2 ** attempt)
                else:
                    print(f"逐条推荐失败(ID={article['id']}): {e}")
                    return False
        return False

    def _get_recommendations_single_article(self, articles, criteria):
        recommended_ids = set()
        skipped_ids = set()
        future_to_article = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.single_article_concurrency) as executor:
            for article in articles:
                future = executor.submit(self._is_article_recommended, article, criteria)
                future_to_article[future] = article

            for future in concurrent.futures.as_completed(future_to_article):
                article = future_to_article[future]
                try:
                    if future.result():
                        recommended_ids.add(article['id'])
                except Exception as e:
                    skipped_ids.add(article['id'])
                    print(f"逐条推荐执行失败，文献ID {article['id']}: {e}")

        if skipped_ids:
            print(f"[recommender] 逐条分析完成: {len(recommended_ids)} 推荐, "
                  f"{len(skipped_ids)} 跳过 (API异常), "
                  f"{len(articles) - len(recommended_ids) - len(skipped_ids)} 不相关")

        return [article['id'] for article in articles if article['id'] in recommended_ids]

    def _extract_categories_from_criteria(self, criteria):
        """从筛选条件中提取分类关键词。返回列表或 None。"""
        parts = re.split(r'[，、；;,\n]', criteria)
        # 常见后缀，会污染分类名
        tail_re = re.compile(r'(领域|方向|方面|相关|等|的|研究|问题|应用|技术|方法)\s*(的\s*)?(文章|文献|论文|内容|工作|进展|前沿|综述|调研)?$')
        categories = []
        for p in parts:
            p = p.strip()
            # 去掉引导性前缀
            p = re.sub(r'^(帮我\s*(筛选出?|找出?|查找|检索|搜索|推荐)?\s*(AI\s*在\s*|人工智能\s*在\s*)?)', '', p)
            # 去掉尾部废话
            p = tail_re.sub('', p).strip()
            if 2 <= len(p) <= 20:
                categories.append(p)
        # 去重保持顺序
        seen = set()
        uniq = []
        for c in categories:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq if len(uniq) >= 2 else None

    def categorize_articles(self, articles, criteria):
        """将文章按 criteria 相关类别分组。返回 {category: [article_dict, ...]}"""
        if not articles or len(articles) < 2:
            return {}

        preset = self._extract_categories_from_criteria(criteria)

        # 限制篇数防止 token 超限：最多 60 篇，每篇摘要截到 120 字
        MAX_CAT_ARTICLES = 60
        to_categorize = articles[:MAX_CAT_ARTICLES]
        article_lines = []
        for a in to_categorize:
            title, short_summary = self._build_article_brief(a)
            short_summary = short_summary[:120] + '...' if len(short_summary) > 120 else short_summary
            article_lines.append(f"ID: {a['id']} | 标题: {title} | 摘要: {short_summary}")
        article_text = '\n'.join(article_lines)

        if preset:
            cat_instruction = f"请使用以下固定类别（可合并相近类别）：{'、'.join(preset)}"
        else:
            cat_instruction = "请根据文献内容自动归纳出 3-8 个合适的类别"

        prompt = f"""你是一个专业的学术文献分类助手。
用户研究方向："{criteria}"

{cat_instruction}。

文献列表：
{article_text}

将每篇文献分配到最合适的一个类别中。返回纯 JSON：
{{"categories": {{"类别名": [ID1, ID2], "类别名2": [ID3]}}}}

规则：每篇只归一类，ID 用原始格式，只返回 JSON。"""

        _, timeout, extra = self._get_call_params()
        if not extra:
            extra = {'enable_thinking': False}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个严谨的学术助手，严格按 JSON 格式输出。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                extra_body=extra, timeout=min(timeout, 120)
            )
            content = response.choices[0].message.content.strip()
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if not match:
                return {}
            result = json.loads(match.group(0))
            cat_dict = result.get('categories', {})
            if not cat_dict:
                return {}

            id_map = {}
            for a in articles:
                id_map[str(a['id'])] = a
                id_map[a['id']] = a

            categorized = {}
            for cat_name, id_list in cat_dict.items():
                group = []
                for aid in id_list:
                    article = id_map.get(str(aid)) or id_map.get(aid)
                    if article:
                        group.append(article)
                if group:
                    categorized[cat_name] = group
            return categorized
        except Exception as e:
            print(f"分类失败: {e}")
        return {}

    def get_recommendations(self, articles, criteria, mode='global'):
        """
        根据模式调用不同的推荐策略
        mode=global 表示全局分析
        mode=single 表示逐条采样分析
        """
        if not self.client:
            print("API 客户端未初始化。")
            return []

        if not articles or not criteria:
            return []

        try:
            if mode == 'single':
                return self._get_recommendations_single_article(articles, criteria)
            return self._get_recommendations_global(articles, criteria)
        except Exception as e:
            print(f"推荐筛选请求出错: {e}")
            return []
