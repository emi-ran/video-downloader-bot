import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from youtubeDownloader import get_video_title, get_video_streams, get_audio_streams, download_video
from pytubefix import YouTube # YouTube sınıfı buradan import edilmeli
from instagramDownloader import download_instagram_video
from tiktokDownloader import download_tiktok_video
from database import add_download, init_db

# Logging'i etkinleştir
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Bot Komutları ve İşlevleri ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start komutu için karşılama mesajı gönderir."""
    await update.message.reply_text(
        "Merhaba! YouTube videolarını indirmek için hazırım.\n"
        "Kullanmak için: /youtube <video_linki>"
    )

async def youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/youtube komutunu işler, video bilgilerini ve kalite butonlarını gönderir."""
    try:
        url = context.args[0]
    except (IndexError, ValueError):
        await update.message.reply_text("Lütfen komutla birlikte bir YouTube linki gönderin.\nÖrnek: /youtube <link>")
        return

    status, title = get_video_title(url)
    if not status:
        await update.message.reply_text(f"Hata: {title}")
        return
        
    context.user_data['url'] = url

    status, video_streams = get_video_streams(url)
    if not status:
        await update.message.reply_text(f"Hata: {video_streams}")
        return

    # Stream bilgilerini önbellekte tut
    context.user_data['video_streams'] = video_streams
    context.user_data['video_title'] = title

    # Önce kapak fotoğrafı (varsa) ayrı bir mesaj olarak gönder
    try:
        thumbnail_url = YouTube(url).thumbnail_url
        await update.message.reply_photo(photo=thumbnail_url)
    except Exception:
        pass

    # Ardından başlık ve kalite butonlarını metin mesajı olarak gönder
    keyboard = []
    for stream in video_streams:
        text = f"{stream['resolution']} ({stream['fps']}fps) - {stream['size_mb']}MB"
        callback_data = f"video_{stream['index']}"
        keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
    # En alta iptal butonu ekle
    keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="iptal")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"*{title}*\n\nLütfen indirmek istediğiniz video kalitesini seçin:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Buton tıklamalarını yönetir."""
    query = update.callback_query
    await query.answer()
    
    data = query.data

    # YouTube video kalite seçimi (yt_video_{index})
    if data.startswith("yt_video_"):
        video_index = int(data.split("_")[2])
        url = context.user_data.get('current_url')
        if not url:
            await query.edit_message_text("URL bulunamadı, lütfen tekrar deneyin.")
            return
            
        # Önbellekteki stream bilgilerini kullan
        video_streams = context.user_data.get('video_streams')
        if not video_streams:
            await query.edit_message_text("Stream bilgileri bulunamadı, lütfen tekrar deneyin.")
            return
            
        selected_stream = next((s for s in video_streams if s['index'] == video_index), None)
        if not selected_stream:
            await query.edit_message_text("Seçilen stream bulunamadı.")
            return
            
        if selected_stream['is_progressive']:
            await query.edit_message_text("İndirme işlemi başlatılıyor...")
            await download_and_send_video(update, context, url, video_index)
        else:
            # Ses stream'lerini önbellekte kontrol et
            audio_streams = context.user_data.get('audio_streams')
            if not audio_streams:
                # Ses stream'lerini al ve önbellekte tut
                status, audio_streams = get_audio_streams(url)
                if not status:
                    await query.edit_message_text(f"Hata: {audio_streams}")
                    return
                context.user_data['audio_streams'] = audio_streams
            
            title = context.user_data.get('video_title', 'Video')
            keyboard = []
            for stream in audio_streams:
                text = f"{stream['abr']} - {stream['size_mb']}MB"
                callback_data = f"yt_audio_{stream['index']}_{video_index}"
                keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
            keyboard.append([InlineKeyboardButton("⬅️ Geri", callback_data="yt_geri")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            metin = f"*{title}*\nLütfen ses kalitesini seçin:"
            if query.message.photo:
                await query.message.reply_text(metin, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await query.edit_message_text(metin, reply_markup=reply_markup, parse_mode='Markdown')
        return
        
    # YouTube ses kalite seçimi (yt_audio_{audio_index}_{video_index})
    if data.startswith("yt_audio_"):
        parts = data.split("_")
        audio_index = int(parts[2])
        video_index = int(parts[3])
        url = context.user_data.get('current_url')
        if not url:
            await query.edit_message_text("URL bulunamadı, lütfen tekrar deneyin.")
            return
            
        await query.edit_message_text("İndirme ve birleştirme işlemi başlatılıyor...")
        await download_and_send_video(update, context, url, video_index, audio_index)
        return
        
    # Geri butonu (yt_geri)
    if data == "yt_geri":
        url = context.user_data.get('current_url')
        if not url:
            await query.edit_message_text("URL bulunamadı, lütfen tekrar deneyin.")
            return
            
        # Önbellekteki bilgileri kullan
        title = context.user_data.get('video_title')
        video_streams = context.user_data.get('video_streams')
        if not title or not video_streams:
            await query.edit_message_text("Bilgiler bulunamadı, lütfen tekrar deneyin.")
            return
            
        keyboard = []
        for stream in video_streams:
            text = f"{stream['resolution']} ({stream['fps']}fps) - {stream['size_mb']}MB"
            callback_data = f"yt_video_{stream['index']}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
        keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="iptal")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"*{title}*\n\nLütfen indirmek istediğiniz video kalitesini seçin:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
        
    # İptal butonu
    if data == "iptal":
        await query.edit_message_text("İşlem iptal edildi.")
        return
        
    # Eski sistemle uyumlu kalması için (komutlu kullanımda)
    url = context.user_data.get('url')
    if not url and not data.startswith('iptal'):
        await query.edit_message_text("Bir şeyler ters gitti, lütfen komutu tekrar kullanın.")
        return
    if data.startswith("video_"):
        video_index = int(data.split("_")[1])
        context.user_data['video_index'] = video_index
        
        # Önbellekteki stream bilgilerini kullan
        video_streams = context.user_data.get('video_streams')
        if not video_streams:
            await query.edit_message_text("Stream bilgileri bulunamadı, lütfen tekrar deneyin.")
            return
            
        selected_stream = next((s for s in video_streams if s['index'] == video_index), None)
        if not selected_stream:
            await query.edit_message_text("Seçilen stream bulunamadı.")
            return
            
        if selected_stream['is_progressive']:
            await query.edit_message_text("İndirme işlemi başlatılıyor...")
            await download_and_send_video(update, context, url, video_index)
        else:
            # Ses stream'lerini önbellekte kontrol et
            audio_streams = context.user_data.get('audio_streams')
            if not audio_streams:
                # Ses stream'lerini al ve önbellekte tut
                status, audio_streams = get_audio_streams(url)
                if not status:
                    await query.edit_message_text(f"Hata: {audio_streams}")
                    return
                context.user_data['audio_streams'] = audio_streams
            
            title = context.user_data.get('video_title', 'Video')
            keyboard = []
            for stream in audio_streams:
                text = f"{stream['abr']} - {stream['size_mb']}MB"
                callback_data = f"audio_{stream['index']}"
                keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
            keyboard.append([InlineKeyboardButton("⬅️ Geri", callback_data="geri_video")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            metin = f"*{title}*\nLütfen ses kalitesini seçin:"
            if query.message.photo:
                await query.message.reply_text(metin, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await query.edit_message_text(metin, reply_markup=reply_markup, parse_mode='Markdown')
    elif data.startswith("audio_"):
        audio_index = int(data.split("_")[1])
        video_index = context.user_data.get('video_index')
        await query.edit_message_text("İndirme ve birleştirme işlemi başlatılıyor...")
        await download_and_send_video(update, context, url, video_index, audio_index)
    elif data == "geri_video":
        # Video kalite seçimine geri dön
        url = context.user_data.get('url')
        if not url:
            await query.edit_message_text("URL bulunamadı, lütfen tekrar deneyin.")
            return
            
        title = context.user_data.get('video_title')
        video_streams = context.user_data.get('video_streams')
        if not title or not video_streams:
            await query.edit_message_text("Bilgiler bulunamadı, lütfen tekrar deneyin.")
            return
            
        keyboard = []
        for stream in video_streams:
            text = f"{stream['resolution']} ({stream['fps']}fps) - {stream['size_mb']}MB"
            callback_data = f"video_{stream['index']}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
        keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="iptal")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"*{title}*\n\nLütfen indirmek istediğiniz video kalitesini seçin:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def download_and_send_video(update, context, url, video_index, audio_index=None):
    """Videoyu indirir, gönderir ve temizler."""
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    status, result = download_video(
        url=url, 
        video_index=video_index, 
        audio_index=audio_index,
        progress_callback=None
    )
    # Her durumda kaydet
    add_download(user_id, username, "YouTube", url, "success" if status else "fail")
    if not status:
        # Callback query için mesaj referansını kontrol et
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(f"Hata oluştu: {result}")
        else:
            await update.effective_message.reply_text(f"Hata oluştu: {result}")
        return

    final_video_path = result
    
    # Callback query için mesaj referansını kontrol et
    if hasattr(update, 'callback_query') and update.callback_query:
        sending_msg = await update.callback_query.edit_message_text("Video gönderiliyor, bu işlem biraz zaman alabilir...")
        chat = update.effective_chat
    else:
        sending_msg = await update.effective_message.reply_text("Video gönderiliyor, bu işlem biraz zaman alabilir...")
        chat = update.effective_chat
        
    try:
        with open(final_video_path, 'rb') as video_file:
            await chat.send_video(video=video_file, supports_streaming=True)
        # Mesajı silmeye çalış, ama hata olursa görmezden gel
        try:
            await sending_msg.delete()
        except:
            pass
    except Exception as e:
        if 'timed out' not in str(e).lower():
            try:
                await sending_msg.edit_text(f"Video gönderilemedi: {e}")
            except:
                await chat.send_text(f"Video gönderilemedi: {e}")
    finally:
        if os.path.exists(final_video_path):
            os.remove(final_video_path)


async def instagram_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/instagram komutu ile Instagram videosu indirir ve gönderir."""
    try:
        url = context.args[0]
    except (IndexError, ValueError):
        await update.message.reply_text("Lütfen komutla birlikte bir Instagram video linki gönderin.\nÖrnek: /instagram <link>")
        return
    msg = await update.message.reply_text("Instagram videosu indiriliyor, lütfen bekleyin...")
    status, result = download_instagram_video(url)
    if not status:
        await msg.edit_text(f"Hata: {result}")
        return
    try:
        with open(result, 'rb') as video_file:
            await update.effective_chat.send_video(video=video_file, supports_streaming=True)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"Video gönderilemedi: {e}")
    finally:
        if os.path.exists(result):
            os.remove(result)


async def tiktok_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/tiktok komutu ile TikTok videosu indirir ve gönderir."""
    try:
        url = context.args[0]
    except (IndexError, ValueError):
        await update.message.reply_text("Lütfen komutla birlikte bir TikTok video linki gönderin.\nÖrnek: /tiktok <link>")
        return
    msg = await update.message.reply_text("TikTok videosu indiriliyor, lütfen bekleyin...")
    status, result = download_tiktok_video(url)
    if not status:
        await msg.edit_text(f"Hata: {result}")
        return
    try:
        with open(result, 'rb') as video_file:
            await update.effective_chat.send_video(video=video_file, supports_streaming=True)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"Video gönderilemedi: {e}")
    finally:
        if os.path.exists(result):
            os.remove(result)

YOUTUBE_DOMAINS = ["youtube.com", "youtu.be"]
INSTAGRAM_DOMAINS = ["instagram.com", "instagr.am"]
TIKTOK_DOMAINS = ["tiktok.com", "vm.tiktok.com"]

async def universal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Herhangi bir metin mesajında linki algılayıp uygun downloader'ı çağırır."""
    text = update.message.text.strip()
    url = None
    # YouTube
    if any(domain in text for domain in YOUTUBE_DOMAINS):
        url = next((word for word in text.split() if any(domain in word for domain in YOUTUBE_DOMAINS)), None)
        if url:
            # URL'yi context'te sakla
            context.user_data['current_url'] = url
            
            # Kalite seçeneklerini butonlarla gönder
            status, title = get_video_title(url)
            if not status:
                await update.message.reply_text(f"Hata: {title}")
                return
                
            status, video_streams = get_video_streams(url)
            if not status or not video_streams:
                await update.message.reply_text(f"Hata: {video_streams}")
                return
                
            # Stream bilgilerini önbellekte tut
            context.user_data['video_streams'] = video_streams
            context.user_data['video_title'] = title
            
            keyboard = []
            for stream in video_streams:
                text_btn = f"{stream['resolution']} ({stream['fps']}fps) - {stream['size_mb']}MB"
                callback_data = f"yt_video_{stream['index']}"
                keyboard.append([InlineKeyboardButton(text_btn, callback_data=callback_data)])
            keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="iptal")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"*{title}*\n\nLütfen indirmek istediğiniz video kalitesini seçin:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
    # Instagram
    if any(domain in text for domain in INSTAGRAM_DOMAINS) and ("/reel/" in text or "/reels/" in text or "/p/" in text or "/tv/" in text or "/stories/" in text):
        url = next((word for word in text.split() if any(domain in word for domain in INSTAGRAM_DOMAINS)), None)
        if url:
            await update.message.reply_text("Instagram videosu indiriliyor, lütfen bekleyin...")
            await instagram_universal(update, context, url)
            return
    # TikTok
    if any(domain in text for domain in TIKTOK_DOMAINS):
        url = next((word for word in text.split() if any(domain in word for domain in TIKTOK_DOMAINS)), None)
        if url:
            await update.message.reply_text("TikTok videosu indiriliyor, lütfen bekleyin...")
            await tiktok_universal(update, context, url)
            return
    await update.message.reply_text("Geçerli bir YouTube, Instagram veya TikTok video linki göndermelisiniz.")

async def youtube_universal(update, context, url):
    status, title = get_video_title(url)
    if not status:
        await update.message.reply_text(f"Hata: {title}")
        return
    status, video_streams = get_video_streams(url)
    if not status or not video_streams:
        await update.message.reply_text(f"Hata: {video_streams}")
        return
    # En yüksek kaliteyi seç (ilk stream)
    selected_video = video_streams[0]
    if selected_video['is_progressive']:
        status, result = download_video(url=url, video_index=selected_video['index'])
    else:
        # Adaptive ise en yüksek ses stream'ini de seç
        status, audio_streams = get_audio_streams(url)
        if not status or not audio_streams:
            await update.message.reply_text(f"Hata: {audio_streams}")
            return
        selected_audio = audio_streams[0]
        status, result = download_video(url=url, video_index=selected_video['index'], audio_index=selected_audio['index'])
    if not status:
        await update.message.reply_text(f"Hata: {result}")
        return
    try:
        with open(result, 'rb') as video_file:
            await update.effective_chat.send_video(video=video_file, supports_streaming=True)
    except Exception as e:
        await update.message.reply_text(f"Video gönderilemedi: {e}")
    finally:
        if os.path.exists(result):
            os.remove(result)

async def instagram_universal(update, context, url):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    status, result = download_instagram_video(url)
    add_download(user_id, username, "Instagram", url, "success" if status else "fail")
    if not status:
        await update.message.reply_text(f"Hata: {result}")
        return
    try:
        with open(result, 'rb') as video_file:
            await update.effective_chat.send_video(video=video_file, supports_streaming=True)
    except Exception as e:
        await update.message.reply_text(f"Video gönderilemedi: {e}")
    finally:
        if os.path.exists(result):
            os.remove(result)

async def tiktok_universal(update, context, url):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    status, result = download_tiktok_video(url)
    add_download(user_id, username, "TikTok", url, "success" if status else "fail")
    if not status:
        await update.message.reply_text(f"Hata: {result}")
        return
    try:
        with open(result, 'rb') as video_file:
            await update.effective_chat.send_video(video=video_file, supports_streaming=True)
    except Exception as e:
        await update.message.reply_text(f"Video gönderilemedi: {e}")
    finally:
        if os.path.exists(result):
            os.remove(result)

def main() -> None:
    """Botu başlatır."""
    token = "7788044450:AAE08m5aDTc7nhuiG9PAqoB0pXGWLTic_0c"
    if not token:
        print("Hata: TELEGRAM_BOT_TOKEN ortam değişkeni bulunamadı.")
        return
    init_db()
    application = Application.builder().token(token).read_timeout(300).write_timeout(300).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, universal_handler))

    application.run_polling()

if __name__ == "__main__":
    main() 