import os
import re
from yt_dlp import YoutubeDL

def safe_filename(s: str) -> str:
    s = re.sub(r'[^\w\-_. ]', '_', s)
    s = s.replace(' ', '_')
    return s

def get_tiktok_info(tiktok_url: str) -> tuple[bool, dict]:
    """
    TikTok video bilgilerini alır (indirmeden).
    Başarılıysa (True, bilgi_dict), başarısızsa (False, hata_mesajı) döndürür.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(tiktok_url, download=False)
            
            # Thumbnail URL'sini farklı alanlardan almaya çalış
            thumbnail = None
            if info.get('thumbnail'):
                thumbnail = info.get('thumbnail')
            elif info.get('thumbnails') and len(info.get('thumbnails', [])) > 0:
                # En yüksek kaliteli thumbnail'i al
                thumbnails = info.get('thumbnails', [])
                best_thumb = max(thumbnails, key=lambda x: x.get('height', 0) if x.get('height') else 0)
                thumbnail = best_thumb.get('url')
            
            # Bilgileri çıkar
            video_info = {
                'title': info.get('title', 'TikTok Video'),
                'duration': info.get('duration'),
                'thumbnail': thumbnail,
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'comment_count': info.get('comment_count'),
                'id': info.get('id'),
                'webpage_url': info.get('webpage_url'),
            }
            
            print(f"TikTok info: {video_info}")  # Debug için
            
            return True, video_info
    except Exception as e:
        print(f"TikTok info error: {e}")  # Debug için
        return False, f"Bilgi alma hatası: {e}"

def download_tiktok_video(tiktok_url: str, output_dir: str = "videos") -> tuple[bool, str]:
    """
    Verilen TikTok video linkinden en yüksek kalitede videoyu indirir.
    Başarılıysa (True, dosya_yolu), başarısızsa (False, hata_mesajı) döndürür.
    """
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts = {
        'format': 'mp4',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(tiktok_url, download=True)
            filename = ydl.prepare_filename(info)
            # Dosya adını güvenli hale getir
            base = safe_filename(os.path.splitext(os.path.basename(filename))[0])
            final_path = os.path.join(output_dir, f"{base}.mp4")
            if filename != final_path:
                os.rename(filename, final_path)
            return True, final_path
    except Exception as e:
        return False, f"Video indirme hatası: {e}" 