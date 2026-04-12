import sqlite3
from fetcher import parse_to_iso

def migrate_published_dates():
    conn = sqlite3.connect('articles.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. 迁移主表日期格式
    cursor.execute("SELECT id, published FROM articles WHERE published IS NOT NULL AND published != ''")
    rows = cursor.fetchall()
    
    updated_count = 0
    for row in rows:
        old_date = row['published']
        new_date = parse_to_iso(old_date)
        if old_date != new_date:
            cursor.execute("UPDATE articles SET published = ? WHERE id = ?", (new_date, row['id']))
            updated_count += 1
            
    print(f"Successfully migrated {updated_count} article dates to ISO format in main table.")
    
    # 2. 修复归档表缺失的 published 数据
    # 从主表中获取对应的 published 时间并更新回归档表
    cursor.execute('''
        UPDATE archive_articles
        SET published = (
            SELECT published 
            FROM articles 
            WHERE articles.article_id = archive_articles.article_id
        )
        WHERE published IS NULL OR published = ''
    ''')
    archive_updated = cursor.rowcount
    print(f"Successfully populated {archive_updated} published dates in archive_articles.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate_published_dates()
