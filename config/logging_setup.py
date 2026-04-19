"""
config/logging_setup.py
──────────────────────────────────────────────────────────────────────────────
Loguru ile merkezi logging kurulumu.
• Console: renkli, kısa format
• Dosya: günlük rotasyon, 7 gün saklama
──────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    logger.remove()  # Default handler'ı kaldır

    # Console — sadece önemli bilgiler
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <7}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    # Dosya — tam detay, günlük rotasyon
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "studio_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",       # Gece yarısı yeni dosya
        retention="7 days",     # 7 günden eski logları sil
        compression="zip",      # Eski logları sıkıştır
        encoding="utf-8",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <7} | "
            "{name}:{line} | "
            "{message}"
        ),
    )

    logger.info("Logging sistemi başlatıldı.")
