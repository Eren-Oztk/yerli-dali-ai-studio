"""
config/users.py
──────────────────────────────────────────────────────────────────────────────
İzinli kullanıcıları yönetir.
• JSON'dan yüklenir, memory'de cache tutulur.
• Her mesajda disk okuma yok — sadece ekle/çıkar işlemlerinde yazılır.
• Thread-safe.
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from loguru import logger

from config.settings import settings

_USERS_FILE: Path = settings.BASE_DIR / "izinli_kullanicilar.json"
_cache: set[int] = set()
_lock = threading.RLock()
_loaded = False


def _load_once() -> None:
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        if _USERS_FILE.exists():
            try:
                data = json.loads(_USERS_FILE.read_text(encoding="utf-8"))
                _cache.update(int(uid) for uid in data)
                logger.debug(f"Kullanıcı listesi yüklendi: {len(_cache)} kullanıcı.")
            except Exception as e:
                logger.error(f"Kullanıcı dosyası okunamadı: {e}")
                _cache.add(settings.ADMIN_ID)
        else:
            _cache.add(settings.ADMIN_ID)
            _flush()
        _loaded = True


def _flush() -> None:
    """Cache'i diske yazar."""
    try:
        _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _USERS_FILE.write_text(
            json.dumps(sorted(_cache), indent=2), encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"Kullanıcı dosyası yazılamadı: {e}")


def is_allowed(uid: int) -> bool:
    _load_once()
    with _lock:
        return uid in _cache


def add_user(uid: int) -> str:
    _load_once()
    with _lock:
        if uid in _cache:
            return f"⚠️ {uid} zaten listede."
        _cache.add(uid)
        _flush()
        logger.info(f"Kullanıcı eklendi: {uid}")
        return f"✅ {uid} eklendi."


def remove_user(uid: int) -> str:
    _load_once()
    with _lock:
        if uid == settings.ADMIN_ID:
            return "❌ Admin çıkarılamaz!"
        if uid not in _cache:
            return f"⚠️ {uid} bulunamadı."
        _cache.discard(uid)
        _flush()
        logger.info(f"Kullanıcı çıkarıldı: {uid}")
        return f"✅ {uid} çıkarıldı."


def list_users() -> list[int]:
    _load_once()
    with _lock:
        return sorted(_cache)
