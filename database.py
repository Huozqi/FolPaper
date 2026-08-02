import sqlite3
import os
import sys
import time
import threading
import re
from datetime import datetime, timedelta


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

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(get_base_path(), "articles.db")
        self.db_path = db_path
        self._write_lock = threading.RLock()
        self._init_db()
        self.prune_old_articles(days=30)
        self.prune_articles_by_subscription_retention()

    from contextlib import contextmanager
    @contextmanager
    def _conn(self, write=False):
        """上下文管理器，保证连接异常安全关闭，写操作自动加锁+提交。"""
        if write:
            self._write_lock.acquire()
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                if write:
                    conn.commit()
            finally:
                conn.close()
        finally:
            if write:
                self._write_lock.release()

    def _init_db(self):
        # 初始化数据库，创建表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # WAL 模式：读写不互斥，显著降低并发任务中的 database is locked
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA busy_timeout=30000')
        
        # articles表保存文献数据，article_id为唯一标识（如链接或DOI），确保增量添加时不重复
        # status字段表示当前文献的状态：'pending' 表示只是在订阅中暂存，'saved' 表示用户已正式添加到个人文库
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT UNIQUE,
                title TEXT,
                authors TEXT,
                summary TEXT,
                link TEXT,
                published TEXT,
                translated_title TEXT,
                translated_summary TEXT,
                source TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # 为了兼容旧数据库，如果已存在表但没有 status 字段，则尝试添加
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN status TEXT DEFAULT 'pending'")
        except sqlite3.OperationalError:
            pass
        
        # config表保存用户的配置，如API Key等
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # subscriptions表保存订阅源
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sub_type TEXT,
                sub_value TEXT UNIQUE,
                source_name TEXT
            )
        ''')
        
        # 为了兼容旧数据库，如果已存在表但没有 source_name 字段，则尝试添加
        try:
            cursor.execute("ALTER TABLE subscriptions ADD COLUMN source_name TEXT")
        except sqlite3.OperationalError:
            pass
            
        # 为订阅添加抓取时限和保留时限配置
        try:
            cursor.execute("ALTER TABLE subscriptions ADD COLUMN fetch_days INTEGER DEFAULT 7")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("ALTER TABLE subscriptions ADD COLUMN retention_days INTEGER DEFAULT 30")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE subscriptions ADD COLUMN openalex_query TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
            
        # 在 articles 表增加 trans_status 字段记录翻译状态：'none', 'translating', 'done', 'error'
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN trans_status TEXT DEFAULT 'none'")
        except sqlite3.OperationalError:
            pass
        
        # 在 articles 表增加 is_read 字段记录是否已读状态，默认 0 为未读，1 为已读
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN is_read INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        # 在 articles 表增加 doi 和 journal 字段
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN doi TEXT")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN journal TEXT")
        except sqlite3.OperationalError:
            pass
            
        # 在 articles 表增加 is_followed 字段记录是否已关注全文
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN is_followed INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # 在 articles 表增加 category 字段记录 AI 分类
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN category TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        # archive_articles 表用于持久化归档所有抓取到的历史文献，防止清理收件箱时遗漏
        # 仅保存核心信息：文章ID(作为去重依据)、标题、翻译标题、DOI、所属期刊、发表时间
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archive_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT UNIQUE,
                title TEXT,
                translated_title TEXT,
                doi TEXT,
                source TEXT,
                published TEXT
            )
        ''')
        
        # 兼容旧表：如果已存在旧表但没有 published 字段，则尝试添加
        try:
            cursor.execute("ALTER TABLE archive_articles ADD COLUMN published TEXT")
        except sqlite3.OperationalError:
            pass

        # 为高频筛选字段补充索引，减少列表页和推荐页的查询压力
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_status_source_published ON articles(status, source, published DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_source_is_read_published ON articles(source, is_read, published DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_is_read_published ON articles(is_read, published DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_trans_status ON articles(trans_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_archive_source_published ON archive_articles(source, published DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_archive_published ON archive_articles(published DESC)')

        # FTS5 全文搜索：索引标题、摘要、作者、翻译标题
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                title, authors, summary, translated_title,
                content='articles', content_rowid='id'
            )
        ''')
        # 触发器：articles 增删改时自动同步 FTS 索引
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS articles_fts_insert AFTER INSERT ON articles BEGIN
                INSERT INTO articles_fts(rowid, title, authors, summary, translated_title)
                VALUES (new.id, new.title, new.authors, new.summary, new.translated_title);
            END
        ''')
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS articles_fts_delete AFTER DELETE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, authors, summary, translated_title)
                VALUES ('delete', old.id, old.title, old.authors, old.summary, old.translated_title);
            END
        ''')
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS articles_fts_update AFTER UPDATE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, authors, summary, translated_title)
                VALUES ('delete', old.id, old.title, old.authors, old.summary, old.translated_title);
                INSERT INTO articles_fts(rowid, title, authors, summary, translated_title)
                VALUES (new.id, new.title, new.authors, new.summary, new.translated_title);
            END
        ''')

        # 将存量文章导入 FTS 索引（首次/重建时）
        cursor.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")

        conn.commit()
        conn.close()

    def search_articles(self, query, limit=50, status='pending'):
        """全文搜索标题、摘要、作者、翻译标题。使用 FTS5 引擎。"""
        # 转义 FTS5 特殊字符，将查询包装为安全的 token 短语
        tokens = re.findall(r'[\w一-鿿]+', query.lower())
        if not tokens:
            return []
        safe_query = ' AND '.join(f'"{t}"' for t in tokens)
        with self._conn() as conn:
            rows = conn.execute('''
                SELECT a.* FROM articles a
                JOIN articles_fts fts ON a.id = fts.rowid
                WHERE articles_fts MATCH ? AND a.status = ?
                ORDER BY rank LIMIT ?
            ''', (safe_query, status, limit)).fetchall()
        return [dict(row) for row in rows]

    def add_subscription(self, sub_type, sub_value, source_name="", fetch_days=7, retention_days=30, openalex_query=""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO subscriptions (sub_type, sub_value, source_name, fetch_days, retention_days, openalex_query) VALUES (?, ?, ?, ?, ?, ?)', (sub_type, sub_value, source_name, fetch_days, retention_days, openalex_query))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def update_subscription_limits(self, sub_value, fetch_days, retention_days):
        with self._conn(write=True) as conn:
            conn.execute('UPDATE subscriptions SET fetch_days = ?, retention_days = ? WHERE sub_value = ?', (fetch_days, retention_days, sub_value))

    def update_subscription(self, sub_value, source_name, fetch_days, retention_days, openalex_query=""):
        # 允许用户修改 source_name，由于文章是按 source 字段关联的，同步更新已有文章的 source
        # 这样不会因为修改了名字导致旧文章游离
        with self._conn(write=True) as conn:
            cursor = conn.cursor()
            # 先获取原来的 source_name
            cursor.execute('SELECT source_name FROM subscriptions WHERE sub_value = ?', (sub_value,))
            row = cursor.fetchone()
            old_source_name = row[0] if row else None

            # 更新订阅表
            cursor.execute('''
                UPDATE subscriptions
                SET source_name = ?, fetch_days = ?, retention_days = ?, openalex_query = ?
                WHERE sub_value = ?
            ''', (source_name, fetch_days, retention_days, openalex_query, sub_value))

            # 如果 source_name 发生了变化，同步更新关联的 articles 表和 archive_articles 表
            if old_source_name and old_source_name != source_name:
                cursor.execute('UPDATE articles SET source = ? WHERE source = ?', (source_name, old_source_name))
                cursor.execute('UPDATE archive_articles SET source = ? WHERE source = ?', (source_name, old_source_name))

    def update_subscriptions_batch(self, updates):
        """在单个事务中批量更新订阅配置。"""
        with self._conn(write=True) as conn:
            cursor = conn.cursor()
            for item in updates:
                cursor.execute('SELECT source_name FROM subscriptions WHERE id = ?', (item['id'],))
                row = cursor.fetchone()
                if not row:
                    continue
                old_source_name = row[0]
                cursor.execute('''
                    UPDATE subscriptions
                    SET source_name = ?, fetch_days = ?, retention_days = ?, openalex_query = ?
                    WHERE id = ?
                ''', (
                    item['source_name'], item['fetch_days'], item['retention_days'],
                    item['openalex_query'], item['id']
                ))
                if old_source_name and old_source_name != item['source_name']:
                    cursor.execute('UPDATE articles SET source = ? WHERE source = ?',
                                   (item['source_name'], old_source_name))
                    cursor.execute('UPDATE archive_articles SET source = ? WHERE source = ?',
                                   (item['source_name'], old_source_name))

    def remove_subscription(self, sub_value):
        with self._conn(write=True) as conn:
            conn.execute('DELETE FROM subscriptions WHERE sub_value = ?', (sub_value,))

    def get_subscriptions(self):
        with self._conn() as conn:
            rows = conn.execute('SELECT * FROM subscriptions').fetchall()
        return [dict(row) for row in rows]

    def add_article(self, article_data, return_status=False):
        article_id = article_data.get('article_id')
        doi = normalize_doi(article_data.get('doi'))
        if doi:
            article_data['doi'] = doi

        with self._conn(write=True) as conn:
            cursor = conn.cursor()
            if doi:
                cursor.execute('SELECT 1 FROM articles WHERE lower(doi) = lower(?) LIMIT 1', (doi,))
                if cursor.fetchone():
                    return 'duplicate_doi' if return_status else False
            elif article_id:
                cursor.execute('SELECT 1 FROM articles WHERE article_id = ? LIMIT 1', (article_id,))
                if cursor.fetchone():
                    return 'duplicate_article_id' if return_status else False

            # 已归档的文章视为历史记录，清理主表后不再重新进入收件箱
            if doi:
                cursor.execute('SELECT 1 FROM archive_articles WHERE lower(doi) = lower(?) LIMIT 1', (doi,))
                if cursor.fetchone():
                    return 'duplicate_archived' if return_status else False
            elif article_id:
                cursor.execute('SELECT 1 FROM archive_articles WHERE article_id = ? LIMIT 1', (article_id,))
                if cursor.fetchone():
                    return 'duplicate_archived' if return_status else False

            added_to_main = False
            duplicate_reason = None
            try:
                cursor.execute('''
                    INSERT INTO articles (article_id, title, authors, summary, link, published, source, doi, journal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (article_id, article_data.get('title'), article_data.get('authors'),
                      article_data.get('summary'), article_data.get('link'),
                      article_data.get('published'), article_data.get('source'),
                      doi, article_data.get('journal')))
                added_to_main = True
            except sqlite3.IntegrityError:
                duplicate_reason = 'duplicate_article_id'

            source = article_data.get('source')
            if source not in ['arXiv AI', 'arXiv LG', 'arXiv sML']:
                try:
                    cursor.execute('''
                        INSERT INTO archive_articles (article_id, title, doi, source, published)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (article_id, article_data.get('title'), doi, source, article_data.get('published')))
                except sqlite3.IntegrityError:
                    if not duplicate_reason:
                        duplicate_reason = 'duplicate_article_id'

        if return_status:
            return 'inserted' if added_to_main else (duplicate_reason or 'duplicate')
        return added_to_main

    def get_archive_articles_paginated(self, source=None, page=1, page_size=50):
        # 归档页改为分页查询，避免一次性渲染全部历史记录导致页面卡顿
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        requested_page = max(int(page), 1)
        page_size = max(int(page_size), 1)

        if source:
            cursor.execute('SELECT COUNT(*) FROM archive_articles WHERE source = ?', (source,))
            total_count = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT COUNT(*) FROM archive_articles')
            total_count = cursor.fetchone()[0]

        total_pages = max((total_count + page_size - 1) // page_size, 1)
        page = min(requested_page, total_pages)
        offset = (page - 1) * page_size

        if source:
            cursor.execute(
                'SELECT * FROM archive_articles WHERE source = ? ORDER BY published DESC LIMIT ? OFFSET ?',
                (source, page_size, offset)
            )
        else:
            cursor.execute(
                'SELECT * FROM archive_articles ORDER BY published DESC LIMIT ? OFFSET ?',
                (page_size, offset)
            )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows], total_count, total_pages, page

    def get_unique_archive_sources(self):
        # 归档页来源筛选应基于归档表本身，避免主表清理后丢失历史来源选项
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT source FROM archive_articles WHERE source IS NOT NULL ORDER BY source')
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def prune_old_articles(self, days=30, return_details=False):
        # 主表清理只处理没有订阅保留规则兜底的待处理文献
        # 对于已经在 subscriptions 表中登记过的来源，统一交给按订阅时限的清理逻辑处理
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        details = []
        with self._conn(write=True) as conn:
            cursor = conn.cursor()
            if return_details:
                cursor.execute(
                    '''
                    SELECT COALESCE(source, '未标记来源') AS source_name, COUNT(*)
                    FROM articles
                    WHERE status = 'pending'
                      AND published IS NOT NULL
                      AND published != ''
                      AND substr(published, 1, 10) < ?
                      AND NOT EXISTS (
                          SELECT 1
                          FROM subscriptions
                          WHERE subscriptions.source_name = articles.source
                      )
                    GROUP BY COALESCE(source, '未标记来源')
                    ORDER BY COUNT(*) DESC, source_name
                    ''',
                    (cutoff_date,)
                )
                details = [
                    {'source_name': row[0], 'count': row[1]}
                    for row in cursor.fetchall()
                ]
            cursor.execute(
                '''
                DELETE FROM articles
                WHERE status = 'pending'
                  AND published IS NOT NULL
                  AND published != ''
                  AND substr(published, 1, 10) < ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM subscriptions
                      WHERE subscriptions.source_name = articles.source
                  )
                ''',
                (cutoff_date,)
            )
            deleted_count = cursor.rowcount
        if return_details:
            return {
                'deleted_count': deleted_count,
                'details': details
            }
        return deleted_count

    def prune_articles_by_subscription_retention(self, return_details=False):
        # 按照各订阅源配置的留存天数清理待处理文章
        deleted_count = 0
        details = []
        with self._conn(write=True) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT source_name, retention_days FROM subscriptions')
            subs = cursor.fetchall()

            for source_name, retention_days in subs:
                if not source_name or not retention_days:
                    continue

                cutoff_date = (datetime.utcnow() - timedelta(days=retention_days)).strftime('%Y-%m-%d')
                cursor.execute(
                    '''
                    DELETE FROM articles
                    WHERE source = ?
                      AND status = 'pending'
                      AND published IS NOT NULL
                      AND published != ''
                      AND substr(published, 1, 10) < ?
                    ''',
                    (source_name, cutoff_date)
                )
                current_deleted = cursor.rowcount
                deleted_count += current_deleted
                if return_details and current_deleted:
                    details.append({
                        'source_name': source_name,
                        'count': current_deleted,
                        'retention_days': retention_days
                    })

        if return_details:
            return {
                'deleted_count': deleted_count,
                'details': details
            }
        return deleted_count

    def update_translation(self, article_id, translated_title, translated_summary):
        # 更新中文翻译内容及状态
        status = 'done' if "翻译出错" not in translated_title else 'error'
        with self._conn(write=True) as conn:
            conn.execute('''
                UPDATE articles
                SET translated_title = ?, translated_summary = ?, trans_status = ?
                WHERE article_id = ?
            ''', (translated_title, translated_summary, status, article_id))
            # 同步更新归档表中的翻译标题
            if status == 'done':
                conn.execute('''
                    UPDATE archive_articles
                    SET translated_title = ?
                    WHERE article_id = ?
                ''', (translated_title, article_id))

    def update_trans_status(self, article_id, status):
        # 仅更新翻译状态 (如设置为 translating)
        with self._conn(write=True) as conn:
            conn.execute('UPDATE articles SET trans_status = ? WHERE article_id = ?', (status, article_id))

    def claim_articles_for_translation(self, source=None):
        """原子领取指定来源中所有待翻译文章，避免重复提交。"""
        with self._conn(write=True) as conn:
            params = []
            where = "COALESCE(TRIM(translated_title), '') = '' AND COALESCE(trans_status, 'none') != 'translating'"
            if source:
                where += ' AND source = ?'
                params.append(source)
            rows = conn.execute(f'SELECT * FROM articles WHERE {where} ORDER BY id', params).fetchall()
            if not rows:
                return []
            ids = [row['id'] for row in rows]
            placeholders = ','.join('?' for _ in ids)
            conn.execute(
                f"UPDATE articles SET trans_status = 'translating' WHERE id IN ({placeholders})",
                ids
            )
        return [dict(row) for row in rows]

    def reset_translating_status(self):
        # 恢复由于程序中断导致的处于 translating 状态的文献为 error，从而实现断点恢复支持
        with self._conn(write=True) as conn:
            conn.execute("UPDATE articles SET trans_status = 'error' WHERE trans_status = 'translating'")

    def clear_articles(self, status='pending', source=None):
        # 清空特定状态下的文章，如果指定了source则仅清空该source下的文章
        with self._conn(write=True) as conn:
            if source:
                conn.execute('DELETE FROM articles WHERE status = ? AND source = ?', (status, source))
            else:
                conn.execute('DELETE FROM articles WHERE status = ?', (status,))

    def get_articles_by_status_paginated(self, status='pending', source=None, sort_by='id_desc', page=1, page_size=20):
        # 文库分页查询，避免列表一次性加载过多记录
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        order_clause = "ORDER BY id DESC"
        if sort_by == 'published_desc':
            order_clause = "ORDER BY published DESC"
        elif sort_by == 'read_status':
            # 未读优先时继续保持发布时间和入库顺序稳定
            order_clause = "ORDER BY is_read ASC, published DESC, id DESC"

        requested_page = max(int(page), 1)
        page_size = max(int(page_size), 1)

        if source:
            cursor.execute('SELECT COUNT(*) FROM articles WHERE status = ? AND source = ?', (status, source))
            total_count = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT COUNT(*) FROM articles WHERE status = ?', (status,))
            total_count = cursor.fetchone()[0]

        total_pages = max((total_count + page_size - 1) // page_size, 1)
        current_page = min(requested_page, total_pages)
        offset = (current_page - 1) * page_size

        if source:
            cursor.execute(
                f'SELECT * FROM articles WHERE status = ? AND source = ? {order_clause} LIMIT ? OFFSET ?',
                (status, source, page_size, offset)
            )
        else:
            cursor.execute(
                f'SELECT * FROM articles WHERE status = ? {order_clause} LIMIT ? OFFSET ?',
                (status, page_size, offset)
            )

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows], total_count, total_pages, current_page

    def get_articles_by_source(self, source=None, sort_by='published_desc'):
        # 获取指定来源的所有文献（不区分状态，包含 pending 和 saved）
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        order_clause = "ORDER BY published DESC"
        if sort_by == 'id_desc':
            order_clause = "ORDER BY id DESC"
        elif sort_by == 'read_status':
            # 收件箱按阅读状态排序时，将未读条目优先显示，便于快速处理
            order_clause = "ORDER BY is_read ASC, published DESC, id DESC"
            
        if source:
            cursor.execute(f'SELECT * FROM articles WHERE source = ? {order_clause}', (source,))
        else:
            cursor.execute(f'SELECT * FROM articles {order_clause}')
            
        rows = cursor.fetchall()
        
        conn.close()
        return [dict(row) for row in rows]

    def get_articles_by_source_paginated(self, source=None, sort_by='published_desc', page=1, page_size=20):
        # 收件箱分页查询，避免列表过长时渲染过慢
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        order_clause = "ORDER BY published DESC"
        if sort_by == 'id_desc':
            order_clause = "ORDER BY id DESC"
        elif sort_by == 'read_status':
            # 收件箱按阅读状态排序时，将未读条目优先显示
            order_clause = "ORDER BY is_read ASC, published DESC, id DESC"

        requested_page = max(int(page), 1)
        page_size = max(int(page_size), 1)

        if source:
            cursor.execute('SELECT COUNT(*) FROM articles WHERE source = ?', (source,))
            total_count = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT COUNT(*) FROM articles')
            total_count = cursor.fetchone()[0]

        total_pages = max((total_count + page_size - 1) // page_size, 1)
        current_page = min(requested_page, total_pages)
        offset = (current_page - 1) * page_size

        if source:
            cursor.execute(
                f'SELECT * FROM articles WHERE source = ? {order_clause} LIMIT ? OFFSET ?',
                (source, page_size, offset)
            )
        else:
            cursor.execute(
                f'SELECT * FROM articles {order_clause} LIMIT ? OFFSET ?',
                (page_size, offset)
            )

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows], total_count, total_pages, current_page

    def get_unique_sources(self):
        # 获取所有不重复的来源列表（不区分状态）
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT source FROM articles WHERE source IS NOT NULL')
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_unique_sources_by_status(self, status='pending'):
        # 获取指定状态下所有不重复的来源列表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT source FROM articles WHERE status = ? AND source IS NOT NULL', (status,))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def update_article_status(self, db_id, new_status):
        # 更新单篇文章的状态（如：将 pending 转为 saved）
        with self._conn(write=True) as conn:
            conn.execute('UPDATE articles SET status = ? WHERE id = ?', (new_status, db_id))

    def update_article_status_by_article_id(self, article_id, new_status):
        # 根据唯一标识更新文章状态
        with self._conn(write=True) as conn:
            conn.execute('UPDATE articles SET status = ? WHERE article_id = ?', (new_status, article_id))

    def update_article_read_status(self, db_id, is_read=1):
        # 更新单篇文章的已读状态
        with self._conn(write=True) as conn:
            conn.execute('UPDATE articles SET is_read = ? WHERE id = ?', (is_read, db_id))

    def toggle_follow(self, db_id):
        # 单事务读改写，避免并发调用相互覆盖
        with self._conn(write=True) as conn:
            row = conn.execute('SELECT is_followed FROM articles WHERE id = ?', (db_id,)).fetchone()
            if not row:
                return None
            new_status = 1 if row[0] == 0 else 0
            conn.execute('UPDATE articles SET is_followed = ? WHERE id = ?', (new_status, db_id))
            return new_status

    def get_unread_counts_by_source(self):
        # 获取各期刊来源的未读数量（针对 pending 状态的文献）
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT source, COUNT(*) 
            FROM articles 
            WHERE status = 'pending' AND is_read = 0 AND source IS NOT NULL 
            GROUP BY source
        ''')
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}

    def delete_articles_by_source(self, source, status='pending'):
        # 彻底删除某个来源的特定状态文章（默认待处理）
        with self._conn(write=True) as conn:
            conn.execute('DELETE FROM articles WHERE source = ? AND status = ?', (source, status))

    def get_all_articles(self):
        # 获取所有文献，按ID降序排列，方便展示最新的
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM articles ORDER BY id DESC')
        rows = cursor.fetchall()
        
        conn.close()
        return [dict(row) for row in rows]

    def get_article_by_id(self, db_id):
        # 通过数据库自增ID获取单篇文章详情
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM articles WHERE id = ?', (db_id,))
        row = cursor.fetchone()

        conn.close()
        return dict(row) if row else None

    def get_adjacent_articles(self, db_id, status=None, source=None):
        """获取相邻文章 ID（上一篇/下一篇），用于详情页导航。

        优先在同 status+source 范围内查找，若未找到则放宽条件。
        返回 (prev_id, next_id)，无相邻时返回 None。
        """
        article = self.get_article_by_id(db_id)
        if not article:
            return None, None

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 优先：同状态同来源
        filters = [('status', status or article.get('status', 'pending')),
                   ('source', source or article.get('source', ''))]

        def _query_one(direction, where_clauses, params):
            """单方向查询：direction='prev' 查 id < db_id ORDER BY id DESC,
                          direction='next' 查 id > db_id ORDER BY id ASC"""
            op = '<' if direction == 'prev' else '>'
            order = 'DESC' if direction == 'prev' else 'ASC'
            clause = ' AND '.join(where_clauses) if where_clauses else '1=1'
            base = f'SELECT id FROM articles WHERE {clause}'
            cursor.execute(f'{base} AND id {op} ? ORDER BY id {order} LIMIT 1', params + [db_id])
            row = cursor.fetchone()
            return row['id'] if row else None

        # 每个方向独立三级回退
        def _find(direction):
            status_val = status or article.get('status', 'pending')
            source_val = source or article.get('source', '')
            # 第一轮：同 status+source
            result = _query_one(direction, ['status = ?', 'source = ?'], [status_val, source_val])
            if result is not None:
                return result
            # 第二轮：只按 status
            result = _query_one(direction, ['status = ?'], [status_val])
            if result is not None:
                return result
            # 第三轮：不限
            return _query_one(direction, [], [])

        prev_id = _find('prev')
        next_id = _find('next')

        conn.close()
        return prev_id, next_id

    def get_articles_for_recommendation(self, sources=None, read_status='unread'):
        # 获取文献（用于大模型智能推荐），支持来源和阅读状态筛选
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM articles WHERE 1=1"
        params = []
        
        if sources:
            placeholders = ','.join('?' for _ in sources)
            query += f" AND source IN ({placeholders})"
            params.extend(sources)
            
        if read_status == 'unread':
            query += " AND is_read = 0"
        elif read_status == 'read':
            query += " AND is_read = 1"
        # 如果 read_status == 'all'，则不限制 is_read
            
        query += " ORDER BY published DESC"
        
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_articles_by_ids(self, article_ids):
        # 批量获取文献列表
        if not article_ids:
            return []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        placeholders = ','.join('?' for _ in article_ids)
        query = f'SELECT * FROM articles WHERE id IN ({placeholders})'
        cursor.execute(query, article_ids)
        rows = cursor.fetchall()
        conn.close()
        
        # 保持原始 ID 列表的顺序
        article_dict = {row['id']: dict(row) for row in rows}
        return [article_dict[id] for id in article_ids if id in article_dict]

    def get_articles_by_trans_status(self, trans_status):
        # 获取特定翻译状态的文献
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles WHERE trans_status = ?', (trans_status,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def set_config(self, key, value):
        with self._conn(write=True) as conn:
            conn.execute('''
                INSERT INTO config (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            ''', (key, value))

    def get_config(self, key, default=None):
        with self._conn() as conn:
            row = conn.execute('SELECT value FROM config WHERE key = ?', (key,)).fetchone()
        return row[0] if row else default

    def get_today_articles(self, limit=200):
        """获取今天抓取到的所有文献 (status='pending')"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        today = time.strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT id, title, summary, source, published, category, translated_title FROM articles WHERE status='pending' AND published LIKE ? ORDER BY published DESC LIMIT ?",
            (f'{today}%', limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_today_stats(self):
        """获取今日文献统计"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        today = time.strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT source, COUNT(*) as cnt FROM articles WHERE status='pending' AND published LIKE ? GROUP BY source ORDER BY cnt DESC",
            (f'{today}%',)
        )
        by_source = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            "SELECT category, COUNT(*) as cnt FROM articles WHERE status='pending' AND published LIKE ? AND category != '' GROUP BY category ORDER BY cnt DESC",
            (f'{today}%',)
        )
        by_category = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            "SELECT COUNT(*) as total FROM articles WHERE status='pending' AND published LIKE ?",
            (f'{today}%',)
        )
        total = cursor.fetchone()['total']
        conn.close()
        return {'total': total, 'by_source': by_source, 'by_category': by_category}

    def get_recent_dashboard(self, limit=200):
        """获取最近入库的待处理文献，用于首页展示刚抓取的内容。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, summary, source, published, category, translated_title FROM articles WHERE status='pending' ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        articles = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            "SELECT source, COUNT(*) as cnt FROM (SELECT source FROM articles WHERE status='pending' ORDER BY id DESC LIMIT ?) GROUP BY source ORDER BY cnt DESC",
            (limit,)
        )
        by_source = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            "SELECT category, COUNT(*) as cnt FROM (SELECT category FROM articles WHERE status='pending' AND category != '' ORDER BY id DESC LIMIT ?) GROUP BY category ORDER BY cnt DESC",
            (limit,)
        )
        by_category = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return {
            'total': len(articles),
            'by_source': by_source,
            'by_category': by_category,
            'articles': articles,
        }

    def get_dashboard_kpis(self):
        """首页 KPI：今日新增、未读待处理、订阅来源数、近7天新增。"""
        today = time.strftime('%Y-%m-%d')
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        with self._conn() as conn:
            today_new = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE status='pending' AND published LIKE ?",
                (f'{today}%',)
            ).fetchone()[0]
            unread = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE status='pending' AND is_read=0"
            ).fetchone()[0]
            sources = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
            week_new = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE status='pending' AND substr(published,1,10) >= ?",
                (week_ago,)
            ).fetchone()[0]
        return {'today_new': today_new, 'unread': unread, 'sources': sources, 'week_new': week_new}

    def set_article_category(self, article_id, category):
        """设置文献分类"""
        with self._conn(write=True) as conn:
            conn.execute("UPDATE articles SET category = ? WHERE id = ?", (category, article_id))

    def get_uncategorized_articles(self, limit=50):
        """获取今天未分类的文献"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        today = time.strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT id, title, summary FROM articles WHERE status='pending' AND published LIKE ? AND (category IS NULL OR category = '') LIMIT ?",
            (f'{today}%', limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
