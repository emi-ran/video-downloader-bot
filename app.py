import os
import uuid
import threading
import time
import base64
import requests
from datetime import datetime, timedelta
from flask import Flask, request, render_template, send_from_directory, jsonify, url_for
from youtubeDownloader import get_video_title, get_video_streams, get_audio_streams, download_video
from instagramDownloader import download_instagram_video, get_instagram_info
from tiktokDownloader import download_tiktok_video, get_tiktok_info
from pytubefix import YouTube
from database import init_db, add_download, update_download_count, get_total_statistics, get_platform_statistics, get_recent_downloads

app = Flask(__name__)
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
                file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp4")
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
    
    if not url or not platform:
        return jsonify({'success': False, 'error': 'Eksik parametre.'}), 400
    
    file_id = str(uuid.uuid4())
    out_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp4")
    
    # İşlem başlangıç zamanı
    start_time = time.time()
    
    try:
        # YouTube
        if platform == 'youtube':
            # audio_index None ise None olarak geç, 0 değil
            status, result = download_video(url, video_index, audio_index if audio_index is not None else None)
            if not status:
                # Hata durumunu veritabanına kaydet
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
    file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp4")
    if not os.path.exists(file_path):
        return "Dosya bulunamadı veya süresi doldu.", 404
    
    # İndirme sayısını artır (basit bir yaklaşım)
    try:
        update_download_count(file_id)
    except:
        pass  # Hata durumunda işlemi durdurma
    
    return send_from_directory(DOWNLOAD_DIR, f"{file_id}.mp4", as_attachment=True)

@app.route('/api/statistics')
def api_statistics():
    """İstatistik API endpoint'i"""
    try:
        total_stats = get_total_statistics()
        platform_stats = get_platform_statistics()
        recent_downloads = get_recent_downloads(5)
        
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
            ],
            'recent_downloads': [
                {
                    'id': row[0],
                    'ip_address': row[1],
                    'platform': row[2],
                    'video_title': row[3],
                    'video_quality': row[4],
                    'file_size': row[5],
                    'processing_time': row[6],
                    'status': row[7],
                    'timestamp': row[8]
                }
                for row in recent_downloads
            ]
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

if __name__ == '__main__':
    app.run(debug=True) 