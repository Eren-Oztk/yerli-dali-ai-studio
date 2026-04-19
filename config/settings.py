"""
config/settings.py
──────────────────────────────────────────────────────────────────────────────
Tüm ayarlar .env dosyasından okunur ve Pydantic ile doğrulanır.
Hiçbir token, yol veya sayısal değer kaynak kodunda hardcode edilmez.
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram
    TELEGRAM_TOKEN: str
    ADMIN_ID: int

    # ── Klasörler
    BASE_DIR: Path = Path("D:/YerliDali")          # .env'den override edilebilir
    OUT_DIR: Optional[Path] = None
    TEMP_DIR: Optional[Path] = None
    LOG_DIR: Optional[Path] = None

    # ── Motor ve Model yolları
    ESRGAN_EXE_PATH: Optional[Path] = None
    GFPGAN_MODEL_PATH: Optional[Path] = None

    # ── İşlem ayarları
    TILE_SIZE: int = 512
    DEFAULT_SCALE: int = 4
    DEFAULT_GRAIN: float = 0.10
    DEFAULT_GFPGAN: bool = True
    MAX_QUEUE_SIZE: int = 50
    WORKER_TIMEOUT: int = 300         # saniye

    # ── Gradio
    GRADIO_HOST: str = "127.0.0.1"
    GRADIO_PORT: int = 7860

    # ── Güvenlik
    MAX_IMAGE_MB: float = 50.0        # MB cinsinden kabul edilecek max görsel boyutu

    @model_validator(mode="after")
    def _fill_derived_paths(self) -> "Settings":
        base = self.BASE_DIR
        if self.OUT_DIR is None:
            self.OUT_DIR = base / "out"
        if self.TEMP_DIR is None:
            self.TEMP_DIR = base / "temp"
        if self.LOG_DIR is None:
            self.LOG_DIR = base / "logs"
        if self.ESRGAN_EXE_PATH is None:
            self.ESRGAN_EXE_PATH = base / "realesrgan-ncnn-vulkan.exe"
        if self.GFPGAN_MODEL_PATH is None:
            self.GFPGAN_MODEL_PATH = base / "gfpgan" / "weights" / "GFPGANv1.4.pth"
        return self

    @field_validator("TELEGRAM_TOKEN")
    @classmethod
    def _token_not_placeholder(cls, v: str) -> str:
        if v in ("BURAYA_TOKEN_YAZ", "", "YOUR_TOKEN_HERE"):
            raise ValueError(
                "TELEGRAM_TOKEN .env dosyasına yazılmamış!\n"
                ".env.example dosyasını kopyalayıp doldurun: cp .env.example .env"
            )
        return v

    @field_validator("TILE_SIZE")
    @classmethod
    def _tile_power_of_two(cls, v: int) -> int:
        if v not in (128, 256, 512, 1024):
            raise ValueError("TILE_SIZE 128, 256, 512 veya 1024 olmalı.")
        return v

    @field_validator("DEFAULT_GRAIN")
    @classmethod
    def _grain_range(cls, v: float) -> float:
        if not 0.0 <= v <= 0.30:
            raise ValueError("DEFAULT_GRAIN 0.0 ile 0.30 arasında olmalı.")
        return v

    def ensure_dirs(self) -> None:
        """Gerekli klasörleri oluşturur. Başlangıçta bir kez çağrılır."""
        for d in (self.BASE_DIR, self.OUT_DIR, self.TEMP_DIR, self.LOG_DIR):
            d.mkdir(parents=True, exist_ok=True)


# Uygulama genelinde tek instance
settings = Settings()
