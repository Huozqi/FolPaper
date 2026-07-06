import json
from openai import OpenAI

class Translator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.client = None

    def _init_client(self):
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

    def _get_model(self, task='default'):
        """按任务取模型名，回退到默认模型。"""
        key_map = {'translate': 'translate_model', 'recommend': 'recommend_model', 'survey': 'survey_model'}
        key = key_map.get(task, 'model')
        model = self.db.get_config(key, '') or self.db.get_config('model', 'gpt-3.5-turbo')
        return model

    def _get_params(self, task='default'):
        """获取通用 LLM 调用参数。"""
        model = self._get_model(task)
        temp = float(self.db.get_config('temperature', '0.3'))
        timeout = float(self.db.get_config('timeout', '60'))
        extra_str = self.db.get_config('extra_body', '')
        extra = {}
        if extra_str:
            try:
                extra = json.loads(extra_str)
            except json.JSONDecodeError:
                pass
        # 思考模式：使用 DeepSeek 新格式 thinking: {type: "enabled"/"disabled"}
        # 兼容其他厂商：在 Extra Body 中覆盖即可
        think = self.db.get_config('think_mode', 'off')
        if think == 'on':
            extra['thinking'] = {'type': 'enabled'}
        elif think == 'off':
            extra['thinking'] = {'type': 'disabled'}
        # 'auto' 不设，由 API 默认行为决定
        return model, temp, timeout, extra

    def _get_task_temp(self, task='default'):
        """按任务取 temperature。"""
        key_map = {'translate': 'translate_temperature', 'survey': 'survey_temperature'}
        key = key_map.get(task)
        if key:
            val = self.db.get_config(key, '')
            if val:
                return float(val)
        return float(self.db.get_config('temperature', '0.3'))

    def translate_title_only(self, title):
        if not self.client and not self._init_client():
            return None
        model, _, timeout, extra = self._get_params('translate')
        temperature = self._get_task_temp('translate')

        prompt = f"请将以下学术文献内容翻译为中文。要求：准确传达学术含义，语句通顺流畅。只需输出翻译结果。\n\n待翻译内容：\n{title}"
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个专业的学术翻译助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                extra_body=extra if extra else None,
                timeout=timeout,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"标题翻译请求发生错误: {e}")
            return "翻译出错"

    def call_llm(self, prompt, system_prompt="你是一个专业的学术助手。", temperature=0.5, task='default'):
        if not self.client and not self._init_client():
            raise Exception("API Key 未配置或初始化失败")
        model, _, timeout, extra = self._get_params(task)
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                extra_body=extra if extra else None,
                timeout=timeout,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM调用发生错误: {e}")
            raise e
