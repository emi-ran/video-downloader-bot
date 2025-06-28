import sqlite3
from datetime import datetime, timedelta
import os

DB_PATH = "downloads.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT,
                user_agent TEXT,
                platform TEXT,
                link TEXT,
                video_title TEXT,
                video_quality TEXT,
                file_size INTEGER,
                processing_time REAL,
                status TEXT,
                error_message TEXT,
                timestamp TEXT,
                download_count INTEGER DEFAULT 0
            )
        ''')
        
        # İstatistikler için ayrı tablo
        c.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                platform TEXT,
                total_downloads INTEGER DEFAULT 0,
                successful_downloads INTEGER DEFAULT 0,
                failed_downloads INTEGER DEFAULT 0,
                total_file_size INTEGER DEFAULT 0,
                avg_processing_time REAL DEFAULT 0
            )
        ''')
        
        # Günlük istatistikler için index
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_statistics_date 
            ON statistics(date)
        ''')
        
        # Downloads tablosu için indexler
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_downloads_timestamp 
            ON downloads(timestamp)
        ''')
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_downloads_platform 
            ON downloads(platform)
        ''')
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_downloads_status 
            ON downloads(status)
        ''')
        
        conn.commit()

def add_download(ip_address: str, user_agent: str, platform: str, link: str, 
                 video_title: str = None, video_quality: str = None, 
                 file_size: int = None, processing_time: float = None, 
                 status: str = "success", error_message: str = None):
    """İndirme işlemini veritabanına kaydet"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO downloads 
            (ip_address, user_agent, platform, link, video_title, video_quality, 
             file_size, processing_time, status, error_message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ip_address, user_agent, platform, link, video_title, video_quality,
              file_size, processing_time, status, error_message, 
              datetime.utcnow().isoformat()))
        conn.commit()

def update_download_count(file_id: str):
    """Dosya indirme sayısını artır"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            UPDATE downloads 
            SET download_count = download_count + 1 
            WHERE id = ?
        ''', (file_id,))
        conn.commit()

def get_daily_statistics(date: str = None):
    """Günlük istatistikleri getir"""
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT 
                platform,
                COUNT(*) as total_downloads,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_downloads,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_downloads,
                SUM(file_size) as total_file_size,
                AVG(processing_time) as avg_processing_time
            FROM downloads 
            WHERE DATE(timestamp) = ?
            GROUP BY platform
        ''', (date,))
        
        return c.fetchall()

def get_platform_statistics():
    """Platform bazında genel istatistikler"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT 
                platform,
                COUNT(*) as total_downloads,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_downloads,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_downloads,
                SUM(file_size) as total_file_size,
                AVG(processing_time) as avg_processing_time
            FROM downloads 
            GROUP BY platform
        ''')
        
        return c.fetchall()

def get_recent_downloads(limit: int = 10):
    """Son indirmeleri getir"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT 
                id, ip_address, platform, video_title, video_quality, 
                file_size, processing_time, status, timestamp
            FROM downloads 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        return c.fetchall()

def get_total_statistics():
    """Genel toplam istatistikler"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT 
                COUNT(*) as total_downloads,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_downloads,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_downloads,
                SUM(file_size) as total_file_size,
                AVG(processing_time) as avg_processing_time
            FROM downloads
        ''')
        
        return c.fetchone()

def cleanup_old_records(days: int = 30):
    """Eski kayıtları temizle"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        c.execute('''
            DELETE FROM downloads 
            WHERE timestamp < ?
        ''', (cutoff_date,))
        conn.commit() 