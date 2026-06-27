from openai import OpenAI

class Translator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.client = None

    def _init_client(self):
        # 延迟初始化客户端，确保能读取到最新的配置信息
        api_key = self.db.get_config('api_key', '')
        base_url = self.db.get_config('base_url', 'https://api.openai.com/v1')
        
        if not api_key:
            return False
            
        try:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            return True
        except Exception as e:
            print(f"API初始化失败: {e}")
            return False

    def translate_title_only(self, title):
        # 仅调用大语言模型API进行标题的中文翻译
        if not self.client and not self._init_client():
            return None
            
        model = self.db.get_config('model', 'gpt-3.5-turbo')
        
        prompt = f"""
        请将以下学术文献的内容翻译为中文。
        要求：准确传达学术含义，语句通顺流畅。只需输出翻译结果，无需其他任何说明。
        
        待翻译内容：
        {title}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个专业的学术翻译助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                extra_body={"enable_thinking": False},
                timeout=30.0  # 放宽超时设置，以兼容可能较长的摘要翻译
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"标题翻译请求发生错误: {e}")
            return "翻译出错"

    def call_llm(self, prompt, system_prompt="你是一个专业的学术助手。", temperature=0.5):
        if not self.client and not self._init_client():
            raise Exception("API Key 未配置或初始化失败")
            
        model = self.db.get_config('model', 'gpt-3.5-turbo')
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                extra_body={"enable_thinking": False},
                timeout=60.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM调用发生错误: {e}")
            raise e
