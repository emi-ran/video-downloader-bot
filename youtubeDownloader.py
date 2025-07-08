import os
import re
import subprocess
from pytubefix import YouTube
import unicodedata

def safe_filename(s: str) -> str:
    """Dosya adlarındaki özel karakterleri ve boşlukları temizler, Türkçe karakterleri ASCII'ye çevirir."""
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^\w\-_. ]', '_', s)
    s = s.replace(' ', '_')
    return s

def get_video_title(url: str) -> tuple[bool, str]:
    """Verilen YouTube linkinden video başlığını alır."""
    try:
        title = YouTube(url).title
        return True, title
    except Exception as e:
        return False, f"Başlık alınamadı: {e}"

def get_video_streams(url: str) -> tuple[bool, list | str]:
    """Verilen link için mevcut video stream'lerini JSON-uyumlu bir formatta döndürür."""
    try:
        yt = YouTube(url)
        streams = yt.streams.filter(type="video", file_extension='mp4').order_by('resolution').desc()
        stream_list = [
            {
                "index": i + 1,
                "resolution": stream.resolution,
                "fps": stream.fps,
                "bitrate_kbps": round(stream.bitrate / 1000) if hasattr(stream, 'bitrate') and stream.bitrate else None,
                "is_progressive": stream.is_progressive,
                "size_mb": round(stream.filesize / (1024*1024), 2) if stream.filesize else None,
            }
            for i, stream in enumerate(streams)
        ]
        return True, stream_list
    except Exception as e:
        return False, f"Video stream'leri alınamadı: {e}"

def get_audio_streams(url: str) -> tuple[bool, list | str]:
    """Verilen link için mevcut ses stream'lerini JSON-uyumlu bir formatta döndürür."""
    try:
        yt = YouTube(url)
        streams = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc()
        stream_list = [
            {
                "index": i + 1,
                "abr": stream.abr,
                "size_mb": round(stream.filesize / (1024*1024), 2) if stream.filesize else None,
            }
            for i, stream in enumerate(streams)
        ]
        return True, stream_list
    except Exception as e:
        return False, f"Ses stream'leri alınamadı: {e}"

def download_video(url: str, video_index: int, audio_index: int = None, progress_callback=None) -> tuple[bool, str]:
    """
    Verilen URL ve index seçimlerine göre videoyu indirir.
    'progress_callback' fonksiyonu indirme ilerlemesini takip etmek için kullanılır.
    Geçici dosyalar 'temp', son videolar 'videos' klasörüne kaydedilir.
    Başarılı olursa (True, dosya_yolu), başarısız olursa (False, hata_mesajı) döndürür.
    """
    videos_dir = "videos"
    temp_dir = "temp"
    os.makedirs(videos_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    video_filename, audio_filename = None, None
    try:
        yt = YouTube(url, on_progress_callback=progress_callback)
        title = yt.title
        base_name = safe_filename(title)

        video_streams = yt.streams.filter(type="video", file_extension='mp4').order_by('resolution').desc()
        if not (1 <= video_index <= len(video_streams)):
            raise ValueError("Geçersiz video indexi.")
        selected_video = video_streams[video_index - 1]

        if selected_video.is_progressive:
            output_filename = os.path.join(videos_dir, f"{base_name}.mp4")
            selected_video.download(output_path=videos_dir, filename=f"{base_name}.mp4")
            return True, output_filename

        if audio_index is None:
            raise ValueError("Adaptive stream için ses seçimi (audio_index) gereklidir.")

        audio_streams = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc()
        if not (1 <= audio_index <= len(audio_streams)):
            raise ValueError("Geçersiz ses indexi.")
        selected_audio = audio_streams[audio_index - 1]

        video_filename = os.path.join(temp_dir, f"{base_name}_video.mp4")
        audio_filename = os.path.join(temp_dir, f"{base_name}_audio.mp4")
        output_filename = os.path.join(videos_dir, f"{base_name}_output.mp4")
        
        selected_video.download(output_path=temp_dir, filename=f"{base_name}_video.mp4")
        selected_audio.download(output_path=temp_dir, filename=f"{base_name}_audio.mp4")

        cmd_fast = ["ffmpeg", "-y", "-i", video_filename, "-i", audio_filename, "-c", "copy", output_filename]
        try:
            subprocess.run(cmd_fast, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            cmd_safe = ["ffmpeg", "-y", "-i", video_filename, "-i", audio_filename, "-c:v", "copy", "-c:a", "aac", output_filename]
            subprocess.run(cmd_safe, check=True, capture_output=True, text=True)
            
        return True, output_filename

    except (ValueError, subprocess.CalledProcessError, Exception) as e:
        error_message = e.stderr if isinstance(e, subprocess.CalledProcessError) else str(e)
        return False, f"İndirme hatası: {error_message}"
    
    finally:
        if video_filename and os.path.exists(video_filename):
            os.remove(video_filename)
        if audio_filename and os.path.exists(audio_filename):
            os.remove(audio_filename)

def download_audio_as_mp3(url: str, audio_index: int) -> tuple[bool, str]:
    """
    Verilen YouTube linki ve ses stream indexine göre MP3 dosyası olarak indirir.
    Başarılı olursa (True, dosya_yolu), hata olursa (False, hata_mesajı) döndürür.
    """
    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp()
    try:
        yt = YouTube(url)
        audio_streams = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc()
        if not (1 <= audio_index <= len(audio_streams)):
            raise ValueError("Geçersiz ses indexi.")
        selected_audio = audio_streams[audio_index - 1]
        base_name = safe_filename(yt.title)
        audio_path = os.path.join(temp_dir, f"{base_name}_audio.mp4")
        mp3_path = os.path.join(temp_dir, f"{base_name}.mp3")
        selected_audio.download(output_path=temp_dir, filename=f"{base_name}_audio.mp4")
        # ffmpeg ile mp3'e çevir
        cmd = ["ffmpeg", "-y", "-i", audio_path, "-vn", "-ab", "192k", "-ar", "44100", "-f", "mp3", mp3_path]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True, mp3_path
    except Exception as e:
        return False, f"MP3 indirme hatası: {str(e)}"
    finally:
        # temp_dir ve dosyalar silinmez, çünkü dosya döndürülüyor. Temizlik işlemi indirme sonrası yapılabilir.
        pass

def main():
    """Ana program akışını yöneten ve kütüphane fonksiyonlarını test eden fonksiyon."""
    video_url = input("Lütfen indirmek istediğiniz YouTube video linkini girin: ")
    if not video_url:
        return

    status, title_or_error = get_video_title(video_url)
    if not status:
        print(f"Hata: {title_or_error}")
        return
    print(f"\nVideo Başlığı: {title_or_error}\n")

    status, video_streams_data = get_video_streams(video_url)
    if not status:
        print(f"Hata: {video_streams_data}")
        return
    
    print("Mevcut Video Kaliteleri:")
    for stream in video_streams_data:
        bitrate_str = f"{stream['bitrate_kbps']} kbps" if stream['bitrate_kbps'] else "Bilinmiyor"
        size_str = f"{stream['size_mb']}MB" if stream['size_mb'] else "Bilinmiyor"
        adaptive_str = "Hayır" if stream['is_progressive'] else "Evet"
        print(f"{stream['index']}) Çözünürlük: {stream['resolution']}, FPS: {stream['fps']}fps, Bitrate: {bitrate_str}, Adaptive: {adaptive_str}, Boyut: {size_str}")

    try:
        video_choice_idx = int(input("\nİndirmek istediğiniz video kalitesinin numarasını girin: "))
        if not (1 <= video_choice_idx <= len(video_streams_data)):
            print("Geçersiz seçim.")
            return
    except ValueError:
        print("Lütfen sayısal bir değer girin.")
        return

    is_progressive = video_streams_data[video_choice_idx - 1]['is_progressive']

    if is_progressive:
        print("\nİndirme işlemi başlatılıyor...")
        status, result = download_video(url=video_url, video_index=video_choice_idx)
        if status:
            print(f"\nİndirme başarıyla tamamlandı: {result}")
        else:
            print(f"\nBir hata oluştu: {result}")
    else:
        status, audio_streams_data = get_audio_streams(video_url)
        if not status:
            print(f"Hata: {audio_streams_data}")
            return
        
        print("\nMevcut Ses Kaliteleri:")
        for stream in audio_streams_data:
            size_str = f"{stream['size_mb']}MB" if stream['size_mb'] else "Bilinmiyor"
            print(f"{stream['index']}) Bitrate: {stream['abr']}, Boyut: {size_str}")
        
        try:
            audio_choice_idx = int(input("\nİndirmek istediğiniz ses kalitesinin numarasını girin: "))
            if not (1 <= audio_choice_idx <= len(audio_streams_data)):
                print("Geçersiz seçim.")
                return
        except ValueError:
            print("Lütfen sayısal bir değer girin.")
            return

        print("\nİndirme ve birleştirme işlemi başlatılıyor...")
        status, result = download_video(url=video_url, video_index=video_choice_idx, audio_index=audio_choice_idx)
        if status:
            print(f"\nİndirme başarıyla tamamlandı: {result}")
        else:
            print(f"\nBir hata oluştu: {result}")

if __name__ == "__main__":
    main()
