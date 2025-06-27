import os
import re
from urllib.parse import urlparse
from yt_dlp import YoutubeDL

def safe_filename(s: str) -> str:
    s = re.sub(r'[^\w\-_. ]', '_', s)
    s = s.replace(' ', '_')
    return s

def download_instagram_video(insta_url: str, output_dir: str = "videos") -> tuple[bool, str]:
    """
    Verilen Instagram video (reels dahil) linkinden en yüksek kalitede videoyu indirir.
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
            info = ydl.extract_info(insta_url, download=True)
            filename = ydl.prepare_filename(info)
            # Dosya adını güvenli hale getir
            base = safe_filename(os.path.splitext(os.path.basename(filename))[0])
            final_path = os.path.join(output_dir, f"{base}.mp4")
            if filename != final_path:
                os.rename(filename, final_path)
            return True, final_path
    except Exception as e:
        return False, f"Video indirme hatası: {e}"