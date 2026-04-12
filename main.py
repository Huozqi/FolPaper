import customtkinter as ctk
import threading
from tkinter import messagebox
import webbrowser
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
from database import DatabaseManager
from fetcher import LiteratureFetcher
from translator import Translator

# 设置外观模式和颜色主题
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("订阅阅读与翻译助手")
        self.geometry("1000x700")

        # 初始化后台组件
        self.db = DatabaseManager()
        self.fetcher = LiteratureFetcher(self.db)
        self.translator = Translator(self.db)

        # 布局配置
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 左侧导航栏
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="订阅阅读器", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.nav_list_btn = ctk.CTkButton(self.sidebar_frame, text="文章列表", command=self.show_list_view)
        self.nav_list_btn.grid(row=1, column=0, padx=20, pady=10)

        self.nav_fetch_btn = ctk.CTkButton(self.sidebar_frame, text="订阅管理", command=self.show_fetch_view)
        self.nav_fetch_btn.grid(row=2, column=0, padx=20, pady=10)

        self.nav_settings_btn = ctk.CTkButton(self.sidebar_frame, text="系统设置", command=self.show_settings_view)
        self.nav_settings_btn.grid(row=3, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="外观模式:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 20))

        # 视图容器
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # 初始化各个视图
        self.views = {}
        self.init_list_view()
        self.init_fetch_view()
        self.init_settings_view()

        # 默认显示列表视图
        self.show_list_view()

        # 启动定期自动更新机制（例如每2小时后台刷新一次默认的arXiv类别）
        self.start_auto_update()

    def start_auto_update(self):
        # 定期自动更新：通过后台线程无感刷新数据
        def auto_fetch():
            try:
                count = self.fetcher.fetch_all()
                if count > 0:
                    # 若在列表页面，则刷新列表
                    if self.views["list"].winfo_ismapped():
                        self.after(0, self.load_articles)
            except Exception as e:
                print(f"Auto update failed: {e}")
                
        threading.Thread(target=auto_fetch, daemon=True).start()
        # 每隔 7200000 毫秒（2小时）执行一次
        self.after(7200000, self.start_auto_update)

    def change_appearance_mode_event(self, new_appearance_mode):
        ctk.set_appearance_mode(new_appearance_mode)

    def hide_all_views(self):
        for view in self.views.values():
            view.grid_forget()

    def show_list_view(self):
        self.hide_all_views()
        self.views["list"].grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.load_articles()

    def show_fetch_view(self):
        self.hide_all_views()
        self.views["fetch"].grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.load_subscriptions()

    def show_settings_view(self):
        self.hide_all_views()
        self.views["settings"].grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.load_settings()

    # ================= 列表视图 =================
    def _format_date(self, date_str):
        if not date_str: return "未知日期"
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.strftime("%Y.%m.%d")
        except Exception:
            pass
        try:
            # 尝试解析arxiv的时间格式
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            return dt.strftime("%Y.%m.%d")
        except Exception:
            pass
        
        # 兜底：尝试使用正则匹配 YYYY-MM-DD
        m = re.search(r'\d{4}-\d{2}-\d{2}', date_str)
        if m:
            return m.group(0).replace('-', '.')
        return date_str[:10]

    def init_list_view(self):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        top_frame = ctk.CTkFrame(frame, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        title = ctk.CTkLabel(top_frame, text="文章列表", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left")
        
        refresh_btn = ctk.CTkButton(top_frame, text="刷新列表", command=self.load_articles, width=100)
        refresh_btn.pack(side="right")

        self.scrollable_list = ctk.CTkScrollableFrame(frame)
        self.scrollable_list.grid(row=1, column=0, sticky="nsew")
        self.scrollable_list.grid_columnconfigure(0, weight=1)

        self.views["list"] = frame

    def load_articles(self):
        # 清空当前列表
        for widget in self.scrollable_list.winfo_children():
            widget.destroy()
            
        articles = self.db.get_all_articles()
        
        if not articles:
            empty_label = ctk.CTkLabel(self.scrollable_list, text="暂无文献数据，请先前往“数据获取”页面获取。")
            empty_label.grid(row=0, column=0, pady=20)
            return
            
        for i, article in enumerate(articles):
            self.create_article_card(self.scrollable_list, article, i)

    def create_article_card(self, parent, article, row):
        # 创建单个文献卡片，背景透明，使用底部线条分隔
        card = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        card.grid(row=row, column=0, sticky="ew", padx=20, pady=(15, 5))
        card.grid_columnconfigure(0, weight=1)
        
        # 1. 英文标题
        title_font = ctk.CTkFont(family="Times New Roman", size=20, weight="bold")
        title_label = ctk.CTkLabel(card, text=article['title'], font=title_font, 
                                   wraplength=750, justify="left", anchor="w", text_color=("black", "white"))
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        # 2. 中文标题（若有）
        if article.get('translated_title'):
            cn_title_label = ctk.CTkLabel(card, text=article['translated_title'], font=ctk.CTkFont(size=14), 
                                       wraplength=750, justify="left", anchor="w", text_color=("gray40", "gray60"))
            cn_title_label.grid(row=1, column=0, sticky="w", pady=(0, 10))
            
        # 3. 作者栏 (头像徽章 + 姓名)
        authors_frame = ctk.CTkFrame(card, fg_color="transparent")
        authors_frame.grid(row=2, column=0, sticky="w", pady=(0, 10))
        
        author_list = [a.strip() for a in article['authors'].split(',')] if article.get('authors') else ["未知作者"]
        col_idx = 0
        for i, author in enumerate(author_list):
            if i < 2:
                # 提取首字母作为徽章文字
                initial = author[0].upper() if author else "?"
                badge = ctk.CTkLabel(authors_frame, text=initial, width=24, height=24, corner_radius=12,
                                     fg_color=("gray85", "gray30"), text_color=("gray40", "gray70"), font=ctk.CTkFont(weight="bold", size=12))
                badge.grid(row=0, column=col_idx, padx=(0, 6))
                col_idx += 1
                
                name_lbl = ctk.CTkLabel(authors_frame, text=author, text_color=("gray40", "gray70"), font=ctk.CTkFont(size=14))
                name_lbl.grid(row=0, column=col_idx, padx=(0, 16))
                col_idx += 1
            elif i == 2:
                # 剩余作者数量徽章
                rem = len(author_list) - 2
                badge = ctk.CTkLabel(authors_frame, text=f"+{rem}", width=32, height=24, corner_radius=12,
                                     fg_color=("gray85", "gray30"), text_color=("gray40", "gray70"), font=ctk.CTkFont(weight="bold", size=12))
                badge.grid(row=0, column=col_idx, padx=(0, 6))
                col_idx += 1
                break
                
        # 4. 日期与来源
        meta_frame = ctk.CTkFrame(card, fg_color="transparent")
        meta_frame.grid(row=3, column=0, sticky="w", pady=(0, 10))
        
        date_str = self._format_date(article.get('published', ''))
        meta_text = f"{date_str}  |  🌐 {article.get('source', '未知来源')}"
        meta_lbl = ctk.CTkLabel(meta_frame, text=meta_text, text_color=("gray40", "gray70"), font=ctk.CTkFont(size=13))
        meta_lbl.grid(row=0, column=0, sticky="w")
        
        # 5. 摘要内容
        summary_text = article.get('translated_summary') or article.get('summary') or ""
        prefix = "摘要： " if article.get('translated_summary') else "Abstract: "
        
        # 替换换行符并截断长摘要
        summary_text = summary_text.replace('\n', ' ')
        display_summary = prefix + summary_text
        if len(display_summary) > 200:
            display_summary = display_summary[:197] + "..."
            
        summary_label = ctk.CTkLabel(card, text=display_summary, wraplength=750, justify="left", anchor="w", 
                                     text_color=("gray30", "gray70"), font=ctk.CTkFont(size=14))
        summary_label.grid(row=4, column=0, sticky="w", pady=(0, 15))
        
        # 6. 操作按钮与底部分隔线
        bottom_frame = ctk.CTkFrame(card, fg_color="transparent")
        bottom_frame.grid(row=5, column=0, sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)
        
        actions_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        actions_frame.grid(row=0, column=1, sticky="e", pady=(0, 10))
        
        link_btn = ctk.CTkButton(actions_frame, text="查看原文", width=80, height=28, fg_color="transparent", 
                                 border_width=1, text_color=("gray30", "gray80"),
                                 command=lambda url=article['link']: webbrowser.open(url))
        link_btn.pack(side="right", padx=(10, 0))
        
        if not article.get('translated_title'):
            trans_btn = ctk.CTkButton(actions_frame, text="AI 翻译", width=80, height=28,
                                      command=lambda a=article: self.start_translation(a))
            trans_btn.pack(side="right")
            
        # 绘制一条极细的分隔线
        sep = ctk.CTkFrame(bottom_frame, height=1, fg_color=("gray85", "gray20"))
        sep.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    def start_translation(self, article):
        # 启动后台线程进行翻译，避免卡死界面
        def run_trans():
            trans_title, trans_summary = self.translator.translate_article(article['title'], article['summary'])
            if trans_title and trans_summary and trans_title != "翻译解析失败" and trans_title != "翻译出错":
                self.db.update_translation(article['article_id'], trans_title, trans_summary)
                # 翻译完成后刷新界面
                self.after(0, self.load_articles)
            else:
                self.after(0, lambda: messagebox.showerror("翻译失败", f"无法完成翻译: {trans_summary}"))
                
        threading.Thread(target=run_trans, daemon=True).start()
        messagebox.showinfo("提示", "翻译任务已提交，请稍候刷新查看结果。")

    # ================= 获取数据视图 =================
    def init_fetch_view(self):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        
        title = ctk.CTkLabel(frame, text="订阅管理与更新", font=ctk.CTkFont(size=24, weight="bold"), anchor="w")
        title.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # 添加订阅区
        add_sub_frame = ctk.CTkFrame(frame, corner_radius=10)
        add_sub_frame.grid(row=1, column=0, sticky="ew", pady=10)
        add_sub_frame.grid_columnconfigure(0, weight=1)
        
        self.sub_value_entry = ctk.CTkEntry(add_sub_frame, placeholder_text="输入 RSS XML 链接")
        self.sub_value_entry.grid(row=0, column=0, padx=15, pady=15, sticky="ew")
        
        ctk.CTkButton(add_sub_frame, text="添加 RSS", command=self.add_subscription_action, width=100, corner_radius=8).grid(row=0, column=1, padx=15, pady=15)

        # 订阅列表区
        self.subs_list_frame = ctk.CTkScrollableFrame(frame, corner_radius=10)
        self.subs_list_frame.grid(row=2, column=0, sticky="nsew", pady=10)
        self.subs_list_frame.grid_columnconfigure(0, weight=1)

        # 抓取控制区
        fetch_ctrl_frame = ctk.CTkFrame(frame, corner_radius=10)
        fetch_ctrl_frame.grid(row=3, column=0, sticky="ew", pady=10)
        
        # 默认近10天
        default_end = datetime.now()
        default_start = default_end - timedelta(days=10)
        
        ctk.CTkLabel(fetch_ctrl_frame, text="开始日期:").grid(row=0, column=0, padx=(15, 5), pady=15)
        self.start_date_entry = ctk.CTkEntry(fetch_ctrl_frame, width=120)
        self.start_date_entry.insert(0, default_start.strftime("%Y-%m-%d"))
        self.start_date_entry.grid(row=0, column=1, padx=5, pady=15)
        
        ctk.CTkLabel(fetch_ctrl_frame, text="结束日期:").grid(row=0, column=2, padx=(15, 5), pady=15)
        self.end_date_entry = ctk.CTkEntry(fetch_ctrl_frame, width=120)
        self.end_date_entry.insert(0, default_end.strftime("%Y-%m-%d"))
        self.end_date_entry.grid(row=0, column=3, padx=5, pady=15)

        ctk.CTkButton(fetch_ctrl_frame, text="开始获取更新", command=self.fetch_all_action, fg_color="#28a745", hover_color="#218838", corner_radius=8).grid(row=0, column=4, padx=20, pady=15)

        self.fetch_status_label = ctk.CTkLabel(frame, text="", text_color="green")
        self.fetch_status_label.grid(row=4, column=0, pady=10)

        # 手动单篇获取区
        manual_frame = ctk.CTkFrame(frame, corner_radius=10)
        manual_frame.grid(row=5, column=0, sticky="ew", pady=10)
        manual_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(manual_frame, text="手动获取(arXiv ID):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=15, sticky="w")
        self.manual_id_entry = ctk.CTkEntry(manual_frame, placeholder_text="例如: 2106.09685")
        self.manual_id_entry.grid(row=0, column=1, padx=15, pady=15, sticky="ew")
        
        ctk.CTkButton(manual_frame, text="定向抓取", command=self.fetch_manual_action, width=100, corner_radius=8).grid(row=0, column=2, padx=15, pady=15)

        self.views["fetch"] = frame

    def load_subscriptions(self):
        for widget in self.subs_list_frame.winfo_children():
            widget.destroy()
            
        subs = self.db.get_subscriptions()
        if not subs:
            ctk.CTkLabel(self.subs_list_frame, text="暂无订阅，请在上方添加").grid(row=0, column=0, pady=20)
            return
            
        for i, sub in enumerate(subs):
            row_frame = ctk.CTkFrame(self.subs_list_frame, fg_color="transparent")
            row_frame.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            row_frame.grid_columnconfigure(1, weight=1)
            
            ctk.CTkLabel(row_frame, text="[RSS]", width=60, anchor="w").grid(row=0, column=0, padx=5)
            ctk.CTkLabel(row_frame, text=sub['source_name'], font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=(0, 5), sticky="w")
            ctk.CTkLabel(row_frame, text=sub['sub_value'], text_color="gray", anchor="w").grid(row=0, column=2, padx=5, sticky="ew")
            
            # 显示时限配置（桌面端暂不支持修改，仅展示）
            ctk.CTkLabel(row_frame, text=f"抓取:{sub.get('fetch_days', 7)}天", text_color="gray", width=60).grid(row=0, column=3, padx=5)
            ctk.CTkLabel(row_frame, text=f"保留:{sub.get('retention_days', 30)}天", text_color="gray", width=60).grid(row=0, column=4, padx=5)
            
            del_btn = ctk.CTkButton(row_frame, text="删除", width=60, fg_color="red", hover_color="darkred",
                                    command=lambda v=sub['sub_value']: self.delete_subscription_action(v))
            del_btn.grid(row=0, column=5, padx=5)

    def add_subscription_action(self):
        sub_value = self.sub_value_entry.get().strip()
        if not sub_value: return
        
        # 桌面端新增订阅统一按 RSS 处理，由于没有额外输入框，采用默认名称与默认时限
        source_name = f"RSS: {sub_value[:20]}..."
        if self.db.add_subscription("rss", sub_value, source_name, fetch_days=7, retention_days=30):
            self.sub_value_entry.delete(0, 'end')
            self.load_subscriptions()
        else:
            messagebox.showwarning("提示", "该订阅已存在")

    def delete_subscription_action(self, sub_value):
        self.db.remove_subscription(sub_value)
        self.load_subscriptions()

    def fetch_all_action(self):
        start_str = self.start_date_entry.get().strip()
        end_str = self.end_date_entry.get().strip()
        
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            # 让 end_date 包含当天最后一秒
            end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
        except ValueError:
            messagebox.showerror("错误", "日期格式不正确，请使用 YYYY-MM-DD")
            return
            
        self.fetch_status_label.configure(text="正在批量获取数据，请稍候...", text_color="blue")
        
        def task():
            try:
                count = self.fetcher.fetch_all(start_date=start_date, end_date=end_date)
                self.after(0, lambda: self.fetch_status_label.configure(text=f"成功获取并入库 {count} 条新文献！", text_color="green"))
            except Exception as e:
                self.after(0, lambda: self.fetch_status_label.configure(text=f"获取失败: {str(e)}", text_color="red"))
                
        threading.Thread(target=task, daemon=True).start()

    def fetch_manual_action(self):
        arxiv_id = self.manual_id_entry.get().strip()
        if not arxiv_id: return
        self.fetch_status_label.configure(text="正在获取数据，请稍候...", text_color="blue")
        
        def task():
            try:
                count = self.fetcher.fetch_manual_arxiv(arxiv_id)
                self.after(0, lambda: self.fetch_status_label.configure(text=f"成功获取并入库 {count} 条新文献！", text_color="green"))
            except Exception as e:
                self.after(0, lambda: self.fetch_status_label.configure(text=f"获取失败: {str(e)}", text_color="red"))
                
        threading.Thread(target=task, daemon=True).start()

    # ================= 设置视图 =================
    def init_settings_view(self):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(frame, text="系统设置", font=ctk.CTkFont(size=24, weight="bold"), anchor="w")
        title.grid(row=0, column=0, sticky="w", pady=(0, 20))

        settings_frame = ctk.CTkFrame(frame)
        settings_frame.grid(row=1, column=0, sticky="ew", pady=10)
        settings_frame.grid_columnconfigure(1, weight=1)
        
        # API Key
        ctk.CTkLabel(settings_frame, text="API Key:").grid(row=0, column=0, padx=15, pady=15, sticky="w")
        self.api_key_entry = ctk.CTkEntry(settings_frame, show="*")
        self.api_key_entry.grid(row=0, column=1, padx=15, pady=15, sticky="ew")
        
        # Base URL
        ctk.CTkLabel(settings_frame, text="Base URL:").grid(row=1, column=0, padx=15, pady=15, sticky="w")
        self.base_url_entry = ctk.CTkEntry(settings_frame)
        self.base_url_entry.grid(row=1, column=1, padx=15, pady=15, sticky="ew")

        # Model
        ctk.CTkLabel(settings_frame, text="Model:").grid(row=2, column=0, padx=15, pady=15, sticky="w")
        self.model_entry = ctk.CTkEntry(settings_frame)
        self.model_entry.grid(row=2, column=1, padx=15, pady=15, sticky="ew")

        save_btn = ctk.CTkButton(frame, text="保存设置", command=self.save_settings)
        save_btn.grid(row=2, column=0, pady=20)

        self.views["settings"] = frame

    def load_settings(self):
        self.api_key_entry.delete(0, 'end')
        self.api_key_entry.insert(0, self.db.get_config('api_key', ''))
        
        self.base_url_entry.delete(0, 'end')
        self.base_url_entry.insert(0, self.db.get_config('base_url', 'https://api.openai.com/v1'))
        
        self.model_entry.delete(0, 'end')
        self.model_entry.insert(0, self.db.get_config('model', 'gpt-3.5-turbo'))

    def save_settings(self):
        self.db.set_config('api_key', self.api_key_entry.get().strip())
        self.db.set_config('base_url', self.base_url_entry.get().strip())
        self.db.set_config('model', self.model_entry.get().strip())
        
        # 重置翻译器客户端以使用新配置
        self.translator.client = None
        messagebox.showinfo("成功", "设置已保存！")

if __name__ == "__main__":
    app = App()
    app.mainloop()
