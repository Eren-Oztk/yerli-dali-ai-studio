# 🎨 Yerli Dali AI Studio

[![Live Demo](https://img.shields.io/badge/🌐_Canlı_Demo-GitHub_Pages-1f6feb?style=for-the-badge)](https://eren-oztk.github.io/yerli-dali-ai-studio/)

**Real-ESRGAN + GFPGAN tabanlı, Telegram bot + Gradio GUI destekli görsel upscale sistemi.**

Düşük çözünürlüklü görselleri yapay zeka ile 4x büyütür; opsiyonel GFPGAN yüz onarımı ve film grain efekti ekler.

---

## ✨ Özellikler

| Özellik | Detay |
|---------|-------|
| 🚀 **Real-ESRGAN** | NCNN-Vulkan tabanlı, GPU hızlandırmalı 4x upscale |
| ✨ **GFPGAN** | Bulanık yüzleri stüdyo kalitesinde onarır |
| 🎞 **Film Grain** | Gerçek Gaussian gürültüsü — yapay görünümü azaltır |
| 🤖 **Telegram Bot** | Dosya olarak gönder, upscale'li halini al |
| 🖥 **Gradio GUI** | Önce/sonra karşılaştırmalı web arayüzü |
| ⚙️ **GPU Kuyruğu** | Aynı anda sadece 1 işlem — VRAM güvenli |
| 🔒 **İzin Sistemi** | Sadece yetkili Telegram kullanıcıları erişebilir |

---

## 📦 Gereksinimler

- Windows 10/11 (64-bit)
- Python 3.10
- NVIDIA GPU (CUDA 12.1 önerilir — RTX serisinde test edildi)
- [Real-ESRGAN NCNN-Vulkan](https://github.com/xinntao/Real-ESRGAN/releases) executable
- _(Opsiyonel)_ [GFPGANv1.4.pth](https://github.com/TencentARC/GFPGAN/releases) model dosyası

---

## 🚀 Kurulum

### 1. Repoyu klonla

```bash
git clone https://github.com/KULLANICI_ADIN/yerli-dali-ai-studio.git
cd yerli-dali-ai-studio
```

### 2. Real-ESRGAN motorunu indir

[Releases sayfasından](https://github.com/xinntao/Real-ESRGAN/releases) `realesrgan-ncnn-vulkan-*-windows.zip` dosyasını indir.

İçindeki `realesrgan-ncnn-vulkan.exe` ve `models/` klasörünü `BASE_DIR` olarak belirleyeceğin klasöre koy (varsayılan: `D:\YerliDali\`).

```
D:\YerliDali\
├── realesrgan-ncnn-vulkan.exe
├── models\
│   ├── realesrgan-x4plus.param
│   ├── realesrgan-x4plus-anime.param
│   └── realesr-animevideov3.param
└── gfpgan\
    └── weights\
        └── GFPGANv1.4.pth          ← opsiyonel
```

### 3. Konfigürasyonu ayarla

```bash
copy .env.example .env
```

`.env` dosyasını bir metin editörüyle aç ve düzenle:

```dotenv
TELEGRAM_TOKEN=1234567890:AAH...     # BotFather'dan al
ADMIN_ID=987654321                   # userinfobot'tan al
BASE_DIR=D:/YerliDali                # motorun bulunduğu klasör
```

> ⚠️ **`.env` dosyasını asla GitHub'a push'lama!** `.gitignore`'da zaten var.

### 4. Başlat

```bash
scripts\baslat.bat
```

İlk çalıştırmada bağımlılıkları otomatik kurar. Sonraki açılışlar hızlıdır.

---

## 🏗 Proje Yapısı

```
yerli-dali-ai-studio/
├── main.py                        # Ana başlatma noktası
├── requirements.txt
├── .env.example                   # Konfigürasyon şablonu
├── .gitignore
│
├── config/
│   ├── settings.py                # Pydantic ile doğrulanmış tüm ayarlar
│   ├── users.py                   # Kullanıcı yönetimi (cache'li, thread-safe)
│   └── logging_setup.py           # Loguru merkezi logging
│
├── core/
│   └── engine.py                  # Saf upscale motoru (UI bağımlılığı yok)
│                                  # bytes → upscale → bytes
│
├── api/
│   └── worker.py                  # GPU kuyruğu (1 işlem, VRAM güvenli)
│
├── clients/
│   ├── telegram_bot/
│   │   └── bot.py                 # Telegram istemcisi
│   └── web_ui/
│       └── gradio_app.py          # Gradio GUI
│
├── scripts/
│   └── baslat.bat                 # Windows başlatıcı
│
└── logs/                          # Otomatik oluşturulur
```

---

## ⚙️ Konfigürasyon Referansı

`.env` dosyasında ayarlanabilecek tüm değerler:

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `TELEGRAM_TOKEN` | — | **Zorunlu.** BotFather token |
| `ADMIN_ID` | — | **Zorunlu.** Admin Telegram ID |
| `BASE_DIR` | `D:/YerliDali` | Motor ve model klasörü |
| `TILE_SIZE` | `512` | ESRGAN tile boyutu (128/256/512/1024) |
| `DEFAULT_SCALE` | `4` | Büyütme çarpanı |
| `DEFAULT_GRAIN` | `0.10` | Film grain yoğunluğu (0.0–0.30) |
| `DEFAULT_GFPGAN` | `true` | Yüz onarımı varsayılan açık mı |
| `MAX_QUEUE_SIZE` | `50` | Maksimum kuyruk uzunluğu |
| `WORKER_TIMEOUT` | `300` | Saniye cinsinden işlem zaman aşımı |
| `GRADIO_HOST` | `127.0.0.1` | Gradio bind adresi |
| `GRADIO_PORT` | `7860` | Gradio port |
| `MAX_IMAGE_MB` | `50.0` | Maksimum görsel boyutu (MB) |

---

## 🤖 Telegram Bot Komutları

| Komut | Açıklama |
|-------|----------|
| `/start` veya `/help` | Kullanım kılavuzu |
| `/photo` | 📸 Gerçek fotoğraf moduna geç |
| `/anime` | 🎨 Karakalem/Anime moduna geç |
| `/general` | 🎬 Genel/Video moduna geç |
| `/model` | Aktif modeli göster |
| `/queue` | Kuyruktaki iş sayısı |
| `/adduser <id>` | _(Admin)_ Kullanıcı ekle |
| `/removeuser <id>` | _(Admin)_ Kullanıcı çıkar |
| `/listusers` | _(Admin)_ Kullanıcı listesi |

> 💡 Görseli **dosya/belge olarak** gönder (photo olarak değil).  
> Paperclip → Dosya Seç → görselini seç.  
> Photo olarak gönderince Telegram ~1280px'e sıkıştırır!

---

## 🧠 Mimari

```
┌─────────────────────────────────────────────────────┐
│                      main.py                        │
│   (Logging + Settings + Temp Clean + Boot)          │
└───────────────┬─────────────────────┬───────────────┘
                │                     │
     daemon thread              ana thread
                │                     │
    ┌───────────▼──────┐   ┌──────────▼──────────┐
    │  Telegram Bot     │   │    Gradio GUI        │
    │  (bot.py)         │   │    (gradio_app.py)   │
    └───────────┬───────┘   └──────────┬───────────┘
                │                      │
                └──────────┬───────────┘
                           │  worker.submit()
                ┌──────────▼───────────┐
                │   GPU Worker Queue   │
                │   (worker.py)        │
                │   queue.Queue        │
                │   tek thread         │
                └──────────┬───────────┘
                           │  core.engine.upscale()
                ┌──────────▼───────────┐
                │   Upscale Engine     │
                │   (engine.py)        │
                │                      │
                │  Real-ESRGAN EXE     │
                │    + GFPGAN          │
                │    + Grain           │
                └──────────────────────┘
```

**Neden bu mimari?**
- **core/engine.py** hiçbir UI/bot bağımlılığı taşımaz — CLI, Discord, REST API; her yerden çağırılabilir.
- **api/worker.py** GPU'ya serialize erişim sağlar — aynı anda tek işlem, VRAM patlaması yok.
- **Bot çökmesi** Gradio'yu etkilemez; **Gradio çökmesi** botu etkilemez.
- Telegram botu ile web arayüzü aynı GPU kuyruğunu paylaşır — adil sıralama.

---

## 🔧 Sorun Giderme

**`Real-ESRGAN motoru bulunamadı` hatası**
→ `.env` içindeki `BASE_DIR` yolunu kontrol et. `realesrgan-ncnn-vulkan.exe` orada olmalı.

**`TELEGRAM_TOKEN .env dosyasına yazılmamış` hatası**
→ `.env.example`'ı kopyalayıp `.env` oluştur ve token'ı doldur.

**`numpy` ile ilgili import hataları**
→ `pip install "numpy<2"` ile düzelt. `requirements.txt` zaten pinli ama bazen PyTorch bozabilir.

**GFPGAN modeli indirilmiyor**
→ [Buradan](https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth) manuel indir, `BASE_DIR/gfpgan/weights/` altına koy.

**Gradio'ya dışarıdan erişmek istiyorum**
→ `.env` içinde `GRADIO_HOST=0.0.0.0` yap. Güvenlik için VPN veya reverse proxy kullan.

---

## 📄 Lisans

MIT License. Detaylar için `LICENSE` dosyasına bak.

---

## 🙏 Teşekkürler

- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — Xintao Wang
- [GFPGAN](https://github.com/TencentARC/GFPGAN) — TencentARC
- [NCNN](https://github.com/Tencent/ncnn) — Tencent
