import os
import uuid
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, render_template, send_from_directory, jsonify, url_for
from youtubeDownloader import get_video_title, get_video_streams, get_audio_streams, download_video
from instagramDownloader import download_instagram_video
from tiktokDownloader import download_tiktok_video
from pytubefix import YouTube

app = Flask(__name__)
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

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
        status, streams = get_video_streams(url)
        if not status:
            return jsonify({'success': False, 'error': streams}), 400
        # Kapak fotoğrafı
        try:
            thumbnail_url = YouTube(url).thumbnail_url
        except Exception:
            thumbnail_url = None
        return jsonify({'success': True, 'platform': 'youtube', 'title': title, 'streams': streams, 'thumbnail_url': thumbnail_url})
    elif any(domain in url for domain in ['instagram.com', 'instagr.am']):
        return jsonify({'success': True, 'platform': 'instagram'})
    elif any(domain in url for domain in ['tiktok.com', 'vm.tiktok.com']):
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
    if not url or not platform:
        return jsonify({'success': False, 'error': 'Eksik parametre.'}), 400
    file_id = str(uuid.uuid4())
    out_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp4")
    # YouTube
    if platform == 'youtube':
        status, result = download_video(url, video_index, audio_index)
        if not status:
            return jsonify({'success': False, 'error': result}), 400
        os.rename(result, out_path)
    elif platform == 'instagram':
        status, result = download_instagram_video(url, output_dir=DOWNLOAD_DIR)
        if not status:
            return jsonify({'success': False, 'error': result}), 400
        os.rename(result, out_path)
    elif platform == 'tiktok':
        status, result = download_tiktok_video(url, output_dir=DOWNLOAD_DIR)
        if not status:
            return jsonify({'success': False, 'error': result}), 400
        os.rename(result, out_path)
    else:
        return jsonify({'success': False, 'error': 'Bilinmeyen platform.'}), 400
    file_registry[file_id] = time.time()
    save_registry()
    download_url = url_for('download_file', file_id=file_id, _external=True)
    return jsonify({'success': True, 'download_url': download_url, 'info': 'Bu dosya 1 saat boyunca indirilebilir, sonra silinecek.'})

@app.route('/download/<file_id>')
def download_file(file_id):
    file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp4")
    if not os.path.exists(file_path):
        return "Dosya bulunamadı veya süresi doldu.", 404
    return send_from_directory(DOWNLOAD_DIR, f"{file_id}.mp4", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True) 