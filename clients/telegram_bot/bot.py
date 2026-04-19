"""
clients/telegram_bot/bot.py
──────────────────────────────────────────────────────────────────────────────
Telegram bot istemcisi.
• GPU işi yapmaz — worker kuyruğunu kullanır
• Görsel sıkışmasını önlemek için "dosya olarak gönder" uyarısı
• Thread-safe mesaj gönderimi
• Kuyruktaki sırasını kullanıcıya bildirir
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import io
import queue as queue_mod
import threading
from pathlib import Path

import telebot
from loguru import logger
from PIL import Image

from api.worker import worker
from config.settings import settings
from config import users
from core.engine import upscale, MODELS, MODEL_DISPLAY, GFPGAN_AVAILABLE


# ─────────────────────────────────────────────
#  Bot ve kullanıcı başına model tercihi
# ─────────────────────────────────────────────
bot = telebot.TeleBot(
    settings.TELEGRAM_TOKEN,
    threaded=False,   # Worker kuyruğunu kendimiz yönetiyoruz
)

# Kullanıcı başına seçilen model key ("photo" / "anime" / "general")
_user_models: dict[int, str] = {}
_models_lock = threading.Lock()


def _get_model(uid: int) -> str:
    with _models_lock:
        return _user_models.get(uid, "photo")


def _set_model(uid: int, key: str) -> None:
    with _models_lock:
        _user_models[uid] = key


# ─────────────────────────────────────────────
#  Yardımcı: izin kontrolü
# ─────────────────────────────────────────────
def _guard(msg) -> bool:
    if not users.is_allowed(msg.from_user.id):
        logger.warning(f"İzinsiz erişim denemesi: {msg.from_user.id}")
        return False
    return True


# ─────────────────────────────────────────────
#  Komutlar
# ─────────────────────────────────────────────
@bot.message_handler(commands=["start", "help"])
def cmd_start(msg):
    if not _guard(msg):
        return
    model_satir = "\n".join(
        f"/{key} — {label}" for key, label in MODEL_DISPLAY.items()
    )
    bot.reply_to(
        msg,
        "🎨 *Yerli Dali AI Studio*\n\n"
        "Görselini *dosya/belge olarak* gönder.\n"
        "_(Photo olarak gönderince Telegram sıkıştırır, kalite düşer!)_\n\n"
        f"*Modeller:*\n{model_satir}\n\n"
        "/model — Aktif modeli göster\n"
        "/queue — Kuyruktaki iş sayısı",
        parse_mode="Markdown",
    )


@bot.message_handler(commands=list(MODELS.keys()))   # /photo, /anime, /general
def cmd_set_model(msg):
    if not _guard(msg):
        return
    key = msg.text.lstrip("/").strip().split()[0]
    if key not in MODELS:
        bot.reply_to(msg, "❌ Geçersiz model.")
        return
    _set_model(msg.from_user.id, key)
    bot.reply_to(
        msg,
        f"{MODEL_DISPLAY[key]} modu aktif.",
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["model"])
def cmd_model(msg):
    if not _guard(msg):
        return
    key = _get_model(msg.from_user.id)
    bot.reply_to(msg, f"🤖 Aktif model: `{MODEL_DISPLAY[key]}`", parse_mode="Markdown")


@bot.message_handler(commands=["queue"])
def cmd_queue(msg):
    if not _guard(msg):
        return
    n = worker.queue_length()
    bot.reply_to(msg, f"⏳ Kuyrukta {n} iş var.")


# Admin komutları
@bot.message_handler(commands=["adduser"])
def cmd_adduser(msg):
    if msg.from_user.id != settings.ADMIN_ID:
        return
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(msg, "Kullanım: /adduser <telegram_id>")
        return
    result = users.add_user(int(parts[1]))
    bot.reply_to(msg, result)


@bot.message_handler(commands=["removeuser"])
def cmd_removeuser(msg):
    if msg.from_user.id != settings.ADMIN_ID:
        return
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(msg, "Kullanım: /removeuser <telegram_id>")
        return
    result = users.remove_user(int(parts[1]))
    bot.reply_to(msg, result)


@bot.message_handler(commands=["listusers"])
def cmd_listusers(msg):
    if msg.from_user.id != settings.ADMIN_ID:
        return
    lst = users.list_users()
    lines = [
        f"{'👑' if u == settings.ADMIN_ID else '•'} {u}"
        for u in lst
    ]
    bot.reply_to(msg, "İzinli kullanıcılar:\n" + "\n".join(lines))


# ─────────────────────────────────────────────
#  Fotoğraf mesajı — uyarı ver
# ─────────────────────────────────────────────
@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    if not _guard(msg):
        return
    bot.reply_to(
        msg,
        "⚠️ Görselini *dosya/belge olarak* gönder.\n"
        "📎 Paperclip → Dosya Seç → görseli seç.\n"
        "_(Photo olarak gönderilince Telegram max ~1280px'e sıkıştırır!)_",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
#  Belge (dosya) mesajı — ana işlem
# ─────────────────────────────────────────────
@bot.message_handler(content_types=["document"])
def handle_document(msg):
    if not _guard(msg):
        return

    mime = msg.document.mime_type or ""
    if not mime.startswith("image/"):
        bot.reply_to(msg, "❌ Sadece görsel dosyaları desteklenir (JPG, PNG, WEBP…)")
        return

    # Dosya boyutu kontrolü
    max_bytes = int(settings.MAX_IMAGE_MB * 1024 * 1024)
    if msg.document.file_size and msg.document.file_size > max_bytes:
        bot.reply_to(
            msg,
            f"❌ Dosya çok büyük! Maksimum {settings.MAX_IMAGE_MB:.0f} MB.",
        )
        return

    # Kuyruktaki iş sayısını önceden bildir
    n = worker.queue_length()
    tahmini = n * 30  # kabaca saniye
    bekleme_txt = (
        f" Tahmini bekleme: ~{tahmini}s." if n > 0 else ""
    )

    status_msg = bot.reply_to(
        msg,
        f"⏳ Alındı, kuyruğa eklendi (sıra: {n + 1}).{bekleme_txt}",
    )

    # Dosyayı indir
    try:
        fi = bot.get_file(msg.document.file_id)
        file_bytes = bot.download_file(fi.file_path)
    except Exception as e:
        logger.error(f"Telegram dosya indirme hatası: {e}")
        bot.edit_message_text(f"❌ Dosya indirilemedi: {e}", msg.chat.id, status_msg.message_id)
        return

    model_key = _get_model(msg.from_user.id)

    # Worker kuyruğuna gönder — ayrı thread'de bekle
    try:
        job = worker.submit(
            upscale,
            image_bytes=file_bytes,
            model_key=model_key,
            grain=settings.DEFAULT_GRAIN,
            use_gfpgan=settings.DEFAULT_GFPGAN and GFPGAN_AVAILABLE,
        )
    except queue_mod.Full as e:
        bot.edit_message_text(str(e), msg.chat.id, status_msg.message_id)
        return

    # Sonucu beklemek için ayrı thread — bot polling'i bloklama
    threading.Thread(
        target=_wait_and_send,
        args=(msg, status_msg, job, file_bytes, model_key),
        daemon=True,
    ).start()


def _wait_and_send(msg, status_msg, job, original_bytes: bytes, model_key: str):
    """Worker sonucunu bekler ve kullanıcıya gönderir."""
    timed_out = not job.result_event.wait(timeout=settings.WORKER_TIMEOUT + 30)

    try:
        if timed_out:
            bot.edit_message_text(
                "❌ İşlem zaman aşımına uğradı. Lütfen tekrar dene.",
                msg.chat.id,
                status_msg.message_id,
            )
            return

        if job.error:
            logger.error(f"Worker job hatası: {job.error}")
            bot.edit_message_text(
                f"❌ İşlem başarısız: {job.error}",
                msg.chat.id,
                status_msg.message_id,
            )
            return

        result_bytes: bytes = job.result

        # Boyut bilgisi
        orig_img = Image.open(io.BytesIO(original_bytes))
        out_img = Image.open(io.BytesIO(result_bytes))
        ow, oh = orig_img.size
        nw, nh = out_img.size

        caption = (
            f"✅ Hazır!\n"
            f"📐 {ow}×{oh} → {nw}×{nh}\n"
            f"🤖 {MODEL_DISPLAY.get(model_key, model_key)}\n"
            f"✨ GFPGAN: {'Aktif' if settings.DEFAULT_GFPGAN and GFPGAN_AVAILABLE else 'Kapalı'}\n"
            f"🎞 Grain: {settings.DEFAULT_GRAIN:.2f}"
        )

        # send_document: Telegram sıkıştırmaz, tam kalite!
        bot.send_document(
            msg.chat.id,
            io.BytesIO(result_bytes),
            caption=caption,
            parse_mode="Markdown",
            visible_file_name="YerliDali_upscaled.jpg",
        )

        # "İşleniyor" mesajını sil
        bot.delete_message(msg.chat.id, status_msg.message_id)

    except Exception as e:
        logger.error(f"Telegram gönderim hatası: {e}")
        try:
            bot.send_message(msg.chat.id, f"❌ Gönderim hatası: {e}")
        except Exception:
            pass


# ─────────────────────────────────────────────
#  Bot başlatma
# ─────────────────────────────────────────────
def start_polling():
    """Telegram polling'i başlatır. Daemon thread olarak çalıştır."""
    logger.info("Telegram bot polling başlatılıyor…")
    bot.infinity_polling(
        timeout=20,
        long_polling_timeout=20,
        none_stop=True,     # Network hatasında durmaz, devam eder
        restart_on_change=False,
        logger_level=None,  # Loguru kullanıyoruz
    )
