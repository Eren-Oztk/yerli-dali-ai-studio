"""
main.py
──────────────────────────────────────────────────────────────────────────────
Yerli Dali AI Studio — ana başlatma noktası.

Sıra:
  1. Logging sistemi kur
  2. Ayarları yükle & klasörleri oluştur
  3. Temp klasörünü temizle (crash kalıntısı)
  4. Telegram bot'u daemon thread olarak başlat
  5. Gradio GUI'yi ana thread'de başlat
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import threading

from loguru import logger

from config.settings import settings
from config.logging_setup import setup_logging


def _clean_temp() -> None:
    """Önceki çalışmadan kalan temp dosyalarını siler."""
    temp = settings.TEMP_DIR
    if not temp.exists():
        return
    removed = 0
    for f in temp.iterdir():
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    if removed:
        logger.info(f"Temp klasörü temizlendi: {removed} dosya silindi.")


def _validate_motor() -> None:
    """Real-ESRGAN exe varlığını kontrol eder."""
    exe = settings.ESRGAN_EXE_PATH
    if not exe.exists():
        logger.critical(
            f"Real-ESRGAN motoru bulunamadı: {exe}\n"
            "İndir: https://github.com/xinntao/Real-ESRGAN/releases\n"
            "Ardından .env içinde BASE_DIR'i güncelle."
        )
        sys.exit(1)


def main() -> None:
    # ── 1. Logging
    setup_logging(settings.LOG_DIR)

    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║     Yerli Dali AI Studio — v4.0          ║")
    logger.info("╚══════════════════════════════════════════╝")

    # ── 2. Klasörler & doğrulama
    settings.ensure_dirs()
    logger.info(f"BASE_DIR: {settings.BASE_DIR}")

    _validate_motor()
    _clean_temp()

    # ── 3. Telegram bot (daemon thread)
    from clients.telegram_bot.bot import start_polling
    bot_thread = threading.Thread(target=start_polling, name="telegram-bot", daemon=True)
    bot_thread.start()
    logger.info("Telegram bot thread başlatıldı.")

    # ── 4. Gradio GUI (ana thread — bloklar)
    logger.info(f"Gradio arayüzü açılıyor → http://{settings.GRADIO_HOST}:{settings.GRADIO_PORT}")
    from clients.web_ui.gradio_app import launch
    launch()


if __name__ == "__main__":
    main()
