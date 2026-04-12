import json
import re
import concurrent.futures
from openai import OpenAI

class Recommender:
    def __init__(self, db_manager):
        self.db = db_manager
        self.api_key = self.db.get_config('api_key', '')
        self.base_url = self.db.get_config('base_url', 'https://api.openai.com/v1')
        self.model = self.db.get_config('model', 'gpt-3.5-turbo')
        self.single_article_concurrency = 20
        
        if not self.api_key:
            print("未配置 OPENAI_API_KEY，推荐功能可能无法使用。")
            self.client = None
        else:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

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
        # 逐条判断时要求返回对象，便于稳妥读取 recommend 字段
        match = re.search(r'\{.*?\}', content, re.DOTALL)
        if not match:
            return {}

        return json.loads(match.group(0))

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

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个严谨的学术助手，严格按照要求的 JSON 格式输出结果。"},
                {"role": "user", "content": prompt}
            ],
            extra_body={"enable_thinking": False},
            timeout=60
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
如果符合，请返回：
{{"recommend": true}}
如果不符合，请返回：
{{"recommend": false}}
不要返回任何其他文字说明！"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个严谨的学术助手，严格按照要求的 JSON 格式输出结果。"},
                    {"role": "user", "content": prompt}
                ],
                extra_body={"enable_thinking": False},
                timeout=30
            )

            content = response.choices[0].message.content.strip()
            result = self._extract_json_object(content)
            return str(result.get('recommend')).lower() == 'true'
        except Exception as e:
            print(f"逐条推荐筛选请求出错，文献ID {article['id']}: {e}")
            return False

    def _get_recommendations_single_article(self, articles, criteria):
        # 逐条发送给模型判断，降低长上下文导致的遗漏概率
        recommended_ids = set()
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
                    print(f"逐条推荐任务执行失败，文献ID {article['id']}: {e}")

        # 按原始顺序返回，保证前端展示顺序与筛选前一致
        return [article['id'] for article in articles if article['id'] in recommended_ids]

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
