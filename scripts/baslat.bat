@echo off
title Yerli Dali AI Studio v4.0
color 0E
chcp 65001 >nul

:: ─────────────────────────────────────────────
::  Yerli Dali AI Studio — Başlatıcı
::
::  Token ve ayarlar .env dosyasından okunur.
::  Token burada YOK — .env.example'ı kopyala!
::    cp .env.example .env
::    .env dosyasını düzenle
:: ─────────────────────────────────────────────

:: Python yolu (PyCharm venv'ini referans al)
set "PY_YOLU=C:\Users\ereno\AppData\Local\Programs\Python\Python310\python.exe"

:: Bu bat dosyasının bulunduğu klasör = proje kökü
set "PROJE_DIZINI=%~dp0"

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     Yerli Dali AI Studio — v4.0          ║
echo  ╚══════════════════════════════════════════╝
echo.

:: .env dosyası var mı kontrol et
if not exist "%PROJE_DIZINI%.env" (
    echo [HATA] .env dosyasi bulunamadi!
    echo.
    echo Cozum:
    echo   1. .env.example dosyasini kopyala: copy .env.example .env
    echo   2. .env icindeki TELEGRAM_TOKEN ve ADMIN_ID degerlerini doldur
    echo.
    pause
    exit /b 1
)

:: Proje dizinine gec
cd /d "%PROJE_DIZINI%"

:: Sanal ortam yoksa oluştur
if not exist "venv\Scripts\activate.bat" (
    echo [*] Sanal ortam olusturuluyor...
    "%PY_YOLU%" -m venv venv
    if errorlevel 1 (
        echo [HATA] Sanal ortam olusturulamadi! Python yolunu kontrol et.
        pause
        exit /b 1
    )
)

:: Sanal ortamı aktif et
call venv\Scripts\activate.bat

echo [*] Python surumu:
python --version

echo.
echo [*] Bagimliliklar kontrol ediliyor...

:: PyTorch ayrı kurulumu (CUDA 12.1)
python -m pip show torch >nul 2>&1
if errorlevel 1 (
    echo [*] PyTorch bulunamadi, kuruluyor (CUDA 12.1 -- RTX 4070 icin)...
    pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121
)

:: Ana bağımlılıklar
pip install -r requirements.txt -q

echo [OK] Bagimliliklar hazir.
echo.
echo [*] Studio baslatiliyor...
echo.

:: Uygulamayı çalıştır
python main.py

echo.
echo [!] Studio kapandi.
pause
