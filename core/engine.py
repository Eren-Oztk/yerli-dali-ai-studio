"""
core/engine.py
──────────────────────────────────────────────────────────────────────────────
Upscale motoru — Real-ESRGAN + GFPGAN + Grain
Hiçbir UI / Telegram / API bağımlılığı yoktur.
Giriş: bytes  →  Çıkış: bytes
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image
from loguru import logger

from config.settings import settings

# ─────────────────────────────────────────────
#  GFPGAN — opsiyonel bağımlılık
# ─────────────────────────────────────────────
try:
    import cv2
    from gfpgan import GFPGANer
    GFPGAN_AVAILABLE = True
    logger.info("GFPGAN modülü aktif.")
except ImportError:
    GFPGAN_AVAILABLE = False
    logger.warning("GFPGAN bulunamadı. Yüz onarımı devre dışı.")

# ─────────────────────────────────────────────
#  Model tanımları
# ─────────────────────────────────────────────
MODELS: dict[str, str] = {
    "photo":   "realesrgan-x4plus",
    "anime":   "realesrgan-x4plus-anime",
    "general": "realesr-animevideov3",
}

MODEL_DISPLAY: dict[str, str] = {
    "photo":   "📸 Gerçek Fotoğraf (x4)",
    "anime":   "🎨 Karakalem / Anime (x4)",
    "general": "🎬 Video Frame / Genel (x4)",
}

# Model başına uygun ölçek değerleri
# realesrgan-x4plus ve anime: sadece 4
# animevideov3: 2, 3 veya 4
MODEL_SCALES: dict[str, list[int]] = {
    "photo":   [4],
    "anime":   [4],
    "general": [2, 3, 4],
}

# ─────────────────────────────────────────────
#  GFPGAN singleton
# ─────────────────────────────────────────────
_gfpgan_restorer: "GFPGANer | None" = None
_gfpgan_lock = threading.Lock()


def _get_gfpgan() -> "GFPGANer | None":
    """Thread-safe singleton: modeli sadece bir kez yükler."""
    global _gfpgan_restorer
    if not GFPGAN_AVAILABLE:
        return None
    with _gfpgan_lock:
        if _gfpgan_restorer is None:
            logger.info("GFPGAN modeli yükleniyor…")
            _gfpgan_restorer = GFPGANer(
                model_path=str(settings.GFPGAN_MODEL_PATH),
                upscale=1,
                arch="clean",
                channel_multiplier=2,
                bg_upsampler=None,
            )
            logger.info("GFPGAN hazır.")
    return _gfpgan_restorer


# ─────────────────────────────────────────────
#  Grain — gerçek Gaussian film gürültüsü
# ─────────────────────────────────────────────
def _apply_grain(img: Image.Image, strength: float) -> Image.Image:
    """
    strength: 0.0 → kapalı | 0.10 → hafif | 0.30 → belirgin
    std = strength * 10  →  0.10 → std=1.0, 0.30 → std=3.0
    Bu aralık gerçek film grain'ine karşılık gelir.
    """
    if strength <= 0.0:
        return img
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(loc=0.0, scale=strength * 10.0, size=arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


# ─────────────────────────────────────────────
#  Ana upscale fonksiyonu
# ─────────────────────────────────────────────
def upscale(
    image_bytes: bytes,
    model_key: str = "photo",
    scale: int = 4,
    tile: int = 512,
    grain: float = 0.10,
    use_gfpgan: bool = False,
) -> bytes:
    """
    Görsel byte'larını alır, upscale edilmiş JPEG byte'larını döndürür.

    Raises:
        ValueError: Geçersiz model_key veya scale değeri.
        RuntimeError: Real-ESRGAN motoru çöktüğünde.
    """
    if model_key not in MODELS:
        raise ValueError(f"Geçersiz model: {model_key!r}. Geçerliler: {list(MODELS)}")

    allowed_scales = MODEL_SCALES[model_key]
    if scale not in allowed_scales:
        logger.warning(
            f"Model '{model_key}' için scale={scale} desteklenmiyor. "
            f"Otomatik {allowed_scales[-1]}'e ayarlandı."
        )
        scale = allowed_scales[-1]

    model_name = MODELS[model_key]
    motor_path = str(settings.ESRGAN_EXE_PATH)

    # ── Temp dosyaları (aynı klasörde olmak zorunda değil)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_in:
        in_path = f_in.name
        f_in.write(image_bytes)

    out_path = in_path.replace(".png", "_out.png")

    try:
        # 1. Real-ESRGAN
        cmd = [
            motor_path,
            "-i", in_path,
            "-o", out_path,
            "-n", model_name,
            "-s", str(scale),
            "-t", str(tile),
            "-f", "png",        # Ara işlemde kayıpsız PNG
        ]
        logger.debug(f"Komut: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,        # 5 dakika hard-limit
        )

        if not Path(out_path).exists():
            raise RuntimeError(
                f"Real-ESRGAN çıktı oluşturmadı.\nSTDERR: {result.stderr}"
            )

        # 2. GFPGAN — Yüz onarımı
        if use_gfpgan:
            restorer = _get_gfpgan()
            if restorer is not None:
                logger.info("GFPGAN yüz onarımı başlatıldı…")
                img_cv = cv2.imread(out_path)
                if img_cv is not None:
                    _, _, restored = restorer.enhance(
                        img_cv,
                        has_aligned=False,
                        only_center_face=False,
                        paste_back=True,
                        weight=0.5,
                    )
                    if restored is not None:
                        cv2.imwrite(out_path, restored)
                        logger.info("GFPGAN onarımı tamamlandı.")
                    else:
                        logger.info("Görüntüde yüz bulunamadı, GFPGAN atlandı.")

        # 3. Grain
        img_out = Image.open(out_path).convert("RGB")
        img_out = _apply_grain(img_out, grain)

        # 4. JPEG final çıktı (kalite 95, chroma subsampling kapalı)
        buf = io.BytesIO()
        img_out.save(buf, format="JPEG", quality=95, subsampling=0)
        result_bytes = buf.getvalue()

        # 5. out/ klasörüne de kaydet
        from datetime import datetime
        out_dir = settings.OUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
        tip = {"photo": "gercek", "anime": "cizim", "general": "genel"}.get(model_key, "out")
        out_file = out_dir / f"YerliDali_{tip}_{zaman}.jpg"
        out_file.write_bytes(result_bytes)
        logger.info(f"Diske kaydedildi: {out_file}")

        return result_bytes

    except subprocess.TimeoutExpired:
        raise RuntimeError("Real-ESRGAN zaman aşımına uğradı (300s).")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Real-ESRGAN motoru çöktü:\n{e.stderr}")
    finally:
        # Temp dosyaları temizle — her koşulda
        _safe_remove(in_path)
        _safe_remove(out_path)
        # VRAM temizliği
        _clear_vram()


def _safe_remove(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError as e:
        logger.warning(f"Temp dosya silinemedi: {path} — {e}")


def _clear_vram() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("VRAM temizlendi.")
    except ImportError:
        pass