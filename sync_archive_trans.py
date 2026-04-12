import sqlite3

def sync_translations_to_archive():
    conn = sqlite3.connect('articles.db')
    cursor = conn.cursor()
    
    # 将主表中已经有翻译的文献（translated_title 不为空），同步回归档表
    cursor.execute('''
        UPDATE archive_articles
        SET translated_title = (
            SELECT translated_title 
            FROM articles 
            WHERE articles.article_id = archive_articles.article_id
            AND articles.translated_title IS NOT NULL 
            AND articles.translated_title != ''
        )
        WHERE EXISTS (
            SELECT 1 
            FROM articles 
            WHERE articles.article_id = archive_articles.article_id
            AND articles.translated_title IS NOT NULL 
            AND articles.translated_title != ''
        )
    ''')
    
    updated_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"Successfully synced {updated_count} translated titles to archive_articles.")

if __name__ == "__main__":
    sync_translations_to_archive()
