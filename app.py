import os
import uuid
import threading
import time
import base64
import requests
from datetime import datetime, timedelta
from flask import Flask, request, render_template, send_from_directory, jsonify, url_for, session, redirect
from youtubeDownloader import get_video_title, get_video_streams, get_audio_streams, download_video, download_audio_as_mp3
from instagramDownloader import download_instagram_video, get_instagram_info
from tiktokDownloader import download_tiktok_video, get_tiktok_info
from pytubefix import YouTube
from database import init_db, add_download, update_download_count, get_total_statistics, get_platform_statistics, get_recent_downloads
from config import config
import sqlite3
import shutil

# Environment'dan config seçimi
config_name = os.environ.get('FLASK_ENV', 'default')
app = Flask(__name__)
app.config.from_object(config[config_name])

# Admin yetkisi kontrolü için decorator
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return jsonify({'success': False, 'error': 'Yetkisiz erişim'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Veritabanını başlat
init_db()

# Her dosyanın oluşturulma zamanı tutulacak
file_registry = {}
REGISTRY_PATH = os.path.join(DOWNLOAD_DIR, 'file_registry.txt')

# Registry'yi dosyadan yükle/kaydet (basit çözüm, ileride sqlite ile değiştirilebilir)
def save_registry():
    with open(REGISTRY_PATH, 'w') as f:
        for k, v in file_registry.items():
            f.write(f"{k},{v}\n")
def load_registry():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, 'r') as f:
            for line in f:
                k, v = line.strip().split(',')
                file_registry[k] = float(v)
load_registry()

def cleanup_files():
    while True:
        now = time.time()
        to_delete = []
        for file_id, ts in list(file_registry.items()):
            if now - ts > 3600:  # 1 saat
                # Hem .mp4 hem .mp3 dosyalarını kontrol et
                for ext in ['mp4', 'mp3']:
                    file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.{ext}")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                to_delete.append(file_id)
        for file_id in to_delete:
            file_registry.pop(file_id, None)
        save_registry()
        time.sleep(600)  # 10 dakikada bir kontrol

threading.Thread(target=cleanup_files, daemon=True).start()

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def api_process():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'Link gerekli.'}), 400
    
    # Platform algılama
    if any(domain in url for domain in ['youtube.com', 'youtu.be']):
        status, title = get_video_title(url)
        if not status:
            return jsonify({'success': False, 'error': title}), 400
        
        status, video_streams = get_video_streams(url)
        if not status:
            return jsonify({'success': False, 'error': video_streams}), 400
        
        # Ses stream'lerini de al
        status, audio_streams = get_audio_streams(url)
        if not status:
            audio_streams = []
        
        # Her ses stream'ine mp3 seçeneği ekle (frontend için)
        for stream in audio_streams:
            stream['mp3_available'] = True
        
        # Kapak fotoğrafı
        try:
            thumbnail_url = YouTube(url).thumbnail_url
        except Exception:
            thumbnail_url = None
        
        return jsonify({
            'success': True, 
            'platform': 'youtube', 
            'title': title, 
            'video_streams': video_streams,
            'audio_streams': audio_streams,
            'thumbnail_url': thumbnail_url
        })
    elif any(domain in url for domain in ['instagram.com', 'instagr.am']):
        try:
            # Instagram video bilgilerini almaya çalış
            status, info = get_instagram_info(url)
            
            if status:
                # Thumbnail'ı base64 olarak indir
                thumbnail_data = None
                if info.get('thumbnail'):
                    thumbnail_data = download_thumbnail_as_base64(info.get('thumbnail'))
                
                return jsonify({
                    'success': True, 
                    'platform': 'instagram',
                    'title': info.get('title', 'Instagram Video'),
                    'thumbnail_url': thumbnail_data,  # Base64 data URL
                    'duration': info.get('duration', None)
                })
            else:
                # Bilgi alınamazsa basit yanıt döndür
                return jsonify({'success': True, 'platform': 'instagram'})
        except Exception as e:
            # Hata durumunda basit yanıt döndür
            return jsonify({'success': True, 'platform': 'instagram'})
    elif any(domain in url for domain in ['tiktok.com', 'vm.tiktok.com']):
        try:
            # TikTok video bilgilerini almaya çalış
            status, info = get_tiktok_info(url)
            
            if status:
                # Thumbnail'ı base64 olarak indir
                thumbnail_data = None
                if info.get('thumbnail'):
                    thumbnail_data = download_thumbnail_as_base64(info.get('thumbnail'))
                
                return jsonify({
                    'success': True, 
                    'platform': 'tiktok',
                    'title': info.get('title', 'TikTok Video'),
                    'thumbnail_url': thumbnail_data,  # Base64 data URL
                    'duration': info.get('duration', None)
                })
            else:
                # Bilgi alınamazsa basit yanıt döndür
                return jsonify({'success': True, 'platform': 'tiktok'})
        except Exception as e:
            # Hata durumunda basit yanıt döndür
            return jsonify({'success': True, 'platform': 'tiktok'})
    else:
        return jsonify({'success': False, 'error': 'Desteklenmeyen platform.'}), 400

@app.route('/api/convert', methods=['POST'])
def api_convert():
    data = request.json
    url = data.get('url')
    platform = data.get('platform')
    video_index = data.get('video_index')
    audio_index = data.get('audio_index')
    video_title = data.get('video_title')
    video_quality = data.get('video_quality')
    mp3 = data.get('mp3')  # yeni parametre: mp3 olarak mı indirilecek?
    
    if not url or not platform:
        return jsonify({'success': False, 'error': 'Eksik parametre.'}), 400
    
    file_id = str(uuid.uuid4())
    # mp3 ise dosya uzantısı mp3 olacak
    out_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3" if mp3 else f"{file_id}.mp4")
    
    # İşlem başlangıç zamanı
    start_time = time.time()
    
    try:
        if platform == 'youtube' and mp3:
            # Sadece ses stream'i seçildi ve mp3 olarak indirilecek
            status, result = download_audio_as_mp3(url, audio_index)
            if not status:
                add_download(
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', ''),
                    platform=platform,
                    link=url,
                    video_title=video_title,
                    video_quality=video_quality,
                    status="error",
                    error_message=result
                )
                return jsonify({'success': False, 'error': result}), 400
            os.rename(result, out_path)
        elif platform == 'youtube':
            # video_index ve audio_index ile video indirme işlemi
            status, result = download_video(url, video_index, audio_index if audio_index is not None else None)
            if not status:
                add_download(
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', ''),
                    platform=platform,
                    link=url,
                    video_title=video_title,
                    video_quality=video_quality,
                    status="error",
                    error_message=result
                )
                return jsonify({'success': False, 'error': result}), 400
            os.rename(result, out_path)
        elif platform == 'instagram':
            status, result = download_instagram_video(url, output_dir=DOWNLOAD_DIR)
            if not status:
                add_download(
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', ''),
                    platform=platform,
                    link=url,
                    status="error",
                    error_message=result
                )
                return jsonify({'success': False, 'error': result}), 400
            os.rename(result, out_path)
        elif platform == 'tiktok':
            status, result = download_tiktok_video(url, output_dir=DOWNLOAD_DIR)
            if not status:
                add_download(
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', ''),
                    platform=platform,
                    link=url,
                    status="error",
                    error_message=result
                )
                return jsonify({'success': False, 'error': result}), 400
            os.rename(result, out_path)
        else:
            return jsonify({'success': False, 'error': 'Bilinmeyen platform.'}), 400
        
        # İşlem süresi ve dosya boyutu
        processing_time = time.time() - start_time
        file_size = os.path.getsize(out_path) if os.path.exists(out_path) else None
        
        # Başarılı işlemi veritabanına kaydet
        add_download(
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            platform=platform,
            link=url,
            video_title=video_title,
            video_quality=video_quality,
            file_size=file_size,
            processing_time=processing_time,
            status="success"
        )
        
        file_registry[file_id] = time.time()
        save_registry()
        download_url = url_for('download_file', file_id=file_id, _external=True)
        return jsonify({'success': True, 'download_url': download_url, 'info': 'Bu dosya 1 saat boyunca indirilebilir, sonra silinecek.'})
        
    except Exception as e:
        # Beklenmeyen hataları da kaydet
        add_download(
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            platform=platform,
            link=url,
            video_title=video_title,
            video_quality=video_quality,
            status="error",
            error_message=str(e)
        )
        return jsonify({'success': False, 'error': f'Beklenmeyen hata: {str(e)}'}), 500

@app.route('/download/<file_id>')
def download_file(file_id):
    mp4_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp4")
    mp3_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")
    if os.path.exists(mp4_path):
        file_name = f"{file_id}.mp4"
    elif os.path.exists(mp3_path):
        file_name = f"{file_id}.mp3"
    else:
        return "Dosya bulunamadı veya süresi doldu.", 404
    try:
        update_download_count(file_id)
    except:
        pass
    return send_from_directory(DOWNLOAD_DIR, file_name, as_attachment=True)

@app.route('/api/statistics')
def api_statistics():
    """İstatistik API endpoint'i"""
    try:
        total_stats = get_total_statistics()
        platform_stats = get_platform_statistics()
        # recent_downloads = get_recent_downloads(5)  # Artık kullanılmıyor
        return jsonify({
            'success': True,
            'total_statistics': {
                'total_downloads': total_stats[0] or 0,
                'successful_downloads': total_stats[1] or 0,
                'failed_downloads': total_stats[2] or 0,
                'total_file_size': total_stats[3] or 0,
                'avg_processing_time': total_stats[4] or 0
            },
            'platform_statistics': [
                {
                    'platform': row[0],
                    'total_downloads': row[1],
                    'successful_downloads': row[2],
                    'failed_downloads': row[3],
                    'total_file_size': row[4] or 0,
                    'avg_processing_time': row[5] or 0
                }
                for row in platform_stats
            ]
            # 'recent_downloads' alanı kaldırıldı
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def download_thumbnail_as_base64(url):
    """Thumbnail'ı indirip base64'e çevirir"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Base64'e çevir
        image_data = base64.b64encode(response.content).decode('utf-8')
        content_type = response.headers.get('content-type', 'image/jpeg')
        
        return f"data:{content_type};base64,{image_data}"
    except Exception as e:
        print(f"Thumbnail indirme hatası: {e}")
        return None

@app.route('/admin')
def admin_panel():
    # Giriş yapılmamışsa login sayfasına yönlendir
    if 'admin_logged_in' not in session:
        return redirect('/admin/login')
    return render_template('admin.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Kullanıcı adı ve şifre kontrolü
        if username == 'emiran' and password == 'Enesmal55!s':
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error='Geçersiz kullanıcı adı veya şifre!')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect('/admin/login')

@app.route('/admin.js')
@admin_required
def admin_js():
    return send_from_directory('templates', 'admin.js', mimetype='application/javascript')

@app.route('/api/admin/downloads')
@admin_required
def api_admin_downloads():
    # Parametreler: page, page_size, search, sort_by, sort_dir, platform, status, date_from, date_to
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_dir = request.args.get('sort_dir', 'desc')
    platform = request.args.get('platform')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    offset = (page - 1) * page_size
    params = []
    where = []

    if search:
        where.append("(video_title LIKE ? OR link LIKE ? OR ip_address LIKE ? OR user_agent LIKE ?)")
        params += [f"%{search}%"] * 4
    if platform:
        where.append("platform = ?")
        params.append(platform)
    if status:
        where.append("status = ?")
        params.append(status)
    if date_from:
        where.append("timestamp >= ?")
        params.append(date_from)
    if date_to:
        where.append("timestamp <= ?")
        params.append(date_to)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ''
    sort_sql = f"ORDER BY {sort_by} {sort_dir.upper()}"
    limit_sql = f"LIMIT ? OFFSET ?"
    params += [page_size, offset]

    with sqlite3.connect('downloads.db') as conn:
        c = conn.cursor()
        total_query = f"SELECT COUNT(*) FROM downloads {where_sql}"
        c.execute(total_query, params[:-2])
        total = c.fetchone()[0]

        query = f"SELECT id, ip_address, user_agent, platform, link, video_title, video_quality, file_size, processing_time, status, error_message, timestamp FROM downloads {where_sql} {sort_sql} {limit_sql}"
        c.execute(query, params)
        rows = c.fetchall()

    columns = ["id", "ip_address", "user_agent", "platform", "link", "video_title", "video_quality", "file_size", "processing_time", "status", "error_message", "timestamp"]
    data = [dict(zip(columns, row)) for row in rows]
    return jsonify({
        'success': True,
        'total': total,
        'page': page,
        'page_size': page_size,
        'data': data
    })

@app.route('/api/admin/charts')
@admin_required
def api_admin_charts():
    """Grafikler için veri döndürür"""
    try:
        with sqlite3.connect('downloads.db') as conn:
            c = conn.cursor()
            
            # Platform dağılımı
            c.execute('''
                SELECT platform, COUNT(*) as count 
                FROM downloads 
                GROUP BY platform 
                ORDER BY count DESC
            ''')
            platform_data = [{'platform': row[0], 'count': row[1]} for row in c.fetchall()]
            
            # Günlük indirme sayıları (son 30 gün)
            c.execute('''
                SELECT DATE(timestamp) as date, COUNT(*) as count 
                FROM downloads 
                WHERE timestamp >= date('now', '-30 days')
                GROUP BY DATE(timestamp) 
                ORDER BY date
            ''')
            daily_data = [{'date': row[0], 'count': row[1]} for row in c.fetchall()]
            
            # Başarı oranları
            c.execute('''
                SELECT 
                    platform,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed
                FROM downloads 
                GROUP BY platform
            ''')
            success_data = []
            for row in c.fetchall():
                platform, total, successful, failed = row
                success_rate = (successful / total * 100) if total > 0 else 0
                success_data.append({
                    'platform': platform,
                    'total': total,
                    'successful': successful,
                    'failed': failed,
                    'success_rate': round(success_rate, 1)
                })
            
            # Saatlik dağılım
            c.execute('''
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as count 
                FROM downloads 
                WHERE timestamp >= date('now', '-7 days')
                GROUP BY strftime('%H', timestamp) 
                ORDER BY hour
            ''')
            hourly_data = [{'hour': int(row[0]), 'count': row[1]} for row in c.fetchall()]
            
            # Dosya boyutu dağılımı
            c.execute('''
                SELECT 
                    CASE 
                        WHEN file_size < 1024*1024 THEN '0-1MB'
                        WHEN file_size < 10*1024*1024 THEN '1-10MB'
                        WHEN file_size < 50*1024*1024 THEN '10-50MB'
                        WHEN file_size < 100*1024*1024 THEN '50-100MB'
                        ELSE '100MB+'
                    END as size_range,
                    COUNT(*) as count
                FROM downloads 
                WHERE file_size IS NOT NULL
                GROUP BY size_range
                ORDER BY 
                    CASE size_range
                        WHEN '0-1MB' THEN 1
                        WHEN '1-10MB' THEN 2
                        WHEN '10-50MB' THEN 3
                        WHEN '50-100MB' THEN 4
                        ELSE 5
                    END
            ''')
            size_data = [{'range': row[0], 'count': row[1]} for row in c.fetchall()]
            
            # Genel istatistikler
            c.execute('''
                SELECT 
                    AVG(file_size) as avg_file_size,
                    AVG(processing_time) as avg_processing_time,
                    COUNT(*) as total_downloads,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_downloads
                FROM downloads 
                WHERE file_size IS NOT NULL AND processing_time IS NOT NULL
            ''')
            general_stats = c.fetchone()
            
            return jsonify({
                'success': True,
                'platform_distribution': platform_data,
                'daily_downloads': daily_data,
                'success_rates': success_data,
                'hourly_distribution': hourly_data,
                'file_size_distribution': size_data,
                'general_stats': {
                    'avg_file_size': general_stats[0] if general_stats[0] else 0,
                    'avg_processing_time': general_stats[1] if general_stats[1] else 0,
                    'total_downloads': general_stats[2] if general_stats[2] else 0,
                    'successful_downloads': general_stats[3] if general_stats[3] else 0
                }
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cut', methods=['POST'])
def api_cut():
    data = request.json
    file_id = data.get('file_id')
    start = data.get('start')
    end = data.get('end')
    if not file_id or start is None or end is None:
        return jsonify({'success': False, 'error': 'Eksik parametre.'}), 400
    # Dosya yolunu bul (mp4 veya mp3)
    mp4_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp4")
    mp3_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")
    if os.path.exists(mp4_path):
        input_path = mp4_path
        ext = 'mp4'
    elif os.path.exists(mp3_path):
        input_path = mp3_path
        ext = 'mp3'
    else:
        return jsonify({'success': False, 'error': 'Dosya bulunamadı veya süresi doldu.'}), 404
    # Yeni dosya adı
    cut_id = str(uuid.uuid4())
    output_path = os.path.join(DOWNLOAD_DIR, f"{cut_id}.{ext}")
    # ffmpeg ile kesme işlemi
    try:
        # ffmpeg komutu: -ss start -to end -i input -c copy output
        # -ss ve -to saniye cinsinden
        import subprocess
        cmd = [
            'ffmpeg',
            '-y',
            '-ss', str(start),
            '-to', str(end),
            '-i', input_path,
            '-c', 'copy',
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        # Dosya başarıyla oluşturulduysa registry'ye ekle
        file_registry[cut_id] = time.time()
        save_registry()
        # Dosya başarıyla oluşturulduysa linki döndür
        download_url = url_for('download_file', file_id=cut_id, _external=True)
        return jsonify({'success': True, 'download_url': download_url})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Kesme işlemi başarısız: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000) 